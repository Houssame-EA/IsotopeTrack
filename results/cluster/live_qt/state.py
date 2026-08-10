"""Palette, marker geometry, element labels and the live view's state model.

Holds everything the drawing code needs that is not itself a widget: the
cluster palette and per-cluster overrides, the ten marker shapes, the overlay
colour ramp, the element-label parser, and :class:`LiveState`, which carries
the dataset, the clustering result and every display preference.

:class:`LiveState` is an object rather than module globals so the view can be
opened twice — two dialogs on two datasets — without the instances trampling
one another.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

from PySide6.QtGui import QPainterPath

PALETTE = ['#2563EB', '#DC2626', '#16A34A', '#D97706', '#7C3AED', '#0891B2',
           '#DB2777', '#65A30D', '#EA580C', '#4F46E5', '#0D9488', '#C026D3']

ELEMENT_PALETTE = [
    '#2563EB', '#DC2626', '#16A34A', '#D97706', '#7C3AED',
    '#0891B2', '#DB2777', '#65A30D', '#EA580C', '#4F46E5',
    '#0D9488', '#C026D3', '#CA8A04', '#E11D48', '#2DD4BF',
    '#6366F1', '#F59E0B', '#10B981', '#EF4444', '#8B5CF6',
    '#0EA5E9', '#A855F7', '#F97316', '#84CC16', '#06B6D4']

VIRIDIS_FALLBACK = ['#440154', '#482878', '#3E4989', '#31688E', '#26828E',
                    '#1F9E89', '#35B779', '#6DCD59', '#B4DE2C', '#FDE725']

PICKER_EXTRA = ['#111827', '#475569', '#94A3B8', '#E11D48', '#F59E0B',
                '#FACC15', '#84CC16', '#10B981', '#06B6D4', '#3B82F6',
                '#8B5CF6', '#EC4899']

DIM_ALPHA = 0.13
FOCUS_MAX_ZOOM = 9
TWEEN_MS = 420
ROT_SENSITIVITY = 0.01
ROT_EL_LIMIT = 1.45


class Theme(dict):
    """The palette the view draws with.

    A dict so a whole ``_theme_vars()`` payload can be applied at once, with
    attribute access for the handful of keys the drawing code reads constantly.
    """

    _DEFAULTS = {
        'noise': '#888', 'text': '#d4d4d4', 'bg': '#1e1e1e',
        'accent': '#007acc', 'bg2': '#252526', 'panel': '#252526',
        'chip': '#2d2d30', 'stroke': '#3e3e42', 'stroke2': '#54545a',
        'muted': '#9d9d9d', 'muted2': '#9d9d9d', 'accent2': '#1177bb',
        'good': '#16a34a', 'warn': '#d97706', 'bad': '#dc2626',
        'dark': True,
    }

    def __init__(self):
        """Start from the dark defaults, before the app palette is applied."""
        super().__init__(self._DEFAULTS)
        self.noise_locked = False

    def __getattr__(self, name):
        """Expose dictionary keys as attributes.

        Args:
            name (str): A palette key such as ``'bg'`` or ``'text'``.

        Returns:
            The colour string.

        Raises:
            AttributeError: When the key is not part of the palette.
        """
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def apply(self, v):
        """Merge a theme payload from the application palette.

        ``noise`` is only taken from the theme until the backend sends an
        explicit noise colour, after which the dataset's choice wins.

        Args:
            v (dict | None): Colour keys to merge.
        """
        if not v:
            return
        self.update({k: val for k, val in v.items() if val})
        if not self.noise_locked:
            self['noise'] = v.get('muted2') or v.get('muted') or '#888'
        self['text'] = v.get('text') or '#d4d4d4'
        self['bg'] = v.get('bg') or '#1e1e1e'
        self['accent'] = v.get('accent') or '#007acc'


THEME = Theme()


_HEX_RE = re.compile(r'^#?([0-9a-f]{6})$', re.I)


def hex_to_rgb(h):
    """Parse ``'#RRGGBB'`` into an ``[r, g, b]`` triple.

    Args:
        h (str): Hex colour, with or without the leading ``#``.

    Returns:
        list[int] | None: The channel values, or None when unparseable.
    """
    m = _HEX_RE.match(str(h or '').strip())
    if not m:
        return None
    v = int(m.group(1), 16)
    return [(v >> 16) & 255, (v >> 8) & 255, v & 255]


def pale_color(hex_color, amount):
    """Fade a colour toward the background.

    Mixing against the background rather than lowering the alpha keeps the
    result pale in light mode and softly muted in dark, and leaves the mark
    opaque so overlapping biplot arrows do not stack into darker patches.

    Args:
        hex_color (str): A ``#RRGGBB`` colour.
        amount (float): Share of background to mix in, 0 to 1.

    Returns:
        str: The mixed colour as ``#RRGGBB``.
    """
    c = hex_to_rgb(hex_color)
    if not c:
        return hex_color
    b = hex_to_rgb(THEME.bg) or [255, 255, 255]
    k = max(0.0, min(1.0, amount))
    mix = [int(round(v + (b[i] - v) * k)) for i, v in enumerate(c)]
    return '#%02X%02X%02X' % tuple(mix)


def cluster_tag(c):
    """Return the user-facing name of a cluster.

    Labels are 0-based internally but shown from 1, matching
    ``_cluster_label_short`` in the main dialog so C1 means the same thing in
    both places.

    Args:
        c (int): Internal cluster id; negative means noise.

    Returns:
        str: ``'C1'``, ``'C2'``… or ``'Noise'``.
    """
    return 'Noise' if c < 0 else 'C%d' % (int(c) + 1)


def element_color(key, elements=None):
    """Return a deterministic colour for an element symbol.

    The palette index is the element's position in the dataset's element list,
    so the same symbol keeps one colour across redraws and matches
    ``_element_color`` in the main dialog. Elements absent from the list fall
    back to a hash of the key so the colour is still stable.

    Args:
        key (str): Element key, e.g. ``'Fe'`` or ``'107Ag'``.
        elements (list[str] | None): The dataset's element list.

    Returns:
        str: A ``#RRGGBB`` colour.
    """
    els = list(elements or [])
    try:
        i = els.index(key)
    except ValueError:
        h = 0
        for ch in str(key):
            h = (h * 31 + ord(ch)) & 0xFFFFFFFF
            if h >= 0x80000000:
                h -= 0x100000000
        i = abs(h)
    return ELEMENT_PALETTE[i % len(ELEMENT_PALETTE)]


def _ring(n, rot, rad):
    """Return ``n`` points evenly spaced on a circle.

    Args:
        n (int): Number of vertices.
        rot (float): Angle of the first vertex, in radians.
        rad (float): Radius in marker units.

    Returns:
        list[tuple[float, float]]: The vertices.
    """
    return [(math.cos(rot + i * 2 * math.pi / n) * rad,
             math.sin(rot + i * 2 * math.pi / n) * rad) for i in range(n)]


def _build_marker_units():
    """Build the unit outline of every non-circular marker.

    Returns:
        dict[str, list[tuple[float, float]]]: Shape key to unit outline.
    """
    a, b, k = 0.40, 1.25, math.sqrt(0.5)
    plus = [(-a, -b), (a, -b), (a, -a), (b, -a), (b, a), (a, a),
            (a, b), (-a, b), (-a, a), (-b, a), (-b, -a), (-a, -a)]
    star = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = 0.62 if i % 2 else 1.55
        star.append((math.cos(ang) * rad, math.sin(ang) * rad))
    return {
        'square':        _ring(4, math.pi / 4, 1.20),
        'triangle':      _ring(3, -math.pi / 2, 1.35),
        'down-triangle': _ring(3, math.pi / 2, 1.35),
        'diamond':       _ring(4, -math.pi / 2, 1.38),
        'hexagon':       _ring(6, -math.pi / 2, 1.15),
        'plus':          plus,
        'cross':         [((px - py) * k, (px + py) * k) for px, py in plus],
        'star':          star,
        'bowtie':        [(-1.25, -1.05), (1.25, 1.05),
                          (1.25, -1.05), (-1.25, 1.05)],
    }


MARKER_UNITS = _build_marker_units()

SHAPES = ['circle', 'square', 'triangle', 'diamond',
          'cross', 'plus', 'star', 'hexagon', 'down-triangle', 'bowtie']

SHAPE_LABELS = {
    'circle': '● Circle', 'square': '■ Square', 'triangle': '▲ Triangle',
    'diamond': '◆ Diamond', 'cross': '✕ Cross', 'plus': '✚ Plus',
    'star': '★ Star', 'hexagon': '⬢ Hexagon',
    'down-triangle': '▼ Down triangle', 'bowtie': '⧓ Bowtie',
}

_SYMBOL_CACHE = {}


def marker_symbol(shape):
    """Return a pyqtgraph symbol for ``shape``.

    Circles use pyqtgraph's built-in ``'o'``, which is already a cached pixmap.
    Everything else becomes a ``QPainterPath`` built once and reused, because
    ``ScatterPlotItem`` keys its pixmap cache on the symbol object — returning
    a fresh path each call would defeat it.

    The path coordinates are half the unit outline: pyqtgraph draws symbols
    under ``painter.scale(size, size)``, and callers pass ``size = 2 * radius``,
    so halving reproduces the intended geometry exactly.

    Args:
        shape (str): A key from :data:`SHAPES`.

    Returns:
        str | QPainterPath: The symbol to hand to ``ScatterPlotItem``.
    """
    if shape == 'circle' or shape not in MARKER_UNITS:
        return 'o'
    path = _SYMBOL_CACHE.get(shape)
    if path is None:
        path = QPainterPath()
        pts = [(x / 2.0, y / 2.0) for x, y in MARKER_UNITS[shape]]
        path.moveTo(pts[0][0], pts[0][1])
        for x, y in pts[1:]:
            path.lineTo(x, y)
        path.closeSubpath()
        _SYMBOL_CACHE[shape] = path
    return path


_EL_PREFIX = re.compile(r'^\s*(\d+)\s*([A-Za-z][A-Za-z]?)\s*([+\-]\d*)?\s*$')
_EL_SUFFIX = re.compile(
    r'^\s*([A-Za-z][A-Za-z]?)\s*(?:[-\s]?\s*(\d+))?\s*([+\-]\d*)?\s*$')
_EL_BARE = re.compile(r'^\s*([A-Za-z][A-Za-z]?)')
_EL_SPLIT = re.compile(r'(\s*[,+]\s*)')
_EL_SEP = re.compile(r'^[\s,+]+$')


def parse_element_label(label):
    """Split an element key into ``(symbol, mass)``.

    Matches the clustering figures' parser: prefix (``107Ag``), suffix
    (``Ag107`` / ``Ag-107``) or a bare symbol.

    Args:
        label (str): Raw element key.

    Returns:
        tuple[str, str | None]: Symbol with any charge, and the mass number or
        None when the key carries none.
    """
    text = str(label or '').strip()
    if not text:
        return '', None
    m = _EL_PREFIX.match(text)
    if m:
        return m.group(2), m.group(1)
    m = _EL_SUFFIX.match(text)
    if m:
        return m.group(1) + (m.group(3) or ''), m.group(2) or None
    m = _EL_BARE.match(text)
    return (m.group(1), None) if m else (text, None)


def element_label_text(key, mode='Mass + Symbol'):
    """Format an element key as plain text.

    Args:
        key (str): Element key, possibly a comma- or plus-separated combination.
        mode (str): 'Symbol' drops the mass, 'Mass + Symbol' passes the key
            through, 'Atomic Notation' reorders to mass-then-symbol.

    Returns:
        str: The formatted label.
    """
    if mode == 'Mass + Symbol':
        return str(key)
    out = []
    for tok in _EL_SPLIT.split(str(key)):
        if not tok.strip() or _EL_SEP.match(tok):
            out.append(tok)
            continue
        sym, mass = parse_element_label(tok)
        out.append((mass + sym) if (mode == 'Atomic Notation' and mass)
                   else (sym or tok))
    return ''.join(out)


def element_label_html(key, mode='Mass + Symbol'):
    """Format an element key as rich text, raising the mass number.

    Qt labels accept a useful subset of HTML, so ``<sup>`` works directly.
    Text painted with ``QPainter`` cannot use markup and is handled separately
    by ``draw_element_label`` in :mod:`~results.cluster.live_qt.scatter`.

    Args:
        key (str): Element key.
        mode (str): One of Symbol, Mass + Symbol or Atomic Notation.

    Returns:
        str: HTML-safe markup.
    """
    from html import escape
    if mode == 'Mass + Symbol':
        return escape(str(key))
    out = []
    for tok in _EL_SPLIT.split(str(key)):
        if not tok.strip() or _EL_SEP.match(tok):
            out.append(escape(tok))
            continue
        sym, mass = parse_element_label(tok)
        if mode == 'Atomic Notation' and mass:
            out.append('<sup>%s</sup>%s' % (escape(mass), escape(sym)))
        else:
            out.append(escape(sym or tok))
    return ''.join(out)


def element_token_html(tok, mode='Mass + Symbol'):
    """Format one legend token, which may be an overflow marker.

    Args:
        tok (str): An element key, or a ``'+N…'`` overflow count.
        mode (str): The element label style.

    Returns:
        str: HTML for the token.
    """
    from html import escape
    return escape(tok) if re.match(r'^\+\d', str(tok)) \
        else element_label_html(tok, mode)


@dataclass
class UiState:
    """Appearance and display preferences."""

    font: str = 'system'
    font_style: str = 'normal'
    font_size: float = 13.5
    label_mode: str = 'Mass + Symbol'
    point_size: float = 0.0
    cent_size: float = 6.5
    colors: dict = field(default_factory=dict)
    shapes: dict = field(default_factory=dict)
    shape_by_sample: bool = True
    biplot_on: bool = True
    biplot_n: int = 8
    overlay_el: str = ''
    overlay_cmap: str = 'viridis'
    max_iso: int = 4
    min_pct: float = 1.0


@dataclass
class ExportState:
    """PNG export options."""

    scale: int = 3
    font_boost: float = 1.25
    transparent: bool = False


@dataclass
class View2D:
    """Pan and zoom of the 2-D view."""

    scale: float = 1.0
    ox: float = 0.0
    oy: float = 0.0


@dataclass
class View3D:
    """Orthographic framing of the 3-D view."""

    scale: float = 1.0
    base_scale: float = 1.0
    zoom: float = 1.0
    cx: float = 0.0
    cy: float = 0.0
    center: list = field(default_factory=lambda: [0.0, 0.0, 0.0])


class LiveState:
    """Everything the view needs to draw the clustering.

    Owns the dataset, the clustering result, the focus and visibility sets, and
    the display preferences.
    """

    def __init__(self):
        """Create an empty state, before any dataset or schema has arrived."""
        self.schema = None
        self.data = None
        self.palette = list(PALETTE)
        self.algo = 'K-Means'
        self.params = {}
        self.param_values = {}
        self.result = None
        self.running = False

        self.hidden = set()
        self.focus = None
        self.sample_hidden = set()
        self.sample_focus = None
        self.hover_idx = -1

        self.view = View2D()
        self.v3 = View3D()
        self.rot = {'az': 0.7, 'el': 0.35}
        self.drag3d = None

        self.proj = 'PCA'
        self.proj_info = {}
        self.dims = 2

        self.inset_on = False
        self.inset_collapsed = False
        self.eq_on = False
        self.eq_collapsed = False
        self.legend_on = True

        self.ui = UiState()
        self.exp = ExportState()
        self.overlay = None
        self._ramp = (None, None)
        self._raw_cache = (None, None)

    def raw_matrix(self):
        """Return the raw composition matrix as an array, built once per state.

        ``data['raw']`` arrives from the controller as nested Python lists.
        Converting it costs about as much as one pass over the whole dataset,
        and the legend asks for it once per cluster — with a thousand clusters
        that conversion alone dominated the redraw. The result is cached against
        the identity of the list it came from, so a new state rebuilds it and
        nothing else does.

        Returns:
            numpy.ndarray | None: An ``(n, elements)`` array, or None.
        """
        raw = (self.data or {}).get('raw')
        if raw is None:
            return None
        if self._raw_cache[0] is not raw:
            try:
                self._raw_cache = (raw, np.asarray(raw, dtype=float))
            except Exception:
                self._raw_cache = (raw, None)
        return self._raw_cache[1]

    def cluster_color(self, c):
        """Return the colour of cluster ``c``, honouring any override.

        Args:
            c (int): Cluster id; negative means noise.

        Returns:
            str: A ``#RRGGBB`` colour.
        """
        if c < 0:
            return THEME.noise
        return self.ui.colors.get(int(c)) or self.palette[int(c) % len(self.palette)]

    def ramp_stops(self):
        """Return the control points of the overlay colormap.

        Returns:
            list[list[int]]: At least two ``[r, g, b]`` stops, falling back to
            viridis when the backend sent no colormaps.
        """
        name = self.ui.overlay_cmap
        cmaps = (self.schema or {}).get('colormaps') or {}
        rgb = [hex_to_rgb(h) for h in (cmaps.get(name) or [])]
        rgb = [c for c in rgb if c]
        return rgb if len(rgb) > 1 else [hex_to_rgb(h) for h in VIRIDIS_FALLBACK]

    def ramp_color(self, i):
        """Return the colour for one of the 256 overlay steps.

        The ramp is interpolated once and cached, so the draw loop only indexes
        an array however many particles are on screen.

        Args:
            i (int): Step index, 0 to 255.

        Returns:
            str: A ``#RRGGBB`` colour.
        """
        name = self.ui.overlay_cmap
        key, arr = self._ramp
        if key != name or arr is None:
            stops = self.ramp_stops()
            last = len(stops) - 1
            arr = []
            for k in range(256):
                t = k / 255 * last
                a = int(math.floor(t))
                b = min(last, a + 1)
                f = t - a
                arr.append('#%02X%02X%02X' % tuple(
                    int(round(v + (stops[b][j] - v) * f))
                    for j, v in enumerate(stops[a])))
            self._ramp = (name, arr)
        return arr[max(0, min(255, int(i)))]


    def sample_names(self):
        """Return every sample in the dataset, in backend order.

        Returns:
            list[str]: Sample names, empty when no data is loaded.
        """
        names = (self.data or {}).get('sample_names')
        return list(names) if isinstance(names, (list, tuple)) else []

    def is_multi_sample(self):
        """Report whether the dataset holds more than one sample.

        Single-sample input gets no shape controls and no sample legend, since
        every particle would carry the same marker.

        Returns:
            bool: True when at least two samples are present.
        """
        return len(self.sample_names()) > 1

    def sample_of(self, i):
        """Return the sample name of particle ``i``.

        Args:
            i (int): Particle index within the current view.

        Returns:
            str: The sample the particle came from, or '' when unknown.
        """
        s = (self.data or {}).get('samples')
        if s is None or i >= len(s):
            return ''
        return s[i] if s[i] is not None else ''

    def shape_for(self, name):
        """Return the marker shape for a sample, honouring any override.

        Unassigned samples fall back to their position in :data:`SHAPES`, so
        the defaults stay stable as long as the sample list does.

        Args:
            name (str): Sample name.

        Returns:
            str: A key from :data:`SHAPES`.
        """
        if not self.ui.shape_by_sample or not self.is_multi_sample():
            return 'circle'
        o = self.ui.shapes.get(name)
        if o and o in SHAPES:
            return o
        names = self.sample_names()
        i = names.index(name) if name in names else 0
        return SHAPES[i % len(SHAPES)]

    def is_dimmed(self, c):
        """Report whether cluster ``c`` should be drawn faded.

        Args:
            c (int): Cluster id.

        Returns:
            bool: True when a different cluster holds the focus.
        """
        return self.focus is not None and c != self.focus

    def is_sample_dimmed(self, name):
        """Report whether sample ``name`` should be drawn faded.

        Args:
            name (str): Sample name.

        Returns:
            bool: True when a different sample is soloed.
        """
        return self.sample_focus is not None and name != self.sample_focus


    def current_frame(self):
        """Return the clustering result on screen right now.

        Returns:
            dict | None: The result, or None before one has arrived.
        """
        return self.result

    def cur_dims(self):
        """Return the display dimensionality.

        Returns:
            int: 2 or 3.
        """
        return (self.data or {}).get('dims') or 2

    def point_radius(self):
        """Return the particle radius in pixels.

        Uses the Appearance slider when set, otherwise scales down as the
        particle count rises so a dense cloud stays readable.

        Returns:
            float: Radius in pixels.
        """
        if self.ui.point_size > 0:
            return self.ui.point_size
        n = (self.data or {}).get('n', 0)
        return 2.0 if n > 1600 else (2.6 if n > 800 else 3.3)
