# `shared_plot_utils.py`

---

## Constants

| Name | Value |
|------|-------|
| `LABEL_MODES` | `['Symbol', 'Mass + Symbol', 'Atomic Notation']` |
| `DEFAULT_FONT_FAMILY` | `'Times New Roman'` |
| `DEFAULT_FONT_SIZE` | `18` |
| `DEFAULT_FONT_COLOR` | `'#000000'` |
| `FONT_FAMILIES` | `['Times New Roman', 'Arial', 'Helvetica', 'Calibri', 'Ver…` |
| `DEFAULT_SAMPLE_COLORS` | `['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '…` |
| `DATA_TYPE_OPTIONS` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `DATA_KEY_MAPPING` | `{'Counts': 'elements', 'Element Mass (fg)': 'element_mass…` |
| `TERNARY_DATA_TYPE_OPTIONS` | `['Counts (%)', 'Element Mass (%)', 'Particle Mass (%)', '…` |
| `TERNARY_DATA_KEY_MAPPING` | `{'Counts (%)': 'elements', 'Element Mass (%)': 'element_m…` |
| `VIRIDIS_POSITIONS` | `np.array([0.0, 0.25, 0.5, 0.75, 1.0])` |
| `VIRIDIS_COLORS` | `np.array([[68, 1, 84, 255], [59, 82, 139, 255], [33, 145,…` |
| `SHADE_TYPES` | `['None', 'Mean +/- 1 SD', 'Mean +/- 2 SD', 'Median +/- IQ…` |
| `_QT_LINE` | `{'solid': _Qt.SolidLine, 'dash': _Qt.DashLine, 'dot': _Qt…` |

## Classes

### `_HideOnCloseFilter` *(extends `QObject`)*

Event filter: closing a figure window hides it instead of destroying it.

Installed on a figure dialog so its window close button keeps the window
(and all its state) alive. Set ``dialog._force_close = True`` to allow a
real close/teardown (e.g. when the owning node is deleted).

| Method | Signature | Description |
|--------|-----------|-------------|
| `eventFilter` | `(self, obj, event)` |  |

### `_FigureView`

One figure of a node: its own ``config``, shared underlying data.

Passed to a figure dialog in place of the node so several figures of the
same node can each keep independent settings. ``config`` is private to the
view; ``extract_plot_data`` runs the node's extraction with this view's
config swapped in; everything else delegates to the real node.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, dialog_class, parent_window, config=None)` |  |
| `__setattr__` | `(self, name, value)` | Keep config/dialog/thumbnail on the view; forward any other attribute |
| `extract_plot_data` | `(self, *args, **kwargs)` | Run the node's extraction with this view's config swapped in. |
| `new_figure` | `(self)` | Spawn another independent figure for the same node. |
| `__getattr__` | `(self, name)` |  |

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
| `__init__` | `(self, figure, parent=None)` |  |
| `set_mouse_mode` | `(self, mode: str)` | Set the transient mouse interaction mode for this canvas. |
| `mouse_mode` | `(self) → str` | Return the current transient mouse interaction mode. |
| `enable_view_limit_tracking` | `(self, enabled: bool)` | Opt this canvas into baseline axis-limit snapshot/restore support. |
| `snapshot_view_limits` | `(self)` | Capture current axis limits for later restoration. |
| `restore_view_limits` | `(self)` | Restore the last snapshotted axis limits when tracking is enabled. |
| `reset_layout` | `(self)` | Reset all axes to auto tight_layout positions. |
| `snapshot_positions` | `(self)` | Save the current bounding box of every axes so reset_layout can |
| `showEvent` | `(self, event)` | Guard matplotlib's installEventFilter call against QWidgetItem parents. |
| `_drag_press` | `(self, event)` | Args: |
| `_drag_motion` | `(self, event)` | Args: |
| `_drag_release` | `(self, event)` | Args: |
| `_zoom_press` | `(self, event)` | Start a rectangle zoom drag when zoom mode is active. |
| `_zoom_motion` | `(self, event)` | Update the active rectangle zoom overlay while dragging. |
| `_zoom_release` | `(self, event)` | Apply or cancel a rectangle zoom selection on mouse release. |
| `_clear_zoom_state` | `(self, draw: bool=True)` | Remove any temporary zoom overlay and clear in-progress state. |

### `HtmlAxisItem` *(extends `pg.AxisItem`)*

AxisItem that renders tick labels as HTML using QTextDocument.

Drop-in replacement for the default pg.AxisItem when tick labels
contain HTML markup — e.g. atomic notation <sup>56</sup>Fe.
Plain-text labels fall through to the standard QPainter path so
there is no cost when Atomic Notation is not active.

Usage::
    pi = layout.addPlot(axisItems={'bottom': HtmlAxisItem('bottom')})

| Method | Signature | Description |
|--------|-----------|-------------|
| `generateDrawSpecs` | `(self, p)` | Generate draw specs while recording the rendered width of HTML ticks. |
| `_updateMaxTextSize` | `(self, x)` | Reserve axis space from the rendered HTML width when available. |
| `drawPicture` | `(self, p, axisSpec, tickSpecs, textSpecs)` |  |

### `Renderer` *(extends `enum.Enum`)*

Target rendering engine for element label formatting.

MATHTEXT  — matplotlib axes, titles, colorbars.
            Atomic Notation uses mathtext: $^{107}\mathrm{Ag}$
            Normal digits raised by the math engine — same font throughout.

HTML      — pyqtgraph axes, legends, tick labels.
            Atomic Notation uses Qt HTML: <sup>107</sup>Ag
            Normal digits raised by Qt — same font throughout.

### `CustomColorBar`

Visual color bar for scatter plots using plot primitives.

Creates colored rectangles + value labels on the right side of a PlotItem.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, plot_item, colormap, vmin: float, vmax: float, config: dict, el` |  |
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
| `__init__` | `(self, default_filename: str='figure', formats: list[str] \| None=None,` |  |
| `set_csv_data` | `(self, data, columns: dict \| None=None)` | Attach data so the dialog can export CSV directly. |
| `_build_ui` | `(self)` |  |
| `_on_format_change` | `(self, fmt: str)` |  |
| `_on_size_toggle` | `(self)` |  |
| `show_dpi_control` | `(self, visible: bool=True)` | Call from Matplotlib callers to expose the DPI spinner. |
| `_get_csv_separator` | `(self) → str` |  |
| `collect` | `(self) → dict` |  |

### `FontSettingsGroup`

Reusable font-settings QGroupBox builder.

Call .build() to get the QGroupBox, then .collect() to read current values.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config: dict)` |  |
| `build` | `(self, on_change=None) → QGroupBox` |  |
| `_pick_color` | `(self)` |  |
| `collect` | `(self) → dict` |  |

### `LegendGroup`

Reusable legend settings QGroupBox builder.

Call .build() to get the QGroupBox, then .collect() to read current values.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config: dict)` |  |
| `build` | `(self) → QGroupBox` |  |
| `collect` | `(self) → dict` |  |

### `ExportSettingsGroup`

Reusable export settings QGroupBox builder (background colour, format, DPI, figure size).

Call .build() to get the QGroupBox, then .collect() to read current values.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config: dict)` |  |
| `build` | `(self) → QGroupBox` |  |
| `_pick_bg` | `(self)` |  |
| `collect` | `(self) → dict` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `compute_bin_edges_fixed_geo` | `(values, bin_width, log_x=False, bin_mode='geometric')` | Compute bin edges for a single array of (possibly log-transformed) values. |
| `compute_global_bin_edges_fixed_geo` | `(all_values_list, bin_width, log_x=False, bin_mode='geometric')` | Compute shared bin edges from multiple value arrays. |
| `compute_bin_edges_width_geo` | `(values, bin_width, log_x=True, bin_mode='geometric')` | Compute bin edges anchored to clean grid boundaries. |
| `compute_global_bin_edges_width_geo` | `(all_values_list, bin_width, log_x=True, bin_mode='geometric')` | Compute shared bin edges from multiple per-sample arrays. |
| `_deep_copy_config` | `(cfg)` | Return a fully independent copy of a config dict. |
| `_figure_alive` | `(dlg)` | Return True if the dialog's underlying C++ object still exists. |
| `capture_figure_thumbnail` | `(node, dlg)` | Grab a small snapshot of the figure's plot for the node hover preview. |
| `_connect_thumb_refresh` | `(node, dlg)` | Re-capture the thumbnail (debounced) whenever the figure changes. |
| `show_persistent_figure` | `(node, factory, _parent_window=None)` | Open a node's figure, reusing one window and hiding (not killing) it. |
| `prime_figure_thumbnail` | `(node, factory)` | Build a figure off-screen once so its hover thumbnail exists before the |
| `_finish_prime` | `(node, dlg)` | Capture the primed thumbnail, then keep the window hidden + ready. |
| `_connect_view_thumb_refresh` | `(view, dlg)` |  |
| `capture_view_thumbnail` | `(view)` | Grab a thumbnail for one figure view (and mirror to the node). |
| `_open_view` | `(view)` | Show a figure view's window, creating it on first open. |
| `_add_node_figure` | `(node, dialog_class, parent_window, base_config=None)` | Create a new figure view for the node, append it, and open it. |
| `open_node_figures` | `(node, dialog_class, parent_window, always_new=False)` | Open a node figure. Double-click passes ``always_new=True`` so each |
| `_encode_pixmap` | `(pm)` | Encode a QPixmap to a base64 PNG string for saving (or None). |
| `_decode_pixmap` | `(s)` | Decode a base64 PNG string from a saved project back to a QPixmap (or None). |
| `serialize_node_figures` | `(node)` | Return a pickle-safe list describing a node's figures for project save. |
| `rebuild_node_figures` | `(node, dialog_class, parent_window, saved)` | Recreate a node's figures from saved data, without opening windows. |
| `focus_node_figure` | `(view)` | Bring a figure (picked from the hover fan) to the front. |
| `close_node_figure` | `(view)` | Close/remove a figure picked from the hover fan. |
| `pick_color_hex` | `(initial_color: str, owner=None, title: str='Select Color') → str \| No` | Open a safely parented color dialog and return a validated hex color. |
| `parse_element_label` | `(label: str) → tuple[str, str \| None]` | Parse element/isotope text into (symbol_like, mass_or_none). |
| `format_element_label` | `(key: str, mode: str, renderer: Renderer=Renderer.HTML, config: dict \|` | Format an element key for display according to label mode and renderer. |
| `format_combination_label` | `(label: str, mode: str, renderer: Renderer=Renderer.HTML, config: dict` | Format combo labels while preserving separators like ',' and '+'. |
| `format_label_text_tokens` | `(text: str, mode: str, renderer: Renderer=Renderer.HTML, config: dict ` | Format isotope-like tokens inside a free-form label string. |
| `get_font_config` | `(config: dict \| None) → dict` | Extract normalized font configuration from config or defaults. |
| `make_qfont` | `(config: dict \| None) → QFont` | Build a ``QFont`` from config values or shared defaults. |
| `_resolve_text_style_fields` | `(config: dict \| None=None, *, family=None, size=None, bold=None, itali` | Resolve explicit text-style fields from config values and overrides. |
| `build_labelitem_style_kwargs` | `(config: dict \| None=None, *, family=None, size=None, bold=None, itali` | Build explicit ``LabelItem.setText`` style kwargs for PyQtGraph. |
| `build_axis_label_style_kwargs` | `(config: dict \| None=None, *, family=None, size=None, bold=None, itali` | Build explicit ``AxisItem.setLabel`` style kwargs for PyQtGraph. |
| `apply_plot_title_style` | `(plot_item, title_text: str, config: dict \| None=None, *, family=None,` | Apply explicit title styling to a ``pg.PlotItem`` title label. |
| `apply_axis_label_style` | `(plot_item, axis_name: str, text: str, units: str \| None=None, config:` | Apply explicit styling to one PyQtGraph axis label. |
| `apply_legend_label_style` | `(legend, config: dict \| None=None, *, family=None, size=None, bold=Non` | Apply explicit styling to every label inside a PyQtGraph legend. |
| `apply_plot_item_text_styling` | `(plot_item, *, family: str, title_size: int, axis_size: int, legend_si` | Apply explicit text styling to title, axes, ticks, and legend. |
| `apply_font_to_pyqtgraph` | `(plot_item, config: dict)` | Apply config-driven text styling to a PyQtGraph plot item. |
| `copy_figure_to_clipboard` | `(widget)` | Copy the full rendered figure to the system clipboard as an image. |
| `set_axis_labels` | `(plot_item, x_label: str, y_label: str, config: dict)` | Set axis labels with proper font formatting on a PyQtGraph PlotItem. |
| `_configure_mathtext_font` | `(family: str) → None` | Sync matplotlib's mathtext roman font to the user's selected font. |
| `apply_font_to_matplotlib` | `(ax, config: dict)` | Apply font settings to a Matplotlib Axes (ticks, title, colorbar). |
| `make_font_properties` | `(config: dict)` | Create matplotlib FontProperties from a config dict. |
| `apply_font_to_ternary` | `(ax, config: dict)` | Apply font settings to a mpltern ternary Axes. |
| `_apply_font_to_colorbar` | `(cbar, fc: dict)` | Apply font config dict to a matplotlib colorbar. |
| `apply_font_to_colorbar_standalone` | `(cbar, config: dict, label_text: str='')` | Apply font settings to a standalone matplotlib colorbar with an explicit label. |
| `apply_saturation_filter` | `(element_data: pd.DataFrame, config: dict) → pd.DataFrame` | Remove particles where *any* element exceeds the saturation threshold. |
| `apply_zero_filter` | `(x: np.ndarray, y: np.ndarray, color: np.ndarray=None) → tuple` | Remove entries where x or y ≤ 0. |
| `apply_log_transform` | `(values: np.ndarray, others: list=None)` | Apply log10 to *values*, removing non-positive entries. |
| `evaluate_equation` | `(equation: str, element_data: dict) → float` | Safely evaluate a mathematical equation with element name substitution. |
| `evaluate_equation_array` | `(equation: str, df: pd.DataFrame) → np.ndarray` | Evaluate an equation row-by-row over a DataFrame. |
| `get_sample_color` | `(sample_name: str, index: int, config: dict) → str` | Return hex color for a sample, falling back to default palette. |
| `get_display_name` | `(original_name: str, config: dict) → str` | Return custom display name or original. |
| `make_viridis_colormap` | `()` | Create a viridis-like PyQtGraph ColorMap. |
| `conc_meta_available` | `(input_data) → bool` | Report whether any sample in the input carries a usable transport rate. |
| `per_ml_factor` | `(input_data, sample_name) → float` | Return the multiplier that converts a particle count to particles per mL. |
| `single_sample_name` | `(input_data)` | Return the sample name for single-sample input data. |
| `count_to_per_ml` | `(count, input_data, sample_name) → float` | Convert a particle count to particles per mL for a given sample. |
| `per_ml_active` | `(cfg, input_data) → bool` | Report whether the particles-per-mL unit should be used for drawing. |
| `format_per_ml` | `(value, renderer: Renderer=Renderer.HTML, config: dict \| None=None) → ` | Format a particles-per-mL value as a mantissa times ten-to-a-power. |
| `apply_sci_y_axis` | `(plot_item, config: dict \| None=None)` | Render the left axis tick labels of a pyqtgraph plot as ten-to-a-power. |
| `per_ml_unit_label` | `(per_ml: bool, base: str='Particle Count') → str` | Return the appropriate y-axis label for the active unit. |
| `build_element_matrix` | `(particles: list, data_key: str) → pd.DataFrame \| None` | Build a particles × elements DataFrame from a list of particle dicts. |
| `compute_correlation_matrix` | `(df: pd.DataFrame, min_nonzero: int=10) → pd.DataFrame` | Compute pairwise Pearson correlation for all element columns. |
| `find_top_correlations` | `(df: pd.DataFrame, n_top: int=10, min_nonzero: int=10) → list[dict]` | Find the top-N strongest correlations (by \|r\|) among all element pairs. |
| `create_single_color_scatter` | `(plot_item, x, y, config, color='#3B82F6')` | Add a uniform-color scatter to plot_item. Returns the ScatterPlotItem. |
| `create_color_mapped_scatter` | `(plot_item, x, y, color_values, config, base_color='#3B82F6', element_` | Add a color-mapped scatter to plot_item. |
| `add_trend_line` | `(plot_item, x, y, color)` | Add a dashed linear regression line. |
| `add_correlation_text` | `(plot_item, x, y, config)` | Add Pearson r text in the top-left corner of the plot. |
| `_prepare_csv_dataframe` | `(data, columns: dict \| None=None) → pd.DataFrame` | Normalise various data shapes into a single DataFrame for CSV export. |
| `export_csv` | `(data, parent, default_name: str='data', columns: dict \| None=None, se` | Export data to CSV with a file-save dialog. |
| `export_plot_data_csv` | `(x_data, y_data, parent, x_label: str='X', y_label: str='Y', color_dat` | Export scatter / correlation plot arrays to CSV. |
| `export_element_matrix_csv` | `(df: pd.DataFrame, parent, default_name: str='particle_data', separato` | Export a particles × elements DataFrame directly to CSV. |
| `download_pyqtgraph_figure` | `(plot_widget, parent, default_name: str='figure', csv_data=None, csv_c` | Export a PyQtGraph graphics target to PNG, SVG, PDF, or CSV. |
| `download_matplotlib_figure` | `(figure, parent, default_name: str='figure', csv_data=None, csv_column` | Export a Matplotlib Figure to PNG, SVG, PDF, or CSV. |
| `build_axis_labels` | `(config: dict, mode: str='simple') → tuple[str, str]` | Build x/y axis label strings from config. |
| `filter_outliers_percentile` | `(values: np.ndarray, pct: float=99.0) → np.ndarray` | Remove values outside [100-pct, pct] percentile range. |
| `apply_outlier_filter` | `(values: np.ndarray, cfg: dict) → np.ndarray` | Apply percentile outlier filter when cfg['filter_outliers'] is True. |
| `_apply_box` | `(plot_item, cfg: dict)` | Show or hide the top + right axes (figure box frame). |
| `_add_shaded_region_hist` | `(plot_item, values: np.ndarray, cfg: dict)` | Vertical shaded statistical band for histogram-type plots. |
| `_add_hband` | `(plot_item, lo: float, hi: float, color: str='#534AB7', alpha: float=0` | Horizontal shaded band for scatter / box plots (Y-axis range). |
| `_add_stat_lines_hist` | `(plot_item, values: np.ndarray, cfg: dict)` | Vertical stat lines (median / mean / mode) for histogram plots. |
| `_add_det_limit_v` | `(plot_item, cfg: dict)` | Vertical detection limit line (for histogram / molar ratio plots). |
| `_add_det_limit_h` | `(plot_item, cfg: dict)` | Horizontal detection limit line (for box plot / scatter plots). |
| `_add_ref_line_vertical` | `(plot_item, cfg: dict, num_label: str='X', den_label: str='Y')` | Customisable vertical reference line (e.g. ratio = 1). |
| `build_quick_toggles_menu` | `(parent_menu, cfg: dict, display_toggles: list, stat_toggles: list \| N` | Build the uniform Quick Toggles submenu. |
