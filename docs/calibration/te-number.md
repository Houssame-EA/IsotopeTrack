# `TE_number.py`

---

## Classes

### `CollapsibleSection` *(extends `QWidget`)*

A themed collapsible panel.  Click the header bar to expand / collapse.
Use ``collapse(status)`` to fold it programmatically and show a summary
string; use ``expand()`` to re-open it.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, title: str, parent = None)` | Args: |
| `toggle` | `(self)` |  |
| `collapse` | `(self, status: str = '')` | Args: |
| `expand` | `(self)` |  |
| `set_status` | `(self, text: str)` | Args: |
| `is_expanded` | `(self)` | Returns: |

### `NoWheelDoubleSpinBox` *(extends `QDoubleSpinBox`)*

QDoubleSpinBox that ignores mouse-wheel events to prevent accidental changes.

| Method | Signature | Description |
|--------|-----------|-------------|
| `wheelEvent` | `(self, event)` | Args: |

### `NoWheelIntSpinBox` *(extends `QSpinBox`)*

QSpinBox that ignores mouse-wheel events to prevent accidental changes.

| Method | Signature | Description |
|--------|-----------|-------------|
| `wheelEvent` | `(self, event)` | Args: |

### `NoWheelComboBox` *(extends `QComboBox`)*

QComboBox that ignores mouse-wheel events to prevent accidental changes.

| Method | Signature | Description |
|--------|-----------|-------------|
| `wheelEvent` | `(self, event)` | Args: |

### `NumberMethodWidget` *(extends `QMainWindow`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Initialize the Number Method Widget for particle-based calibration. |
| `apply_theme` | `(self, *_)` | Re-apply the themed stylesheet and refresh dynamic labels. |
| `initUI` | `(self)` | Build the single-page collapsible layout. |
| `_build_samples_content` | `(self)` | Populate the Samples collapsible section. |
| `_build_element_content` | `(self)` | Populate the Element Selection collapsible section. |
| `_build_detection_content` | `(self)` | Populate the Detection Parameters collapsible section. |
| `_build_plot` | `(self, parent_layout)` | Add the always-visible signal visualization plot to parent_layout. |
| `_build_results_calibration_content` | `(self)` | Populate the Results & Calibration collapsible section. |
| `select_folders` | `(self)` | Enhanced folder/file selection matching main window structure. |
| `select_tofwerk_files` | `(self)` | Handle TOFWERK .h5 file selection for particle analysis. |
| `handle_tofwerk_import` | `(self, h5_file_paths)` | Handle TOFWERK .h5 file import for particle analysis. |
| `select_nu_folders` | `(self)` | Handle NU folder selection for particle analysis. |
| `select_data_files` | `(self)` | Handle data file selection for CSV, TXT, and Excel formats. |
| `handle_folder_import` | `(self, selected_paths)` | Handle folder import - simplified logic without mass validation. |
| `handle_csv_import` | `(self, file_paths)` | Handle CSV file import with configuration dialog. |
| `extract_masses_from_csv_config` | `(self, config)` | Extract available masses from CSV configuration. |
| `show_periodic_table_after_csv_config` | `(self)` | Show periodic table after CSV configuration. |
| `process_csv_files_with_isotopes` | `(self, selected_isotopes)` | Process CSV files with selected isotopes. |
| `filter_csv_config_by_isotopes` | `(self, config, selected_isotopes)` | Filter CSV configuration to only include selected isotopes. |
| `handle_csv_finished` | `(self, data, run_info, time_array, sample_name, datetime_str)` | Handle completion of CSV processing. |
| `handle_csv_error` | `(self, error_message)` | Handle CSV processing errors. |
| `update_sample_table` | `(self)` | Update the sample overview table - supports folders, CSV files, and TOFWERK files. |
| `enable_ui_elements` | `(self)` | Enable UI elements after successful folder loading. |
| `show_periodic_table` | `(self)` | Show periodic table - handle case where masses aren't loaded yet. |
| `handle_isotopes_selected` | `(self, selected_isotopes)` | Handle isotope selection from periodic table - supports both folders and CSV. |
| `_update_periodic_table_selections` | `(self)` | Helper method to efficiently update periodic table selections. |
| `load_element_data_for_all_samples` | `(self)` | Load element data for all samples - supports NU folders, CSV files, and TOFWERK files. |
| `_visible_exclusion_entries_for` | `(self, sample_name)` | Return the list of exclusion entries stored for *sample_name*. |
| `_on_exclusion_regions_changed` | `(self)` | Sync the plot's current exclusion bands into the bookkeeping store. |
| `_rebuild_plot_exclusion_regions` | `(self)` | Redraw the plot's exclusion bands from the bookkeeping store. |
| `on_detection_params_selection_changed` | `(self)` | Handle selection change in detection parameters table to show sample preview. |
| `plot_raw_signal_preview` | `(self, folder_path, sample_name)` | Plot raw signal preview for a sample. |
| `update_detection_parameters_table` | `(self)` | Update detection parameters table with all samples. |
| `apply_global_detection_params` | `(self, method)` | Apply global detection method to all samples. |
| `detect_particles_all_samples` | `(self)` | Detect particles for all samples with individual parameters. |
| `get_sample_detection_parameters` | `(self, row)` | Get detection parameters for a specific sample row. |
| `update_results_table` | `(self)` | Update results table with all detection results (simplified to 4 columns). |
| `highlight_selected_particle` | `(self)` | Zoom in on selected particle in plot. |
| `highlight_particle_in_plot` | `(self, particle, results)` | Add highlighting to a specific particle in the plot. |
| `update_sample_visualization` | `(self)` | Update visualization for selected sample. |
| `plot_sample_results` | `(self, sample_name, signal, particles, lambda_bkgd, threshold, time_ar` | Plot results for a specific sample. |
| `update_calibration_data_table` | `(self)` | Update calibration data table with sample information and default values. |
| `auto_fill_calibration_data` | `(self)` | Automatically fill calibration data from detection results. |
| `calculate_transport_rates` | `(self)` | Calculate transport rates for all selected samples. |
| `export_results_to_csv` | `(self)` | Export detection results to CSV file. |
