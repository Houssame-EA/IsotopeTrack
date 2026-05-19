# `mainwindow.py`

---

## Classes

### `NoWheelSpinBox` *(extends `QDoubleSpinBox`)*

Custom QDoubleSpinBox that ignores mouse wheel events.


**Args:**

- `Inherits from QDoubleSpinBox`


**Returns:**

- `None`

| Method | Signature | Description |
|--------|-----------|-------------|
| `wheelEvent` | `(self, event)` | Ignore mouse wheel scroll events. |

### `NoWheelIntSpinBox` *(extends `QSpinBox`)*

Custom QSpinBox that ignores mouse wheel events.


**Args:**

- `Inherits from QSpinBox`


**Returns:**

- `None`

| Method | Signature | Description |
|--------|-----------|-------------|
| `wheelEvent` | `(self, event)` | Ignore mouse wheel scroll events. |

### `NoWheelComboBox` *(extends `QComboBox`)*

Custom QComboBox that ignores mouse wheel events.


**Args:**

- `Inherits from QComboBox`


**Returns:**

- `None`

| Method | Signature | Description |
|--------|-----------|-------------|
| `wheelEvent` | `(self, event)` | Ignore mouse wheel scroll events. |

### `MainWindow` *(extends `QMainWindow`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` | Initialize the MainWindow for IsotopeTrack application. |
| `setup_window_size` | `(self)` | Configure initial window size and position. |
| `initialize_help_manager` | `(self)` | Initialize help dialog manager. |
| `center_on_screen` | `(self)` | Center window on screen. |
| `reset_data_structures` | `(self)` | Reset all data structures before loading a saved project. |
| `create_central_widget` | `(self)` | Create and configure the central widget with main UI layout. |
| `create_sidebar` | `(self)` | Create sidebar with calibration and sample management tools. |
| `create_menu_bar` | `(self)` | Create application menu bar with actions. |
| `open_new_window` | `(self)` | Returns: |
| `close_all_windows` | `(self)` | Close all open windows and quit application. |
| `create_status_bar` | `(self)` | Create application status bar with progress indicator. |
| `apply_theme` | `(self)` | Apply the currently-active theme palette to every styled widget |
| `create_plot_widget` | `(self)` | Create plot widget for data visualization with an inline Time / m/z toggle. |
| `create_control_panel` | `(self)` | Create control panel for particle detection parameters. |
| `create_summary_widget` | `(self)` | Create widget for particle summary statistics display. |
| `create_results_container` | `(self)` | Create container for results display with element and particle tables. |
| `create_sample_table` | `(self)` | Create sample list table widget. |
| `create_results_table` | `(self)` | Create table for single element detection results. |
| `create_multi_element_table` | `(self)` | Create table for multi-element particle results. |
| `create_table_header` | `(self, title, bg_color, text_color)` | Create styled header label for tables. |
| `create_enhanced_checkbox` | `(self, text, tooltip)` | Create styled checkbox with custom appearance. |
| `toggle_sidebar` | `(self)` | Animate sidebar visibility toggle. |
| `on_animation_finished` | `(self)` | Clean up after sidebar animation completes. |
| `toggle_info` | `(self)` | Toggle visibility of sample information tooltip. |
| `hide_info_tooltip` | `(self, event)` | Hide the information tooltip. |
| `toggle_fullscreen` | `(self)` | Toggle fullscreen mode. |
| `exit_fullscreen` | `(self)` | Exit fullscreen mode. |
| `keyPressEvent` | `(self, event)` | Handle keyboard events. |
| `resizeEvent` | `(self, event)` | Handle window resize events. |
| `_has_loaded_samples` | `(self)` | Check whether any sample data is currently loaded in this window. |
| `_probe_masses` | `(self, paths, source_type)` | Quickly probe the mass list of the first accessible path. |
| `_prepare_for_load` | `(self, source_type, paths, new_masses = None)` | Decide how to handle a new load request against the current session. |
| `_open_in_new_window` | `(self, paths, source_type)` | Open a fresh MainWindow and auto-load the given paths into it. |
| `_load_selected_isotopes_for_new_samples` | `(self, sample_names)` | Load currently-selected isotopes for samples added in append mode. |
| `select_folder` | `(self)` | Show dialog to select data source type and load data. |
| `get_unique_sample_name` | `(self, base_name)` | Generate a unique sample name by appending a number if name already exists. |
| `select_folders` | `(self)` | Select NU folders for data loading. |
| `check_data_source_accessible` | `(self, path)` | Check if a data source path is still accessible. |
| `verify_all_data_sources` | `(self)` | Verify that all loaded data sources are still accessible. |
| `prompt_reconnect_data_source` | `(self, inaccessible_samples)` | Prompt user to reconnect inaccessible data sources. |
| `rebuild_isotope_dict_from_set` | `(self, isotope_set)` | Rebuild isotope dictionary from a set of (element, isotope) tuples. |
| `select_csv_files` | `(self)` | Select CSV/Excel files for data loading. |
| `select_tofwerk_files` | `(self)` | Select TOFWERK .h5 files for processing. |
| `process_folders` | `(self, folder_paths)` | Process selected NU folders. |
| `process_csv_files_with_isotopes` | `(self, selected_isotopes)` | Process CSV files with selected isotopes. |
| `process_tofwerk_files` | `(self, h5_file_paths)` | Process selected TOFWERK .h5 files. |
| `handle_csv_import` | `(self, file_paths)` | Handle CSV file import with configuration. |
| `extract_masses_from_csv_config` | `(self, config, append_mode = False)` | Extract available masses from CSV configuration. |
| `filter_csv_config_by_isotopes` | `(self, config, selected_isotopes)` | Filter CSV configuration to include only selected isotopes. |
| `handle_thread_finished` | `(self, data, run_info, time_array, sample_name, analysis_datetime = No` | Handle completion of data processing thread. |
| `handle_csv_finished` | `(self, data, run_info, time_array, sample_name, datetime_str)` | Handle completion of CSV file processing. |
| `handle_new_elements_finished` | `(self, new_data, run_info, time_array, sample_name, analysis_datetime ` | Handle completion of new element processing. |
| `handle_error` | `(self, error_message)` | Handle errors from data processing threads. |
| `display_data` | `(self, new_data, run_info, time_array, sample_name)` | Display processed data in UI. |
| `on_sample_selected` | `(self, item)` | Handle sample selection from sample table. |
| `update_sample_table` | `(self)` | Update sample table with all loaded samples. |
| `show_sample_context_menu` | `(self, position)` | Show context menu for sample table. |
| `remove_sample` | `(self, sample_name)` | Remove sample and all associated data. |
| `remove_all_samples` | `(self)` | Remove all samples and reset application. |
| `sample_table_key_press` | `(self, event)` | Handle keyboard navigation in sample table. |
| `show_periodic_table` | `(self)` | Display periodic table for element selection. |
| `show_periodic_table_after_load` | `(self)` | Show periodic table after data is loaded. |
| `handle_isotopes_selected` | `(self, selected_isotopes)` | Handle confirmed isotope selections from periodic table. |
| `handle_isotopes_selection_from_calibration` | `(self, selected_isotopes)` | Handle isotope selections from ionic calibration window. |
| `find_closest_isotope` | `(self, target_mass)` | Find closest isotope mass in loaded data. |
| `get_formatted_label` | `(self, element_key)` | Get proper isotope label from periodic table data with caching. |
| `clear_element_caches` | `(self)` | Clear element-related caches when data changes. |
| `_build_element_lookup_cache` | `(self)` | Build fast lookup cache for element display labels. |
| `_build_element_conversion_cache` | `(self)` | Build cache for element count to mass conversions. |
| `_update_periodic_table_selections` | `(self)` | Update periodic table with current isotope selections. |
| `update_parameters_table` | `(self)` | Populate detection parameters table with element-specific settings. |
| `color_parameters_table_rows` | `(self)` | Highlight parameter table rows red when >=90% of that element's |
| `load_or_initialize_parameters` | `(self, sample_name)` | Load or initialize detection parameters for sample. |
| `save_current_parameters` | `(self)` | Save current detection parameters for active sample. |
| `update_parameter_ranges` | `(self, row, method)` | Update parameter ranges based on detection method. |
| `get_element_parameters` | `(self, row)` | Get detection parameters from table row. |
| `on_parameter_changed` | `(self, row)` | Handle parameter change in table. |
| `parameters_table_clicked` | `(self, row, column)` | Handle click on parameters table row. |
| `toggle_manual_threshold_input` | `(self, row, method)` | Enable or disable manual threshold input based on method. |
| `toggle_window_size_parameters` | `(self, row, state)` | Enable or disable window size parameters. |
| `open_batch_parameters_dialog` | `(self)` | Open dialog for batch editing element parameters. |
| `filter_table` | `(self)` | Filter parameters table based on search text. |
| `on_sigma_changed` | `(self, value)` | Update sigma value for all samples and elements (Global mode), |
| `_on_sigma_mode_changed` | `(self, global_checked)` | Handle toggling between Global and Per-Isotope sigma modes. |
| `_on_per_element_sigma_changed` | `(self, row, value)` | Handle a per-element sigma edit in the parameters table. |
| `_current_element_key` | `(self)` | element_key string for the currently displayed element, or None. |
| `_visible_exclusion_entries_for` | `(self, sample_name, element_key)` | Entries that should be drawn on the plot right now. |
| `_rebuild_plot_exclusion_regions` | `(self)` | Redraw the plot's exclusion bands from the bookkeeping store. |
| `_on_exclusion_regions_changed` | `(self)` | Sync the plot's current bands back into the bookkeeping store. |
| `detect_particles` | `(self)` | Run particle detection, honouring per-sample / per-element |
| `process_single_sample` | `(self, sample_name)` | Process particle detection for single sample. |
| `detect_peaks_with_poisson` | `(self, signal, alpha = 1e-06, sample_name = None, element_key = None, ` | Detect peaks using Poisson-based methods. |
| `find_particles` | `(self, time, raw_signal, lambda_bkgd, threshold, min_continuous_points` | Find individual particles in signal. |
| `process_multi_element_particles` | `(self, all_particles)` | Process and identify multi-element particles. |
| `mark_element_changed` | `(self, sample_name, element_key)` | Mark element as having changed parameters. |
| `get_parameter_hash` | `(self, sample_name, element_key)` | Generate hash of current parameters for change detection. |
| `update_results_table` | `(self, detected_particles, signal, element, isotope)` | Update single element results table with detection results. |
| `update_multi_element_table` | `(self)` | Update multi-element particle results table. |
| `toggle_element_results` | `(self, checked)` | Show or hide single element results table. |
| `toggle_particle_results` | `(self, checked)` | Show or hide multi-element particle results table. |
| `restore_results_tables` | `(self, sample_name)` | Restore results tables for selected sample. |
| `update_element_summary` | `(self, element, isotope, detected_particles)` | Update summary statistics for selected element. |
| `show_results` | `(self)` | Display particle detection results in canvas dialog. |
| `plot_results` | `(self, mass, signal, particles, lambda_bkgd, threshold, preserve_view_` | Plot detection results with peaks and thresholds. |
| `show_mass_spectrum_popup` | `(self)` | Open a floating window showing the mean signal intensity for every |
| `switch_plot_view` | `(self, mode: str)` | Switch the main plot area between the time-domain trace ('time') |
| `_update_mz_plot` | `(self)` | Refresh the embedded m/z bar chart (page 1 of _plot_stack). |
| `highlight_selected_particle` | `(self)` | Highlight selected particle from single element results table. |
| `show_signal_selector` | `(self)` | Display signal selector dialog for multi-signal view. |
| `toggle_all_signals` | `(self)` | Toggle between single and multi-signal view. |
| `open_transport_rate_calibration` | `(self)` | Open transport rate calibration window. |
| `show_calibration_info` | `(parent)` | Display enhanced calibration information dialog. |
| `handle_calibration_result` | `(self, method, calibration_data)` | Process calibration results from calibration windows. |
| `open_ionic_calibration` | `(self)` | Open ionic calibration window for sensitivity calibration. |
| `calculate_average_transport_rate` | `(self)` | Calculate average transport rate from selected methods. |
| `update_calibration_display` | `(self)` | Update calibration information display panel. |
| `update_method_preferences` | `(self, preferences)` | Update calibration method preferences without recalculation. |
| `calculate_mass_limits` | `(self)` | Calculate mass detection limits for all elements. |
| `open_mass_fraction_calculator` | `(self)` | Open mass fraction calculator dialog. |
| `handle_mass_fractions_updated` | `(self, data)` | Handle mass fraction updates from calculator. |
| `get_molecular_weight` | `(self, element_key, sample_name = None)` | Get molecular weight for element compound. |
| `get_mass_fraction` | `(self, element_key, sample_name = None)` | Get mass fraction for element in compound. |
| `get_element_density` | `(self, element_key, sample_name = None)` | Get density for element compound. |
| `mass_to_diameter` | `(self, mass_fg, density)` | Convert mass to spherical particle diameter. |
| `update_calculations` | `(self)` | Update calculations after transport rate changes. |
| `_calculate_mass_data_optimized` | `(self, particles, element_cache, progress = None, process_all_samples ` | Calculate comprehensive mass, mole, and diameter data for particles. |
| `update_progress` | `(self, value)` | Update progress bar value. |
| `update_sample_progress` | `(self, thread_progress, sample_name, current_sample, total_samples)` | Update progress bar for sample processing. |
| `update_element_progress` | `(self, thread_progress, sample_name, current_sample, total_samples)` | Update progress bar during element processing. |
| `log_status` | `(self, message, level = 'info', context = None)` | Update status bar and log message with context. |
| `save_project` | `(self)` | Save current project to file. |
| `load_project` | `(self)` | Load project from file. |
| `export_data` | `(self)` | Export all data using external export utility. |
| `closeEvent` | `(self, event)` | Handle application close event with unsaved changes check. |
| `show_user_guide` | `(self)` | Display user guide dialog. |
| `show_detection_methods` | `(self)` | Display detection methods information dialog. |
| `show_calibration_methods` | `(self)` | Display calibration methods information dialog. |
| `show_about_dialog` | `(self)` | Display about application dialog. |
| `show_log_window` | `(self)` | Open the application log viewer window. |
| `eventFilter` | `(self, obj, event)` | Handle keyboard navigation for tables. |
| `get_snr_color` | `(self, snr)` | Get color code based on signal-to-noise ratio. |
| `calculate_accuracy` | `(self)` | Calculate suspected percentage using SNR criteria. |
| `clear_all_displays` | `(self)` | Clear all display elements when no samples available. |
