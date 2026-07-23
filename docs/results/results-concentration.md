# `results_concentration.py`

Concentration-Comparison Plot Node – dot-and-circle strip chart.

Each element gets a horizontal row.
Individual sample values are small dots (jittered), group means are large
open circles.  Numeric mean values displayed on the right.

Single sample  → one column of dots per element.
Multi-sample   → overlaid colours per sample / group.

Rendered with Matplotlib (MplDraggableCanvas) for full drag/export support.

---

## Constants

| Name | Value |
|------|-------|
| `CONC_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `CONC_DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'element_mass…` |
| `CONC_LABEL_MAP` | `{'Counts': 'Intensity (counts)', 'Element Mass (fg)': 'Ma…` |
| `CONC_AGG_METHODS` | `['Mean', 'Median', 'Geometric Mean']` |
| `DEFAULT_CONFIG` | `{'data_type_display': 'Counts', 'aggregation': 'Mean', 'l…` |
| `DEFAULT_GROUP_COLORS` | `['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6', '…` |

## Classes

### `ConcentrationSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, parent=None, scope='all')` |  |
| `_build_ui` | `(self)` |  |
| `_pick_point_color` | `(self, sn, btn)` | Pick one per-sample individual-point color and refresh its preview. |
| `_pick_mean_color` | `(self, sn, btn)` | Pick one per-sample mean-marker color and refresh its preview. |
| `collect` | `(self) → dict` |  |

### `ConcentrationDisplayDialog` *(extends `QDialog`)*

Matplotlib-based concentration strip-chart with drag support.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window=None)` |  |
| `_build_ui` | `(self)` |  |
| `_ctx_menu` | `(self, pos)` | Build a minimal Concentration right-click menu with quick controls only. |
| `_toggle` | `(self, key)` |  |
| `_set` | `(self, key, value)` |  |
| `_set_mouse_mode` | `(self, mode: str)` | Update the transient Concentration mouse interaction mode. |
| `_reset_layout` | `(self)` | Reset subplot layout and restore the baseline Concentration view limits. |
| `_export_figure` | `(self)` |  |
| `_open_plot_format_settings` | `(self)` |  |
| `_open_configure_plot_quantities` | `(self)` |  |
| `_open_settings` | `(self)` |  |
| `_refresh` | `(self)` |  |
| `_draw_chart` | `(self, data, cfg)` | Draw the horizontal strip chart onto self.figure. |

### `ConcentrationComparisonNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` |  |
| `process_data` | `(self, input_data)` |  |
| `_get_elements` | `(self)` |  |
| `extract_concentration_data` | `(self)` |  |
| `_extract_single` | `(self, data_key, elements, agg_method, unit)` |  |
| `_extract_multi` | `(self, data_key, elements, agg_method, unit)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_is_multi` | `(input_data)` |  |
| `_agg` | `(values, method)` |  |
| `_fmt_val` | `(v)` |  |
