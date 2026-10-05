"""Distribution charts: histograms, box plots and violin plots."""

from __future__ import annotations

import numpy as np

from results.figure_builder.core.common import (
    add_legend, bin_edges, handles, label_n, style_axes, value_groups)
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
    groups = [(g, v) for g, v in value_groups(panel, table) if v.size]
    if not groups:
        raise ExpressionError('No finite values to plot')
    allv = np.concatenate([v for _, v in groups])
    bins = max(2, int(panel.get('bins') or 40))
    log_x = bool(panel.get('log_x'))
    edges = bin_edges(allv, bins, log_x)
    if log_x:
        ax.set_xscale('log')
    if panel.get('log_y'):
        ax.set_yscale('log')
    filled = panel.get('hist_style', 'filled') == 'filled'
    density = bool(panel.get('density'))
    cumulative = bool(panel.get('cumulative'))
    handles(report, panel)['hist'] = [(g.label, edges, np.histogram(v, bins=edges)[0]) for g, v in groups]
    for g, v in groups:
        if cumulative:
            xs = np.sort(v)
            ys = np.arange(1, xs.size + 1, dtype=float)
            if density:
                ys /= xs.size
            ax.step(np.r_[xs[0], xs], np.r_[0.0, ys], where='post', color=g.color,
                    lw=float(panel.get('line_width') or 1.6), ls=panel.get('line_style') or '-',
                    label=label_n(g, v.size, panel))
            continue
        if filled:
            ax.hist(v, bins=edges, density=density, histtype='bar', rwidth=1.0,
                    color=_with_alpha(g.color, 0.5 if len(groups) > 1 else 0.8),
                    edgecolor='white', linewidth=0.5, label=label_n(g, v.size, panel))
            if len(groups) > 1:
                ax.hist(v, bins=edges, density=density, histtype='step', color=_darker(g.color),
                        linewidth=1.0)
        else:
            ax.hist(v, bins=edges, density=density, histtype='step', color=g.color,
                    linewidth=float(panel.get('line_width') or 1.6), label=label_n(g, v.size, panel))
        if panel.get('kde') and v.size > 2 and not cumulative:
            t = np.log10(v) if log_x else v
            if np.ptp(t) > 0:
                kde = stats.gaussian_kde(t)
                grid = np.linspace(t.min(), t.max(), 256)
                width = (np.log10(edges[1]) - np.log10(edges[0])) if log_x else (edges[1] - edges[0])
                scale = 1.0 if density and not log_x else v.size * width
                if density and log_x:
                    scale = 1.0 / (np.log(10) * 10 ** grid)
                yk = kde(grid) * scale
                ax.plot(10 ** grid if log_x else grid, yk, color=g.color,
                        lw=float(panel.get('line_width') or 1.6), ls=panel.get('line_style') or '-')
    report.counts[panel['id']] = int(allv.size)
    _, lines = run_tests([(g.label, v) for g, v in groups], panel)
    report.stats.extend(lines)
    if cumulative:
        ylabel = 'Cumulative fraction' if density else 'Cumulative count'
    else:
        ylabel = 'Density' if density else 'Particle count'
    style_axes(ax, panel, table, style, panel['value'], '')
    if not panel.get('y_label'):
        ax.set_ylabel(ylabel)
    add_legend(ax, panel)


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
    if panel['kind'] == 'violin':
        plot_data = [np.log10(v) if log else v for v in data]
        if log:
            ax.set_yscale('linear')
        parts = ax.violinplot(plot_data, positions=positions, showmedians=False,
                              showextrema=False, widths=0.82)
        for body, (g, _) in zip(parts['bodies'], groups):
            body.set_facecolor(g.color)
            body.set_edgecolor(_darker(g.color))
            body.set_linewidth(0.9)
            body.set_alpha(0.6)
        for pos, v in zip(positions, plot_data):
            q1, med, q3 = np.percentile(v, [25, 50, 75])
            ax.vlines(pos, q1, q3, color='#1f2937', lw=5, zorder=3, capstyle='butt')
            ax.scatter([pos], [med], s=18, color='white', edgecolors='#1f2937', linewidths=0.8,
                       zorder=4)
        if panel.get('show_mean'):
            ax.scatter(positions, [np.mean(v) for v in plot_data], marker='s', s=26,
                       color='white', edgecolors='#1d4ed8', linewidths=1.2, zorder=5)
        if log:
            from matplotlib.ticker import FuncFormatter, MaxNLocator
            ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda val, _p: f'$10^{{{val:g}}}$'))
    else:
        bp = ax.boxplot(data, positions=positions, widths=0.58, patch_artist=True,
                        notch=bool(panel.get('notch')), showmeans=bool(panel.get('show_mean')),
                        showfliers=not panel.get('show_points'),
                        medianprops={'color': '#111827', 'lw': 1.8},
                        whiskerprops={'color': '#374151', 'lw': 1.1},
                        capprops={'color': '#374151', 'lw': 1.1},
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
            jitter = rng.uniform(-0.18, 0.18, size=vv.size)
            ax.scatter(pos + jitter, vv, s=4, color=g.color, alpha=0.35, linewidths=0,
                       rasterized=True, zorder=3)
    handles(report, panel)['categories'] = {'axis': 'x', 'positions': positions,
                                            'items': [(g.label, v) for g, v in groups]}
    ax.set_xticks(positions)
    ax.set_xticklabels([f'{g.label}\n(n={v.size})' if panel.get('show_n', True) else g.label
                        for g, v in groups])
    report.counts[panel['id']] = int(sum(v.size for v in data))
    pairs, lines = run_tests([(g.label, v) for g, v in groups], panel)
    report.stats.extend(lines)
    style_axes(ax, panel, table, style, '', panel['value'])
    draw_brackets(ax, pairs, positions, panel)
