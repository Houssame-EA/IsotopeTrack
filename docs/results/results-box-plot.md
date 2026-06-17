# `results_box_plot.py`

Distribution Plot Node – Box / Violin / Strip / Bar-with-errors.

---

## Constants

| Name | Value |
|------|-------|
| `PLOT_SHAPES` | `['Box Plot (Traditional)', 'Violin Plot', 'Box + Violin (…` |
| `BOX_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `BOX_DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'element_mass…` |
| `BOX_LABEL_MAP` | `{'Counts': 'Intensity (counts)', 'Element Mass (fg)': 'El…` |
| `BOX_DISPLAY_MODES` | `['Side by Side', 'Subplots by sample', 'Subplots by isoto…` |
| `BOX_SORT_OPTIONS` | `['No Sorting', 'Ascending', 'Descending', 'Alphabetical']` |
| `DEFAULT_ELEMENT_COLORS` | `['#663399', '#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '…` |
| `DEFAULT_CONFIG` | `{'data_type_display': 'Counts', 'plot_shape': 'Box Plot (…` |
| `_DISPLAY_MODE_ALIASES` | `{'Individual Subplots': 'Subplots by sample', 'Grouped by…` |
| `_SHAPE_DRAWERS` | `{'Box Plot (Traditional)': _draw_box, 'Violin Plot': _dra…` |

## Classes

### `BoxPlotSettingsDialog` *(extends `QDialog`)*

Scope-aware settings dialog for Box Plot format or quantity controls.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, parent=None, scope='all')` | Args: |
| `_build_ui` | `(self)` | Build settings widgets for the selected scope. |
| `_pick_shade_color` | `(self)` |  |
| `_on_shade_type_changed` | `(self, text)` | Args: |
| `_move_up` | `(self)` |  |
| `_move_down` | `(self)` |  |
| `collect` | `(self)` | Collect settings from the active scope without touching missing widgets. |

### `BoxPlotDisplayDialog` *(extends `QDialog`)*

Main dialog with PyQtGraph plot and right-click context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window=None)` | Args: |
| `_build_ui` | `(self)` | Build plot canvas, stats row, and standardized bottom action buttons. |
| `_ctx_menu` | `(self, pos)` | Show Box Plot custom right-click menu with Box-specific quick actions. |
| `_plot_item_at` | `(self, pos)` | Resolve the clicked subplot via ``mapRectToScene`` hit testing. |
| `_sanitize_filename_part` | `(value)` | Convert subplot context text into a filesystem-safe token. |
| `_export_subplot` | `(self, plot_item, subplot_ctx)` | Export one already-rendered Box Plot subplot using shared workflow. |
| `_toggle` | `(self, key)` | Args: |
| `_set` | `(self, key, value)` | Args: |
| `_open_settings` | `(self, scope='all', title_override=None)` | Open scoped Box Plot settings dialog and apply updates on accept. |
| `_open_plot_settings` | `(self)` | Open rich PyQtGraph visual settings dialog bound to one PlotItem. |
| `_open_plot_format_settings` | `(self)` | Open Box Plot visual format settings in a config-driven route. |
| `_open_configure_plot_quantities` | `(self)` | Open quantity/data Box Plot settings routed from bottom button. |
| `_export_figure` | `(self)` | Export the current Box Plot figure using the existing helper. |
| `_disable_native_pyqtgraph_context_menu` | `(self)` | Disable native PyQtGraph menus locally for Box Plot dialog only. |
| `_reset_layout` | `(self)` | Reset Box Plot view ranges to auto layout without changing data. |
| `_get_custom_title_map` | `(self)` | Return the canonical custom-title mapping for this Box Plot dialog. |
| `_title_key_for_combined_plot` | `(is_multi)` | Return the stable custom-title key for one combined Box Plot. |
| `_title_key_for_sample_plot` | `(sample_name)` | Return the stable custom-title key for one sample subplot. |
| `_title_key_for_element_plot` | `(raw_element_key)` | Return the stable custom-title key for one element subplot. |
| `_effective_title_for_key` | `(self, plot_key, default_title='')` | Resolve the effective title for one Box Plot panel key. |
| `_apply_title_text_to_plot` | `(self, plot_item, title_text)` | Apply a Box Plot title while preserving the current title styling. |
| `_store_custom_title_text` | `(self, plot_key, title_text)` | Store or clear one display-only Box Plot title override. |
| `_apply_custom_title_edit` | `(self, plot_item, plot_key, title_text, default_title='')` | Persist one Box Plot title edit and reapply the effective title. |
| `_configure_plot_title` | `(self, plot_item, plot_key, default_title='')` | Bind text-only title editing and render the effective Box Plot title. |
| `_get_custom_axis_label_map` | `(self)` | Return the canonical custom axis-label mapping for this Box Plot. |
| `_effective_axis_labels_for_key` | `(self, plot_key, default_axis_labels)` | Resolve effective bottom/left axis labels for one Box Plot key. |
| `_store_custom_axis_label` | `(self, plot_key, axis_name, text, units)` | Store or clear one display-only Box Plot axis-label override. |
| `_apply_effective_axis_labels` | `(self, plot_item, plot_key, default_axis_labels)` | Apply effective Box Plot axis labels and persistence callbacks. |
| `_category_sort_mode` | `(cfg)` | Return the active Box Plot category sort mode. |
| `_refresh` | `(self)` | Rebuild the Box Plot from extracted data and current config. |
| `_draw_single_sample` | `(self, pi, data, cfg)` | Draw one sample panel with element-only x-axis labels. |
| `_draw_combined` | `(self, pi, plot_data, cfg)` | Draw the dense multi-sample ``Side by Side`` combined layout. |
| `_draw_subplots` | `(self, plot_data, cfg)` | Draw ``Subplots by sample`` as one panel per sample. |
| `_draw_grouped` | `(self, plot_data, cfg)` | Draw ``Subplots by isotope`` with one panel per element/isotope. |
| `_draw_by_sample` | `(self, plot_data, cfg)` | X-axis = samples (time-ordered), one subplot per element. |
| `_update_stats` | `(self, plot_data, multi)` | Args: |

### `BoxPlotNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `extract_plot_data` | `(self)` | Returns: |
| `_extract_single` | `(self, data_key)` | Args: |
| `_extract_multi` | `(self, data_key)` | Args: |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_y_label` | `(cfg)` | Args: |
| `_element_color` | `(element, index, cfg)` | Args: |
| `_fmt_elem` | `(elem, cfg)` | Args: |
| `_is_multi` | `(input_data)` | Args: |
| `_available_elements` | `(input_data)` | Args: |
| `_filter_values` | `(values, data_type, log_y, cfg=None)` | Args: |
| `_apply_box_overlays` | `(plot_item, all_values_flat, cfg)` | Apply horizontal band + detection limit + figure box to a finished plot. |
| `_normalize_box_display_mode` | `(mode)` | Normalize legacy Box Plot display-mode values to supported UI modes. |
| `_apply_boxplot_grid` | `(plot_item, cfg)` | Apply config-driven grid visibility to one Box Plot ``PlotItem``. |
| `_sort_box_category_records` | `(records, sort_mode)` | Return Box Plot display records in the requested display order. |
| `_sort_box_sample_records` | `(records, sort_mode)` | Return ``Subplots by isotope`` sample records in subplot display order. |
| `_draw_box` | `(plot_item, x, values, color, alpha, width, cfg)` | Args: |
| `_draw_violin` | `(plot_item, x, values, color, alpha, width, cfg)` | Args: |
| `_draw_box_violin` | `(plot_item, x, values, color, alpha, width, cfg)` | Args: |
| `_draw_strip` | `(plot_item, x, values, color, alpha, width, cfg)` | Args: |
| `_draw_half_violin_box` | `(plot_item, x, values, color, alpha, width, cfg)` | Args: |
| `_draw_notched_box` | `(plot_item, x, values, color, alpha, width, cfg)` | Args: |
| `_draw_bar_errors` | `(plot_item, x, values, color, alpha, width, cfg)` | Args: |
| `_draw_single_element` | `(plot_item, x, values, sample_name, element, cfg, is_multi)` | Dispatch one series to the configured Box Plot shape drawer. |
| `_add_empty_panel_message` | `(plot_item, message='No valid data')` | Add a small, panel-local empty-state note for subplot readability. |
| `_add_stats_text` | `(plot_item, plot_data, cfg)` | Add statistics text box. |
