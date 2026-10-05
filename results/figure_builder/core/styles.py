"""Palettes, layout templates and one-click style presets for the Figure Builder."""

from __future__ import annotations

import copy

PALETTES: dict[str, list[str]] = {
    'IsotopeTrack': ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
                     '#06B6D4', '#F97316', '#84CC16', '#EC4899', '#6366F1'],
    'Default': ['#2a78d6', '#eb6834', '#1baf7a', '#eda100',
                '#e87ba4', '#008300', '#4a3aa7', '#e34948'],
    'Colorblind (Okabe-Ito)': ['#0072B2', '#E69F00', '#009E73', '#CC79A7',
                               '#56B4E9', '#D55E00', '#F0E442', '#000000'],
    'Tableau': ['#4E79A7', '#F28E2B', '#E15759', '#76B7B2',
                '#59A14F', '#EDC948', '#B07AA1', '#FF9DA7'],
    'Muted': ['#4878D0', '#EE854A', '#6ACC64', '#D65F5F',
              '#956CB4', '#8C613C', '#DC7EC0', '#797979'],
    'Bold': ['#1B9E77', '#D95F02', '#7570B3', '#E7298A',
             '#66A61E', '#E6AB02', '#A6761D', '#666666'],
    'Pastel': ['#8DA0CB', '#FC8D62', '#66C2A5', '#E78AC3',
               '#A6D854', '#FFD92F', '#E5C494', '#B3B3B3'],
    'Grayscale': ['#000000', '#6b6b6b', '#a8a8a8', '#d0d0d0',
                  '#3a3a3a', '#8a8a8a', '#bdbdbd', '#e2e2e2'],
}
"""Categorical palettes; colours are assigned to groups in fixed order."""

COLORMAPS = ['viridis', 'magma', 'plasma', 'inferno', 'cividis', 'turbo',
             'Blues', 'Reds', 'Greens', 'Greys', 'YlOrRd', 'coolwarm', 'RdBu', 'Spectral']

MARKERS = {
    'o': 'Circle', 's': 'Square', '^': 'Triangle up', 'v': 'Triangle down',
    'D': 'Diamond', 'P': 'Plus (filled)', 'X': 'Cross (filled)', 'h': 'Hexagon',
    '*': 'Star', '.': 'Point', '+': 'Plus', 'x': 'Cross',
}

LINE_STYLES = {'-': 'Solid', '--': 'Dashed', ':': 'Dotted', '-.': 'Dash-dot'}

LEGEND_LOCATIONS = {
    'best': 'Best inside', 'upper right': 'Upper right', 'upper left': 'Upper left',
    'lower left': 'Lower left', 'lower right': 'Lower right', 'center right': 'Center right',
    'outside right': 'Outside, right', 'below': 'Below the plot', 'above': 'Above the plot',
    'custom': 'Where I dragged it',
}

FONT_SIZES = {'xx-small': 'XX-small', 'x-small': 'X-small', 'small': 'Small',
              'medium': 'Medium', 'large': 'Large', 'x-large': 'X-large'}

TEMPLATES: dict[str, list[list[float]]] = {
    'Single': [[0.0, 0.0, 1.0, 1.0]],
    'Side by side': [[0.0, 0.0, 0.5, 1.0], [0.5, 0.0, 0.5, 1.0]],
    'Three in a row': [[0.0, 0.0, 1 / 3, 1.0], [1 / 3, 0.0, 1 / 3, 1.0], [2 / 3, 0.0, 1 / 3, 1.0]],
    'Stacked': [[0.0, 0.0, 1.0, 0.5], [0.0, 0.5, 1.0, 0.5]],
    '2 × 2': [[0.0, 0.0, 0.5, 0.5], [0.5, 0.0, 0.5, 0.5],
              [0.0, 0.5, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5]],
    '2 × 3': [[0.0, 0.0, 1 / 3, 0.5], [1 / 3, 0.0, 1 / 3, 0.5], [2 / 3, 0.0, 1 / 3, 0.5],
              [0.0, 0.5, 1 / 3, 0.5], [1 / 3, 0.5, 1 / 3, 0.5], [2 / 3, 0.5, 1 / 3, 0.5]],
    'Main + inset': [[0.0, 0.0, 1.0, 1.0], [0.55, 0.08, 0.38, 0.38]],
    'Wide + two': [[0.0, 0.0, 1.0, 0.55], [0.0, 0.55, 0.5, 0.45],
                   [0.5, 0.55, 0.5, 0.45]],
    'Big left + two right': [[0.0, 0.0, 0.62, 1.0], [0.62, 0.0, 0.38, 0.5],
                             [0.62, 0.5, 0.38, 0.5]],
    'Scatter + marginals': [[0.0, 0.25, 0.75, 0.75], [0.0, 0.0, 0.75, 0.25],
                            [0.75, 0.25, 0.25, 0.75]],
}
"""Ready-made layouts, as panel rectangles (fractions, origin top-left)."""

SIZE_PRESETS = {
    'Single column (3.5 × 3 in)': (3.5, 3.0),
    '1.5 column (5.5 × 4 in)': (5.5, 4.0),
    'Double column (7.2 × 5 in)': (7.2, 5.0),
    'Full page (7.2 × 9 in)': (7.2, 9.0),
    'Square (6 × 6 in)': (6.0, 6.0),
    'Slide 16:9 (10 × 5.6 in)': (10.0, 5.625),
    'Poster panel (12 × 9 in)': (12.0, 9.0),
}

STYLE_PRESETS: dict[str, dict] = {
    'IsotopeTrack (app style)': {
        'figure': {'font_family': 'Times New Roman', 'font_size': 12, 'axes_linewidth': 1.0,
                   'palette': 'IsotopeTrack'},
        'panel': {'frame': 'box', 'tick_dir': 'out', 'minor_ticks': True, 'grid': False,
                  'edge_color': '#1f2937', 'edge_width': 0.4, 'marker_size': 16.0,
                  'legend_frame': True, 'legend_size': 'small'},
    },
    'Publication': {
        'figure': {'font_size': 9, 'font_family': 'Arial', 'axes_linewidth': 0.8,
                   'palette': 'Default'},
        'panel': {'frame': 'open', 'tick_dir': 'out', 'minor_ticks': False, 'grid': False,
                  'marker_size': 8.0, 'line_width': 1.2, 'legend_size': 'small'},
    },
    'Presentation': {
        'figure': {'font_size': 16, 'font_family': 'Arial', 'axes_linewidth': 1.4,
                   'palette': 'Bold'},
        'panel': {'frame': 'open', 'tick_dir': 'out', 'grid': True, 'marker_size': 28.0,
                  'line_width': 2.6, 'legend_size': 'medium'},
    },
    'Boxed (classic)': {
        'figure': {'font_family': 'Times New Roman', 'axes_linewidth': 1.0},
        'panel': {'frame': 'box', 'tick_dir': 'in', 'minor_ticks': True, 'grid': False},
    },
    'Minimal': {
        'figure': {'axes_linewidth': 0.6, 'palette': 'Muted'},
        'panel': {'frame': 'open', 'tick_dir': 'out', 'minor_ticks': False, 'grid': True},
    },
    'Colorblind safe': {
        'figure': {'palette': 'Colorblind (Okabe-Ito)'},
        'panel': {},
    },
    'Grayscale print': {
        'figure': {'palette': 'Grayscale'},
        'panel': {'colormap': 'Greys'},
    },
}
"""Each preset updates figure settings and every panel at once."""


def apply_style_preset(spec: dict, name: str) -> dict:
    """Return a copy of ``spec`` with the named style preset applied."""
    preset = STYLE_PRESETS[name]
    out = copy.deepcopy(spec)
    out.setdefault('figure', {}).update(copy.deepcopy(preset['figure']))
    for panel in out.get('panels', []):
        panel.update(copy.deepcopy(preset['panel']))
    return out


def palette_colors(name: str | None) -> list[str]:
    """Colours of a named palette (the app palette when unknown)."""
    return list(PALETTES.get(name or 'IsotopeTrack', PALETTES['IsotopeTrack']))


SERIF_FAMILIES = {'Times New Roman', 'Times', 'Georgia', 'Palatino', 'Garamond', 'Book Antiqua',
                  'Liberation Serif', 'DejaVu Serif', 'Nimbus Roman', 'STIXGeneral', 'Cambria'}


def font_stack(family: str | None) -> tuple[list[str], str]:
    """Font fallback list and matching mathtext set for a chosen family.

    Isotope labels use mathtext superscripts, so serif figures use the STIX
    (Times-like) math font and sans-serif figures the DejaVu Sans one.
    """
    family = family or 'Times New Roman'
    if family in SERIF_FAMILIES or 'serif' in family.lower() and 'sans' not in family.lower():
        stack = [family, 'Times New Roman', 'Times', 'Liberation Serif', 'Nimbus Roman',
                 'STIXGeneral', 'DejaVu Serif']
        math = 'stix'
    else:
        stack = [family, 'Arial', 'Helvetica', 'Liberation Sans', 'DejaVu Sans']
        math = 'dejavusans'
    available = installed_fonts()
    kept = [f for f in dict.fromkeys(stack) if f in available]
    return (kept or ['DejaVu Sans']), math


_INSTALLED: set | None = None


def installed_fonts() -> set:
    """Font family names matplotlib can use on this computer (cached)."""
    global _INSTALLED
    if _INSTALLED is None:
        try:
            from matplotlib import font_manager
            _INSTALLED = {f.name for f in font_manager.fontManager.ttflist}
        except Exception:
            _INSTALLED = {'DejaVu Sans', 'DejaVu Serif'}
    return _INSTALLED
