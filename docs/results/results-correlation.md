# `results_correlation.py`

---

## Classes

### `CorrelationSettingsDialog` *(extends `QDialog`)*

Full settings dialog opened from the right-click → Configure… action.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config: dict, available_elements: list, is_multi: bool, sample_` |  |
| `_sample_point_colors_available` | `(self) → bool` | Return whether sample-owned colors currently drive scatter points. |
| `_sample_point_color_unavailable_text` | `(self) → str` | Return the explanatory note for disabled sample point colors. |
| `_style_color_button` | `(self, button: QPushButton, color: str) → None` | Apply a compact swatch preview to a Correlation color button. |
| `_sample_display_label` | `(self, sample_name: str) → str` | Return the visible display label for one raw sample key. |
| `_pick_single_sample_color` | `(self) → None` | Pick the actual single-sample scatter point color. |
| `_pick_sample_color` | `(self, sample_name: str, button: QPushButton) → None` | Pick one canonical scatter color for a raw multi-sample key. |
| `_reset_sample_color` | `(self, sample_name: str, sample_index: int, button: QPushButton) → Non` | Reset one sample color override back to palette fallback. |
| `_build_ui` | `(self)` | Build settings UI sections and mark each section as format or quantities. |
| `_apply_scope_visibility` | `(self)` | Show only relevant setting groups for the current route scope. |
| `_on_mode_changed` | `(self)` | Toggle simple/custom selector groups for quantity-editing routes. |
| `_on_eq_changed` | `(self)` | Auto-populate axis labels from equation text when label is blank or was auto. |
| `_move_up` | `(self)` |  |
| `_move_down` | `(self)` |  |
| `_pick_sd_color` | `(self)` |  |
| `_pick_ref_color` | `(self)` |  |
| `_pick_font_color` | `(self)` | Pick the font/text color used for axis labels and overlay text. |
| `_open_sample_correlations` | `(self)` | Open the SampleCorrelationsDialog as a non-modal child window. |
| `collect` | `(self) → dict` | Return scope-safe config updates for format/quantities routes. |

### `AutoCorrelationDialog` *(extends `QDialog`)*

Table of top correlations — double-click to jump to that pair.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, top_pairs: list, parent=None)` |  |
| `_build` | `(self)` |  |
| `_on_double_click` | `(self, index)` |  |

### `SampleCorrelationsDialog` *(extends `QDialog`)*

Two-tab popup showing per-sample r and a cross-sample CDF correlation matrix.

Tab 1 — Per-sample r: Pearson r(x_element, y_element) computed within
each sample's own particle population.

Tab 2 — Cross-sample matrix: Pearson r between the empirical CDFs of a
chosen element across sample pairs. Uses np.quantile on a shared grid so
unequal sample sizes are handled naturally. Diagonal = 1.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict, plot_data: dict, parent=None)` |  |
| `_valid_samples` | `(self)` |  |
| `_get_xy` | `(self, df)` | Return (x, y) arrays for current x/y elements, zero-filtered. |
| `_ecdf_corr` | `(self, vals_a, vals_b)` | Pearson r between empirical CDFs evaluated on a shared quantile grid. |
| `_r_color` | `(r)` |  |
| `_build` | `(self)` |  |
| `_build_per_sample_tab` | `(self, widget)` |  |
| `_build_matrix_tab` | `(self, widget)` |  |
| `_rebuild_matrix` | `(self, elem)` |  |

### `CorrelationPlotDisplayDialog` *(extends `QDialog`)*

Full-figure correlation dialog.

The dialog follows the four-button Results contract for settings, reset, and
export. Right-click stays minimal with quick visual toggles, isotope-label
rendering modes, and the correlation-specific auto-detect action.

| Method | Signature | Description |
|--------|-----------|-------------|
| `normalize_display_mode` | `(mode: str) → str` | Normalize legacy Correlation display modes to active UI modes. |
| `__init__` | `(self, correlation_node, parent_window=None)` |  |
| `_is_multi` | `(self) → bool` |  |
| `_sample_names` | `(self) → list` |  |
| `_ordered_plot_data_items` | `(self, plot_data)` | Return plot_data items in configured sample order when available. |
| `_available_elements` | `(self) → list` |  |
| `_setup_ui` | `(self)` | Build the Correlation dialog with a full-width four-button action row. |
| `_show_context_menu` | `(self, pos)` | Show Correlation right-click actions with mode-aware subplot export. |
| `_add_toggle` | `(self, menu, label, key)` |  |
| `_toggle` | `(self, key, value)` |  |
| `_set_data_type` | `(self, dt)` |  |
| `_set_elem` | `(self, key, elem)` |  |
| `_set_display_mode` | `(self, mode)` | Set display mode using alias-normalized values and refresh. |
| `_open_plot_format_settings` | `(self)` | Open scoped visual formatting controls and refresh on apply. |
| `_open_configure_plot_quantities` | `(self)` | Open scoped quantity controls and refresh on apply. |
| `_reset_layout` | `(self)` | Reset current view layout by re-enabling axis autorange and redrawing. |
| `_export_figure` | `(self)` | Export the full Correlation figure with the shared export workflow. |
| `_plot_item_at` | `(self, pos)` | Resolve the clicked PlotItem using scene-space hit testing. |
| `_sanitize_filename_token` | `(self, text: str) → str` | Sanitize subplot names for use in export filename stems. |
| `_export_subplot` | `(self, plot_item, subplot_ctx: dict)` | Export only the clicked subplot while reusing full export options. |
| `_open_plot_settings` | `(self)` | Open PlotSettingsDialog via the adapter bridge. |
| `_click_to_data_coords` | `(self, widget_pos) → tuple` | Convert a right-click position in plot_widget coords to data coords |
| `_current_xy_arrays` | `(self)` | Return (x_array, y_array) pooled across samples in the plot's |
| `_build_smart_actions` | `(self) → list` | Data-aware smart actions for correlation plots. |
| `_auto_detect_correlations` | `(self)` |  |
| `_apply_auto_pair` | `(self, x_elem, y_elem)` |  |
| `_cleanup_color_bars` | `(self)` | Remove any existing per-plot color bars before a redraw. |
| `_suppress_native_plot_menus` | `(self)` | Disable native PyQtGraph right-click menus for Correlation plot items. |
| `_refresh` | `(self)` | Redraw Correlation plots from current config without changing math semantics. |
| `_extract_xy_color` | `(self, df, cfg)` | Extract (x, y, color_or_None) arrays from a DataFrame and config. |
| `_prepare_data` | `(self, df, cfg)` | Filter + log-transform + outlier removal. Returns (x, y, color) ready for plotting. |
| `_plot_scatter` | `(self, pi, x, y, c, cfg, color, correlation_label: str \| None=None, co` | Add scatter + overlays to a PlotItem using already-prepared sample data. |
| `_apply_labels` | `(self, pi, cfg)` |  |
| `_draw_single` | `(self, pi, plot_data, cfg)` |  |
| `_draw_subplots` | `(self, plot_data, cfg)` | Draw one subplot per sample and register subplot-export context. |
| `_draw_side_by_side` | `(self, plot_data, cfg)` | Draw one panel per sample in one row and register export context. |
| `_draw_combined` | `(self, pi, plot_data, cfg)` | Draw all samples overlaid in one panel with capped per-sample r labels. |
| `_add_no_valid_data_message` | `(self, pi, text: str='No valid paired data after filtering.')` | Show a centered non-modal empty-data message in the given PlotItem. |

### `CorrelationGraphicsLayoutWidget` *(extends `EnhancedGraphicsLayoutWidget`)*

Correlation GraphicsLayout widget.

Uses the shared inline double-click editors, uniform with the other plots:
clicking a sample's scatter series opens a colour picker that persists to
config (``single_sample_color`` / ``sample_colors``), while the axis, title,
legend and background use the shared editors. The scatter series are tagged
with their colour identity in ``_plot_scatter`` so no override is needed.

### `CorrelationPlotNode` *(extends `QObject`)*

Correlation plot node with multiple sample support and auto-detection.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` | Open this node's figure, reusing one persistent (hide-on-close) window. |
| `process_data` | `(self, input_data)` |  |
| `_auto_configure_elements` | `(self)` |  |
| `_get_elements` | `(self) → list` |  |
| `extract_plot_data` | `(self)` |  |
