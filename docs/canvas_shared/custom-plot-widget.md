# `custom_plot_widget.py`

---

## Constants

| Name | Value |
|------|-------|
| `LINE_STYLE_MAP` | `{'Solid': Qt.SolidLine, 'Dash': Qt.DashLine, 'Dot': Qt.Do…` |
| `LINE_STYLE_REVERSE` | `{v: k for k, v in LINE_STYLE_MAP.items()}` |
| `SCATTER_SYMBOLS` | `{'Circle': 'o', 'Square': 's', 'Triangle Up': 't', 'Trian…` |
| `SCATTER_SYMBOLS_REVERSE` | `{v: k for k, v in SCATTER_SYMBOLS.items()}` |

## Classes

### `TraceEditorDialog` *(extends `QDialog`)*

Edit a single trace: color, width, line style, legend name.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, curve_item, plot_widget, parent=None)` |  |
| `_setup_ui` | `(self)` |  |
| `_refresh_color_btn` | `(self)` |  |
| `_pick_color` | `(self)` |  |
| `_apply` | `(self)` |  |

### `ScatterEditorDialog` *(extends `QDialog`)*

Edit scatter points: fill color, symbol shape, size.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, scatter_item, plot_widget, parent=None)` |  |
| `_setup_ui` | `(self)` |  |
| `_pick_color` | `(self)` |  |
| `_apply` | `(self)` |  |

### `AxisLabelEditorDialog` *(extends `QDialog`)*

Edit an axis label: text, units, font, size, bold/italic, color.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, plot_widget, axis_name, parent=None)` |  |
| `_setup_ui` | `(self)` |  |
| `_pick_color` | `(self)` | Select a color for the axis label text. |
| `_apply` | `(self)` | Apply axis label text plus explicit styling to the target axis. |

### `TitleEditorDialog` *(extends `QDialog`)*

Edit the plot title.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, plot_widget, parent=None, text_only: bool=False, title_apply_ca` |  |
| `_setup_ui` | `(self)` | Build the title editor controls for the current plot widget. |
| `_pick_color` | `(self)` | Select a title text color for the styled editor mode. |
| `_apply` | `(self)` | Apply the edited title text, with optional style controls. |

### `LegendEditorDialog` *(extends `QDialog`)*

Edit legend appearance.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, plot_widget, parent=None)` |  |
| `_setup_ui` | `(self)` |  |
| `_pick_color` | `(self)` |  |
| `_apply` | `(self)` |  |

### `BackgroundEditorDialog` *(extends `QDialog`)*

Edit background color and grid.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, plot_widget, parent=None)` |  |
| `_setup_ui` | `(self)` |  |
| `_pick_bg` | `(self)` |  |
| `_apply` | `(self)` |  |

### `PlotSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, plot_widget, parent=None, show_apply: bool=True, allow_title_te` | Preserved behavior: |
| `_setup_ui` | `(self)` | Build PlotSettings tabs and bottom action buttons. |
| `_create_font_tab` | `(self)` | Build global text-format controls for the current plot widget. |
| `_create_grid_tab` | `(self)` |  |
| `_create_traces_tab` | `(self)` |  |
| `_populate_traces` | `(self)` |  |
| `_curve_row` | `(self, item, index)` |  |
| `_scatter_row` | `(self, item, index)` |  |
| `_bar_row` | `(self, name, items, index)` | One row in the Traces tab for a group of BarGraphItems that |
| `_toggle_particle_scatter` | `(self, checked: bool)` | Show or hide all particle integration scatter items on the plot. |
| `_choose_color` | `(self, color_type)` |  |
| `_load_persistent` | `(self)` | Restore shared plot-format state from the target plot widget. |
| `_save_persistent` | `(self)` | Persist shared plot-format state back onto the target plot widget. |
| `_apply_settings` | `(self)` | Apply shared global plot-format settings to the live plot widget. |
| `_reset_defaults` | `(self)` | Reset shared plot-format controls to their default values. |
| `_accept_and_apply` | `(self)` |  |
| `closeEvent` | `(self, event)` |  |

### `CustomPlotItem` *(extends `pg.PlotItem`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, *args, **kwargs)` |  |
| `getContextMenus` | `(self, event)` |  |

### `ExclusionRegion` *(extends `pg.LinearRegionItem`)*

A vertical shaded band marking an excluded X-range.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, values, owner, scope='element')` |  |
| `scope` | `(self)` |  |
| `set_scope` | `(self, scope)` | Change scope in-place (updates the visual styling). |
| `mouseClickEvent` | `(self, ev)` |  |
| `_show_context_menu` | `(self, ev)` |  |
| `_edit_bounds_dialog` | `(self)` |  |

### `EnhancedPlotWidget` *(extends `pg.PlotWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `setup_appearance` | `(self)` |  |
| `apply_theme` | `(self, *args)` | Repaint background and all foreground elements (axes, tick text, |
| `_style_legend` | `(self, legend)` | Apply theme colors to a legend (text, background, border). |
| `setup_interaction_features` | `(self)` |  |
| `_install_autorange_button` | `(self)` | Overlay a small auto-scale button in the top-right corner. |
| `_reposition_autorange_btn` | `(self)` |  |
| `resizeEvent` | `(self, event)` |  |
| `_install_exclusion_context_menu` | `(self)` | Add 'Add exclusion region here (this element / whole sample)' and |
| `_capture_context_menu_position` | `(self)` | Cache the data-X under the cursor when the context menu opens. |
| `_add_exclusion_region_at_cursor` | `(self, scope='element')` | Create a new band centred on the last right-click X-position. |
| `add_exclusion_region` | `(self, x_min, x_max, scope='element')` | Add a new exclusion band spanning [x_min, x_max] (data coords). |
| `remove_exclusion_region` | `(self, region)` | Remove a single exclusion band. Emits exclusionRegionsChanged. |
| `clear_exclusion_regions` | `(self)` | Remove every exclusion band. Emits exclusionRegionsChanged. |
| `get_exclusion_regions` | `(self)` | Return excluded X-ranges as a list of (x_min, x_max, scope). |
| `set_exclusion_regions` | `(self, regions)` | Replace the current set of exclusion bands with the given list. |
| `get_exclusion_mask` | `(self, x_array)` | Boolean mask the same length as `x_array`. |
| `_on_region_edited` | `(self, *_)` |  |
| `_emit_exclusion_changed` | `(self)` |  |
| `clear` | `(self)` |  |
| `open_plot_settings` | `(self)` |  |
| `mouseDoubleClickEvent` | `(self, event)` | Hit-detection priority: |
| `_find_closest_scatter` | `(self, scene_pos, threshold_px=20)` |  |
| `_find_closest_curve` | `(self, scene_pos, threshold_px=15)` |  |
| `wheelEvent` | `(self, event)` |  |
| `update_plot` | `(self, time_array, data)` |  |
| `mouse_moved` | `(self, pos)` |  |
| `clear_plot` | `(self)` |  |

### `BasicPlotWidget` *(extends `pg.PlotWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `setup_basic_appearance` | `(self)` |  |
| `_install_autorange_button` | `(self)` |  |
| `_reposition_autorange_btn` | `(self)` |  |
| `resizeEvent` | `(self, event)` |  |
| `update_plot` | `(self, time_array, data)` |  |
| `clear_plot` | `(self)` |  |
| `setTitle` | `(self, title)` |  |

### `CalibrationPlotWidget` *(extends `EnhancedPlotWidget`)*

Calibration plot with interactive exclusion of outlier points.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `setup_interaction_features` | `(self)` | Override: calibration plot uses no crosshair lines. |
| `_setup_calibration_appearance` | `(self)` |  |
| `_build_calibration_items` | `(self)` |  |
| `setLabel` | `(self, axis, text, units=None, color=None, font=None)` |  |
| `setTitle` | `(self, title)` |  |
| `update_plot` | `(self, x_data, y_data, y_std, method='zero', y_fit=None, key='Data', *` | Refresh the plot with new data. |
| `clear_plot` | `(self)` |  |
| `mouseDoubleClickEvent` | `(self, event)` |  |
| `_redraw_markers` | `(self)` |  |
| `_redraw_fit_line` | `(self)` |  |
| `_redraw_equation` | `(self)` |  |
| `_reposition_equation` | `(self)` |  |
| `_on_scatter_clicked` | `(self, _plot, points, event=None)` | A single press on a scatter fires this. We queue the |
| `_emit_pending_click` | `(self)` |  |

### `BarEditorDialog` *(extends `QDialog`)*

Simple editor for a single m/z bar: fill color.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, meta, parent=None)` |  |
| `_setup_ui` | `(self)` |  |
| `_pick_fill` | `(self)` |  |
| `_apply` | `(self)` |  |

### `MzBarPlotWidget` *(extends `pg.PlotWidget`)*

Drop-in pg.PlotWidget for the inline m/z bar chart.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `open_plot_settings` | `(self)` |  |
| `set_bar_meta` | `(self, meta)` | Store per-bar metadata dicts for hit-testing on double-click. |
| `mouseDoubleClickEvent` | `(self, event)` | Hit-detection priority (same order as EnhancedPlotWidget): |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_editor_dialog_qss` | `()` | Stylesheet applied to every small plot editor dialog |
| `_editor_header_qss` | `()` | Header label at the top of each editor dialog (was '#2c3e50' bold). |
| `_editor_ok_button_qss` | `()` | Primary OK/Apply button. Was hardcoded #3498db → #2980b9. |
| `_editor_cancel_button_qss` | `()` | Neutral Cancel button. Was hardcoded #95a5a6 → #7f8c8d. |
| `_color_swatch_qss` | `(hex_color)` | Small color picker swatch. hex_color may be any valid CSS color. |
| `_tall_color_swatch_qss` | `(hex_color)` | Full-width color swatch used in the PlotSettingsDialog form rows |
| `_hint_label_qss` | `()` | Italic tip / hint labels (the 'Double-click any element…' line and |
| `_trace_row_qss` | `()` | Per-trace row background on the Traces tab (formerly hardcoded white |
| `_scatter_row_qss` | `()` | Per-scatter row background on the Traces tab (formerly cream `#fff8f0` |
| `_inline_apply_btn_qss` | `(variant='primary')` | Small 'Apply' button rendered inside each trace/scatter row. |
| `_install_theme_subscription` | `(dialog)` | Attach the editor_dialog_qss to a dialog AND keep it updated when the |
| `get_system_font_families` | `()` | Get available system font families from Qt font database, |
