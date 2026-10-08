"""Distribution charts: histograms, box plots and violin plots."""

from __future__ import annotations

import numpy as np

from results.figure_builder.core.common import (
    add_legend, bin_edges, compact, count_label, draw_marks, draw_summary_box, edges_by_width,
    float_or_none, handles, ink, label_n, style_axes, value_groups)
from results.figure_builder.core.expressions import ExpressionError
from results.figure_builder.core.stats import draw_brackets, run_tests


def _with_alpha(color, alpha):
    """``color`` as an RGBA tuple with the given opacity."""
    from matplotlib.colors import to_rgba
    return to_rgba(color, alpha)


def _darker(color, factor=0.72):
    """A darker shade of ``color`` for outlines."""
    from matplotlib.colors import to_rgb
    r, g, b = to_rgb(color)
    return (r * factor, g * factor, b * factor)


def draw_histogram(fig, ax, panel, table, report, style):
    """Overlaid histograms per group with log binning, KDE, cumulative and tests."""
    from scipy import stats
    triples = [t for t in value_groups(panel, table, with_weights=True) if t[1].size]
    if not triples:
        raise ExpressionError('No finite values to plot')
    groups = [(g, v) for g, v, _w in triples]
    weights = [w if panel.get('per_ml') else None for _g, _v, w in triples]
    allv = np.concatenate([v for _, v in groups])
    bins = max(2, int(panel.get('bins') or 40))
    log_x = bool(panel.get('log_x'))
    edges = None
    if panel.get('bin_mode') == 'width':
        edges = edges_by_width(allv, panel.get('bin_width'), log_x)
    if edges is None:
        edges = bin_edges(allv, bins, log_x)
    if log_x:
        ax.set_xscale('log')
    if panel.get('log_y'):
        ax.set_yscale('log')
    filled = panel.get('hist_style', 'filled') == 'filled'
    density = bool(panel.get('density'))
    cumulative = bool(panel.get('cumulative'))
    handles(report, panel)['hist'] = [(g.label, edges, np.histogram(v, bins=edges, weights=w)[0])
                                      for (g, v), w in zip(groups, weights)]
    for (g, v), w in zip(groups, weights):
        scale_n = float(np.sum(w)) if w is not None else float(v.size)
        if cumulative:
            order = np.argsort(v)
            xs = v[order]
            ys = np.cumsum(w[order]) if w is not None else np.arange(1, xs.size + 1, dtype=float)
            if density:
                ys = ys / max(ys[-1], 1e-300)
            ax.step(np.r_[xs[0], xs], np.r_[0.0, ys], where='post', color=g.color,
                    lw=float(panel.get('line_width') or 1.6), ls=panel.get('line_style') or '-',
                    label=label_n(g, v.size, panel))
            continue
        if filled:
            counts, _e, bars = ax.hist(v, bins=edges, density=density, histtype='bar', rwidth=1.0,
                                       weights=w, color=_with_alpha(g.color, 0.5 if len(groups) > 1 else 0.8),
                                       edgecolor='white', linewidth=0.5, label=label_n(g, v.size, panel))
            if len(groups) > 1:
                ax.hist(v, bins=edges, density=density, histtype='step', color=_darker(g.color),
                        linewidth=1.0, weights=w)
            elif panel.get('bar_values') and not density:
                _bar_values(ax, edges, counts, log_x, bool(panel.get('per_ml')))
        else:
            ax.hist(v, bins=edges, density=density, histtype='step', color=g.color, weights=w,
                    linewidth=float(panel.get('line_width') or 1.6), label=label_n(g, v.size, panel))
        if panel.get('kde') and v.size > 2 and not cumulative:
            t = np.log10(v) if log_x else v
            if np.ptp(t) > 0:
                kde = stats.gaussian_kde(t)
                grid = np.linspace(t.min(), t.max(), 256)
                width = (np.log10(edges[1]) - np.log10(edges[0])) if log_x else (edges[1] - edges[0])
                scale = 1.0 if density and not log_x else scale_n * width
                if density and log_x:
                    scale = 1.0 / (np.log(10) * 10 ** grid)
                yk = kde(grid) * scale
                ax.plot(10 ** grid if log_x else grid, yk, color=g.color,
                        lw=float(panel.get('line_width') or 1.6), ls=panel.get('line_style') or '-')
        if not cumulative:
            _fit_curve(ax, g, v, edges, log_x, density, panel, report, scale_n)
        _stat_lines(ax, g, v, panel, edges, len(groups) == 1)
    report.counts[panel['id']] = int(allv.size)
    draw_marks(ax, panel, [v for _g, v in groups], vertical=True)
    _, lines = run_tests([(g.label, v) for g, v in groups], panel)
    report.stats.extend(lines)
    if cumulative:
        ylabel = 'Cumulative fraction' if density else 'Cumulative ' + count_label(panel).lower()
    else:
        ylabel = 'Density' if density else count_label(panel)
    style_axes(ax, panel, table, style, panel['value'], '')
    if not panel.get('y_label'):
        ax.set_ylabel(ylabel)
    add_legend(ax, panel)
    draw_summary_box(ax, panel, [(g.label, v) for g, v in groups])


MARKS = {'none': 'Nothing', 'median': 'Median', 'mean': 'Mean', 'mode': 'Mode (tallest bin)',
         'both': 'Median and mean', 'all': 'Median, mean and mode'}
"""Statistic lines a histogram can mark."""


def _bar_values(ax, edges, counts, log_x, per_ml):
    """Write each bin's count (or particles per mL) above its bar."""
    for k, c in enumerate(counts):
        if c <= 0:
            continue
        x = np.sqrt(edges[k] * edges[k + 1]) if log_x else (edges[k] + edges[k + 1]) / 2
        txt = compact(c) if per_ml else f'{int(round(c))}'
        t = ax.text(x, c, txt, ha='center', va='bottom', fontsize='xx-small', color=ink('#374151'),
                    zorder=6, clip_on=True)
        t._fb_cell = True


def _mode_of(v, edges):
    """Centre of the tallest bin of ``v`` with the drawn bin edges."""
    counts, _ = np.histogram(v, bins=edges)
    if not counts.size or counts.max() == 0:
        return None
    k = int(np.argmax(counts))
    lo, hi = edges[k], edges[k + 1]
    return float(np.sqrt(lo * hi)) if lo > 0 and hi / lo > 1.5 else float((lo + hi) / 2)


def _stat_lines(ax, g, v, panel, edges=None, label=False):
    """Lines at a group's median, mean and/or mode, each with its value written on top."""
    mode = panel.get('mark_stats', 'none')
    if mode == 'none' or v.size == 0:
        return
    from matplotlib import transforms
    color = _darker(g.color)
    wanted = []
    if mode in ('median', 'both', 'all'):
        wanted.append(('median', float(np.median(v)), '--'))
    if mode in ('mean', 'both', 'all'):
        wanted.append(('mean', float(np.mean(v)), ':'))
    if mode in ('mode', 'all') and edges is not None:
        m = _mode_of(v, edges)
        if m is not None:
            wanted.append(('mode', m, '-.'))
    trans = transforms.blended_transform_factory(ax.transData, ax.transAxes)
    top = 0.95
    if panel.get('summary_box') and str(panel.get('summary_loc') or 'upper right').startswith('upper'):
        top = 0.8
    for k, (name, value, ls) in enumerate(wanted):
        ax.axvline(value, color=color, lw=1.4, ls=ls, zorder=5)
        if label:
            t = ax.text(value, top - 0.09 * k, f' {name}: {value:.3g}', transform=trans, ha='left',
                        va='top', fontsize='x-small', color=color, zorder=8,
                        bbox={'boxstyle': 'round,pad=0.15', 'fc': 'white', 'ec': 'none', 'alpha': 0.75})
            t._fb_cell = True


def _fit_curve(ax, g, v, edges, log_x, density, panel, report, scale_n=None):
    """Overlay a fitted normal or log-normal distribution and report its parameters."""
    from scipy import stats
    kind = panel.get('fit_dist', 'none')
    if kind == 'none' or v.size < 5:
        return
    if kind == 'lognormal':
        pos = v[v > 0]
        if pos.size < 5:
            return
        logs = np.log(pos)
        mu, sigma = float(np.mean(logs)), float(np.std(logs, ddof=1))
        lo, hi = pos.min(), pos.max()
        xs = np.logspace(np.log10(lo), np.log10(hi), 300) if log_x else np.linspace(lo, hi, 300)
        pdf = stats.lognorm.pdf(xs, s=sigma, scale=np.exp(mu))
        report.stats.append(f'{g.label}: log-normal fit, geometric mean = {np.exp(mu):.4g}, '
                            f'geometric SD = {np.exp(sigma):.3g}, mode = {np.exp(mu - sigma ** 2):.4g}, '
                            f'n = {pos.size}')
    else:
        mu, sd = float(np.mean(v)), float(np.std(v, ddof=1))
        lo, hi = v.min(), v.max()
        xs = np.linspace(lo, hi, 300)
        pdf = stats.norm.pdf(xs, mu, sd)
        report.stats.append(f'{g.label}: normal fit, mean = {mu:.4g}, SD = {sd:.4g}, n = {v.size}')
    if density:
        ys = pdf
    else:
        idx = np.clip(np.searchsorted(edges, xs, side='right') - 1, 0, len(edges) - 2)
        widths = np.diff(edges)[idx]
        ys = pdf * (v.size if scale_n is None else scale_n) * widths
    from matplotlib import patheffects
    ax.plot(xs, ys, color=_darker(g.color), lw=2.0, zorder=6,
            path_effects=[patheffects.withStroke(linewidth=4, foreground='white')])


def draw_distribution(fig, ax, panel, table, report, style):
    """Box or violin plot per group, optional points, mean, notches and brackets."""
    groups = [(g, v) for g, v in value_groups(panel, table) if v.size]
    if not groups:
        raise ExpressionError('No finite values to plot')
    log = bool(panel.get('log_y'))
    if log:
        ax.set_yscale('log')
    positions = list(range(1, len(groups) + 1))
    data = [v for _, v in groups]
    half = panel['kind'] == 'violin' and panel.get('violin_style') == 'half'
    if panel['kind'] == 'violin':
        plot_data = [np.log10(v) if log else v for v in data]
        if log:
            ax.set_yscale('linear')
        bw = float_or_none(panel.get('bandwidth')) or None
        kept = [i for i, v in enumerate(plot_data) if v.size >= 2 and np.ptp(v) > 0]
        parts = ax.violinplot([plot_data[i] for i in kept], positions=[positions[i] for i in kept],
                              showmedians=False, showextrema=False, widths=0.82,
                              bw_method=bw) if kept else {'bodies': []}
        for body, i in zip(parts['bodies'], kept):
            g = groups[i][0]
            body.set_facecolor(g.color)
            body.set_edgecolor(_darker(g.color))
            body.set_linewidth(0.9)
            body.set_alpha(0.6)
            if half:
                verts = body.get_paths()[0].vertices
                verts[:, 0] = np.minimum(verts[:, 0], positions[i])
        if half:
            bp = ax.boxplot(plot_data, positions=[p + 0.13 for p in positions], widths=0.12,
                            patch_artist=True, showfliers=False,
                            medianprops={'color': ink('#111827'), 'lw': 1.6},
                            whiskerprops={'color': ink('#374151'), 'lw': 1.0},
                            capprops={'color': ink('#374151'), 'lw': 1.0})
            for box, (g, _v) in zip(bp['boxes'], groups):
                box.set_facecolor(_with_alpha(g.color, 0.35))
                box.set_edgecolor(_darker(g.color))
        else:
            for pos, v in zip(positions, plot_data):
                q1, med, q3 = np.percentile(v, [25, 50, 75])
                ax.vlines(pos, q1, q3, color=ink('#1f2937'), lw=5, zorder=3, capstyle='butt')
                ax.scatter([pos], [med], s=18, color='white', edgecolors=ink('#1f2937'), linewidths=0.8,
                           zorder=4)
        if panel.get('show_mean'):
            ax.scatter(positions, [np.mean(v) for v in plot_data], marker='s', s=26,
                       color='white', edgecolors='#1d4ed8', linewidths=1.2, zorder=5)
        if log:
            from matplotlib.ticker import FuncFormatter, MaxNLocator
            span = max(np.ptp(np.concatenate(plot_data)), 1e-9) if plot_data else 1.0
            ax.yaxis.set_major_locator(MaxNLocator(integer=span >= 2.5, nbins=6))
            ax.yaxis.set_major_formatter(FuncFormatter(
                lambda val, _p: f'$10^{{{val:g}}}$' if float(val).is_integer() else f'{10 ** val:.3g}'))
    else:
        bp = ax.boxplot(data, positions=positions, widths=0.58, patch_artist=True,
                        notch=bool(panel.get('notch')), showmeans=bool(panel.get('show_mean')),
                        showfliers=bool(panel.get('show_outliers', True)) and not panel.get('show_points'),
                        medianprops={'color': ink('#111827'), 'lw': 1.8},
                        whiskerprops={'color': ink('#374151'), 'lw': 1.1},
                        capprops={'color': ink('#374151'), 'lw': 1.1},
                        meanprops={'marker': 's', 'markerfacecolor': 'white',
                                   'markeredgecolor': '#1d4ed8', 'markersize': 6,
                                   'markeredgewidth': 1.2},
                        flierprops={'marker': 'o', 'markersize': 3, 'alpha': 0.55,
                                    'markeredgewidth': 0})
        for i, (box, (g, _)) in enumerate(zip(bp['boxes'], groups)):
            box.set_facecolor(_with_alpha(g.color, 0.55))
            box.set_edgecolor(_darker(g.color))
            box.set_linewidth(1.1)
            if i < len(bp['fliers']):
                bp['fliers'][i].set_markerfacecolor(g.color)
    if panel.get('show_points'):
        rng = np.random.default_rng(0)
        for pos, (g, v) in zip(positions, groups):
            vv = np.log10(v) if (log and panel['kind'] == 'violin') else v
            if half:
                xs = pos + rng.uniform(0.25, 0.42, size=vv.size)
            else:
                xs = pos + rng.uniform(-0.18, 0.18, size=vv.size)
            ax.scatter(xs, vv, s=4, color=g.color, alpha=0.35, linewidths=0,
                       rasterized=True, zorder=3)
    handles(report, panel)['categories'] = {'axis': 'x', 'positions': positions,
                                            'items': [(g.label, v) for g, v in groups]}
    ax.set_xticks(positions)
    ax.set_xticklabels([f'{g.label}\n(n={v.size})' if panel.get('show_n', True) else g.label
                        for g, v in groups])
    report.counts[panel['id']] = int(sum(v.size for v in data))
    from results.figure_builder.charts.detectability import draw_on_categories
    draw_on_categories(ax, panel, table, report, groups, positions, panel['value'],
                       to_axis=np.log10 if (log and panel['kind'] == 'violin') else None)
    pairs, lines = run_tests([(g.label, v) for g, v in groups], panel)
    report.stats.extend(lines)
    style_axes(ax, panel, table, style, '', panel['value'])
    if half:
        ax.set_xlim(0.4, len(groups) + 0.6)
    in_log10 = log and panel['kind'] == 'violin'
    marks = dict(panel)
    dl = float_or_none(panel.get('dl_value'))
    if in_log10 and dl is not None:
        marks['dl_value'] = np.log10(dl) if dl > 0 else None
    draw_marks(ax, marks, [np.log10(v) if in_log10 else v for v in data], vertical=False)
    draw_brackets(ax, pairs, positions, panel)
    draw_summary_box(ax, panel, [(g.label, v) for g, v in groups])
