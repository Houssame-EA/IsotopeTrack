# `results_triangle.py`

Ternary Plot Node — full-figure view with right-click context menu.

---

## Constants

| Name | Value |
|------|-------|
| `DISPLAY_MODES` | `['Individual Subplots', 'Side by Side Subplots', 'Combine…` |
| `PLOT_TYPES` | `['Scatter Plot', 'Density Plot (Hexbin)']` |
| `COLORMAPS` | `['YlGn', 'viridis', 'plasma', 'inferno', 'magma', 'cividi…` |
| `ANNOTATION_MARKERS` | `[('● Circle', 'o'), ('■ Square', 's'), ('▲ Triangle ▲', '…` |
| `_MARKER_NAMES` | `[m[0] for m in ANNOTATION_MARKERS]` |
| `_MARKER_CODES` | `[m[1] for m in ANNOTATION_MARKERS]` |
| `ANN_TYPES` | `['Text', 'Marker', 'Marker + Text']` |
| `_ANN_DEFAULTS` | `{'type': 'Text', 'x_frac': 0.5, 'y_frac': 0.5, 't': 0.33,…` |

## Classes

### `TernarySettingsDialog` *(extends `QDialog`)*

Scoped settings dialog for triangle plot format and quantity configuration.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config, available_elements, is_multi, sample_names, parent=None` | Initialize the triangle settings dialog. |
| `_build_ui` | `(self)` | Build the dialog UI based on scope while preserving existing control behavior. |
| `_on_plot_type_changed` | `(self)` | Toggle scatter/hexbin sub-sections for format controls. |
| `_pick_avg_color` | `(self)` | Pick average-point color used for plot formatting only. |
| `_pick_sample_color` | `(self, name, btn)` | Pick visual color for a sample in multi-sample format settings. |
| `_reset_name` | `(self, original)` | Reset user-facing sample display name to the raw original sample name. |
| `collect` | `(self) → dict` | Collect dialog values for the active scope and preserve untouched config fields. |

### `_ColorSwatch` *(extends `QPushButton`)*

Compact colour-picker button.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, color='#FFFFFF', parent=None)` | Args: |
| `_update` | `(self)` | Refresh the swatch preview without styling any parent dialog. |
| `color` | `(self)` | Returns: |
| `set_color` | `(self, c)` | Store one validated triangle-preview color and refresh the swatch. |
| `mousePressEvent` | `(self, event)` | Open the shared safe color picker for this swatch on left click. |

### `AnnotationDialog` *(extends `QDialog`)*

Add or edit a single ternary-plot annotation (Text / Marker / Marker+Text).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, ann: dict \| None=None, parent=None)` | Args: |
| `_build` | `(self)` |  |
| `_on_type_changed` | `(self, t)` | Args: |
| `_update_sum` | `(self)` |  |
| `_normalize` | `(self)` |  |
| `collect` | `(self) → dict` | Returns: |

### `ManageAnnotationsDialog` *(extends `QDialog`)*

View, edit, reorder and delete existing annotations.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, annotations: list, parent=None)` | Args: |
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
| `__init__` | `(self, triangle_node, parent_window=None)` | Args: |
| `_is_multi` | `(self) → bool` | Returns: |
| `_sample_names` | `(self) → list` | Returns: |
| `_available_elements` | `(self) → list` | Returns: |
| `_setup_ui` | `(self)` | Build the triangle display UI and wire bottom actions without altering plot logic. |
| `_show_context_menu` | `(self, pos)` | Build the intentionally minimal Triangle right-click menu. |
| `_add_toggle` | `(self, menu, label, key)` | Args: |
| `_toggle` | `(self, key, value)` | Args: |
| `_set` | `(self, key, value)` | Args: |
| `_add_annotation` | `(self)` | Open annotation creator; preserves existing annotation data model/behavior. |
| `_manage_annotations` | `(self)` | Open annotation manager; preserves existing annotation ordering/edit behavior. |
| `_open_settings` | `(self)` | Open legacy combined settings dialog to preserve backward-compatible entry point. |
| `_open_plot_format_settings` | `(self)` | Open format-scoped settings dialog. |
| `_open_configure_plot_quantities` | `(self)` | Open quantities-scoped settings dialog. |
| `_reset_layout` | `(self)` | Reset subplot layout/view positions; same behavior as prior reset action. |
| `_export_figure` | `(self)` | Open the existing figure export workflow for the ternary figure. |
| `_refresh` | `(self)` |  |
| `_draw_annotations` | `(self, ax, cfg)` | Render all custom annotations onto a ternary axes. |
| `_save_ann_positions` | `(self, event=None)` | Called on mouse button release — persist dragged text positions back to config. |
| `_update_stats` | `(self, plot_data)` | Update the bottom statistics label. |
| `_draw_sample` | `(self, ax, sample_data, cfg, title, sample_color=None)` | Draw a ternary scatter or hexbin for one sample. |
| `_draw_average` | `(self, ax, sample_data, cfg, sample_name)` | Draw average point with optional stats text and confidence ellipse. |
| `_draw_subplots` | `(self, plot_data, cfg)` | Args: |
| `_draw_side_by_side` | `(self, plot_data, cfg)` | Args: |
| `_draw_combined` | `(self, plot_data, cfg)` | Args: |
| `_draw_overlaid` | `(self, plot_data, cfg)` | Args: |

### `TrianglePlotNode` *(extends `QObject`)*

Ternary plot node with right-click driven configuration.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `_auto_configure_elements` | `(self)` | Pick first 3 elements from input data. |
| `extract_plot_data` | `(self)` | Extract ternary data — normalised fractions of the three selected elements. |
| `_extract_particles` | `(self, particles, dk, ea, eb, ec, color_elem)` | Extract ternary points from a list of particle dicts. |
| `_extract_single` | `(self, dk, ea, eb, ec, color_elem)` | Args: |
| `_extract_multi` | `(self, dk, ea, eb, ec, color_elem)` | Args: |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `setup_ternary_axes` | `(ax, element_labels, config)` | Configure mpltern axes with labels, grid, and font settings. |
| `confidence_ellipse_params` | `(data_x, data_y, n_std=2.0)` | Compute 2D confidence ellipse parameters from data. |
| `_hbox_widget` | `(hbox: QHBoxLayout) → QWidget` | Args: |
