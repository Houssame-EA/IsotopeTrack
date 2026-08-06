# `export_utils.py`

---

## Classes

### `_ExportWorker` *(extends `QThread`)*

Background worker that writes the export files off the UI thread.

Building a summary row means walking every particle of every selected
sample, so a large project used to lock the interface for the whole export
and the window stopped repainting. The worker performs only the file
writing; everything that reads a widget — sample selection, unit choices,
mass-limit recalculation and the isotope label cache — is resolved on the
main thread before the worker starts, so nothing here touches Qt.

Signals:
    progressed (int, str): Percent complete (0-100) and a status message.
    done (object): Emitted on completion with ``{'successful': int,
        'failed': [(name, error), ...], 'cancelled': bool}``.
    failed (str): Emitted when the run aborts with an unexpected error.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, main_window, export_dir, export_type, selected_samples, sample_` | Store everything the run needs, already resolved from the UI. |
| `cancel` | `(self)` | Request cancellation; the loop stops before the next file. |
| `_steps` | `(self)` | Number of files this run will attempt to write. |
| `run` | `(self)` | Write every requested file, reporting progress as each completes. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `is_pure_element` | `(mass_fraction)` | Check if mass fraction indicates a pure element (effectively 1.0). |
| `export_data` | `(main_window: MainWindow)` | Export all sample data and summary file in one unified process with mass fraction, |
| `export_saturation_filter_info` | `(main_window, summary_file, selected_samples)` | Write the detector non-linearity filter status to the summary |
| `export_mass_fraction_info` | `(main_window: MainWindow, file_handle, selected_samples, data_type)` | Export mass fraction configuration information with data type and molecular weights. |
| `export_summary_file_with_mass_fractions` | `(main_window: MainWindow, summary_file, selected_samples, all_elements` | Export summary file with mixed element/particle calculations based on mass fractions and molecular weights. |
| `export_sample_file_with_mass_fractions` | `(main_window: MainWindow, sample_name, file_path, all_elements, ionic_` | Export individual sample file with mixed element/particle calculations based on mass fractions and molecular weights. |
