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
               'lollipop', 'timeline', 'pca'}
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
    has_cbar = kind in ('density', 'hexbin') or (kind in ('scatter', 'ternary')
                                                  and bool((panel.get('color_by') or '').strip()))
    x, y, w, h = rect
    if kind == 'pie':
        ml, mr, mb, mt = 0.15, 0.15, 0.6, 0.35 if has_title else 0.15
    elif kind == 'treemap':
        ml, mr, mb, mt = 0.1, 0.1, 0.55 if panel.get('legend') else 0.1, 0.35 if has_title else 0.1
    elif kind == 'text':
        ml, mr, mb, mt = 0.15, 0.15, 0.15, 0.35 if has_title else 0.15
    elif kind == 'ternary':
        ml, mr, mb, mt = 0.8, 0.8 + (0.7 if has_cbar else 0.0), 0.75, 0.8 if has_title else 0.55
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
                if panel.get('facet', 'none') == 'groups' and panel.get('kind') not in NO_FACET:
                    _render_facets(fig, index, panel, spec, table, report, style, fw, fh, bg, Rectangle)
                else:
                    _render_panel(fig, index, panel, spec, table, report, style, fw, fh, bg, Rectangle)
    finally:
        font_log.setLevel(previous)
    return report


NO_FACET = {'text', 'code', 'pairs'}
"""Panel kinds that cannot be split into one small plot per group."""

SHARED_LIMIT_KINDS = {'scatter', 'line', 'density', 'hexbin', 'contour', 'histogram', 'box', 'violin',
                      'strip', 'bar', 'ridgeline', 'ecdf', 'lollipop', 'timeline', 'combinations', 'pca'}
"""Kinds whose small multiples can share their axis ranges."""


def facet_rects(rect, n, cols=0, fw=8.0, fh=6.0):
    """Split a panel rectangle into ``n`` cells (figure fractions, top-left origin)."""
    import math
    x, y, w, h = rect
    if cols <= 0:
        aspect = (w * fw) / max(h * fh, 1e-9)
        cols = max(1, min(n, round(math.sqrt(n * aspect))))
    cols = max(1, min(n, int(cols)))
    rows = math.ceil(n / cols)
    cw, ch = w / cols, h / rows
    return [[x + (k % cols) * cw, y + (k // cols) * ch, cw, ch] for k in range(n)]


def _render_facets(fig, index, panel, spec, table, report, style, fw, fh, bg, Rectangle):
    """Draw one small copy of a panel per group (the nodes' "individual subplots").

    Each copy shows a single group with the panel's settings, titled with the
    group name. The copies are recorded under the panel's own id so clicks,
    errors and counts still belong to the panel the user drew.
    """
    import copy as _copy
    pid = panel['id']
    ptable = table.view(panel.get('data_type'))
    try:
        groups = resolve_groups(panel, ptable) if len(table) else []
    except Exception as exc:
        report.errors[pid] = str(exc)
        groups = []
    if len(groups) < 2:
        _render_panel(fig, index, panel, spec, table, report, style, fw, fh, bg, Rectangle)
        return
    rect = panel.get('rect') or [0, 0, 1, 1]
    if index:
        fig.add_artist(Rectangle((rect[0], 1 - rect[1] - rect[3]), rect[2], rect[3],
                                 transform=fig.transFigure, zorder=index + 0.5,
                                 facecolor=bg, edgecolor='none'))
    cells = facet_rects(rect, len(groups), int(panel.get('facet_cols') or 0), fw, fh)
    all_keys = [g.key for g in groups]
    subs = []
    for k, (g, cell) in enumerate(zip(groups, cells)):
        sub = _copy.deepcopy(panel)
        sub['id'] = f'{pid}#{k}'
        sub['rect'] = cell
        sub['facet'] = 'none'
        sub['hidden_groups'] = list(panel.get('hidden_groups') or []) + [x for x in all_keys if x != g.key]
        sub['group_colors'] = dict(panel.get('group_colors') or {}, **{g.key: g.color})
        sub['title'] = f"{panel['title']} — {g.label}" if panel.get('title') else g.label
        sub['_palette'] = panel.get('_palette')
        _render_panel(fig, index, sub, spec, table, report, style, fw, fh, bg, Rectangle,
                      letter=False, background=False)
        subs.append(sub['id'])
    hds = [report.artists.pop(sid, {}) for sid in subs]
    errored = {sid for sid in subs if sid in report.errors}
    errors = [report.errors.pop(sid) for sid in subs if sid in report.errors]
    counts = [report.counts.pop(sid, 0) for sid in subs]
    boxes = [report.axes.pop(sid) for sid in subs if sid in report.axes]
    axes = [hd['ax'] for hd in hds if hd.get('ax') is not None]
    if panel.get('facet_share', True) and panel.get('kind') in SHARED_LIMIT_KINDS and len(axes) > 1:
        _share_limits([hd for hd, sid in zip(hds, subs) if sid not in errored and hd.get('ax')], panel)
    merged = dict(hds[0]) if hds else {}
    extra = []
    for hd in hds[1:]:
        if hd.get('ax') is not None:
            extra.append(hd['ax'])
        extra.extend(hd.get('extra_axes') or [])
    merged['extra_axes'] = list(merged.get('extra_axes') or []) + extra
    merged['facets'] = hds
    report.artists[pid] = merged
    report.counts[pid] = int(sum(counts))
    if errors and len(errors) == len(subs):
        report.errors[pid] = errors[0]
    if boxes:
        left = min(b[0] for b in boxes)
        bottom = min(b[1] for b in boxes)
        right = max(b[0] + b[2] for b in boxes)
        top = max(b[1] + b[3] for b in boxes)
        report.axes[pid] = [left, bottom, right - left, top - bottom]
    _panel_letter(fig, index, panel, spec, fw, fh)


def _category_axes(panel) -> tuple[bool, bool]:
    """Which of X and Y list categories (groups or items) rather than numbers."""
    kind = panel.get('kind')
    flat = bool(panel.get('horizontal'))
    if kind in ('box', 'violin', 'strip'):
        return True, False
    if kind in ('bar', 'combinations'):
        return (not flat), flat
    if kind == 'lollipop':
        vertical = bool(panel.get('lolli_vertical'))
        return vertical, not vertical
    if kind == 'ridgeline':
        return False, True
    return False, False


def _share_limits(hds, panel):
    """Give small multiples the same numeric X and Y ranges (category axes keep their own)."""
    cat_x, cat_y = _category_axes(panel)
    try:
        for is_cat, get, put, inv in ((cat_x, 'get_xlim', 'set_xlim', 'xaxis_inverted'),
                                      (cat_y, 'get_ylim', 'set_ylim', 'yaxis_inverted')):
            if is_cat:
                continue
            lims = [getattr(hd['ax'], get)() for hd in hds]
            lo = min(min(lim) for lim in lims)
            hi = max(max(lim) for lim in lims)
            for hd in hds:
                inverted = getattr(hd['ax'], inv)()
                getattr(hd['ax'], put)((hi, lo) if inverted else (lo, hi))
    except Exception:
        pass


def _panel_letter(fig, index, panel, spec, fw, fh):
    """The bold panel letter in the top-left corner of the panel's rectangle."""
    figcfg = spec['figure']
    if not (figcfg.get('panel_letters') and len(spec['panels']) > 1) or panel.get('caption'):
        return
    rect = panel.get('rect') or [0, 0, 1, 1]
    size = float(figcfg.get('letter_size') or 0) or float(figcfg.get('font_size') or 11) + 3
    letter = fig.text(rect[0] + 0.06 / fw, 1 - rect[1] - 0.06 / fh,
                      panel_letter(index, figcfg.get('letter_style', 'a')),
                      ha='left', va='top', fontweight='bold', fontsize=size, zorder=100)
    letter._fb_element = (panel['id'], 'letters')
    textstyle.apply(letter, textstyle.resolve(figcfg, None, 'letters'))


def _render_panel(fig, index, panel, spec, table, report, style, fw, fh, bg, Rectangle,
                  letter=True, background=True):
    """Draw one panel, catching its errors so the rest of the figure survives."""
    figcfg = spec['figure']
    kind = panel.get('kind', 'scatter')
    rect = panel.get('rect') or [0, 0, 1, 1]
    if index and background:
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
    if letter:
        _panel_letter(fig, index, panel, spec, fw, fh)
