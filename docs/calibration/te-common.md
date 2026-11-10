# `te_common.py`

---

## Constants

| Name | Value |
|------|-------|
| `BASE_STYLESHEET` | `base_stylesheet(LIGHT)` |
| `PREVIEW_STYLES` | `preview_styles(LIGHT)` |
| `RETURN_BUTTON_STYLE` | `return_button_style(LIGHT)` |
| `PLOT_STYLES` | `{'raw_signal': pg.mkPen(color=(30, 144, 255), width=1), '…` |
| `HISTOGRAM_COLORS` | `[(30, 144, 255, 180), (50, 205, 50, 180), (255, 69, 0, 18…` |
| `DEFAULT_DETECTION_PARAMS` | `{'method': 'Automatic', 'manual_threshold': 10.0, 'min_co…` |
| `DETECTION_METHODS` | `detection_registry.selectable_labels()` |
| `REMOVE_SAMPLES_TEXT` | `' Remove Selected Samples'` |

## Classes

### `NumericDelegate` *(extends `QStyledItemDelegate`)*

Custom delegate that restricts table-cell editing to numeric values.

| Method | Signature | Description |
|--------|-----------|-------------|
| `createEditor` | `(self, parent, option, index)` | Create a QLineEdit with a QDoubleValidator for the given cell. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `base_stylesheet` | `(p) → str` | Stylesheet for the calibration and transport-rate windows. |
| `section_stylesheet` | `(p) → str` | Rules for the collapsible sections and panel headers of the TE windows. |
| `preview_styles` | `(p) → dict` | Stylesheets for the result-preview label, keyed 'default', 'error', |
| `return_button_style` | `(p) → str` | Stylesheet for the 'Back to Main' button of the calibration windows. |
| `return_button_icon_color` | `(p) → str` | Colour of the house icon on the 'Back to Main' button. |
| `show_data_source_dialog` | `(parent=None)` | Show the "Select Data Source" popup and return the user's choice. |
| `snr_to_color` | `(ratio, palette=None)` | Map a signal-to-noise ratio to a QColor for table row highlighting. |
| `create_scrollable_container` | `(parent_layout=None, spacing=15)` | Build a QScrollArea wrapping a container QWidget with a QVBoxLayout. |
| `export_table_to_csv` | `(table, parent_widget, dialog_title='Export Detection Results')` | Export the contents of a QTableWidget or ResultsTableView to a CSV file. |
| `populate_detection_row` | `(table, row, sample_name, element_label, defaults=None)` | Populate a single row in a detection-parameters QTableWidget. |
| `read_detection_row` | `(table, row)` | Read all detection parameters from a single row of the detection table. |
| `style_remove_button` | `(button, p=None)` | Give a Remove button the theme's danger colours and a trash icon. |
| `make_remove_button` | `(slot, tooltip)` | Create a themed "Remove Selected Samples" button. |
| `remove_menu_label` | `(count)` | Return the context-menu label for removing selected samples. |
| `remove_menu_icon` | `()` | Return the danger-coloured trash icon used in context menus. |
| `confirm_remove_samples` | `(parent, names, consequence)` | Ask before removing samples; Cancel is the default. |
| `quiet_progress` | `(widget, progress)` | Keep a progress dialog hidden while the widget is restored from a project. |
| `mark_project_unsaved` | `(widget)` | Flag the main window's project as having unsaved changes. |
| `remove_rows_by_name` | `(table, names, column=0)` | Remove the rows of a table whose text in one column is in ``names``. |
| `set_detection_row_params` | `(table, row, params)` | Write saved detection parameters into one row of a TE detection table. |
| `apply_global_method` | `(table, method_name)` | Set the detection method combo box on every row to *method_name*. |
| `_style_plot_axes` | `(plot_widget, title=None)` | Apply the main-window plot appearance to *plot_widget*. |
| `plot_raw_signal` | `(plot_widget, sample_name, signal, time_array)` | Plot a raw signal preview using the main-window plot settings. |
| `_add_styled_legend` | `(plot_widget)` | Add a legend styled exactly like the main window's (20 pt labels). |
| `plot_detection_results` | `(plot_widget, sample_name, signal, particles, lambda_bkgd, threshold, ` | Render the particle-detection visualisation on *plot_widget*. |
| `highlight_particle` | `(plot_widget, particle, time_array, signal, current_item_ref=None)` | Draw a red highlight over a single particle in *plot_widget*. |
| `particle_mass_from_diameter` | `(diameter_nm, density_g_cm3)` | Compute the mass of a spherical particle. |
| `number_method_transport_rate` | `(particles_detected, diameter_nm, concentration_ng_l, acquisition_time` | Calculate transport rate using the particle-number method. |
| `weight_method_transport_rate` | `(w_initial_g, w_final_g, w_waste_g, time_s)` | Calculate transport rate using the liquid-weight method. |
| `fit_zero` | `(x, y)` | Force-through-zero (FTZ) linear regression. |
| `fit_simple` | `(x, y)` | Ordinary least squares (OLS) linear regression. |
| `fit_weighted` | `(x, y, y_std)` | Weighted least squares (WLS) linear regression. |
| `compute_figures_of_merit` | `(slope, intercept, sigma_blank)` | Compute analytical figures of merit from regression results. |
| `run_all_fits_on_subset` | `(x, y, y_std, included_mask, density)` | Run the three calibration fits on the subset of points selected by |
| `compute_outlier_indices` | `(y, y_fit, included_mask, z_threshold=1.5)` | Flag included points whose standardized residual exceeds ``z_threshold``. |
| `standards_in_sample_name` | `(sample_name, presets)` | Named multi-element standards (preset lists) found in a sample name. |
| `elements_in_sample_name` | `(sample_name, elements, presets=None)` | Elements named in a calibration sample name. |
