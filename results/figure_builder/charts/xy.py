"""X/Y charts: scatter (with overlays, fits and a right axis), binned trend lines and density maps."""

from __future__ import annotations

import numpy as np

from results.figure_builder.core.common import (
    add_legend, bin_edges, cmap_name, edge_kwargs, finite_mask, handles, label_n,
    marker_sizes, nonzero_mask, panel_palette, resolve_groups, style_axes)
from results.figure_builder.core.expressions import ExpressionError, evaluate, pretty
from results.figure_builder.core.spec import PALETTE


def draw_scatter(fig, ax, panel, table, report, style):
    """Scatter of X against Y with rules, colour/size scales, overlays and a right axis."""
    if not panel.get('x') or not panel.get('y'):
        raise ExpressionError('Set both X and Y expressions')
    x = evaluate(panel['x'], table)
    y = evaluate(panel['y'], table)
    log_x, log_y = panel.get('log_x'), panel.get('log_y')
    if log_x:
        ax.set_xscale('log')
    if log_y:
        ax.set_yscale('log')
    groups = resolve_groups(panel, table)
    cvals = evaluate(panel['color_by'], table) if (panel.get('color_by') or '').strip() else None
    size = float(panel.get('marker_size') or 12)
    sizes = marker_sizes(panel, table, size)
    alpha = float(panel.get('alpha') or 0.7)
    marker = panel.get('marker') or 'o'
    edge = edge_kwargs(panel) if marker not in ('+', 'x', '.') else {}
    total = 0
    mappable = None
    nz = nonzero_mask(panel, x, y)
    for g in groups:
        m = g.mask & nz & finite_mask(x, y, log_flags=(log_x, log_y))
        if cvals is not None:
            m &= np.isfinite(cvals)
        if not m.any():
            continue
        total += int(m.sum())
        hover = handles(report, panel).setdefault('points', [])
        hover.append({'x': x[m], 'y': y[m], 'index': np.flatnonzero(m), 'group': g.label,
                      'color': g.color})
        s = sizes[m] if sizes is not None else size
        if cvals is not None:
            mappable = ax.scatter(x[m], y[m], c=cvals[m], cmap=cmap_name(panel), s=s, alpha=alpha,
                                  marker=marker, rasterized=True,
                                  label=label_n(g, int(m.sum()), panel) if len(groups) > 1 else None,
                                  **edge)
        else:
            ax.scatter(x[m], y[m], color=g.color, s=s, alpha=alpha, marker=marker,
                       rasterized=True, label=label_n(g, int(m.sum()), panel), **edge)
        if panel.get('show_fit') or panel.get('show_r'):
            draw_fit(ax, x[m], y[m], g, panel, report, log_x, log_y)
    draw_series(ax, panel, table, style, log_x, log_y)
    if mappable is not None:
        cb = fig.colorbar(mappable, ax=ax, pad=0.02, fraction=0.05)
        handles(report, panel)['cbar'] = cb
        cb.ax.set_zorder(ax.get_zorder())
        cb.set_label(panel.get('cbar_label') or pretty(panel['color_by'], table, style))
        cb.outline.set_linewidth(0.6)
        cb.ax.tick_params(direction='out', length=3, width=0.6)
    if panel.get('diagonal'):
        lo = max(ax.get_xlim()[0], ax.get_ylim()[0])
        hi = min(ax.get_xlim()[1], ax.get_ylim()[1])
        ax.plot([lo, hi], [lo, hi], color='#555555', lw=1, ls=':', zorder=1)
    extra = None
    if (panel.get('y2') or '').strip():
        ax2 = ax.twinx()
        handles(report, panel)['ax2'] = ax2
        ax2.set_zorder(ax.get_zorder() + 0.1)
        ax2.patch.set_visible(False)
        y2 = evaluate(panel['y2'], table)
        if panel.get('log_y2'):
            ax2.set_yscale('log')
        base = np.zeros(len(table), dtype=bool)
        for g in groups:
            base |= g.mask
        m = base & nonzero_mask(panel, x, y2) & finite_mask(x, y2, log_flags=(log_x, panel.get('log_y2')))
        color = panel.get('y2_color') or PALETTE[1]
        extra = ax2.scatter(x[m], y2[m], s=size, facecolors='none', edgecolors=color,
                            linewidths=0.8, alpha=alpha, marker=marker if marker not in ('+', 'x', '.') else 'o',
                            rasterized=True,
                            label=f'{pretty(panel["y2"], table, style)} (right axis)')
        ax2.set_ylabel(panel.get('y2_label') or pretty(panel['y2'], table, style), color=color)
        ax2.tick_params(axis='y', colors=color, direction=panel.get('tick_dir') or 'out')
        ax2.spines['right'].set_color(color)
        for side in ('top', 'left', 'bottom'):
            ax2.spines[side].set_visible(False)
    report.counts[panel['id']] = total
    hd = handles(report, panel)
    hd['x_name'] = panel['x']
    hd['y_name'] = panel['y']
    hd['table'] = table
    style_axes(ax, panel, table, style, panel['x'], panel['y'])
    add_legend(ax, panel, [extra] if extra is not None else None)


def draw_series(ax, panel, table, style, log_x, log_y):
    """Extra X/Y series drawn on top of a scatter panel."""
    pal = panel_palette(panel)
    for i, s in enumerate(panel.get('series') or []):
        xe, ye = (s.get('x') or '').strip(), (s.get('y') or '').strip()
        if not xe or not ye:
            continue
        x = evaluate(xe, table)
        y = evaluate(ye, table)
        m = nonzero_mask(panel, x, y) & finite_mask(x, y, log_flags=(log_x, log_y))
        if (s.get('filter') or '').strip():
            m &= evaluate(s['filter'], table, as_mask=True)
        if not m.any():
            continue
        color = s.get('color') or pal[(i + 2) % len(pal)]
        label = s.get('label') or f'{pretty(ye, table, style)} vs {pretty(xe, table, style)}'
        mode = s.get('style') or 'points'
        xs, ys = x[m], y[m]
        if mode in ('line', 'points+line'):
            order = np.argsort(xs)
            ax.plot(xs[order], ys[order], color=color, lw=float(panel.get('line_width') or 1.6),
                    ls=panel.get('line_style') or '-', label=label if mode == 'line' else None,
                    zorder=4)
        if mode in ('points', 'points+line'):
            mk = s.get('marker') or 'o'
            ax.scatter(xs, ys, color=color, s=float(s.get('size') or panel.get('marker_size') or 12),
                       marker=mk, alpha=float(panel.get('alpha') or 0.7),
                       linewidths=1.2 if mk in ('+', 'x', '.') else 0, rasterized=True,
                       label=f'{label} (n={xs.size})', zorder=4)


def draw_fit(ax, x, y, g, panel, report, log_x, log_y):
    """Least-squares line (in plotted space) and Pearson / Spearman r."""
    from scipy import stats
    if x.size < 3:
        return
    fx = np.log10(x) if log_x else x
    fy = np.log10(y) if log_y else y
    res = stats.linregress(fx, fy)
    rho = stats.spearmanr(fx, fy).statistic
    report.stats.append(
        f'{g.label}: slope = {res.slope:.4g}, intercept = {res.intercept:.4g}, '
        f'Pearson r = {res.rvalue:.3f} (R² = {res.rvalue ** 2:.3f}, p = {res.pvalue:.3g}), '
        f'Spearman ρ = {rho:.3f}, n = {x.size}'
        + (' [fit in log space]' if (log_x or log_y) else ''))
    if panel.get('show_fit'):
        xs = np.linspace(fx.min(), fx.max(), 100)
        ys = res.intercept + res.slope * xs
        from matplotlib import patheffects
        ax.plot(10 ** xs if log_x else xs, 10 ** ys if log_y else ys,
                color=g.color, lw=float(panel.get('line_width') or 1.6) + 0.4,
                ls=panel.get('line_style') or '-', zorder=5,
                path_effects=[patheffects.withStroke(linewidth=float(panel.get('line_width') or 1.6) + 2.6,
                                                     foreground='white')])
    if panel.get('show_r'):
        existing = sum(1 for t in ax.texts if getattr(t, '_fb_r', False))
        t = ax.text(0.03, 0.97 - existing * 0.07,
                    f'r = {res.rvalue:.3f}  R² = {res.rvalue ** 2:.3f}',
                    transform=ax.transAxes, ha='left', va='top', color=g.color,
                    fontsize='small')
        t._fb_r = True


def draw_line(fig, ax, panel, table, report, style):
    """Binned trend: Y aggregated in bins of X, one line per group with a band."""
    if not (panel.get('x') or '').strip():
        raise ExpressionError('Set the X expression (e.g. time)')
    x = evaluate(panel['x'], table)
    y_expr = (panel.get('y') or '').strip()
    y = evaluate(y_expr, table) if y_expr else np.ones(len(table))
    log_x = bool(panel.get('log_x'))
    groups = resolve_groups(panel, table)
    agg = panel.get('agg', 'mean') if y_expr else 'count'
    nz = nonzero_mask(panel, x, y) if y_expr else nonzero_mask(panel, x)
    ok = nz & finite_mask(x, y, log_flags=(log_x, False))
    if ok.sum() < 2:
        raise ExpressionError('Not enough finite values')
    bins = max(2, int(panel.get('bins') or 40))
    edges = bin_edges(x[ok], bins, log_x)
    centres = np.sqrt(edges[:-1] * edges[1:]) if log_x else (edges[:-1] + edges[1:]) / 2
    total = 0
    for g in groups:
        m = g.mask & ok
        if not m.any():
            continue
        total += int(m.sum())
        idx = np.clip(np.digitize(x[m], edges) - 1, 0, bins - 1)
        vals = y[m]
        mid, lo, hi = np.full(bins, np.nan), np.full(bins, np.nan), np.full(bins, np.nan)
        for b in range(bins):
            v = vals[idx == b]
            if agg == 'count':
                mid[b] = v.size
                continue
            if v.size == 0:
                continue
            mid[b] = {'mean': np.mean, 'median': np.median, 'sum': np.sum}.get(agg, np.mean)(v)
            band = panel.get('band', 'sem')
            if v.size > 1 and band != 'none' and agg in ('mean', 'median'):
                if band == 'iqr':
                    lo[b], hi[b] = np.percentile(v, [25, 75])
                else:
                    sd = np.std(v, ddof=1)
                    w = sd if band == 'sd' else sd / np.sqrt(v.size)
                    lo[b], hi[b] = mid[b] - w, mid[b] + w
        marker = panel.get('marker') if panel.get('show_points') else None
        ax.plot(centres, mid, color=g.color, lw=float(panel.get('line_width') or 1.6),
                ls=panel.get('line_style') or '-', marker=marker,
                ms=np.sqrt(float(panel.get('marker_size') or 12)),
                label=label_n(g, int(m.sum()), panel))
        if np.isfinite(lo).any():
            ax.fill_between(centres, lo, hi, color=g.color, alpha=0.18, lw=0)
    if log_x:
        ax.set_xscale('log')
    if panel.get('log_y'):
        ax.set_yscale('log')
    report.counts[panel['id']] = total
    ylab = 'Particles per bin' if agg == 'count' else f'{agg.capitalize()} {pretty(y_expr, table, style)}'
    style_axes(ax, panel, table, style, panel['x'], '')
    if not panel.get('y_label'):
        ax.set_ylabel(ylab)
    add_legend(ax, panel)


def draw_density(fig, ax, panel, table, report, style):
    """2-D histogram of X against Y, useful when points overplot."""
    if not panel.get('x') or not panel.get('y'):
        raise ExpressionError('Set both X and Y expressions')
    from matplotlib.colors import LogNorm
    x = evaluate(panel['x'], table)
    y = evaluate(panel['y'], table)
    base = np.zeros(len(table), dtype=bool)
    for g in resolve_groups(panel, table):
        base |= g.mask
    log_x, log_y = panel.get('log_x'), panel.get('log_y')
    m = base & nonzero_mask(panel, x, y) & finite_mask(x, y, log_flags=(log_x, log_y))
    if m.sum() < 2:
        raise ExpressionError('Not enough finite points')
    xs, ys = x[m], y[m]
    bins = max(4, int(panel.get('bins') or 40))
    _, _, _, img = ax.hist2d(xs, ys, bins=[bin_edges(xs, bins, log_x), bin_edges(ys, bins, log_y)],
                             cmap=cmap_name(panel), norm=LogNorm(), rasterized=True)
    if log_x:
        ax.set_xscale('log')
    if log_y:
        ax.set_yscale('log')
    cb = fig.colorbar(img, ax=ax, pad=0.02, fraction=0.05)
    handles(report, panel)['cbar'] = cb
    cb.ax.set_zorder(ax.get_zorder())
    cb.set_label(panel.get('cbar_label') or 'Particles per bin')
    cb.outline.set_linewidth(0.6)
    cb.ax.tick_params(direction='out', length=3, width=0.6)
    report.counts[panel['id']] = int(m.sum())
    style_axes(ax, panel, table, style, panel['x'], panel['y'])
