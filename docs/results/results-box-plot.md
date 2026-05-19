# `results_box_plot.py`

Distribution Plot Node – Box / Violin / Strip / Bar-with-errors.

Keeps **PyQtGraph** for interactive zoom/pan.
Sidebar replaced by **right-click context menu** + settings dialog.
Uses shared_plot_utils for fonts, colors, sample helpers, and download.

---

## Constants

| Name | Value |
|------|-------|
| `PLOT_SHAPES` | `['Box Plot (Traditional)', 'Violin Plot', 'Box ...` |
| `BOX_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass ...` |
| `BOX_DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'el...` |
| `BOX_LABEL_MAP` | `{'Counts': 'Intensity (counts)', 'Element Mass ...` |
| `BOX_DISPLAY_MODES` | `['Side by Side', 'By Sample (Ordered)', 'Indivi...` |
| `DEFAULT_ELEMENT_COLORS` | `['#663399', '#2E86AB', '#A23B72', '#F18F01', '#...` |
| `DEFAULT_CONFIG` | `{'data_type_display': 'Counts', 'plot_shape': '...` |
| `_SHAPE_DRAWERS` | `{'Box Plot (Traditional)': _draw_box, 'Violin P...` |

## Classes

### `BoxPlotSettingsDialog` *(extends `QDialog`)*

Full settings dialog opened from context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, parent = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `_pick_shade_color` | `(self)` |  |
| `_on_shade_type_changed` | `(self, text)` | Args: |
| `_move_up` | `(self)` |  |
| `_move_down` | `(self)` |  |
| `collect` | `(self)` | Returns: |

### `BoxPlotDisplayDialog` *(extends `QDialog`)*

Main dialog with PyQtGraph plot and right-click context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `_ctx_menu` | `(self, pos)` | Args: |
| `_toggle` | `(self, key)` | Args: |
| `_set` | `(self, key, value)` | Args: |
| `_open_settings` | `(self)` |  |
| `_open_plot_settings` | `(self)` | Open full PlotSettingsDialog via the adapter bridge. |
| `_refresh` | `(self)` |  |
| `_draw_single_sample` | `(self, pi, data, cfg)` | Single sample – one shape per element. |
| `_draw_combined` | `(self, pi, plot_data, cfg)` | Multi-sample Side by Side. |
| `_draw_subplots` | `(self, plot_data, cfg)` | Args: |
| `_draw_grouped` | `(self, plot_data, cfg)` | Args: |
| `_draw_by_sample` | `(self, plot_data, cfg)` | X-axis = samples (time-ordered), one subplot per element. |
| `_update_stats` | `(self, plot_data, multi)` | Args: |

### `BoxPlotNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `extract_plot_data` | `(self)` | Returns: |
| `_extract_single` | `(self, data_key)` | Args: |
| `_extract_multi` | `(self, data_key)` | Args: |

## Functions

### `_y_label`

```python
def _y_label(cfg)
```


**Args:**

- `cfg (Any): The cfg.`

**Returns:**

- `object: Result of the operation.`

### `_element_color`

```python
def _element_color(element, index, cfg)
```


**Args:**

- `element (Any): The element.`
- `index (Any): Row or item index.`
- `cfg (Any): The cfg.`

**Returns:**

- `object: Result of the operation.`

### `_fmt_elem`

```python
def _fmt_elem(elem, cfg)
```


**Args:**

- `elem (Any): The elem.`
- `cfg (Any): The cfg.`

**Returns:**

- `object: Result of the operation.`

### `_is_multi`

```python
def _is_multi(input_data)
```


**Args:**

- `input_data (Any): The input data.`

**Returns:**

- `object: Result of the operation.`

### `_available_elements`

```python
def _available_elements(input_data)
```


**Args:**

- `input_data (Any): The input data.`

**Returns:**

- `list: Result of the operation.`

### `_filter_values`

```python
def _filter_values(values, data_type, log_y, cfg = None)
```


**Args:**

- `values (Any): Array or sequence of values.`
- `data_type (Any): The data type.`
- `log_y (Any): The log y.`
- `cfg (Any): The cfg.`

**Returns:**

- `object: Result of the operation.`

### `_apply_box_overlays`

```python
def _apply_box_overlays(plot_item, all_values_flat, cfg)
```

Apply horizontal band + detection limit + figure box to a finished plot.

**Args:**

- `plot_item (Any): The plot item.`
- `all_values_flat (Any): The all values flat.`
- `cfg (Any): The cfg.`

### `_draw_box`

```python
def _draw_box(plot_item, x, values, color, alpha, width, cfg)
```


**Args:**

- `plot_item (Any): The plot item.`
- `x (Any): Input array or value.`
- `values (Any): Array or sequence of values.`
- `color (Any): Colour value.`
- `alpha (Any): The alpha.`
- `width (Any): Width in pixels.`
- `cfg (Any): The cfg.`

### `_draw_violin`

```python
def _draw_violin(plot_item, x, values, color, alpha, width, cfg)
```


**Args:**

- `plot_item (Any): The plot item.`
- `x (Any): Input array or value.`
- `values (Any): Array or sequence of values.`
- `color (Any): Colour value.`
- `alpha (Any): The alpha.`
- `width (Any): Width in pixels.`
- `cfg (Any): The cfg.`

### `_draw_box_violin`

```python
def _draw_box_violin(plot_item, x, values, color, alpha, width, cfg)
```


**Args:**

- `plot_item (Any): The plot item.`
- `x (Any): Input array or value.`
- `values (Any): Array or sequence of values.`
- `color (Any): Colour value.`
- `alpha (Any): The alpha.`
- `width (Any): Width in pixels.`
- `cfg (Any): The cfg.`

### `_draw_strip`

```python
def _draw_strip(plot_item, x, values, color, alpha, width, cfg)
```


**Args:**

- `plot_item (Any): The plot item.`
- `x (Any): Input array or value.`
- `values (Any): Array or sequence of values.`
- `color (Any): Colour value.`
- `alpha (Any): The alpha.`
- `width (Any): Width in pixels.`
- `cfg (Any): The cfg.`

### `_draw_half_violin_box`

```python
def _draw_half_violin_box(plot_item, x, values, color, alpha, width, cfg)
```


**Args:**

- `plot_item (Any): The plot item.`
- `x (Any): Input array or value.`
- `values (Any): Array or sequence of values.`
- `color (Any): Colour value.`
- `alpha (Any): The alpha.`
- `width (Any): Width in pixels.`
- `cfg (Any): The cfg.`

### `_draw_notched_box`

```python
def _draw_notched_box(plot_item, x, values, color, alpha, width, cfg)
```


**Args:**

- `plot_item (Any): The plot item.`
- `x (Any): Input array or value.`
- `values (Any): Array or sequence of values.`
- `color (Any): Colour value.`
- `alpha (Any): The alpha.`
- `width (Any): Width in pixels.`
- `cfg (Any): The cfg.`

### `_draw_bar_errors`

```python
def _draw_bar_errors(plot_item, x, values, color, alpha, width, cfg)
```


**Args:**

- `plot_item (Any): The plot item.`
- `x (Any): Input array or value.`
- `values (Any): Array or sequence of values.`
- `color (Any): Colour value.`
- `alpha (Any): The alpha.`
- `width (Any): Width in pixels.`
- `cfg (Any): The cfg.`

### `_draw_single_element`

```python
def _draw_single_element(plot_item, x, values, sample_name, element, cfg, is_multi)
```

Dispatch to the correct shape drawer.

**Args:**

- `plot_item (Any): The plot item.`
- `x (Any): Input array or value.`
- `values (Any): Array or sequence of values.`
- `sample_name (Any): The sample name.`
- `element (Any): The element.`
- `cfg (Any): The cfg.`
- `is_multi (Any): The is multi.`

### `_add_stats_text`

```python
def _add_stats_text(plot_item, plot_data, cfg)
```

Add statistics text box.

**Args:**

- `plot_item (Any): The plot item.`
- `plot_data (Any): The plot data.`
- `cfg (Any): The cfg.`
