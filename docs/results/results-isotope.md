# `results_isotope.py`

---

## Constants

| Name | Value |
|------|-------|
| `_BATCH_SUFFIX_RE` | `re.compile('\\s*\\[W\\d+\\]\\s*$')` |
| `CORRECTION_METHODS` | `['None', 'Exponential Law (instrumental mass fractionatio…` |
| `DISPLAY_MODES` | `['Overlaid (Different Colors)', 'Side by Side Subplots', …` |
| `JET_POSITIONS` | `np.array([0.0, 0.11, 0.34, 0.65, 0.89, 1.0])` |
| `JET_COLORS` | `np.array([[0, 0, 143, 255], [0, 0, 255, 255], [0, 255, 25…` |

## Classes

### `InsetColorBarItem` *(extends `pg.GraphicsWidget`)*

Draws an inset legend-style colorbar inside the plot.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, label_text, parent=None)` |  |
| `paint` | `(self, p, opt, widget)` |  |

### `SampleCorrectionDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, sample_name: str, sample_cfg: dict, available_elements: list, a` |  |
| `_build_ui` | `(self)` |  |
| `_on_method_changed` | `(self)` |  |
| `_auto_compute_exp` | `(self)` |  |
| `collect` | `(self) → dict` |  |

### `IsotopeSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config: dict, available_elements: list, all_isotope_labels: lis` |  |
| `_build_ui` | `(self)` | Build settings UI and apply scope visibility rules. |
| `_format_correction_details` | `(self, scfg)` |  |
| `_on_per_sample_toggled` | `(self, enabled)` |  |
| `_on_method_changed` | `(self)` |  |
| `_apply_scope_visibility` | `(self)` | Apply scope-based section visibility for format and quantity dialogs. |
| `_configure_sample_correction` | `(self, sample_name, row)` |  |
| `_copy_correction_to_all` | `(self)` |  |
| `_get_input_sample_names` | `(self)` | Get the list of individual replicate/sample names from the node's |
| `_compute_replicate_ratios` | `(self)` | Compute and plot the measured reference ratio for each individual replicate, |
| `_ratio_from_sample_ts` | `(pw, sample_ts, ref_num_label, ref_den_label)` | Compute ref ratio from time-series data for a single sample. |
| `_auto_compute_ref_measured` | `(self)` | Compute the measured reference ratio. |
| `_move_order_up` | `(self)` |  |
| `_move_order_down` | `(self)` |  |
| `_pick_color` | `(self, attr, btn)` |  |
| `collect` | `(self) → dict` | Collect settings for the active scope only. |

### `IsotopicRatioDisplayDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, isotopic_ratio_node, parent_window=None)` |  |
| `_is_multi` | `(self) → bool` |  |
| `_sample_names` | `(self) → list` |  |
| `_available_elements` | `(self) → list` |  |
| `_all_isotope_labels` | `(self) → list` |  |
| `_setup_ui` | `(self)` | Build the isotopic ratio dialog layout with the standard four-button row. |
| `_auto_calc_natural` | `(self)` |  |
| `_auto_calc_standard` | `(self)` |  |
| `_show_context_menu` | `(self, pos)` | Show the minimal custom right-click menu for quick visual toggles. |
| `_download_figure` | `(self)` |  |
| `_add_toggle` | `(self, menu, label, key)` |  |
| `_toggle` | `(self, key, value)` |  |
| `_set_cfg` | `(self, key, value)` |  |
| `_set_data_type` | `(self, dt)` |  |
| `_set_elem` | `(self, key, elem)` |  |
| `_set_correction` | `(self, method)` |  |
| `_set_display_mode` | `(self, mode)` |  |
| `_open_settings` | `(self, scope: str='all', title: str='Isotopic Ratio Settings')` | Open settings with a scope-safe collection path. |
| `_open_plot_format_settings` | `(self)` | Open the format-scoped settings dialog for visual/presentation controls. |
| `_open_configure_plot_quantities` | `(self)` | Open the quantities-scoped settings dialog for scientific/data controls. |
| `_open_isotope_correction_settings` | `(self)` | Open the correction-only settings dialog from right-click. |
| `_reset_layout` | `(self)` | Reset view layout to autorange for all active plot panels. |
| `_open_plot_settings` | `(self)` | Open PlotSettingsDialog via the adapter bridge. |
| `_get_custom_title_map` | `(self)` | Return the canonical custom-title mapping for this ratio dialog. |
| `_title_key_for_combined_plot` | `(is_multi)` | Return the stable custom-title key for a combined ratio plot. |
| `_title_key_for_sample_plot` | `(sample_name)` | Return the stable custom-title key for one sample ratio subplot. |
| `_effective_title_for_key` | `(self, plot_key, default_title='')` | Resolve the effective title for one stable ratio plot key. |
| `_apply_title_text_to_plot` | `(self, plot_item, title_text)` | Apply a ratio plot title while preserving current title styling. |
| `_store_custom_title_text` | `(self, plot_key, title_text)` | Store or clear one display-only custom title override. |
| `_apply_custom_title_edit` | `(self, plot_item, plot_key, title_text, default_title='')` | Persist one ratio custom title edit and reapply the effective title. |
| `_configure_plot_title` | `(self, plot_item, plot_key, default_title='')` | Bind text-only title editing and render the effective ratio title. |
| `_get_custom_axis_label_map` | `(self)` | Return the canonical custom axis-label mapping for this ratio dialog. |
| `_effective_axis_labels_for_key` | `(self, plot_key, default_axis_labels)` | Resolve effective bottom/left axis labels for one ratio plot key. |
| `_store_custom_axis_label` | `(self, plot_key, axis_name, text, units)` | Store or clear one display-only custom ratio axis-label override. |
| `_apply_effective_axis_labels` | `(self, plot_item, plot_key, default_axis_labels)` | Apply effective ratio axis labels and bind editor persistence hooks. |
| `_refresh` | `(self)` | Redraw the isotopic ratio plot from extracted source data and config. |
| `_set_mouse_mode` | `(self, mode: str)` | Switch all ViewBoxes between Pan and Zoom (rect) mode. |
| `_apply_mouse_mode` | `(self)` |  |
| `_suppress_native_pg_context_menu` | `(self)` | Disable native PyQtGraph menus on all current plot items and |
| `_iter_samples_in_display_order` | `(self, plot_data, cfg)` | Yield sample items in configured display order when provided. |
| `_prepare_sample` | `(self, element_data, cfg, sample_name=None)` | Prepare one sample by filtering invalid ratio inputs before plotting. |
| `_build_csv_data` | `(self) → pd.DataFrame \| None` | Build a DataFrame of per-particle isotopic ratio data for CSV export. |
| `_correct_per_replicate` | `(self, df, ratios, eff_cfg, e1, e2, sources)` | Apply per-replicate exponential correction. |
| `_compute_replicate_ref_ratio` | `(self, sample_name, ref_num_label, ref_den_label)` | Compute the reference ratio for a specific replicate sample. |
| `_ratio_from_time_series` | `(self, pw, sample_ts, ref_num_label, ref_den_label)` |  |
| `_build_labels` | `(self, cfg, sample_name=None)` |  |
| `_add_scatter` | `(self, pi, x, y, cfg, color, color_values=None, sample_key=None, is_si` |  |
| `_add_inset_colorbar` | `(self, pi, cfg, vmin, vmax)` |  |
| `_add_poisson_ci` | `(self, pi, cfg, mean_ratio, color, x_data=None, sample_name=None)` |  |
| `_make_legend_proxy` | `(self, color, style='solid', width=2)` |  |
| `_add_reference_lines` | `(self, pi, cfg, ratios_linear, legend_items, sample_name=None)` |  |
| `_apply_labels_and_font` | `(self, pi, cfg, plot_key, x_label=None, y_label=None, sample_name=None` | Apply effective labels, fonts, and axis state to one ratio plot. |
| `_draw_single` | `(self, pi, plot_data, cfg)` |  |
| `_draw_combined` | `(self, pi, plot_data, cfg)` |  |
| `_draw_subplots` | `(self, plot_data, cfg)` |  |
| `_draw_side_by_side` | `(self, plot_data, cfg)` |  |
| `_draw_single_on_plot` | `(self, pi, edf, cfg, color, sample_name)` | Draw one sample onto a target subplot using current ratio settings. |

### `IsotopicRatioPlotNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` | Open this node's figure, reusing one persistent (hide-on-close) window. |
| `process_data` | `(self, input_data)` |  |
| `_auto_configure_elements` | `(self)` |  |
| `_get_elements` | `(self) → list` |  |
| `extract_plot_data` | `(self)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_mass_of` | `(label: str) → float \| None` | Extract mass number from an isotope label like '206Pb', '203Tl'. |
| `_format_ratio_text` | `(num_label: str, den_label: str, mode: str) → str` | Display-only ratio text using configured label mode. |
| `_strip_batch_suffix` | `(sample_name: str) → str` | Strip batch window suffix like ' [W1]' from a sample name. |
| `make_jet_colormap` | `()` | Create a jet-like PyQtGraph ColorMap for scatter color dimension. |
| `get_overall_mean_signal` | `(parent_window, formatted_label: str) → float \| None` |  |
| `compute_ratio_from_mean_signals` | `(parent_window, num_label: str, den_label: str) → tuple` |  |
| `get_all_isotope_labels` | `(parent_window) → list` |  |
| `compute_exponential_correction` | `(r_measured: np.ndarray, m_num: float, m_den: float, ref_certified: fl` |  |
| `apply_isotope_correction` | `(r_measured: np.ndarray, config: dict) → np.ndarray` |  |
| `_find_particles_for_sample` | `(sample_name, dk, node=None, parent_window=None)` | Find unfiltered particles for a sample. |
| `get_correction_factor` | `(config: dict) → float` |  |
| `build_equation_text` | `(config: dict, sample_name: str=None) → str` |  |
| `_default_sample_correction` | `() → dict` |  |
| `get_sample_correction_config` | `(cfg: dict, sample_name: str=None) → dict` |  |
| `poisson_ratio_sigma` | `(R: float, lambda_B: np.ndarray) → np.ndarray` |  |
| `poisson_ci_curves` | `(R: float, x_range: np.ndarray, k: float=2.0)` |  |
