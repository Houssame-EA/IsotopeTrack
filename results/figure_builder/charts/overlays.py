"""Extras drawn on scatter panels: group ellipses and hulls, trend curves, marginals and a zoom inset."""

from __future__ import annotations

import numpy as np

from results.figure_builder.core.common import bin_edges, float_or_none, handles, ink, numbers

ELLIPSES = {
    'none': 'None', '1sd': '68% (1 SD) ellipse', '2sd': '95% ellipse', '3sd': '99% ellipse',
}
"""Confidence ellipses that can surround each group."""

ELLIPSE_P = {'1sd': 0.6827, '2sd': 0.95, '3sd': 0.99}

TRENDS = {'none': 'None', 'median': 'Running median', 'mean': 'Running mean'}
"""Smooth curves that can follow each group."""

MARGINALS = {'none': 'None', 'hist': 'Histograms', 'kde': 'Smooth curves (KDE)', 'box': 'Box plots'}
"""What can be drawn along the top and right edges of a scatter."""

INSET_LOCS = {'upper left': 'Upper left', 'upper right': 'Upper right',
              'lower left': 'Lower left', 'lower right': 'Lower right'}
"""Where a zoom inset can go."""


def _to_space(v, log):
    return np.log10(v) if log else v


def _from_space(v, log):
    return 10 ** v if log else v


def draw_group_shapes(ax, panel, data, log_x, log_y):
    """Confidence ellipses and convex hulls around each group of points.

    Args:
        data: ``[(group, x, y), ...]`` of the points drawn for each group.
    """
    level = panel.get('ellipse', 'none')
    hull = bool(panel.get('hull'))
    if level == 'none' and not hull:
        return
    from scipy import stats
    for g, x, y in data:
        if x.size < 3:
            continue
        tx, ty = _to_space(x, log_x), _to_space(y, log_y)
        if level in ELLIPSE_P and x.size >= 3:
            cov = np.cov(tx, ty)
            if np.all(np.isfinite(cov)) and np.linalg.det(cov) > 0:
                vals, vecs = np.linalg.eigh(cov)
                k = np.sqrt(stats.chi2.ppf(ELLIPSE_P[level], 2))
                a = np.linspace(0, 2 * np.pi, 200)
                circle = np.vstack([np.cos(a), np.sin(a)])
                pts = vecs @ (np.sqrt(np.maximum(vals, 0))[:, None] * k * circle)
                ex = _from_space(pts[0] + tx.mean(), log_x)
                ey = _from_space(pts[1] + ty.mean(), log_y)
                ax.fill(ex, ey, color=g.color, alpha=0.1, lw=0, zorder=1)
                ax.plot(ex, ey, color=g.color, lw=1.4, zorder=4)
                ax.scatter([_from_space(tx.mean(), log_x)], [_from_space(ty.mean(), log_y)], marker='+',
                           s=70, color=g.color, linewidths=1.6, zorder=5)
        if hull and x.size >= 3:
            try:
                from scipy.spatial import ConvexHull
                pts = np.column_stack([tx, ty])
                h = ConvexHull(pts)
            except Exception:
                continue
            ring = np.r_[h.vertices, h.vertices[:1]]
            hx, hy = _from_space(pts[ring, 0], log_x), _from_space(pts[ring, 1], log_y)
            ax.fill(hx, hy, color=g.color, alpha=0.08, lw=0, zorder=1)
            ax.plot(hx, hy, color=g.color, lw=1.0, ls='--', zorder=4)


def draw_trends(ax, panel, data, log_x, log_y):
    """Running median or mean of Y in bins of X, one curve per group."""
    mode = panel.get('trend', 'none')
    if mode not in ('median', 'mean'):
        return
    from matplotlib import patheffects
    lw = float(panel.get('line_width') or 1.6) + 0.6
    nb = max(4, min(60, int(panel.get('trend_bins') or 15)))
    for g, x, y in data:
        if x.size < 8:
            continue
        edges = bin_edges(x, nb, log_x)
        idx = np.clip(np.digitize(x, edges) - 1, 0, len(edges) - 2)
        cx, cy = [], []
        for b in range(len(edges) - 1):
            sel = idx == b
            if np.count_nonzero(sel) < 4:
                continue
            ty = _to_space(y[sel], log_y)
            cx.append(_from_space(np.median(_to_space(x[sel], log_x)), log_x))
            cy.append(_from_space(np.median(ty) if mode == 'median' else np.mean(ty), log_y))
        if len(cx) >= 2:
            ax.plot(cx, cy, color=g.color, lw=lw, zorder=6, solid_capstyle='round',
                    path_effects=[patheffects.withStroke(linewidth=lw + 2.6, foreground='white')])


def fit_band(ax, fx, fy, res, color, log_x, log_y):
    """95% confidence band of a least-squares line (computed in plotted space)."""
    from scipy import stats
    n = fx.size
    if n < 4:
        return
    xs = np.linspace(fx.min(), fx.max(), 120)
    yhat = res.intercept + res.slope * xs
    resid = fy - (res.intercept + res.slope * fx)
    s = np.sqrt(np.sum(resid ** 2) / (n - 2))
    sxx = np.sum((fx - fx.mean()) ** 2)
    if sxx <= 0:
        return
    half = stats.t.ppf(0.975, n - 2) * s * np.sqrt(1 / n + (xs - fx.mean()) ** 2 / sxx)
    ax.fill_between(_from_space(xs, log_x), _from_space(yhat - half, log_y), _from_space(yhat + half, log_y),
                    color=color, alpha=0.16, lw=0, zorder=4)


def _marginal_hist(mx, values, log, color, bins, vertical, edges):
    counts, _ = np.histogram(values, edges)
    if counts.sum() == 0:
        return
    dens = counts / counts.sum()
    if vertical:
        mx.stairs(dens, edges, orientation='horizontal', fill=True, color=color, alpha=0.3)
        mx.stairs(dens, edges, orientation='horizontal', color=color, lw=1.0)
    else:
        mx.stairs(dens, edges, fill=True, color=color, alpha=0.3)
        mx.stairs(dens, edges, color=color, lw=1.0)


def _marginal_kde(mx, values, log, color, vertical, lo, hi):
    from scipy import stats
    t = _to_space(values, log)
    if t.size < 3 or np.ptp(t) == 0:
        return
    grid = np.linspace(lo, hi, 200)
    d = stats.gaussian_kde(t)(grid)
    xs = _from_space(grid, log)
    if vertical:
        mx.fill_betweenx(xs, 0, d, color=color, alpha=0.25, lw=0)
        mx.plot(d, xs, color=color, lw=1.2)
    else:
        mx.fill_between(xs, 0, d, color=color, alpha=0.25, lw=0)
        mx.plot(xs, d, color=color, lw=1.2)


def _boxplot(axes, values, position, vertical, style):
    """One box, using ``orientation`` where matplotlib has it and ``vert`` otherwise."""
    try:
        axes.boxplot([values], positions=[position],
                     orientation='vertical' if vertical else 'horizontal', **style)
    except TypeError:
        axes.boxplot([values], positions=[position], vert=vertical, **style)


def add_marginals(fig, ax, panel, data, log_x, log_y, report):
    """Distributions of X along the top and of Y along the right edge of a scatter."""
    mode = panel.get('marginals', 'none')
    if mode not in ('hist', 'kde', 'box') or not data:
        return
    right_too = not (panel.get('y2') or '').strip()
    p = ax.get_position()
    frac = 0.18
    gap = 0.015
    main_w = p.width * (1 - frac - gap) if right_too else p.width
    main_h = p.height * (1 - frac - gap)
    ax.set_position([p.x0, p.y0, main_w, main_h])
    top = fig.add_axes([p.x0, p.y0 + main_h + p.height * gap, main_w, p.height * frac], sharex=ax)
    marg = [top]
    right = None
    if right_too:
        right = fig.add_axes([p.x0 + main_w + p.width * gap, p.y0, p.width * frac, main_h], sharey=ax)
        marg.append(right)
    allx = np.concatenate([x for _g, x, _y in data])
    ally = np.concatenate([y for _g, _x, y in data])
    bins = max(5, min(80, int(panel.get('bins') or 40)))
    ex, ey = bin_edges(allx, bins, log_x), bin_edges(ally, bins, log_y)
    tx_all, ty_all = _to_space(allx, log_x), _to_space(ally, log_y)
    xlo, xhi = tx_all.min(), tx_all.max()
    ylo, yhi = ty_all.min(), ty_all.max()
    for k, (g, x, y) in enumerate(data):
        if mode == 'hist':
            _marginal_hist(top, x, log_x, g.color, bins, False, ex)
            if right is not None:
                _marginal_hist(right, y, log_y, g.color, bins, True, ey)
        elif mode == 'kde':
            _marginal_kde(top, x, log_x, g.color, False, xlo, xhi)
            if right is not None:
                _marginal_kde(right, y, log_y, g.color, True, ylo, yhi)
        else:
            style = {'patch_artist': True, 'widths': 0.6, 'showfliers': False,
                     'boxprops': {'facecolor': g.color, 'alpha': 0.55, 'edgecolor': g.color},
                     'medianprops': {'color': ink('#111827'), 'lw': 1.4},
                     'whiskerprops': {'color': g.color}, 'capprops': {'color': g.color}}
            _boxplot(top, x, k, False, style)
            if right is not None:
                _boxplot(right, y, k, True, style)
    for m in marg:
        m.set_zorder(ax.get_zorder())
        m.set_facecolor('none')
        for side in ('top', 'right', 'left'):
            m.spines[side].set_visible(False)
        m.tick_params(which='both', left=False, bottom=False, labelleft=False, labelbottom=False,
                      top=False, right=False, labeltop=False, labelright=False)
    top.spines['bottom'].set_visible(True)
    top.spines['bottom'].set_color('#9ca3af')
    if right is not None:
        right.spines['bottom'].set_visible(False)
        right.spines['left'].set_visible(True)
        right.spines['left'].set_color('#9ca3af')
    if mode == 'box':
        top.set_ylim(-0.7, len(data) - 0.3)
        if right is not None:
            right.set_xlim(-0.7, len(data) - 0.3)
    else:
        top.set_ylim(bottom=0)
        if right is not None:
            right.set_xlim(left=0)
    if ax.get_title():
        ax.set_title(ax.get_title(), y=1 + (p.height * (frac + gap)) / main_h)
    hd = handles(report, panel)
    hd.setdefault('extra_axes', []).extend(marg)
    hd['marg_top'] = top
    if right is not None:
        hd['marg_right'] = right


def add_zoom_inset(ax, panel, report):
    """A magnified copy of part of the scatter, linked to the region it shows."""
    vals = numbers(panel.get('inset_zoom'))
    if len(vals) != 4:
        return
    x1, x2, y1, y2 = vals
    if x1 == x2 or y1 == y2:
        return
    size = max(0.15, min(0.7, float_or_none(panel.get('inset_size')) or 0.4))
    loc = panel.get('inset_loc', 'upper left')
    pad = 0.04
    bx = pad if 'left' in loc else 1 - pad - size
    by = 1 - pad - size if 'upper' in loc else pad
    ins = ax.inset_axes([bx, by, size, size])
    ins.set_zorder(ax.get_zorder() + 0.3)
    from matplotlib.collections import PathCollection
    marker = panel.get('marker') or 'o'
    for coll in list(ax.collections):
        if not isinstance(coll, PathCollection):
            continue
        off = coll.get_offsets()
        if len(off) == 0:
            continue
        fc = coll.get_facecolors()
        ec = coll.get_edgecolors()
        sizes = coll.get_sizes()
        kw = {'s': sizes if len(sizes) > 1 else (sizes[0] if len(sizes) else 16), 'marker': marker,
              'rasterized': True, 'zorder': coll.get_zorder()}
        if len(fc):
            kw['c'] = fc if len(fc) > 1 else [fc[0]]
            kw['linewidths'] = 0.3
            kw['edgecolors'] = ec if len(ec) else 'none'
        else:
            kw.update(facecolors='none', edgecolors=ec, linewidths=0.8)
        ins.scatter(np.asarray(off)[:, 0], np.asarray(off)[:, 1], **kw)
    ins.set_xscale(ax.get_xscale())
    ins.set_yscale(ax.get_yscale())
    ins.set_xlim(min(x1, x2), max(x1, x2))
    ins.set_ylim(min(y1, y2), max(y1, y2))
    ins.tick_params(labelsize='x-small', length=2, which='both')
    ins.set_facecolor('#ffffff')
    for sp in ins.spines.values():
        sp.set_color(ink('#374151'))
        sp.set_linewidth(0.9)
    try:
        ax.indicate_inset_zoom(ins, edgecolor=ink('#374151'), alpha=0.8, linewidth=0.8)
    except Exception:
        pass
    handles(report, panel)['inset'] = ins
