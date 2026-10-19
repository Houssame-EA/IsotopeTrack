"""Figures the model draws itself, with matplotlib, inside the sandbox.

There are no figure templates. The model creates a figure with
``new_figure`` (or the familiar ``plt.subplots``) and draws whatever the user
asked for with ordinary matplotlib calls. Figures are plain
:class:`matplotlib.figure.Figure` objects, never pyplot state, so drawing in
the sandbox thread is safe.

After the code runs, every figure is styled for print, rendered once off
screen to catch drawing errors, and described in text (axes, scales, what
was drawn, empty panels). That description goes back to the model, which
cannot see the picture, so it can notice and fix a wrong or empty figure.
"""
from __future__ import annotations

import functools
import io
import logging
import math

import matplotlib
import numpy as np
from matplotlib import colormaps
from matplotlib.colors import (
    BoundaryNorm, LinearSegmentedColormap, ListedColormap, LogNorm, Normalize, SymLogNorm,
    TwoSlopeNorm, to_hex, to_rgba,
)
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, Patch, Polygon, Rectangle
from matplotlib.ticker import (
    AutoMinorLocator, FixedLocator, FormatStrFormatter, FuncFormatter, LogFormatterSciNotation,
    LogLocator, MaxNLocator, MultipleLocator, NullFormatter, PercentFormatter, ScalarFormatter,
)

_itk_log = logging.getLogger("IsotopeTrack.results.ai.figures")


def _marks_groups(name):
    """Wrap an Axes plotting method so the axis that holds the group names is recorded.

    Box and violin plots put one group per position on one axis; a log
    scale on that axis replaces the group names with numbers. The figure
    check reads ``itk_category_axis`` to catch it.
    """
    original = getattr(Axes, name)

    @functools.wraps(original)
    def wrapper(self, *args, **kwargs):
        """Draw, then note which axis carries the groups."""
        out = original(self, *args, **kwargs)
        horizontal = kwargs.get('vert') is False or kwargs.get('orientation') == 'horizontal'
        try:
            self.itk_category_axis = 'y' if horizontal else 'x'
        except Exception:
            pass
        return out
    wrapper.itk_wrapped = True
    return wrapper


for _name in ('boxplot', 'violinplot'):
    if not getattr(getattr(Axes, _name), 'itk_wrapped', False):
        setattr(Axes, _name, _marks_groups(_name))

try:
    import mpltern
    TERNARY = True
except Exception:
    TERNARY = False
    _itk_log.exception("mpltern is not available; ternary plots are disabled")

PALETTE = ['#0072B2', '#E69F00', '#009E73', '#D55E00', '#CC79A7',
           '#56B4E9', '#F0E442', '#000000', '#999999']

FONT_SIZE = 10

BASE_STYLE = {
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.edgecolor': '#333333',
    'axes.labelcolor': '#111111',
    'axes.titlesize': FONT_SIZE + 1,
    'axes.labelsize': FONT_SIZE,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.grid': False,
    'axes.prop_cycle': matplotlib.cycler(color=PALETTE),
    'font.size': FONT_SIZE,
    'legend.fontsize': FONT_SIZE - 1,
    'legend.frameon': False,
    'xtick.labelsize': FONT_SIZE - 1,
    'ytick.labelsize': FONT_SIZE - 1,
    'xtick.color': '#333333',
    'ytick.color': '#333333',
    'lines.linewidth': 1.6,
    'patch.linewidth': 0.6,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
}

LAB_INK = '#0b0b0b'
LAB_INK2 = '#52514e'
LAB_GRID = '#e3e2de'
LAB_INFLUENT = '#2a78d6'
LAB_EFFLUENT = '#eb6834'

def _installed_fonts(candidates):
    """The candidate font families that are installed, in order.

    Listing a family that is missing makes matplotlib print a warning every
    time it draws text, so only installed ones are named. DejaVu ships with
    matplotlib and is always there to supply characters the others lack.
    """
    try:
        from matplotlib import font_manager
        have = {f.name for f in font_manager.fontManager.ttflist}
    except Exception:
        have = set()
    found = [c for c in candidates if c in have]
    return found + [c for c in ('DejaVu Serif', 'DejaVu Sans') if c not in found]


LAB_FONTS = _installed_fonts(['Times New Roman', 'Times', 'Nimbus Roman', 'Liberation Serif'])

LAB_STYLE = {
    'font.family': list(LAB_FONTS),
    'font.serif': list(LAB_FONTS),
    'mathtext.fontset': 'stix',
    'font.weight': 'bold',
    'font.size': FONT_SIZE + 1,
    'axes.labelweight': 'bold',
    'axes.titleweight': 'bold',
    'axes.titlelocation': 'left',
    'axes.titlesize': FONT_SIZE + 2,
    'axes.labelsize': FONT_SIZE + 1,
    'axes.edgecolor': LAB_INK,
    'axes.labelcolor': LAB_INK,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'grid.color': LAB_GRID,
    'text.color': LAB_INK,
    'xtick.color': LAB_INK2,
    'ytick.color': LAB_INK2,
    'xtick.labelsize': FONT_SIZE,
    'ytick.labelsize': FONT_SIZE,
    'legend.fontsize': FONT_SIZE,
    'mathtext.default': 'bf',
}

STYLE = {**BASE_STYLE, **LAB_STYLE}

DEFAULT_SIZE = (6.4, 4.2)
MAX_FIGURES = 12
PANEL_LABEL_GID = 'itk_panel_label'
MAX_SIZE_IN = 16.0

def label_panels(axes, labels=None, size=None):
    """Put panel letters (a), (b), ... at the top left of each panel.

    Works on ordinary, ternary and polar panels alike.

    Args:
        axes (Axes or array-like): The panels, in reading order.
        labels (list): Letters to use instead of (a), (b), ...
        size (float): Font size; one step above the axis labels by default.
    """
    flat = list(np.ravel(np.asarray(axes, dtype=object))) if not hasattr(axes, 'transAxes') else [axes]
    for k, ax in enumerate(flat):
        text = labels[k] if labels and k < len(labels) else f"({chr(ord('a') + k)})"
        letter = ax.text(-0.08, 1.04, text, transform=ax.transAxes, ha='right', va='bottom',
                         fontsize=size or (FONT_SIZE + 2), fontweight='bold')
        letter.set_gid(PANEL_LABEL_GID)


def lognormal_hist(ax, values, bins=None, color=None, label=None, fit=True, alpha=0.45, unit=''):
    """Draw a filled log-binned histogram with its fitted log-normal curve.

    The fit is the maximum-likelihood log-normal (mean and standard
    deviation of the log values). The curve is scaled to the counts, so it
    sits on the bars. The fitted geometric mean (GM, the centre of the
    log-normal) and geometric standard deviation (GSD) are added to the
    legend label; the GM differs from the measured median when the data are
    not log-normal, e.g. cut off at the detection limit.

    Args:
        ax (Axes): Axes to draw on; its x axis is set to log.
        values (array-like): Positive values, e.g. masses or diameters.
        bins (array-like): Bin edges; 50 log-spaced edges over the data by default.
        color (str): Bar and curve colour.
        label (str): Legend label; the fitted GM and GSD are appended to it.
        fit (bool): Whether to draw the fitted curve.
        alpha (float): Bar transparency, so overlapping samples stay readable.
        unit (str): Unit shown after the median in the label, e.g. 'nm'.

    Returns:
        dict: ``n``, ``gm`` and ``gsd`` of the fit (NaN when fewer than 3 values).
    """
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v) & (v > 0)]
    if bins is None:
        lo, hi = (v.min(), v.max()) if v.size else (1.0, 10.0)
        if hi <= lo:
            lo, hi = lo / 2, hi * 2
        bins = np.logspace(np.log10(lo), np.log10(hi), 50)
    bins = np.asarray(bins, dtype=float)
    out = {'n': int(v.size), 'gm': float('nan'), 'gsd': float('nan')}
    if v.size >= 3:
        logs = np.log(v)
        mu, sigma = float(logs.mean()), float(logs.std(ddof=0))
        out.update(gm=float(np.exp(mu)), gsd=float(np.exp(sigma)))
    text = label
    if label is not None and v.size >= 3 and fit:
        suffix = f" {unit}" if unit else ''
        text = f"{label} (GM {out['gm']:.3g}{suffix}, GSD {out['gsd']:.2f})"
    _, _, patches = ax.hist(v, bins=bins, color=color, alpha=alpha, edgecolor=color, linewidth=0.6, label=text)
    if fit and v.size >= 3 and out['gsd'] > 1:
        line_color = color or (patches[0].get_facecolor() if len(patches) else None)
        edges = bins[(bins > 0)]
        widths = np.diff(np.log(edges))
        width = float(np.median(widths)) if widths.size else 1.0
        x = np.logspace(np.log10(edges[0]), np.log10(edges[-1]), 400)
        z = (np.log(x) - np.log(out['gm'])) / np.log(out['gsd'])
        y = v.size * width * np.exp(-0.5 * z * z) / (np.log(out['gsd']) * math.sqrt(2 * math.pi))
        ax.plot(x, y, color=line_color, lw=1.8, alpha=1.0)
    ax.set_xscale('log')
    if bins.size and bins[0] > 0 and math.log10(bins[-1] / bins[0]) <= 2.5:
        ax.xaxis.set_major_locator(LogLocator(subs=(1.0, 2.0, 5.0)))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}"))
        ax.xaxis.set_minor_formatter(NullFormatter())
    return out


NAMESPACE = {
    'LogNorm': LogNorm, 'Normalize': Normalize, 'SymLogNorm': SymLogNorm,
    'TwoSlopeNorm': TwoSlopeNorm, 'BoundaryNorm': BoundaryNorm,
    'ListedColormap': ListedColormap, 'LinearSegmentedColormap': LinearSegmentedColormap,
    'to_rgba': to_rgba, 'to_hex': to_hex, 'colormaps': colormaps,
    'Patch': Patch, 'Line2D': Line2D, 'Rectangle': Rectangle, 'Ellipse': Ellipse,
    'Circle': Circle, 'Polygon': Polygon, 'FancyArrowPatch': FancyArrowPatch,
    'LogLocator': LogLocator, 'MaxNLocator': MaxNLocator, 'MultipleLocator': MultipleLocator,
    'FixedLocator': FixedLocator, 'AutoMinorLocator': AutoMinorLocator,
    'FuncFormatter': FuncFormatter, 'FormatStrFormatter': FormatStrFormatter,
    'ScalarFormatter': ScalarFormatter, 'LogFormatterSciNotation': LogFormatterSciNotation,
    'PercentFormatter': PercentFormatter, 'NullFormatter': NullFormatter,
    'PALETTE': list(PALETTE),
    'lognormal_hist': lognormal_hist,
    'label_panels': label_panels,
}


def lab_colors(samples):
    """The lab's colour for each sample: influent blue, effluent orange, others from the palette.

    Args:
        samples (list): Sample names.

    Returns:
        dict: ``{sample: hex colour}``.
    """
    import re as _re
    out, k = {}, 0
    for s in samples:
        name = str(s)
        if _re.search(r'(?i)(\binf\b|[_\s-]inf(?=[_\s-]|\d|$)|^inf|influent)', name):
            out[s] = LAB_INFLUENT
        elif _re.search(r'(?i)(\beff\b|[_\s-]eff(?=[_\s-]|\d|$)|^eff|effluent)', name):
            out[s] = LAB_EFFLUENT
        else:
            out[s] = PALETTE[k % len(PALETTE)]
            k += 1
    return out


def axes_title(ax):
    """A panel's title wherever it sits: the lab style puts titles on the left."""
    parts = []
    for loc in ('left', 'center', 'right'):
        try:
            text = ax.get_title(loc=loc)
        except Exception:
            text = ''
        if text:
            parts.append(text)
    return ' '.join(parts)


def figure_rc(fig):
    """The style a figure is drawn and saved with: the lab style plus any change the user asked for."""
    return {**STYLE, **(getattr(fig, 'itk_rc', None) or {})}


class _RcShim(dict):
    """Stand-in for ``plt.rcParams``: a change applies at once and stays with this answer's figures.

    Tick labels are drawn after the code has finished, so a change made
    only to matplotlib's settings would be lost there; the collector keeps
    it and every figure is drawn and saved with it.
    """

    def __init__(self, collector):
        """Bind to a collector."""
        super().__init__()
        self._collector = collector

    def __setitem__(self, key, value):
        """Apply one setting, refusing names matplotlib does not know."""
        matplotlib.rcParams[key] = value
        super().__setitem__(key, matplotlib.rcParams[key])
        self._collector.set_rc(key, matplotlib.rcParams[key])

    def update(self, *args, **kwargs):
        """Apply several settings."""
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def __getitem__(self, key):
        """Return the setting in force."""
        return matplotlib.rcParams[key]

    def get(self, key, default=None):
        """Return the setting in force, or *default*."""
        try:
            return matplotlib.rcParams[key]
        except KeyError:
            return default


class FigureLimitError(RuntimeError):
    """Raised when generated code asks for too many or too large figures."""


class FigureCollector:
    """Creates and keeps the figures one piece of generated code draws."""

    def __init__(self):
        """Start with no figures."""
        self.figures = []
        self._current = None
        self._current_ax = None
        self.rc = {}

    def set_rc(self, key, value):
        """Keep a style change the code made, for every figure of this answer."""
        self.rc[key] = value
        for fig in self.figures:
            fig.itk_rc = dict(self.rc)

    def new_figure(self, nrows=1, ncols=1, size=None, title=None, sharex=False,
                   sharey=False, projection=None, **subplot_kw):
        """Create a figure with a grid of axes.

        Args:
            nrows (int): Rows of panels.
            ncols (int): Columns of panels.
            size (tuple): ``(width, height)`` in inches; grows with the grid
                by default.
            title (str): Optional figure title.
            sharex (bool): Share x axes between panels.
            sharey (bool): Share y axes between panels.
            projection (str or list): Projection of every panel, e.g.
                ``'polar'``, ``'3d'`` or ``'ternary'``, or one entry per
                panel in reading order (``None`` for an ordinary panel), e.g.
                ``['ternary', None]`` for a ternary next to a heatmap.
            **subplot_kw: Passed to ``Figure.subplots`` (e.g.
                ``gridspec_kw``, ``subplot_kw=dict(projection='polar')``).

        Returns:
            tuple: ``(fig, axes)``; ``axes`` is one Axes for a single panel,
            otherwise a numpy array of Axes.
        """
        fig = self._make(size or (DEFAULT_SIZE[0] * min(ncols, 3) * 0.85 if ncols > 1 else DEFAULT_SIZE[0],
                                  DEFAULT_SIZE[1] * min(nrows, 3) * 0.85 if nrows > 1 else DEFAULT_SIZE[1]))
        if isinstance(projection, (list, tuple)):
            n = int(nrows) * int(ncols)
            kinds = list(projection) + [None] * (n - len(projection))
            extra = dict(subplot_kw.pop('subplot_kw', None) or {})
            panels = [fig.add_subplot(int(nrows), int(ncols), k + 1,
                                      **({**extra, 'projection': kinds[k]} if kinds[k] else extra))
                      for k in range(n)]
            axes = panels[0] if n == 1 else np.array(panels, dtype=object).reshape(int(nrows), int(ncols)).squeeze()
            if title:
                fig.suptitle(str(title))
            self._current_ax = panels[0]
            return fig, axes
        if projection:
            kw = dict(subplot_kw.pop('subplot_kw', None) or {})
            kw['projection'] = projection
            subplot_kw['subplot_kw'] = kw
        axes = fig.subplots(int(nrows), int(ncols), sharex=sharex, sharey=sharey, squeeze=True, **subplot_kw)
        if title:
            fig.suptitle(str(title))
        first = axes if not hasattr(axes, 'flat') else axes.flat[0]
        self._current_ax = first
        return fig, axes

    def _make(self, size):
        """Create one empty figure, enforcing the count and size limits."""
        if len(self.figures) >= MAX_FIGURES:
            raise FigureLimitError(f"At most {MAX_FIGURES} figures per answer.")
        w, h = (float(size[0]), float(size[1]))
        if not (0 < w <= MAX_SIZE_IN and 0 < h <= MAX_SIZE_IN):
            raise FigureLimitError(f"Figure size must be within {MAX_SIZE_IN:g} x {MAX_SIZE_IN:g} inches.")
        fig = Figure(figsize=(w, h), dpi=100, layout='constrained')
        if self.rc:
            fig.itk_rc = dict(self.rc)
        self.figures.append(fig)
        self._current = fig
        self._current_ax = None
        return fig

    def current_figure(self):
        """The figure pyplot-style calls draw on, created when there is none."""
        if self._current is None:
            self._make(DEFAULT_SIZE)
        return self._current

    def current_axes(self):
        """The axes pyplot-style calls draw on, created when there is none."""
        fig = self.current_figure()
        if self._current_ax is None or self._current_ax.figure is not fig:
            self._current_ax = fig.axes[0] if fig.axes else fig.add_subplot(111)
        return self._current_ax

    def set_current_axes(self, ax):
        """Make *ax* and its figure the target of pyplot-style calls."""
        self._current_ax = ax
        self._current = ax.figure


class _StyleShim:
    """Stand-in for ``plt.style``: the house style is always used."""

    available = ['default']

    def use(self, *args, **kwargs):
        """Ignore style changes; figures keep the house style."""
        return None

    def context(self, *args, **kwargs):
        """Return a context manager that changes nothing."""
        import contextlib
        return contextlib.nullcontext()


class _ColormapShim:
    """Stand-in for ``plt.cm``: ``plt.cm.viridis`` returns the colormap."""

    def __getattr__(self, name):
        """Look a colormap up by name."""
        if name.startswith('_'):
            raise AttributeError(name)
        try:
            return colormaps[name]
        except KeyError:
            raise AttributeError(f"No colormap '{name}'") from None


class PyplotShim:
    """A safe ``plt`` that draws on the collector's figures.

    Supports both styles models commonly write: ``fig, ax = plt.subplots()``
    followed by ``ax.*`` calls, and stateful calls like ``plt.hist(...)`` and
    ``plt.xlabel(...)``, which go to the current axes. Saving to disk is not
    available; the user saves from the chat.
    """

    _AXES_ALIASES = {
        'xlabel': 'set_xlabel', 'ylabel': 'set_ylabel', 'title': 'set_title',
        'xlim': 'set_xlim', 'ylim': 'set_ylim', 'xscale': 'set_xscale', 'yscale': 'set_yscale',
    }
    _NO_OPS = {'show', 'close', 'tight_layout', 'ion', 'ioff', 'draw', 'pause', 'clf', 'cla',
               'subplots_adjust', 'margins_adjust', 'interactive', 'rcdefaults', 'switch_backend'}

    def __init__(self, collector):
        """Bind the shim to a collector.

        Args:
            collector (FigureCollector): Where figures are created.
        """
        self._c = collector
        self.style = _StyleShim()
        self.cm = _ColormapShim()
        self.rcParams = _RcShim(collector)
        self.colormaps = colormaps

    def subplots(self, nrows=1, ncols=1, figsize=None, sharex=False, sharey=False, **kw):
        """Create a figure and axes, like ``matplotlib.pyplot.subplots``."""
        kw.pop('dpi', None)
        kw.pop('layout', None)
        kw.pop('constrained_layout', None)
        kw.pop('tight_layout', None)
        squeeze = kw.pop('squeeze', True)
        fig, axes = self._c.new_figure(nrows, ncols, size=figsize, sharex=sharex, sharey=sharey, **kw)
        if not squeeze and not hasattr(axes, 'flat'):
            import numpy as np
            axes = np.array([[axes]])
        return fig, axes

    def figure(self, figsize=None, **kw):
        """Create an empty figure, like ``matplotlib.pyplot.figure``."""
        return self._c._make(figsize or DEFAULT_SIZE)

    def subplot(self, *args, **kw):
        """Add a panel to the current figure, like ``matplotlib.pyplot.subplot``."""
        fig = self._c.current_figure()
        ax = fig.add_subplot(*(args or (111,)), **kw)
        self._c.set_current_axes(ax)
        return ax

    def subplot_mosaic(self, mosaic, figsize=None, **kw):
        """Create a figure from a mosaic layout, like ``pyplot.subplot_mosaic``."""
        fig = self._c._make(figsize or DEFAULT_SIZE)
        axd = fig.subplot_mosaic(mosaic, **kw)
        first = next(iter(axd.values()))
        self._c.set_current_axes(first)
        return fig, axd

    def gcf(self):
        """Return the current figure."""
        return self._c.current_figure()

    def gca(self):
        """Return the current axes."""
        return self._c.current_axes()

    def sca(self, ax):
        """Make *ax* the current axes."""
        self._c.set_current_axes(ax)

    def rc(self, group, **kwargs):
        """Change a group of style settings, like ``matplotlib.pyplot.rc('font', family='Arial')``."""
        for key, value in kwargs.items():
            self.rcParams[f"{group}.{key}"] = value

    def get_cmap(self, name=None, lut=None):
        """Return a colormap by name."""
        cmap = colormaps[name or 'viridis']
        return cmap.resampled(lut) if lut else cmap

    def colorbar(self, mappable=None, ax=None, **kw):
        """Add a colour bar to the current figure, like ``matplotlib.pyplot.colorbar``."""
        axes = ax if ax is not None else self._c.current_axes()
        if mappable is None:
            found = list(axes.images) + list(axes.collections)
            if not found:
                raise RuntimeError("plt.colorbar needs something coloured by value; pass the scatter or image.")
            mappable = found[-1]
        return self._c.current_figure().colorbar(mappable, ax=axes, **kw)

    def savefig(self, *args, **kwargs):
        """Refuse: figures are saved from the chat window."""
        raise PermissionError("Saving files is not available; the user saves figures from the chat.")

    def suptitle(self, text, **kw):
        """Set the current figure's title."""
        return self._c.current_figure().suptitle(text, **kw)

    def colorbar(self, mappable=None, ax=None, **kw):
        """Add a colour bar for *mappable*, or for the last image or scatter drawn."""
        axes = ax or self._c.current_axes()
        if mappable is None:
            target = axes if not hasattr(axes, 'flat') else axes.flat[0]
            found = list(target.images) + [c for c in target.collections if c.get_array() is not None]
            if not found:
                raise RuntimeError("colorbar() needs something with a colour scale drawn first")
            mappable = found[-1]
        return self._c.current_figure().colorbar(mappable, ax=axes, **kw)

    def xticks(self, ticks=None, labels=None, **kw):
        """Set x ticks on the current axes, like ``pyplot.xticks``."""
        return self._ticks('x', ticks, labels, **kw)

    def yticks(self, ticks=None, labels=None, **kw):
        """Set y ticks on the current axes, like ``pyplot.yticks``."""
        return self._ticks('y', ticks, labels, **kw)

    def _ticks(self, axis, ticks, labels, **kw):
        """Shared body of :meth:`xticks` and :meth:`yticks`."""
        ax = self._c.current_axes()
        rotation = kw.pop('rotation', None)
        setter = ax.set_xticks if axis == 'x' else ax.set_yticks
        if ticks is not None:
            setter(ticks, labels) if labels is not None else setter(ticks)
        if rotation is not None:
            ax.tick_params(axis=axis, labelrotation=rotation)
        if kw:
            ax.tick_params(axis=axis, **{k: v for k, v in kw.items() if k in ('labelsize', 'colors', 'direction')})
        return (ax.get_xticks() if axis == 'x' else ax.get_yticks())

    def __getattr__(self, name):
        """Send any other pyplot call to the current axes."""
        if name.startswith('_'):
            raise AttributeError(name)
        if name in self._NO_OPS:
            return lambda *a, **k: None
        if name in NAMESPACE:
            return NAMESPACE[name]
        target = self._AXES_ALIASES.get(name, name)
        ax = self._c.current_axes()
        if hasattr(ax, target):
            return getattr(ax, target)
        raise AttributeError(f"plt.{name} is not available here; draw with the axes object instead")


def style_figure(fig):
    """Apply the house tick style and layout so they survive redrawing outside the sandbox.

    A ``tight_layout`` call in generated code is replaced by the constrained
    layout, which keeps a figure title clear of the panel titles.

    Args:
        fig (Figure): Figure to style.
    """
    try:
        fig.set_layout_engine('constrained')
    except Exception:
        _itk_log.debug("Could not set the constrained layout", exc_info=True)
    rc = figure_rc(fig)
    weight = rc.get('font.weight', 'normal')
    for ax in fig.axes:
        try:
            ax.tick_params(labelsize=rc.get('xtick.labelsize', FONT_SIZE), colors=rc.get('xtick.color', LAB_INK2),
                           direction='out')
            for label in ax.get_xticklabels() + ax.get_yticklabels():
                label.set_fontweight(weight)
        except Exception:
            _itk_log.debug("Could not style an axes", exc_info=True)


_INK = {'#000000', '#0b0b0b', '#111111', '#1f1f1f', '#222222', '#333333', '#444444', '#52514e'}
_PAPER = {'#ffffff', '#fefefe', '#fafafa'}
DARK_PREVIEW = {'paper': '#252526', 'ink': '#d4d4d4', 'soft': '#9d9d9d'}


def _hex(color):
    """A colour as lower-case hex, or ``None`` when it cannot be read."""
    try:
        return to_hex(color, keep_alpha=False).lower()
    except Exception:
        return None


def _dark_swaps(fig):
    """Recolour a figure's paper and ink for a dark preview.

    Only the default black text, white backgrounds and dark-grey axes are
    changed; the colours of the data stay as the model chose them.

    Returns:
        list: ``(setter, original)`` pairs that undo every change.
    """
    undo = []
    paper, ink, soft = DARK_PREVIEW['paper'], DARK_PREVIEW['ink'], DARK_PREVIEW['soft']

    def swap(getter, setter, table, new):
        """Replace a colour if it is one of the defaults in *table*."""
        old = getter()
        if _hex(old) in table:
            setter(new)
            undo.append((setter, old))

    swap(fig.get_facecolor, fig.set_facecolor, _PAPER, paper)
    texts = list(fig.texts)
    if getattr(fig, '_suptitle', None) is not None:
        texts.append(fig._suptitle)
    for ax in fig.axes:
        swap(ax.get_facecolor, ax.set_facecolor, _PAPER, paper)
        for spine in ax.spines.values():
            swap(spine.get_edgecolor, spine.set_edgecolor, _INK, soft)
        for axis in (ax.xaxis, ax.yaxis):
            texts.append(axis.label)
            texts.extend(axis.get_ticklabels(which='both'))
            for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                swap(tick.tick1line.get_color, tick.tick1line.set_color, _INK, soft)
                swap(tick.tick2line.get_color, tick.tick2line.set_color, _INK, soft)
                swap(tick.label1.get_color, tick.label1.set_color, _INK, ink)
                swap(tick.label2.get_color, tick.label2.set_color, _INK, ink)
        texts.extend([ax.title, ax._left_title, ax._right_title] + list(ax.texts))
        for line in ax.lines:
            swap(line.get_color, line.set_color, _INK, ink)
        leg = ax.get_legend()
        if leg is not None:
            texts.extend(leg.get_texts())
            if leg.get_title() is not None:
                texts.append(leg.get_title())
            frame = leg.get_frame()
            swap(frame.get_facecolor, frame.set_facecolor, _PAPER, paper)
            for h in getattr(leg, 'legend_handles', None) or getattr(leg, 'legendHandles', []):
                if isinstance(h, Line2D):
                    swap(h.get_color, h.set_color, _INK, ink)
                elif hasattr(h, 'get_edgecolor'):
                    swap(h.get_edgecolor, h.set_edgecolor, _INK, ink)
    for t in texts:
        swap(t.get_color, t.set_color, _INK, ink)
    return undo


def render_png(fig, dpi=100, dark=False):
    """Draw a figure off screen and return PNG bytes.

    Drawing is where many plotting mistakes surface (bad data, impossible
    limits), so this is also the check that the figure is valid.

    Args:
        fig (Figure): Figure to draw.
        dpi (int): Resolution.
        dark (bool): Draw a dark-theme preview; the figure itself is left
            unchanged afterwards, so saving still gives the white version.

    Returns:
        bytes: The PNG image.
    """
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    FigureCanvasAgg(fig)
    buf = io.BytesIO()
    with matplotlib.rc_context(figure_rc(fig)):
        if dark:
            fig.canvas.draw()
            undo = _dark_swaps(fig)
            try:
                fig.savefig(buf, format='png', dpi=dpi, facecolor=fig.get_facecolor())
            finally:
                for setter, old in reversed(undo):
                    setter(old)
        else:
            fig.savefig(buf, format='png', dpi=dpi, facecolor='white')
    return buf.getvalue()


def _span(lo, hi):
    """Decades covered between two positive limits, or 0."""
    if lo > 0 and hi > 0 and hi > lo:
        return math.log10(hi / lo)
    return 0.0


_SHARE_WORDS = ('cumulative', 'ecdf', 'cdf', 'fraction', 'probability', 'proportion', 'percent', '%', 'share')


def _is_share_axis(lo, hi, label):
    """Whether an axis shows a share or a cumulative fraction, which stays linear.

    Args:
        lo (float): Lowest data value.
        hi (float): Highest data value.
        label (str): Axis label.

    Returns:
        bool: True for values within 0 to 1, or a label naming a share.
    """
    text = str(label or '').lower()
    if lo >= 0 and hi <= 1.0 + 1e-9:
        return True
    return any(w in text for w in _SHARE_WORDS)


def _shares_labelled_x(ax, panels):
    """Whether *ax* shares its x axis with a panel that has an x label, as a twin y axis does."""
    try:
        group = ax.get_shared_x_axes()
        return any(o is not ax and o.get_xlabel() and group.joined(ax, o) for o in panels)
    except Exception:
        return False


def _shares_labelled_y(ax, panels):
    """Whether *ax* shares its y axis with a panel that has a y label."""
    try:
        group = ax.get_shared_y_axes()
        return any(o is not ax and o.get_ylabel() and group.joined(ax, o) for o in panels)
    except Exception:
        return False


def _categorical(ax, which='x'):
    """Whether the tick labels of one axis are names rather than numbers."""
    for t in (ax.get_xticklabels() if which == 'x' else ax.get_yticklabels()):
        text = t.get_text().replace('\u2212', '-').replace(',', '').strip()
        if not text:
            continue
        try:
            float(text.lstrip('$').rstrip('$'))
        except ValueError:
            if not text.startswith('$'):
                return True
    return False


def _text_overlaps(fig):
    """Pairs of visible titles and labels that are drawn on top of each other."""
    try:
        renderer = fig.canvas.get_renderer()
    except Exception:
        return []
    items = []
    sup = getattr(fig, '_suptitle', None)
    if sup is not None and sup.get_text():
        items.append(('figure title', sup))
    for k, ax in enumerate(fig.axes, start=1):
        for name, t in (('title', ax.title), ('x label', ax.xaxis.label), ('y label', ax.yaxis.label)):
            if t.get_text() and t.get_visible():
                items.append((f'panel {k} {name}', t))
        leg = ax.get_legend()
        if leg is not None and leg.get_visible():
            items.append((f'panel {k} legend', leg))
    boxes = []
    for name, artist in items:
        try:
            boxes.append((name, artist.get_window_extent(renderer)))
        except Exception:
            continue
    found = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i][1], boxes[j][1]
            if a.width and b.width and a.overlaps(b):
                found.append((boxes[i][0], boxes[j][0]))
    return found


def describe_figure(fig, index=1):
    """Describe what a figure shows, for a model that cannot see it.

    Args:
        fig (Figure): Figure to describe.
        index (int): Figure number shown in the description.

    Returns:
        tuple: ``(description, warnings)``, a short text and a list of
        problems worth fixing (empty panels, unlabelled axes, data spanning
        several decades on a linear axis).
    """
    lines = []
    warnings = []
    title = fig._suptitle.get_text() if getattr(fig, '_suptitle', None) else ''
    w, h = fig.get_size_inches()
    lines.append(f"Figure {index}: {w:.1f} x {h:.1f} in" + (f", title '{title}'" if title else ''))
    panels = [ax for ax in fig.axes if ax.get_label() != '<colorbar>' and ax.get_visible()]
    for k, ax in enumerate(panels, start=1):
        n_lines = len(ax.lines)
        n_points = 0
        for c in ax.collections:
            try:
                n_points += len(c.get_offsets())
            except Exception:
                pass
        n_patches = len(ax.patches)
        n_images = len(ax.images)
        drawn = []
        if n_lines:
            drawn.append(f"{n_lines} line(s)")
        if n_points:
            drawn.append(f"{n_points} marker(s)")
        if n_patches:
            drawn.append(f"{n_patches} bar/patch(es)")
        if n_images:
            drawn.append(f"{n_images} image(s)")
        leg = ax.get_legend()
        legend = [t.get_text() for t in leg.get_texts()] if leg else []
        name = getattr(ax, 'name', 'rectilinear')
        desc = (f"  panel {k}: title '{axes_title(ax)}', x '{ax.get_xlabel()}' ({ax.get_xscale()}), "
                f"y '{ax.get_ylabel()}' ({ax.get_yscale()})")
        if name != 'rectilinear':
            desc = f"  panel {k}: {name} projection, title '{axes_title(ax)}'"
        desc += f"; drawn: {', '.join(drawn) if drawn else 'nothing'}"
        if legend:
            desc += f"; legend: {', '.join(legend[:8])}"
        lines.append(desc)
        if not drawn and not ax.texts:
            warnings.append(f"Figure {index} panel {k} is empty.")
            continue
        if name == 'rectilinear' and n_images == 0:
            groups = getattr(ax, 'itk_category_axis', None)
            if groups and (ax.get_xscale() if groups == 'x' else ax.get_yscale()) == 'log':
                value = 'y' if groups == 'x' else 'x'
                warnings.append(f"Figure {index} panel {k}: the log scale is on the {groups} axis, which holds "
                                f"the groups of the box or violin plot, so their names are lost; set it on the "
                                f"value axis instead (ax.set_{value}scale('log')) and keep the names.")
            rects = [r for r in ax.patches if isinstance(r, Rectangle)]
            gone = 0
            if rects and ax.get_xscale() == 'log' and _categorical(ax, 'y'):
                gone = sum(1 for r in rects if r.get_width() <= 0)
            elif rects and ax.get_yscale() == 'log' and _categorical(ax, 'x'):
                gone = sum(1 for r in rects if r.get_height() <= 0)
            if gone:
                warnings.append(f"Figure {index} panel {k}: {gone} bar(s) are zero or negative, so they are "
                                "invisible on the log axis; leave them out and say so in the title or a note, "
                                "or use a linear axis.")
            if not ax.get_xlabel() and not _categorical(ax) and not _shares_labelled_x(ax, panels):
                warnings.append(f"Figure {index} panel {k} has no x-axis label.")
            if not ax.get_ylabel() and not _shares_labelled_y(ax, panels):
                warnings.append(f"Figure {index} panel {k} has no y-axis label.")
            dl = ax.dataLim
            if (ax.get_xscale() == 'linear' and _span(dl.x0, dl.x1) > 2.5 and n_patches == 0
                    and not _is_share_axis(dl.x0, dl.x1, ax.get_xlabel())):
                warnings.append(f"Figure {index} panel {k}: x data span {_span(dl.x0, dl.x1):.1f} "
                                "decades on a linear axis; a log axis may read better.")
            if (ax.get_yscale() == 'linear' and _span(dl.y0, dl.y1) > 2.5
                    and not _is_share_axis(dl.y0, dl.y1, ax.get_ylabel())):
                warnings.append(f"Figure {index} panel {k}: y data span {_span(dl.y0, dl.y1):.1f} "
                                "decades on a linear axis; a log axis may read better.")
    for a, b in _text_overlaps(fig)[:3]:
        warnings.append(f"Figure {index}: the {a} and the {b} overlap; move or shorten one of them.")
    return '\n'.join(lines), warnings
