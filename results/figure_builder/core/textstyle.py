"""Bold, italic, size, colour and font for every piece of text in a figure.

Styles are stored as ``{element: {'size': float, 'bold': bool, 'italic': bool,
'color': str, 'family': str}}`` at two levels: ``figure['text_styles']``
applies to every panel, ``panel['text_styles']`` overrides it for one panel.
Missing keys (or a size of 0, an empty colour or family) mean "inherit".
"""

from __future__ import annotations

PANEL_ELEMENTS = {
    'title': 'Panel title',
    'x_label': 'X axis label',
    'y_label': 'Y axis label',
    'y2_label': 'Right axis label',
    'corner_labels': 'Ternary corner labels',
    'ticks': 'Tick labels',
    'legend': 'Legend',
    'cbar_label': 'Colour bar label',
    'cells': 'Values inside cells and bars',
}
"""Text elements every panel can style, with display names."""

FIGURE_ELEMENTS = {
    'figure_title': 'Figure title',
    'letters': 'Panel letters',
}
"""Text elements that only exist once per figure."""

ALL_ELEMENTS = {**PANEL_ELEMENTS, **FIGURE_ELEMENTS}

KIND_ELEMENTS = {
    'scatter': ['title', 'x_label', 'y_label', 'y2_label', 'ticks', 'legend', 'cbar_label'],
    'line': ['title', 'x_label', 'y_label', 'ticks', 'legend'],
    'histogram': ['title', 'x_label', 'y_label', 'ticks', 'legend'],
    'box': ['title', 'x_label', 'y_label', 'ticks'],
    'violin': ['title', 'x_label', 'y_label', 'ticks'],
    'bar': ['title', 'x_label', 'y_label', 'ticks', 'legend'],
    'pie': ['title', 'legend', 'cells'],
    'density': ['title', 'x_label', 'y_label', 'ticks', 'cbar_label'],
    'ternary': ['title', 'corner_labels', 'ticks', 'legend'],
    'corr_matrix': ['title', 'ticks', 'cbar_label', 'cells'],
    'heatmap': ['title', 'x_label', 'y_label', 'ticks', 'cbar_label', 'cells'],
    'cooccurrence': ['title', 'ticks', 'cbar_label', 'cells'],
    'combinations': ['title', 'x_label', 'y_label', 'ticks', 'legend', 'cells'],
    'composition': ['title', 'x_label', 'y_label', 'ticks', 'legend', 'cells'],
    'pairs': ['title', 'x_label', 'y_label', 'ticks', 'legend'],
    'strip': ['title', 'x_label', 'y_label', 'ticks', 'cells'],
    'ridgeline': ['title', 'x_label', 'ticks', 'cells'],
    'hexbin': ['title', 'x_label', 'y_label', 'ticks', 'cbar_label'],
    'contour': ['title', 'x_label', 'y_label', 'ticks', 'legend'],
    'radar': ['title', 'ticks', 'legend'],
    'parallel': ['title', 'y_label', 'ticks', 'legend'],
    'ecdf': ['title', 'x_label', 'y_label', 'ticks', 'legend'],
    'lollipop': ['title', 'x_label', 'y_label', 'ticks', 'legend', 'cells'],
    'treemap': ['title', 'legend', 'cells'],
    'timeline': ['title', 'x_label', 'y_label', 'ticks', 'legend'],
    'text': ['title'],
    'code': ['title', 'x_label', 'y_label', 'ticks', 'legend'],
}
"""Which text elements make sense for each chart type."""


def resolve(figcfg: dict, panel: dict | None, element: str) -> dict:
    """Merged style of ``element`` (figure level, then panel level)."""
    out: dict = {}
    for source in ((figcfg or {}).get('text_styles') or {}, ((panel or {}).get('text_styles') or {})):
        st = source.get(element) or {}
        for key, value in st.items():
            if key == 'size' and not value:
                continue
            if key in ('color', 'family') and not value:
                continue
            if value is None:
                continue
            out[key] = value
    return out


def apply(text, style: dict):
    """Apply a resolved style to one matplotlib Text (no-op for None)."""
    if text is None or not style:
        return
    if style.get('size'):
        text.set_fontsize(float(style['size']))
    if 'bold' in style:
        text.set_fontweight('bold' if style['bold'] else 'normal')
    if 'italic' in style:
        text.set_fontstyle('italic' if style['italic'] else 'normal')
    if style.get('color'):
        text.set_color(style['color'])
    if style.get('family'):
        text.set_fontfamily(style['family'])


def apply_ticks(axis, style: dict):
    """Style every tick label of a matplotlib axis, including future ticks."""
    if axis is None or not style:
        return
    kw = {}
    if style.get('size'):
        kw['labelsize'] = float(style['size'])
    if style.get('color'):
        kw['labelcolor'] = style['color']
    if kw:
        axis.set_tick_params(which='both', **kw)
    ticks = list(axis.get_major_ticks()) + list(axis.get_minor_ticks())
    for tick in ticks:
        for lab in (tick.label1, tick.label2):
            if 'bold' in style:
                lab.set_fontweight('bold' if style['bold'] else 'normal')
            if 'italic' in style:
                lab.set_fontstyle('italic' if style['italic'] else 'normal')
            if style.get('family'):
                lab.set_fontfamily(style['family'])


def _axes_list(handles: dict):
    axes = [handles.get('ax')] + list(handles.get('extra_axes') or [])
    return [a for a in axes if a is not None]


def apply_panel(handles: dict, panel: dict, figcfg: dict):
    """Apply every text style of one panel to the artists it drew.

    Args:
        handles: ``{'ax', 'ax2', 'cbar', 'extra_axes'}`` recorded while drawing.
        panel: The panel dict.
        figcfg: The figure settings.
    """
    ax = handles.get('ax')
    if ax is None:
        return

    def st(element):
        return resolve(figcfg, panel, element)

    apply(ax.title, st('title'))
    for a in _axes_list(handles):
        if getattr(a, 'name', '') == 'ternary':
            corner = st('corner_labels')
            for axis_name in ('taxis', 'laxis', 'raxis'):
                axis = getattr(a, axis_name, None)
                if axis is not None:
                    apply(axis.label, corner)
                    apply_ticks(axis, st('ticks'))
            continue
        apply(a.xaxis.label, st('x_label'))
        apply(a.yaxis.label, st('y_label'))
        apply_ticks(a.xaxis, st('ticks'))
        apply_ticks(a.yaxis, st('ticks'))
        cells = st('cells')
        if cells:
            for t in a.texts:
                if getattr(t, '_fb_cell', False):
                    apply(t, cells)
    ax2 = handles.get('ax2')
    if ax2 is not None:
        apply(ax2.yaxis.label, st('y2_label'))
        apply_ticks(ax2.yaxis, st('ticks'))
    cbar = handles.get('cbar')
    if cbar is not None:
        apply(cbar.ax.yaxis.label, st('cbar_label'))
        apply(cbar.ax.xaxis.label, st('cbar_label'))
        apply_ticks(cbar.ax.yaxis, st('ticks'))
    leg_style = st('legend')
    if leg_style:
        for a in [ax] + list(handles.get('extra_axes') or []):
            leg = a.get_legend()
            if leg is None:
                continue
            for t in leg.get_texts():
                apply(t, leg_style)
            apply(leg.get_title(), leg_style)
