"""Whether a particle is large enough to show a minor element at a natural ratio.

A particle with no detected Ti is only "Ti-free" if it was big enough for Ti to
have been seen. If Ti sits in the particle at the upper-crust Ti:Fe ratio,
Ti becomes detectable once the particle's Fe mass reaches

    m(Fe) = MDL(Ti) / (Ti:Fe)

where MDL(Ti) is the calibrated mass detection limit of Ti in that sample.
Below that Fe mass, missing Ti tells nothing. This module draws that mass on
box, violin and dot plots of the major element (C) and on mass-against-mass
scatter plots (B), and reports how many particles fall below it.

Only element masses are used, because counts depend on each isotope's
sensitivity. Nothing is drawn, and the report says why, when the plotted
value is not a single element's mass or the samples have no calibrated limit.
"""

from __future__ import annotations

import re

import numpy as np

from results.figure_builder.core.common import ink
from results.figure_builder.core.expressions import QUANTITY_PREFIXES, ExpressionError

LINE_COLORS = ['#7c3aed', '#0891b2', '#b45309', '#be123c']
"""Colours of the detectability lines, one per minor element."""


def mass_label(expr: str, table) -> str | None:
    """Isotope label of an expression that is one element's mass, else ``None``.

    ``mass:Fe`` qualifies, and so does a bare ``Fe`` when the figure reads
    element mass by default.
    """
    text = (expr or '').strip()
    m = re.match(r'^(\w+):(.+)$', text)
    if m and m.group(1) in QUANTITY_PREFIXES:
        prefix, name = m.group(1), m.group(2).strip()
    else:
        prefix, name = table.default_prefix, text
    if prefix != 'mass':
        return None
    try:
        return table.resolve_label(name)
    except ExpressionError:
        return None


def _ratio(panel, minor: str, major: str) -> tuple[float, str]:
    """Minor-to-major mass ratio to test against, and where it came from."""
    from results.figure_builder.core.references import crust_ratio
    custom = str(panel.get('ptl_ratio') or '').strip()
    if custom:
        try:
            value = float(custom)
        except ValueError as exc:
            raise ValueError(f'Ratio "{custom}" is not a number') from exc
        if value <= 0:
            raise ValueError('The ratio must be positive')
        return value, f'{minor}:{major} = {value:.3g}'
    value = crust_ratio(minor, major, 'mass')
    return value, 'upper-crust ratio'


def required_masses(panel, table, major_label: str, masks) -> list[tuple[str, list, str]]:
    """Major-element mass needed to detect each listed minor element.

    Args:
        panel: Panel carrying ``ptl_minor`` and optionally ``ptl_ratio``.
        table: Table with calibrated limits attached.
        major_label: Isotope label of the plotted element.
        masks: One particle mask per group; each group uses the highest
            limit among its samples.

    Returns:
        ``(minor_symbol, [mass or None per group], how)`` per minor element.

    Raises:
        ValueError: With a readable reason when nothing can be drawn.
    """
    from results.figure_builder.core.limits import group_limit
    from results.figure_builder.core.references import symbol_of
    minors = [m.strip() for m in str(panel.get('ptl_minor') or '').replace(';', ',').split(',') if m.strip()]
    major = symbol_of(major_label)
    out = []
    for name in minors:
        try:
            label = table.resolve_label(name)
        except ExpressionError as exc:
            raise ValueError(f'{name} is not measured in this data') from exc
        symbol = symbol_of(label)
        ratio, how = _ratio(panel, symbol, major)
        per_group = []
        for mask in masks:
            mdl = group_limit(table, 'mass', label, mask)
            per_group.append(None if mdl is None else mdl / ratio)
        if all(v is None for v in per_group):
            raise ValueError(f'No calibrated mass detection limit (MDL) for {label} in these samples')
        out.append((symbol, per_group, how))
    return out


def draw_on_categories(ax, panel, table, report, groups, positions, value_expr, horizontal=False,
                       to_axis=None):
    """Draw the needed major-element mass on each group of a box, violin or dot plot.

    Args:
        groups: ``[(group, values), ...]`` in drawing order.
        positions: Category positions of the groups.
        value_expr: The plotted expression (must be one element's mass).
        horizontal: Values run along the x axis.
        to_axis: Converts a mass to the axis's data coordinate, for charts
            drawn in log10 space; identity when ``None``.
    """
    if not str(panel.get('ptl_minor') or '').strip():
        return
    major_label = mass_label(value_expr, table)
    if major_label is None:
        report.stats.append('Detectability lines need the value as one element\'s mass, '
                            'e.g. mass:Fe')
        return
    try:
        lines = required_masses(panel, table, major_label, [g.mask for g, _v in groups])
    except ValueError as exc:
        report.stats.append(f'Detectability: {exc}')
        return
    from matplotlib.lines import Line2D
    major = major_label
    legend = []
    for k, (minor, per_group, how) in enumerate(lines):
        color = LINE_COLORS[k % len(LINE_COLORS)]
        shares = []
        for pos, (g, v), need in zip(positions, groups, per_group):
            if need is None:
                continue
            span = (pos - 0.42, pos + 0.42)
            at = to_axis(need) if to_axis is not None else need
            if horizontal:
                ax.vlines(at, *span, color=color, lw=1.8, ls=(0, (2, 1.5)), zorder=8)
            else:
                ax.hlines(at, *span, color=color, lw=1.8, ls=(0, (2, 1.5)), zorder=8)
            below = float(np.mean(v < need)) if v.size else 0.0
            shares.append(f'{g.label} {100 * below:.0f}%')
        legend.append(Line2D([], [], color=color, lw=1.8, ls=(0, (2, 1.5)),
                             label=f'{major} needed to see {minor} ({how})'))
        report.stats.append(f'Too small to show {minor} at the {how}: ' + ', '.join(shares))
    from matplotlib.legend import Legend
    leg = Legend(ax, legend, [h.get_label() for h in legend], loc='upper left', fontsize='x-small',
                 frameon=True, framealpha=0.85)
    leg.set_zorder(20)
    ax.add_artist(leg)


def draw_on_scatter(ax, panel, table, report, x_expr, y_expr):
    """Mark, on a mass-against-mass scatter, where the x element shows a minor one.

    Left of the line a particle is too small for the listed minor element to
    be detected at the reference ratio, so its absence there means nothing;
    that side is shaded. Optionally adds the upper-crust y:x ratio line.
    """
    major_label = mass_label(x_expr, table)
    if str(panel.get('ptl_minor') or '').strip():
        if major_label is None:
            report.stats.append('Detectability needs X as one element\'s mass, e.g. mass:Fe')
        else:
            try:
                lines = required_masses(panel, table, major_label, [np.ones(len(table), dtype=bool)])
            except ValueError as exc:
                report.stats.append(f'Detectability: {exc}')
                lines = []
            for k, (minor, per_group, how) in enumerate(lines):
                need = per_group[0]
                if need is None:
                    continue
                color = LINE_COLORS[k % len(LINE_COLORS)]
                limits = ax.get_xlim()
                ax.axvline(need, color=color, lw=1.6, ls=(0, (2, 1.5)), zorder=7)
                ax.axvspan(min(limits[0], need), need, color=color, alpha=0.07, lw=0, zorder=0.4)
                ax.set_xlim(*limits)
                t = ax.text(need, 0.98, f' {minor} detectable →\n ({how})', color=color,
                            fontsize='x-small', va='top', ha='left',
                            transform=ax.get_xaxis_transform(), zorder=8)
                t._fb_cell = True
                report.stats.append(f'{minor} is detectable at the {how} once {major_label} '
                                    f'exceeds {need:.3g} fg')
    if panel.get('crust_line'):
        y_label = mass_label(y_expr, table)
        if major_label is None or y_label is None:
            report.stats.append('The upper-crust line needs X and Y as element masses')
            return
        from results.figure_builder.core.references import crust_ratio, symbol_of
        try:
            ratio = crust_ratio(y_label, major_label, 'mass')
        except ValueError as exc:
            report.stats.append(f'Upper-crust line: {exc}')
            return
        x0, x1 = ax.get_xlim()
        xs = np.geomspace(max(x0, 1e-12), x1, 50) if ax.get_xscale() == 'log' else np.linspace(x0, x1, 50)
        y0, y1 = ax.get_ylim()
        ax.plot(xs, ratio * xs, color=ink('#111827'), lw=1.1, zorder=6)
        inside = (ratio * xs >= y0) & (ratio * xs <= y1)
        if inside.any():
            k = int(np.flatnonzero(inside)[-1])
            t = ax.annotate(f'upper crust {symbol_of(y_label)}:{symbol_of(major_label)} = {ratio:.3g}',
                            (xs[k], ratio * xs[k]), xytext=(-4, -10), textcoords='offset points',
                            ha='right', va='top', fontsize='x-small', color=ink('#111827'), zorder=8)
            t._fb_cell = True
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
