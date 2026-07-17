# `peak_detection.py`

---

## Constants

| Name | Value |
|------|-------|
| `INTEGRATION_METHODS` | `['Background', 'Threshold', 'Midpoint']` |
| `PEAK_SPLIT_METHODS` | `['No Splitting', '1D Watershed']` |

## Classes

### `CompoundPoissonLognormal`

Compound Poisson-Lognormal distribution using analytical approximation.

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_threshold` | `(self, lambda_bkgd, alpha, sigma=0.55)` | Calculate compound Poisson threshold using log-normal approximation. |

### `CompoundPoissonLognormalOptimized`

Optimized Compound Poisson-Lognormal with dict cache

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` |  |
| `get_threshold` | `(self, lambda_bkgd, alpha, sigma=0.55)` | Calculate compound Poisson threshold with caching. |
| `clear_cache` | `(self)` | Clear the threshold cache (e.g. when sigma changes). |

### `CompoundPoissonLognormaltable`

Lookup-table based Compound Poisson-Lognormal threshold.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, lut_path: str \| None=None)` |  |
| `_load_table` | `(self, path: str) → None` | Load and build the RegularGridInterpolator from the .npz file. |
| `get_threshold` | `(self, lambda_bkgd: float, alpha: float, sigma: float=0.55) → float` | Return the CPLN detection threshold. |
| `clear_cache` | `(self) → None` | No-op kept for interface compatibility with other classes. |

### `PeakDetection`

Features:

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` | Initialize PeakDetection instance. |
| `clear_threshold_cache` | `(self) → None` | Reset the lru_cache on ``_cached_threshold_calculation``. |
| `optimize_data_types` | `(self, signal)` | Optimize signal data types to reduce memory usage. |
| `prepare_signals_for_processing` | `(self, signals_dict)` | Prepare all signals for processing by optimizing data types. |
| `_find_particles_numba` | `(raw_signal, threshold, lambda_bkgd, min_continuous_points, integratio` | JIT-compiled particle detection with configurable integration baseline. |
| `_find_particles_numba_dynamic` | `(raw_signal, threshold_arr, lambda_bkgd_arr, min_continuous_points, in` | JIT-compiled particle detection for dynamic array thresholds (window) |
| `calculate_iterative_threshold` | `(self, signal, method, alpha=1e-06, max_iters=4, manual_threshold=10.0` | Calculate threshold using iterative background refinement with |
| `_rolling_background` | `(self, signal, threshold, window_size)` | Calculates a dynamic rolling background excluding peaks above threshold. |
| `_calculate_array_threshold` | `(self, lambda_bkgd_array, method, alpha, sigma=0.55)` | Fast threshold calculation for moving window arrays. |
| `_calculate_single_threshold` | `(self, lambda_bkgd, method, alpha, sigma=0.55)` | Calculate threshold for a single background value. |
| `_cached_threshold_calculation` | `(self, lambda_bkgd, method, alpha, isotope_key)` | Cached threshold calculation for performance. |
| `calculate_thresholds_batch_safe` | `(self, signals_dict, params_dict, method_groups=None, isotope_mapping=` | Safe batch threshold calculation with iterative refinement and window size support. |
| `calculate_thresholds_batch` | `(self, signals_dict, params_dict, method_groups=None)` | Wrapper for safe batch threshold processing. |
| `_compute_integration_level` | `(lambda_bkgd, threshold, integration_method)` | Compute the integration baseline level based on the chosen method. |
| `split_peak_region` | `(self, signal, start_idx, end_idx, lambda_bkgd, threshold, split_metho` | Dispatcher: apply the chosen splitting method to a single peak region |
| `_split_no_split` | `(signal, start_idx, end_idx, **kwargs)` | Baseline: return the region unchanged. |
| `_split_watershed_1d` | `(signal, start_idx, end_idx, lambda_bkgd, threshold, min_valley_ratio=` | 1D Watershed peak splitting — operates directly on the raw signal |
| `_particle_from_region` | `(time, signal, start_idx, end_idx, lambda_bkgd, threshold, integration` | Extract particle metrics from a single [start_idx, end_idx] sub-region. |
| `find_particles_safe` | `(self, time, raw_signal, lambda_bkgd, threshold, min_width=3, min_cont` | Threading-safe particle detection with configurable integration method |
| `find_particles_vectorized` | `(self, time, raw_signal, lambda_bkgd, threshold, min_width=3, min_cont` | Vectorized particle detection using NumPy with configurable integration |
| `find_particles` | `(self, time, raw_signal, lambda_bkgd, threshold, min_width=3, min_cont` | Wrapper for safe particle detection. |
| `process_single_sample_safe` | `(self, main_window, sample_name)` | Threading-safe sample processing with iterative calculation. |
| `process_single_sample` | `(self, main_window, sample_name)` |  |
| `detect_peaks_with_poisson` | `(self, signal, alpha=1e-06, sample_name=None, element_key=None, method` | Detect peaks using Poisson-based methods with iterative calculation. |
| `detect_particles_incremental` | `(self, main_window)` | Incremental particle detection for changed elements only. |
| `process_sample_incremental` | `(self, main_window, sample_name, changed_elements)` | Process only changed elements for a sample incrementally. |
| `merge_detection_results` | `(self, main_window, sample_name, new_results, changed_elements)` | Merge new detection results with existing results. |
| `update_current_sample_display` | `(self, main_window, sample_name)` | Update display for currently selected sample. |
| `apply_window_size` | `(self, signal, use_window_size, window_size)` | Apply window size limitation to signal if enabled. |
| `get_changed_elements` | `(self, main_window, sample_name)` | Determine which elements need reprocessing for a sample. |
| `process_multi_element_particles` | `(self, all_particles, time_array, sample_detected_peaks, selected_isot` | Process and identify multi-element particles. |
| `is_overlapping` | `(self, particle, multi_particle, min_overlap_percentage=75.0)` | Check if particles overlap by at least `min_overlap_percentage` percent. |
| `detect_particles` | `(self, main_window)` | Main threading-safe particle detection function. |
| `get_snr_color` | `(self, snr)` | Get color based on signal-to-noise ratio. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `erf` | `(x: float \| np.ndarray) → float \| np.ndarray` | Error function using SciPy's optimized implementation. |
| `erfinv` | `(x: float \| np.ndarray) → float \| np.ndarray` | Inverse error function using SciPy's optimized implementation. |
| `lognormal_cdf` | `(x: np.ndarray, mu: float, sigma: float) → np.ndarray` | Optimized log-normal cumulative distribution function. |
| `lognormal_quantile` | `(quantile: np.ndarray, mu: float, sigma: float) → np.ndarray` | Optimized log-normal quantile function. |
| `_poisson_pdf_numba` | `(k, lam)` | Numba-optimized Poisson probability mass function for single values. |
| `poisson_pdf` | `(k: np.ndarray, lam: float) → np.ndarray` | Optimized Poisson probability mass function. |
| `zero_trunc_quantile` | `(lam: np.ndarray \| float, y: np.ndarray \| float) → np.ndarray \| float` | Calculate zero-truncated Poisson quantile. |
| `sum_iid_lognormals` | `(n: float, mu: float, sigma: float, method: str='Fenton-Wilkinson') → ` | Sum of n identical independent log-normal distributions. |
| `_standard_quantile_scalar` | `(p)` | Optimized scalar standard normal quantile function. |
| `standard_quantile` | `(p: float \| np.ndarray) → float \| np.ndarray` | Optimized standard normal quantile function. |
| `compound_poisson_lognormal_quantile_approximation` | `(q: float, lam: float, mu: float, sigma: float) → float` | Compound Poisson log-normal quantile approximation. |
| `compound_poisson_lognormal_quantile_approximation_fast` | `(q: float, lam: float, mu: float, sigma: float) → float` | Optimized compound Poisson log-normal quantile approximation. |
| `_assignments_to_regions` | `(assignments: np.ndarray, n_peaks: int, start_idx: int)` | Convert per-sample peak-index assignments to a list of contiguous |
