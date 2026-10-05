"""Categorical charts: bars and pies."""

from __future__ import annotations

import numpy as np

from results.figure_builder.core.common import (
    add_legend, item_exprs, item_label, legend_kwargs, panel_palette, resolve_groups,
    style_axes)
from results.figure_builder.core.expressions import ExpressionError, evaluate, pretty, split_list
from results.figure_builder.core.stats import draw_brackets, run_tests


def draw_bar(fig, ax, panel, table, report, style):
    """Grouped, stacked or horizontal bars: clusters per group, bars per value."""
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
    stacked = bool(panel.get('stacked')) and len(exprs) > 1
    pal = panel_palette(panel)
    width = 0.8 if stacked else 0.8 / len(exprs)
    positions = np.arange(len(groups), dtype=float)
    per_group_values = [np.array([]) for _ in groups]
    bottoms = np.zeros(len(groups))
    for k, expr in enumerate(exprs):
        v = evaluate(expr, table)
        heights, errs = [], []
        for gi, g in enumerate(groups):
            vals = v[g.mask & np.isfinite(v)]
            if panel.get('drop_zeros', True) and agg in ('mean', 'median'):
                vals = vals[vals != 0]
            if k == 0:
                per_group_values[gi] = vals
            if agg == 'count':
                heights.append(float(vals.size))
                errs.append(0.0)
                continue
            if agg == 'sum':
                heights.append(float(vals.sum()) if vals.size else 0.0)
                errs.append(0.0)
                continue
            if vals.size == 0:
                heights.append(np.nan)
                errs.append(0.0)
                continue
            centre = float(np.median(vals) if agg == 'median' else np.mean(vals))
            heights.append(centre)
            sd = float(np.std(vals, ddof=1)) if vals.size > 1 else 0.0
            errs.append({'sd': sd, 'sem': sd / np.sqrt(vals.size),
                         'ci95': 1.96 * sd / np.sqrt(vals.size)}.get(err, 0.0))
        offs = positions if stacked else positions - 0.4 + width * (k + 0.5)
        if len(exprs) == 1:
            colors = [g.color for g in groups]
            label = None
        else:
            colors = pal[k % len(pal)]
            label = pretty(expr, table, style)
        show_err = agg in ('mean', 'median') and err != 'none' and not stacked
        heights = np.asarray(heights, dtype=float)
        kw = dict(color=colors, label=label, zorder=2,
                  edgecolor=panel.get('edge_color') if float(panel.get('edge_width') or 0) > 0 else None,
                  linewidth=float(panel.get('edge_width') or 0),
                  error_kw={'elinewidth': 1, 'ecolor': '#333333'},
                  capsize=3 if show_err else 0)
        if horizontal:
            ax.barh(offs, heights, height=width * 0.92, left=bottoms if stacked else None,
                    xerr=errs if show_err else None, **kw)
        else:
            ax.bar(offs, heights, width=width * 0.92, bottom=bottoms if stacked else None,
                   yerr=errs if show_err else None, **kw)
        if stacked:
            bottoms = bottoms + np.nan_to_num(heights)
    names = [g.label for g in groups]
    if horizontal:
        ax.set_yticks(positions)
        ax.set_yticklabels(names)
        ax.invert_yaxis()
        if log:
            ax.set_xscale('log')
    else:
        ax.set_xticks(positions)
        ax.set_xticklabels(names)
        if log:
            ax.set_yscale('log')
    report.counts[panel['id']] = int(sum(v.size for v in per_group_values))
    vlab = {'count': 'Particle count', 'sum': 'Sum', 'median': 'Median', 'mean': 'Mean'}[agg]
    if len(exprs) == 1 and agg != 'count':
        vlab = f'{vlab} {pretty(exprs[0], table, style)}'
    style_axes(ax, panel, table, style, swap=horizontal)
    if not panel.get('y_label'):
        (ax.set_xlabel if horizontal else ax.set_ylabel)(vlab)
    if len(exprs) == 1 and agg in ('mean', 'median') and not horizontal:
        pairs, lines = run_tests([(g.label, v) for g, v in zip(groups, per_group_values)], panel)
        report.stats.extend(lines)
        draw_brackets(ax, pairs, list(positions), panel)
    add_legend(ax, panel)


def draw_pie(fig, ax, panel, table, report, style):
    """Pie or donut of particle counts per group, or of summed values."""
    pal = panel_palette(panel)
    if panel.get('pie_mode') == 'values':
        exprs = split_list(panel.get('value'))
        if not exprs:
            raise ExpressionError('Set the Value expressions to share out (comma separated)')
        base = np.zeros(len(table), dtype=bool)
        for g in resolve_groups(panel, table):
            base |= g.mask
        sizes, labels, colors = [], [], []
        for k, expr in enumerate(exprs):
            v = evaluate(expr, table)
            sizes.append(float(np.nansum(np.where(base & np.isfinite(v), v, 0))))
            labels.append(pretty(expr, table, style))
            colors.append(pal[k % len(pal)])
        report.counts[panel['id']] = int(base.sum())
    else:
        groups = resolve_groups(panel, table)
        sizes = [float(g.mask.sum()) for g in groups]
        labels = [g.label for g in groups]
        colors = [g.color for g in groups]
        report.counts[panel['id']] = int(sum(sizes))
    keep = [i for i, s in enumerate(sizes) if s > 0]
    if not keep:
        raise ExpressionError('Nothing to share out')
    sizes = [sizes[i] for i in keep]
    labels = [labels[i] for i in keep]
    colors = [colors[i] for i in keep]
    edge = panel.get('edge_color') or 'white'
    lw = float(panel.get('edge_width') or 0) or 2
    wedge = {'edgecolor': edge, 'linewidth': lw}
    if panel.get('donut'):
        wedge['width'] = 0.42
    wedges, _t, autotexts = ax.pie(
        sizes, colors=colors, autopct=lambda pct: f'{pct:.1f}%' if pct >= 3 else '',
        startangle=90, counterclock=False, wedgeprops=wedge,
        pctdistance=0.79 if panel.get('donut') else 0.62, textprops={'fontsize': 'small'})
    from matplotlib import patheffects
    for t in autotexts:
        t._fb_cell = True
        t.set_color('#1f2937')
        t.set_fontweight('bold')
        t.set_path_effects([patheffects.withStroke(linewidth=2.5, foreground='white')])
    ax.set_aspect('equal')
    if panel.get('title'):
        ax.set_title(panel['title'])
    if panel.get('legend', True):
        total = float(sum(sizes))
        ax.legend(wedges, [f'{lab} ({100 * s / total:.1f}%)' for lab, s in zip(labels, sizes)],
                  handlelength=1.0, **legend_kwargs(panel, len(labels), 'below'))


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
