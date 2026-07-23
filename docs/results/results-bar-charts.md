# `results_bar_charts.py`

---

## Constants

| Name | Value |
|------|-------|
| `_AXIS_NAMES` | `('left', 'bottom', 'right', 'top')` |
| `HIST_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `SUMMABLE_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `HIST_DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'element_mass…` |
| `HIST_LABEL_MAP` | `{'Counts': 'Intensity (counts)', 'Element Mass (fg)': 'El…` |
| `HIST_DISPLAY_MODES` | `['Overlaid (Different Colors)', 'Side by Side Subplots', …` |
| `BAR_DISPLAY_MODES` | `['Grouped Bars (Side by Side)', 'By Sample (Element Color…` |
| `SORT_OPTIONS` | `['No Sorting', 'Ascending', 'Descending', 'Alphabetical']` |
| `CURVE_TYPES` | `['Log-Normal Fit', 'Normal Fit']` |
| `DEFAULT_ELEMENT_COLORS` | `['#663399', '#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '…` |
| `_BROKEN_AXIS_WIDTH` | `70` |
| `_BROKEN_SEG_PAD` | `0.02` |

## Classes

### `_BreakMarkRow` *(extends `pg.GraphicsWidget`)*

Thin strip between two stacked broken-axis panels.

Draws the classic diagonal double-slash break marks centered on the
left and right axis spines of the panels above and below it.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, ref_plot, height=16)` | Store the reference panel used to locate the axis spines. |
| `boundingRect` | `(self)` | Return the full-width bounding rectangle of the strip. |
| `paint` | `(self, painter, option, widget=None)` | Paint two diagonal slash pairs aligned with the plot spines. |

### `BrokenYAxisEditor` *(extends `QGroupBox`)*

Settings-dialog group box for configuring broken Y-axis cuts.

Purely value-driven: an enable checkbox plus one row per cut, each row
being "cut from [low] to [high]" spin boxes with a remove button, and
an "+ Add cut" button for multiple cuts. The whole group is disabled
while log Y is checked because the two features do not combine.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, log_y_checkbox=None, parent=None)` | Build the editor from existing config values. |
| `guard_apply` | `(self, parent_widget)` | Block Apply/Done when Log Y-axis and the broken Y-axis cut are both on. |
| `_sync_log_state` | `(self, *_args)` | Enable or disable every control based on the log-Y checkbox. |
| `_add_row` | `(self, lo=None, hi=None)` | Append one "cut from LOW to HIGH" editor row. |
| `_remove_row` | `(self, entry)` | Remove one cut row, always keeping at least one row present. |
| `collect_into` | `(self, out)` | Write ``broken_y_enabled`` and ``broken_y_cuts`` into a config. |

### `_PlotWidgetAdapter`

Wraps a (GraphicsLayoutWidget, PlotItem) pair so that all editor
dialogs from custom_plot_widget.py treat it like a pg.PlotWidget.

``custom_axis_labels`` and ``persistent_dialog_settings`` are stored
directly on the PlotItem (prefixed with '_') so they survive across
multiple double-click events even though the adapter is re-created
each time.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, glw, plot_item)` |  |
| `custom_axis_labels` | `(self)` |  |
| `custom_axis_labels` | `(self, val)` |  |
| `persistent_dialog_settings` | `(self)` |  |
| `persistent_dialog_settings` | `(self, val)` |  |
| `getPlotItem` | `(self)` |  |
| `backgroundBrush` | `(self)` |  |
| `setBackground` | `(self, color)` |  |
| `repaint` | `(self)` |  |
| `notify_bar_group_color_changed` | `(self, items, color_hex)` | Forward shared bar-color edits to a plot-specific sync callback. |
| `parent` | `(self)` |  |

### `EnhancedGraphicsLayoutWidget` *(extends `pg.GraphicsLayoutWidget`)*

GraphicsLayoutWidget with double-click inline editing.

Double-clicking on any subplot opens the same editor dialogs that
EnhancedPlotWidget uses in the main signal window:
  • Title label      → TitleEditorDialog
  • Left axis        → AxisLabelEditorDialog('left')
  • Bottom axis      → AxisLabelEditorDialog('bottom')
  • Legend           → LegendEditorDialog
  • Background area  → BackgroundEditorDialog

Works correctly across all multi-subplot display modes.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `_plot_item_at` | `(self, scene_pos)` | Return the PlotItem whose bounding rect contains scene_pos. |
| `_adapter_for` | `(self, plot_item)` | Build an adapter for plot_item, syncing legend from it. |
| `_closest_scatter` | `(self, pi, scene_pos, threshold_px=20)` |  |
| `_closest_curve` | `(self, pi, scene_pos, threshold_px=15)` |  |
| `_bar_at` | `(self, pi, scene_pos)` | Return the BarGraphItem the cursor is inside (data-space test). |
| `mouseDoubleClickEvent` | `(self, event)` | Route double-click editing to the most specific plot item hit. |
| `_owner_node` | `(self)` | Resolve the owning display dialog's node by walking up the parents. |
| `_persist_element_color` | `(self, item, qcolor)` | Write an edited colour into the owning node's config and redraw. |
| `_current_identity_color` | `(self, item, fallback='#3B82F6')` | Current colour for a tagged item, read from the owning node config. |
| `_tagged_color_item_at` | `(self, pi, scene_pos)` | Topmost non-bar graphics item at ``scene_pos`` tagged with a colour |
| `_persist_inline_edit` | `(self, adapter)` | Save a double-click axis edit into the ONE shared config. |
| `_write_global_font` | `(node, font_info)` | Copy an editor's font choice into the shared global ``font_*`` config. |
| `reapply_inline_overrides` | `(self)` | Reapply persisted inline axis-label TEXT after a redraw (single-panel). |

### `_ClickableLegendSwatch` *(extends `pg.BarGraphItem`)*

Legend swatch item that forwards click events to a visibility callback.

The swatch stores a raw histogram element/isotope key and emits that key
through ``toggle_callback`` when clicked. This keeps histogram visibility
state keyed by raw identifiers instead of formatted legend labels.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, *args, raw_key=None, toggle_callback=None, **kwargs)` |  |
| `mouseClickEvent` | `(self, ev)` | Toggle the associated raw-key visibility on left-click. |

### `ElementGroupEditor` *(extends `QGroupBox`)*

Widget for defining element groups (sum per particle).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, groups, available_elements, parent=None)` |  |
| `_build_ui` | `(self)` |  |
| `_refresh_group_list` | `(self)` |  |
| `_on_group_selected` | `(self, row)` |  |
| `_add_group` | `(self)` |  |
| `_remove_group` | `(self)` |  |
| `_on_name_changed` | `(self, text)` |  |
| `_on_elements_changed` | `(self)` |  |
| `_pick_color` | `(self)` |  |
| `collect` | `(self)` | Return list of valid groups (with ≥1 element and a name). |

### `HistogramSettingsDialog` *(extends `QDialog`)*

Full settings dialog for histogram node.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config, is_multi, sample_names, parent=None, available_elements` | Preserved behavior: |
| `_build_ui` | `(self)` |  |
| `_try_apply` | `(self)` |  |
| `_try_done` | `(self)` |  |
| `_pick_curve_color` | `(self)` |  |
| `_pick_shade_color_hist` | `(self)` |  |
| `collect` | `(self) → dict` | Preserved behavior: |

### `HistogramFormatSettingsDialog` *(extends `QDialog`)*

Global visual-format settings dialog for Histogram plots.

This dialog is intentionally config-driven and plot-global: it collects
only presentation settings (fonts, labels, visual toggles, and element
colors) and relies on Histogram redraw to apply those settings uniformly
across all subplot PlotItems.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config, is_multi, sample_names, parent=None, available_elements` | Initialize the histogram format-only settings dialog. |
| `_build_ui` | `(self)` | Build visual-only controls used by the histogram format route. |
| `_refresh_font_color_btn` | `(self)` | Refresh the font-color swatch preview. |
| `_pick_font_color` | `(self)` | Select and store a global histogram font color. |
| `_pick_element_color` | `(self, element)` | Select an element color used globally across histogram subplots. |
| `collect` | `(self) → dict` | Collect only histogram visual-format settings. |

### `HistogramDisplayDialog` *(extends `QDialog`)*

Full-figure histogram dialog with PyQtGraph and right-click menu.

This dialog owns parent-level histogram visibility state for legend-click
hiding/showing of both raw isotope/element keys and raw sample keys.
Visibility state is UI-local and render-only; scientific calculations and
extracted data remain unchanged.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, histogram_node, parent_window=None)` |  |
| `_build_ui` | `(self)` | Build histogram canvas, stats footer, and standardized bottom buttons. |
| `_ctx_menu` | `(self, pos)` | Show lightweight histogram quick actions. |
| `_toggle_histogram_element_visibility` | `(self, raw_element_key: str)` | Toggle parent histogram element visibility by raw isotope key. |
| `_show_all_histogram_elements` | `(self)` | Clear all legend-hidden isotopes/elements and redraw. |
| `_toggle_histogram_sample_visibility` | `(self, raw_sample_key: str)` | Toggle parent histogram sample visibility by raw sample key. |
| `_show_all_histogram_samples` | `(self)` | Clear legend-hidden samples and redraw the parent histogram. |
| `_plot_item_at` | `(self, pos)` | Resolve the clicked histogram PlotItem from a context-menu position. |
| `_get_hist_display_mode` | `(self)` | Return the active histogram display mode for current input type. |
| `_density_curve_supported` | `(self, mode, plot_data)` | Determine whether density curve toggle can render in current view. |
| `_count_plottable_series` | `(self, element_data, cfg)` | Count series that can actually be plotted in a histogram panel. |
| `_snapshot_panel_element_data` | `(self, element_data)` | Copy per-element value arrays for a child decomposition snapshot. |
| `_register_panel_context` | `(self, plot_item, mode, panel_label, element_data, sample_name=None)` | Store per-panel context for right-click decomposition eligibility. |
| `_decomposition_eligibility` | `(self, panel_ctx)` | Return whether isotope decomposition can open for clicked panel. |
| `_open_decomposition_window` | `(self, panel_ctx)` | Open a decoupled child histogram window split by isotope/element. |
| `_get_quick_toggle_support` | `(self, mode, plot_data)` | Return per-toggle enabled/disabled support for current histogram mode. |
| `_toggle_key` | `(self, key)` | Toggle a visual overlay key and redraw histogram. |
| `_set` | `(self, key, value)` |  |
| `_get_available_elements` | `(self)` | Get raw element names from input (before grouping). |
| `_open_settings` | `(self, title_override=None)` | Open histogram quantity/configuration controls. |
| `_open_plot_format_settings` | `(self)` | Open histogram format-only settings with global multi-subplot scope. |
| `_open_configure_plot_quantities` | `(self)` | Open histogram quantity/configuration controls. |
| `_open_plot_settings` | `(self, title_override=None, show_apply=True)` | Compatibility wrapper for the legacy single-plot settings editor. |
| `_download_figure` | `(self)` | Export histogram figure and CSV via existing PyQtGraph helper. |
| `_export_figure` | `(self)` | Route standardized bottom export action to histogram export path. |
| `_disable_native_pyqtgraph_context_menu` | `(self)` | Disable native PyQtGraph menus locally for Histogram. |
| `_reset_layout` | `(self)` | Reset histogram layout/ranges without changing scientific settings. |
| `_refresh` | `(self)` | Rebuild and redraw the histogram canvas from current configuration. |
| `_draw_subplots` | `(self, plot_data, cfg)` | Draw one subplot per sample using per-element color encoding. |
| `_draw_side_by_side` | `(self, plot_data, cfg)` | Draw side-by-side sample subplots using per-element color encoding. |
| `_draw_overlaid` | `(self, plot_data, cfg)` | Draw multi-sample overlaid histogram view. |
| `_draw_combined` | `(self, plot_data, cfg)` | Legacy wrapper for historical ``Combined with Legend`` mode values. |
| `_update_stats` | `(self, plot_data)` |  |

### `HistogramDecompositionDialog` *(extends `QDialog`)*

Independent child dialog that decomposes one histogram panel by isotope.

This window renders one single-series histogram panel per element/isotope
using a snapshot of parent panel data, with no write-back to parent node
or project lifecycle state.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config_snapshot, panel_label, panel_element_data, parent=None, ` | Preserved behavior: |
| `_build_ui` | `(self)` | Build decomposition plot area and standardized bottom buttons. |
| `_plot_item_at` | `(self, pos)` | Resolve which decomposed histogram subplot was right-clicked. |
| `_sanitize_filename_part` | `(value)` | Return a filesystem-safe token for subplot export filenames. |
| `_ctx_menu` | `(self, pos)` | Show child quick toggles, isotope label, and subplot export action. |
| `_toggle_key` | `(self, key)` | Toggle one local child visual setting and redraw. |
| `_set_key` | `(self, key, value)` | Set one local child config key and redraw. |
| `_open_plot_format_settings` | `(self)` | Open local format settings for decomposed histogram panels. |
| `_open_configure_plot_quantities` | `(self)` | Open local quantity settings for decomposed histogram panels. |
| `_reset_layout` | `(self)` | Reset child view ranges without modifying plotted values. |
| `_download_figure` | `(self)` | Export the child decomposition figure and per-element CSV rows. |
| `_export_subplot` | `(self, plot_item, subplot_ctx)` | Export only one clicked decomposed histogram subplot. |
| `_export_figure` | `(self)` | Route standardized export action to child export helper. |
| `_disable_native_pyqtgraph_context_menu` | `(self)` | Disable native PyQtGraph context menus for all child panels. |
| `_get_custom_title_map` | `(self)` | Return the child-local custom title mapping for decomposed subplots. |
| `_default_title_for_element` | `(self, raw_element_key)` | Return the default rendered title for one decomposed subplot. |
| `_effective_title_for_element` | `(self, raw_element_key)` | Resolve the visible title text for one decomposed subplot. |
| `_store_custom_title_text` | `(self, raw_element_key, title_text)` | Persist one custom decomposed-subplot title in child-local config. |
| `_apply_custom_title_edit` | `(self, plot_item, raw_element_key, title_text)` | Persist one edited title and update the live decomposed subplot. |
| `_configure_plot_title` | `(self, plot_item, raw_element_key)` | Attach persistent title-edit behavior to one decomposed subplot. |
| `_refresh` | `(self)` | Rebuild and redraw one single-series subplot per isotope/element. |
| `_add_density_unavailable_note` | `(self, plot_item)` | Add a minimal per-panel note when density curve cannot be rendered. |

### `HistogramPlotNode` *(extends `QObject`)*

Histogram visualization node with element grouping support.

Element groups sum selected element values PER PARTICLE into a
single combined value, then plot the histogram of those sums.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` | Open this node's figure, reusing one persistent (hide-on-close) window. |
| `process_data` | `(self, input_data)` |  |
| `extract_plot_data` | `(self)` | Extract plottable data, applying element groups when active. |
| `_extract_single` | `(self, dk)` |  |
| `_extract_multi` | `(self, dk)` |  |

### `BarChartSettingsDialog` *(extends `QDialog`)*

Scope-aware settings dialog for the element bar chart.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config, is_multi, sample_names, parent=None, scope='all', te_av` | Initialize bar-chart settings dialog with optional scope filtering. |
| `_build_ui` | `(self)` | Build settings controls for the selected scope. |
| `_try_apply` | `(self)` |  |
| `_try_done` | `(self)` |  |
| `_build_format_groups` | `(self, layout)` | Build the flat Element Bar Chart format controls. |
| `_uses_element_colors_in_format_dialog` | `(self)` | Return whether the active bar-chart mode visibly uses element colors. |
| `_uses_sample_colors_in_format_dialog` | `(self)` | Return whether the active bar-chart mode visibly uses sample colors. |
| `_format_settings_seed` | `(self)` | Return the current Element Bar Chart format-settings state. |
| `_style_swatch_button` | `(button, color)` | Apply a simple color-preview stylesheet to one swatch button. |
| `_pick_font_color` | `(self)` | Select a canonical font color for Element Bar Chart text styling. |
| `_pick_background_color` | `(self)` | Select the Element Bar Chart plot background color. |
| `_pick_element_color` | `(self, element)` | Select one canonical per-element bar color. |
| `_pick_sample_color` | `(self, sample_name)` | Select one canonical per-sample bar color. |
| `_normalized_display_name` | `(raw_name, edited_text)` | Normalize one display-name edit against its canonical raw key. |
| `_move_up` | `(self)` | Move selected sample-order row up in quantities scope. |
| `_move_down` | `(self)` | Move selected sample-order row down in quantities scope. |
| `collect` | `(self) → dict` | Collect settings values only for controls present in the active scope. |

### `ElementBarChartDisplayDialog` *(extends `QDialog`)*

Full-figure bar chart dialog with controlled custom context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, bar_node, parent_window=None)` | Initialize the element bar chart display dialog. |
| `_build_ui` | `(self)` | Build the PyQtGraph canvas plus standardized bottom action buttons. |
| `_ctx_menu` | `(self, pos)` | Show the custom bar-chart right-click menu. |
| `_toggle_key` | `(self, key)` | Toggle a lightweight visual option from the custom context menu. |
| `_set` | `(self, key, value)` | Set a config value from right-click quick actions. |
| `_plot_item_at` | `(self, pos)` | Return the PlotItem under a right-click position, or None. |
| `_toggle_bar_sample_visibility` | `(self, raw_sample_key)` | Toggle one raw sample's visibility in supported multi-sample modes. |
| `_no_visible_samples_message` | `()` | Return the standard empty-state message for fully hidden samples. |
| `_add_no_visible_samples_message` | `(self, plot_item)` | Render the standard no-visible-samples message on one plot item. |
| `_open_settings` | `(self)` | Open the legacy all-in-one settings dialog for compatibility. |
| `_open_plot_format_settings` | `(self)` | Open the Element-Bar-Chart-specific flat format settings dialog. |
| `_open_configure_plot_quantities` | `(self)` | Open quantities-scoped bar chart settings dialog. |
| `_get_available_bar_elements` | `(self)` | Return canonical raw element keys currently available to the chart. |
| `_open_plot_settings` | `(self, title_override=None, show_apply=True)` | Open the existing PlotSettingsDialog on the first available PlotItem. |
| `_plot_items` | `(self)` | Return all current PyQtGraph plot items in the dialog canvas. |
| `_get_custom_title_map` | `(self)` | Return the mutable Element Bar Chart custom-title mapping. |
| `_title_key_for_combined_plot` | `(self, mode_key)` | Build the stable custom-title key for a combined bar-chart view. |
| `_title_key_for_sample_plot` | `(self, sample_name)` | Build the stable custom-title key for one sample subplot. |
| `_default_title_for_key` | `(self, plot_key)` | Return the default rendered title for one custom-title key. |
| `_effective_title_for_key` | `(self, plot_key, default_title)` | Resolve the visible title text for one plot from config state. |
| `_apply_title_text_to_plot` | `(self, plot_item, title_text)` | Apply title text while preserving current global title formatting. |
| `_propagate_plot_format_text_settings` | `(self, source_plot_item)` | Apply accepted plot-format text settings to every current subplot. |
| `_reapply_saved_plot_format_settings` | `(self)` | Reapply saved Element Bar Chart plot-format settings after redraw. |
| `_apply_plot_text_settings_to_plot_item` | `(self, plot_item, settings)` | Apply explicit saved-format styling to one plot item. |
| `_store_custom_title_text` | `(self, plot_key, title_text)` | Persist one custom title text value into Element Bar Chart config. |
| `_apply_custom_title_edit` | `(self, plot_item, plot_key, title_text)` | Update live plot title text and persist it in node config. |
| `_configure_plot_title` | `(self, plot_item, plot_key, default_title='')` | Bind Element Bar Chart title behavior to one freshly drawn plot. |
| `_sync_element_bar_group_color` | `(self, items, color_hex)` | Persist shared bar-color edits into canonical element config state. |
| `_update_element_legend_swatches` | `(self, raw_keys, color_hex)` | Refresh live legend swatches for element-colored bar-chart entries. |
| `_download_figure` | `(self)` | Export bar chart as image or CSV via existing PyQtGraph export path. |
| `_export_subplot` | `(self, plot_item, subplot_ctx)` | Export one Individual Subplots panel as a standalone figure. |
| `_export_figure` | `(self)` | Route standardized export button to existing bar-chart export path. |
| `_disable_native_pyqtgraph_context_menu` | `(self)` | Disable native PyQtGraph plot/view menus for this dialog only. |
| `_reset_layout` | `(self)` | Reset current PyQtGraph view ranges to auto-range without changing data. |
| `_refresh` | `(self)` | Rebuild the Element Bar Chart canvas from node config and data. |
| `_draw_subplots` | `(self, plot_data, cfg)` | Draw one titled subplot per sample and reapply custom title text. |
| `_draw_side_by_side` | `(self, plot_data, cfg)` | Draw horizontal sample subplots and reapply custom title text. |
| `_draw_grouped` | `(self, plot_data, cfg)` | Draw the combined grouped-bars multi-sample view. |
| `_draw_stacked` | `(self, plot_data, cfg)` | Draw the combined stacked-bars multi-sample view. |
| `_draw_by_sample` | `(self, plot_data, cfg)` | Draw the multi-sample element-colored grouped bar chart view. |
| `_update_stats` | `(self, plot_data)` |  |

### `ElementBarChartPlotNode` *(extends `QObject`)*

Element particle-count bar chart node with right-click context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` | Open this node's figure, reusing one persistent (hide-on-close) window. |
| `process_data` | `(self, input_data)` |  |
| `extract_plot_data` | `(self)` | Extract element particle counts from input. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_ensure_project_root_on_sys_path` | `()` | Ensure package-style imports work when this file is run directly. |
| `_normalize_hist_display_mode` | `(mode: str) → str` | Normalize legacy histogram display-mode aliases to active modes. |
| `_fmt_elem` | `(elem: str, cfg: dict) → str` | Format an element key using the configured label_mode. |
| `_meta_te_available` | `(input_data)` | Report whether any sample in the input carries a usable transport rate. |
| `_per_ml_active` | `(cfg, input_data)` | Report whether the particles per millilitre y-axis unit should be used. |
| `_pml_factor` | `(input_data, sample_name)` | Return the multiplier that converts a particle count to particles per mL. |
| `_fmt_bar_value` | `(value, per_ml, cfg=None)` | Format a bar value label as an integer count or ten-to-a-power. |
| `_bar_value_textitem` | `(value, per_ml, anchor=(0.5, 1), color='#374151', cfg=None)` | Build a bar value-label TextItem, using HTML so a ten-to-a-power exponent |
| `_apply_sci_y_axis` | `(plot_item, cfg=None)` | Render the left axis tick labels of a plot as ten-to-a-power. |
| `_get_broken_cuts` | `(cfg)` | Return the sanitized, sorted list of broken Y-axis removed bands. |
| `_broken_segments` | `(cuts, y_max)` | Return the visible Y bands between cuts, ordered bottom to top. |
| `_broken_panel_range` | `(segs, i)` | Return the displayed Y range of stacked panel ``i``. |
| `_iter_bar_tops` | `(plot_item)` | Yield the geometry of every bar drawn on a panel. |
| `_add_torn_bar_marks` | `(plot_item, lo, hi, seg_lo, view_top)` | Draw torn edges for bars whose true top is inside a removed band. |
| `_apply_broken_ticks` | `(panels, segs)` | Synchronize tick spacing across the stacked panels. |
| `_broken_axis_width` | `(cfg, y_max)` | Return the left-axis width in pixels sized from the tick font. |
| `_rebind_auto_button` | `(pi, restore_fn)` | Make the panel's 'A' auto-range button cut-aware. |
| `_render_broken_or_plain` | `(glw, cuts, draw_fn, *, axis_factory, row=None, col=None, title=None, ` | Create one figure slot as a plain plot or a broken-axis panel group. |
| `_finalize_broken_panels` | `(panels, cuts, cfg=None)` | Finalize a stacked broken-axis panel group after drawing. |
| `_iter_panel_values` | `(plot_item)` | Yield every plotted Y-value on a panel that represents a real quantity. |
| `warn_if_values_swallowed` | `(container, cuts, parent)` | Warn when a broken Y-axis cut hides a real plotted value. |
| `_attach_histogram_legend_toggle` | `(legend, raw_key, toggle_callback)` | Wire histogram legend-row clicks to a raw-key visibility toggle callback. |
| `_attach_bar_chart_legend_toggle` | `(legend, raw_key, toggle_callback)` | Wire one Element Bar Chart legend row to a sample-visibility callback. |
| `_get_element_color` | `(element, index, cfg)` | Get color for an element from config or defaults. |
| `_get_element_display_name` | `(element, cfg)` | Get display name for an element (renamed or original). |
| `_tag_element_color_item` | `(item, raw_element_key, trace_name)` | Attach canonical raw-element identity metadata to a graphics item. |
| `_get_legend_sample_graphics_item` | `(legend_sample_item)` | Resolve the live swatch graphics item stored in a legend row. |
| `_get_xy_labels` | `(cfg)` | Build x/y label strings. |
| `_is_multi` | `(input_data)` |  |
| `_sample_names` | `(input_data)` |  |
| `_can_sum` | `(cfg)` | Check if current data type supports per-particle summation. |
| `_apply_element_groups` | `(particles, dk, groups)` | Apply element groups to particle data by summing per particle. |
| `_apply_element_groups_multi` | `(particles, sample_names, dk, groups)` | Apply element groups to multi-sample particle data. |
| `_get_label_color` | `(label, idx, cfg)` | Get color for a label: check element_colors → group color → default. |
| `_prepare_values` | `(values, data_type, log_x)` | Filter and optionally log-transform histogram values. |
| `_compute_hist_bar_data` | `(values, cfg, bin_edges=None, y_scale=1.0)` | Compute histogram bar arrays without drawing anything. |
| `_draw_histogram_bars` | `(plot_item, values, cfg, color_hex, bin_edges=None, name='', y_scale=1` | Draw histogram bars using PyQtGraph BarGraphItem. |
| `_apply_histogram_grid` | `(plot_item, cfg)` | Apply histogram grid visibility/alpha settings to a PlotItem. |
| `_add_density_curve` | `(plot_item, values, cfg, bin_edges, total_count)` | Add density curve overlay scaled to match count histogram. |
| `_density_curve_status` | `(values, cfg)` | Classify whether density can be attempted for one histogram series. |
| `_add_median_line` | `(plot_item, values, cfg)` | Add median vertical line with annotation. |
| `_add_stats_text` | `(plot_item, plot_data, cfg)` | Add statistics text box to histogram plot. |
| `_draw_single_histogram` | `(plot_item, element_data, cfg, single_color=None, density_status_out=N` | Draw histogram for one set of element data onto a PyQtGraph PlotItem. |
| `_sort_elements_for_display` | `(elements, counts, sort_option)` | Sort elements by user preference. |
| `_draw_single_bar_chart` | `(plot_item, element_counts, cfg, single_color=None, show_y_label=True,` | Draw one element bar chart and tag element-colored bars for sync hooks. |
