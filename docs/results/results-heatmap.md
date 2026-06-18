# `results_heatmap.py`

---

## Constants

| Name | Value |
|------|-------|
| `HEATMAP_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `DEGREE_SIGN` | `'°'` |
| `HEATMAP_MULTI_DISPLAY_MODES` | `['Individual Subplots', 'Side by Side Subplots', 'Combine…` |

## Classes

### `HeatmapSettingsDialog` *(extends `QDialog`)*

Scoped settings dialog for heatmap format/quantity configuration.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config: dict, is_multi: bool, sample_names: list, parent=None, ` | Args: |
| `_sample_name_keys` | `(self) → list[str]` | Return raw sample keys that can be renamed in Heatmap settings. |
| `_build` | `(self)` | Build scoped Heatmap settings controls for the current route. |
| `collect` | `(self) → dict` | Collect Heatmap settings without touching removed or missing widgets. |

### `HeatmapDisplayDialog` *(extends `QDialog`)*

Full-figure heatmap dialog with right-click context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, heatmap_node, parent_window=None)` | Args: |
| `_is_multi` | `(self) → bool` | Returns: |
| `_sample_names` | `(self) → list` | Returns: |
| `_single_sample_name` | `(self) → str` | Return the canonical single-sample key when one is available. |
| `_single_sample_title` | `(self, cfg: dict) → str` | Return the visible single-sample Heatmap title. |
| `_setup_ui` | `(self)` |  |
| `_show_context_menu` | `(self, pos)` | Build a minimal Heatmap right-click menu with quick controls only. |
| `_add_toggle` | `(self, menu, label, key)` | Args: |
| `_toggle` | `(self, key, value)` | Args: |
| `_set_label_mode` | `(self, mode)` |  |
| `_set_and_refresh` | `(self, key, value)` | Args: |
| `_search_dialog` | `(self)` |  |
| `_range_dialog` | `(self)` | Quick range adjustment via two input dialogs. |
| `_open_settings` | `(self)` |  |
| `_open_plot_format_settings` | `(self)` |  |
| `_open_configure_plot_quantities` | `(self)` |  |
| `_reset_layout` | `(self)` |  |
| `_export_figure` | `(self)` |  |
| `_refresh` | `(self)` | Rebuild the Heatmap figure from current config and extracted data. |
| `_draw_multi` | `(self, data, cfg, display_mode)` | Draw the active multi-sample Heatmap layout. |
| `_combine_data` | `(data)` | Args: |
| `_draw_heatmap` | `(self, ax, sample_data, cfg, title)` | Args: |

### `HeatmapPlotNode` *(extends `QObject`)*

Heatmap plot node with multiple sample support.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `extract_combinations_data` | `(self)` | Returns: |
| `_extract_single` | `(self, data_key)` | Args: |
| `_extract_multi` | `(self, data_key)` | Args: |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_normalize_heatmap_display_mode` | `(display_mode: str) → str` | Normalize legacy Heatmap display-mode values to supported UI modes. |
| `_combo_matches` | `(combination: str, search_elements: list) → bool` | Check if a combination string contains all search elements (order-independent). |
| `draw_combinations_heatmap` | `(ax, fig, sample_data, cfg, title='', is_multi=False)` | Draw a combinations heatmap onto an arbitrary axes/figure. |
| `_build_combinations` | `(particles, data_key, pml_factor=0.0)` | Build combination dict from a list of particle dicts. |
