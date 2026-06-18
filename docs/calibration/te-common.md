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
| `DEFAULT_DETECTION_PARAMS` | `{'method': 'Compound Poisson LogNormal', 'manual_threshol…` |

## Classes

### `NumericDelegate` *(extends `QStyledItemDelegate`)*

Custom delegate that restricts table-cell editing to numeric values.

| Method | Signature | Description |
|--------|-----------|-------------|
| `createEditor` | `(self, parent, option, index)` | Create a QLineEdit with a QDoubleValidator for the given cell. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `base_stylesheet` | `(p) → str` | Full base stylesheet for calibration/TE windows, built from a |
| `preview_styles` | `(p) → dict` | Return the four preview-label stylesheet strings tinted for the |
| `return_button_style` | `(p) → str` | Stylesheet for the 'Back to Main' button.  In light mode it keeps |
| `show_data_source_dialog` | `(parent=None)` | Show the "Select Data Source" popup and return the user's choice. |
| `snr_to_color` | `(ratio, palette=None)` | Map a signal-to-noise ratio to a QColor for table row highlighting. |
| `create_scrollable_container` | `(parent_layout=None, spacing=15)` | Build a QScrollArea wrapping a container QWidget with a QVBoxLayout. |
| `export_table_to_csv` | `(table, parent_widget, dialog_title='Export Detection Results')` | Export the contents of a QTableWidget to a CSV file. |
| `populate_detection_row` | `(table, row, sample_name, element_label, defaults=None)` | Populate a single row in a detection-parameters QTableWidget. |
| `read_detection_row` | `(table, row)` | Read all detection parameters from a single row of the detection table. |
| `apply_global_method` | `(table, method_name)` | Set the detection method combo box on every row to *method_name*. |
| `plot_detection_results` | `(plot_widget, sample_name, signal, particles, lambda_bkgd, threshold, ` | Render a comprehensive particle-detection visualisation on *plot_widget*. |
| `highlight_particle` | `(plot_widget, particle, time_array, signal, current_item_ref=None)` | Draw a red highlight over a single particle in *plot_widget*. |
| `particle_mass_from_diameter` | `(diameter_nm, density_g_cm3)` | Compute the mass of a spherical particle. |
| `number_method_transport_rate` | `(particles_detected, diameter_nm, concentration_ng_l, acquisition_time` | Calculate transport rate using the particle-number method. |
| `weight_method_transport_rate` | `(w_initial_g, w_final_g, w_waste_g, time_s)` | Calculate transport rate using the liquid-weight method. |
