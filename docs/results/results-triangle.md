# `results_triangle.py`

Ternary Plot Node — full-figure view with right-click context menu.

Features:
- Three-element ternary composition diagram (mpltern)
- Scatter and density (hexbin) plot types
- Color-by-fourth-element option for scatter plots
- Average point with optional 2σ confidence ellipse
- Particle statistics bar (total, filtered, per-sample)
- Multiple sample support (overlaid, subplots, side-by-side, combined)
- Right-click context menu replaces sidebar for all settings
- Shared font, color, and export utilities via shared_plot_utils

---

## Constants

| Name | Value |
|------|-------|
| `DISPLAY_MODES` | `['Individual Subplots', 'Side by Side Subplots'...` |
| `PLOT_TYPES` | `['Scatter Plot', 'Density Plot (Hexbin)']` |
| `COLORMAPS` | `['YlGn', 'viridis', 'plasma', 'inferno', 'magma...` |
| `ANNOTATION_MARKERS` | `[('● Circle', 'o'), ('■ Square', 's'), ('▲ Tria...` |
| `_MARKER_NAMES` | `[m[0] for m in ANNOTATION_MARKERS]` |
| `_MARKER_CODES` | `[m[1] for m in ANNOTATION_MARKERS]` |
| `ANN_TYPES` | `['Text', 'Marker', 'Marker + Text']` |
| `_ANN_DEFAULTS` | `{'type': 'Text', 'x_frac': 0.5, 'y_frac': 0.5, ...` |

## Classes

### `TernarySettingsDialog` *(extends `QDialog`)*

Full settings dialog opened from right-click → Configure.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config, available_elements, is_multi, sample_names, parent = No` | Args: |
| `_build_ui` | `(self)` |  |
| `_on_plot_type_changed` | `(self)` |  |
| `_pick_avg_color` | `(self)` |  |
| `_pick_sample_color` | `(self, name, btn)` | Args: |
| `_reset_name` | `(self, original)` | Args: |
| `collect` | `(self) → dict` | Returns: |

### `_ColorSwatch` *(extends `QPushButton`)*

Compact colour-picker button.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, color = '#FFFFFF', parent = None)` | Args: |
| `_update` | `(self)` |  |
| `color` | `(self)` | Returns: |
| `set_color` | `(self, c)` | Args: |
| `mousePressEvent` | `(self, event)` | Args: |

### `AnnotationDialog` *(extends `QDialog`)*

Add or edit a single ternary-plot annotation (Text / Marker / Marker+Text).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, ann: dict | None = None, parent = None)` | Args: |
| `_build` | `(self)` |  |
| `_on_type_changed` | `(self, t)` | Args: |
| `_update_sum` | `(self)` |  |
| `_normalize` | `(self)` |  |
| `collect` | `(self) → dict` | Returns: |

### `ManageAnnotationsDialog` *(extends `QDialog`)*

View, edit, reorder and delete existing annotations.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, annotations: list, parent = None)` | Args: |
| `_build` | `(self)` |  |
| `_reload` | `(self)` |  |
| `_selected_row` | `(self)` | Returns: |
| `_add` | `(self)` |  |
| `_edit` | `(self)` |  |
| `_delete` | `(self)` |  |
| `_move_up` | `(self)` |  |
| `_move_down` | `(self)` |  |
| `collect` | `(self) → list` | Returns: |

### `TriangleDisplayDialog` *(extends `QDialog`)*

Full-figure dialog with right-click context menu for all settings.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, triangle_node, parent_window = None)` | Args: |
| `_is_multi` | `(self) → bool` | Returns: |
| `_sample_names` | `(self) → list` | Returns: |
| `_available_elements` | `(self) → list` | Returns: |
| `_setup_ui` | `(self)` |  |
| `_show_context_menu` | `(self, pos)` | Args: |
| `_add_toggle` | `(self, menu, label, key)` | Args: |
| `_toggle` | `(self, key, value)` | Args: |
| `_set` | `(self, key, value)` | Args: |
| `_add_annotation` | `(self)` |  |
| `_manage_annotations` | `(self)` |  |
| `_open_settings` | `(self)` |  |
| `_reset_layout` | `(self)` |  |
| `_export_figure` | `(self)` |  |
| `_refresh` | `(self)` |  |
| `_draw_annotations` | `(self, ax, cfg)` | Render all custom annotations onto a ternary axes. |
| `_save_ann_positions` | `(self, event = None)` | Called on mouse button release — persist dragged text positions back to config. |
| `_update_stats` | `(self, plot_data)` | Update the bottom statistics label. |
| `_draw_sample` | `(self, ax, sample_data, cfg, title, sample_color = None)` | Draw a ternary scatter or hexbin for one sample. |
| `_draw_average` | `(self, ax, sample_data, cfg, sample_name)` | Draw average point with optional stats text and confidence ellipse. |
| `_draw_subplots` | `(self, plot_data, cfg)` | Args: |
| `_draw_side_by_side` | `(self, plot_data, cfg)` | Args: |
| `_draw_combined` | `(self, plot_data, cfg)` | Args: |
| `_draw_overlaid` | `(self, plot_data, cfg)` | Args: |

### `TrianglePlotNode` *(extends `QObject`)*

Ternary plot node with right-click driven configuration.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `_auto_configure_elements` | `(self)` | Pick first 3 elements from input data. |
| `extract_plot_data` | `(self)` | Extract ternary data — normalised fractions of the three selected elements. |
| `_extract_particles` | `(self, particles, dk, ea, eb, ec, color_elem)` | Extract ternary points from a list of particle dicts. |
| `_extract_single` | `(self, dk, ea, eb, ec, color_elem)` | Args: |
| `_extract_multi` | `(self, dk, ea, eb, ec, color_elem)` | Args: |

## Functions

### `setup_ternary_axes`

```python
def setup_ternary_axes(ax, element_labels, config)
```

Configure mpltern axes with labels, grid, and font settings.

Ternary coordinate mapping (mpltern convention):
L (left)   = element A = bottom-left vertex
R (right)  = element B = bottom-right vertex
T (top)    = element C = top vertex


**Args:**

- `ax:             mpltern axes (projection='ternary')`
- `element_labels: [elem_a, elem_b, elem_c]`
- `config:         node config dict`

### `confidence_ellipse_params`

```python
def confidence_ellipse_params(data_x, data_y, n_std = 2.0)
```

Compute 2D confidence ellipse parameters from data.

Performs eigendecomposition of the covariance matrix to get the orientation
and semi-axes of the n_std confidence region.


**Args:**

- `data_x:  array of x-coordinates (e.g. b_vals in ternary space)`
- `data_y:  array of y-coordinates (e.g. c_vals in ternary space)`
- `n_std:   number of standard deviations (2.0 ≈ 95% for bivariate normal)`


**Returns:**

- `dict with cx, cy, width, height, angle_deg — or None if < 3 points.`

### `_hbox_widget`

```python
def _hbox_widget(hbox: QHBoxLayout) → QWidget
```


**Args:**

- `hbox (QHBoxLayout): The hbox.`

**Returns:**

- `QWidget: Result of the operation.`
