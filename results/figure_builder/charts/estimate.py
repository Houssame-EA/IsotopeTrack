"""Estimate chart: one value per group with its 95% interval."""

from __future__ import annotations

import numpy as np

from results.figure_builder.core import estimates
from results.figure_builder.core.common import add_legend, handles, ink, resolve_groups, style_axes
from results.figure_builder.core.expressions import ExpressionError, evaluate, pretty

MAX_PAIRS = 6
"""Most pairs of groups whose difference is reported."""

MIN_REPLICATE_PARTICLES = 5
"""Particles a replicate needs before its own value is marked."""


def group_estimate(table, expr: str, mask) -> estimates.Estimate | None:
    """Estimate *expr* on the particles of *mask*.

    A ratio is estimated as the ratio of its sums and anything else by its
    mean (see :mod:`results.figure_builder.core.estimates`). Particles
    where the value is not finite, or where a ratio's denominator is not
    positive, are left out.
    """
    v = np.asarray(evaluate(expr, table), dtype=float)
    den = estimates.denominator(expr)
    if den is None:
        return estimates.estimate(v[mask])
    w = np.asarray(evaluate(den, table), dtype=float)
    return estimates.estimate(v[mask], w[mask])


def draw_estimate(fig, ax, panel, table, report, style):
    """One value per group with its 95% interval, the groups in rows.

    A ratio such as ``206Pb / 207Pb`` is shown as the ratio of summed
    signals, which the large, well-counted particles decide; any other
    value as its mean. The open diamond is the median of the particles' own
    values, for comparison, and small open circles are the replicates of a
    pooled group, each estimated on its own. The differences between groups
    are reported under Statistics.
    """
    expr = (panel.get('value') or '').strip()
    if not expr:
        raise ExpressionError('Set a Value expression, e.g. 206Pb / 207Pb')
    groups = resolve_groups(panel, table)
    if not groups:
        raise ExpressionError('Every group is hidden')
    v = np.asarray(evaluate(expr, table), dtype=float)
    den = estimates.denominator(expr)
    ratio = den is not None
    keep = np.isfinite(v)
    if panel.get('drop_zeros', True):
        keep &= v != 0
    rows = []
    for g in groups:
        est = group_estimate(table, expr, g.mask & keep)
        if est is not None:
            rows.append((g, est))
    if not rows:
        raise ExpressionError('No group has three or more particles with a value')
    vertical = bool(panel.get('est_vertical'))
    size = max(5.0, float(panel.get('marker_size') or 12) * 0.75)
    lw = float(panel.get('line_width') or 1.8)
    pos = np.arange(len(rows), dtype=float)
    replicates = table.column('replicate') if panel.get('est_replicates', True) else None
    drew_median = drew_replicates = False
    for p, (g, est) in zip(pos, rows):
        m = g.mask & keep
        if vertical:
            ax.errorbar([p], [est.value], yerr=[est.half], fmt='o', color=g.color, ms=size,
                        lw=lw, capsize=5, capthick=lw, zorder=4)
        else:
            ax.errorbar([est.value], [p], xerr=[est.half], fmt='o', color=g.color, ms=size,
                        lw=lw, capsize=5, capthick=lw, zorder=4)
        if panel.get('est_median', True):
            used = m & (np.asarray(evaluate(den, table), dtype=float) > 0) if ratio else m
            med = float(np.median(v[used])) if used.any() else np.nan
            if np.isfinite(med):
                xy = (p + 0.24, med) if vertical else (med, p + 0.24)
                ax.plot(*xy, marker='D', mfc='white', mec=g.color, ms=size * 0.75, mew=1.3,
                        ls='none', zorder=3)
                drew_median = True
        if replicates is not None:
            names = list(dict.fromkeys(replicates[m].tolist()))
            if len(names) >= 2:
                for name in names:
                    rm = m & (replicates == name)
                    if int(rm.sum()) < MIN_REPLICATE_PARTICLES:
                        continue
                    rep = group_estimate(table, expr, rm)
                    if rep is None:
                        continue
                    xy = (p - 0.24, rep.value) if vertical else (rep.value, p - 0.24)
                    ax.plot(*xy, marker='o', mfc='none', mec=g.color, ms=size * 0.55, mew=1.1,
                            ls='none', zorder=3)
                    drew_replicates = True
        if panel.get('annotate', True):
            text = estimates.fmt_pm(est.value, est.half)
            if vertical:
                t = ax.annotate(text, (p, est.value + est.half), xytext=(0, 6),
                                textcoords='offset points', ha='center', va='bottom',
                                fontsize='small', color=g.color, fontweight='bold')
            else:
                t = ax.annotate(text, (est.value, p), xytext=(0, 8), textcoords='offset points',
                                ha='center', va='bottom', fontsize='small', color=g.color,
                                fontweight='bold')
            t._fb_cell = True
    labels = [f'{g.label}\n(n={est.n:,})' if panel.get('show_n', True) else g.label
              for g, est in rows]
    what = 'Ratio of summed signals' if ratio else 'Mean'
    if vertical:
        ax.set_xticks(pos)
        ax.set_xticklabels(labels)
        ax.set_xlim(-0.6, len(rows) - 0.4)
        if panel.get('log_y'):
            ax.set_yscale('log')
    else:
        ax.set_yticks(pos)
        ax.set_yticklabels(labels)
        ax.set_ylim(len(rows) - 0.4, -0.6)
        if panel.get('log_y'):
            ax.set_xscale('log')
    from matplotlib.lines import Line2D
    from matplotlib.ticker import NullLocator
    (ax.xaxis if vertical else ax.yaxis).set_minor_locator(NullLocator())
    dark = ink('#374151')
    proxies = [Line2D([], [], marker='o', color=dark, ms=6, lw=1.5, label=f'{what} ± 95% interval')]
    if drew_median:
        proxies.append(Line2D([], [], marker='D', mfc='white', mec=dark, ls='none', ms=5.5,
                              label='Median of particles'))
    if drew_replicates:
        proxies.append(Line2D([], [], marker='o', mfc='none', mec=dark, ls='none', ms=4.5,
                              label='Each replicate'))
    name = pretty(expr, table, style)
    style_axes(ax, panel, table, style, x_default='' if vertical else expr,
               y_default=expr if vertical else '')
    if vertical and not panel.get('y_label'):
        ax.set_ylabel(name)
    if not vertical and not panel.get('x_label'):
        ax.set_xlabel(name)
    record = handles(report, panel)
    record['estimates'] = [(g.label, est.value, est.se, est.n) for g, est in rows]
    record['categories'] = {'axis': 'x' if vertical else 'y', 'positions': list(pos),
                            'items': [(g.label, v[g.mask & keep]) for g, _est in rows]}
    report.counts[panel['id']] = int(sum(est.n for _g, est in rows))
    for g, est in rows:
        report.stats.append(f'{g.label}: {what.lower()} {estimates.fmt_pm(est.value, est.half)} '
                            f'(95% interval, n = {est.n:,})')
    pairs = [(i, j) for i in range(len(rows)) for j in range(i + 1, len(rows))][:MAX_PAIRS]
    for i, j in pairs:
        (ga, ea), (gb, eb) = rows[i], rows[j]
        z, p = estimates.difference(ea, eb)
        if not np.isfinite(z):
            continue
        rel = (ea.value / eb.value - 1) * 100 if eb.value else np.nan
        report.stats.append(f'{ga.label} against {gb.label}: difference {ea.value - eb.value:+.4g} '
                            f'({rel:+.1f}%), z = {z:.2f}, p = {p:.3g}')
    add_legend(ax, panel, proxies, min_items=1)
