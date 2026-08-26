# `results_heatmap.py`

---

## Constants

| Name | Value |
|------|-------|
| `HEATMAP_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `DEGREE_SIGN` | `'°'` |
| `HEATMAP_MULTI_DISPLAY_MODES` | `['Individual Subplots', 'Side by Side Subplots', 'Combine…` |
| `DEFAULT_UNDERLINE_COLOR` | `'#000000'` |
| `PANEL_GROUP_CONFIG_KEY` | `'classifier_panel_group'` |
| `UNDERLINE_CONFIG_KEY` | `'underlined_combos'` |
| `LEGACY_UNDERLINE_CONFIG_KEY` | `'highlighted_combos'` |
| `CELL_STAT_OPTIONS` | `['Mean', 'Median', 'Mode', 'Geometric Mean']` |
| `CELL_SPREAD_OPTIONS` | `['None', 'SD', 'SEM', 'IQR (Q1–Q3)', 'Min–Max', 'CV %']` |

## Classes

### `HeatmapSettingsDialog` *(extends `QDialog`)*

Scoped settings dialog for heatmap format/quantity configuration.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config: dict, is_multi: bool, sample_names: list, parent=None, ` |  |
| `_sample_name_keys` | `(self) → list[str]` | Return raw sample keys that can be renamed in Heatmap settings. |
| `_build` | `(self)` | Build scoped Heatmap settings controls for the current route. |
| `collect` | `(self) → dict` | Collect Heatmap settings without touching removed or missing widgets. |

### `HeatmapDisplayDialog` *(extends `QDialog`)*

Full-figure heatmap dialog with right-click context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, heatmap_node, parent_window=None)` |  |
| `_is_multi` | `(self) → bool` |  |
| `_sample_names` | `(self) → list` |  |
| `_single_sample_name` | `(self) → str` | Return the canonical single-sample key when one is available. |
| `_single_sample_title` | `(self, cfg: dict) → str` | Return the visible single-sample Heatmap title. |
| `_setup_ui` | `(self)` |  |
| `_show_context_menu` | `(self, pos)` | Build a minimal Heatmap right-click menu with quick controls only. |
| `_get_row_at` | `(self, widget_pos)` | Return the raw combo key for the heatmap row at widget_pos, or None. |
| `_axes_sample_at` | `(self, widget_pos)` | Return the sample name for the heatmap axes under widget_pos, or None. |
| `_toggle_row_underline` | `(self, combo_key, add)` |  |
| `_change_row_underline_color` | `(self, combo_key)` |  |
| `_clear_all_underlines` | `(self)` |  |
| `_add_toggle` | `(self, menu, label, key)` |  |
| `_toggle` | `(self, key, value)` |  |
| `_set_label_mode` | `(self, mode)` |  |
| `_set_and_refresh` | `(self, key, value)` |  |
| `_search_dialog` | `(self)` |  |
| `_range_dialog` | `(self)` | Quick range adjustment via two input dialogs. |
| `_open_settings` | `(self)` |  |
| `_open_plot_format_settings` | `(self)` |  |
| `_open_configure_plot_quantities` | `(self)` |  |
| `_reset_layout` | `(self)` |  |
| `_export_figure` | `(self)` |  |
| `_export_subplot` | `(self, sample_name)` | Export one heatmap subplot as a standalone single-panel figure. |
| `_refresh` | `(self)` | Rebuild the Heatmap figure from current config and extracted data. |
| `_current_data_key` | `(self)` |  |
| `_all_particles` | `(self)` |  |
| `_particles_for_sample` | `(self, sample_name)` |  |
| `_panel_title_for` | `(self, label)` | Panel/window title for one classifier group, honoring the |
| `_refresh_panels` | `(self)` | Draw PANELS role. |
| `_draw_multi` | `(self, data, cfg, display_mode, role=None)` | Draw the active multi-sample Heatmap layout. |
| `_combine_data` | `(data)` |  |
| `_draw_heatmap` | `(self, ax, sample_data, cfg, title, role=None, particles_for_colors=No` | Args: |
| `_ensure_underline_margin` | `(self)` | Widen the figure's left margin when COLORS-role underline |
| `_bucket_legend_entries` | `(self)` | ``[(label, color), ...]`` for the COLORS-role "what color is what |

### `HeatmapPlotNode` *(extends `QObject`)*

Heatmap plot node with multiple sample support.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` | Open this node's figure, reusing one persistent (hide-on-close) window. |
| `process_data` | `(self, input_data)` |  |
| `classifier_role` | `(self)` | The GROUPS/PANELS/COLORS/OFF role in force for this render (see |
| `classifier_scope` | `(self)` | The DEFINITION-or-TOTAL-PARTICLE aggregation scope in force for |
| `classifier_denominator` | `(self)` | The Whole-Group-or-Detected-Only denominator in force for this |
| `extract_plot_data` | `(self)` | Row data for the GROUPS/COLORS/OFF roles, in the same |
| `_extract_single` | `(self, data_key, role=None)` |  |
| `_extract_multi` | `(self, data_key, role=None)` |  |
| `_group_rows` | `(self, particles, data_key, pml_factor)` | GROUPS-role rows: one row per classifier bucket, built via |
| `panel_groups` | `(self)` | Every classifier group PANELS role can show, in registry order. |
| `panel_group` | `(self)` | The single classifier group PANELS role is showing per sample |
| `extract_panel_data` | `(self)` | PANELS-role data: particles partitioned by the bucket the |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_normalize_underlined_combos` | `(raw)` | Return ``{combo_key: color_or_colors}`` from either the current dict |
| `_read_underlined_combos` | `(cfg)` | Manual per-row underline overrides from a config, honoring the |
| `_write_underlined_combos` | `(cfg, value)` | Store manual underline overrides under the current key, clearing the |
| `_normalize_heatmap_display_mode` | `(display_mode: str) → str` | Normalize legacy Heatmap display-mode values to supported UI modes. |
| `_combo_matches` | `(combination: str, search_elements: list) → bool` | Check if a combination string contains all search elements (order-independent). |
| `_combo_exact_matches` | `(combination: str, search_elements: list) → bool` | Check if a combination has exactly the search elements — no more, no less. |
| `_mode_estimate` | `(arr)` | Estimate the mode of continuous values from the densest histogram bin. |
| `_cell_center` | `(vals, stat)` | Central value for one heatmap cell: Mean, Median, Mode, or Geo. Mean. |
| `_cell_spread_value` | `(vals, spread)` | Secondary value shown after a cell centre. |
| `_fmt_cell_number` | `(v)` | Format one numeric cell value with the heatmap's standard precision. |
| `_per_particle_percentages` | `(total_values)` | Convert a combination's raw per-element values into per-particle %. |
| `_bulk_percentages` | `(total_values)` | Bulk composition %: each element's summed signal over the grand total. |
| `draw_combinations_heatmap` | `(ax, fig, sample_data, cfg, title='', is_multi=False, row_label_raw=Fa` | Draw a combinations heatmap onto an arbitrary axes/figure. |
| `_combo_signature` | `(particle, data_key)` | One particle's contribution to a combination row for ``data_key``. |
| `_build_combinations` | `(particles, data_key, pml_factor=0.0)` | Build combination dict from a list of particle dicts. |
| `_default_row_bucket_colors_by_combo` | `(particles, data_key, input_data)` | ``{combo_key: [hex_color, ...]}`` classifier-derived defaults for |
