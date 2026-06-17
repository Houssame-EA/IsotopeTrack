# `results_network.py`

Network / Chord Diagram Node – circular element correlation network.

---

## Constants

| Name | Value |
|------|-------|
| `NET_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `NET_DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'element_mass…` |
| `DEFAULT_CONFIG` | `{'data_type_display': 'Counts', 'r_threshold': 0.3, 'min_…` |

## Classes

### `_ColorBtn` *(extends `QPushButton`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, color='#FFFFFF', parent=None, dialog_parent=None, title='Select` | Create a small color swatch button with a safe color picker. |
| `_apply` | `(self)` | Refresh the swatch preview without styling any parent dialog. |
| `color` | `(self)` | Return the currently selected network-preview color. |
| `mousePressEvent` | `(self, event)` | Open the shared safe color picker for this swatch on left click. |

### `_NetworkFontSettingsGroup` *(extends `FontSettingsGroup`)*

Network-local font settings group with a safe font color picker.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config, dialog_parent=None)` | Initialize the network font settings wrapper. |
| `_pick_color` | `(self)` | Select the font color without inheriting swatch button stylesheets. |

### `NetworkSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, parent=None, scope='all')` | Build the network settings dialog for format or quantity controls. |
| `_build_ui` | `(self)` | Create dialog controls for the requested settings scope. |
| `collect` | `(self)` | Collect normalized config values from the visible dialog controls. |
| `_commit_numeric_inputs` | `(self)` | Commit pending text edits for all numeric spinboxes in the dialog. |

### `NetworkDisplayDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window=None)` | Create the Matplotlib-backed network display dialog. |
| `showEvent` | `(self, event)` | Schedule one post-show redraw so the first open uses settled geometry. |
| `_build_ui` | `(self)` |  |
| `_ctx_menu` | `(self, pos)` | Open a quick-toggle context menu for network display settings. |
| `_toggle` | `(self, key)` | Flip a boolean config flag and redraw the current figure. |
| `_set` | `(self, key, value)` | Set a config value and redraw the current figure. |
| `_reset_layout` | `(self)` |  |
| `_export_figure` | `(self)` |  |
| `_open_plot_format_settings` | `(self)` | Open the formatting dialog and apply accepted display settings. |
| `_open_configure_plot_quantities` | `(self)` | Open the quantities dialog and apply accepted quantity settings. |
| `_open_settings` | `(self)` | Open the combined settings dialog and apply accepted changes. |
| `_refresh` | `(self)` | Rebuild the Matplotlib figure from current config and extracted data. |
| `_draw_network` | `(self, ax, net_data, cfg)` | Draw one correlation network on an axes and report legend signs. |
| `_build_title_and_subtitle` | `(self, net_data, cfg, mean_r)` | Build config-driven title and subtitle text for one network plot. |
| `_apply_shared_legend` | `(self, cfg, legend_signs, top_layout)` | Add one figure-level correlation legend in the bottom figure margin. |
| `_apply_node_size_note` | `(self, cfg, top_layout)` | Add one figure-level node-size explanation below the top legend row. |
| `_measure_reference_node_diameter_points` | `(self, cfg, reference_ax)` | Measure the plotted base node diameter in display points. |
| `_apply_node_size_visual_legend` | `(self, cfg, network_payloads, reference_ax, top_layout)` | Draw a RHS visual legend showing example proportional node sizes. |

### `NetworkDiagramNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `_get_elements` | `(self)` | Returns: |
| `extract_network_data` | `(self)` | Returns: |
| `_extract_single` | `(self, data_key, elements, r_threshold, min_n, aggregation)` | Extract single-sample network data without presentation-side counts. |
| `_extract_multi` | `(self, data_key, elements, r_threshold, min_n, aggregation)` | Extract per-sample network data for a multi-sample selection. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_is_multi` | `(input_data)` | Args: |
| `_compute_edges` | `(particles, elements, data_key, r_threshold, min_n)` | Return list of (i, j, r) where \|r\| >= threshold. |
| `_compute_node_amounts` | `(particles, elements, data_key, aggregation='Sum')` | Aggregate per-element amounts for one sample and one selected data type. |
| `_normalize_node_size_aggregation` | `(value)` | Normalize node-size aggregation config values to supported options. |
| `_node_size_note_text` | `(cfg)` | Build the figure-level node-size explanation text when scaling is enabled. |
| `_node_size_max_scale` | `()` | Return the current maximum node-radius scale for proportional sizing. |
| `_node_size_visual_legend_enabled` | `(cfg)` | Return whether the figure should render the RHS node-size visual legend. |
| `_node_size_amount_unit` | `(data_type)` | Return a compact unit label for node-size amount text. |
| `_format_node_size_amount` | `(value, unit)` | Format a quantitative node-size amount label compactly for the RHS legend. |
| `_collect_node_size_base_amounts` | `(network_payloads)` | Collect per-network minimum valid node amounts used for proportional sizing. |
| `_node_size_legend_scales` | `(max_scale)` | Return example radius scales for the RHS node-size visual legend. |
| `_node_size_legend_amount_ratio` | `(radius_scale)` | Convert a radius scale into the corresponding relative amount ratio. |
| `_node_size_visual_legend_labels` | `(scales)` | Build compact labels for RHS node-size legend example circles. |
| `_legend_base_amount_text` | `(network_payloads, data_type)` | Build the quantitative base-amount line for the RHS node-size legend. |
| `_top_annotation_layout` | `(has_legend, has_node_size_note)` | Return coordinated figure annotation positions and layout bounds. |
| `_compute_node_radii` | `(elements, node_amounts, base_radius, enabled)` | Compute per-element node radii from aggregated isotope amounts. |
| `_pick_color_hex` | `(current_color, parent=None, title='Select Color', fallback='#FFFFFF')` | Open a safe color dialog and return a validated hex color string. |
