# `results_pie_charts.py`

---

## Constants

| Name | Value |
|------|-------|
| `PIE_CHART_TYPES` | `['Element Distribution', 'Particle Count Distribution']` |
| `PIE_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `PIE_DISPLAY_MODES` | `['Individual Subplots', 'Side by Side Subplots', 'Combine…` |
| `COMP_ANALYSIS_TYPES` | `['Single vs Multiple Elements', 'Specific Element Combina…` |
| `DEFAULT_PIE_COLORS` | `['#FF6347', '#FFD700', '#FFA500', '#20B2AA', '#00BFFF', '…` |
| `DEFAULT_COMBO_COLORS` | `['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '…` |
| `LEGEND_POSITIONS` | `['best', 'upper right', 'upper left', 'lower left', 'lowe…` |
| `_LINE_STYLES` | `['-', '--', '-.', ':']` |
| `_LINE_NAMES` | `['Solid', 'Dashed', 'Dash-dot', 'Dotted']` |
| `EXPORT_FORMATS` | `['svg', 'pdf', 'png', 'eps']` |
| `DEGREE_SIGN` | `'°'` |

## Classes

### `_ColorBtn` *(extends `QPushButton`)*

Single-click colour-picker button with a colour swatch.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, color: str='#FFFFFF', parent=None)` | Args: |
| `_apply` | `(self)` | Refresh the swatch preview without styling any parent dialog. |
| `color` | `(self) → str` | Returns: |
| `set_color` | `(self, c: str)` | Store one validated pie-preview color and refresh the swatch. |
| `mousePressEvent` | `(self, event)` | Open the shared safe color picker for this swatch on left click. |

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

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict, parent=None)` | Args: |
| `set_context_menu_callback` | `(self, fn)` | Args: |
| `render` | `(self, subplots: list[dict])` | subplots â€“ list of dicts: |
| `reset_label_positions` | `(self, key: str \| None=None)` | Clear saved drag positions â€“ all subplots or one. |
| `export_figure` | `(self, parent=None)` | Args: |
| `_fwd_ctx` | `(self, pos)` | Args: |
| `_persist_positions` | `(self, _event)` | Args: |
| `_pie_drag_press` | `(self, event)` | Start dragging an axes when the user clicks on its background. |
| `_pie_drag_motion` | `(self, event)` | Args: |
| `_pie_drag_release` | `(self, event)` | Args: |
| `_draw_one` | `(self, ax, sp: dict, cfg: dict)` | Args: |

### `PieChartSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, available_elements, parent=None, scope='all')` | Initialize pie-chart settings with optional scope-based control filtering. |
| `_build_ui` | `(self)` | Build settings controls for the active scope. |
| `collect` | `(self) → dict` | Collect updates from only the controls instantiated in the active scope. |

### `PieChartDisplayDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window=None)` | Initialize the element-distribution pie-chart display dialog. |
| `_build_ui` | `(self)` | Build the pie display and standardized bottom action buttons. |
| `_ctx_menu` | `(self, global_pos)` | Show minimal right-click controls for quick visual toggles and isotope labels. |
| `_toggle` | `(self, key)` | Toggle a lightweight visual option from the Quick Toggles menu. |
| `_set` | `(self, key, value)` | Set a configuration value from right-click quick controls. |
| `_reset_labels` | `(self)` | Reset persisted dragged label positions for pie labels. |
| `_reset_layout` | `(self)` | Route standardized reset action to existing pie label-position reset behavior. |
| `_export` | `(self)` | Open the existing pie-chart figure export workflow. |
| `_open_settings` | `(self)` | Open the legacy combined settings dialog. |
| `_open_plot_format_settings` | `(self)` | Open pie-chart format settings containing visual and presentation controls. |
| `_open_configure_plot_quantities` | `(self)` | Open pie-chart quantity settings containing chart/data/threshold controls. |
| `_get_available_elements` | `(self)` | Collect sortable element keys available in current plot data. |
| `_refresh` | `(self)` |  |
| `_calc_single` | `(self, sample_data, cfg)` | Calculate per-element totals and particle counts for one sample. |
| `_build_sp` | `(self, data, orig_counts, cfg, title, key, per_ml=False) → dict` | Build one subplot payload consumed by ``MplPieCanvas.render``. |

### `PieChartPlotNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `extract_plot_data` | `(self)` | Returns: |
| `_extract_single` | `(self, data_key)` | Args: |
| `_extract_multi` | `(self, data_key)` | Args: |

### `ElementCompositionSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, available_combos, parent=None, scope='all')` | Initialize Element Composition settings dialog with optional scope filtering. |
| `_build_ui` | `(self)` | Build settings controls for the selected scope. |
| `collect` | `(self) → dict` | Collect only settings for controls that exist in the active scope. |

### `ElementCompositionDisplayDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window=None)` | Initialize the Element Composition pie-chart display dialog. |
| `_build_ui` | `(self)` | Build display canvas and standardized bottom action buttons. |
| `_ctx_menu` | `(self, global_pos)` | Show minimal right-click controls for quick visual toggles and isotope labels. |
| `_toggle` | `(self, key)` | Toggle a quick visual setting from the context menu. |
| `_set` | `(self, key, value)` | Set a config value from right-click quick controls. |
| `_reset_labels` | `(self)` | Reset persisted dragged label positions for composition pie labels. |
| `_reset_layout` | `(self)` | Route standardized reset action to existing label-position reset behavior. |
| `_export` | `(self)` | Open the existing figure export workflow for composition pie charts. |
| `_get_actual_combos` | `(self) → list[str]` | Collect combinations ordered by particle-count prominence. |
| `_open_settings` | `(self)` | Open the legacy all-in-one settings dialog for compatibility. |
| `_open_plot_format_settings` | `(self)` | Open format-scoped composition settings dialog. |
| `_open_configure_plot_quantities` | `(self)` | Open quantities-scoped composition settings dialog. |
| `_refresh` | `(self)` | Recompute subplot payloads and redraw the composition pie canvas. |
| `_calc_data` | `(self, plot_data, cfg) → dict` | Compute analysis-specific composition buckets from raw plot data. |
| `_build_sp` | `(self, data, cfg, title, key, per_ml=False, pml_factor=0.0, pml_map=No` | Build one subplot payload consumed by ``MplPieCanvas.render``. |

### `ElementCompositionPlotNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `extract_plot_data` | `(self)` | Returns: |
| `_extract_single_enhanced` | `(self, data_key)` | Args: |
| `_extract_multi_enhanced` | `(self, data_key)` | Args: |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_is_multi` | `(input_data)` | Args: |
