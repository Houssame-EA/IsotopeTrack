# `export_utils.py`

---

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `is_pure_element` | `(mass_fraction)` | Check if mass fraction indicates a pure element (effectively 1.0). |
| `export_data` | `(main_window: MainWindow)` | Export all sample data and summary file in one unified process with mass fraction, |
| `export_saturation_filter_info` | `(main_window, summary_file, selected_samples)` | Write the detector non-linearity filter status to the summary |
| `export_mass_fraction_info` | `(main_window: MainWindow, file_handle, selected_samples, data_type)` | Export mass fraction configuration information with data type and molecular weights. |
| `export_summary_file_with_mass_fractions` | `(main_window: MainWindow, summary_file, selected_samples, all_elements` | Export summary file with mixed element/particle calculations based on mass fractions and molecular weights. |
| `export_sample_file_with_mass_fractions` | `(main_window: MainWindow, sample_name, file_path, all_elements, ionic_` | Export individual sample file with mixed element/particle calculations based on mass fractions and molecular weights. |
