# `figures.py`

Figures the model draws itself, with matplotlib, inside the sandbox.

There are no figure templates. The model creates a figure with
``new_figure`` (or the familiar ``plt.subplots``) and draws whatever the user
asked for with ordinary matplotlib calls. Figures are plain
:class:`matplotlib.figure.Figure` objects, never pyplot state, so drawing in
the sandbox thread is safe.

After the code runs, every figure is styled for print, rendered once off
screen to catch drawing errors, and described in text (axes, scales, what
was drawn, empty panels). That description goes back to the model, which
cannot see the picture, so it can notice and fix a wrong or empty figure.

---

## Constants

| Name | Value |
|------|-------|
| `PALETTE` | `['#0072B2', '#E69F00', '#009E73', '#D55E00', '#CC79A7', '…` |
| `FONT_SIZE` | `10` |
| `STYLE` | `{'figure.facecolor': 'white', 'axes.facecolor': 'white', …` |
| `DEFAULT_SIZE` | `(6.4, 4.2)` |
| `MAX_FIGURES` | `6` |
| `MAX_SIZE_IN` | `16.0` |
| `NAMESPACE` | `{'LogNorm': LogNorm, 'Normalize': Normalize, 'SymLogNorm'…` |

## Classes

### `FigureLimitError` *(extends `RuntimeError`)*

Raised when generated code asks for too many or too large figures.

### `FigureCollector`

Creates and keeps the figures one piece of generated code draws.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` | Start with no figures. |
| `new_figure` | `(self, nrows=1, ncols=1, size=None, title=None, sharex=False, sharey=F` | Create a figure with a grid of axes. |
| `_make` | `(self, size)` | Create one empty figure, enforcing the count and size limits. |
| `current_figure` | `(self)` | The figure pyplot-style calls draw on, created when there is none. |
| `current_axes` | `(self)` | The axes pyplot-style calls draw on, created when there is none. |
| `set_current_axes` | `(self, ax)` | Make *ax* and its figure the target of pyplot-style calls. |

### `_StyleShim`

Stand-in for ``plt.style``: the house style is always used.

| Method | Signature | Description |
|--------|-----------|-------------|
| `use` | `(self, *args, **kwargs)` | Ignore style changes; figures keep the house style. |
| `context` | `(self, *args, **kwargs)` | Return a context manager that changes nothing. |

### `_ColormapShim`

Stand-in for ``plt.cm``: ``plt.cm.viridis`` returns the colormap.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__getattr__` | `(self, name)` | Look a colormap up by name. |

### `PyplotShim`

A safe ``plt`` that draws on the collector's figures.

Supports both styles models commonly write: ``fig, ax = plt.subplots()``
followed by ``ax.*`` calls, and stateful calls like ``plt.hist(...)`` and
``plt.xlabel(...)``, which go to the current axes. Saving to disk is not
available; the user saves from the chat.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, collector)` | Bind the shim to a collector. |
| `subplots` | `(self, nrows=1, ncols=1, figsize=None, sharex=False, sharey=False, **k` | Create a figure and axes, like ``matplotlib.pyplot.subplots``. |
| `figure` | `(self, figsize=None, **kw)` | Create an empty figure, like ``matplotlib.pyplot.figure``. |
| `subplot` | `(self, *args, **kw)` | Add a panel to the current figure, like ``matplotlib.pyplot.subplot``. |
| `subplot_mosaic` | `(self, mosaic, figsize=None, **kw)` | Create a figure from a mosaic layout, like ``pyplot.subplot_mosaic``. |
| `gcf` | `(self)` | Return the current figure. |
| `gca` | `(self)` | Return the current axes. |
| `sca` | `(self, ax)` | Make *ax* the current axes. |
| `get_cmap` | `(self, name=None, lut=None)` | Return a colormap by name. |
| `savefig` | `(self, *args, **kwargs)` | Refuse: figures are saved from the chat window. |
| `suptitle` | `(self, text, **kw)` | Set the current figure's title. |
| `colorbar` | `(self, mappable=None, ax=None, **kw)` | Add a colour bar for *mappable*, or for the last image or scatter drawn. |
| `xticks` | `(self, ticks=None, labels=None, **kw)` | Set x ticks on the current axes, like ``pyplot.xticks``. |
| `yticks` | `(self, ticks=None, labels=None, **kw)` | Set y ticks on the current axes, like ``pyplot.yticks``. |
| `_ticks` | `(self, axis, ticks, labels, **kw)` | Shared body of :meth:`xticks` and :meth:`yticks`. |
| `__getattr__` | `(self, name)` | Send any other pyplot call to the current axes. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `style_figure` | `(fig)` | Apply the house tick style so it survives redrawing outside the sandbox. |
| `render_png` | `(fig, dpi=100)` | Draw a figure off screen and return PNG bytes. |
| `_span` | `(lo, hi)` | Decades covered between two positive limits, or 0. |
| `_shares_labelled_y` | `(ax, panels)` | Whether *ax* shares its y axis with a panel that has a y label. |
| `_categorical` | `(ax)` | Whether the x tick labels are names rather than numbers. |
| `describe_figure` | `(fig, index=1)` | Describe what a figure shows, for a model that cannot see it. |
