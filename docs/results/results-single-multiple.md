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
| `SM_DISPLAY_MODES` | `['Individual Subplots', 'Side by Side Subplots'...` |
| `DEFAULT_CONFIG` | `{'custom_title': 'Single vs Multiple Element An...` |

## Classes

### `SingleMultipleElementHelper`

Analysis helper for single vs multiple element particle classification.

| Method | Signature | Description |
|--------|-----------|-------------|
| `analyze_particles` | `(particle_data, pct_single = 0.5, pct_multiple = 0.5)` | Args: |
| `format_clean` | `(combo_str)` | Args: |
| `calc_per_ml` | `(count, parent_window, dilution = 1.0, sample_info = None)` | Args: |
| `pie_data` | `(results, combo_type, custom_colors = None, per_ml = False, parent_win` | Args: |
| `heatmap_data` | `(results_dict, per_ml = False, parent_window = None, dilution = 1.0)` | Args: |
| `statistics_table` | `(analysis_data, is_multi = False, per_ml = False, parent_window = None` | Args: |

### `_ColorBtn` *(extends `QPushButton`)*

Compact colour-picker button.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, color: str = '#FFFFFF', parent = None)` | Args: |
| `_apply` | `(self)` |  |
| `color` | `(self) → str` | Returns: |
| `set_color` | `(self, c: str)` | Args: |
| `mousePressEvent` | `(self, event)` | Args: |

### `PieStyleGroup`

Pie / donut style settings reusable group for Single/Multiple dialog.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict)` | Args: |
| `build` | `(self) → QGroupBox` | Returns: |
| `collect` | `(self) → dict` | Returns: |

### `SingleMultipleSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, analysis_data, parent = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `_pick_lbl_color` | `(self)` |  |
| `_pick_sc` | `(self, sn, btn)` | Args: |
| `collect` | `(self)` | Returns: |

### `SingleMultipleElementDisplayDialog` *(extends `QDialog`)*

Main dialog with matplotlib figure and right-click context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window = None)` | Args: |
| `_multi` | `(self)` | Returns: |
| `_build_ui` | `(self)` |  |
| `_ctx_menu` | `(self, pos)` | Args: |
| `_toggle` | `(self, key)` | Args: |
| `_set` | `(self, key, value)` | Args: |
| `_open_settings` | `(self)` |  |
| `_reset_layout` | `(self)` |  |
| `_export_figure` | `(self)` |  |
| `_download_table` | `(self)` |  |
| `_persist_positions` | `(self, _event)` | Save current annotation positions into config so they survive redraws. |
| `_refresh` | `(self)` |  |
| `_draw_pies` | `(self, ad, cfg)` | Args: |
| `_pie_one` | `(self, ax, results, ctype, custom_colors, pml, dil, si, cfg, fp, lc, s` | Args: |
| `_draw_heatmaps` | `(self, ad, cfg)` | Args: |
| `_update_stats` | `(self, ad)` | Args: |
| `_update_table` | `(self, ad)` | Args: |

### `SingleMultipleElementPlotNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `extract_analysis_data` | `(self)` | Returns: |
| `_extract_multi` | `(self, st, mt)` | Args: |
