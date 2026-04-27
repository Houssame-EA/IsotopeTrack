# `results_molar_ratio.py`

---

## Constants

| Name | Value |
|------|-------|
| `MOLAR_DATA_TYPES` | `['Element Moles (fmol)', 'Particle Moles (fmol)']` |
| `MOLAR_DATA_KEY_MAP` | `{'Element Moles (fmol)': 'element_moles_fmol', ...` |
| `MR_DISPLAY_MODES` | `['Overlaid (Different Colors)', 'Side by Side S...` |
| `ZERO_HANDLING` | `['Skip particles with zero values', 'Replace ze...` |
| `SHADE_TYPES` | `['None', 'Mean ± 1 SD', 'Mean ± 2 SD', 'Median ...` |
| `DEFAULT_CONFIG` | `{'data_type_display': 'Element Moles (fmol)', '...` |
| `_QT_LINE` | `{'solid': pg.QtCore.Qt.SolidLine, 'dash': pg.Qt...` |

## Classes

### `MolarRatioSettingsDialog` *(extends `QDialog`)*

Full settings dialog opened from context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, available_elements, parent = None)` | Args: |
| `_build_ui` | `(self)` | Returns: |
| `_move_up` | `(self)` |  |
| `_move_down` | `(self)` |  |
| `_pick_shade_color` | `(self)` |  |
| `collect` | `(self)` | Returns: |

### `MolarRatioDisplayDialog` *(extends `QDialog`)*

Main dialog with PyQtGraph plot and right-click context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `_refresh_hint` | `(self)` | Show hint only when the plot has zero annotations. |
| `_ctx_menu` | `(self, pos)` | Args: |
| `_current_ratios` | `(self)` | Return a 1-D numpy array of all current ratio values (pooled across |
| `_toggle` | `(self, key)` | Args: |
| `_set` | `(self, key, value)` | Args: |
| `_open_settings` | `(self)` |  |
| `_open_plot_settings` | `(self)` |  |
| `_refresh` | `(self)` |  |
| `_draw_single` | `(self, pi, ratios, cfg)` | Args: |
| `_draw_overlaid` | `(self, pi, plot_data, cfg)` | Args: |
| `_draw_subplots` | `(self, plot_data, cfg)` | Args: |
| `_draw_side_by_side` | `(self, plot_data, cfg)` | Args: |
| `_update_stats` | `(self, plot_data, multi)` | Args: |

### `MolarRatioPlotNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `extract_available_elements` | `(self)` | Returns: |
| `extract_plot_data` | `(self)` | Returns: |
| `_compute_ratios` | `(self, particles, dk, num, den)` | Args: |
| `_extract_single` | `(self, dk, num, den)` | Args: |
| `_extract_multi` | `(self, dk, num, den)` | Args: |

## Functions

### `_is_multi`

```python
def _is_multi(input_data)
```


**Args:**

- `input_data (Any): The input data.`

**Returns:**

- `object: Result of the operation.`

### `_xy_labels`

```python
def _xy_labels(cfg)
```


**Args:**

- `cfg (Any): The cfg.`

**Returns:**

- `tuple: Result of the operation.`

### `_draw_histogram_bars`

```python
def _draw_histogram_bars(plot_item, ratios, cfg, color)
```

Draw histogram bars for ratio values.

**Args:**

- `plot_item (Any): The plot item.`
- `ratios (Any): The ratios.`
- `cfg (Any): The cfg.`
- `color (Any): Colour value.`

**Returns:**

- `tuple: Result of the operation.`

### `_add_density_curve`

```python
def _add_density_curve(plot_item, values, cfg, edges, total)
```

KDE density curve scaled to histogram counts.

**Args:**

- `plot_item (Any): The plot item.`
- `values (Any): Array or sequence of values.`
- `cfg (Any): The cfg.`
- `edges (Any): The edges.`
- `total (Any): The total.`

### `_apply_box`

```python
def _apply_box(plot_item, cfg)
```

Show or hide the figure frame (top + right axes = closed box).

**Args:**

- `plot_item (Any): The plot item.`
- `cfg (Any): The cfg.`

### `_add_ref_line`

```python
def _add_ref_line(plot_item, cfg)
```

Draw a customisable reference vertical line (e.g. ratio = 1).

**Args:**

- `plot_item (Any): The plot item.`
- `cfg (Any): The cfg.`

### `_add_stat_lines`

```python
def _add_stat_lines(plot_item, values, cfg)
```

Draw median / mean / mode marker lines.

``values`` must already be in plot-space (log10 if log_x is True).
Lines are drawn as pg.InfiniteLine with built-in labels — no floating
TextItem so they can't be mispositioned by view-range race conditions.
Colors, styles and widths are all customisable via cfg.

**Args:**

- `plot_item (Any): The plot item.`
- `values (Any): Array or sequence of values.`
- `cfg (Any): The cfg.`

### `_add_shaded_region`

```python
def _add_shaded_region(plot_item, values, cfg)
```

Draw a statistical shaded band — applied to every subplot.

``values`` must already be in plot-space (log10 if log_x is True).

**Args:**

- `plot_item (Any): The plot item.`
- `values (Any): Array or sequence of values.`
- `cfg (Any): The cfg.`

**Returns:**

- `object: Result of the operation.`

### `_add_stats_text`

```python
def _add_stats_text(plot_item, ratios, cfg)
```

Add statistics text box.

**Args:**

- `plot_item (Any): The plot item.`
- `ratios (Any): The ratios.`
- `cfg (Any): The cfg.`

### `_draw_ratio_plot`

```python
def _draw_ratio_plot(plot_item, ratios, cfg, color)
```

Draw a complete ratio histogram with overlays (applied to every subplot).

**Args:**

- `plot_item (Any): The plot item.`
- `ratios (Any): The ratios.`
- `cfg (Any): The cfg.`
- `color (Any): Colour value.`
