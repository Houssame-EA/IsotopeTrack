# `mainwindow.py`

---

## Classes

### `NoWheelSpinBox` *(extends `QDoubleSpinBox`)*

Custom QDoubleSpinBox that ignores mouse wheel events.

Args:
    Inherits from QDoubleSpinBox

| Method | Signature | Description |
|--------|-----------|-------------|
| `wheelEvent` | `(self, event)` | Ignore mouse wheel scroll events. |

### `NoWheelIntSpinBox` *(extends `QSpinBox`)*

Custom QSpinBox that ignores mouse wheel events.

Args:
    Inherits from QSpinBox

| Method | Signature | Description |
|--------|-----------|-------------|
| `wheelEvent` | `(self, event)` | Ignore mouse wheel scroll events. |

### `NoWheelComboBox` *(extends `QComboBox`)*

Custom QComboBox that ignores mouse wheel events.

Args:
    Inherits from QComboBox

| Method | Signature | Description |
|--------|-----------|-------------|
| `wheelEvent` | `(self, event)` | Ignore mouse wheel scroll events. |

### `MainWindow` *(extends `QMainWindow`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` | Initialize the MainWindow for IsotopeTrack application. |
| `_init_ui_enhancements` | `(self)` | Set up toast notifications and the home panel. |
| `_sync_home_state` | `(self)` | Show the home panel only while no samples are loaded (never over a plot). |
| `_recover_session` | `(self, path)` | Load a crashed session's autosave snapshot, then clear the snapshot. |
| `notify` | `(self, message, level='info', duration=3500)` | Show a non-blocking toast notification. |
| `_maybe_show_welcome` | `(self)` | Show the welcome screen on first launch unless the user opted out |
| `show_welcome` | `(self)` | Open the Welcome / Home dialog. |
| `update_window_title` | `(self, filepath=None)` | Update the window title to reflect the current project state. |
| `setup_window_size` | `(self)` | Configure initial window size and position. |
| `initialize_help_manager` | `(self)` | Initialize help dialog manager. |
| `center_on_screen` | `(self)` | Center window on screen. |
| `reset_data_structures` | `(self)` | Reset all data structures before loading a saved project. |
| `open_isobaric_correction` | `(self)` | Open the isobaric correction dialog, reusing a single instance. |
| `create_central_widget` | `(self)` | Create and configure the central widget with main UI layout. |
| `compute_isobaric_corrections` | `(self)` | Derive every applicable correction from self.selected_isotopes. |
| `preview_isobaric_correction` | `(self, sample_name=None, corrections=None)` | Return per-channel before/after for the in/out plot. No mutation. |
| `apply_isobaric_correction` | `(self, sample_names=None, corrections=None)` | Overwrite the working signal with the corrected signal. |
| `revert_isobaric_correction` | `(self)` | Restore the raw signal everywhere a correction was applied. |
| `_invalidate_particle_detection` | `(self, sample_names=None)` | Clear stale particle-detection results after the signal changed. |
| `_set_results_attention` | `(self, on)` | Highlight or un-highlight the sidebar Results button. |
| `_mark_results_changed` | `(self)` | Flag that the stored results are now out of date. |
| `create_sidebar` | `(self)` | Create sidebar with calibration and sample management tools. |
| `create_menu_bar` | `(self)` | Create application menu bar with actions. |
| `open_new_window` | `(self)` |  |
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
| `_set_content_frozen` | `(self, frozen)` | Suspend/resume repaints of the heavy plot widget during the slide. |
| `_apply_sidebar_grip_style` | `(self)` | Style the resize grip's divider line and pill holder for the theme. |
| `_sidebar_grip_press` | `(self, event)` | Begin a sidebar resize drag. |
| `_sidebar_grip_move` | `(self, event)` | Record the live drag width; applied on the next frame tick. |
| `_apply_pending_grip_width` | `(self)` | Apply the most recent width requested during a grip drag. |
| `_sidebar_grip_release` | `(self, event)` | End a sidebar resize drag and remember the chosen width. |
| `on_animation_finished` | `(self)` | Clean up after sidebar animation completes. |
| `toggle_info` | `(self)` | Toggle visibility of sample information tooltip. |
| `hide_info_tooltip` | `(self, event)` | Hide the information tooltip. |
| `toggle_fullscreen` | `(self)` | Toggle fullscreen mode. |
| `exit_fullscreen` | `(self)` | Exit fullscreen mode. |
| `keyPressEvent` | `(self, event)` | Handle keyboard events. |
| `resizeEvent` | `(self, event)` | Handle window resize events. |
| `changeEvent` | `(self, event)` | Attribute subsequent log records to whichever window is active. |
| `_has_loaded_samples` | `(self)` | Check whether any sample data is currently loaded in this window. |
| `_probe_masses` | `(self, paths, source_type)` | Quickly probe the mass list of the first accessible path. |
| `_prepare_for_load` | `(self, source_type, paths, new_masses=None)` | Decide how to handle a new load request against the current session. |
| `_open_in_new_window` | `(self, paths, source_type)` | Open a fresh MainWindow and auto-load the given paths into it. |
| `_load_selected_isotopes_for_new_samples` | `(self, sample_names)` | Load currently-selected isotopes for samples added in append mode. |
| `select_folder` | `(self)` | Show dialog to select data source type and load data. |
| `expand_nu_replicate_folders` | `(self, selected_paths)` | Expand selected folders into Nu run folders, descending into replicate subfolders. |
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
| `extract_masses_from_csv_config` | `(self, config, append_mode=False)` | Extract available masses from CSV configuration. |
| `filter_csv_config_by_isotopes` | `(self, config, selected_isotopes)` | Filter CSV configuration to include only selected isotopes. |
| `handle_thread_finished` | `(self, data, run_info, time_array, sample_name, analysis_datetime=None` | Handle completion of data processing thread. |
| `handle_csv_finished` | `(self, data, run_info, time_array, sample_name, datetime_str)` | Handle completion of CSV file processing. |
| `handle_new_elements_finished` | `(self, new_data, run_info, time_array, sample_name, analysis_datetime=` | Handle completion of new element processing. |
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
| `update_parameters_table` | `(self, force=True)` | Rebuild the detection-parameters table. |
| `_populate_parameters_table` | `(self)` | Populate detection parameters table with element-specific settings. |
| `color_parameters_table_rows` | `(self)` | Highlight parameter table rows red when >=90% of that element's |
| `load_or_initialize_parameters` | `(self, sample_name)` | Load or initialize detection parameters for sample. |
| `save_current_parameters` | `(self)` | Save current table parameters back to sample_parameters dict. |
| `update_parameter_ranges` | `(self, row, method)` | No-op: enabled states are now derived by the delegate from model data. |
| `get_element_parameters` | `(self, row)` | Get detection parameters from model row (replaces cellWidget reads). |
| `_on_param_model_changed` | `(self, row: int, col: int)` | Called when the user edits any cell in the parameters table. |
| `on_parameter_changed` | `(self, row)` | Handle parameter change in table. |
| `_on_element_selector_activated` | `(self, element_key)` | Switch the plotted element when a chip in the quick-selector is |
| `parameters_table_clicked` | `(self, row, column)` | Handle click on parameters table row. |
| `toggle_manual_threshold_input` | `(self, row, method)` | No-op: threshold cell enabled state is derived by the delegate from method. |
| `toggle_window_size_parameters` | `(self, row, state)` | No-op: window size enabled state is derived by the delegate from use_window_size. |
| `open_batch_parameters_dialog` | `(self)` | Open dialog for batch editing element parameters. |
| `filter_table` | `(self)` | Filter parameters table based on search text. |
| `on_sigma_changed` | `(self, value)` | Update sigma value for all samples and elements (Global mode). |
| `_on_sigma_mode_changed` | `(self, global_checked)` | Handle toggling between Global and Per-Isotope sigma modes. |
| `_on_per_element_sigma_changed` | `(self, row, value)` | Handle a per-element sigma edit — update model highlight and sample_parameters. |
| `_current_element_key` | `(self)` | element_key string for the currently displayed element, or None. |
| `_visible_exclusion_entries_for` | `(self, sample_name, element_key)` | Entries that should be drawn on the plot right now. |
| `_rebuild_plot_exclusion_regions` | `(self)` | Redraw the plot's exclusion bands from the bookkeeping store. |
| `_on_exclusion_regions_changed` | `(self)` | Sync the plot's current bands back into the bookkeeping store. |
| `detect_particles` | `(self)` | Run particle detection, honouring per-sample / per-element |
| `process_single_sample` | `(self, sample_name)` | Process particle detection for single sample. |
| `detect_peaks_with_poisson` | `(self, signal, alpha=1e-06, sample_name=None, element_key=None, method` | Detect peaks using Poisson-based methods. |
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
| `rebuild_particle_data` | `(self, sample_name=None)` | Rebuild the multi-element particle list of a sample from the |
| `show_results` | `(self)` | Display particle detection results in canvas dialog. |
| `plot_results` | `(self, mass, signal, particles, lambda_bkgd, threshold, preserve_view_` | Plot detection results with peaks and thresholds. |
| `show_mass_spectrum_popup` | `(self)` | Open a floating window showing the mean signal intensity for every |
| `switch_plot_view` | `(self, mode: str)` | Switch the main plot area between the time-domain trace ('time') |
| `_update_mz_plot` | `(self)` | " |
| `highlight_selected_particle` | `(self)` | Highlight selected particle from single element results table. |
| `highlight_multi_element_particle` | `(self)` | Highlight and display selected multi-element particle. |
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
| `get_molecular_weight` | `(self, element_key, sample_name=None)` | Get molecular weight for element compound. |
| `get_mass_fraction` | `(self, element_key, sample_name=None)` | Get mass fraction for element in compound. |
| `get_element_density` | `(self, element_key, sample_name=None)` | Get density for element compound. |
| `mass_to_diameter` | `(self, mass_fg, density)` | Convert mass to spherical particle diameter. |
| `get_sample_dilution` | `(self, sample_name)` | Return the dilution factor stored for a sample. |
| `set_sample_dilution` | `(self, sample_name, factor)` | Store the dilution factor for a sample. |
| `effective_volume_ml` | `(self, sample_name, element_key=None)` | Return the analyzed sample volume in millilitres for a sample. |
| `particles_per_ml` | `(self, sample_name, particle_count, element_key=None, apply_dilution=T` | Return the particle number concentration in particles per millilitre. |
| `has_transport_rate` | `(self)` | Report whether a transport rate calibration is available. |
| `open_dilution_factor_dialog` | `(self)` | Open the per sample dilution factor editor dialog. |
| `open_autosave_settings` | `(self)` | Open the Auto Save Settings dialog. |
| `maybe_prompt_dilution` | `(self)` | Show the one time dilution correction prompt when appropriate. |
| `update_calculations` | `(self)` | Update calculations after transport rate changes. |
| `_calculate_mass_data_optimized` | `(self, particles, element_cache, progress=None, process_all_samples=Fa` | Calculate comprehensive mass, mole, and diameter data for particles. |
| `update_progress` | `(self, value)` | Update progress bar value. |
| `update_sample_progress` | `(self, thread_progress, sample_name, current_sample, total_samples)` | Update progress bar for sample processing. |
| `update_element_progress` | `(self, thread_progress, sample_name, current_sample, total_samples)` | Update progress bar during element processing. |
| `log_status` | `(self, message, level='info', context=None)` | Update status bar and log message with context. |
| `save_project` | `(self)` | Save the current project. |
| `save_project_as` | `(self)` | Save the current project under a new filename (always prompts). |
| `_do_undo` | `(self)` | Step back to the previous editable-input state (Cmd/Ctrl+Z). |
| `_do_redo` | `(self)` | Step forward again after an undo (Cmd/Ctrl+Shift+Z). |
| `load_project` | `(self, filepath: str \| None=None)` | Load project from file. |
| `_update_saturation_button_text` | `(self)` | Refresh the non-linearity filter button caption with the current |
| `_particle_fwhm_s` | `(self, particle, time_arr, signal=None)` | Return the FWHM of a particle event in seconds. |
| `_particle_apex_time` | `(self, particle, time_arr)` | Return the apex time of a particle event in seconds. |
| `_particle_flat_ratio` | `(self, particle, time_arr, signal)` | Return the flat-top index of a peak: the width at the configured |
| `_merge_time_windows` | `(windows)` | Merge overlapping time intervals into their sorted union. |
| `apply_saturation_filter` | `(self, samples=None)` | Particle-level filtering of detector non-linearity events, |
| `restore_saturation_filtered` | `(self, samples=None)` | Merge previously filtered particles back into the detection |
| `get_saturation_excluded_time` | `(self, sample_name=None)` | Return the total time excluded by the non-linearity filter for a |
| `_on_isotopes_removed` | `(self, removed_isotopes)` | Keep the non-linearity filter consistent after isotopes are |
| `_sync_saturation_filter_ui` | `(self)` | Synchronize the non-linearity filter button with the current |
| `on_saturation_filter_toggled` | `(self, checked)` | Toggle the detector non-linearity filter on or off. |
| `show_saturation_filter_menu` | `(self, pos)` | Show the right-click menu of the non-linearity filter button. |
| `configure_saturation_filter` | `(self)` | Open the settings dialog of the non-linearity filter. The |
| `_refresh_after_saturation_change` | `(self)` | Refresh the plot, the results tables and the summary of the |
| `export_data` | `(self)` | Export all data using external export utility. |
| `_offer_crash_recovery` | `(self)` | Offer to reload an autosave snapshot left behind by a crashed session. |
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

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `element_chip_qss` | `(p) → str` | Stylesheet for a single element chip in the quick-selector. |
