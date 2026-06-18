# `export_utils.py`

---

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `is_pure_element` | `(mass_fraction)` | Check if mass fraction indicates a pure element (effectively 1.0). |
| `get_molecular_weight_for_export` | `(main_window, element_key, sample_name=None)` | Get molecular weight for export calculations. |
| `export_data` | `(main_window)` | Export all sample data and summary file in one unified process with mass fraction, |
| `export_saturation_filter_info` | `(main_window, summary_file, selected_samples)` | Write the detector non-linearity filter status to the summary |
| `export_mass_fraction_info` | `(main_window, file_handle, selected_samples, data_type)` | Export mass fraction configuration information with data type and molecular weights. |
| `export_summary_file_with_mass_fractions` | `(main_window, summary_file, selected_samples, all_elements, element_la` | Export summary file with mixed element/particle calculations based on mass fractions and molecular weights. |
| `export_sample_file_with_mass_fractions` | `(main_window, sample_name, file_path, all_elements, ionic_data, thresh` | Export individual sample file with mixed element/particle calculations based on mass fractions and molecular weights. |
