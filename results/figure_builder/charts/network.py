"""Charts from the Network and Clustering nodes: a correlation network and a compositional PCA biplot."""

from __future__ import annotations

import numpy as np

from results.figure_builder.core.common import (
    add_legend, base_mask, handles, ink, item_exprs, item_label, label_n, panel_palette,
    resolve_groups, style_axes)
from results.figure_builder.core.expressions import ExpressionError, evaluate, plain

NODE_SIZES = {'none': 'Same size', 'sum': 'Summed amount', 'mean': 'Mean amount',
              'detect': 'Particles detected'}
"""What a network node's size can show."""

PCA_TRANSFORMS = {'clr': 'Centred log-ratio (compositional)', 'log': 'log10 of the values',
                  'zscore': 'Standardised values (z-score)'}
"""How values are prepared before a PCA."""


def draw_network(fig, ax, panel, table, report, style):
    """Isotopes on a circle joined by their correlation, as in the Network node.

    An edge links two isotopes when at least ``min_n`` particles contain both
    and the Pearson r of their values in those particles reaches
    ``r_threshold``. Edge width follows |r| and colour its sign; node size can
    follow the summed or mean amount or the number of particles detected.
    """
    from scipy import stats
    exprs = item_exprs(panel, table)
    if len(exprs) < 2:
        raise ExpressionError('List at least two isotopes or expressions')
    base = base_mask(panel, table)
    values = [np.nan_to_num(evaluate(e, table), nan=0.0) for e in exprs]
    names = [item_label(panel, e, table, style, short=True) for e in exprs]
    min_n = max(3, int(panel.get('min_n') or 10))
    thr = float(panel.get('net_r_min') if panel.get('net_r_min') is not None else 0.3)
    log = bool(panel.get('log_values'))
    k = len(exprs)
    edges = []
    for i in range(k):
        for j in range(i + 1, k):
            m = base & (values[i] > 0) & (values[j] > 0)
            if m.sum() < min_n:
                continue
            x, y = values[i][m], values[j][m]
            if log:
                x, y = np.log10(x), np.log10(y)
            if np.ptp(x) == 0 or np.ptp(y) == 0:
                continue
            r = float(stats.pearsonr(x, y).statistic)
            if abs(r) >= thr:
                edges.append((i, j, r, int(m.sum())))
    angles = np.pi / 2 - 2 * np.pi * np.arange(k) / k
    xy = np.column_stack([np.cos(angles), np.sin(angles)])
    pos_color = panel.get('edge_pos_color') or '#2563eb'
    neg_color = panel.get('edge_neg_color') or '#dc2626'
    wf = float(panel.get('line_width') or 1.6) * 2.5
    for i, j, r, _n in sorted(edges, key=lambda e: abs(e[2])):
        ax.plot(*zip(xy[i], xy[j]), color=pos_color if r > 0 else neg_color, lw=max(0.5, abs(r) * wf),
                alpha=0.35 + 0.5 * abs(r), zorder=2, solid_capstyle='round')
    how = panel.get('node_size', 'sum')
    amounts = []
    for v in values:
        vv = v[base & (v > 0)]
        amounts.append({'sum': vv.sum(), 'mean': vv.mean() if vv.size else 0.0,
                        'detect': float(vv.size)}.get(how, 1.0) if vv.size else 0.0)
    amounts = np.asarray(amounts, dtype=float)
    base_size = float(panel.get('marker_size') or 16) * 30
    if how == 'none' or not (amounts > 0).any():
        sizes = np.full(k, base_size)
    else:
        lo = amounts[amounts > 0].min()
        scale = np.where(amounts > 0, 1 + np.log10(np.maximum(amounts, lo) / lo), 0.5)
        sizes = base_size * np.minimum(scale, 4.0)
    color = panel.get('color') or panel_palette(panel)[0]
    ax.scatter(xy[:, 0], xy[:, 1], s=sizes, color=color, edgecolors='white', linewidths=1.5, zorder=3)
    for (x, y), name in zip(xy, names):
        t = ax.text(x * 1.2, y * 1.2, name, ha='center', va='center', fontsize='small', zorder=4,
                    color=ink('#111827'))
        t._fb_cell = True
    from matplotlib.lines import Line2D
    proxies = [Line2D([], [], color=pos_color, lw=2.5, label='r > 0'),
               Line2D([], [], color=neg_color, lw=2.5, label='r < 0')]
    ax.set_xlim(-1.45, 1.45)
    ax.set_ylim(-1.4, 1.4)
    ax.set_aspect('equal')
    ax.axis('off')
    if panel.get('title'):
        ax.set_title(panel['title'])
    rs = [abs(e[2]) for e in edges]
    report.stats.append(f'Network: {len(edges)} links with |r| ≥ {thr:g} and ≥ {min_n} shared particles'
                        + (f'; mean |r| = {np.mean(rs):.3f}' if rs else ''))
    for i, j, r, n in sorted(edges, key=lambda e: -abs(e[2]))[:8]:
        report.stats.append(f'  {plain(names[i])} — {plain(names[j])}: r = {r:.3f} (n = {n})')
    report.counts[panel['id']] = int(base.sum())
    handles(report, panel)['network'] = {'xy': xy, 'names': names, 'edges': edges}
    add_legend(ax, panel, proxies, default_loc='lower right', min_items=1)


def _prepare(M, how):
    """Rows of particle values prepared for PCA."""
    if how == 'clr':
        from results.compositional import _apply_clr
        return np.asarray(_apply_clr(M, zero_replacement='multiplicative'), dtype=float)
    if how == 'log':
        return np.log10(np.where(M > 0, M, np.nan))
    sd = M.std(axis=0)
    sd[sd == 0] = 1.0
    return (M - M.mean(axis=0)) / sd


def draw_pca(fig, ax, panel, table, report, style):
    """Principal components of particle compositions, with loadings drawn as arrows.

    This is the projection view of the Clustering node: values are closed and
    centred-log-ratio transformed (or log / z-scored), the first two principal
    components are plotted for each group, and each isotope's loading is an
    arrow from the centre.
    """
    exprs = item_exprs(panel, table)
    if len(exprs) < 2:
        raise ExpressionError('List at least two isotopes or expressions')
    base = base_mask(panel, table)
    M = np.column_stack([np.clip(np.nan_to_num(evaluate(e, table), nan=0.0), 0, None) for e in exprs])
    keep = base & (M.sum(axis=1) > 0)
    how = panel.get('pca_transform', 'clr')
    if how == 'log':
        keep &= (M > 0).all(axis=1)
    if keep.sum() < 3:
        raise ExpressionError('Not enough particles for a PCA')
    try:
        X = _prepare(M[keep], how)
    except Exception as exc:
        raise ExpressionError(f'Could not transform the values: {exc}')
    X = X[:, np.isfinite(X).all(axis=0)] if np.isfinite(X).all(axis=0).any() else X
    X = X - X.mean(axis=0)
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    if S.size < 2:
        raise ExpressionError('Need at least two varying isotopes')
    scores = U[:, :2] * S[:2]
    var = S ** 2 / max(np.sum(S ** 2), 1e-300) * 100
    idx = np.flatnonzero(keep)
    size = float(panel.get('marker_size') or 16) * 0.7
    alpha = float(panel.get('alpha') or 0.7)
    hover = handles(report, panel).setdefault('points', [])
    for g in resolve_groups(panel, table):
        m = g.mask[idx]
        if not m.any():
            continue
        ax.scatter(scores[m, 0], scores[m, 1], s=size, color=g.color, alpha=alpha, linewidths=0,
                   rasterized=True, zorder=2, label=label_n(g, int(m.sum()), panel))
        hover.append({'x': scores[m, 0], 'y': scores[m, 1], 'index': idx[m], 'group': g.label,
                      'color': g.color})
    if panel.get('pca_loadings', True):
        names = [item_label(panel, e, table, style, short=True) for e in exprs]
        L = Vt[:2].T
        span = np.abs(scores).max(axis=0)
        scale = 0.85 * float(np.min(span / np.maximum(np.abs(L).max(axis=0), 1e-12)))
        for (lx, ly), name in zip(L, names):
            ax.annotate('', xy=(lx * scale, ly * scale), xytext=(0, 0),
                        arrowprops={'arrowstyle': '-|>', 'color': ink('#111827'), 'lw': 1.2}, zorder=5)
            t = ax.text(lx * scale * 1.1, ly * scale * 1.1, name, ha='center', va='center',
                        fontsize='small', zorder=6, color=ink('#111827'),
                        bbox={'boxstyle': 'round,pad=0.15', 'fc': 'white', 'ec': 'none', 'alpha': 0.75})
            t._fb_cell = True
    ax.axhline(0, color='#9ca3af', lw=0.7, zorder=1)
    ax.axvline(0, color='#9ca3af', lw=0.7, zorder=1)
    hd = handles(report, panel)
    hd['x_name'], hd['y_name'], hd['table'] = 'PC1', 'PC2', table
    report.counts[panel['id']] = int(keep.sum())
    report.stats.append(f'PCA ({PCA_TRANSFORMS.get(how, how)}): PC1 explains {var[0]:.1f}%, '
                        f'PC2 {var[1]:.1f}% of the variance ({int(keep.sum()):,} particles)')
    style_axes(ax, panel, table, style)
    if not panel.get('x_label'):
        ax.set_xlabel(f'PC1 ({var[0]:.1f}%)')
    if not panel.get('y_label'):
        ax.set_ylabel(f'PC2 ({var[1]:.1f}%)')
    add_legend(ax, panel)
