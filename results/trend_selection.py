"""Trend lines fitted to points the user draws around.

Automatic trend lines decide for themselves which particles belong together.
Sometimes the user knows better: one cloud is the TiO₂ particles, another the
steel. Here the user draws a free-hand loop around a cloud on the plot, and a
straight line is fitted to the points inside it only. Each loop is kept with
the plot's settings, so it is redrawn, and refitted on the current data,
every time the plot is drawn, until it is removed.

A loop is stored in the plot's own coordinates, as drawn (log10 values on a
log axis), together with what the axes showed when it was drawn. It is only
used while the axes show the same quantities in the same way, because the
same loop over different axes would enclose unrelated points.
"""

from __future__ import annotations

import numpy as np

SELECTION_COLORS = ['#DB2777', '#7C3AED', '#0891B2', '#CA8A04', '#16A34A', '#DC2626']
"""Colours of user-selected trend lines, in the order they are drawn."""

MIN_SELECTED = 3
"""Fewest points a loop must hold before a line is fitted."""


def axes_signature(cfg: dict) -> dict:
    """What the axes show, so a loop is only reused on the same axes.

    Args:
        cfg: Correlation plot settings.

    Returns:
        The plotted quantities, their log scaling and the data type.
    """
    if cfg.get('mode', 'Simple Element Correlation') == 'Simple Element Correlation':
        x, y = cfg.get('x_element', ''), cfg.get('y_element', '')
    else:
        x, y = cfg.get('x_equation', '').strip(), cfg.get('y_equation', '').strip()
    return {
        'x': str(x), 'y': str(y),
        'log_x': bool(cfg.get('log_x', False)), 'log_y': bool(cfg.get('log_y', False)),
        'data': str(cfg.get('data_type_display', '')),
    }


def inside(polygon, x, y) -> np.ndarray:
    """Which points fall inside a drawn loop.

    Args:
        polygon: ``[[x, y], ...]`` vertices in plot coordinates.
        x: Point x values in the same coordinates.
        y: Point y values in the same coordinates.

    Returns:
        A boolean mask, all ``False`` for a loop of fewer than three vertices.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(polygon) < 3 or x.size == 0:
        return np.zeros(x.size, dtype=bool)
    from matplotlib.path import Path
    return Path(np.asarray(polygon, dtype=float)).contains_points(np.column_stack([x, y]))


def new_selection(polygon, plot_key: str, cfg: dict) -> dict:
    """A loop ready to store in the plot settings.

    Args:
        polygon: ``[[x, y], ...]`` vertices as drawn.
        plot_key: Which panel it was drawn on: the sample name in per-sample
            layouts, ``""`` for a single shared panel.
        cfg: The plot settings, used for the axes signature and the colour.
    """
    used = len(cfg.get('trend_selections') or [])
    return {
        'polygon': [[float(a), float(b)] for a, b in polygon],
        'plot': plot_key or '',
        'axes': axes_signature(cfg),
        'color': SELECTION_COLORS[used % len(SELECTION_COLORS)],
    }


def active_selections(cfg: dict, plot_key: str | None = None) -> list[tuple[int, dict]]:
    """Stored loops that apply to the current axes, with their position in the list.

    Args:
        cfg: Correlation plot settings.
        plot_key: Only loops drawn on this panel; every panel when ``None``.
    """
    sig = axes_signature(cfg)
    out = []
    for i, sel in enumerate(cfg.get('trend_selections') or []):
        if sel.get('axes') != sig:
            continue
        if plot_key is not None and (sel.get('plot') or '') != (plot_key or ''):
            continue
        out.append((i, sel))
    return out


def fit_selection(sel: dict, x, y):
    """Fit one straight line to the points inside a loop.

    Returns:
        ``(mask, line)``, where *line* is a
        :class:`results.multi_trend.TrendLine`, or ``(mask, None)`` when the
        loop holds fewer than :data:`MIN_SELECTED` points or they do not
        spread along x.
    """
    mask = inside(sel.get('polygon') or [], x, y)
    if int(mask.sum()) < MIN_SELECTED:
        return mask, None
    xs = np.asarray(x, dtype=float)[mask]
    ys = np.asarray(y, dtype=float)[mask]
    if np.ptp(xs) <= 0:
        return mask, None
    return mask, _single_line(xs, ys)


def _single_line(x, y):
    """Least-squares line through a handful of points, as a TrendLine."""
    from results.multi_trend import TrendLine
    slope, icpt = np.polyfit(x, y, 1)
    res = y - (slope * x + icpt)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float((res ** 2).sum()) / ss_tot if ss_tot > 0 else float('nan')
    r = float(np.corrcoef(x, y)[0, 1]) if np.ptp(y) > 0 else float('nan')
    return TrendLine(slope=float(slope), intercept=float(icpt), sigma=float(res.std()),
                     n=int(x.size), share=1.0, r2=r2, r=r)


def legend_text(number: int, line, log_x: bool, log_y: bool, series: str | None = None) -> str:
    """Legend entry for a selected-point line: r, the ratio or slope, and n.

    On log–log axes a slope near one is a fixed ratio and is given as such;
    otherwise the slope is given.
    """
    if log_x and log_y and abs(line.slope - 1) <= 0.1:
        shape = f", ratio {10 ** line.intercept:.3g}"
    else:
        shape = f", slope {line.slope:.3g}"
    prefix = f"{series}, " if series else ""
    return f"{prefix}selection {number}: r = {line.r:.3f}{shape} (n = {line.n:,})"
