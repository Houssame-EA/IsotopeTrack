# `Info_table.py`

---

## Classes

### `InfoTooltip` *(extends `QWidget`)*

Custom tooltip widget for displaying sample analysis information and quality metrics.

Uses SNR for per-isotope quality assessment and natural-abundance ratios
(from the periodic table widget) for isotope consistency anomaly detection.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `set_trigger_widget` | `(self, widget)` | Set the widget (e.g. info button) whose clicks should NOT auto-close us. |
| `show` | `(self)` | Show the tooltip and install a global click filter. |
| `hide` | `(self)` | Hide the tooltip and remove the global click filter. |
| `eventFilter` | `(self, obj, event)` | Hide on any mouse click that lands outside the tooltip. |
| `setup_ui` | `(self)` | Setup the user interface. |
| `_create_stat_box` | `(self)` | Returns: |
| `update_stats` | `(self, active_samples, total_elements, Suspected_percentage, analysis_` | Update the statistics display. |
| `update_sample_content` | `(self, current_sample, selected_isotopes, detected_peaks, multi_elemen` | Update the sample content display with isotope information, SNR quality |

## Functions

### `_build_abundance_map`

```python
def _build_abundance_map(element_data)
```

Build a {nominal_mass: fractional_abundance} map from periodic-table element data.

The periodic table stores abundance as a percentage (0-100). We convert to
fraction (0-1) for statistical calculations.


**Args:**

- `element_data (dict): Element dict from PeriodicTableWidget, containing`
- `an 'isotopes' list of dicts with 'mass', 'abundance', 'label'.`


**Returns:**

- `dict: {int(round(mass)): fractional_abundance} for isotopes with abundance > 0`

### `detect_isotope_anomalies`

```python
def detect_isotope_anomalies(element_symbol, isotope_counts, element_data, min_detections = 3)
```

Detect anomalies in isotope detection consistency for a single element.

Compares observed detection counts across isotopes of the same element
against expected ratios from natural abundances using a chi-squared test.

Anomaly types reported:
missing_major     – Major isotope (>10 %) has 0 detections while a
minor isotope was detected.
reverse_detection – Less-abundant isotope detected more than the
more-abundant one (chi-squared p < 0.01).
ratio_anomaly     – Both detected, but observed ratio significantly
deviates from natural abundance (chi-squared p < 0.01).
missing_minor_unexpected – Minor isotope has 0 detections but Poisson
probability of 0 given expected count is < 5 %.
expected           – Minor isotope not detected, consistent with low
abundance (Poisson p(0) > 5 %).


**Args:**

- `element_symbol (str): Element symbol, e.g. "Ag".`
- `isotope_counts (dict): {isotope_mass (float): n_detected_peaks (int)}`
- `The keys are the exact masses from the periodic table.`
- `element_data (dict): Element dict from PeriodicTableWidget.`
- `min_detections (int): Minimum total detections to run the test.`


**Returns:**

- `list[dict]: Anomaly records with keys:`
- `type, isotope_a, isotope_b, details, severity, p_value`

### `batch_pvalues`

```python
def batch_pvalues(heights, bg_scalar, sigma = 0.47)
```

Calculate p-values for a batch of peak heights given a background level.


**Args:**

- `heights (list or np.ndarray): Detected peak heights.`
- `bg_scalar (float): Mean background level.`
- `sigma (float): Sigma value for compound Poisson (if applicable).`


**Returns:**

- `np.ndarray: Array of calculated p-values.`
