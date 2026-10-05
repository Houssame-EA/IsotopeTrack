"""Figure Builder rendering engine.

:func:`render` draws a spec (see :mod:`results.figure_builder.core.spec`)
onto a :class:`matplotlib.figure.Figure` and returns a
:class:`~results.figure_builder.core.common.RenderReport` with statistics,
per-panel errors and the artists drawn, so a broken expression in one panel
never blanks the rest of the figure and the window can map clicks back to
panels and labels.

The module has no Qt dependency and is fully testable headless.
"""

from __future__ import annotations

import logging

from results.figure_builder.charts import DRAWERS
from results.figure_builder.core.common import (
    CBAR_LOCATIONS, Group, RenderReport, annotate, candidate_groups, draw_shapes, fit_decorations,
    fit_outside_legend, merge_legend, place_colorbar, resolve_groups)

SHAPE_KINDS = {'scatter', 'line', 'density', 'hexbin', 'contour', 'histogram', 'box', 'violin',
               'strip', 'bar', 'combinations', 'composition', 'ridgeline', 'code', 'ecdf',
               'lollipop', 'timeline'}
"""Panel kinds that can carry grey areas and reference lines."""
from results.figure_builder.core.expressions import ExpressionError, ParticleTable
from results.figure_builder.core.spec import (
    CODE_EXAMPLE, FIGURE_DEFAULTS, GROUP_MODES, OTHER_COLOR, PALETTE, PANEL_DEFAULTS,
    PANEL_KINDS, apply_template, default_spec, make_panel, new_panel_id, normalise_spec,
    panel_letter, strip_spec)
from results.figure_builder.core.stats import (
    CORRECTIONS, PAIRWISE_TESTS, STAT_TESTS, correct, p_text, run_tests)
from results.figure_builder.core.styles import (
    PALETTES, STYLE_PRESETS, TEMPLATES, apply_style_preset, font_stack, palette_colors)
from results.figure_builder.core import textstyle

__all__ = [
    'CBAR_LOCATIONS', 'CODE_EXAMPLE', 'CORRECTIONS', 'DRAWERS', 'FIGURE_DEFAULTS', 'GROUP_MODES', 'Group',
    'OTHER_COLOR', 'PAIRWISE_TESTS', 'PALETTE', 'PALETTES', 'PANEL_DEFAULTS', 'PANEL_KINDS',
    'RenderReport', 'STAT_TESTS', 'STYLE_PRESETS', 'TEMPLATES', 'apply_style_preset',
    'apply_template', 'candidate_groups', 'correct', 'default_spec', 'make_panel',
    'new_panel_id', 'normalise_spec', 'p_text', 'panel_letter', 'render', 'resolve_groups',
    'run_tests', 'strip_spec',
]


def _inner_rect(rect, fig_w, fig_h, panel):
    """Inset a drawn panel rectangle to leave room for ticks, labels and legends.

    Returns matplotlib ``[left, bottom, width, height]`` in figure fractions.
    """
    kind = panel.get('kind', 'scatter')
    has_title = bool(panel.get('title'))
    has_y2 = kind == 'scatter' and bool((panel.get('y2') or '').strip())
    has_cbar = kind in ('density', 'hexbin') or (kind == 'scatter' and bool((panel.get('color_by') or '').strip()))
    x, y, w, h = rect
    if kind == 'pie':
        ml, mr, mb, mt = 0.15, 0.15, 0.6, 0.35 if has_title else 0.15
    elif kind == 'treemap':
        ml, mr, mb, mt = 0.1, 0.1, 0.55 if panel.get('legend') else 0.1, 0.35 if has_title else 0.1
    elif kind == 'text':
        ml, mr, mb, mt = 0.15, 0.15, 0.15, 0.35 if has_title else 0.15
    elif kind == 'ternary':
        ml, mr, mb, mt = 0.8, 0.8, 0.75, 0.8 if has_title else 0.55
    elif kind == 'radar':
        ml, mr, mb, mt = 0.6, 0.6, 0.45, 0.75 if has_title else 0.5
    else:
        ml, mb = 0.75, 0.62
        mr = 0.75 if has_y2 else 0.2
        cbar_loc = panel.get('cbar_loc') or 'right'
        mt = 0.4 if has_title else 0.18
        if has_cbar:
            if cbar_loc == 'right':
                mr += 0.7
            elif cbar_loc == 'left':
                ml += 0.7
            elif cbar_loc == 'top':
                mt += 0.55
            elif cbar_loc == 'bottom':
                mb += 0.55
        if float(panel.get('xtick_rotation') or 0):
            mb += 0.35
        if kind in ('box', 'violin') and panel.get('show_n', True):
            mb += 0.15
        if kind in ('bar', 'composition') and panel.get('horizontal'):
            ml += 0.5
        if kind == 'combinations':
            if panel.get('horizontal'):
                ml += 0.9
            else:
                mb += 0.6
        if kind in ('corr_matrix', 'cooccurrence', 'heatmap'):
            ml += 0.35
            mb += 0.35
            mr += 0.75
        if kind == 'composition':
            mb += 0.15
        if kind == 'lollipop' and not panel.get('lolli_vertical'):
            ml += 0.3
        if kind == 'pairs':
            ml += 0.25
            mb += 0.1
    if panel.get('legend', True) and kind not in ('text', 'code'):
        loc = panel.get('legend_loc')
        if loc == 'outside right':
            mr += 1.5
        elif loc == 'below' and kind not in ('pie', 'treemap'):
            mb += 0.55
        elif loc == 'above':
            mt += 0.45
    left = x + ml / fig_w
    right = x + w - mr / fig_w
    bottom = 1 - (y + h) + mb / fig_h
    top = 1 - y - mt / fig_h
    if right - left < 0.02:
        mid = x + w / 2
        left, right = mid - 0.01, mid + 0.01
    if top - bottom < 0.02:
        mid = 1 - y - h / 2
        bottom, top = mid - 0.01, mid + 0.01
    return [left, bottom, right - left, top - bottom]


def ensure_ternary_projection():
    """Register the mpltern projection if the package is available."""
    try:
        import importlib
        importlib.import_module('mpltern')
        return True
    except Exception:
        return False


def render(fig, spec: dict, table: ParticleTable) -> RenderReport:
    """Draw ``spec`` onto ``fig`` (which is cleared first).

    Args:
        fig: A :class:`matplotlib.figure.Figure`.
        spec: Figure Builder spec (normalised internally, never modified).
        table: Particle columns from the upstream stream; the spec's
            variables are installed on it.

    Returns:
        RenderReport: statistics lines, per-panel errors and counts.
    """
    import matplotlib
    from matplotlib.patches import Rectangle
    spec = normalise_spec(spec)
    figcfg = spec['figure']
    report = RenderReport()
    report.variable_errors = table.set_variables(spec.get('variables'))
    fig.clear()
    fw, fh = float(figcfg['width']), float(figcfg['height'])
    fig.set_size_inches(fw, fh, forward=False)
    bg = figcfg.get('background') or '#ffffff'
    fig.set_facecolor(bg)
    style = figcfg.get('label_style', 'isotope')
    pal = palette_colors(figcfg.get('palette'))
    ensure_ternary_projection()
    fs = float(figcfg.get('font_size') or 12)
    fonts, math_set = font_stack(figcfg.get('font_family'))
    lw = float(figcfg.get('axes_linewidth') or 0.8)
    rc = {
        'font.family': fonts,
        'mathtext.fontset': math_set,
        'font.size': fs,
        'axes.titlesize': float(figcfg.get('title_size') or fs * 1.05),
        'axes.labelsize': float(figcfg.get('label_size') or fs),
        'xtick.labelsize': float(figcfg.get('tick_size') or fs * 0.9),
        'ytick.labelsize': float(figcfg.get('tick_size') or fs * 0.9),
        'mathtext.default': 'regular',
        'axes.titleweight': 'bold',
        'axes.linewidth': lw,
        'xtick.major.width': lw,
        'ytick.major.width': lw,
        'xtick.minor.width': lw * 0.7,
        'ytick.minor.width': lw * 0.7,
        'legend.frameon': False,
        'xtick.major.size': 4.5,
        'ytick.major.size': 4.5,
        'xtick.minor.size': 2.5,
        'ytick.minor.size': 2.5,
        'xtick.major.pad': 4,
        'ytick.major.pad': 4,
        'axes.labelpad': 6,
        'axes.titlepad': 8,
        'savefig.facecolor': bg,
        'lines.solid_capstyle': 'round',
    }
    ink = figcfg.get('ink') or ''
    if ink:
        rc.update({'text.color': ink, 'axes.labelcolor': ink, 'xtick.color': ink, 'ytick.color': ink,
                   'axes.edgecolor': ink, 'axes.titlecolor': ink, 'legend.labelcolor': ink})
    if figcfg.get('sketchy'):
        rc['path.sketch'] = (1.1, 90.0, 2.0)
    font_log = logging.getLogger('matplotlib.font_manager')
    previous = font_log.level
    font_log.setLevel(logging.ERROR)
    try:
        with matplotlib.rc_context(rc):
            if figcfg.get('title'):
                sup = fig.suptitle(figcfg['title'], fontweight='bold')
                sup._fb_element = ('', 'figure_title')
                textstyle.apply(sup, textstyle.resolve(figcfg, None, 'figure_title'))
            for index, panel in enumerate(spec['panels']):
                panel['_palette'] = pal
                _render_panel(fig, index, panel, spec, table, report, style, fw, fh, bg, Rectangle)
    finally:
        font_log.setLevel(previous)
    return report


def _render_panel(fig, index, panel, spec, table, report, style, fw, fh, bg, Rectangle):
    """Draw one panel, catching its errors so the rest of the figure survives."""
    figcfg = spec['figure']
    kind = panel.get('kind', 'scatter')
    rect = panel.get('rect') or [0, 0, 1, 1]
    if index:
        fig.add_artist(Rectangle((rect[0], 1 - rect[1] - rect[3]), rect[2], rect[3],
                                 transform=fig.transFigure, zorder=index + 0.5,
                                 facecolor=bg, edgecolor='none'))
    inner = _inner_rect(rect, fw, fh, panel)
    report.axes[panel['id']] = inner
    ax = fig.add_axes(inner, projection={'ternary': 'ternary', 'radar': 'polar'}.get(kind))
    ax.set_zorder(index + 1)
    ax.set_facecolor(panel.get('panel_bg') or '#ffffff')
    report.artists[panel['id']] = {'ax': ax}
    ptable = table.view(panel.get('data_type'))
    try:
        if len(table) == 0 and kind not in ('text', 'code'):
            raise ExpressionError('No particles: connect a sample or filter node')
        DRAWERS.get(kind, DRAWERS['scatter'])(fig, ax, panel, ptable, report, style)
        if kind in SHAPE_KINDS:
            merge_legend(ax, panel, draw_shapes(ax, panel))
        annotate(ax, panel)
        textstyle.apply_panel(report.artists[panel['id']], panel, figcfg)
        hd = report.artists[panel['id']]
        if hd.get('cbar') is not None:
            place_colorbar(fig, panel, hd)
        fit_outside_legend(fig, ax, rect)
        if kind not in ('text', 'code'):
            fit_decorations(fig, hd, rect)
            if hd.get('cbar') is not None:
                place_colorbar(fig, panel, hd)
                fit_decorations(fig, hd, rect)
                place_colorbar(fig, panel, hd)
    except Exception as exc:
        report.errors[panel['id']] = str(exc)
        ax.cla()
        ax.axis('off')
        ax.text(0.5, 0.5, f'⚠ {exc}', transform=ax.transAxes, ha='center',
                va='center', color='#b42318', wrap=True, fontsize='small')
    if figcfg.get('panel_letters') and len(spec['panels']) > 1:
        size = float(figcfg.get('letter_size') or 0) or float(figcfg.get('font_size') or 11) + 3
        letter = fig.text(rect[0] + 0.06 / fw, 1 - rect[1] - 0.06 / fh,
                          panel_letter(index, figcfg.get('letter_style', 'a')),
                          ha='left', va='top', fontweight='bold', fontsize=size, zorder=100)
        letter._fb_element = (panel['id'], 'letters')
        textstyle.apply(letter, textstyle.resolve(figcfg, None, 'letters'))
