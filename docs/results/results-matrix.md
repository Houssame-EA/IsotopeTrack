# `results_matrix.py`

Correlation-Matrix Plot Node – pairwise Pearson-r heat-maps.

Single sample  → one matrix.
Multi-sample   → side-by-side or individual subplot matrices.

Rendered with Matplotlib (MplDraggableCanvas) for full drag/export support.

---

## Constants

| Name | Value |
|------|-------|
| `MATRIX_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `MATRIX_DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'element_mass…` |
| `MATRIX_COLORMAPS` | `['RdBu_r', 'coolwarm', 'seismic', 'BrBG', 'PiYG', 'PRGn',…` |
| `MATRIX_DISPLAY_MODES` | `['Side by Side', 'Individual Subplots', 'Difference Matrix']` |
| `DEGREE_SIGN` | `'°'` |
| `DEFAULT_HIGHLIGHT_COLOR` | `'#000000'` |
| `TRIVIALITY_MARKER` | `'*'` |
| `ZERO_MODE_BOTH` | `'both'` |
| `ZERO_MODE_EITHER` | `'either'` |
| `ZERO_MODE_ALL` | `'all'` |
| `ZERO_MODE_CONFIG_KEY` | `'zero_handling'` |
| `ZERO_MODE_LABELS` | `{ZERO_MODE_BOTH: 'Both present - only particles carrying …` |
| `PANEL_GROUP_CONFIG_KEY` | `'classifier_panel_group'` |
| `PART_WHOLE_IN_STATS_KEY` | `'part_whole_in_stats'` |
| `CELL_LABEL_MODES` | `['r value', 'Particle count', 'Both']` |
| `DEFAULT_CONFIG` | `{'data_type_display': 'Counts', 'min_particles': 5, 'cell…` |
| `_UNSUMMABLE_KEYS` | `('element_diameter_nm', 'particle_diameter_nm')` |

## Classes

### `MatrixSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, parent=None, scope='all')` |  |
| `_build_ui` | `(self)` |  |
| `collect` | `(self)` |  |

### `CorrelationMatrixDisplayDialog` *(extends `QDialog`)*

Matplotlib-based correlation matrix dialog with drag support.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window=None)` |  |
| `_build_ui` | `(self)` |  |
| `_ctx_menu` | `(self, pos)` | Build a minimal Matrix right-click menu with quick controls only. |
| `_toggle` | `(self, key)` |  |
| `_set` | `(self, key, value)` |  |
| `_get_row_at` | `(self, widget_pos)` | Return the element for the matrix row at widget_pos, or None. |
| `_toggle_row_highlight` | `(self, elem, add)` |  |
| `_change_row_highlight_color` | `(self, elem)` |  |
| `_clear_all_highlights` | `(self)` |  |
| `_reset_layout` | `(self)` |  |
| `_export_figure` | `(self)` |  |
| `_open_plot_format_settings` | `(self)` |  |
| `_open_configure_plot_quantities` | `(self)` |  |
| `_open_settings` | `(self)` |  |
| `_refresh` | `(self)` |  |
| `_stats_exclusion` | `(self, info, cfg)` | Which cells to leave out of the header's mean\|r\|. |
| `_group_note` | `(self, info)` | Explain a GROUPS matrix that came out structurally empty, rather |
| `_draw_single` | `(self, data, cfg)` |  |
| `_draw_multi` | `(self, data, cfg)` |  |
| `_draw_panels` | `(self, cfg)` | PANELS role: one correlation matrix per classifier group |
| `_draw_difference` | `(self, data, cfg)` |  |
| `_draw_matrix_ax` | `(self, ax, mat, elems, cfg, title='', counts=None, exact_trivial=None,` | Draw one correlation matrix onto ax using imshow. |

### `CorrelationMatrixNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` |  |
| `process_data` | `(self, input_data)` |  |
| `classifier_role` | `(self)` | GROUPS/PANELS/COLORS/OFF in force for this render. |
| `classifier_scope` | `(self)` | BY DEFINITION vs TOTAL PARTICLE, defaulting to TOTAL PARTICLE for |
| `panel_groups` | `(self)` | Classifier groups PANELS role can show, registry order. |
| `panel_group` | `(self)` | The single group PANELS shows per sample (multi-sample only). |
| `_zero_mode` | `(self)` |  |
| `extract_matrix_data` | `(self)` | Matrix data for GROUPS / COLORS / OFF. |
| `_isotope_labels` | `(self)` | Real isotope labels for the axes, mass-sorted. |
| `_group_labels` | `(self, data_key)` | Classifier groups eligible to sit on the axes under GROUPS role. |
| `_get_elements` | `(self)` |  |
| `_min_particles` | `(self)` | Return the configured Min Particles value, clamped to a usable minimum. |
| `_matrix_for` | `(self, particles, data_key)` | One matrix payload for a set of particles, honouring the role. |
| `_extract_single` | `(self, data_key)` |  |
| `_extract_multi` | `(self, data_key)` |  |
| `extract_panel_data` | `(self)` | PANELS-role data: one correlation matrix per classifier group, |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_pair_mask` | `(vi, vj, zero_mode)` | Boolean mask of the particles a pair is correlated over. |
| `effective_zero_mode` | `(cfg)` | Resolve the zero-handling mode, defaulting to the historical |
| `_normalize_highlighted_elements` | `(raw)` | Return ``{element: hex_color}`` from the highlighted_elements config value. |
| `_is_multi` | `(input_data)` |  |
| `_clean_value` | `(v, data_key)` | One raw composition value, normalised for correlation. |
| `correlate_columns` | `(columns, labels, min_particles=5, zero_mode=ZERO_MODE_BOTH)` | Pearson-r matrix over pre-built per-label value columns. |
| `_compute_correlation_matrix` | `(particles, elements, data_key, min_particles=5, zero_mode=ZERO_MODE_B` | Build NxN Pearson-r matrix from particle data. |
| `_merge_copies_by_identity` | `(particles)` | Group a particle list into one entry per REAL particle. |
| `build_mixed_columns` | `(particles, isotopes, groups, data_key, scope)` | Per-particle value columns for a MIXED isotope + group vocabulary. |
| `triviality_masks` | `(labels, isotopes, groups, contributing, scope=None, zero_mode=None)` | ``(exact, partial)`` NxN bool masks for a mixed-vocabulary matrix. |
| `_matrix_stats` | `(mat, exclude=None)` | Summary line for the header: mean \|r\| and the share of strong pairs. |
| `_pair_count_stats` | `(counts, min_particles)` | Summarise how the Min Particles cut-off lands on the current data. |
