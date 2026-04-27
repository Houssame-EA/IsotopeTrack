# `custom_plot_widget.py`

---

## Constants

| Name | Value |
|------|-------|
| `LINE_STYLE_MAP` | `{'Solid': Qt.SolidLine, 'Dash': Qt.DashLine, 'D...` |
| `LINE_STYLE_REVERSE` | `{v: k for k, v in LINE_STYLE_MAP.items()}` |
| `SCATTER_SYMBOLS` | `{'Circle': 'o', 'Square': 's', 'Triangle Up': '...` |
| `SCATTER_SYMBOLS_REVERSE` | `{v: k for k, v in SCATTER_SYMBOLS.items()}` |

## Classes

### `TraceEditorDialog` *(extends `QDialog`)*

Edit a single trace: color, width, line style, legend name.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, curve_item, plot_widget, parent = None)` | Args: |
| `_setup_ui` | `(self)` |  |
| `_refresh_color_btn` | `(self)` |  |
| `_pick_color` | `(self)` |  |
| `_apply` | `(self)` |  |

### `ScatterEditorDialog` *(extends `QDialog`)*

Edit scatter points: fill color, symbol shape, size.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, scatter_item, plot_widget, parent = None)` | Args: |
| `_setup_ui` | `(self)` |  |
| `_pick_color` | `(self)` |  |
| `_apply` | `(self)` |  |

### `AxisLabelEditorDialog` *(extends `QDialog`)*

Edit an axis label: text, units, font, size, bold/italic, color.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, plot_widget, axis_name, parent = None)` | Args: |
| `_setup_ui` | `(self)` |  |
| `_pick_color` | `(self)` |  |
| `_apply` | `(self)` |  |

### `TitleEditorDialog` *(extends `QDialog`)*

Edit the plot title.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, plot_widget, parent = None)` | Args: |
| `_setup_ui` | `(self)` |  |
| `_pick_color` | `(self)` |  |
| `_apply` | `(self)` |  |

### `LegendEditorDialog` *(extends `QDialog`)*

Edit legend appearance.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, plot_widget, parent = None)` | Args: |
| `_setup_ui` | `(self)` |  |
| `_pick_color` | `(self)` |  |
| `_apply` | `(self)` |  |

### `BackgroundEditorDialog` *(extends `QDialog`)*

Edit background color and grid.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, plot_widget, parent = None)` | Args: |
| `_setup_ui` | `(self)` |  |
| `_pick_bg` | `(self)` |  |
| `_apply` | `(self)` |  |

### `PlotSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, plot_widget, parent = None)` | Args: |
| `_setup_ui` | `(self)` |  |
| `_create_font_tab` | `(self)` |  |
| `_create_grid_tab` | `(self)` |  |
| `_create_traces_tab` | `(self)` |  |
| `_populate_traces` | `(self)` |  |
| `_curve_row` | `(self, item, index)` | Args: |
| `_scatter_row` | `(self, item, index)` | Args: |
| `_bar_row` | `(self, name, items, index)` | One row in the Traces tab for a group of BarGraphItems that |
| `_choose_color` | `(self, color_type)` | Args: |
| `_load_persistent` | `(self)` |  |
| `_save_persistent` | `(self)` |  |
| `_apply_settings` | `(self)` |  |
| `_reset_defaults` | `(self)` |  |
| `_accept_and_apply` | `(self)` |  |
| `closeEvent` | `(self, event)` | Args: |

### `CustomPlotItem` *(extends `pg.PlotItem`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, *args, **kwargs)` | Args: |
| `getContextMenus` | `(self, event)` | Args: |

### `ExclusionRegion` *(extends `pg.LinearRegionItem`)*

A vertical shaded band marking an excluded X-range.

Each region carries a ``scope``:
- ``'element'`` : applies only to the element currently displayed.
Drawn with a red dashed outline.
- ``'sample'``  : applies to every element in the active sample.
Drawn with a thicker blue solid outline so it is
visually distinct from element-scope bands.

Drag the middle to move, drag the edges to resize. Right-click on
the band for a small menu (Remove / Edit bounds / Change scope /
Clear all). The widget that owns this region is held as ``_owner``
so the region can ask the owner to apply the chosen action.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, values, owner, scope = 'element')` | Args: |
| `scope` | `(self)` | Returns: |
| `set_scope` | `(self, scope)` | Change scope in-place (updates the visual styling). |
| `mouseClickEvent` | `(self, ev)` | Args: |
| `_show_context_menu` | `(self, ev)` | Args: |
| `_edit_bounds_dialog` | `(self)` |  |

### `EnhancedPlotWidget` *(extends `pg.PlotWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `setup_appearance` | `(self)` |  |
| `setup_interaction_features` | `(self)` |  |
| `_install_autorange_button` | `(self)` | Overlay a small auto-scale button in the top-right corner. |
| `_reposition_autorange_btn` | `(self)` |  |
| `resizeEvent` | `(self, event)` | Args: |
| `_install_exclusion_context_menu` | `(self)` | Add 'Add exclusion region here (this element / whole sample)' and |
| `_capture_context_menu_position` | `(self)` | Cache the data-X under the cursor when the context menu opens. |
| `_add_exclusion_region_at_cursor` | `(self, scope = 'element')` | Create a new band centred on the last right-click X-position. |
| `add_exclusion_region` | `(self, x_min, x_max, scope = 'element')` | Add a new exclusion band spanning [x_min, x_max] (data coords). |
| `remove_exclusion_region` | `(self, region)` | Remove a single exclusion band. Emits exclusionRegionsChanged. |
| `clear_exclusion_regions` | `(self)` | Remove every exclusion band. Emits exclusionRegionsChanged. |
| `get_exclusion_regions` | `(self)` | Return excluded X-ranges as a list of (x_min, x_max, scope). |
| `set_exclusion_regions` | `(self, regions)` | Replace the current set of exclusion bands with the given list. |
| `get_exclusion_mask` | `(self, x_array)` | Boolean mask the same length as `x_array`. |
| `_on_region_edited` | `(self, *_)` | Args: |
| `_emit_exclusion_changed` | `(self)` |  |
| `clear` | `(self)` |  |
| `open_plot_settings` | `(self)` |  |
| `mouseDoubleClickEvent` | `(self, event)` | Hit-detection priority: |
| `_find_closest_scatter` | `(self, scene_pos, threshold_px = 20)` | Args: |
| `_find_closest_curve` | `(self, scene_pos, threshold_px = 15)` | Args: |
| `wheelEvent` | `(self, event)` | Args: |
| `update_plot` | `(self, time_array, data)` | Args: |
| `mouse_moved` | `(self, pos)` | Args: |
| `clear_plot` | `(self)` |  |

### `BasicPlotWidget` *(extends `pg.PlotWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `setup_basic_appearance` | `(self)` |  |
| `_install_autorange_button` | `(self)` |  |
| `_reposition_autorange_btn` | `(self)` |  |
| `resizeEvent` | `(self, event)` | Args: |
| `update_plot` | `(self, time_array, data)` | Args: |
| `clear_plot` | `(self)` |  |
| `setTitle` | `(self, title)` | Args: |

### `CalibrationPlotWidget` *(extends `EnhancedPlotWidget`)*

Calibration plot with interactive exclusion of outlier points.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `setup_interaction_features` | `(self)` | Override: calibration plot uses no crosshair lines. |
| `_setup_calibration_appearance` | `(self)` |  |
| `_build_calibration_items` | `(self)` |  |
| `setLabel` | `(self, axis, text, units = None, color = None, font = None)` | Args: |
| `setTitle` | `(self, title)` | Args: |
| `update_plot` | `(self, x_data, y_data, y_std, method = 'zero', y_fit = None, key = 'Da` | Refresh the plot with new data. |
| `clear_plot` | `(self)` |  |
| `mouseDoubleClickEvent` | `(self, event)` | Args: |
| `_redraw_markers` | `(self)` |  |
| `_redraw_fit_line` | `(self)` |  |
| `_redraw_equation` | `(self)` |  |
| `_reposition_equation` | `(self)` |  |
| `_on_scatter_clicked` | `(self, _plot, points, event = None)` | A single press on a scatter fires this. We queue the |
| `_emit_pending_click` | `(self)` |  |

### `BarEditorDialog` *(extends `QDialog`)*

Simple editor for a single m/z bar: fill color.

Operates directly on the bar meta-dict so changes are immediately
reflected in the chart and survive subsequent data refreshes.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, meta, parent = None)` | Args: |
| `_setup_ui` | `(self)` |  |
| `_pick_fill` | `(self)` |  |
| `_apply` | `(self)` |  |

### `MzBarPlotWidget` *(extends `pg.PlotWidget`)*

Drop-in pg.PlotWidget for the inline m/z bar chart.

Gives the same double-click-to-edit experience as EnhancedPlotWidget:

Double-click title       → TitleEditorDialog
Double-click left axis   → AxisLabelEditorDialog('left')
Double-click bottom axis → AxisLabelEditorDialog('bottom')
Double-click a bar       → BarEditorDialog  (fill color)
Double-click empty area  → BackgroundEditorDialog
Right-click anywhere     → 'Plot Settings…' → PlotSettingsDialog
(Font + Grid tabs; Traces tab omitted
because bars are not PlotDataItem objects)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `open_plot_settings` | `(self)` |  |
| `set_bar_meta` | `(self, meta)` | Store per-bar metadata dicts for hit-testing on double-click. |
| `mouseDoubleClickEvent` | `(self, event)` | Hit-detection priority (same order as EnhancedPlotWidget): |

## Functions

### `_editor_dialog_qss`

```python
def _editor_dialog_qss()
```

Stylesheet applied to every small plot editor dialog
(TraceEditor, ScatterEditor, AxisLabelEditor, TitleEditor,
LegendEditor, BackgroundEditor, etc). Pulls from the current theme.

**Returns:**

- `object: Result of the operation.`

### `_editor_header_qss`

```python
def _editor_header_qss()
```

Header label at the top of each editor dialog (was '#2c3e50' bold).

**Returns:**

- `object: Result of the operation.`

### `_editor_ok_button_qss`

```python
def _editor_ok_button_qss()
```

Primary OK/Apply button. Was hardcoded #3498db → #2980b9.

**Returns:**

- `object: Result of the operation.`

### `_editor_cancel_button_qss`

```python
def _editor_cancel_button_qss()
```

Neutral Cancel button. Was hardcoded #95a5a6 → #7f8c8d.

**Returns:**

- `object: Result of the operation.`

### `_color_swatch_qss`

```python
def _color_swatch_qss(hex_color)
```

Small color picker swatch. hex_color may be any valid CSS color.

**Args:**

- `hex_color (Any): The hex color.`

**Returns:**

- `object: Result of the operation.`

### `_tall_color_swatch_qss`

```python
def _tall_color_swatch_qss(hex_color)
```

Full-width color swatch used in the PlotSettingsDialog form rows
(font color / background color / grid color). Keeps the border
theme-aware so the button doesn't look pasted-on in dark mode.

**Args:**

- `hex_color (Any): The hex color.`

**Returns:**

- `object: Result of the operation.`

### `_hint_label_qss`

```python
def _hint_label_qss()
```

Italic tip / hint labels (the 'Double-click any element…' line and
the 'Edit all traces…' header on the Traces tab). Used to be hardcoded
#555/#666/#999 which is unreadable in dark mode.

**Returns:**

- `object: Result of the operation.`

### `_trace_row_qss`

```python
def _trace_row_qss()
```

Per-trace row background on the Traces tab (formerly hardcoded white
`#fff`). Uses the theme's tertiary surface in both light and dark mode,
with a left-edge accent bar to visually distinguish it from scatter rows.

**Returns:**

- `object: Result of the operation.`

### `_scatter_row_qss`

```python
def _scatter_row_qss()
```

Per-scatter row background on the Traces tab (formerly cream `#fff8f0`
with an orange accent). Shares the same dark surface as trace rows but
uses a 'success' / teal left-edge accent so scatter vs. line is still
visually distinguishable — no more olive-yellow warning color showing up
in dark mode.

**Returns:**

- `object: Result of the operation.`

### `_inline_apply_btn_qss`

```python
def _inline_apply_btn_qss(variant = 'primary')
```

Small 'Apply' button rendered inside each trace/scatter row.
`variant` is either 'primary' (trace rows) or 'warn' (scatter rows).
Theme-aware replacement for the old hardcoded blue/orange — the
'warn' variant now uses the theme's success color to stay readable.

**Args:**

- `variant (Any): The variant.`

**Returns:**

- `object: Result of the operation.`

### `_install_theme_subscription`

```python
def _install_theme_subscription(dialog)
```

Attach the editor_dialog_qss to a dialog AND keep it updated when the
user toggles theme. Safe to call from any editor dialog's __init__.

**Args:**

- `dialog (Any): Parent or target dialog.`

### `get_system_font_families`

```python
def get_system_font_families()
```

Get available system font families from Qt font database,
sorted with common scientific fonts first.


**Returns:**

- `list: Sorted list of font family names`
