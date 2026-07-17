# `results_matrix.py`

Correlation-Matrix Plot Node – pairwise Pearson-r heat-maps.

---

## Constants

| Name | Value |
|------|-------|
| `MATRIX_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `MATRIX_DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'element_mass…` |
| `MATRIX_COLORMAPS` | `['RdBu_r', 'coolwarm', 'seismic', 'BrBG', 'PiYG', 'PRGn',…` |
| `MATRIX_DISPLAY_MODES` | `['Side by Side', 'Individual Subplots', 'Difference Matrix']` |
| `DEGREE_SIGN` | `'°'` |
| `DEFAULT_HIGHLIGHT_COLOR` | `'#000000'` |
| `DEFAULT_CONFIG` | `{'data_type_display': 'Counts', 'min_particles': 5, 'r_th…` |

## Classes

### `MatrixSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, parent=None, scope='all')` |  |
| `_build_ui` | `(self)` |  |
| `collect` | `(self)` |  |

### `CorrelationMatrixDisplayDialog` *(extends `QDialog`)*

Matplotlib-based correlation matrix dialog with drag support.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window=None)` |  |
| `_build_ui` | `(self)` |  |
| `_ctx_menu` | `(self, pos)` | Build a minimal Matrix right-click menu with quick controls only. |
| `_toggle` | `(self, key)` |  |
| `_set` | `(self, key, value)` |  |
| `_get_row_at` | `(self, widget_pos)` | Return the element for the matrix row at widget_pos, or None. |
| `_toggle_row_highlight` | `(self, elem, add)` |  |
| `_change_row_highlight_color` | `(self, elem)` |  |
| `_clear_all_highlights` | `(self)` |  |
| `_reset_layout` | `(self)` |  |
| `_export_figure` | `(self)` |  |
| `_open_plot_format_settings` | `(self)` |  |
| `_open_configure_plot_quantities` | `(self)` |  |
| `_open_settings` | `(self)` |  |
| `_refresh` | `(self)` |  |
| `_draw_single` | `(self, data, cfg)` |  |
| `_draw_multi` | `(self, data, cfg)` |  |
| `_draw_difference` | `(self, data, cfg)` |  |
| `_draw_matrix_ax` | `(self, ax, mat, elems, cfg, title='')` | Draw one correlation matrix onto ax using imshow. |

### `CorrelationMatrixNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` |  |
| `process_data` | `(self, input_data)` |  |
| `extract_matrix_data` | `(self)` |  |
| `_get_elements` | `(self)` |  |
| `_extract_single` | `(self, data_key)` |  |
| `_extract_multi` | `(self, data_key)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_normalize_highlighted_elements` | `(raw)` | Return ``{element: hex_color}`` from the highlighted_elements config value. |
| `_is_multi` | `(input_data)` |  |
| `_compute_correlation_matrix` | `(particles, elements, data_key)` | Build NxN Pearson-r matrix from particle data. |
| `_matrix_stats` | `(mat)` |  |
