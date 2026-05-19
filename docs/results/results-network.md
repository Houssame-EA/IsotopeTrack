# `results_network.py`

Network / Chord Diagram Node – circular element correlation network.

Elements are arranged around a circle.  Edges represent significant
pairwise Pearson correlations.  Red = positive, Blue = negative.
Edge width ∝ |r|.

Rendered with Matplotlib (MplDraggableCanvas) for full drag/export support.

---

## Constants

| Name | Value |
|------|-------|
| `NET_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass ...` |
| `NET_DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'el...` |
| `DEFAULT_CONFIG` | `{'data_type_display': 'Counts', 'r_threshold': ...` |

## Classes

### `_ColorBtn` *(extends `QPushButton`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, color = '#FFFFFF', parent = None)` | Args: |
| `_apply` | `(self)` |  |
| `color` | `(self)` | Returns: |
| `mousePressEvent` | `(self, event)` | Args: |

### `NetworkSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, parent = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `collect` | `(self)` | Returns: |

### `NetworkDisplayDialog` *(extends `QDialog`)*

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
| `_draw_network` | `(self, ax, net_data, cfg)` | Draw one circular correlation network onto ax. |

### `NetworkDiagramNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `_get_elements` | `(self)` | Returns: |
| `extract_network_data` | `(self)` | Returns: |
| `_extract_single` | `(self, data_key, elements, r_threshold, min_n)` | Args: |
| `_extract_multi` | `(self, data_key, elements, r_threshold, min_n)` | Args: |

## Functions

### `_is_multi`

```python
def _is_multi(input_data)
```


**Args:**

- `input_data (Any): The input data.`

**Returns:**

- `object: Result of the operation.`

### `_compute_edges`

```python
def _compute_edges(particles, elements, data_key, r_threshold, min_n)
```

Return list of (i, j, r) where |r| >= threshold.

**Args:**

- `particles (Any): The particles.`
- `elements (Any): The elements.`
- `data_key (Any): The data key.`
- `r_threshold (Any): The r threshold.`
- `min_n (Any): The min n.`

**Returns:**

- `object: Result of the operation.`
