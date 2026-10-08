"""Even more charts: ECDF, lollipop / dumbbell, particle timeline and treemap."""

from __future__ import annotations

import numpy as np

from results.figure_builder.core.common import (
    add_legend, base_mask, bin_edges, finite_mask, handles, ink, item_exprs, item_label, label_n,
    legend_kwargs, nonzero_mask, panel_palette, resolve_groups, style_axes, value_groups)
from results.figure_builder.core.expressions import ExpressionError, evaluate, pretty

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
"""What a treemap shares out."""


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
    """``(labels, sizes, colors, n)`` for a treemap."""
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
