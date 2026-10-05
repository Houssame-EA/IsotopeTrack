"""Even more charts: UpSet, Q-Q, lollipop / dumbbell, particle timeline, waffle and treemap."""

from __future__ import annotations

import numpy as np

from results.figure_builder.core.common import (
    add_legend, base_mask, bin_edges, finite_mask, handles, ink, item_exprs, item_label, label_n,
    legend_kwargs, nonzero_mask, panel_palette, resolve_groups, style_axes, value_groups)
from results.figure_builder.core.expressions import ExpressionError, evaluate, pretty, split_symbol

LOLLI_STATS = {
    'median': 'Median', 'mean': 'Mean', 'detect': 'Detected in (% of particles)',
    'sum': 'Sum', 'count': 'Particles detected',
}
"""What a lollipop chart can show for each isotope."""

TIME_MODES = {
    'rate': 'Particles per second', 'cumulative': 'Cumulative particles',
    'signal': 'Value of every particle over time',
}
"""What a particle timeline can show."""

SHARE_MODES = {'groups': 'Particle count per group', 'combinations': 'Element combinations'}
"""What waffle and treemap charts share out."""


def _no_minor(axis):
    from matplotlib.ticker import NullLocator
    axis.set_minor_locator(NullLocator())


def _text_color(color) -> str:
    """Black or white, whichever reads better on ``color``."""
    from matplotlib.colors import to_rgb
    r, g, b = to_rgb(color)
    return '#111827' if 0.299 * r + 0.587 * g + 0.114 * b > 0.6 else '#ffffff'


def _combination_counts(panel, table):
    """Element combination of every kept particle, and the most frequent ones."""
    from results.figure_builder.charts.matrices import combination_keys
    exprs = item_exprs(panel, table)
    if len(exprs) < 2:
        raise ExpressionError('List at least two isotopes or expressions')
    groups = resolve_groups(panel, table)
    if not groups:
        raise ExpressionError('Every group is hidden')
    base = base_mask(panel, table)
    keys, _values = combination_keys(table, exprs, base)
    keys = np.where(base, keys, '')
    keep = base & (keys != '') & (keys != 'none')
    n_parts = np.array([0 if not k or k == 'none' else k.count(' + ') + 1 for k in keys])
    filt = panel.get('combo_filter', 'all')
    if filt == 'single':
        keep &= n_parts == 1
    elif filt == 'multi':
        keep &= n_parts >= 2
    uniq, counts = np.unique(keys[keep], return_counts=True)
    if uniq.size == 0:
        raise ExpressionError('No particles with these isotopes')
    order = np.argsort(-counts, kind='stable')
    return exprs, groups, keys, keep, [str(uniq[i]) for i in order], counts[order]


def draw_upset(fig, ax, panel, table, report, style):
    """UpSet plot: how many particles hold each element combination, with a dot matrix below."""
    exprs, groups, keys, keep, combos, _counts = _combination_counts(panel, table)
    top = combos[:max(1, int(panel.get('top_n') or 15))]
    names = []
    for e in exprs:
        sym, _mass = split_symbol(e)
        names.append(sym if sym else e)
    shown = [item_label(panel, e, table, style, short=True) for e in exprs]
    percent = bool(panel.get('as_percent'))
    total_kept = max(1, int(keep.sum()))
    pos = np.arange(len(top), dtype=float)
    bottom = np.zeros(len(top))
    width = 0.62
    for g in groups:
        gk = keys[g.mask & keep]
        vals = np.array([np.count_nonzero(gk == t) for t in top], dtype=float)
        if percent:
            vals = 100.0 * vals / total_kept
        ax.bar(pos, vals, bottom=bottom, width=width, color=g.color, zorder=2,
               label=g.label if len(groups) > 1 else None, edgecolor='white', linewidth=0.4)
        bottom += vals
    if panel.get('annotate', True):
        for p, v in zip(pos, bottom):
            t = ax.text(p, v, f'{v:.1f}%' if percent else f'{int(v):,}', ha='center', va='bottom',
                        fontsize='x-small', color=ink('#374151'))
            t._fb_cell = True
    ax.set_xlim(-0.6, len(top) - 0.4)
    ax.set_ylim(0, max(bottom.max() * 1.12, 1e-9))
    if panel.get('log_y'):
        ax.set_yscale('log')
        ax.set_ylim(bottom=max(0.5, bottom[bottom > 0].min() * 0.6))
    ax.set_xticks(pos)
    ax.tick_params(axis='x', which='both', bottom=False, labelbottom=False)
    ax.set_ylabel(panel.get('y_label') or ('% of particles' if percent else 'Particles'))
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    if panel.get('grid'):
        ax.grid(True, axis='y', color=panel.get('grid_color') or '#d9dde3', lw=0.6, zorder=0)
        ax.set_axisbelow(True)
    if panel.get('title'):
        ax.set_title(panel['title'])
    p = ax.get_position()
    rows = len(exprs)
    mat_h = p.height * min(0.55, 0.07 * rows + 0.08)
    gap = p.height * 0.02
    ax.set_position([p.x0, p.y0 + mat_h + gap, p.width, p.height - mat_h - gap])
    mat = fig.add_axes([p.x0, p.y0, p.width, mat_h], sharex=ax)
    mat.set_zorder(ax.get_zorder())
    mat.set_facecolor('none')
    for i in range(rows):
        if i % 2 == 0:
            mat.axhspan(i - 0.5, i + 0.5, color=ink('#111827'), alpha=0.05, zorder=0, lw=0)
    for j, combo in enumerate(top):
        parts = combo.split(' + ')
        present = [i for i, n in enumerate(names) if n in parts]
        absent = [i for i in range(rows) if i not in present]
        mat.scatter([j] * len(absent), absent, s=38, color=ink('#111827'), alpha=0.18, zorder=2, linewidths=0)
        if present:
            mat.plot([j, j], [min(present), max(present)], color=ink('#1f2937'), lw=2.2, zorder=3,
                     solid_capstyle='round')
            mat.scatter([j] * len(present), present, s=46, color=ink('#1f2937'), zorder=4, linewidths=0)
    det = np.vstack([np.nan_to_num(evaluate(e, table), nan=0.0) > 0 for e in exprs])
    sizes = (det & keep).sum(axis=1)
    mat.set_yticks(range(rows))
    mat.set_yticklabels([f'{s} ({n:,})' if panel.get('show_n', True) else s
                         for s, n in zip(shown, sizes)])
    mat.set_ylim(rows - 0.5, -0.5)
    mat.tick_params(axis='both', which='both', length=0)
    mat.tick_params(axis='x', labelbottom=False)
    _no_minor(mat.yaxis)
    _no_minor(ax.xaxis)
    for side in mat.spines.values():
        side.set_visible(False)
    hd = handles(report, panel)
    hd.setdefault('extra_axes', []).append(mat)
    hd['bar_info'] = {'axis': 'x', 'positions': list(pos),
                      'texts': [f'{t}\n{v:.1f}% of particles' if percent
                                else f'{t}\n{int(v):,} particles'
                                for t, v in zip(top, bottom)]}
    report.counts[panel['id']] = int(keep.sum())
    report.stats.append(f'UpSet: {len(combos)} combinations in {int(keep.sum()):,} particles; '
                        f'the most common is {top[0]}.')
    add_legend(ax, panel)


def draw_qq(fig, ax, panel, table, report, style):
    """Quantile-quantile plot against a normal or log-normal distribution, one set per group."""
    from scipy import stats
    groups = [(g, v) for g, v in value_groups(panel, table) if v.size >= 3]
    if not groups:
        raise ExpressionError('Need at least three finite values')
    dist = panel.get('qq_dist', 'lognormal')
    size = max(2.0, float(panel.get('marker_size') or 16) * 0.8)
    alpha = float(panel.get('alpha') or 0.75)
    total = 0
    lo_z, hi_z = np.inf, -np.inf
    for g, v in groups:
        if dist == 'lognormal':
            v = v[v > 0]
            if v.size < 3:
                continue
            t = np.log10(v)
        else:
            t = v
        t = np.sort(t)
        n = t.size
        total += n
        z = stats.norm.ppf((np.arange(1, n + 1) - 0.5) / n)
        ys = 10 ** t if dist == 'lognormal' else t
        ax.scatter(z, ys, s=size, color=g.color, alpha=alpha, linewidths=0, rasterized=True, zorder=3,
                   label=label_n(g, n, panel))
        q1, q3 = np.percentile(t, [25, 75])
        z1, z3 = stats.norm.ppf([0.25, 0.75])
        slope = (q3 - q1) / (z3 - z1) if z3 != z1 else 0.0
        icpt = q1 - slope * z1
        zz = np.array([z.min(), z.max()])
        line = icpt + slope * zz
        ax.plot(zz, 10 ** line if dist == 'lognormal' else line, color=g.color, lw=1.4, ls='--', zorder=4)
        lo_z, hi_z = min(lo_z, z.min()), max(hi_z, z.max())
        sub = t if n <= 5000 else np.random.default_rng(0).choice(t, 5000, replace=False)
        if np.ptp(sub) > 0:
            w, p = stats.shapiro(sub)
            what = 'log-normal' if dist == 'lognormal' else 'normal'
            report.stats.append(f'{g.label}: Shapiro–Wilk W = {w:.3f}, p = {p:.3g}, n = {n} '
                                f'({"consistent with" if p >= 0.05 else "differs from"} {what})')
    if total == 0:
        raise ExpressionError('No positive values for a log-normal Q-Q plot')
    if dist == 'lognormal':
        ax.set_yscale('log')
    report.counts[panel['id']] = total
    style_axes(ax, panel, table, style, '', panel['value'])
    if not panel.get('x_label'):
        ax.set_xlabel('Theoretical quantiles (standard normal)')
    if not panel.get('y_label') and dist == 'lognormal':
        ax.set_ylabel(pretty(panel['value'], table, style) + ' (log scale)')
    add_legend(ax, panel)


def _item_stat(v, mask, stat, drop_zeros):
    sel = v[mask & np.isfinite(v)]
    if stat == 'detect':
        return 100.0 * float((sel > 0).mean()) if sel.size else np.nan
    if stat == 'count':
        return float((sel > 0).sum())
    if stat == 'sum':
        return float(np.nansum(sel))
    if drop_zeros:
        sel = sel[sel > 0]
    if not sel.size:
        return np.nan
    return float(np.median(sel) if stat == 'median' else np.mean(sel))


def draw_lollipop(fig, ax, panel, table, report, style):
    """One value per isotope as a lollipop; two groups become a dumbbell, more a dot plot."""
    exprs = item_exprs(panel, table)
    if not exprs:
        raise ExpressionError('List isotopes or expressions')
    groups = resolve_groups(panel, table)
    if not groups:
        raise ExpressionError('Every group is hidden')
    stat = panel.get('lolli_stat', 'median')
    drop = bool(panel.get('drop_zeros', True))
    M = np.array([[_item_stat(evaluate(e, table), g.mask, stat, drop) for e in exprs] for g in groups])
    labels = [item_label(panel, e, table, style, short=True) for e in exprs]
    order = list(range(len(exprs)))
    if panel.get('lolli_sort', True):
        key = np.nan_to_num(np.nanmax(M, axis=0), nan=-np.inf)
        order = list(np.argsort(-key, kind='stable'))
    M = M[:, order]
    labels = [labels[i] for i in order]
    vertical = bool(panel.get('lolli_vertical'))
    log = bool(panel.get('log_y'))
    pos = np.arange(len(labels), dtype=float)
    size = max(20.0, float(panel.get('marker_size') or 16) * 3)
    lw = float(panel.get('line_width') or 1.6)

    def seg(p, a, b, **kw):
        if vertical:
            ax.plot([p, p], [a, b], **kw)
        else:
            ax.plot([a, b], [p, p], **kw)

    def dots(p, v, **kw):
        if vertical:
            ax.scatter(p, v, **kw)
        else:
            ax.scatter(v, p, **kw)

    finite = M[np.isfinite(M)]
    if not finite.size:
        raise ExpressionError('No values to show')
    floor = (finite[finite > 0].min() * 0.5 if (finite > 0).any() else 1.0) if log else 0.0
    if len(groups) == 1:
        g = groups[0]
        for p, v in zip(pos, M[0]):
            if np.isfinite(v):
                seg(p, floor, v, color=g.color, lw=lw + 0.4, zorder=2, solid_capstyle='round')
        dots(pos, M[0], s=size, color=g.color, zorder=3, edgecolors='white', linewidths=1.0)
    else:
        for k, p in enumerate(pos):
            col = M[:, k]
            ok = col[np.isfinite(col)]
            if ok.size >= 2:
                seg(p, ok.min(), ok.max(), color='#9ca3af', lw=lw + 1.6, zorder=2, solid_capstyle='round',
                    alpha=0.7)
        for gi, g in enumerate(groups):
            dots(pos, M[gi], s=size, color=g.color, zorder=3 + gi * 0.01, edgecolors='white',
                 linewidths=1.0, label=g.label)
    if panel.get('annotate', True) and len(groups) == 1:
        for p, v in zip(pos, M[0]):
            if not np.isfinite(v):
                continue
            txt = f'{v:.1f}%' if stat == 'detect' else f'{v:.3g}'
            if vertical:
                t = ax.annotate(txt, (p, v), xytext=(0, 8), textcoords='offset points', ha='center',
                                va='bottom', fontsize='x-small', color=ink('#374151'))
            else:
                t = ax.annotate(txt, (v, p), xytext=(8, 0), textcoords='offset points', ha='left',
                                va='center', fontsize='x-small', color=ink('#374151'))
            t._fb_cell = True
    value_label = LOLLI_STATS.get(stat, stat)
    if vertical:
        ax.set_xticks(pos)
        ax.set_xticklabels(labels)
        ax.set_xlim(-0.6, len(labels) - 0.4)
        if log:
            ax.set_yscale('log')
        elif np.nanmin(finite) >= 0:
            ax.set_ylim(bottom=0)
    else:
        ax.set_yticks(pos)
        ax.set_yticklabels(labels)
        ax.set_ylim(len(labels) - 0.4, -0.6)
        if log:
            ax.set_xscale('log')
        elif np.nanmin(finite) >= 0:
            ax.set_xlim(left=0)
    style_axes(ax, panel, table, style, swap=False)
    if vertical:
        _no_minor(ax.xaxis)
        if not panel.get('y_label'):
            ax.set_ylabel(value_label)
        ax.tick_params(axis='x', which='both', length=0)
    else:
        _no_minor(ax.yaxis)
        if not panel.get('x_label'):
            ax.set_xlabel(value_label)
        ax.tick_params(axis='y', which='both', length=0)
    if not panel.get('grid'):
        ax.grid(True, axis='y' if vertical else 'x', color='#eceff3', lw=0.6, zorder=0)
        ax.set_axisbelow(True)
    hd = handles(report, panel)
    hd['bar_info'] = {'axis': 'x' if vertical else 'y', 'positions': list(pos),
                      'texts': [label_text(lab, [(g.label, M[gi, k]) for gi, g in enumerate(groups)], stat)
                                for k, lab in enumerate(labels)]}
    report.counts[panel['id']] = int(base_mask(panel, table).sum())
    if len(groups) == 2:
        a, b = groups
        diffs = [f'{labels[k]}: {M[1, k] / M[0, k]:.2f}×' for k in range(len(labels))
                 if np.isfinite(M[0, k]) and np.isfinite(M[1, k]) and M[0, k] > 0]
        if diffs:
            report.stats.append(f'{b.label} / {a.label} ({value_label.lower()}): ' + ', '.join(diffs[:12]))
    add_legend(ax, panel)


def label_text(label, values, stat) -> str:
    """Hover text of one lollipop row."""
    lines = [str(label)]
    for name, v in values:
        if np.isfinite(v):
            lines.append(f'{name}: {v:.1f}%' if stat == 'detect' else f'{name}: {v:.4g}')
    return '\n'.join(lines)


def draw_timeline(fig, ax, panel, table, report, style):
    """Particles over acquisition time: event rate, cumulative count or each particle's value."""
    t = evaluate('time', table)
    groups = resolve_groups(panel, table)
    if not groups:
        raise ExpressionError('Every group is hidden')
    mode = panel.get('time_mode', 'rate')
    value = (panel.get('value') or '').strip()
    v = evaluate(value, table) if value else None
    ok = np.isfinite(t)
    if v is not None and mode != 'signal':
        ok &= np.nan_to_num(v, nan=0.0) > 0
    if not ok.any() or np.ptp(t[ok]) <= 0:
        raise ExpressionError('No particle times in this data')
    bins = max(2, int(panel.get('bins') or 40))
    edges = np.linspace(np.nanmin(t[ok]), np.nanmax(t[ok]), bins + 1)
    centres = (edges[:-1] + edges[1:]) / 2
    width = edges[1] - edges[0]
    lw = float(panel.get('line_width') or 1.6)
    total = 0
    if mode == 'signal':
        if v is None:
            raise ExpressionError('Set the Value expression to follow over time')
        log = bool(panel.get('log_y'))
        if log:
            ax.set_yscale('log')
        hover = handles(report, panel).setdefault('points', [])
        for g in groups:
            m = g.mask & ok & nonzero_mask(panel, v) & finite_mask(v, log_flags=(log,))
            if not m.any():
                continue
            total += int(m.sum())
            ax.scatter(t[m], v[m], s=max(2.0, float(panel.get('marker_size') or 16) * 0.5), color=g.color,
                       alpha=float(panel.get('alpha') or 0.75) * 0.7, linewidths=0, rasterized=True,
                       zorder=2, label=label_n(g, int(m.sum()), panel))
            hover.append({'x': t[m], 'y': v[m], 'index': np.flatnonzero(m), 'group': g.label,
                          'color': g.color})
            idx = np.clip(np.digitize(t[m], edges) - 1, 0, bins - 1)
            med = np.array([np.median(v[m][idx == b]) if np.count_nonzero(idx == b) >= 3 else np.nan
                            for b in range(bins)])
            from matplotlib import patheffects
            ax.plot(centres, med, color=g.color, lw=lw + 0.6, zorder=4,
                    path_effects=[patheffects.withStroke(linewidth=lw + 3, foreground='white')])
        hd = handles(report, panel)
        hd['x_name'], hd['y_name'], hd['table'] = 'time', value, table
        y_default = value
    else:
        for g in groups:
            m = g.mask & ok
            if not m.any():
                continue
            total += int(m.sum())
            counts, _ = np.histogram(t[m], edges)
            if mode == 'cumulative':
                y = np.cumsum(counts)
                ax.plot(edges[1:], y, color=g.color, lw=lw, zorder=3, label=label_n(g, int(m.sum()), panel),
                        drawstyle='steps-post')
            else:
                y = counts / width
                ax.fill_between(centres, y, step='mid', color=g.color, alpha=0.18, lw=0, zorder=2)
                ax.step(centres, y, where='mid', color=g.color, lw=lw, zorder=3,
                        label=label_n(g, int(m.sum()), panel))
                rate = m.sum() / max(1e-12, edges[-1] - edges[0])
                report.stats.append(f'{g.label}: {int(m.sum()):,} particles, mean rate {rate:.3g} per second')
        y_default = ''
        ax.set_ylim(bottom=0)
    if total == 0:
        raise ExpressionError('No particles to place on the time line')
    report.counts[panel['id']] = total
    style_axes(ax, panel, table, style, '', y_default)
    if not panel.get('x_label'):
        ax.set_xlabel('Time (s)')
    if mode != 'signal' and not panel.get('y_label'):
        what = TIME_MODES[mode]
        if v is not None:
            what += f' with {pretty(value, table, style)}'
        ax.set_ylabel(what)
    add_legend(ax, panel)


def _share_items(panel, table):
    """``(labels, sizes, colors)`` for waffle and treemap charts."""
    pal = panel_palette(panel)
    if panel.get('share_mode', 'groups') == 'combinations':
        _exprs, _groups, keys, keep, combos, counts = _combination_counts(panel, table)
        n = max(1, int(panel.get('top_n') or 8))
        labels = [(panel.get('item_labels') or {}).get(c) or c for c in combos[:n]]
        sizes = [float(c) for c in counts[:n]]
        rest = float(counts[n:].sum())
        colors = [pal[i % len(pal)] for i in range(len(labels))]
        if rest > 0:
            labels.append('Other')
            sizes.append(rest)
            colors.append('#c4c8cf')
        return labels, sizes, colors, int(keep.sum())
    groups = resolve_groups(panel, table)
    sizes = [float(g.mask.sum()) for g in groups]
    keep = [i for i, s in enumerate(sizes) if s > 0]
    if not keep:
        raise ExpressionError('Nothing to share out')
    return ([groups[i].label for i in keep], [sizes[i] for i in keep],
            [groups[i].color for i in keep], int(sum(sizes)))


def _legend_below(ax, panel, artists, labels, sizes):
    if not panel.get('legend', True):
        return
    total = float(sum(sizes)) or 1.0
    kw = legend_kwargs(panel, len(labels), 'below')
    custom = kw.pop('_custom', False)
    leg = ax.legend(artists, [f'{lab} ({100 * s / total:.1f}%)' for lab, s in zip(labels, sizes)],
                    handlelength=1.0, **kw)
    leg._fb_custom = custom


def _allocate(sizes, cells):
    """Whole cells per item by the largest-remainder method."""
    sizes = np.asarray(sizes, dtype=float)
    exact = sizes / sizes.sum() * cells
    whole = np.floor(exact).astype(int)
    for i in np.argsort(-(exact - whole))[:cells - whole.sum()]:
        whole[i] += 1
    return whole


def draw_waffle(fig, ax, panel, table, report, style):
    """Waffle chart: 100 squares shared out between groups or element combinations."""
    from matplotlib.patches import FancyBboxPatch
    labels, sizes, colors, n = _share_items(panel, table)
    cols = max(5, min(40, int(panel.get('waffle_cols') or 10)))
    rows = max(2, min(40, int(panel.get('waffle_rows') or 10)))
    cells = cols * rows
    alloc = _allocate(sizes, cells)
    total = float(sum(sizes))
    wedges = []
    firsts = []
    k = 0
    for item, count in enumerate(alloc):
        first = None
        for _ in range(count):
            r, c = divmod(k, cols)
            sq = FancyBboxPatch((c + 0.06, r + 0.06), 0.88, 0.88, boxstyle='round,pad=0,rounding_size=0.14',
                                facecolor=colors[item], edgecolor='none', zorder=2)
            ax.add_patch(sq)
            wedges.append((sq, labels[item], sizes[item], 100 * sizes[item] / total))
            first = first or sq
            k += 1
        firsts.append(first)
    ax.set_xlim(-0.1, cols + 0.1)
    ax.set_ylim(rows + 0.1, -0.1)
    ax.set_aspect('equal')
    ax.axis('off')
    if panel.get('title'):
        ax.set_title(panel['title'])
    handles(report, panel)['wedges'] = wedges
    report.counts[panel['id']] = n
    report.stats.append(f'Waffle: each square is {100 / cells:.2g}% of {int(total):,} particles.')
    shown = [(a, lab, s) for a, lab, s in zip(firsts, labels, sizes) if a is not None]
    _legend_below(ax, panel, [a for a, _l, _s in shown], [lab for _a, lab, _s in shown],
                  [s for _a, _l, s in shown])


def squarify(sizes, x, y, w, h):
    """Squarified treemap rectangles ``(x, y, w, h)`` for ``sizes`` sorted largest first."""
    values = [float(s) for s in sizes if s > 0]
    if not values:
        return []
    scale = w * h / sum(values)
    remaining = [v * scale for v in values]
    rects = []

    def worst(row, length):
        s = sum(row)
        return max(max(length ** 2 * r / s ** 2, s ** 2 / (length ** 2 * r)) for r in row)

    while remaining:
        length = min(w, h)
        row = [remaining[0]]
        i = 1
        while i < len(remaining) and worst(row + [remaining[i]], length) <= worst(row, length):
            row.append(remaining[i])
            i += 1
        s = sum(row)
        if w >= h:
            rw = s / h if h > 0 else 0
            cy = y
            for r in row:
                rh = r / rw if rw > 0 else 0
                rects.append((x, cy, rw, rh))
                cy += rh
            x += rw
            w -= rw
        else:
            rh = s / w if w > 0 else 0
            cx = x
            for r in row:
                rww = r / rh if rh > 0 else 0
                rects.append((cx, y, rww, rh))
                cx += rww
            y += rh
            h -= rh
        remaining = remaining[i:]
    return rects


def draw_treemap(fig, ax, panel, table, report, style):
    """Treemap: rectangles sized by particle count per group or element combination."""
    from matplotlib.patches import Rectangle
    labels, sizes, colors, n = _share_items(panel, table)
    order = np.argsort(-np.asarray(sizes), kind='stable')
    labels = [labels[i] for i in order]
    sizes = [sizes[i] for i in order]
    colors = [colors[i] for i in order]
    pos = ax.get_position()
    fig_w, fig_h = fig.get_figwidth(), fig.get_figheight()
    W, H = pos.width * fig_w, pos.height * fig_h
    rects = squarify(sizes, 0, 0, W, H)
    total = float(sum(sizes))
    wedges = []
    gap = min(W, H) * 0.006
    for (x, y, w, h), lab, s, c in zip(rects, labels, sizes, colors):
        rect = Rectangle((x + gap, y + gap), max(0, w - 2 * gap), max(0, h - 2 * gap), facecolor=c,
                         edgecolor='white', linewidth=1.2, zorder=2)
        ax.add_patch(rect)
        pct = 100 * s / total
        wedges.append((rect, lab, s, pct))
        if w > 0.45 and h > 0.28:
            fs = max(6.0, min(14.0, 5.0 + 3.2 * min(w, h * 1.6)))
            t = ax.text(x + w / 2, y + h / 2, f'{lab}\n{pct:.1f}%', ha='center', va='center',
                        fontsize=fs, color=_text_color(c), zorder=3, clip_on=True)
            t._fb_cell = True
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis('off')
    if panel.get('title'):
        ax.set_title(panel['title'])
    handles(report, panel)['wedges'] = wedges
    report.counts[panel['id']] = n
    if panel.get('legend', False):
        _legend_below(ax, panel, [w[0] for w in wedges], labels, sizes)


def draw_ecdf(fig, ax, panel, table, report, style):
    """Empirical cumulative distribution, one step curve per group, with the median marked."""
    groups = [(g, v) for g, v in value_groups(panel, table) if v.size]
    if not groups:
        raise ExpressionError('No finite values to plot')
    log = bool(panel.get('log_x'))
    if log:
        ax.set_xscale('log')
    lw = float(panel.get('line_width') or 1.6)
    for g, v in groups:
        s = np.sort(v)
        y = 100.0 * np.arange(1, s.size + 1) / s.size
        ax.step(np.r_[s[0], s], np.r_[0, y], where='post', color=g.color, lw=lw, zorder=3,
                label=label_n(g, s.size, panel))
        med = np.median(s)
        ax.plot([med, med], [0, 50], color=g.color, lw=0.9, ls=':', zorder=2)
    ax.axhline(50, color='#9ca3af', lw=0.8, ls='--', zorder=1)
    ax.set_ylim(0, 102)
    allv = np.concatenate([v for _g, v in groups])
    edges = bin_edges(allv, 4, log)
    ax.set_xlim(edges[0], edges[-1])
    report.counts[panel['id']] = int(allv.size)
    if len(groups) >= 2:
        from scipy import stats
        a, b = groups[0][1], groups[1][1]
        res = stats.ks_2samp(a, b)
        report.stats.append(f'ECDF: Kolmogorov–Smirnov {groups[0][0].label} vs {groups[1][0].label}: '
                            f'D = {res.statistic:.3f}, p = {res.pvalue:.3g}')
    style_axes(ax, panel, table, style, panel['value'], '')
    if not panel.get('y_label'):
        ax.set_ylabel('Cumulative % of particles')
    add_legend(ax, panel)
