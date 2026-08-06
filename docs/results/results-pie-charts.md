# `results_pie_charts.py`

---

## Constants

| Name | Value |
|------|-------|
| `PIE_CHART_TYPES` | `['Element Distribution', 'Particle Count Distribution']` |
| `PIE_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `PIE_DISPLAY_MODES` | `['Individual Subplots', 'Side by Side Subplots', 'Combine…` |
| `COMP_ANALYSIS_TYPES` | `['Single vs Multiple Elements', 'Specific Isotope Combina…` |
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
| `__init__` | `(self, color: str='#FFFFFF', parent=None)` |  |
| `_apply` | `(self)` | Refresh the swatch preview without styling any parent dialog. |
| `color` | `(self) → str` |  |
| `set_color` | `(self, c: str)` | Store one validated pie-preview color and refresh the swatch. |
| `mousePressEvent` | `(self, event)` | Open the shared safe color picker for this swatch on left click. |

### `PieStyleGroup`

Donut, start angle, shadow, edge style, label distance.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict)` |  |
| `build` | `(self) → QGroupBox` |  |
| `collect` | `(self) → dict` |  |

### `LabelLineGroup`

Connection lines + label background box.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict)` |  |
| `build` | `(self) → QGroupBox` |  |
| `collect` | `(self) → dict` |  |

### `LegendGroup`

Legend visibility and placement.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict)` |  |
| `build` | `(self) → QGroupBox` |  |
| `collect` | `(self) → dict` |  |

### `ExportGroup`

Export format, DPI, background colour.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict)` |  |
| `build` | `(self) → QGroupBox` |  |
| `collect` | `(self) → dict` |  |

### `MplPieCanvas` *(extends `QWidget`)*

Matplotlib FigureCanvasQTAgg wrapped in a QWidget.

â€¢ Renders one or more pie / donut subplots in a grid.
â€¢ Every label annotation is individually draggable.
â€¢ Drag positions are saved back to cfg['label_positions'][key][label]
  on mouse-button release â€" they persist across redraws.
â€¢ Right-click is forwarded to the parent dialog via a callback so the
  existing context-menu code works unchanged.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict, parent=None)` |  |
| `set_context_menu_callback` | `(self, fn)` |  |
| `render` | `(self, subplots: list[dict])` | subplots â€“ list of dicts: |
| `reset_label_positions` | `(self, key: str \| None=None)` | Clear saved drag positions â€" all subplots or one. |
| `export_figure` | `(self, parent=None)` |  |
| `subplot_at` | `(self, canvas_pos) → 'dict \| None'` | Return the subplot dict for the axes under canvas_pos, or None. |
| `export_one_subplot` | `(self, sp: dict, parent=None)` | Export one pie subplot as a standalone figure with format/DPI choice. |
| `_fwd_ctx` | `(self, pos)` |  |
| `_persist_positions` | `(self, _event)` |  |
| `_pie_drag_press` | `(self, event)` | Start dragging an axes when the user clicks on its background. |
| `_pie_drag_motion` | `(self, event)` |  |
| `_pie_drag_release` | `(self, event)` |  |
| `_draw_one` | `(self, ax, sp: dict, cfg: dict)` |  |

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
| `_ctx_menu` | `(self, global_pos, subplot=None)` | Show minimal right-click controls for quick visual toggles and isotope labels. |
| `_toggle` | `(self, key)` | Toggle a lightweight visual option from the Quick Toggles menu. |
| `_set` | `(self, key, value)` | Set a configuration value from right-click quick controls. |
| `_export_subplot` | `(self, sp: dict)` |  |
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
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` | Open this node's figure, reusing one persistent (hide-on-close) window. |
| `process_data` | `(self, input_data)` |  |
| `extract_plot_data` | `(self)` |  |
| `_extract_single` | `(self, data_key)` |  |
| `_extract_multi` | `(self, data_key)` |  |

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
| `_ctx_menu` | `(self, global_pos, subplot=None)` | Show minimal right-click controls for quick visual toggles and isotope labels. |
| `_toggle` | `(self, key)` | Toggle a quick visual setting from the context menu. |
| `_set` | `(self, key, value)` | Set a config value from right-click quick controls. |
| `_export_subplot` | `(self, sp: dict)` |  |
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
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` | Open this node's figure, reusing one persistent (hide-on-close) window. |
| `process_data` | `(self, input_data)` |  |
| `extract_plot_data` | `(self)` |  |
| `_extract_single_enhanced` | `(self, data_key)` |  |
| `_extract_multi_enhanced` | `(self, data_key)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_is_multi` | `(input_data)` |  |
