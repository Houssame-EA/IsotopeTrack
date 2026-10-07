"""Categorical charts: bars and pies."""

from __future__ import annotations

import numpy as np

from results.figure_builder.core.common import (
    add_legend, compact, count_label, draw_marks, handles, ink, item_exprs, item_label,
    legend_kwargs, panel_palette, particle_weights, resolve_groups, style_axes)
from results.figure_builder.core.expressions import ExpressionError, evaluate, pretty, split_list
from results.figure_builder.core.stats import draw_brackets, run_tests


BAR_SORTS = {'none': 'As listed', 'desc': 'Largest first', 'asc': 'Smallest first',
             'alpha': 'Alphabetical'}
"""Orders for the items along a bar chart's axis."""


def _bar_stat(vals, w, agg, err, drop_zeros, n_group, w_group):
    """Height and error of one bar."""
    if agg in ('detect', 'detect_pct'):
        hit = vals > 0
        total = float(np.sum(w[hit])) if w is not None else float(np.count_nonzero(hit))
        if agg == 'detect_pct':
            denom = w_group if w is not None else n_group
            return (100.0 * total / denom if denom else np.nan), 0.0
        return total, 0.0
    if agg == 'count':
        return (float(np.sum(w)) if w is not None else float(vals.size)), 0.0
    if agg == 'sum':
        return (float(vals.sum()) if vals.size else 0.0), 0.0
    if drop_zeros:
        vals = vals[vals != 0]
    if vals.size == 0:
        return np.nan, 0.0
    centre = float(np.median(vals) if agg == 'median' else np.mean(vals))
    sd = float(np.std(vals, ddof=1)) if vals.size > 1 else 0.0
    return centre, {'sd': sd, 'sem': sd / np.sqrt(vals.size), 'ci95': 1.96 * sd / np.sqrt(vals.size)}.get(err, 0.0)


def draw_bar(fig, ax, panel, table, report, style):
    """Grouped, stacked or horizontal bars: one value per group and expression.

    The value can be a mean, median or sum, a particle count or, as in the
    Bar Chart node, the number (or %) of particles in which each isotope is
    detected. ``bar_swap`` puts the expressions on the axis with one bar per
    group (the node's "grouped bars" layout).
    """
    exprs = split_list(panel.get('value'))
    if not exprs:
        raise ExpressionError('Set one or more Value expressions (comma separated)')
    groups = resolve_groups(panel, table)
    if not groups:
        raise ExpressionError('Every group is hidden')
    agg = panel.get('agg', 'mean')
    err = panel.get('error', 'sd')
    log = bool(panel.get('log_y'))
    horizontal = bool(panel.get('horizontal'))
    swap = bool(panel.get('bar_swap'))
    pal = panel_palette(panel)
    counted = agg in ('count', 'detect', 'detect_pct')
    w_all = particle_weights(panel, table) if (counted and panel.get('per_ml')) else None
    H = np.full((len(exprs), len(groups)), np.nan)
    ERR = np.zeros_like(H)
    per_group_values = [np.array([]) for _ in groups]
    for k, expr in enumerate(exprs):
        v = evaluate(expr, table)
        for gi, g in enumerate(groups):
            m = g.mask & np.isfinite(v)
            vals = v[m]
            w = w_all[m] if w_all is not None else None
            if k == 0:
                keep = vals[vals != 0] if (panel.get('drop_zeros', True) and agg in ('mean', 'median')) else vals
                per_group_values[gi] = keep
            n_group = int(g.mask.sum())
            w_group = float(np.sum(w_all[g.mask])) if w_all is not None else None
            H[k, gi], ERR[k, gi] = _bar_stat(vals, w, agg, err, panel.get('drop_zeros', True) and
                                             agg in ('mean', 'median'), n_group, w_group)
    item_names = [pretty(e, table, style) for e in exprs]
    item_names = [(panel.get('item_labels') or {}).get(e) or n for e, n in zip(exprs, item_names)]
    min_n = float(panel.get('min_count') or 0)
    keep_items = list(range(len(exprs)))
    if min_n and counted:
        keep_items = [k for k in keep_items if np.nansum(H[k]) >= min_n]
        if not keep_items:
            raise ExpressionError(f'No bar reaches the minimum of {min_n:g}')
    how = panel.get('sort_items') or 'none'
    if how in ('asc', 'desc'):
        keep_items.sort(key=lambda k: np.nansum(H[k]) * (-1 if how == 'desc' else 1))
    elif how == 'alpha':
        keep_items.sort(key=lambda k: str(item_names[k]).lower())
    H, ERR = H[keep_items], ERR[keep_items]
    exprs = [exprs[k] for k in keep_items]
    item_names = [item_names[k] for k in keep_items]
    if swap:
        cats, series = item_names, [(g.label, g.color) for g in groups]
    else:
        cats = [g.label for g in groups]
        series = [(name, pal[k % len(pal)]) for k, name in enumerate(item_names)]
        H, ERR = H.T, ERR.T
    n_series = H.shape[1]
    stacked = bool(panel.get('stacked')) and n_series > 1
    width = 0.8 if stacked else 0.8 / n_series
    positions = np.arange(len(cats), dtype=float)
    bottoms = np.zeros(len(cats))
    show_err = agg in ('mean', 'median') and err != 'none' and not stacked
    edge = float(panel.get('edge_width') or 0)
    for k in range(n_series):
        heights = H[:, k]
        offs = positions if stacked else positions - 0.4 + width * (k + 0.5)
        if n_series == 1 and not swap:
            colors, label = [g.color for g in groups], None
        else:
            colors, label = series[k][1], series[k][0]
        kw = dict(color=colors, label=label, zorder=2,
                  edgecolor=panel.get('edge_color') if edge > 0 else None, linewidth=edge,
                  error_kw={'elinewidth': 1, 'ecolor': '#333333'}, capsize=3 if show_err else 0)
        if horizontal:
            bars = ax.barh(offs, heights, height=width * 0.92, left=bottoms if stacked else None,
                           xerr=ERR[:, k] if show_err else None, **kw)
        else:
            bars = ax.bar(offs, heights, width=width * 0.92, bottom=bottoms if stacked else None,
                          yerr=ERR[:, k] if show_err else None, **kw)
        if panel.get('bar_values') and not stacked:
            _label_bars(ax, bars, heights, horizontal, agg, bool(panel.get('per_ml')))
        if stacked:
            bottoms = bottoms + np.nan_to_num(heights)
    if panel.get('bar_values') and stacked:
        for p, tot in zip(positions, bottoms):
            _value_text(ax, p, tot, horizontal, agg, bool(panel.get('per_ml')))
    if swap:
        info = [f'{name}\n' + '\n'.join(f'{g.label}: {_fmt_bar(H[i, gi], agg)}' for gi, g in enumerate(groups))
                for i, name in enumerate(cats)]
        handles(report, panel)['bar_info'] = {'axis': 'y' if horizontal else 'x',
                                              'positions': list(positions), 'texts': info}
    else:
        handles(report, panel)['categories'] = {
            'axis': 'y' if horizontal else 'x', 'positions': list(positions),
            'items': [(g.label, v) for g, v in zip(groups, per_group_values)]}
    if horizontal:
        ax.set_yticks(positions)
        ax.set_yticklabels(cats)
        ax.invert_yaxis()
        if log:
            ax.set_xscale('log')
    else:
        ax.set_xticks(positions)
        ax.set_xticklabels(cats)
        if log:
            ax.set_yscale('log')
    report.counts[panel['id']] = int(sum(int(g.mask.sum()) for g in groups))
    vlab = {'count': count_label(panel), 'sum': 'Sum', 'median': 'Median', 'mean': 'Mean',
            'detect': count_label(panel, 'Particles detected'),
            'detect_pct': 'Detected in (% of particles)'}[agg]
    if len(exprs) == 1 and agg in ('sum', 'median', 'mean'):
        vlab = f'{vlab} {pretty(exprs[0], table, style)}'
    style_axes(ax, panel, table, style, swap=horizontal)
    from matplotlib.ticker import NullLocator
    (ax.yaxis if horizontal else ax.xaxis).set_minor_locator(NullLocator())
    if not panel.get('y_label'):
        (ax.set_xlabel if horizontal else ax.set_ylabel)(vlab)
    if not horizontal:
        draw_marks(ax, panel, [], vertical=False)
    if len(exprs) == 1 and agg in ('mean', 'median') and not horizontal and not swap:
        pairs, lines = run_tests([(g.label, v) for g, v in zip(groups, per_group_values)], panel)
        report.stats.extend(lines)
        draw_brackets(ax, pairs, list(positions), panel)
    add_legend(ax, panel)


def _fmt_bar(v, agg) -> str:
    if not np.isfinite(v):
        return '–'
    if agg == 'detect_pct':
        return f'{v:.0f}%' if v >= 10 else f'{v:.1f}%'
    if agg in ('count', 'detect') and float(v).is_integer():
        return f'{int(v):,}'
    return f'{v:.3g}'


def _value_text(ax, pos, value, horizontal, agg, per_ml):
    if not np.isfinite(value) or value == 0:
        return
    txt = compact(value) if per_ml else _fmt_bar(value, agg)
    if horizontal:
        t = ax.annotate(txt, (value, pos), xytext=(3, 0), textcoords='offset points', ha='left',
                        va='center', fontsize='x-small', color=ink('#374151'))
    else:
        t = ax.annotate(txt, (pos, value), xytext=(0, 2), textcoords='offset points', ha='center',
                        va='bottom', fontsize='x-small', color=ink('#374151'))
    t._fb_cell = True


def _label_bars(ax, bars, heights, horizontal, agg, per_ml):
    """Write each bar's value at its end."""
    for b, h in zip(bars, heights):
        pos = b.get_y() + b.get_height() / 2 if horizontal else b.get_x() + b.get_width() / 2
        _value_text(ax, pos, h, horizontal, agg, per_ml)


PIE_MODES = {
    'groups': 'Particle count per group',
    'values': 'Share of the Value list (summed amounts)',
    'detect': 'Particles containing each isotope',
    'combinations': 'Element combinations',
    'single_multi': 'Single- vs multi-element particles',
    'sunburst': 'Main element, then what it comes with (sunburst)',
}
"""What the slices of a pie chart represent."""

PIE_LABELS = {'pct': 'Percent', 'name_pct': 'Name and percent', 'count_pct': 'Count and percent',
              'all': 'Name, count and percent', 'none': 'No labels'}
"""What is written on each slice."""


def _pie_items(panel, table, style):
    """``(labels, sizes, colors, n_particles, counted)`` for the chosen pie mode."""
    pal = panel_palette(panel)
    mode = panel.get('pie_mode', 'groups')
    groups = resolve_groups(panel, table)
    base = np.zeros(len(table), dtype=bool)
    for g in groups:
        base |= g.mask
    w = particle_weights(panel, table)
    names = panel.get('item_labels') or {}
    if mode == 'values':
        exprs = split_list(panel.get('value'))
        if not exprs:
            raise ExpressionError('Set the Value expressions to share out (comma separated)')
        sizes, labels, colors = [], [], []
        for k, expr in enumerate(exprs):
            v = evaluate(expr, table)
            sizes.append(float(np.nansum(np.where(base & np.isfinite(v), v, 0))))
            labels.append(names.get(expr) or pretty(expr, table, style))
            colors.append(pal[k % len(pal)])
        return labels, sizes, colors, int(base.sum()), False
    if mode == 'detect':
        exprs = item_exprs(panel, table)
        sizes, labels, colors = [], [], []
        for k, expr in enumerate(exprs):
            v = np.nan_to_num(evaluate(expr, table), nan=0.0)
            sizes.append(float(np.sum(w[base & (v > 0)])))
            labels.append(names.get(expr) or item_label(panel, expr, table, style, short=True))
            colors.append(pal[k % len(pal)])
        return labels, sizes, colors, int(base.sum()), True
    if mode in ('combinations', 'single_multi'):
        from results.figure_builder.charts.matrices import combination_keys
        exprs = item_exprs(panel, table)
        keys, _v = combination_keys(table, exprs, base)
        keep = base & (keys != '') & (keys != 'none')
        if mode == 'single_multi':
            single = keep & np.array([' + ' not in str(k) for k in keys])
            multi = keep & ~single
            return (['Single element', 'Multiple elements'],
                    [float(np.sum(w[single])), float(np.sum(w[multi]))],
                    [pal[0], pal[1 % len(pal)]], int(keep.sum()), True)
        uniq = list(dict.fromkeys(keys[keep].tolist()))
        sizes = [float(np.sum(w[keep & (keys == u)])) for u in uniq]
        order = np.argsort(-np.asarray(sizes), kind='stable')
        top = max(1, int(panel.get('top_n') or 8))
        labels = [names.get(uniq[i]) or uniq[i] for i in order[:top]]
        out_sizes = [sizes[i] for i in order[:top]]
        rest = float(sum(sizes[i] for i in order[top:]))
        colors = [pal[k % len(pal)] for k in range(len(labels))]
        if rest > 0:
            labels.append('Others')
            out_sizes.append(rest)
            colors.append('#c4c8cf')
        return labels, out_sizes, colors, int(keep.sum()), True
    sizes = [float(np.sum(w[g.mask])) for g in groups]
    return [g.label for g in groups], sizes, [g.color for g in groups], int(base.sum()), True


def _merge_small(labels, sizes, colors, pct):
    """Put every slice under ``pct`` % into one grey "Others" slice."""
    total = float(sum(sizes))
    if not pct or pct <= 0 or total <= 0:
        return labels, sizes, colors
    out = [(lab, s, c) for lab, s, c in zip(labels, sizes, colors) if 100 * s / total >= pct and lab != 'Others']
    small = total - sum(s for _l, s, _c in out)
    if small > 0:
        out.append(('Others', small, '#c4c8cf'))
    return [o[0] for o in out], [o[1] for o in out], [o[2] for o in out]


def draw_pie(fig, ax, panel, table, report, style):
    """Pie or donut of groups, summed values, detections or element combinations.

    Small slices can be merged into "Others"; labels can show names, counts
    (or particles per mL) and percentages, inside the slices or outside with
    leader lines.
    """
    if panel.get('pie_mode') == 'sunburst':
        draw_sunburst(ax, panel, table, report)
        return
    labels, sizes, colors, n, counted = _pie_items(panel, table, style)
    report.counts[panel['id']] = n
    keep = [i for i, sz in enumerate(sizes) if sz > 0]
    if not keep:
        raise ExpressionError('Nothing to share out')
    labels = [labels[i] for i in keep]
    sizes = [sizes[i] for i in keep]
    colors = [colors[i] for i in keep]
    labels, sizes, colors = _merge_small(labels, sizes, colors, float(panel.get('other_pct') or 0))
    per_ml = counted and bool(panel.get('per_ml'))
    total_size = float(sum(sizes))

    def amount(sz):
        if per_ml:
            return f'{compact(sz)}/mL'
        return f'{int(round(sz)):,}' if counted else f'{sz:.3g}'

    style_key = panel.get('pie_labels', 'pct')
    outside = panel.get('pie_label_pos') == 'outside'

    def slice_text(k):
        pct = 100 * sizes[k] / total_size
        if style_key == 'none' or (pct < 3 and not outside):
            return ''
        parts = {'pct': [f'{pct:.1f}%'], 'name_pct': [labels[k], f'{pct:.1f}%'],
                 'count_pct': [amount(sizes[k]), f'{pct:.1f}%'],
                 'all': [labels[k], amount(sizes[k]), f'{pct:.1f}%']}.get(style_key, [f'{pct:.1f}%'])
        return '\n'.join(parts)

    wedge = {'edgecolor': 'white', 'linewidth': max(1.5, float(panel.get('edge_width') or 0))}
    donut = bool(panel.get('donut'))
    if donut:
        wedge['width'] = 0.42
    explode = [float(panel.get('pie_explode') or 0)] * len(sizes)
    wedges, _t = ax.pie(sizes, colors=colors, startangle=float(panel.get('start_angle', 90) or 0),
                        counterclock=False, wedgeprops=wedge, explode=explode,
                        textprops={'fontsize': 'small'})
    from matplotlib import patheffects
    for k, w_ in enumerate(wedges):
        txt = slice_text(k)
        if not txt:
            continue
        ang = np.deg2rad((w_.theta1 + w_.theta2) / 2)
        if outside:
            r = 1.0 + float(panel.get('pie_explode') or 0)
            x, y = np.cos(ang), np.sin(ang)
            t = ax.annotate(txt, xy=(r * x, r * y), xytext=(1.28 * x, 1.22 * y),
                            ha='left' if x >= 0 else 'right', va='center', fontsize='small',
                            arrowprops={'arrowstyle': '-', 'color': '#9ca3af', 'lw': 0.8,
                                        'connectionstyle': 'arc3,rad=0'})
        else:
            r = (0.79 if donut else 0.62) + float(panel.get('pie_explode') or 0)
            t = ax.text(r * np.cos(ang), r * np.sin(ang), txt, ha='center', va='center', fontsize='small',
                        color='#1f2937', fontweight='bold',
                        path_effects=[patheffects.withStroke(linewidth=2.5, foreground='white')])
        t._fb_cell = True
    handles(report, panel)['wedges'] = [(w_, lab, sz, 100 * sz / total_size)
                                        for w_, lab, sz in zip(wedges, labels, sizes)]
    centre = (panel.get('donut_text') or '').strip()
    if donut and centre:
        centre = centre.replace('{n}', f'{n:,}').replace('{total}', amount(total_size))
        t = ax.text(0, 0, centre, ha='center', va='center', fontsize='medium', fontweight='bold',
                    color=ink('#1f2937'))
        t._fb_cell = True
    ax.set_aspect('equal')
    if outside:
        ax.set_xlim(-1.6, 1.6)
        ax.set_ylim(-1.45, 1.45)
    if panel.get('title'):
        ax.set_title(panel['title'])
    mode = panel.get('pie_mode', 'groups')
    if mode in ('detect', 'combinations', 'single_multi'):
        report.stats.append(f'Pie ({PIE_MODES[mode].lower()}): ' + ', '.join(
            f'{lab} {amount(sz)} ({100 * sz / total_size:.1f}%)' for lab, sz in zip(labels, sizes)))
    if panel.get('legend', True):
        kw = legend_kwargs(panel, len(labels), 'below')
        custom = kw.pop('_custom', False)
        leg = ax.legend(wedges, [f'{lab} ({100 * sz / total_size:.1f}%)' for lab, sz in zip(labels, sizes)],
                        handlelength=1.0, **kw)
        leg._fb_custom = custom


def draw_combinations(fig, ax, panel, table, report, style):
    """Most frequent element combinations (which isotopes occur together in a particle)."""
    from results.figure_builder.charts.matrices import combination_keys
    exprs = item_exprs(panel, table)
    if not exprs:
        raise ExpressionError('List isotopes or expressions to combine')
    groups = resolve_groups(panel, table)
    if not groups:
        raise ExpressionError('Every group is hidden')
    base = np.zeros(len(table), dtype=bool)
    for g in groups:
        base |= g.mask
    keys, _values = combination_keys(table, exprs, base)
    keys = np.where(base, keys, '')
    filt = panel.get('combo_filter', 'all')
    n_parts = np.array([0 if not k or k == 'none' else k.count(' + ') + 1 for k in keys])
    keep = base & (keys != 'none')
    if filt == 'single':
        keep &= n_parts == 1
    elif filt == 'multi':
        keep &= n_parts >= 2
    uniq, counts = np.unique(keys[keep], return_counts=True)
    if uniq.size == 0:
        raise ExpressionError('No particles with these isotopes')
    top = [uniq[i] for i in np.argsort(-counts)[:max(1, int(panel.get('top_n') or 15))]]
    percent = bool(panel.get('as_percent', True))
    horizontal = bool(panel.get('horizontal'))
    width = 0.8 / len(groups)
    pos = np.arange(len(top), dtype=float)
    for gi, g in enumerate(groups):
        gk = keys[g.mask & keep]
        total = max(1, int((g.mask & keep).sum()))
        vals = np.array([np.count_nonzero(gk == t) for t in top], dtype=float)
        if percent:
            vals = 100.0 * vals / total
        offs = pos - 0.4 + width * (gi + 0.5)
        label = g.label if len(groups) > 1 else None
        if horizontal:
            bars = ax.barh(offs, vals, height=width * 0.9, color=g.color, label=label, zorder=2)
        else:
            bars = ax.bar(offs, vals, width=width * 0.9, color=g.color, label=label, zorder=2)
        if panel.get('annotate', True) and len(groups) == 1:
            for b, v in zip(bars, vals):
                txt = f'{v:.1f}%' if percent else f'{int(v)}'
                if horizontal:
                    t = ax.text(b.get_width(), b.get_y() + b.get_height() / 2, f' {txt}',
                                va='center', ha='left', fontsize='x-small')
                else:
                    t = ax.text(b.get_x() + b.get_width() / 2, b.get_height(), txt,
                                va='bottom', ha='center', fontsize='x-small')
                t._fb_cell = True
    names = [(panel.get('item_labels') or {}).get(t) or t for t in top]
    vlab = '% of particles' if percent else 'Particles'
    if horizontal:
        ax.set_yticks(pos)
        ax.set_yticklabels(names)
        ax.invert_yaxis()
        ax.set_xlabel(panel.get('x_label') or vlab)
        if panel.get('y_label'):
            ax.set_ylabel(panel['y_label'])
        if panel.get('log_y'):
            ax.set_xscale('log')
    else:
        ax.set_xticks(pos)
        ax.set_xticklabels(names, rotation=float(panel.get('xtick_rotation') or 45),
                           ha='right', rotation_mode='anchor')
        ax.set_ylabel(panel.get('y_label') or vlab)
        if panel.get('x_label'):
            ax.set_xlabel(panel['x_label'])
        if panel.get('log_y'):
            ax.set_yscale('log')
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    if panel.get('grid'):
        ax.grid(True, axis='x' if horizontal else 'y', color='#e5e5e5', lw=0.6, zorder=0)
    if panel.get('title'):
        ax.set_title(panel['title'])
    report.counts[panel['id']] = int(keep.sum())
    add_legend(ax, panel)


def draw_composition(fig, ax, panel, table, report, style):
    """100% stacked bars: the share of each isotope in every group."""
    exprs = item_exprs(panel, table)
    if not exprs:
        raise ExpressionError('List isotopes or expressions to share out')
    groups = resolve_groups(panel, table)
    if not groups:
        raise ExpressionError('Every group is hidden')
    values = np.vstack([np.clip(np.nan_to_num(evaluate(e, table), nan=0.0), 0, None)
                        for e in exprs])
    mode = panel.get('comp_mode', 'mean_fraction')
    shares = []
    for g in groups:
        sub = values[:, g.mask]
        tot = sub.sum(axis=0)
        if mode == 'total':
            s = sub.sum(axis=1)
            s = 100.0 * s / s.sum() if s.sum() > 0 else np.zeros(len(exprs))
        else:
            ok = tot > 0
            frac = np.divide(sub[:, ok], tot[ok])
            s = 100.0 * frac.mean(axis=1) if ok.any() else np.zeros(len(exprs))
        shares.append(s)
    S = np.array(shares)
    pal = panel_palette(panel)
    horizontal = bool(panel.get('horizontal'))
    pos = np.arange(len(groups), dtype=float)
    left = np.zeros(len(groups))
    for k, e in enumerate(exprs):
        name = item_label(panel, e, table, style, short=True)
        color = pal[k % len(pal)]
        if horizontal:
            bars = ax.barh(pos, S[:, k], left=left, height=0.75, color=color, label=name,
                           edgecolor='white', linewidth=0.6, zorder=2)
        else:
            bars = ax.bar(pos, S[:, k], bottom=left, width=0.75, color=color, label=name,
                          edgecolor='white', linewidth=0.6, zorder=2)
        if panel.get('annotate', True):
            pos_ax = ax.get_position()
            span_in = (pos_ax.width * fig.get_figwidth()) if horizontal else (pos_ax.height * fig.get_figheight())
            for b, v, l0 in zip(bars, S[:, k], left):
                if v / 100.0 * span_in >= 0.32:
                    if horizontal:
                        t = ax.text(l0 + v / 2, b.get_y() + b.get_height() / 2, f'{v:.0f}%',
                                    ha='center', va='center', fontsize='x-small', color='white')
                    else:
                        t = ax.text(b.get_x() + b.get_width() / 2, l0 + v / 2, f'{v:.0f}%',
                                    ha='center', va='center', fontsize='x-small', color='white')
                    t._fb_cell = True
        left = left + S[:, k]
    labels = [f'{g.label}\n(n={int(g.mask.sum())})' if panel.get('show_n', True) else g.label
              for g in groups]
    what = 'Mean share (%)' if mode != 'total' else 'Share of total (%)'
    if horizontal:
        ax.set_yticks(pos)
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.set_xlabel(panel.get('x_label') or what)
    else:
        ax.set_xticks(pos)
        ax.set_xticklabels(labels)
        ax.set_ylim(0, 100)
        ax.set_ylabel(panel.get('y_label') or what)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    if panel.get('title'):
        ax.set_title(panel['title'])
    report.counts[panel['id']] = int(sum(int(g.mask.sum()) for g in groups))
    add_legend(ax, panel, default_loc='outside right', min_items=1)


def _lighter(color: str, amount: float) -> str:
    """Mix *color* with white by *amount* (0 keeps it, 1 gives white)."""
    from matplotlib.colors import to_hex, to_rgb
    r, g, b = to_rgb(color)
    return to_hex((r + (1 - r) * amount, g + (1 - g) * amount, b + (1 - b) * amount))


def sunburst_items(panel, table):
    """Group particles by main element, then by the elements they come with.

    The main element of a particle is the one with the largest mass when the
    data carry masses, otherwise the largest amount in the panel's quantity.
    Counts depend on each isotope's sensitivity, so mass is the fairer basis.

    Returns:
        ``(inner, outer, basis, n)``: ``inner`` is ``[(element, weight)]``
        largest first, ``outer`` maps each element to
        ``[(companions, weight)]`` largest first, ``basis`` names the
        quantity used and ``n`` is the number of particles counted.
    """
    from results.figure_builder.charts.matrices import combination_keys
    from results.figure_builder.core.expressions import split_symbol
    exprs = item_exprs(panel, table)
    if not exprs:
        raise ExpressionError('List the elements to include')
    base = np.zeros(len(table), dtype=bool)
    for g in resolve_groups(panel, table):
        base |= g.mask
    _keys, values = combination_keys(table, exprs, base)
    basis = 'the figure\'s quantity'
    mass_values = []
    for e in exprs:
        try:
            mass_values.append(np.nan_to_num(evaluate(f'mass:{e}', table), nan=0.0))
        except ExpressionError:
            mass_values = []
            break
    amounts = np.vstack(values)
    if mass_values and np.any(np.vstack(mass_values) > 0):
        amounts = np.vstack(mass_values)
        basis = 'mass'
    detected = np.vstack(values) > 0
    names = [split_symbol(e)[0] or e for e in exprs]
    has_any = base & detected.any(axis=0)
    main = np.argmax(np.where(detected, amounts, -np.inf), axis=0)
    w = particle_weights(panel, table)
    inner_totals: dict[str, float] = {}
    outer: dict[str, dict[str, float]] = {}
    for i in np.flatnonzero(has_any):
        m = int(main[i])
        el = names[m]
        mates = [names[c] for c in range(len(names)) if c != m and detected[c, i]]
        key = ('+ ' + ' + '.join(mates)) if mates else 'alone'
        inner_totals[el] = inner_totals.get(el, 0.0) + w[i]
        outer.setdefault(el, {})
        outer[el][key] = outer[el].get(key, 0.0) + w[i]
    inner = sorted(inner_totals.items(), key=lambda kv: -kv[1])
    ordered = {el: sorted(parts.items(), key=lambda kv: -kv[1]) for el, parts in outer.items()}
    return inner, ordered, basis, int(has_any.sum())


def draw_sunburst(ax, panel, table, report):
    """Two-ring pie: each particle's main element inside, its companions outside.

    The inner ring keeps the largest ``top_n`` main elements and merges the
    rest into "Others"; each outer ring keeps the ``sun_outer`` most common
    companion sets of that element and merges the rest into "other".
    """
    from matplotlib import patheffects
    from matplotlib.patches import Wedge
    inner, outer, basis, n = sunburst_items(panel, table)
    report.counts[panel['id']] = n
    if not inner:
        raise ExpressionError('No particle carries the listed elements')
    pal = panel_palette(panel)
    top = max(1, int(panel.get('top_n') or 8))
    keep_outer = max(1, int(panel.get('sun_outer') or 4))
    total = float(sum(v for _e, v in inner))
    shown = inner[:top]
    rest = float(sum(v for _e, v in inner[top:]))
    halo = [patheffects.withStroke(linewidth=2.5, foreground='white')]
    edge = {'edgecolor': 'white', 'linewidth': max(1.5, float(panel.get('edge_width') or 0))}
    start = float(panel.get('start_angle', 90) or 0)
    lines = []
    records = []
    for k, (el, weight) in enumerate(shown + ([('Others', rest)] if rest > 0 else [])):
        color = pal[k % len(pal)] if el != 'Others' else '#c4c8cf'
        span = 360.0 * weight / total
        w_in = Wedge((0, 0), 0.58, start - span, start, width=0.32, facecolor=color, **edge)
        ax.add_patch(w_in)
        records.append((w_in, el, weight, 100 * weight / total))
        mid = np.deg2rad(start - span / 2)
        if span >= 12:
            t = ax.text(0.42 * np.cos(mid), 0.42 * np.sin(mid), f'{el}\n{100 * weight / total:.0f}%',
                        ha='center', va='center', fontsize='small', fontweight='bold',
                        color='#1f2937', path_effects=halo)
            t._fb_cell = True
        parts = outer.get(el, []) if el != 'Others' else []
        kept = parts[:keep_outer]
        other = float(sum(v for _p, v in parts[keep_outer:]))
        if other > 0:
            kept = kept + [('other', other)]
        s2 = start
        for j, (mates, w2) in enumerate(kept):
            span2 = 360.0 * w2 / total
            shade = 0.25 + 0.5 * j / max(1, len(kept) - 1) if mates != 'other' else 0.85
            w_out = Wedge((0, 0), 1.0, s2 - span2, s2, width=0.4, facecolor=_lighter(color, shade), **edge)
            ax.add_patch(w_out)
            records.append((w_out, f'{el} {mates}', w2, 100 * w2 / total))
            m2 = np.deg2rad(s2 - span2 / 2)
            if span2 >= 9:
                t = ax.text(0.8 * np.cos(m2), 0.8 * np.sin(m2), mates, ha='center', va='center',
                            fontsize='x-small', color='#1f2937', path_effects=halo)
                t._fb_cell = True
            s2 -= span2
        if parts:
            lines.append(f'{el} {100 * weight / total:.1f}% (' + ', '.join(
                f'{mates} {100 * w2 / weight:.0f}%' for mates, w2 in parts[:keep_outer]) + ')')
        start -= span
    handles(report, panel)['wedges'] = records
    ax.set_xlim(-1.08, 1.08)
    ax.set_ylim(-1.08, 1.08)
    ax.set_aspect('equal')
    ax.axis('off')
    if panel.get('title'):
        ax.set_title(panel['title'])
    report.stats.append(f'Sunburst, main element by {basis}: ' + '; '.join(lines))
