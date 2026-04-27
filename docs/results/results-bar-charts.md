# `results_bar_charts.py`

---

## Constants

| Name | Value |
|------|-------|
| `HIST_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass ...` |
| `SUMMABLE_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass ...` |
| `HIST_DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'el...` |
| `HIST_LABEL_MAP` | `{'Counts': 'Intensity (counts)', 'Element Mass ...` |
| `HIST_DISPLAY_MODES` | `['Overlaid (Different Colors)', 'Side by Side S...` |
| `BAR_DISPLAY_MODES` | `['Grouped Bars (Side by Side)', 'By Sample (Ele...` |
| `SORT_OPTIONS` | `['No Sorting', 'Ascending', 'Descending', 'Alph...` |
| `CURVE_TYPES` | `['Log-Normal Fit', 'Normal Fit']` |
| `DEFAULT_ELEMENT_COLORS` | `['#663399', '#2E86AB', '#A23B72', '#F18F01', '#...` |

## Classes

### `_PlotWidgetAdapter`

Wraps a (GraphicsLayoutWidget, PlotItem) pair so that all editor
dialogs from custom_plot_widget.py treat it like a pg.PlotWidget.

``custom_axis_labels`` and ``persistent_dialog_settings`` are stored
directly on the PlotItem (prefixed with '_') so they survive across
multiple double-click events even though the adapter is re-created
each time.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, glw, plot_item)` | Args: |
| `custom_axis_labels` | `(self)` | Returns: |
| `custom_axis_labels` | `(self, val)` | Args: |
| `persistent_dialog_settings` | `(self)` | Returns: |
| `persistent_dialog_settings` | `(self, val)` | Args: |
| `getPlotItem` | `(self)` | Returns: |
| `backgroundBrush` | `(self)` | Returns: |
| `setBackground` | `(self, color)` | Args: |
| `repaint` | `(self)` |  |
| `parent` | `(self)` | Returns: |

### `EnhancedGraphicsLayoutWidget` *(extends `pg.GraphicsLayoutWidget`)*

GraphicsLayoutWidget with double-click inline editing.

Double-clicking on any subplot opens the same editor dialogs that
EnhancedPlotWidget uses in the main signal window:
• Title label      → TitleEditorDialog
• Left axis        → AxisLabelEditorDialog('left')
• Bottom axis      → AxisLabelEditorDialog('bottom')
• Legend           → LegendEditorDialog
• Background area  → BackgroundEditorDialog

Works correctly across all multi-subplot display modes.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `_plot_item_at` | `(self, scene_pos)` | Return the PlotItem whose bounding rect contains scene_pos. |
| `_adapter_for` | `(self, plot_item)` | Build an adapter for plot_item, syncing legend from it. |
| `_closest_scatter` | `(self, pi, scene_pos, threshold_px = 20)` | Args: |
| `_closest_curve` | `(self, pi, scene_pos, threshold_px = 15)` | Args: |
| `_bar_at` | `(self, pi, scene_pos)` | Return the BarGraphItem the cursor is inside (data-space test). |
| `mouseDoubleClickEvent` | `(self, event)` | Args: |

### `ElementGroupEditor` *(extends `QGroupBox`)*

Widget for defining element groups (sum per particle).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, groups, available_elements, parent = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `_refresh_group_list` | `(self)` |  |
| `_on_group_selected` | `(self, row)` | Args: |
| `_add_group` | `(self)` |  |
| `_remove_group` | `(self)` |  |
| `_on_name_changed` | `(self, text)` | Args: |
| `_on_elements_changed` | `(self)` |  |
| `_pick_color` | `(self)` |  |
| `collect` | `(self)` | Return list of valid groups (with ≥1 element and a name). |

### `HistogramSettingsDialog` *(extends `QDialog`)*

Full settings dialog for histogram node.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config, is_multi, sample_names, parent = None, available_elemen` | Args: |
| `_build_ui` | `(self)` | Returns: |
| `_pick_curve_color` | `(self)` |  |
| `_pick_shade_color_hist` | `(self)` |  |
| `collect` | `(self) → dict` | Returns: |

### `HistogramDisplayDialog` *(extends `QDialog`)*

Full-figure histogram dialog with PyQtGraph and right-click menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, histogram_node, parent_window = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `_ctx_menu` | `(self, pos)` | Args: |
| `_toggle_key` | `(self, key)` | Args: |
| `_set` | `(self, key, value)` | Args: |
| `_get_available_elements` | `(self)` | Get raw element names from input (before grouping). |
| `_open_settings` | `(self)` |  |
| `_open_plot_settings` | `(self)` | Open the full PlotSettingsDialog (font, grid, traces) on the |
| `_download_figure` | `(self)` |  |
| `_refresh` | `(self)` |  |
| `_draw_subplots` | `(self, plot_data, cfg)` | Args: |
| `_draw_side_by_side` | `(self, plot_data, cfg)` | Args: |
| `_draw_overlaid` | `(self, plot_data, cfg)` | Args: |
| `_draw_combined` | `(self, plot_data, cfg)` | Args: |
| `_update_stats` | `(self, plot_data)` | Args: |

### `HistogramPlotNode` *(extends `QObject`)*

Histogram visualization node with element grouping support.

Element groups sum selected element values PER PARTICLE into a
single combined value, then plot the histogram of those sums.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `extract_plot_data` | `(self)` | Extract plottable data, applying element groups when active. |
| `_extract_single` | `(self, dk)` | Args: |
| `_extract_multi` | `(self, dk)` | Args: |

### `BarChartSettingsDialog` *(extends `QDialog`)*

Full settings dialog for element bar chart node.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config, is_multi, sample_names, parent = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `_move_up` | `(self)` |  |
| `_move_down` | `(self)` |  |
| `collect` | `(self) → dict` | Returns: |

### `ElementBarChartDisplayDialog` *(extends `QDialog`)*

Full-figure bar chart dialog with PyQtGraph and right-click context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, bar_node, parent_window = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `_ctx_menu` | `(self, pos)` | Args: |
| `_toggle_key` | `(self, key)` | Args: |
| `_set` | `(self, key, value)` | Args: |
| `_open_settings` | `(self)` |  |
| `_open_plot_settings` | `(self)` | Open the full PlotSettingsDialog (font, grid, traces) on the |
| `_download_figure` | `(self)` | Export bar chart as image or CSV. |
| `_refresh` | `(self)` |  |
| `_draw_subplots` | `(self, plot_data, cfg)` | Args: |
| `_draw_side_by_side` | `(self, plot_data, cfg)` | Args: |
| `_draw_grouped` | `(self, plot_data, cfg)` | Args: |
| `_draw_stacked` | `(self, plot_data, cfg)` | Args: |
| `_draw_by_sample` | `(self, plot_data, cfg)` | X-axis = samples, one bar per element per sample, colors = elements. |
| `_update_stats` | `(self, plot_data)` | Args: |

### `ElementBarChartPlotNode` *(extends `QObject`)*

Element particle-count bar chart node with right-click context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `extract_plot_data` | `(self)` | Extract element particle counts from input. |

## Functions

### `_fmt_elem`

```python
def _fmt_elem(elem: str, cfg: dict) → str
```

Format an element key using the configured label_mode.

'Symbol'        → strip leading mass number  (e.g. '107Ag' → 'Ag')
'Mass + Symbol' → keep as-is                 (e.g. '107Ag')

**Args:**

- `elem (str): The elem.`
- `cfg (dict): The cfg.`

**Returns:**

- `str: Result of the operation.`

### `_get_element_color`

```python
def _get_element_color(element, index, cfg)
```

Get color for an element from config or defaults.

**Args:**

- `element (Any): The element.`
- `index (Any): Row or item index.`
- `cfg (Any): The cfg.`

**Returns:**

- `object: Result of the operation.`

### `_get_element_display_name`

```python
def _get_element_display_name(element, cfg)
```

Get display name for an element (renamed or original).

**Args:**

- `element (Any): The element.`
- `cfg (Any): The cfg.`

**Returns:**

- `object: Result of the operation.`

### `_get_xy_labels`

```python
def _get_xy_labels(cfg)
```

Build x/y label strings.

**Args:**

- `cfg (Any): The cfg.`

**Returns:**

- `tuple: Result of the operation.`

### `_is_multi`

```python
def _is_multi(input_data)
```


**Args:**

- `input_data (Any): The input data.`

**Returns:**

- `object: Result of the operation.`

### `_sample_names`

```python
def _sample_names(input_data)
```


**Args:**

- `input_data (Any): The input data.`

**Returns:**

- `list: Result of the operation.`

### `_can_sum`

```python
def _can_sum(cfg)
```

Check if current data type supports per-particle summation.

**Args:**

- `cfg (Any): The cfg.`

**Returns:**

- `object: Result of the operation.`

### `_apply_element_groups`

```python
def _apply_element_groups(particles, dk, groups)
```

Apply element groups to particle data by summing per particle.


**Args:**

- `particles: list of particle dicts`
- `dk: data key (e.g. 'elements', 'element_mass_fg', ...)`
- `groups: list of group dicts`


**Returns:**

- `dict {display_label: [values]}  where grouped elements are summed`
- `per particle, ungrouped elements kept as-is.`

### `_apply_element_groups_multi`

```python
def _apply_element_groups_multi(particles, sample_names, dk, groups)
```

Apply element groups to multi-sample particle data.


**Returns:**

- `dict {sample_name: {display_label: [values]}}`

**Args:**

- `particles (Any): The particles.`
- `sample_names (Any): The sample names.`
- `dk (Any): The dk.`
- `groups (Any): The groups.`

### `_get_label_color`

```python
def _get_label_color(label, idx, cfg)
```

Get color for a label: check element_colors → group color → default.

**Args:**

- `label (Any): Label text.`
- `idx (Any): The idx.`
- `cfg (Any): The cfg.`

**Returns:**

- `object: Result of the operation.`

### `_prepare_values`

```python
def _prepare_values(values, data_type, log_x)
```

Filter and optionally log-transform histogram values.

**Args:**

- `values (Any): Array or sequence of values.`
- `data_type (Any): The data type.`
- `log_x (Any): The log x.`

**Returns:**

- `object: Result of the operation.`

### `_draw_histogram_bars`

```python
def _draw_histogram_bars(plot_item, values, cfg, color_hex, bins_n = None, name = '')
```

Draw histogram bars using PyQtGraph BarGraphItem.

Returns: (processed_values, bin_edges, counts)

**Args:**

- `plot_item (Any): The plot item.`
- `values (Any): Array or sequence of values.`
- `cfg (Any): The cfg.`
- `color_hex (Any): The color hex.`
- `bins_n (Any): The bins n.`
- `name (Any): Name string.`

### `_add_density_curve`

```python
def _add_density_curve(plot_item, values, cfg, bin_edges, total_count)
```

Add density curve overlay scaled to match count histogram.

**Args:**

- `plot_item (Any): The plot item.`
- `values (Any): Array or sequence of values.`
- `cfg (Any): The cfg.`
- `bin_edges (Any): The bin edges.`
- `total_count (Any): The total count.`

### `_add_median_line`

```python
def _add_median_line(plot_item, values, cfg)
```

Add median vertical line with annotation.

**Args:**

- `plot_item (Any): The plot item.`
- `values (Any): Array or sequence of values.`
- `cfg (Any): The cfg.`

### `_add_stats_text`

```python
def _add_stats_text(plot_item, plot_data, cfg)
```

Add statistics text box to histogram plot.

**Args:**

- `plot_item (Any): The plot item.`
- `plot_data (Any): The plot data.`
- `cfg (Any): The cfg.`

### `_draw_single_histogram`

```python
def _draw_single_histogram(plot_item, element_data, cfg, single_color = None)
```

Draw histogram for one set of element data onto a PyQtGraph PlotItem.

**Args:**

- `plot_item (Any): The plot item.`
- `element_data (Any): The element data.`
- `cfg (Any): The cfg.`
- `single_color (Any): The single color.`

**Returns:**

- `object: Result of the operation.`

### `_sort_elements_for_display`

```python
def _sort_elements_for_display(elements, counts, sort_option)
```

Sort elements by user preference.

**Args:**

- `elements (Any): The elements.`
- `counts (Any): The counts.`
- `sort_option (Any): The sort option.`

**Returns:**

- `tuple: Result of the operation.`

### `_draw_single_bar_chart`

```python
def _draw_single_bar_chart(plot_item, element_counts, cfg, single_color = None, show_y_label = True)
```

Draw bar chart for one set of element counts onto a PyQtGraph PlotItem.

**Args:**

- `plot_item (Any): The plot item.`
- `element_counts (Any): The element counts.`
- `cfg (Any): The cfg.`
- `single_color (Any): The single color.`
- `show_y_label (Any): The show y label.`
