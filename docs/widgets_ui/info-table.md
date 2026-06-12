# `Info_table.py`

---

## Classes

### `InfoTooltip` *(extends `QWidget`)*

Custom tooltip widget for displaying sample analysis information and quality metrics.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Args: |
| `set_trigger_widget` | `(self, widget)` | Set the widget (e.g. info button) whose clicks should NOT auto-close us. |
| `show` | `(self)` | Show the tooltip and install a global click filter. |
| `hide` | `(self)` | Hide the tooltip and remove the global click filter. |
| `eventFilter` | `(self, obj, event)` | Hide on any mouse click that lands outside the tooltip. |
| `setup_ui` | `(self)` | Setup the user interface. |
| `_create_stat_box` | `(self)` | Returns: |
| `update_stats` | `(self, active_samples, total_elements, Suspected_percentage, analysis_` | Update the statistics display. |
| `update_sample_content` | `(self, current_sample, selected_isotopes, detected_peaks, multi_elemen` | Update the sample content display with isotope information, SNR quality |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_build_abundance_map` | `(element_data)` | Build a {nominal_mass: fractional_abundance} map from periodic-table element data. |
| `detect_isotope_anomalies` | `(element_symbol, isotope_counts, element_data, min_detections=3)` | Detect anomalies in isotope detection consistency for a single element. |
| `batch_pvalues` | `(heights, bg_scalar, sigma=0.47)` | Calculate p-values for a batch of peak heights given a background level. |
