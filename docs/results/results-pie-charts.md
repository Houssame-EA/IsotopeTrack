# `results_pie_charts.py`

---

## Constants

| Name | Value |
|------|-------|
| `PIE_CHART_TYPES` | `['Element Distribution', 'Particle Count Distri...` |
| `PIE_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass ...` |
| `PIE_DISPLAY_MODES` | `['Individual Subplots', 'Side by Side Subplots'...` |
| `COMP_ANALYSIS_TYPES` | `['Single vs Multiple Elements', 'Specific Eleme...` |
| `DEFAULT_PIE_COLORS` | `['#FF6347', '#FFD700', '#FFA500', '#20B2AA', '#...` |
| `DEFAULT_COMBO_COLORS` | `['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#...` |
| `LABEL_MODES` | `['Symbol', 'Mass + Symbol']` |
| `LEGEND_POSITIONS` | `['best', 'upper right', 'upper left', 'lower le...` |
| `_LINE_STYLES` | `['-', '--', '-.', ':']` |
| `_LINE_NAMES` | `['Solid', 'Dashed', 'Dash-dot', 'Dotted']` |
| `EXPORT_FORMATS` | `['svg', 'pdf', 'png', 'eps']` |

## Classes

### `_ColorBtn` *(extends `QPushButton`)*

Single-click colour-picker button with a colour swatch.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, color: str = '#FFFFFF', parent = None)` | Args: |
| `_apply` | `(self)` |  |
| `color` | `(self) → str` | Returns: |
| `set_color` | `(self, c: str)` | Args: |
| `mousePressEvent` | `(self, event)` | Args: |

### `PieStyleGroup`

Donut, start angle, shadow, edge style, label distance.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict)` | Args: |
| `build` | `(self) → QGroupBox` | Returns: |
| `collect` | `(self) → dict` | Returns: |

### `LabelLineGroup`

Connection lines + label background box.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict)` | Args: |
| `build` | `(self) → QGroupBox` | Returns: |
| `collect` | `(self) → dict` | Returns: |

### `LegendGroup`

Legend visibility and placement.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict)` | Args: |
| `build` | `(self) → QGroupBox` | Returns: |
| `collect` | `(self) → dict` | Returns: |

### `ExportGroup`

Export format, DPI, background colour.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict)` | Args: |
| `build` | `(self) → QGroupBox` | Returns: |
| `collect` | `(self) → dict` | Returns: |

### `MplPieCanvas` *(extends `QWidget`)*

Matplotlib FigureCanvasQTAgg wrapped in a QWidget.

• Renders one or more pie / donut subplots in a grid.
• Every label annotation is individually draggable.
• Drag positions are saved back to cfg['label_positions'][key][label]
on mouse-button release – they persist across redraws.
• Right-click is forwarded to the parent dialog via a callback so the
existing context-menu code works unchanged.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict, parent = None)` | Args: |
| `set_context_menu_callback` | `(self, fn)` | Args: |
| `render` | `(self, subplots: list[dict])` | subplots – list of dicts: |
| `reset_label_positions` | `(self, key: str | None = None)` | Clear saved drag positions – all subplots or one. |
| `export_figure` | `(self, parent = None)` | Args: |
| `_fwd_ctx` | `(self, pos)` | Args: |
| `_persist_positions` | `(self, _event)` | Args: |
| `_pie_drag_press` | `(self, event)` | Start dragging an axes when the user clicks on its background. |
| `_pie_drag_motion` | `(self, event)` | Args: |
| `_pie_drag_release` | `(self, event)` | Args: |
| `_draw_one` | `(self, ax, sp: dict, cfg: dict)` | Args: |

### `PieChartSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, available_elements, parent = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `collect` | `(self) → dict` | Returns: |

### `PieChartDisplayDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `_ctx_menu` | `(self, global_pos)` | Args: |
| `_toggle` | `(self, key)` | Args: |
| `_set` | `(self, key, value)` | Args: |
| `_reset_labels` | `(self)` |  |
| `_export` | `(self)` |  |
| `_open_settings` | `(self)` |  |
| `_get_available_elements` | `(self)` | Returns: |
| `_refresh` | `(self)` |  |
| `_calc_single` | `(self, sample_data, cfg)` | Args: |
| `_build_sp` | `(self, data, orig_counts, cfg, title, key) → dict` | Args: |

### `PieChartPlotNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `extract_plot_data` | `(self)` | Returns: |
| `_extract_single` | `(self, data_key)` | Args: |
| `_extract_multi` | `(self, data_key)` | Args: |

### `ElementCompositionSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, available_combos, parent = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `collect` | `(self) → dict` | Returns: |

### `ElementCompositionDisplayDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `_ctx_menu` | `(self, global_pos)` | Args: |
| `_toggle` | `(self, key)` | Args: |
| `_set` | `(self, key, value)` | Args: |
| `_reset_labels` | `(self)` |  |
| `_export` | `(self)` |  |
| `_get_actual_combos` | `(self) → list[str]` | Returns: |
| `_open_settings` | `(self)` |  |
| `_refresh` | `(self)` |  |
| `_calc_data` | `(self, plot_data, cfg) → dict` | Args: |
| `_build_sp` | `(self, data, cfg, title, key) → dict` | Args: |

### `ElementCompositionPlotNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `extract_plot_data` | `(self)` | Returns: |
| `_extract_single_enhanced` | `(self, data_key)` | Args: |
| `_extract_multi_enhanced` | `(self, data_key)` | Args: |

## Functions

### `_is_multi`

```python
def _is_multi(input_data)
```


**Args:**

- `input_data (Any): The input data.`

**Returns:**

- `object: Result of the operation.`

### `_format_element_label`

```python
def _format_element_label(key: str, mode: str) → str
```

Format an element key for display according to label mode.

'Symbol'        → bare symbol, stripping any leading mass number
e.g. '107Ag' → 'Ag',  '107Ag, 197Au' → 'Ag, Au'
'Mass + Symbol' → keep as-is (full isotope notation)
e.g. '107Ag',          '107Ag, 197Au'

**Args:**

- `key (str): Dictionary or storage key.`
- `mode (str): Operating mode string.`

**Returns:**

- `str: Result of the operation.`
