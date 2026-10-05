"""Matrix charts: correlation matrix, heatmap, co-occurrence and scatter matrix."""

from __future__ import annotations

import numpy as np

from results.figure_builder.core.common import (
    base_mask, bin_edges, cmap_name, finite_mask, handles, item_exprs, item_label,
    resolve_groups)
from results.figure_builder.core.expressions import ExpressionError, evaluate, plain, split_symbol

METHOD_NAMES = {'pearson': 'Pearson r', 'spearman': 'Spearman ρ', 'kendall': 'Kendall τ'}


def _cell_text(ax, x, y, text, value, vmin, vmax, cmap, size='small'):
    """Write a value inside a heatmap cell in a colour that stays readable."""
    import matplotlib
    norm = 0.5 if vmax == vmin else (value - vmin) / (vmax - vmin)
    r, g, b, _a = matplotlib.colormaps[cmap](float(np.clip(norm, 0, 1)))
    light = (0.299 * r + 0.587 * g + 0.114 * b) > 0.55
    t = ax.text(x, y, text, ha='center', va='center', fontsize=size,
                color='#111111' if light else '#ffffff')
    t._fb_cell = True
    return t


def cell_fontsize(fig, ax, ncols, nrows):
    """A font size for in-cell values that fits the cell."""
    pos = ax.get_position()
    w_in = pos.width * fig.get_figwidth() / max(1, ncols)
    h_in = pos.height * fig.get_figheight() / max(1, nrows)
    cell = min(w_in, h_in * 2.2)
    return float(max(4.5, min(10.0, cell * 15)))


def _matrix_ticks(ax, panel, rows, cols):
    """Category tick labels on both axes of an image-style matrix."""
    rot = float(panel.get('xtick_rotation') or 45)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=rot, ha='right' if 0 < rot < 90 else 'center',
                       rotation_mode='anchor')
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(rows)
    ax.tick_params(length=0)
    for side in ('top', 'right', 'left', 'bottom'):
        ax.spines[side].set_visible(False)
    if panel.get('title'):
        ax.set_title(panel['title'])


def _colorbar(fig, ax, img, panel, report, label):
    """Attach a colour bar to ``ax`` and record it for text styling."""
    cb = fig.colorbar(img, ax=ax, pad=0.02, fraction=0.05)
    cb.ax.set_zorder(ax.get_zorder())
    cb.outline.set_linewidth(0.6)
    cb.ax.tick_params(direction='out', length=3, width=0.6)
    cb.set_label(panel.get('cbar_label') or label)
    handles(report, panel)['cbar'] = cb
    return cb


def _stars(p):
    """Significance stars for a p-value."""
    if not np.isfinite(p):
        return ''
    return '***' if p < 1e-3 else '**' if p < 1e-2 else '*' if p < 0.05 else ''


def correlation(a, b, method):
    """Correlation coefficient and p-value of two arrays with one of three methods."""
    from scipy import stats
    if method == 'spearman':
        res = stats.spearmanr(a, b)
    elif method == 'kendall':
        res = stats.kendalltau(a, b)
    else:
        res = stats.pearsonr(a, b)
    return float(res.statistic), float(res.pvalue)


def draw_corr_matrix(fig, ax, panel, table, report, style):
    """Pairwise correlation of isotopes or expressions, as a coloured matrix."""
    exprs = item_exprs(panel, table)
    if len(exprs) < 2:
        raise ExpressionError('List at least two isotopes or expressions')
    base = base_mask(panel, table)
    values = [evaluate(e, table) for e in exprs]
    method = panel.get('corr_method', 'pearson')
    log = bool(panel.get('log_values'))
    drop = panel.get('drop_zeros', True)
    min_n = max(3, int(panel.get('min_n') or 10))
    k = len(exprs)
    R = np.full((k, k), np.nan)
    P = np.full((k, k), np.nan)
    N = np.zeros((k, k), dtype=int)
    for i in range(k):
        for j in range(i, k):
            a, b = values[i], values[j]
            m = base & finite_mask(a, b, log_flags=(log, log))
            if drop:
                m &= (a != 0) & (b != 0)
            n = int(m.sum())
            N[i, j] = N[j, i] = n
            if i == j:
                R[i, i] = 1.0 if n >= min_n else np.nan
                continue
            if n < min_n:
                continue
            x, y = a[m], b[m]
            if log:
                x, y = np.log10(x), np.log10(y)
            if np.ptp(x) == 0 or np.ptp(y) == 0:
                continue
            r, p = correlation(x, y, method)
            R[i, j] = R[j, i] = r
            P[i, j] = P[j, i] = p
    tri = panel.get('triangle', 'full')
    show = np.ones((k, k), dtype=bool)
    if tri == 'lower':
        show = np.tril(show)
    elif tri == 'upper':
        show = np.triu(show)
    data = np.where(show, R, np.nan)
    cmap = panel.get('div_cmap') or 'RdBu_r'
    if panel.get('reverse_cmap'):
        cmap = cmap[:-2] if cmap.endswith('_r') else f'{cmap}_r'
    img = ax.imshow(np.ma.masked_invalid(data), cmap=cmap, vmin=-1, vmax=1, aspect='auto',
                    interpolation='nearest')
    names = [item_label(panel, e, table, style, short=True) for e in exprs]
    _matrix_ticks(ax, panel, names, names)
    handles(report, panel)['matrix'] = {'values': data, 'rows': names, 'cols': names,
                                         'label': METHOD_NAMES.get(method, 'r'), 'n': N, 'p': P}
    if panel.get('annotate', True) and k <= 20:
        for i in range(k):
            for j in range(k):
                if show[i, j] and np.isfinite(R[i, j]):
                    txt = f'{R[i, j]:.2f}'
                    if panel.get('show_sig') and i != j:
                        txt += _stars(P[i, j])
                    _cell_text(ax, j, i, txt, R[i, j], -1, 1, cmap, cell_fontsize(fig, ax, k, k))
    _colorbar(fig, ax, img, panel, report, METHOD_NAMES.get(method, 'r')
              + (' (log values)' if log else ''))
    pairs = [(abs(R[i, j]), names[i], names[j], R[i, j], P[i, j], N[i, j])
             for i in range(k) for j in range(i + 1, k) if np.isfinite(R[i, j])]
    pairs.sort(reverse=True)
    for _a, n1, n2, r, p, n in pairs[:8]:
        report.stats.append(f'{METHOD_NAMES.get(method, "r")}: {plain(n1)} vs {plain(n2)} = {r:.3f} '
                            f'(p = {p:.3g}, n = {n})')
    report.counts[panel['id']] = int(base.sum())


def combination_keys(table, exprs, mask):
    """Per-particle combination labels (bare symbols joined by ' + ')."""
    values = [np.nan_to_num(evaluate(e, table), nan=0.0) for e in exprs]
    names = []
    for e in exprs:
        sym, _mass = split_symbol(e)
        names.append(sym if sym else e)
    idx = np.flatnonzero(mask)
    keys = np.empty(len(mask), dtype=object)
    keys[:] = ''
    det = np.vstack([v > 0 for v in values]) if values else np.zeros((0, len(mask)), dtype=bool)
    for i in idx:
        parts = [names[c] for c in range(len(values)) if det[c, i]]
        keys[i] = ' + '.join(parts) if parts else 'none'
    return keys, values


def draw_heatmap(fig, ax, panel, table, report, style):
    """Heatmap of isotopes against groups, element combinations or single particles."""
    import matplotlib.colors as mcolors
    exprs = item_exprs(panel, table)
    if not exprs:
        raise ExpressionError('List isotopes or expressions for the columns')
    rows_mode = panel.get('heat_rows', 'groups')
    agg = panel.get('heat_value', 'mean')
    drop = panel.get('drop_zeros', True)
    cols = [item_label(panel, e, table, style, short=True) for e in exprs]
    base = base_mask(panel, table)
    values = [evaluate(e, table) for e in exprs]

    def summarise(mask):
        out = []
        for v in values:
            vv = v[mask & np.isfinite(v)]
            if agg == 'detect':
                out.append(100.0 * np.count_nonzero(vv > 0) / vv.size if vv.size else np.nan)
                continue
            if agg == 'count':
                out.append(float(np.count_nonzero(vv > 0)))
                continue
            if drop and agg in ('mean', 'median'):
                vv = vv[vv != 0]
            if vv.size == 0:
                out.append(np.nan)
            elif agg == 'median':
                out.append(float(np.median(vv)))
            elif agg == 'sum':
                out.append(float(np.sum(vv)))
            else:
                out.append(float(np.mean(vv)))
        return out

    if rows_mode == 'particles':
        idx = np.flatnonzero(base)
        cap = max(10, int(panel.get('max_rows') or 2000))
        if idx.size > cap:
            idx = np.sort(np.random.default_rng(0).choice(idx, cap, replace=False))
        M = np.vstack([np.nan_to_num(v[idx], nan=0.0) for v in values]).T
        if agg in ('detect', 'count'):
            agg = 'mean'
        if panel.get('heat_norm', 'none') == 'none' and not panel.get('log_color'):
            tot = M.sum(axis=1, keepdims=True)
            M = np.divide(M, tot, out=np.zeros_like(M), where=tot > 0) * 100
            unit = '% of particle'
        else:
            unit = 'value'
        order = np.lexsort((-M.sum(axis=1), np.argmax(M, axis=1)))
        M = M[order]
        rows = []
        row_title = f'Particles (n = {M.shape[0]:,})'
    elif rows_mode == 'combinations':
        keys, _v = combination_keys(table, exprs, base)
        uniq, counts = np.unique(keys[base], return_counts=True)
        order = np.argsort(-counts)[:max(1, int(panel.get('top_n') or 15))]
        rows = [f'{uniq[i]} (n={counts[i]})' if panel.get('show_n', True) else str(uniq[i])
                for i in order]
        M = np.array([summarise(base & (keys == uniq[i])) for i in order], dtype=float)
        row_title = 'Element combination'
        unit = ''
    else:
        groups = resolve_groups(panel, table)
        rows = [g.label for g in groups]
        M = np.array([summarise(g.mask) for g in groups], dtype=float)
        row_title = ''
        unit = ''
    if M.size == 0:
        raise ExpressionError('Nothing to show')
    norm_mode = panel.get('heat_norm', 'none')
    with np.errstate(all='ignore'):
        if norm_mode == 'row':
            M = M / np.nanmax(np.abs(M), axis=1, keepdims=True)
        elif norm_mode == 'column':
            M = M / np.nanmax(np.abs(M), axis=0, keepdims=True)
        elif norm_mode == 'zscore':
            M = (M - np.nanmean(M, axis=0, keepdims=True)) / np.nanstd(M, axis=0, keepdims=True)
    label = {'mean': 'Mean', 'median': 'Median', 'sum': 'Sum', 'detect': 'Detected in (%)',
             'count': 'Particles detected'}.get(agg, agg)
    if rows_mode == 'particles':
        label = unit
    if norm_mode == 'row':
        label += ' (÷ row max)'
    elif norm_mode == 'column':
        label += ' (÷ column max)'
    elif norm_mode == 'zscore':
        label = 'z-score per column'
    transpose = bool(panel.get('transpose'))
    if transpose:
        M = M.T
        rows, cols = cols, rows
    cmap = cmap_name(panel)
    finite = M[np.isfinite(M)]
    norm = None
    if panel.get('log_color') and finite.size and (finite > 0).any():
        norm = mcolors.LogNorm(vmin=finite[finite > 0].min(), vmax=finite.max())
    img = ax.imshow(np.ma.masked_invalid(M), cmap=cmap, aspect='auto', interpolation='nearest',
                    norm=norm)
    handles(report, panel)['matrix'] = {'values': M, 'rows': list(rows), 'cols': list(cols),
                                         'label': label}
    if rows_mode == 'particles':
        rot = float(panel.get('xtick_rotation') or 45)
        if transpose:
            ax.set_yticks(range(len(rows)))
            ax.set_yticklabels(rows)
            ax.set_xticks([])
            ax.set_xlabel(panel.get('x_label') or row_title)
        else:
            ax.set_xticks(range(len(cols)))
            ax.set_xticklabels(cols, rotation=rot, ha='right' if 0 < rot < 90 else 'center',
                               rotation_mode='anchor')
            ax.set_yticks([])
            ax.set_ylabel(panel.get('y_label') or row_title)
        for side in ('top', 'right', 'left', 'bottom'):
            ax.spines[side].set_visible(False)
        if panel.get('title'):
            ax.set_title(panel['title'])
    else:
        _matrix_ticks(ax, panel, rows, cols)
        if row_title and not transpose and not panel.get('y_label'):
            ax.set_ylabel(row_title)
        if panel.get('x_label'):
            ax.set_xlabel(panel['x_label'])
        if panel.get('y_label'):
            ax.set_ylabel(panel['y_label'])
        if panel.get('annotate', True) and M.size <= 400 and finite.size:
            vmin, vmax = float(np.nanmin(finite)), float(np.nanmax(finite))
            for i in range(M.shape[0]):
                for j in range(M.shape[1]):
                    v = M[i, j]
                    if np.isfinite(v):
                        txt = f'{v:.0f}' if abs(v) >= 100 else f'{v:.3g}'
                        shade = v if norm is None else (np.log10(max(v, 1e-300)) if v > 0 else vmin)
                        lo = vmin if norm is None else np.log10(max(norm.vmin, 1e-300))
                        hi = vmax if norm is None else np.log10(norm.vmax)
                        _cell_text(ax, j, i, txt, shade, lo, hi, cmap,
                                   cell_fontsize(fig, ax, M.shape[1], M.shape[0]))
    _colorbar(fig, ax, img, panel, report, label)
    report.counts[panel['id']] = int(base.sum())


def draw_cooccurrence(fig, ax, panel, table, report, style):
    """How often isotopes are detected together in the same particle."""
    exprs = item_exprs(panel, table)
    if len(exprs) < 2:
        raise ExpressionError('List at least two isotopes or expressions')
    base = base_mask(panel, table)
    det = np.vstack([(np.nan_to_num(evaluate(e, table), nan=0.0) > 0) & base for e in exprs])
    n = max(1, int(base.sum()))
    both = det.astype(int) @ det.T.astype(int)
    mode = panel.get('cooc_mode', 'joint')
    with np.errstate(all='ignore'):
        if mode == 'conditional':
            M = 100.0 * both / np.diag(both)[:, None]
            label = '% of row particles with column isotope'
        elif mode == 'count':
            M = both.astype(float)
            label = 'Particles containing both'
        else:
            M = 100.0 * both / n
            label = '% of particles containing both'
    k = len(exprs)
    tri = panel.get('triangle', 'full')
    show = np.ones((k, k), dtype=bool)
    if tri == 'lower':
        show = np.tril(show)
    elif tri == 'upper':
        show = np.triu(show)
    data = np.where(show, M, np.nan)
    cmap = cmap_name(panel)
    img = ax.imshow(np.ma.masked_invalid(data), cmap=cmap, aspect='auto', interpolation='nearest')
    names = [item_label(panel, e, table, style, short=True) for e in exprs]
    _matrix_ticks(ax, panel, names, names)
    handles(report, panel)['matrix'] = {'values': data, 'rows': names, 'cols': names, 'label': label}
    finite = data[np.isfinite(data)]
    if panel.get('annotate', True) and k <= 20 and finite.size:
        vmin, vmax = float(finite.min()), float(finite.max())
        for i in range(k):
            for j in range(k):
                if show[i, j] and np.isfinite(M[i, j]):
                    txt = f'{M[i, j]:.0f}' if mode == 'count' else f'{M[i, j]:.1f}'
                    _cell_text(ax, j, i, txt, M[i, j], vmin, vmax, cmap, cell_fontsize(fig, ax, k, k))
    _colorbar(fig, ax, img, panel, report, label)
    report.counts[panel['id']] = int(base.sum())


def draw_pairs(fig, ax, panel, table, report, style):
    """Scatter matrix: every pair of isotopes, histograms on the diagonal."""
    exprs = item_exprs(panel, table)[:6]
    if len(exprs) < 2:
        raise ExpressionError('List two to six isotopes or expressions')
    groups = resolve_groups(panel, table)
    log = bool(panel.get('log_values'))
    drop = panel.get('drop_zeros', True)
    values = [evaluate(e, table) for e in exprs]
    names = [item_label(panel, e, table, style) for e in exprs]
    k = len(exprs)
    pos = ax.get_position()
    ax.axis('off')
    gap = 0.012
    w = (pos.width - gap * (k - 1)) / k
    h = (pos.height - gap * (k - 1)) / k
    grid = [[None] * k for _ in range(k)]
    extra = []
    size = max(1.0, float(panel.get('marker_size') or 12) * 0.5)
    alpha = float(panel.get('alpha') or 0.7)
    upper = panel.get('pairs_upper', 'r')
    method = panel.get('corr_method', 'pearson')
    for i in range(k):
        for j in range(k):
            if j > i and upper == 'empty':
                continue
            sub = fig.add_axes([pos.x0 + j * (w + gap), pos.y0 + (k - 1 - i) * (h + gap), w, h])
            sub.set_zorder(ax.get_zorder())
            grid[i][j] = sub
            extra.append(sub)
            xv, yv = values[j], values[i]
            if i == j:
                for g in groups:
                    m = g.mask & finite_mask(xv, log_flags=(log,))
                    if drop:
                        m &= xv != 0
                    if m.sum() < 2:
                        continue
                    edges = bin_edges(xv[m], 25, log)
                    sub.hist(xv[m], bins=edges, histtype='stepfilled', alpha=0.55, color=g.color)
                if log:
                    sub.set_xscale('log')
                sub.set_yticks([])
            elif j < i or upper == 'scatter':
                for g in groups:
                    m = g.mask & finite_mask(xv, yv, log_flags=(log, log))
                    if drop:
                        m &= (xv != 0) & (yv != 0)
                    sub.scatter(xv[m], yv[m], s=size, color=g.color, alpha=alpha, linewidths=0,
                                rasterized=True, label=g.label)
                if log:
                    sub.set_xscale('log')
                    sub.set_yscale('log')
            else:
                m = base_mask(panel, table) & finite_mask(xv, yv, log_flags=(log, log))
                if drop:
                    m &= (xv != 0) & (yv != 0)
                if m.sum() >= 3:
                    a, b = (np.log10(xv[m]), np.log10(yv[m])) if log else (xv[m], yv[m])
                    r, p = correlation(a, b, method)
                    t = sub.text(0.5, 0.5, f'{r:.2f}{_stars(p)}', transform=sub.transAxes,
                                 ha='center', va='center', fontsize='large',
                                 color='#b42318' if r < 0 else '#1c4f95')
                    t._fb_cell = True
                sub.set_xticks([])
                sub.set_yticks([])
            for side in ('top', 'right'):
                sub.spines[side].set_visible(False)
            if i < k - 1:
                sub.tick_params(labelbottom=False)
            else:
                sub.set_xlabel(names[j])
            if j > 0:
                sub.tick_params(labelleft=False)
            elif i > 0:
                sub.set_ylabel(names[i])
            sub.tick_params(labelsize='x-small')
    if panel.get('title'):
        ax.set_title(panel['title'])
        ax.title.set_visible(True)
    handles(report, panel)['extra_axes'] = extra
    if len(groups) > 1 and panel.get('legend', True):
        from matplotlib.lines import Line2D
        proxies = [Line2D([], [], ls='', marker='o', color=g.color, label=g.label) for g in groups]
        ax.legend(handles=proxies, loc='upper right', bbox_to_anchor=(1.0, 1.0), frameon=False,
                  fontsize=panel.get('legend_size') or 'small')
    report.counts[panel['id']] = int(base_mask(panel, table).sum())
