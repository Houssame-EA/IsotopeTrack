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
| `BASE_STYLE` | `{'figure.facecolor': 'white', 'axes.facecolor': 'white', …` |
| `LAB_INK` | `'#0b0b0b'` |
| `LAB_INK2` | `'#52514e'` |
| `LAB_GRID` | `'#e3e2de'` |
| `LAB_INFLUENT` | `'#2a78d6'` |
| `LAB_EFFLUENT` | `'#eb6834'` |
| `LAB_FONTS` | `_installed_fonts(['Times New Roman', 'Times', 'Nimbus Rom…` |
| `LAB_STYLE` | `{'font.family': list(LAB_FONTS), 'font.serif': list(LAB_F…` |
| `STYLE` | `{**BASE_STYLE, **LAB_STYLE}` |
| `DEFAULT_SIZE` | `(6.4, 4.2)` |
| `MAX_FIGURES` | `12` |
| `PANEL_LABEL_GID` | `'itk_panel_label'` |
| `MAX_SIZE_IN` | `16.0` |
| `NAMESPACE` | `{'LogNorm': LogNorm, 'Normalize': Normalize, 'SymLogNorm'…` |
| `_INK` | `{'#000000', '#0b0b0b', '#111111', '#1f1f1f', '#222222', '…` |
| `_PAPER` | `{'#ffffff', '#fefefe', '#fafafa'}` |
| `DARK_PREVIEW` | `{'paper': '#252526', 'ink': '#d4d4d4', 'soft': '#9d9d9d'}` |
| `_SHARE_WORDS` | `('cumulative', 'ecdf', 'cdf', 'fraction', 'probability', …` |

## Classes

### `_RcShim` *(extends `dict`)*

Stand-in for ``plt.rcParams``: a change applies at once and stays with this answer's figures.

Tick labels are drawn after the code has finished, so a change made
only to matplotlib's settings would be lost there; the collector keeps
it and every figure is drawn and saved with it.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, collector)` | Bind to a collector. |
| `__setitem__` | `(self, key, value)` | Apply one setting, refusing names matplotlib does not know. |
| `update` | `(self, *args, **kwargs)` | Apply several settings. |
| `__getitem__` | `(self, key)` | Return the setting in force. |
| `get` | `(self, key, default=None)` | Return the setting in force, or *default*. |

### `FigureLimitError` *(extends `RuntimeError`)*

Raised when generated code asks for too many or too large figures.

### `FigureCollector`

Creates and keeps the figures one piece of generated code draws.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` | Start with no figures. |
| `set_rc` | `(self, key, value)` | Keep a style change the code made, for every figure of this answer. |
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
| `rc` | `(self, group, **kwargs)` | Change a group of style settings, like ``matplotlib.pyplot.rc('font', family='Arial')``. |
| `get_cmap` | `(self, name=None, lut=None)` | Return a colormap by name. |
| `colorbar` | `(self, mappable=None, ax=None, **kw)` | Add a colour bar to the current figure, like ``matplotlib.pyplot.colorbar``. |
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
| `_marks_groups` | `(name)` | Wrap an Axes plotting method so the axis that holds the group names is recorded. |
| `_installed_fonts` | `(candidates)` | The candidate font families that are installed, in order. |
| `label_panels` | `(axes, labels=None, size=None)` | Put panel letters (a), (b), ... at the top left of each panel. |
| `lognormal_hist` | `(ax, values, bins=None, color=None, label=None, fit=True, alpha=0.45, ` | Draw a filled log-binned histogram with its fitted log-normal curve. |
| `lab_colors` | `(samples)` | The lab's colour for each sample: influent blue, effluent orange, others from the palette. |
| `axes_title` | `(ax)` | A panel's title wherever it sits: the lab style puts titles on the left. |
| `figure_rc` | `(fig)` | The style a figure is drawn and saved with: the lab style plus any change the user asked for. |
| `style_figure` | `(fig)` | Apply the house tick style and layout so they survive redrawing outside the sandbox. |
| `_hex` | `(color)` | A colour as lower-case hex, or ``None`` when it cannot be read. |
| `_dark_swaps` | `(fig)` | Recolour a figure's paper and ink for a dark preview. |
| `render_png` | `(fig, dpi=100, dark=False)` | Draw a figure off screen and return PNG bytes. |
| `_span` | `(lo, hi)` | Decades covered between two positive limits, or 0. |
| `_is_share_axis` | `(lo, hi, label)` | Whether an axis shows a share or a cumulative fraction, which stays linear. |
| `_shares_labelled_x` | `(ax, panels)` | Whether *ax* shares its x axis with a panel that has an x label, as a twin y axis does. |
| `_shares_labelled_y` | `(ax, panels)` | Whether *ax* shares its y axis with a panel that has a y label. |
| `_categorical` | `(ax, which='x')` | Whether the tick labels of one axis are names rather than numbers. |
| `_text_overlaps` | `(fig)` | Pairs of visible titles and labels that are drawn on top of each other. |
| `describe_figure` | `(fig, index=1)` | Describe what a figure shows, for a model that cannot see it. |
