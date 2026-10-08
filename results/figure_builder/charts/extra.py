"""More ways to look at particles: dot plots, ridgelines, hexbins, contours, radar and parallel coordinates."""

from __future__ import annotations

import warnings

import numpy as np

from results.figure_builder.core.common import (
    add_colorbar, add_legend, base_mask, cmap_name, draw_marks, draw_summary_box, finite_mask,
    handles, ink, item_exprs, item_label, label_n, nonzero_mask, resolve_groups, style_axes,
    value_groups)
from results.figure_builder.core.expressions import ExpressionError, evaluate
from results.figure_builder.core.stats import draw_brackets, run_tests


def _kde_on(values, grid):
    """Gaussian KDE of ``values`` evaluated on ``grid`` (flat when degenerate)."""
    from scipy import stats
    if values.size < 3 or np.ptp(values) == 0:
        return np.zeros_like(grid)
    return stats.gaussian_kde(values)(grid)


def _darker(color, factor=0.7):
    from matplotlib.colors import to_rgb
    r, g, b = to_rgb(color)
    return (r * factor, g * factor, b * factor)


STRIP_COLORS = {
    'rows': 'Same as the rows',
    'sample': 'Sample',
    'class': 'Classifier class',
    'rules': 'My rules',
    'combination': 'Element combination',
}
"""What the dots of a dot plot can be coloured by, independently of its rows."""

STRIP_SIZES = {'': 'All the same', 'n_elements': 'Number of elements detected'}
"""What the dot size of a dot plot can show."""


def strip_colour_groups(panel, table, mask):
    """Colour classes for a dot plot: ``[(label, color, particle_mask)]``.

    Rows come from the panel's grouping; the colour can follow another
    grouping (sample, class, rules) or each particle's element combination,
    whose most common ``top_n`` get their own colour and the rest are grey.
    """
    mode = panel.get('strip_color') or 'rows'
    if mode == 'rows':
        return []
    if mode == 'combination':
        from results.figure_builder.charts.matrices import combination_keys
        from results.figure_builder.core.common import panel_palette
        keys, _v = combination_keys(table, item_exprs(panel, table), mask)
        keep = mask & (keys != '') & (keys != 'none')
        uniq, counts = np.unique(keys[keep].astype(str), return_counts=True)
        order = uniq[np.argsort(-counts, kind='stable')]
        top = max(1, int(panel.get('top_n') or 8))
        pal = panel_palette(panel)
        out = [(str(k), pal[i % len(pal)], keep & (keys == k)) for i, k in enumerate(order[:top])]
        rest = keep & np.isin(keys.astype(str), order[top:])
        if rest.any():
            out.append(('Other', '#c4c8cf', rest))
        return out
    alt = {**panel, 'group_by': mode, 'group_colors': {}, 'group_labels': {}, 'hidden_groups': [],
           'group_order': []}
    return [(g.label, g.color, g.mask & mask) for g in resolve_groups(alt, table)]


def draw_strip(fig, ax, panel, table, report, style):
    """Every particle as a dot per group, spread by local density (sina) or randomly.

    Rows follow the panel's grouping. Dots can be coloured by a second
    grouping or by element combination, sized by the number of elements in
    the particle, and laid out with the values along the horizontal axis.
    """
    groups = [(g, v, m) for g, v, m in value_groups(panel, table, with_masks=True) if v.size]
    if not groups:
        raise ExpressionError('No finite values to plot')
    horizontal = bool(panel.get('strip_horizontal'))
    log = bool(panel.get('log_y'))
    if log:
        (ax.set_xscale if horizontal else ax.set_yscale)('log')
    positions = list(range(1, len(groups) + 1))
    width = max(0.05, min(0.48, float(panel.get('jitter') or 0.35)))
    size = max(1.0, float(panel.get('marker_size') or 16) * 0.55)
    alpha = float(panel.get('alpha') or 0.7)
    rng = np.random.default_rng(1)
    summary = panel.get('strip_summary', 'mean_sd')
    v_all = evaluate(panel['value'], table)
    union = np.zeros(len(table), dtype=bool)
    for _g, _v, m in groups:
        union |= m
    colour_groups = strip_colour_groups(panel, table, union)
    n_el = np.asarray(table.column('n_elements'), dtype=float) if panel.get('strip_size') == 'n_elements' else None
    seen_labels: set = set()
    ew = float(panel.get('edge_width') or 0)
    edge = {'linewidths': ew, 'edgecolors': panel.get('edge_color') or 'none'} if ew else {'linewidths': 0}

    def dots(pos, idx, color, label=None):
        if not idx.size:
            return
        t = np.log10(v_all[idx]) if log else v_all[idx]
        if panel.get('sina', True) and idx.size > 3 and np.ptp(t) > 0:
            dens = _kde_on(t, t)
            spread = dens / dens.max()
        else:
            spread = np.ones_like(t)
        offs = pos + rng.uniform(-1, 1, size=idx.size) * width * spread
        sizes = size if n_el is None else size * (0.45 + 0.55 * np.clip(n_el[idx], 1, None)) ** 1.3
        xy = (v_all[idx], offs) if horizontal else (offs, v_all[idx])
        ax.scatter(*xy, s=sizes, color=color, alpha=alpha, rasterized=True, zorder=2,
                   label=label, **edge)

    for pos, (g, v, m) in zip(positions, groups):
        if colour_groups:
            for name, color, cm in colour_groups:
                idx = np.flatnonzero(m & cm)
                label = name if (idx.size and name not in seen_labels) else None
                if label:
                    seen_labels.add(name)
                dots(pos, idx, color, label)
        else:
            dots(pos, np.flatnonzero(m), g.color)
        if summary == 'none':
            continue
        t = np.log10(v) if log else v
        if summary == 'gmean':
            pos_v = v[v > 0]
            if not pos_v.size:
                continue
            lt = np.log10(pos_v)
            centre = 10 ** np.mean(lt)
            gsd = 10 ** (np.std(lt, ddof=1) if lt.size > 1 else 0.0)
            lo, hi = centre / gsd, centre * gsd
        elif summary == 'median_iqr':
            centre = np.median(v)
            lo, hi = np.percentile(v, [25, 75])
        elif summary == 'mean_ci':
            centre = np.mean(v)
            half = 1.96 * np.std(v, ddof=1) / np.sqrt(v.size) if v.size > 1 else 0.0
            lo, hi = centre - half, centre + half
        else:
            centre = np.mean(v)
            sd = np.std(v, ddof=1) if v.size > 1 else 0.0
            lo, hi = centre - sd, centre + sd
            if log:
                gm = 10 ** np.mean(t)
                gsd = 10 ** (np.std(t, ddof=1) if t.size > 1 else 0.0)
                centre, lo, hi = gm, gm / gsd, gm * gsd
        if horizontal:
            ax.hlines(pos, lo, hi, color=ink('#111827'), lw=1.6, zorder=4)
            ax.vlines(centre, pos - width * 0.7, pos + width * 0.7, color=ink('#111827'), lw=2.2, zorder=4)
        else:
            ax.vlines(pos, lo, hi, color=ink('#111827'), lw=1.6, zorder=4)
            ax.hlines(centre, pos - width * 0.7, pos + width * 0.7, color=ink('#111827'), lw=2.2, zorder=4)
        if panel.get('strip_values'):
            at = (centre, pos + width * 0.75) if horizontal else (pos + width * 0.75, centre)
            t = ax.annotate(f'{centre:.3g}', at, xytext=(3, 0),
                            textcoords='offset points', ha='left', va='center', fontsize='x-small',
                            color=ink('#111827'), zorder=6,
                            bbox={'boxstyle': 'round,pad=0.15', 'fc': 'white', 'ec': 'none', 'alpha': 0.8})
            t._fb_cell = True
    names = [f'{g.label}\n(n={v.size})' if panel.get('show_n', True) else g.label for g, v, _m in groups]
    if horizontal:
        ax.set_yticks(positions)
        ax.set_yticklabels([n.replace('\n', ' ') for n in names])
        ax.set_ylim(len(groups) + 0.6, 0.4)
    else:
        ax.set_xticks(positions)
        ax.set_xticklabels(names)
        ax.set_xlim(0.4, len(groups) + 0.6)
    handles(report, panel)['categories'] = {'axis': 'y' if horizontal else 'x', 'positions': positions,
                                            'items': [(g.label, v) for g, v, _m in groups]}
    report.counts[panel['id']] = int(sum(v.size for _g, v, _m in groups))
    from results.figure_builder.charts.detectability import draw_on_categories
    draw_on_categories(ax, panel, table, report, [(g, v) for g, v, _m in groups], positions,
                       panel['value'], horizontal=horizontal)
    pairs, lines = run_tests([(g.label, v) for g, v, _m in groups], panel)
    report.stats.extend(lines)
    if horizontal:
        style_axes(ax, panel, table, style, panel['value'], '')
    else:
        style_axes(ax, panel, table, style, '', panel['value'])
    draw_marks(ax, panel, [v for _g, v, _m in groups], vertical=horizontal)
    if not horizontal:
        draw_brackets(ax, pairs, positions, panel)
    draw_summary_box(ax, panel, [(g.label, v) for g, v, _m in groups])
    if colour_groups or n_el is not None:
        extra = []
        if n_el is not None:
            from matplotlib.lines import Line2D
            present = sorted({int(x) for x in n_el[union] if x >= 1})
            picks = sorted({present[0], present[len(present) // 2], present[-1]}) if present else []
            for k in picks:
                extra.append(Line2D([], [], marker='o', linestyle='none', color='#9ca3af',
                                    markersize=np.sqrt(size * (0.45 + 0.55 * k) ** 1.3),
                                    label=f'{k} element' + ('s' if k > 1 else '')))
        add_legend(ax, panel, extra=extra or None, min_items=1)


def draw_ridgeline(fig, ax, panel, table, report, style):
    """One smoothed distribution per group, stacked and slightly overlapping."""
    groups = [(g, v) for g, v in value_groups(panel, table) if v.size > 2]
    if not groups:
        raise ExpressionError('Need at least three finite values per group')
    log = bool(panel.get('log_x'))
    allv = np.concatenate([v for _, v in groups])
    t_all = np.log10(allv) if log else allv
    lo, hi = np.percentile(t_all, [0.5, 99.5])
    pad = (hi - lo) * 0.08 or 1.0
    grid = np.linspace(lo - pad, hi + pad, 400)
    overlap = max(0.0, min(2.5, float(panel.get('overlap') or 0.6)))
    step = 1.0
    curves = []
    for g, v in groups:
        t = np.log10(v) if log else v
        dens = _kde_on(t, grid)
        curves.append(dens / dens.max() if dens.max() > 0 else dens)
    xs = 10 ** grid if log else grid
    n = len(groups)
    for k, ((g, v), dens) in enumerate(zip(groups, curves)):
        base = (n - 1 - k) * step
        height = dens * step * (1 + overlap)
        z = 2 + k * 0.01
        ax.fill_between(xs, base, base + height, color=g.color, alpha=0.7, lw=0, zorder=z)
        ax.plot(xs, base + height, color=_darker(g.color), lw=1.1, zorder=z + 0.005)
        ax.plot(xs, np.full_like(xs, base), color='#9ca3af', lw=0.6, zorder=z + 0.004)
        if panel.get('mark_stats', 'none') != 'none':
            t = np.log10(v) if log else v
            med = np.median(t)
            mx = 10 ** med if log else med
            hmed = np.interp(med, grid, dens) * step * (1 + overlap)
            ax.plot([mx, mx], [base, base + hmed], color=ink('#111827'), lw=1.2, zorder=z + 0.006)
    if log:
        ax.set_xscale('log')
    ax.set_yticks([(n - 1 - k) * step + 0.25 for k in range(n)])
    ax.set_yticklabels([label_n(g, v.size, panel) if panel.get('show_n', True) else g.label
                        for g, v in groups])
    ax.tick_params(axis='y', length=0)
    ax.set_ylim(-0.1, (n - 1) * step + (1 + overlap) * step + 0.1)
    report.counts[panel['id']] = int(allv.size)
    _, lines = run_tests([(g.label, v) for g, v in groups], panel)
    report.stats.extend(lines)
    style_axes(ax, panel, table, style, panel['value'], '')
    draw_marks(ax, panel, [v for _g, v in groups], vertical=True)
    for side in ('left', 'right', 'top'):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis='y', which='both', left=False, right=False)
    ax.tick_params(axis='x', which='both', top=False)
    draw_summary_box(ax, panel, [(g.label, v) for g, v in groups])


def draw_hexbin(fig, ax, panel, table, report, style):
    """Hexagonal-bin density of X against Y (good for very many particles)."""
    if not panel.get('x') or not panel.get('y'):
        raise ExpressionError('Set both X and Y expressions')
    from matplotlib.colors import LogNorm
    x = evaluate(panel['x'], table)
    y = evaluate(panel['y'], table)
    log_x, log_y = bool(panel.get('log_x')), bool(panel.get('log_y'))
    m = base_mask(panel, table) & nonzero_mask(panel, x, y) & finite_mask(x, y, log_flags=(log_x, log_y))
    if m.sum() < 3:
        raise ExpressionError('Not enough finite points')
    gridsize = max(5, int(panel.get('bins') or 40))
    hb = ax.hexbin(x[m], y[m], gridsize=gridsize, cmap=cmap_name(panel), mincnt=1,
                   xscale='log' if log_x else 'linear', yscale='log' if log_y else 'linear',
                   norm=LogNorm() if panel.get('log_color', True) else None, linewidths=0.2,
                   edgecolors='face', rasterized=True)
    add_colorbar(fig, ax, hb, panel, report, 'Particles per cell')
    report.counts[panel['id']] = int(m.sum())
    style_axes(ax, panel, table, style, panel['x'], panel['y'])


def draw_contour(fig, ax, panel, table, report, style):
    """2-D kernel density contours of X against Y, one set per group."""
    if not panel.get('x') or not panel.get('y'):
        raise ExpressionError('Set both X and Y expressions')
    from scipy import stats
    x = evaluate(panel['x'], table)
    y = evaluate(panel['y'], table)
    log_x, log_y = bool(panel.get('log_x')), bool(panel.get('log_y'))
    groups = resolve_groups(panel, table)
    nz = nonzero_mask(panel, x, y) & finite_mask(x, y, log_flags=(log_x, log_y))
    levels = max(2, min(20, int(panel.get('levels') or 6)))
    filled = bool(panel.get('filled', True))
    tx_all = np.log10(x[nz]) if log_x else x[nz]
    ty_all = np.log10(y[nz]) if log_y else y[nz]
    if tx_all.size < 5:
        raise ExpressionError('Not enough finite points')
    xlo, xhi = np.percentile(tx_all, [0.5, 99.5])
    ylo, yhi = np.percentile(ty_all, [0.5, 99.5])
    px, py = (xhi - xlo) * 0.15 or 1, (yhi - ylo) * 0.15 or 1
    gx, gy = np.meshgrid(np.linspace(xlo - px, xhi + px, 120), np.linspace(ylo - py, yhi + py, 120))
    from matplotlib.lines import Line2D
    proxies = []
    total = 0
    for g in groups:
        m = g.mask & nz
        if m.sum() < 5:
            continue
        total += int(m.sum())
        tx = np.log10(x[m]) if log_x else x[m]
        ty = np.log10(y[m]) if log_y else y[m]
        if np.ptp(tx) == 0 or np.ptp(ty) == 0:
            continue
        kde = stats.gaussian_kde(np.vstack([tx, ty]))
        zz = kde(np.vstack([gx.ravel(), gy.ravel()])).reshape(gx.shape)
        qs = np.linspace(zz.max() * 0.08, zz.max() * 0.95, levels)
        X = 10 ** gx if log_x else gx
        Y = 10 ** gy if log_y else gy
        if panel.get('show_points'):
            ax.scatter(x[m], y[m], s=3, color=g.color, alpha=0.25, linewidths=0, rasterized=True,
                       zorder=1)
        if filled:
            from matplotlib.colors import to_rgba
            colors = [to_rgba(g.color, a) for a in np.linspace(0.12, 0.55, levels - 1)]
            ax.contourf(X, Y, zz, levels=qs, colors=colors, zorder=2)
        ax.contour(X, Y, zz, levels=qs, colors=[_darker(g.color)], linewidths=0.9, zorder=3)
        proxies.append(Line2D([], [], color=g.color, lw=6, alpha=0.6,
                              label=label_n(g, int(m.sum()), panel)))
    if not proxies:
        raise ExpressionError('Not enough points in any group')
    if log_x:
        ax.set_xscale('log')
    if log_y:
        ax.set_yscale('log')
    report.counts[panel['id']] = total
    style_axes(ax, panel, table, style, panel['x'], panel['y'])
    add_legend(ax, panel, proxies, min_items=2)


def draw_radar(fig, ax, panel, table, report, style):
    """Composition profile of each group on a radar (spider) chart."""
    exprs = item_exprs(panel, table)
    if len(exprs) < 3:
        raise ExpressionError('A radar needs at least three isotopes or expressions')
    groups = resolve_groups(panel, table)
    if not groups:
        raise ExpressionError('Every group is hidden')
    values = np.vstack([np.clip(np.nan_to_num(evaluate(e, table), nan=0.0), 0, None) for e in exprs])
    mode = panel.get('radar_mode', 'share')
    rows = []
    for g in groups:
        sub = values[:, g.mask]
        if sub.shape[1] == 0:
            rows.append(np.zeros(len(exprs)))
            continue
        if mode == 'detect':
            rows.append(100.0 * (sub > 0).mean(axis=1))
        elif mode == 'mean':
            with np.errstate(all='ignore'):
                rows.append(np.array([np.mean(r[r > 0]) if (r > 0).any() else 0.0 for r in sub]))
        else:
            tot = sub.sum(axis=0)
            ok = tot > 0
            rows.append(100.0 * (sub[:, ok] / tot[ok]).mean(axis=1) if ok.any() else np.zeros(len(exprs)))
    R = np.array(rows)
    if mode == 'mean':
        peak = R.max(axis=0)
        peak[peak == 0] = 1
        R = 100.0 * R / peak
    k = len(exprs)
    angles = np.linspace(0, 2 * np.pi, k, endpoint=False)
    closed = np.r_[angles, angles[:1]]
    for g, r in zip(groups, R):
        rr = np.r_[r, r[:1]]
        ax.plot(closed, rr, color=g.color, lw=float(panel.get('line_width') or 1.6),
                label=g.label, zorder=3)
        if panel.get('radar_fill', True):
            ax.fill(closed, rr, color=g.color, alpha=0.15, zorder=2)
        ax.scatter(angles, r, s=14, color=g.color, zorder=4)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles)
    ax.set_xticklabels([item_label(panel, e, table, style, short=True) for e in exprs])
    top = float(np.nanmax(R)) if R.size else 100.0
    ax.set_ylim(0, top * 1.08 if top > 0 else 1)
    ax.tick_params(axis='y', labelsize='x-small', colors='#6b7280')
    ax.grid(True, color='#d9dde3', lw=0.6)
    ax.spines['polar'].set_color('#9ca3af')
    if panel.get('title'):
        ax.set_title(panel['title'], pad=18)
    report.counts[panel['id']] = int(sum(int(g.mask.sum()) for g in groups))
    what = {'share': 'mean share (%)', 'detect': 'detected in (% of particles)',
            'mean': 'mean value (% of the largest group)'}[mode]
    report.stats.append(f'Radar shows {what}.')
    add_legend(ax, panel, default_loc='below', min_items=2)


def draw_parallel(fig, ax, panel, table, report, style):
    """Parallel coordinates: one line per particle across several isotopes."""
    exprs = item_exprs(panel, table)
    if len(exprs) < 2:
        raise ExpressionError('List at least two isotopes or expressions')
    groups = resolve_groups(panel, table)
    values = np.vstack([evaluate(e, table) for e in exprs])
    scale = panel.get('parallel_scale', 'log')
    with np.errstate(all='ignore'), warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        if scale == 'log':
            T = np.where(values > 0, np.log10(values), np.nan)
        else:
            T = values.astype(float)
        if scale in ('log', 'minmax'):
            lo = np.nanpercentile(T, 1, axis=1, keepdims=True)
            hi = np.nanpercentile(T, 99, axis=1, keepdims=True)
            span = np.where(hi > lo, hi - lo, 1.0)
            T = np.clip((T - lo) / span, -0.05, 1.05)
    xs = np.arange(len(exprs))
    cap = max(20, int(panel.get('max_lines') or 400))
    rng = np.random.default_rng(2)
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D
    proxies = []
    total = 0
    for g in groups:
        idx = np.flatnonzero(g.mask)
        if idx.size == 0:
            continue
        total += idx.size
        shown = idx if idx.size <= cap else rng.choice(idx, cap, replace=False)
        segs = [np.column_stack([xs, T[:, i]]) for i in shown]
        lc = LineCollection(segs, colors=[g.color], linewidths=0.6,
                            alpha=float(panel.get('alpha') or 0.7) * 0.35, zorder=2,
                            rasterized=True)
        ax.add_collection(lc)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            med = np.nanmedian(T[:, idx], axis=1)
        ax.plot(xs, med, color=_darker(g.color), lw=2.4, zorder=4, marker='o', ms=4)
        proxies.append(Line2D([], [], color=g.color, lw=2.4, label=label_n(g, idx.size, panel)))
    ax.set_xlim(-0.2, len(exprs) - 0.8)
    if scale in ('log', 'minmax'):
        ax.set_ylim(-0.08, 1.08)
        ax.set_yticks([0, 0.5, 1])
        ax.set_yticklabels(['low', 'mid', 'high'])
        default_y = 'Scaled value' + (' (log)' if scale == 'log' else '')
    else:
        ax.autoscale_view()
        default_y = 'Value'
    ax.set_xticks(xs)
    ax.set_xticklabels([item_label(panel, e, table, style, short=True) for e in exprs])
    for x in xs:
        ax.axvline(x, color='#9ca3af', lw=0.8, zorder=1)
    report.counts[panel['id']] = total
    style_axes(ax, panel, table, style)
    if not panel.get('y_label'):
        ax.set_ylabel(default_y)
    ax.minorticks_off()
    add_legend(ax, panel, proxies, min_items=2)
