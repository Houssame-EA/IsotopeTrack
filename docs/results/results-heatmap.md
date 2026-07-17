# `results_heatmap.py`

---

## Constants

| Name | Value |
|------|-------|
| `HEATMAP_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `DEGREE_SIGN` | `'°'` |
| `HEATMAP_MULTI_DISPLAY_MODES` | `['Individual Subplots', 'Side by Side Subplots', 'Combine…` |
| `DEFAULT_HIGHLIGHT_COLOR` | `'#000000'` |
| `CELL_STAT_OPTIONS` | `['Mean', 'Median', 'Mode', 'Geometric Mean']` |
| `CELL_SPREAD_OPTIONS` | `['None', 'SD', 'SEM', 'IQR (Q1–Q3)', 'Min–Max', 'CV %']` |

## Classes

### `HeatmapSettingsDialog` *(extends `QDialog`)*

Scoped settings dialog for heatmap format/quantity configuration.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config: dict, is_multi: bool, sample_names: list, parent=None, ` |  |
| `_sample_name_keys` | `(self) → list[str]` | Return raw sample keys that can be renamed in Heatmap settings. |
| `_build` | `(self)` | Build scoped Heatmap settings controls for the current route. |
| `collect` | `(self) → dict` | Collect Heatmap settings without touching removed or missing widgets. |

### `HeatmapDisplayDialog` *(extends `QDialog`)*

Full-figure heatmap dialog with right-click context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, heatmap_node, parent_window=None)` |  |
| `_is_multi` | `(self) → bool` |  |
| `_sample_names` | `(self) → list` |  |
| `_single_sample_name` | `(self) → str` | Return the canonical single-sample key when one is available. |
| `_single_sample_title` | `(self, cfg: dict) → str` | Return the visible single-sample Heatmap title. |
| `_setup_ui` | `(self)` |  |
| `_show_context_menu` | `(self, pos)` | Build a minimal Heatmap right-click menu with quick controls only. |
| `_get_row_at` | `(self, widget_pos)` | Return the raw combo key for the heatmap row at widget_pos, or None. |
| `_axes_sample_at` | `(self, widget_pos)` | Return the sample name for the heatmap axes under widget_pos, or None. |
| `_toggle_row_highlight` | `(self, combo_key, add)` |  |
| `_change_row_highlight_color` | `(self, combo_key)` |  |
| `_clear_all_highlights` | `(self)` |  |
| `_add_toggle` | `(self, menu, label, key)` |  |
| `_toggle` | `(self, key, value)` |  |
| `_set_label_mode` | `(self, mode)` |  |
| `_set_and_refresh` | `(self, key, value)` |  |
| `_search_dialog` | `(self)` |  |
| `_range_dialog` | `(self)` | Quick range adjustment via two input dialogs. |
| `_open_settings` | `(self)` |  |
| `_open_plot_format_settings` | `(self)` |  |
| `_open_configure_plot_quantities` | `(self)` |  |
| `_reset_layout` | `(self)` |  |
| `_export_figure` | `(self)` |  |
| `_export_subplot` | `(self, sample_name)` | Export one heatmap subplot as a standalone single-panel figure. |
| `_refresh` | `(self)` | Rebuild the Heatmap figure from current config and extracted data. |
| `_draw_multi` | `(self, data, cfg, display_mode)` | Draw the active multi-sample Heatmap layout. |
| `_combine_data` | `(data)` |  |
| `_draw_heatmap` | `(self, ax, sample_data, cfg, title)` | Args: |

### `HeatmapPlotNode` *(extends `QObject`)*

Heatmap plot node with multiple sample support.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` | Open this node's figure, reusing one persistent (hide-on-close) window. |
| `process_data` | `(self, input_data)` |  |
| `extract_plot_data` | `(self)` |  |
| `_extract_single` | `(self, data_key)` |  |
| `_extract_multi` | `(self, data_key)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_normalize_highlighted_combos` | `(raw)` | Return ``{combo_key: hex_color}`` from either the current dict format |
| `_normalize_heatmap_display_mode` | `(display_mode: str) → str` | Normalize legacy Heatmap display-mode values to supported UI modes. |
| `_combo_matches` | `(combination: str, search_elements: list) → bool` | Check if a combination string contains all search elements (order-independent). |
| `_combo_exact_matches` | `(combination: str, search_elements: list) → bool` | Check if a combination has exactly the search elements — no more, no less. |
| `_mode_estimate` | `(arr)` | Estimate the mode of continuous values from the densest histogram bin. |
| `_cell_center` | `(vals, stat)` | Central value for one heatmap cell: Mean, Median, Mode, or Geo. Mean. |
| `_cell_spread_value` | `(vals, spread)` | Secondary value shown after a cell centre. |
| `_fmt_cell_number` | `(v, is_pct)` | Format one numeric cell value with the heatmap's standard precision. |
| `draw_combinations_heatmap` | `(ax, fig, sample_data, cfg, title='', is_multi=False)` | Draw a combinations heatmap onto an arbitrary axes/figure. |
| `_build_combinations` | `(particles, data_key, pml_factor=0.0)` | Build combination dict from a list of particle dicts. |
