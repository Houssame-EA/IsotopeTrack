# `results_single_multiple.py`

Single vs Multiple Element Analysis Node – Pie charts & heatmaps.

Uses **Matplotlib** for publication-quality figures (pie/heatmap).
Sidebar replaced by **right-click context menu** + settings dialog.
Uses shared_plot_utils for fonts, colors, sample helpers, and download.

---

## Constants

| Name | Value |
|------|-------|
| `VIZ_TYPES` | `['Pie Charts', 'Heatmaps']` |
| `SM_DISPLAY_MODES` | `['Individual Subplots', 'Side by Side Subplots', 'Combine…` |
| `DEGREE_SIGN` | `'°'` |
| `DEFAULT_CONFIG` | `{'custom_title': 'Single vs Multiple Element Analysis', '…` |

## Classes

### `SingleMultipleElementHelper`

Analysis helper for single vs multiple element particle classification.

| Method | Signature | Description |
|--------|-----------|-------------|
| `analyze_particles` | `(particle_data, pct_single=0.5, pct_multiple=0.5)` |  |
| `format_clean` | `(combo_str, label_mode='Symbol', cfg=None)` | Format a raw combination label for display using the selected isotope label mode. |
| `calc_per_ml` | `(count, parent_window, dilution=1.0, sample_info=None)` |  |
| `pie_data` | `(results, combo_type, custom_colors=None, per_ml=False, parent_window=` |  |
| `heatmap_data` | `(results_dict, per_ml=False, parent_window=None, dilution=1.0, label_m` | Build heatmap matrices for single- and multiple-element combinations. |
| `statistics_table` | `(analysis_data, is_multi=False, per_ml=False, parent_window=None, dilu` |  |

### `_ColorBtn` *(extends `QPushButton`)*

Compact colour-picker button.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, color: str='#FFFFFF', parent=None)` |  |
| `_apply` | `(self)` | Refresh the swatch preview without styling any parent dialog. |
| `color` | `(self) → str` |  |
| `set_color` | `(self, c: str)` | Store one validated composition-preview color and refresh the swatch. |
| `mousePressEvent` | `(self, event)` | Open the shared safe color picker for this swatch on left click. |

### `PieStyleGroup`

Pie / donut style settings reusable group for Single/Multiple dialog.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict)` |  |
| `build` | `(self) → QGroupBox` |  |
| `collect` | `(self) → dict` |  |

### `SingleMultipleSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, analysis_data, parent=None, scope='all')` | Initialize Single/Multiple settings with optional scope-based filtering. |
| `_build_ui` | `(self)` | Build settings groups for the selected scope. |
| `_update_quantities_scope_state` | `(self, viz_type: str)` | Update quantity-scope control availability based on visualization type. |
| `collect` | `(self)` | Collect selected settings for the active scope while preserving untouched values. |

### `SingleMultipleElementDisplayDialog` *(extends `QDialog`)*

Main dialog with matplotlib figure and right-click context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window=None)` |  |
| `_multi` | `(self)` |  |
| `_build_ui` | `(self)` | Build the display dialog with visualization and table tabs. |
| `_ctx_menu` | `(self, pos)` | Build an intentionally minimal right-click menu. |
| `_toggle` | `(self, key)` |  |
| `_set` | `(self, key, value)` |  |
| `_open_settings` | `(self)` | Open the legacy all-in-one settings dialog for compatibility. |
| `_open_plot_format_settings` | `(self)` | Open format-scoped settings dialog. |
| `_open_configure_plot_quantities` | `(self)` | Open quantities-scoped settings dialog. |
| `_reset_layout` | `(self)` | Reset subplot layout and clear persisted draggable label positions. |
| `_export_figure` | `(self)` | Open the existing figure export workflow for the Single/Multiple plot. |
| `_download_table` | `(self)` | Export the statistics table as CSV from a table-specific UI location. |
| `_persist_positions` | `(self, _event)` | Save current annotation positions into config so they survive redraws. |
| `_refresh` | `(self)` |  |
| `_draw_pies` | `(self, ad, cfg)` | Draw pie/donut visualizations for single vs multiple-element distributions. |
| `_combine_multi_analysis` | `(self, analysis_by_sample)` | Combine per-sample analysis into one aggregated analysis structure. |
| `_pie_one` | `(self, ax, results, ctype, custom_colors, pml, dil, si, cfg, fp, lc, s` |  |
| `_draw_heatmaps` | `(self, ad, cfg)` |  |
| `_update_stats` | `(self, ad)` |  |
| `_update_table` | `(self, ad)` |  |

### `SingleMultipleElementPlotNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` |  |
| `process_data` | `(self, input_data)` |  |
| `extract_analysis_data` | `(self)` |  |
| `_extract_multi` | `(self, st, mt)` |  |
