# `results_molar_ratio.py`

---

## Constants

| Name | Value |
|------|-------|
| `MOLAR_DATA_TYPES` | `['Element Moles (fmol)', 'Particle Moles (fmol)']` |
| `MOLAR_DATA_KEY_MAP` | `{'Element Moles (fmol)': 'element_moles_fmol', 'Particle …` |
| `MR_DISPLAY_MODES` | `['Overlaid (Different Colors)', 'Individual Subplots', 'S…` |
| `_MR_DISPLAY_MODE_ALIASES` | `{'Combined with Legend': 'Overlaid (Different Colors)'}` |
| `SHADE_TYPES` | `['None', 'Mean ± 1 SD', 'Mean ± 2 SD', 'Median ± IQR  (Q1…` |
| `DEFAULT_CONFIG` | `{'data_type_display': 'Element Moles (fmol)', 'numerator_…` |
| `_QT_LINE` | `{'solid': pg.QtCore.Qt.SolidLine, 'dash': pg.QtCore.Qt.Da…` |

## Classes

### `MolarRatioSettingsDialog` *(extends `QDialog`)*

Scope-aware settings dialog for Molar Ratio format or quantities.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, available_elements, parent=None, scope='all')` | Preserved behavior: |
| `_build_ui` | `(self)` |  |
| `_try_apply` | `(self)` |  |
| `_try_done` | `(self)` |  |
| `_move_up` | `(self)` |  |
| `_move_down` | `(self)` |  |
| `_pick_shade_color` | `(self)` |  |
| `collect` | `(self)` | Collect config updates using strict scope-aware key groups. |

### `MolarRatioDisplayDialog` *(extends `QDialog`)*

Main dialog with PyQtGraph plot and right-click context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window=None)` |  |
| `_build_ui` | `(self)` | Build plot area and standardized four-button action row. |
| `_toggle_molar_sample` | `(self, raw_key)` | Toggle visibility of one sample in overlaid mode and redraw. |
| `_restore_hidden_molar_samples` | `(self)` | Unhide all legend-hidden samples and redraw. |
| `_ctx_menu` | `(self, pos)` | Show the minimal Molar Ratio right-click menu. |
| `_toggle` | `(self, key)` |  |
| `_set` | `(self, key, value)` |  |
| `_open_settings` | `(self, scope='all', title_override=None)` | Open scoped Molar Ratio settings and apply on accept. |
| `_open_plot_format_settings` | `(self)` | Open visual format settings for Molar Ratio presentation. |
| `_open_configure_plot_quantities` | `(self)` | Open scientific quantity settings for ratio selection and filters. |
| `_export_figure` | `(self)` | Export the full Molar Ratio figure using existing helper options. |
| `_disable_native_pyqtgraph_context_menu` | `(self)` | Suppress native PyQtGraph menus only for this Molar Ratio dialog. |
| `_reset_layout` | `(self)` | Reset view ranges only, preserving all ratio scientific settings. |
| `_refresh` | `(self)` | Rebuild the ratio plot and show non-modal invalid-data explanations. |
| `_draw_single` | `(self, pi, ratios, cfg)` | Draw single-sample ratio histogram and apply explicit axis log states. |
| `_draw_overlaid` | `(self, pi, plot_data, cfg, with_legend=True)` | Draw multi-sample overlaid ratios in one panel with explicit log states. |
| `_draw_subplots` | `(self, plot_data, cfg)` | Draw one subplot per sample and apply explicit log + stats behavior. |
| `_draw_side_by_side` | `(self, plot_data, cfg)` | Draw side-by-side sample subplots with explicit log + stats behavior. |
| `_update_stats` | `(self, plot_data, multi)` |  |

### `MolarRatioPlotNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` | Open this node's figure, reusing one persistent (hide-on-close) window. |
| `process_data` | `(self, input_data)` |  |
| `extract_available_elements` | `(self)` |  |
| `extract_plot_data` | `(self)` | Compute ratio arrays for current numerator/denominator/data-type config. |
| `_compute_ratios` | `(self, particles, dk, num, den)` | Compute positive finite ratios with fixed skip-invalid behavior. |
| `_extract_single` | `(self, dk, num, den)` |  |
| `_extract_multi` | `(self, dk, num, den)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_is_multi` | `(input_data)` |  |
| `_xy_labels` | `(cfg)` |  |
| `_normalize_mr_display_mode` | `(mode)` | Normalize legacy/redundant display-mode values for Molar Ratio. |
| `_draw_histogram_bars` | `(plot_item, ratios, cfg, color, y_scale=1.0, bin_edges=None, sample_ke` | Draw histogram bars for ratio values. |
| `_mr_compute_bar_data` | `(ratios, cfg, y_scale=1.0, bin_edges=None)` | Compute molar-ratio histogram bar arrays without drawing. |
| `_add_density_curve` | `(plot_item, values, cfg, edges, total)` | KDE density curve scaled to histogram counts. |
| `_apply_box` | `(plot_item, cfg)` | Show or hide the figure frame (top + right axes = closed box). |
| `_add_ref_line` | `(plot_item, cfg)` | Draw a customisable reference vertical line (e.g. ratio = 1). |
| `_add_stat_lines` | `(plot_item, values, cfg)` | Draw median / mean / mode marker lines. |
| `_add_shaded_region` | `(plot_item, values, cfg)` | Draw a statistical shaded band — applied to every subplot. |
| `_add_stats_text` | `(plot_item, ratios, cfg)` | Add statistics text box. |
| `_draw_ratio_plot` | `(plot_item, ratios, cfg, color, y_scale=1.0, bin_edges=None, sample_ke` | Draw a complete ratio histogram with overlays (applied to every subplot). |
