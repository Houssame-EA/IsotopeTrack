# `ionic_CAL.py`

---

## Classes

### `IonicCalibrationWindow` *(extends `QMainWindow`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Initialize the Ionic Calibration Window. |
| `initUI` | `(self)` | Initialize and configure the user interface. |
| `apply_theme` | `(self, *_)` | Re-apply the shared calibration stylesheet from the current palette. |
| `_refresh_tool_icons` | `(self)` | Recolour the toolbar icons for the current theme. |
| `_refresh_return_button` | `(self)` | Apply the theme's 'Back to Main' style and icon colour, if the |
| `_refresh_plot_label_colors` | `(self)` | Swap the pyqtgraph axis label color to the current theme's |
| `_refresh_results_table_colors` | `(self)` | When the theme changes, any existing background QBrush() values |
| `_tool` | `(self, action, icon)` | A flat toolbar button driven by *action*, with a themed icon. |
| `_separator` | `()` |  |
| `setup_toolbar` | `(self)` | Build the toolbar card at the top of the window. |
| `setup_data_tab` | `(self)` | Set up the Data Management tab. |
| `setup_sensitivity_tab` | `(self)` | Set up the Manual Sensitivity tab. |
| `setup_calibration_tab` | `(self)` | Set up the Calibration Results tab. |
| `_log_tab_switch` | `(self, index)` | Log which tab the user switches to. |
| `create_shortcuts` | `(self)` | Create keyboard shortcuts for common actions. |
| `next_tab` | `(self)` | Switch to the next tab in the tab widget. |
| `prev_tab` | `(self)` | Switch to the previous tab in the tab widget. |
| `_density_for` | `(self, element, data=None)` | Density of *element* from the periodic table, else the record's. |
| `_seed_slope` | `(self, isotope_key)` | Starting slope for a new manual value: the Simple-linear fit when |
| `_manual_record` | `(self, isotope_key, slope)` | Build the calibration record for a manual slope. |
| `apply_manual_slope` | `(self, isotope_key, slope, refresh=True)` | Make *slope* the manual calibration of one isotope. |
| `clear_manual_slope` | `(self, isotope_key, refresh=True)` | Remove the manual calibration of one isotope and fall back to the |
| `_best_fit_display` | `(data)` | Display name of the fitted method with the highest R². |
| `_refresh_after_manual_change` | `(self, isotope_key)` | Bring the sensitivity row, results table and plot up to date. |
| `_sensitivity_row` | `(self, isotope_key)` | Row of *isotope_key* in the sensitivity table, or -1. |
| `_sync_sensitivity_row` | `(self, isotope_key)` | Show the stored override state and slope in the isotope's row. |
| `update_sensitivity_table` | `(self)` | Rebuild the sensitivity table, one row per selected isotope. |
| `on_override_changed` | `(self, element_key, checked)` | Turn the manual slope of one isotope on or off. |
| `on_slope_changed` | `(self, element_key, value)` | Apply an edited manual slope from the sensitivity table. |
| `_set_global_slope` | `(self, keys)` | Give every isotope in *keys* the global manual slope. |
| `_all_isotope_keys` | `(self)` |  |
| `apply_global_slope_to_all` | `(self)` | Override every isotope with the global manual slope. |
| `apply_global_slope_to_checked` | `(self)` | Give the global manual slope to the isotopes already overridden. |
| `update_calibration_with_overrides` | `(self)` | Rebuild the manual records against the current calibration data. |
| `extract_concentration_from_sample_name` | `(self, sample_name)` | Extract concentration value from sample name using flexible pattern matching. |
| `apply_global_method` | `(self)` | Apply the selected global method to all isotopes. |
| `_abundance_of` | `(self, element, mass)` | Natural abundance (%) of an isotope from the periodic table, or None. |
| `_method_record` | `(self, key, data)` | The calibration record of the method in use for *key*. |
| `compute_checks` | `(self)` | Run every calibration check on the current results. |
| `_drift_check` | `(data, keep)` | Repeated-standard drift on the uncorrected signals; not flagged |
| `_history` | `(self)` |  |
| `run_checks` | `(self, record_history=False)` | Run the checks, show the warning count on the Checks button and, |
| `show_checks` | `(self)` | Open the Checks window: one row per isotope, warnings highlighted. |
| `_fit_with_drift` | `(self, x, y, y_std, included_mask, density)` | Run the three fits, first correcting the standards for drift when |
| `_on_drift_toggled` | `(self, checked)` | Refit with or without drift correction when the toggle changes. |
| `apply_manual_to_all_isotopes` | `(self)` | Switch every selected isotope to a manual slope. |
| `apply_auto_method_selection` | `(self)` | Automatically select the best method for each isotope based on highest R². |
| `apply_method_to_all_isotopes` | `(self, method_name)` | Apply the specified method to all isotopes. |
| `auto_fill_concentrations` | `(self)` | Fill concentrations from the sample names. |
| `filter_results_table` | `(self)` | Filter the results table based on the selected option. |
| `update_results_table_best_methods` | `(self)` | Update the results table showing only the best method for each isotope. |
| `show_method_summary` | `(self)` | Show a summary of method preferences in the status bar. |
| `export_results` | `(self)` | Export calibration results to a CSV file. |
| `export_sensitivity_results` | `(self)` | Export sensitivity settings to CSV. |
| `_current_time_plot_context` | `(self)` | Return (folder, isotope_key) describing what is currently shown |
| `_on_time_exclusion_changed` | `(self)` | Persist the current widget regions into the keyed storage dicts |
| `_restore_time_exclusions` | `(self, folder, isotope_key)` | Load the stored regions for (folder, isotope_key) into the |
| `update_time_plot` | `(self)` | Update the time plot based on selected sample and isotope. |
| `show_periodic_table` | `(self)` | Show the periodic table dialog for element selection. |
| `_handle_selection_confirmed` | `(self, selected_data)` | Handle selection confirmation and close dialog. |
| `on_selection_confirmed` | `(self, selected_data)` | Handle confirmed selections from the periodic table. |
| `on_isotope_selected` | `(self, element, mass, abundance)` | Handle individual isotope selections. |
| `update_plot_isotope_combo` | `(self)` | Update the isotope combo box for the time plot. |
| `save_session` | `(self)` | Save session using the CSV handler. |
| `load_session` | `(self)` | Load session from CSV format. |
| `_go_prev_isotope` | `(self)` | Navigate to the previous isotope in the combo box. |
| `_go_next_isotope` | `(self)` | Navigate to the next isotope in the combo box. |
| `update_element_isotope_combo` | `(self)` | Update element-isotope combo with sorted isotopes. |
| `update_ui_from_compressed_data` | `(self)` | Update UI elements after loading compressed data. |
| `update_sample_combo` | `(self)` | Update the sample combo box with folder names. |
| `table_key_press_event` | `(self, event)` | Handle key press events for copy/paste operations. |
| `show_context_menu` | `(self, position)` | Show context menu for cell operations. |
| `set_selected_cells_to_value` | `(self, value)` | Set selected cells to a specific value. |
| `set_selected_cells_to_minus_one` | `(self)` | Set all selected cells to -1. |
| `copy_cells` | `(self)` | Copy selected cells to clipboard. |
| `paste_cells` | `(self)` | Paste clipboard data into selected cells. |
| `on_data_changed` | `(self, item)` | Handle data changes in the table. |
| `update_table_rows` | `(self)` | Update table rows with loaded folder data. |
| `update_table_columns` | `(self)` | Update table columns with sorted isotope labels while preserving existing data. |
| `update_periodic_table` | `(self)` | Update periodic table with available masses. |
| `parse_header_for_element_isotope_and_unit` | `(self, header)` | Parse header text to extract element, mass, and unit information. |
| `plot_count_vs_time` | `(self, selected_row=None, selected_col=None)` | Plot count vs time data with proper isotope labels. |
| `on_table_cell_clicked` | `(self, row, col)` | Handle table cell click events. |
| `calculate_calibration` | `(self)` | Calculate calibration with proper isotope matching. |
| `get_table_data` | `(self)` | Get table data with both display and internal formats. |
| `set_table_data` | `(self, data)` | Set table data restoring both formats. |
| `display_selected_calibration` | `(self, selection)` | Handle selection changes in combo box. |
| `update_calibration_display` | `(self)` | Update the calibration display when method is changed and save preference. |
| `display_calibration` | `(self, element, isotope)` | Display calibration data with original isotope labels. |
| `convert_concentration` | `(self, value, from_unit, to_unit)` | Convert concentration between different units. |
| `update_concentration_unit` | `(self, new_unit)` | Update concentration values when unit is changed. |
| `update_results_table` | `(self)` | Update the results table with calibration results for all methods. |
| `update_results_table_with_method` | `(self, isotope_key, data, unit)` | Update results table with original isotope labels. |
| `get_isotope_label` | `(self, element, mass)` | Get the isotope label directly from the isotope data. |
| `element_selected` | `(self, element)` | Placeholder for element selection signal handler. |
| `refit_isotope` | `(self, isotope_key)` | Re-run the three fits for a single isotope using the current |
| `on_calibration_point_exclusion_toggled` | `(self, index)` | Toggle exclusion of the clicked point for the current isotope, |
| `reset_current_isotope_exclusions` | `(self)` | Clear all exclusions for the currently-displayed isotope and refit. |
| `_update_exclusion_status_label` | `(self, isotope_key, total_points)` | Refresh the small status label next to the plot controls. |
| `_set_manual_slope_controls_visible` | `(self, visible: bool)` | Show or hide the inline manual-slope input + Match-fit button. |
| `_sync_manual_slope_input` | `(self, isotope_key, data, current_unit)` | Populate the inline slope input for the currently-displayed |
| `on_manual_match_fit` | `(self)` | Copy the Simple-linear slope into the manual input for the |
| `on_manual_slope_changed` | `(self)` | Apply the inline manual slope to the isotope shown on the |
| `next_isotope` | `(self)` |  |
| `prev_isotope` | `(self)` |  |
| `perform_calibration` | `(self, concentrations, progress=None)` | Orchestrate calibration calculations for all selected isotopes. |
| `load_folders` | `(self)` | Load folders or CSV files for calibration with improved dialog structure. |
| `select_tofwerk_files` | `(self)` | Handle TOFWERK .h5 file selection for calibration. |
| `handle_tofwerk_import` | `(self, h5_file_paths)` | Handle TOFWERK .h5 file import for calibration. |
| `select_nu_folders` | `(self)` | Handle NU folder selection for calibration. |
| `select_data_files` | `(self)` | Handle data file selection for CSV, TXT, and Excel formats. |
| `handle_csv_import` | `(self, selected_paths)` | Handle CSV/Excel file import using loading.csv. |
| `handle_folder_import` | `(self, selected_paths)` | Handle folder import with mass range validation. |
| `load_data` | `(self)` | Load data from folders or files. |
| `prompt_save_changes` | `(self)` | Prompt user to save changes if data is modified. |
| `closeEvent` | `(self, event)` | Handle window close event. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_ual` | `()` | Return the UserActionLogger, or None if logging isn't ready. |
| `_r2_text` | `(value, digits)` | R² for display; '—' when there is none (a manual slope is not a fit). |
| `_build_ionic_status_colors` | `(p) → dict` | Row-highlight colors used to indicate calibration method status in |
