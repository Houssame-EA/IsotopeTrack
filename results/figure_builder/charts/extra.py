"""More ways to look at particles: dot plots, ridgelines, hexbins, contours, radar and parallel coordinates."""

from __future__ import annotations

import warnings

import numpy as np

from results.figure_builder.core.common import (
    add_legend, base_mask, cmap_name, draw_summary_box, finite_mask, handles, item_exprs,
    item_label, label_n, nonzero_mask, resolve_groups, style_axes, value_groups)
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


def draw_strip(fig, ax, panel, table, report, style):
    """Every particle as a dot per group, spread by local density (sina) or randomly."""
    groups = [(g, v) for g, v in value_groups(panel, table) if v.size]
    if not groups:
        raise ExpressionError('No finite values to plot')
    log = bool(panel.get('log_y'))
    if log:
        ax.set_yscale('log')
    positions = list(range(1, len(groups) + 1))
    width = max(0.05, min(0.48, float(panel.get('jitter') or 0.35)))
    size = max(1.0, float(panel.get('marker_size') or 16) * 0.55)
    alpha = float(panel.get('alpha') or 0.7)
    rng = np.random.default_rng(1)
    summary = panel.get('strip_summary', 'mean_sd')
    for pos, (g, v) in zip(positions, groups):
        t = np.log10(v) if log else v
        if panel.get('sina', True) and v.size > 3 and np.ptp(t) > 0:
            dens = _kde_on(t, t)
            spread = dens / dens.max()
        else:
            spread = np.ones_like(t)
        xs = pos + rng.uniform(-1, 1, size=v.size) * width * spread
        ew = float(panel.get('edge_width') or 0)
        edge = {'linewidths': ew, 'edgecolors': panel.get('edge_color') or 'none'} if ew else {'linewidths': 0}
        ax.scatter(xs, v, s=size, color=g.color, alpha=alpha, rasterized=True, zorder=2, **edge)
        if summary == 'none':
            continue
        if summary == 'median_iqr':
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
        ax.vlines(pos, lo, hi, color='#111827', lw=1.6, zorder=4)
        ax.hlines(centre, pos - width * 0.7, pos + width * 0.7, color='#111827', lw=2.2, zorder=4)
    ax.set_xticks(positions)
    ax.set_xticklabels([f'{g.label}\n(n={v.size})' if panel.get('show_n', True) else g.label
                        for g, v in groups])
    ax.set_xlim(0.4, len(groups) + 0.6)
    handles(report, panel)['categories'] = {'axis': 'x', 'positions': positions,
                                            'items': [(g.label, v) for g, v in groups]}
    report.counts[panel['id']] = int(sum(v.size for _, v in groups))
    pairs, lines = run_tests([(g.label, v) for g, v in groups], panel)
    report.stats.extend(lines)
    style_axes(ax, panel, table, style, '', panel['value'])
    draw_brackets(ax, pairs, positions, panel)
    draw_summary_box(ax, panel, [(g.label, v) for g, v in groups])


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
            ax.plot([mx, mx], [base, base + hmed], color='#111827', lw=1.2, zorder=z + 0.006)
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
    cb = fig.colorbar(hb, ax=ax, pad=0.02, fraction=0.05)
    cb.ax.set_zorder(ax.get_zorder())
    cb.outline.set_linewidth(0.6)
    cb.set_label(panel.get('cbar_label') or 'Particles per cell')
    hd = handles(report, panel)
    hd['cbar'] = cb
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
