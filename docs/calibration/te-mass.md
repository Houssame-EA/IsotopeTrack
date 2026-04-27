# `TE_mass.py`

---

## Classes

### `NoWheelDoubleSpinBox` *(extends `QDoubleSpinBox`)*

QDoubleSpinBox that ignores mouse-wheel to prevent accidental changes.

### `NoWheelIntSpinBox` *(extends `QSpinBox`)*

QSpinBox that ignores mouse-wheel to prevent accidental changes.

### `NoWheelComboBox` *(extends `QComboBox`)*

QComboBox that ignores mouse-wheel to prevent accidental changes.

### `CollapsibleSection` *(extends `QWidget`)*

Themed collapsible panel. Click header to expand/collapse.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, title: str, parent = None)` | Args: |
| `toggle` | `(self)` |  |
| `collapse` | `(self, status: str = '')` | Args: |
| `expand` | `(self)` |  |

### `PeriodicTableDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Initialize the Periodic Table Dialog for element selection. |
| `on_selection_confirmed` | `(self, selected_data)` | Handle when user confirms their element selection. |
| `on_isotope_selected` | `(self, symbol, mass, abundance)` | Track individual isotope selections. |
| `update_available_masses` | `(self, masses)` | Update the periodic table with available masses. |

### `MassMethodWidget` *(extends `QMainWindow`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Initialize the Mass Method Widget for mass-based calibration. |
| `apply_theme` | `(self, *_)` | Re-apply themed stylesheet; refresh plots and dynamic labels. |
| `_mark_button_modified` | `(self, button, modified = True)` | Toggle the 'warning' look on a button to indicate unsaved / |
| `initUI` | `(self)` | Single-page collapsible layout replacing the 5-tab structure. |
| `_build_samples_content` | `(self)` | Section 1 — sample folder selection. |
| `_build_element_content` | `(self)` | Section 2 — element / isotope selection. |
| `_build_detection_content` | `(self)` | Section 3 — 12-column detection parameters + detect button. |
| `_build_plot` | `(self, parent_layout)` | Always-visible signal visualization plot. |
| `_build_detection_results_content` | `(self)` | Section 4 — results table (left) | file info table (right). |
| `_hint` | `(text: str) → QLabel` | Convenience: create a styled hint label. |
| `_build_analysis_results_content` | `(self)` | Section 6 — Mass Analysis regression + Transport Rate + Diameter Distribution. |
| `_build_ionic_calibration_content` | `(self)` | Section 5 — Ionic calibration setup + visualization. |
| `show_periodic_table` | `(self)` | Show the periodic table dialog for element selection. |
| `update_folder_list` | `(self)` | Update the folder list widget with selected folders - supports folders, CSV, and TOFWERK. |
| `enable_ui_elements` | `(self)` | Enable UI elements after successful folder loading. |
| `on_element_selected` | `(self, element)` | Handle element selection from periodic table. |
| `load_element_data_for_all_samples` | `(self)` | Load element data for all samples - supports NU folders, CSV files, and TOFWERK files. |
| `update_detection_parameters_table` | `(self)` | Update detection parameters table with all samples. |
| `apply_global_detection_params` | `(self, method)` | Apply global detection method to all samples. |
| `_visible_exclusion_entries_for` | `(self, sample_name)` | Return stored exclusion entries for *sample_name* (empty list if none). |
| `_on_exclusion_regions_changed` | `(self)` | Sync particle-detection plot bands into the bookkeeping store. |
| `_rebuild_plot_exclusion_regions` | `(self)` | Redraw particle-detection exclusion bands when switching sample. |
| `_on_ionic_calibration_exclusion_changed` | `(self)` | Persist ionic-calibration plot bands into the time-exclusion dicts. |
| `_restore_ionic_calibration_exclusions` | `(self, folder_path, isotope_key)` | Reload stored ionic-calibration exclusion bands onto the plot. |
| `on_detection_params_selection_changed` | `(self)` | Handle selection change in detection parameters table to show sample preview. |
| `plot_raw_signal_preview` | `(self, folder_path, sample_name)` | Plot raw signal preview for a sample. |
| `detect_particles_all_samples` | `(self)` | Detect particles for all samples using PeakDetection class. |
| `toggle_calibration_view` | `(self)` | Toggle between raw data view and calibration view. |
| `show_calibration_plot_in_raw_area` | `(self)` | Show the calibration plot in the raw data plot area. |
| `refresh_current_raw_data_view` | `(self)` | Refresh the current raw data view for the last selected sample. |
| `get_sample_detection_parameters` | `(self, row)` | Get detection parameters for a specific sample row. |
| `update_results_table` | `(self)` | Update results table with all detection results. |
| `highlight_selected_particle` | `(self)` | Zoom in on selected particle in plot. |
| `highlight_particle_in_plot` | `(self, particle, results)` | Add highlighting to a specific particle in the plot. |
| `update_sample_visualization` | `(self)` | Update visualization for selected sample. |
| `plot_sample_results` | `(self, sample_name, signal, particles, lambda_bkgd, threshold, time_ar` | Plot results for a specific sample. |
| `update_file_info_table` | `(self)` | Update file info table with improved average count display. |
| `on_folder_selected` | `(self, item)` | Handle folder selection from the list. |
| `calculate_particle_mass` | `(self, diameter, density)` | Calculate the mass of a spherical particle in femtograms. |
| `calculate_mass_and_regression` | `(self)` | Calculate mass and perform regression analysis. |
| `select_calibration_folders` | `(self)` | Enhanced calibration folder selection dialog matching particle folder approach. |
| `select_calibration_nu_folders` | `(self)` | Handle NU folder selection for ionic calibration. |
| `select_calibration_data_files` | `(self)` | Handle data file selection for ionic calibration. |
| `select_calibration_tofwerk_files` | `(self)` | Handle TOFWERK .h5 file selection for ionic calibration. |
| `handle_calibration_tofwerk_import` | `(self, h5_file_paths)` | Handle TOFWERK .h5 file import for ionic calibration. |
| `process_calibration_folder_selection` | `(self, selected_paths)` | Process selected calibration folders. |
| `process_calibration_csv_selection` | `(self, file_paths)` | Process selected calibration CSV files. |
| `process_calibration_csv_import` | `(self, config)` | Process calibration CSV import with given configuration. |
| `select_particle_folders` | `(self)` | Enhanced folder/file selection matching number method structure. |
| `select_nu_folders` | `(self)` | Handle NU folder selection for particle analysis. |
| `select_tofwerk_files` | `(self)` | Handle TOFWERK .h5 file selection for particle analysis. |
| `handle_tofwerk_import` | `(self, h5_file_paths)` | Handle TOFWERK .h5 file import for particle analysis. |
| `process_folder_selection` | `(self, selected_paths)` | Process selected folders. |
| `process_csv_selection` | `(self, file_paths)` | Process selected CSV files. |
| `process_csv_import` | `(self, config)` | Process CSV import with given configuration. |
| `handle_csv_import_finished` | `(self, data, run_info, time_array, sample_name, analysis_datetime)` | Handle completion of CSV import. |
| `handle_error` | `(self, error_message)` | Handle errors from data processing threads. |
| `auto_fill_concentrations` | `(self)` | Automatically fill concentration values based on sample names. |
| `show_concentration_context_menu` | `(self, position)` | Show context menu for concentration table operations. |
| `set_selected_cells_to_minus_one` | `(self)` | Set selected concentration cells to -1. |
| `set_selected_concentration_cells_to_value` | `(self, value)` | Set selected concentration cells to a specific value. |
| `on_concentration_data_changed` | `(self, item)` | Handle data changes in the concentration table. |
| `on_concentration_table_clicked` | `(self, row, col)` | Handle clicks on concentration table to show raw data. |
| `show_calibration_sample_raw_data` | `(self, folder_path, sample_name)` | Show raw data for a calibration sample using cached data. |
| `extract_concentration_from_sample_name` | `(self, sample_name)` | Extract concentration value from sample name using flexible pattern matching. |
| `update_concentration_table` | `(self)` | Update the concentration table with selected folders. |
| `validate_calibration_folders` | `(self, folders)` | Validate that calibration folders have compatible mass ranges. |
| `calculate_calibration` | `(self)` | Calculate ionic calibration with multiple regression methods using cached data. |
| `convert_concentration_to_ppb` | `(self, value, unit)` | Convert concentration to ppb. |
| `perform_ionic_calibration` | `(self, x, y, method)` | Perform calibration using specified method. |
| `calculate_transport_rate` | `(self)` | Calculate transport rate based on particle and ionic calibrations. |
| `plot_multiple_diameter_distributions` | `(self, all_diameters)` | Plot histogram of particle diameters for multiple files with statistics. |
| `export_to_csv` | `(self)` | Export detection results to CSV file. |
