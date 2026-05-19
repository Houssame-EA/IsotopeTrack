# `results_matrix.py`

Correlation-Matrix Plot Node – pairwise Pearson-r heat-maps.

Single sample  → one matrix.
Multi-sample   → side-by-side or individual subplot matrices.

Rendered with Matplotlib (MplDraggableCanvas) for full drag/export support.

---

## Constants

| Name | Value |
|------|-------|
| `MATRIX_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass ...` |
| `MATRIX_DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'el...` |
| `MATRIX_COLORMAPS` | `['RdBu_r', 'coolwarm', 'seismic', 'BrBG', 'PiYG...` |
| `MATRIX_DISPLAY_MODES` | `['Side by Side', 'Individual Subplots', 'Differ...` |
| `DEFAULT_CONFIG` | `{'data_type_display': 'Counts', 'min_particles'...` |

## Classes

### `MatrixSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, parent = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `collect` | `(self)` | Returns: |

### `CorrelationMatrixDisplayDialog` *(extends `QDialog`)*

Matplotlib-based correlation matrix dialog with drag support.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `_ctx_menu` | `(self, pos)` | Args: |
| `_toggle` | `(self, key)` | Args: |
| `_set` | `(self, key, value)` | Args: |
| `_reset_layout` | `(self)` |  |
| `_export_figure` | `(self)` |  |
| `_open_settings` | `(self)` |  |
| `_refresh` | `(self)` |  |
| `_draw_single` | `(self, data, cfg)` | Args: |
| `_draw_multi` | `(self, data, cfg)` | Args: |
| `_draw_difference` | `(self, data, cfg)` | Args: |
| `_draw_matrix_ax` | `(self, ax, mat, elems, cfg, title = '')` | Draw one correlation matrix onto ax using imshow. |

### `CorrelationMatrixNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `extract_matrix_data` | `(self)` | Returns: |
| `_get_elements` | `(self)` | Returns: |
| `_extract_single` | `(self, data_key)` | Args: |
| `_extract_multi` | `(self, data_key)` | Args: |

## Functions

### `_is_multi`

```python
def _is_multi(input_data)
```


**Args:**

- `input_data (Any): The input data.`

**Returns:**

- `object: Result of the operation.`

### `_compute_correlation_matrix`

```python
def _compute_correlation_matrix(particles, elements, data_key)
```

Build NxN Pearson-r matrix from particle data.

**Args:**

- `particles (Any): The particles.`
- `elements (Any): The elements.`
- `data_key (Any): The data key.`

**Returns:**

- `tuple: Result of the operation.`

### `_matrix_stats`

```python
def _matrix_stats(mat)
```


**Args:**

- `mat (Any): The mat.`

**Returns:**

- `object: Result of the operation.`
