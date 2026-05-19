# `results_correlation.py`

---

## Classes

### `CorrelationSettingsDialog` *(extends `QDialog`)*

Full settings dialog opened from the right-click → Configure… action.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config: dict, available_elements: list, is_multi: bool, sample_` | Args: |
| `_build_ui` | `(self)` | Returns: |
| `_on_mode_changed` | `(self)` |  |
| `_on_eq_changed` | `(self)` | Auto-populate axis labels from equation text when label is blank or was auto. |
| `_move_up` | `(self)` |  |
| `_move_down` | `(self)` |  |
| `_pick_sd_color` | `(self)` |  |
| `_pick_ref_color` | `(self)` |  |
| `collect` | `(self) → dict` | Return the updated config dict. |

### `AutoCorrelationDialog` *(extends `QDialog`)*

Table of top correlations — double-click to jump to that pair.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, top_pairs: list, parent = None)` | Args: |
| `_build` | `(self)` |  |
| `_on_double_click` | `(self, index)` | Args: |

### `CorrelationPlotDisplayDialog` *(extends `QDialog`)*

Full-figure correlation dialog.

Right-click anywhere on the plot to access:
- Quick toggles (log axes, trend line, correlation coeff)
- Data type switching
- Auto-detect correlations
- Full settings dialog
- Download

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, correlation_node, parent_window = None)` | Args: |
| `_is_multi` | `(self) → bool` | Returns: |
| `_sample_names` | `(self) → list` | Returns: |
| `_available_elements` | `(self) → list` | Returns: |
| `_setup_ui` | `(self)` |  |
| `_refresh_hint` | `(self)` |  |
| `_show_context_menu` | `(self, pos)` | Args: |
| `_add_toggle` | `(self, menu, label, key)` | Args: |
| `_toggle` | `(self, key, value)` | Args: |
| `_set_data_type` | `(self, dt)` | Args: |
| `_set_elem` | `(self, key, elem)` | Args: |
| `_set_display_mode` | `(self, mode)` | Args: |
| `_open_settings` | `(self)` |  |
| `_open_plot_settings` | `(self)` | Open PlotSettingsDialog via the adapter bridge. |
| `_click_to_data_coords` | `(self, widget_pos) → tuple` | Convert a right-click position in plot_widget coords to data coords |
| `_current_xy_arrays` | `(self)` | Return (x_array, y_array) pooled across samples in the plot's |
| `_build_smart_actions` | `(self) → list` | Data-aware smart actions for correlation plots. |
| `_auto_detect_correlations` | `(self)` |  |
| `_apply_auto_pair` | `(self, x_elem, y_elem)` | Args: |
| `_cleanup_color_bars` | `(self)` |  |
| `_refresh` | `(self)` |  |
| `_extract_xy_color` | `(self, df, cfg)` | Extract (x, y, color_or_None) arrays from a DataFrame and config. |
| `_prepare_data` | `(self, df, cfg)` | Filter + log-transform + outlier removal. Returns (x, y, color) ready for plotting. |
| `_plot_scatter` | `(self, pi, x, y, c, cfg, color)` | Add scatter + optional trend + SD envelope + ref line + box to a PlotItem. |
| `_apply_labels` | `(self, pi, cfg)` | Args: |
| `_draw_single` | `(self, pi, plot_data, cfg)` | Args: |
| `_draw_subplots` | `(self, plot_data, cfg)` | Args: |
| `_draw_side_by_side` | `(self, plot_data, cfg)` | Args: |
| `_draw_combined` | `(self, pi, plot_data, cfg)` | Args: |

### `CorrelationPlotNode` *(extends `QObject`)*

Correlation plot node with multiple sample support and auto-detection.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `_auto_configure_elements` | `(self)` |  |
| `_get_elements` | `(self) → list` | Returns: |
| `extract_plot_data` | `(self)` | Returns: |
