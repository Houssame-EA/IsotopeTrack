# `results_triangle.py`

Ternary Plot Node — full-figure view with right-click context menu.

---

## Constants

| Name | Value |
|------|-------|
| `DISPLAY_MODES` | `['Individual Subplots', 'Combined Plot', 'Overlaid Samples']` |
| `PLOT_TYPES` | `['Scatter Plot', 'Density Plot (Tribin)']` |
| `COLORMAPS` | `['YlGn', 'viridis', 'plasma', 'inferno', 'magma', 'cividi…` |
| `COLOR_PARTICLE_QUANTITY_OPTIONS` | `[('Total Counts', 'total_counts'), ('Total Isotope Mass (…` |
| `COLOR_PARTICLE_QUANTITY_LABELS` | `[x[0] for x in COLOR_PARTICLE_QUANTITY_OPTIONS]` |
| `COLOR_PARTICLE_QUANTITY_KEYS` | `[x[1] for x in COLOR_PARTICLE_QUANTITY_OPTIONS]` |
| `COLOR_ISOTOPE_DATA_TYPE_OPTIONS` | `[('Counts', 'counts'), ('Isotope Mass (fg)', 'element_mas…` |
| `COLOR_ISOTOPE_DATA_TYPE_LABELS` | `[x[0] for x in COLOR_ISOTOPE_DATA_TYPE_OPTIONS]` |
| `COLOR_ISOTOPE_DATA_TYPE_KEYS` | `[x[1] for x in COLOR_ISOTOPE_DATA_TYPE_OPTIONS]` |
| `_COLOR_ISOTOPE_DK_MAP` | `{'counts': 'elements', 'element_mass_fg': 'element_mass_f…` |
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
| `_on_plot_type_changed` | `(self)` | Toggle scatter/tribin sub-sections for both format controls and color encoding groups. |
| `_on_color_mode_changed` | `(self)` | Toggle particle-quantity vs isotope-measurement sub-frames inside scatter color group. |
| `_on_tribin_color_mode_changed` | `(self)` | Show/hide isotope sub-frame inside the tribin color encoding group. |
| `_pick_avg_color` | `(self)` | Pick average-point color used for plot formatting only. |
| `_pick_axis_color` | `(self, which)` | Pick color for a single ternary axis (a, b, or c). |
| `_pick_sample_color` | `(self, name, btn)` | Pick visual color for a sample in multi-sample format settings. |
| `_pick_mean_color` | `(self, name, btn)` | Pick mean marker color for a sample in overlaid mode. |
| `_reset_name` | `(self, original)` | Reset user-facing sample display name to the raw original sample name. |
| `collect` | `(self) → dict` | Collect dialog values for the active scope and preserve untouched config fields. |

### `_ColorSwatch` *(extends `QPushButton`)*

Compact colour-picker button.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, color='#FFFFFF', parent=None)` |  |
| `_update` | `(self)` | Refresh the swatch preview without styling any parent dialog. |
| `color` | `(self)` |  |
| `set_color` | `(self, c)` | Store one validated triangle-preview color and refresh the swatch. |
| `mousePressEvent` | `(self, event)` | Open the shared safe color picker for this swatch on left click. |

### `AnnotationDialog` *(extends `QDialog`)*

Add or edit a single ternary-plot annotation (Text / Marker / Marker+Text).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, ann: dict \| None=None, parent=None)` |  |
| `_build` | `(self)` |  |
| `_on_type_changed` | `(self, t)` |  |
| `_update_sum` | `(self)` |  |
| `_normalize` | `(self)` |  |
| `collect` | `(self) → dict` |  |

### `ManageAnnotationsDialog` *(extends `QDialog`)*

View, edit, reorder and delete existing annotations.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, annotations: list, parent=None)` |  |
| `_build` | `(self)` |  |
| `_reload` | `(self)` |  |
| `_selected_row` | `(self)` |  |
| `_add` | `(self)` |  |
| `_edit` | `(self)` |  |
| `_delete` | `(self)` |  |
| `_move_up` | `(self)` |  |
| `_move_down` | `(self)` |  |
| `collect` | `(self) → list` |  |

### `TriangleDisplayDialog` *(extends `QDialog`)*

Full-figure dialog with right-click context menu for all settings.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, triangle_node, parent_window=None)` |  |
| `_is_multi` | `(self) → bool` |  |
| `_sample_names` | `(self) → list` |  |
| `_single_sample_triangle_zoom_supported` | `(self) → bool` | Return whether ternary zoom is currently supported for single-sample view. |
| `_triangle_viewport_summary` | `(self) → str` | Return a short human-readable summary of the active single-sample viewport. |
| `_enable_ternary_zoom` | `(self)` | Activate ternary zoom: connect our mouse handlers. |
| `_disable_ternary_zoom` | `(self)` | Deactivate ternary zoom: disconnect handlers, clear rubber-band. |
| `_ternary_zoom_clear_rubberband` | `(self, redraw: bool=True)` | Remove rubber-band artist and clear all blit state. |
| `_ternary_xdata_to_abc` | `(xdata: float, ydata: float) → tuple` | Convert mpltern Cartesian projection coords to visual ternary (a, b, c). |
| `_ternary_abc_to_xdata` | `(a: float, b: float, c: float) → tuple` | Convert visual ternary (a, b, c) to mpltern Cartesian (xdata, ydata). |
| `_ternary_main_edge_px` | `(self, ax) → float` | Return the pixel length of the main triangle edge. |
| `_ternary_zoom_on_press` | `(self, event)` | Record anchor vertex and capture blit background. |
| `_ternary_zoom_on_motion` | `(self, event)` | Update rubber-band triangle in-place using blitting. |
| `_ternary_zoom_on_release` | `(self, event)` | On left release, compute final viewport and apply it. |
| `_available_elements` | `(self) → list` |  |
| `_setup_ui` | `(self)` | Build the triangle display UI and wire bottom actions without altering plot logic. |
| `_show_context_menu` | `(self, pos)` | Build the intentionally minimal Triangle right-click menu. |
| `_subplot_under_cursor` | `(self, widget_pos)` | Return the sample key of the subplot under widget_pos, or None. |
| `_examine_sample` | `(self, sample_key)` | Open a full single-sample ternary window for one subplot. |
| `_add_toggle` | `(self, menu, label, key)` |  |
| `_toggle` | `(self, key, value)` |  |
| `_set` | `(self, key, value)` |  |
| `_set_mouse_mode` | `(self, mode: str)` | Update Triangle mouse interaction mode. |
| `_add_annotation` | `(self)` | Open annotation creator; preserves existing annotation data model/behavior. |
| `_manage_annotations` | `(self)` | Open annotation manager; preserves existing annotation ordering/edit behavior. |
| `_open_settings` | `(self)` | Open legacy combined settings dialog to preserve backward-compatible entry point. |
| `_open_plot_format_settings` | `(self)` | Open format-scoped settings dialog. |
| `_open_configure_plot_quantities` | `(self)` | Open quantities-scoped settings dialog. |
| `_reset_layout` | `(self)` | Reset subplot layout/view positions; same behavior as prior reset action. |
| `_export_figure` | `(self)` | Open the existing figure export workflow for the ternary figure. |
| `_refresh` | `(self)` |  |
| `_draw_annotations` | `(self, ax, cfg, viewport=None)` | Render all custom annotations onto a ternary axes. |
| `_save_ann_positions` | `(self, event=None)` | Called on mouse button release — persist dragged text positions back to config. |
| `_update_stats` | `(self, plot_data)` | Update the bottom statistics label. |
| `_open_or_update_stats_table` | `(self)` | Show or refresh the per-sample statistics table for overlaid mode. |
| `_element_filter_mask` | `(a_raw, b_raw, c_raw, cfg)` | Return a boolean mask for the element filter mode. |
| `_auto_colorbar_label` | `(self, cfg, is_tribin=False)` | Return an automatic colorbar label based on plot mode and color encoding config. |
| `_draw_sample` | `(self, ax, sample_data, cfg, title, sample_color=None, viewport=None, ` | Draw a ternary scatter or tribin for one sample. |
| `_draw_average` | `(self, ax, sample_data, cfg, sample_name, viewport=None)` | Draw average point with optional stats text and confidence ellipse. |
| `_draw_average_arrays` | `(self, ax, a_orig, b_orig, c_orig, a_local, b_local, c_local, cfg, sam` | Draw average point, stats text and confidence ellipse from pre-filtered numpy arrays. |
| `_draw_subplots` | `(self, plot_data, cfg)` | Draw one ternary subplot per sample in a 2-column grid |
| `_draw_combined` | `(self, plot_data, cfg)` |  |
| `_draw_overlaid` | `(self, plot_data, cfg)` | Render all samples on a single ternary axes. |

### `TrianglePlotNode` *(extends `QObject`)*

Ternary plot node with right-click driven configuration.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` |  |
| `process_data` | `(self, input_data)` |  |
| `_auto_configure_elements` | `(self)` | Pick first 3 elements from input data. |
| `extract_plot_data` | `(self)` | Extract ternary data — normalised fractions of the three selected elements. |
| `_extract_particles` | `(self, particles, dk, ea, eb, ec)` | Extract ternary points from a list of particle dicts. |
| `_extract_single` | `(self, dk, ea, eb, ec)` |  |
| `_extract_multi` | `(self, dk, ea, eb, ec)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_full_triangle_viewport` | `() → dict` | Return the default full ternary viewport. |
| `_validate_triangle_viewport` | `(viewport: dict \| None) → dict` | Return a sanitized valid ternary viewport or the full viewport. |
| `_is_full_triangle_viewport` | `(viewport: dict, tol: float=1e-12) → bool` | Return whether the viewport matches the full simplex within tolerance. |
| `_viewport_remaining` | `(viewport: dict) → float` | Return the remaining simplex width for a lower-bound ternary viewport. |
| `_point_in_triangle_viewport` | `(a: float, b: float, c: float, viewport: dict, tol: float=1e-09) → boo` | Return whether a ternary point lies inside the viewport. |
| `_remap_point_to_triangle_viewport` | `(a: float, b: float, c: float, viewport: dict) → tuple[float, float, f` | Map original ternary fractions into local viewport fractions. |
| `_viewport_tick_labels` | `(viewport: dict, component_key: str, ticks: list[float]) → list[str]` | Return original-composition percentage labels for local ternary ticks. |
| `setup_ternary_axes` | `(ax, element_labels, config, viewport=None)` | Configure mpltern axes with labels, grid, and font settings. |
| `confidence_ellipse_params` | `(data_x, data_y, n_std=2.0)` | Compute 2D confidence ellipse parameters from data. |
| `_hbox_widget` | `(hbox: QHBoxLayout) → QWidget` |  |
