# `shared_plot_utils.py`

---

## Constants

| Name | Value |
|------|-------|
| `LABEL_MODES` | `['Symbol', 'Mass + Symbol']` |
| `DEFAULT_FONT_FAMILY` | `'Times New Roman'` |
| `DEFAULT_FONT_SIZE` | `18` |
| `DEFAULT_FONT_COLOR` | `'#000000'` |
| `FONT_FAMILIES` | `['Times New Roman', 'Arial', 'Helvetica', 'Cali...` |
| `DEFAULT_SAMPLE_COLORS` | `['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#...` |
| `DATA_TYPE_OPTIONS` | `['Counts', 'Element Mass (fg)', 'Particle Mass ...` |
| `DATA_KEY_MAPPING` | `{'Counts': 'elements', 'Element Mass (fg)': 'el...` |
| `TERNARY_DATA_TYPE_OPTIONS` | `['Counts (%)', 'Element Mass (%)', 'Particle Ma...` |
| `TERNARY_DATA_KEY_MAPPING` | `{'Counts (%)': 'elements', 'Element Mass (%)': ...` |
| `VIRIDIS_POSITIONS` | `np.array([0.0, 0.25, 0.5, 0.75, 1.0])` |
| `VIRIDIS_COLORS` | `np.array([[68, 1, 84, 255], [59, 82, 139, 255],...` |
| `SHADE_TYPES` | `['None', 'Mean +/- 1 SD', 'Mean +/- 2 SD', 'Med...` |
| `_QT_LINE` | `{'solid': _Qt.SolidLine, 'dash': _Qt.DashLine, ...` |

## Classes

### `MplDraggableCanvas` *(extends `_FigureCanvasBase`)*

FigureCanvasQTAgg with built-in axes-drag support.

• Left-click + drag on any axes **background** repositions that subplot
within the figure (like the pie-chart node).
• Middle-click anywhere resets all axes to the auto tight_layout positions.
• Right-click is forwarded to Qt as usual (context menus work unchanged).

Drop-in replacement for ``FigureCanvasQTAgg``:
just pass the same ``Figure`` object::

self.canvas = MplDraggableCanvas(self.figure)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, figure, parent = None)` | Args: |
| `reset_layout` | `(self)` | Reset all axes to auto tight_layout positions. |
| `snapshot_positions` | `(self)` | Save the current bounding box of every axes so reset_layout can |
| `_drag_press` | `(self, event)` | Args: |
| `_drag_motion` | `(self, event)` | Args: |
| `_drag_release` | `(self, event)` | Args: |

### `CustomColorBar`

Visual color bar for scatter plots using plot primitives.

Creates colored rectangles + value labels on the right side of a PlotItem.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, plot_item, colormap, vmin: float, vmax: float, config: dict, el` | Args: |
| `create` | `(self) → list` | Draw the color bar and return list of added plot items. |
| `remove` | `(self)` | Remove all color bar items from the plot. |

### `DownloadConfigDialog` *(extends `QDialog`)*

Unified download configuration dialog for all plot types.

Supports PNG (with scale or custom pixel size), SVG, PDF, and CSV output.
Used by both PyQtGraph and Matplotlib export helpers.

CSV export requires the caller to attach data via set_csv_data() before
calling exec(). The dialog hides irrelevant resolution/appearance
controls when CSV is selected.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, default_filename: str = 'figure', formats: list[str] | None = N` | Args: |
| `set_csv_data` | `(self, data, columns: dict | None = None)` | Attach data so the dialog can export CSV directly. |
| `_build_ui` | `(self)` |  |
| `_on_format_change` | `(self, fmt: str)` | Args: |
| `_on_size_toggle` | `(self)` |  |
| `show_dpi_control` | `(self, visible: bool = True)` | Call from Matplotlib callers to expose the DPI spinner. |
| `_get_csv_separator` | `(self) → str` | Returns: |
| `collect` | `(self) → dict` | Returns: |

### `FontSettingsGroup`

Reusable font-settings QGroupBox builder.

Call .build() to get the QGroupBox, then .collect() to read current values.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config: dict)` | Args: |
| `build` | `(self, on_change = None) → QGroupBox` | Args: |
| `_pick_color` | `(self)` |  |
| `collect` | `(self) → dict` | Returns: |

### `LegendGroup`

Reusable legend settings QGroupBox builder.

Call .build() to get the QGroupBox, then .collect() to read current values.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config: dict)` | Args: |
| `build` | `(self) → QGroupBox` | Returns: |
| `collect` | `(self) → dict` | Returns: |

### `ExportSettingsGroup`

Reusable export settings QGroupBox builder (background colour, format, DPI, figure size).

Call .build() to get the QGroupBox, then .collect() to read current values.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config: dict)` | Args: |
| `build` | `(self) → QGroupBox` | Returns: |
| `_pick_bg` | `(self)` |  |
| `collect` | `(self) → dict` | Returns: |

## Functions

### `format_element_label`

```python
def format_element_label(key: str, mode: str) → str
```

Format an element key for display according to label mode.

'Symbol'        → bare symbol, stripping any leading mass number
e.g. '107Ag' → 'Ag',  '107Ag, 197Au' → 'Ag, Au'
'Mass + Symbol' → keep as-is (full isotope notation)
e.g. '107Ag',          '107Ag, 197Au'

**Args:**

- `key (str): Dictionary or storage key.`
- `mode (str): Operating mode string.`

**Returns:**

- `str: Result of the operation.`

### `get_font_config`

```python
def get_font_config(config: dict) → dict
```

Extract font configuration from a config dict.

**Args:**

- `config (dict): Configuration dictionary.`

**Returns:**

- `dict: Result of the operation.`

### `make_qfont`

```python
def make_qfont(config: dict) → QFont
```

Build a QFont from a config dict.

**Args:**

- `config (dict): Configuration dictionary.`

**Returns:**

- `QFont: Result of the operation.`

### `apply_font_to_pyqtgraph`

```python
def apply_font_to_pyqtgraph(plot_item, config: dict)
```

Apply font settings to a PyQtGraph PlotItem (axes, ticks, legend).


**Args:**

- `plot_item: pg.PlotItem`
- `config: dict with font_family, font_size, font_bold, font_italic, font_color`

### `set_axis_labels`

```python
def set_axis_labels(plot_item, x_label: str, y_label: str, config: dict)
```

Set axis labels with proper font formatting on a PyQtGraph PlotItem.

**Args:**

- `plot_item (Any): The plot item.`
- `x_label (str): The x label.`
- `y_label (str): The y label.`
- `config (dict): Configuration dictionary.`

### `apply_font_to_matplotlib`

```python
def apply_font_to_matplotlib(ax, config: dict)
```

Apply font settings to a Matplotlib Axes (ticks, title, colorbar).


**Args:**

- `ax: matplotlib Axes`
- `config: dict with font keys`

### `make_font_properties`

```python
def make_font_properties(config: dict)
```

Create matplotlib FontProperties from a config dict.

Useful for mpltern ternary axes and other matplotlib text that needs
explicit FontProperties objects (not just keyword args).


**Args:**

- `config: dict with 'font_family', 'font_size', 'font_bold', 'font_italic'`


**Returns:**

- `matplotlib.font_manager.FontProperties`

### `apply_font_to_ternary`

```python
def apply_font_to_ternary(ax, config: dict)
```

Apply font settings to a mpltern ternary Axes.

Handles the three ternary axes (taxis, laxis, raxis), title, and legend.


**Args:**

- `ax: matplotlib ternary Axes (mpltern projection)`
- `config: dict with font keys`

### `_apply_font_to_colorbar`

```python
def _apply_font_to_colorbar(cbar, fc: dict)
```

Apply font config dict to a matplotlib colorbar.

**Args:**

- `cbar (Any): The cbar.`
- `fc (dict): The fc.`

### `apply_font_to_colorbar_standalone`

```python
def apply_font_to_colorbar_standalone(cbar, config: dict, label_text: str = '')
```

Apply font settings to a standalone matplotlib colorbar with an explicit label.

**Args:**

- `cbar (Any): The cbar.`
- `config (dict): Configuration dictionary.`
- `label_text (str): The label text.`

### `apply_saturation_filter`

```python
def apply_saturation_filter(element_data: pd.DataFrame, config: dict) → pd.DataFrame
```

Remove particles where *any* element exceeds the saturation threshold.


**Args:**

- `element_data: DataFrame (rows = particles, cols = elements)`
- `config: dict with 'filter_saturated' and 'saturation_threshold'`


**Returns:**

- `Filtered DataFrame.`

### `apply_zero_filter`

```python
def apply_zero_filter(x: np.ndarray, y: np.ndarray, color: np.ndarray = None) → tuple
```

Remove entries where x or y ≤ 0.


**Returns:**

- `(x, y, color) filtered arrays.  color may be None.`

**Args:**

- `x (np.ndarray): Input array or value.`
- `y (np.ndarray): Input array or value.`
- `color (np.ndarray): Colour value.`

### `apply_log_transform`

```python
def apply_log_transform(values: np.ndarray, others: list = None)
```

Apply log10 to *values*, removing non-positive entries.


**Args:**

- `values: array to log-transform.`
- `others: list of companion arrays to filter in parallel (or None).`


**Returns:**

- `(log_values, filtered_others) — filtered_others is a list or None.`

### `evaluate_equation`

```python
def evaluate_equation(equation: str, element_data: dict) → float
```

Safely evaluate a mathematical equation with element name substitution.

Supported functions: log (log10), ln, sqrt, abs, min, max, pow.


**Args:**

- `equation: expression string, e.g. "Fe/Ti"`
- `element_data: {element_name: float_value, …}`


**Returns:**

- `float result`


**Raises:**

- `ValueError on invalid expression.`

### `evaluate_equation_array`

```python
def evaluate_equation_array(equation: str, df: pd.DataFrame) → np.ndarray
```

Evaluate an equation row-by-row over a DataFrame.


**Returns:**

- `numpy array of results (NaN for failed rows).`

**Args:**

- `equation (str): The equation.`
- `df (pd.DataFrame): Pandas DataFrame.`

### `get_sample_color`

```python
def get_sample_color(sample_name: str, index: int, config: dict) → str
```

Return hex color for a sample, falling back to default palette.

**Args:**

- `sample_name (str): The sample name.`
- `index (int): Row or item index.`
- `config (dict): Configuration dictionary.`

**Returns:**

- `str: Result of the operation.`

### `get_display_name`

```python
def get_display_name(original_name: str, config: dict) → str
```

Return custom display name or original.

**Args:**

- `original_name (str): The original name.`
- `config (dict): Configuration dictionary.`

**Returns:**

- `str: Result of the operation.`

### `make_viridis_colormap`

```python
def make_viridis_colormap()
```

Create a viridis-like PyQtGraph ColorMap.

**Returns:**

- `object: Result of the operation.`

### `build_element_matrix`

```python
def build_element_matrix(particles: list, data_key: str) → pd.DataFrame | None
```

Build a particles × elements DataFrame from a list of particle dicts.


**Args:**

- `particles: list of particle dicts`
- `data_key: key inside each particle dict ('elements', 'element_mass_fg', etc.)`


**Returns:**

- `DataFrame or None.`

### `compute_correlation_matrix`

```python
def compute_correlation_matrix(df: pd.DataFrame, min_nonzero: int = 10) → pd.DataFrame
```

Compute pairwise Pearson correlation for all element columns.

Only considers pairs where both columns have ≥ min_nonzero positive values.


**Args:**

- `df: particles × elements DataFrame`
- `min_nonzero: minimum number of jointly non-zero observations`


**Returns:**

- `Correlation matrix as DataFrame (NaN where insufficient data).`

### `find_top_correlations`

```python
def find_top_correlations(df: pd.DataFrame, n_top: int = 10, min_nonzero: int = 10) → list[dict]
```

Find the top-N strongest correlations (by |r|) among all element pairs.


**Args:**

- `df: particles × elements DataFrame`
- `n_top: number of top correlations to return`
- `min_nonzero: minimum jointly non-zero observations`


**Returns:**

- `List of dicts: [{'x': elem1, 'y': elem2, 'r': corr_value, 'n': count}, …]`
- `sorted by descending |r|.`

### `create_single_color_scatter`

```python
def create_single_color_scatter(plot_item, x, y, config, color = '#3B82F6')
```

Add a uniform-color scatter to plot_item. Returns the ScatterPlotItem.

**Args:**

- `plot_item (Any): The plot item.`
- `x (Any): Input array or value.`
- `y (Any): Input array or value.`
- `config (Any): Configuration dictionary.`
- `color (Any): Colour value.`

### `create_color_mapped_scatter`

```python
def create_color_mapped_scatter(plot_item, x, y, color_values, config, base_color = '#3B82F6', element_name = '', active_color_bars = None)
```

Add a color-mapped scatter to plot_item.

Returns the ScatterPlotItem.
If active_color_bars (list) is provided, appends the new CustomColorBar to it.

**Args:**

- `plot_item (Any): The plot item.`
- `x (Any): Input array or value.`
- `y (Any): Input array or value.`
- `color_values (Any): The color values.`
- `config (Any): Configuration dictionary.`
- `base_color (Any): The base color.`
- `element_name (Any): The element name.`
- `active_color_bars (Any): The active color bars.`

### `add_trend_line`

```python
def add_trend_line(plot_item, x, y, color)
```

Add a dashed linear regression line.

**Args:**

- `plot_item (Any): The plot item.`
- `x (Any): Input array or value.`
- `y (Any): Input array or value.`
- `color (Any): Colour value.`

### `add_correlation_text`

```python
def add_correlation_text(plot_item, x, y, config)
```

Add Pearson r text in the top-left corner of the plot.

**Args:**

- `plot_item (Any): The plot item.`
- `x (Any): Input array or value.`
- `y (Any): Input array or value.`
- `config (Any): Configuration dictionary.`

### `_prepare_csv_dataframe`

```python
def _prepare_csv_dataframe(data, columns: dict | None = None) → pd.DataFrame
```

Normalise various data shapes into a single DataFrame for CSV export.

Accepted input types:
- pd.DataFrame       → returned as-is (with optional column rename)
- dict of DataFrames → concatenated with a 'Sample' column
- list[dict]         → flattened particle dicts
- dict with arrays   → simple column frame (e.g. {'x': [...], 'y': [...]})

**Args:**

- `data (Any): Input data.`
- `columns (dict | None): The columns.`

**Returns:**

- `pd.DataFrame: Result of the operation.`

### `export_csv`

```python
def export_csv(data, parent, default_name: str = 'data', columns: dict | None = None, separator: str = ',', include_index: bool = False, precision: int = 6)
```

Export data to CSV with a file-save dialog.


**Args:**

- `data:          DataFrame, dict of DataFrames, list of particle dicts, etc.`
- `parent:        QWidget parent for dialogs`
- `default_name:  suggested filename (no extension)`
- `columns:       optional column rename mapping`
- `separator:     CSV delimiter`
- `include_index: whether to write the DataFrame index`
- `precision:     float decimal places`

### `export_plot_data_csv`

```python
def export_plot_data_csv(x_data, y_data, parent, x_label: str = 'X', y_label: str = 'Y', color_data = None, color_label: str = '', sample_labels = None, default_name: str = 'plot_data', separator: str = ',', include_index: bool = False, precision: int = 6)
```

Export scatter / correlation plot arrays to CSV.

Handles single-sample and multi-sample data.


**Args:**

- `x_data:        np.ndarray  OR  list[np.ndarray]`
- `y_data:        np.ndarray  OR  list[np.ndarray]`
- `color_data:    optional np.ndarray or list[np.ndarray]`
- `sample_labels: list of sample name strings`

### `export_element_matrix_csv`

```python
def export_element_matrix_csv(df: pd.DataFrame, parent, default_name: str = 'particle_data', separator: str = ',', include_index: bool = False, precision: int = 6)
```

Export a particles × elements DataFrame directly to CSV.

**Args:**

- `df (pd.DataFrame): Pandas DataFrame.`
- `parent (Any): Parent widget or object.`
- `default_name (str): The default name.`
- `separator (str): The separator.`
- `include_index (bool): The include index.`
- `precision (int): The precision.`

### `download_pyqtgraph_figure`

```python
def download_pyqtgraph_figure(plot_widget, parent, default_name: str = 'figure', csv_data = None, csv_columns: dict | None = None)
```

Export a PyQtGraph GraphicsLayoutWidget to PNG, SVG, PDF, or CSV.

The FULL scene is captured (all subplots), not just a single PlotItem.


**Args:**

- `plot_widget:  pg.GraphicsLayoutWidget`
- `parent:       QWidget parent for dialogs`
- `default_name: suggested filename stem (no extension)`
- `csv_data:     data to export when CSV is chosen (DataFrame, dict, etc.)`
- `csv_columns:  optional column rename mapping for CSV`

### `download_matplotlib_figure`

```python
def download_matplotlib_figure(figure, parent, default_name: str = 'figure', csv_data = None, csv_columns: dict | None = None)
```

Export a Matplotlib Figure to PNG, SVG, PDF, or CSV.


**Args:**

- `figure:       matplotlib.figure.Figure`
- `parent:       QWidget parent for dialogs`
- `default_name: suggested filename stem (no extension)`
- `csv_data:     data to export when CSV is chosen`
- `csv_columns:  optional column rename mapping for CSV`

### `build_axis_labels`

```python
def build_axis_labels(config: dict, mode: str = 'simple') → tuple[str, str]
```

Build x/y axis label strings from config.


**Returns:**

- `(x_label, y_label)`

**Args:**

- `config (dict): Configuration dictionary.`
- `mode (str): Operating mode string.`

### `filter_outliers_percentile`

```python
def filter_outliers_percentile(values: np.ndarray, pct: float = 99.0) → np.ndarray
```

Remove values outside [100-pct, pct] percentile range.


**Args:**

- `values: 1-D array of numeric values.`
- `pct:    Upper keep-percentile (e.g. 99 keeps the central 98%).`


**Returns:**

- `Filtered array (may be shorter than input).`

### `apply_outlier_filter`

```python
def apply_outlier_filter(values: np.ndarray, cfg: dict) → np.ndarray
```

Apply percentile outlier filter when cfg['filter_outliers'] is True.

**Args:**

- `values (np.ndarray): Array or sequence of values.`
- `cfg (dict): The cfg.`

**Returns:**

- `np.ndarray: Result of the operation.`

### `_apply_box`

```python
def _apply_box(plot_item, cfg: dict)
```

Show or hide the top + right axes (figure box frame).

**Args:**

- `plot_item (Any): The plot item.`
- `cfg (dict): The cfg.`

### `_add_shaded_region_hist`

```python
def _add_shaded_region_hist(plot_item, values: np.ndarray, cfg: dict)
```

Vertical shaded statistical band for histogram-type plots.

``values`` must be in plot-space already (log10 if log_x is on).
Applies to every subplot since it is called per-panel.

**Args:**

- `plot_item (Any): The plot item.`
- `values (np.ndarray): Array or sequence of values.`
- `cfg (dict): The cfg.`

**Returns:**

- `object: Result of the operation.`

### `_add_hband`

```python
def _add_hband(plot_item, lo: float, hi: float, color: str = '#534AB7', alpha: float = 0.18, label: str = '')
```

Horizontal shaded band for scatter / box plots (Y-axis range).

**Args:**

- `plot_item (Any): The plot item.`
- `lo (float): The lo.`
- `hi (float): The hi.`
- `color (str): Colour value.`
- `alpha (float): The alpha.`
- `label (str): Label text.`

### `_add_stat_lines_hist`

```python
def _add_stat_lines_hist(plot_item, values: np.ndarray, cfg: dict)
```

Vertical stat lines (median / mean / mode) for histogram plots.

``values`` must already be in plot-space.
Colors, styles, widths all read from cfg.

**Args:**

- `plot_item (Any): The plot item.`
- `values (np.ndarray): Array or sequence of values.`
- `cfg (dict): The cfg.`

### `_add_det_limit_v`

```python
def _add_det_limit_v(plot_item, cfg: dict)
```

Vertical detection limit line (for histogram / molar ratio plots).

**Args:**

- `plot_item (Any): The plot item.`
- `cfg (dict): The cfg.`

### `_add_det_limit_h`

```python
def _add_det_limit_h(plot_item, cfg: dict)
```

Horizontal detection limit line (for box plot / scatter plots).

**Args:**

- `plot_item (Any): The plot item.`
- `cfg (dict): The cfg.`

### `_add_ref_line_vertical`

```python
def _add_ref_line_vertical(plot_item, cfg: dict, num_label: str = 'X', den_label: str = 'Y')
```

Customisable vertical reference line (e.g. ratio = 1).

Reads: show_ref_line, ref_line_value, ref_line_label,
ref_line_color, ref_line_style, ref_line_width, log_x.

**Args:**

- `plot_item (Any): The plot item.`
- `cfg (dict): The cfg.`
- `num_label (str): The num label.`
- `den_label (str): The den label.`

### `build_quick_toggles_menu`

```python
def build_quick_toggles_menu(parent_menu, cfg: dict, display_toggles: list, stat_toggles: list | None = None, shade_types: list | None = None)
```

Build the uniform Quick Toggles submenu.


**Args:**

- `parent_menu:     The QMenu to add the Quick Toggles submenu to.`
- `cfg:             Current node config dict.`
- `display_toggles: list of (cfg_key, label, default) for top section.`
- `stat_toggles:    list of (cfg_key, label) for stat lines section.`
- `shade_types:     list of shade type strings; if given, adds shade submenu.`


**Returns:**

- `The QMenu for Quick Toggles (so caller can connect signals).`
