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
| `CONC_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass ...` |
| `CONC_DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'el...` |
| `CONC_LABEL_MAP` | `{'Counts': 'Intensity (counts)', 'Element Mass ...` |
| `CONC_AGG_METHODS` | `['Mean', 'Median', 'Geometric Mean']` |
| `DEFAULT_CONFIG` | `{'data_type_display': 'Counts', 'aggregation': ...` |
| `DEFAULT_GROUP_COLORS` | `['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#...` |

## Classes

### `ConcentrationSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, parent = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `_pick_color` | `(self, sn, btn)` | Args: |
| `collect` | `(self) → dict` | Returns: |

### `ConcentrationDisplayDialog` *(extends `QDialog`)*

Matplotlib-based concentration strip-chart with drag support.

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
| `_draw_chart` | `(self, data, cfg)` | Draw the horizontal strip chart onto self.figure. |

### `ConcentrationComparisonNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `_get_elements` | `(self)` | Returns: |
| `extract_concentration_data` | `(self)` | Returns: |
| `_extract_single` | `(self, data_key, elements, agg_method, unit)` | Args: |
| `_extract_multi` | `(self, data_key, elements, agg_method, unit)` | Args: |

## Functions

### `_is_multi`

```python
def _is_multi(input_data)
```


**Args:**

- `input_data (Any): The input data.`

**Returns:**

- `object: Result of the operation.`

### `_agg`

```python
def _agg(values, method)
```


**Args:**

- `values (Any): Array or sequence of values.`
- `method (Any): The method.`

**Returns:**

- `object: Result of the operation.`

### `_fmt_val`

```python
def _fmt_val(v)
```


**Args:**

- `v (Any): The v.`

**Returns:**

- `object: Result of the operation.`
