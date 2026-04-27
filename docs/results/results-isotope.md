# `results_isotope.py`

---

## Constants

| Name | Value |
|------|-------|
| `_BATCH_SUFFIX_RE` | `re.compile('\\s*\\[W\\d+\\]\\s*$')` |
| `CORRECTION_METHODS` | `['None', 'Exponential Law (instrumental mass fr...` |
| `DISPLAY_MODES` | `['Overlaid (Different Colors)', 'Side by Side S...` |
| `JET_POSITIONS` | `np.array([0.0, 0.11, 0.34, 0.65, 0.89, 1.0])` |
| `JET_COLORS` | `np.array([[0, 0, 143, 255], [0, 0, 255, 255], [...` |

## Classes

### `InsetColorBarItem` *(extends `pg.GraphicsWidget`)*

Draws an inset legend-style colorbar inside the plot.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, label_text, parent = None)` | Args: |
| `paint` | `(self, p, opt, widget)` | Args: |

### `SampleCorrectionDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, sample_name: str, sample_cfg: dict, available_elements: list, a` | Args: |
| `_build_ui` | `(self)` |  |
| `_on_method_changed` | `(self)` |  |
| `_auto_compute_exp` | `(self)` |  |
| `collect` | `(self) → dict` | Returns: |

### `IsotopeSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config: dict, available_elements: list, all_isotope_labels: lis` | Args: |
| `_build_ui` | `(self)` | Returns: |
| `_format_correction_details` | `(self, scfg)` | Args: |
| `_on_per_sample_toggled` | `(self, enabled)` | Args: |
| `_on_method_changed` | `(self)` |  |
| `_configure_sample_correction` | `(self, sample_name, row)` | Args: |
| `_copy_correction_to_all` | `(self)` |  |
| `_get_input_sample_names` | `(self)` | Get the list of individual replicate/sample names from the node's |
| `_compute_replicate_ratios` | `(self)` | Compute and plot the measured reference ratio for each individual replicate, |
| `_ratio_from_sample_ts` | `(pw, sample_ts, ref_num_label, ref_den_label)` | Compute ref ratio from time-series data for a single sample. |
| `_auto_compute_ref_measured` | `(self)` | Compute the measured reference ratio. |
| `_move_order_up` | `(self)` |  |
| `_move_order_down` | `(self)` |  |
| `_pick_color` | `(self, attr, btn)` | Args: |
| `collect` | `(self) → dict` | Returns: |

### `IsotopicRatioDisplayDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, isotopic_ratio_node, parent_window = None)` | Args: |
| `_is_multi` | `(self) → bool` | Returns: |
| `_sample_names` | `(self) → list` | Returns: |
| `_available_elements` | `(self) → list` | Returns: |
| `_all_isotope_labels` | `(self) → list` | Returns: |
| `_setup_ui` | `(self)` |  |
| `_auto_calc_natural` | `(self)` |  |
| `_auto_calc_standard` | `(self)` | Returns: |
| `_show_context_menu` | `(self, pos)` | Args: |
| `_download_figure` | `(self)` |  |
| `_add_toggle` | `(self, menu, label, key)` | Args: |
| `_toggle` | `(self, key, value)` | Args: |
| `_set_cfg` | `(self, key, value)` | Args: |
| `_set_data_type` | `(self, dt)` | Args: |
| `_set_elem` | `(self, key, elem)` | Args: |
| `_set_correction` | `(self, method)` | Args: |
| `_set_display_mode` | `(self, mode)` | Args: |
| `_open_settings` | `(self)` |  |
| `_open_plot_settings` | `(self)` | Open PlotSettingsDialog via the adapter bridge. |
| `_refresh` | `(self)` |  |
| `_prepare_sample` | `(self, element_data, cfg, sample_name = None)` | Args: |
| `_build_csv_data` | `(self) → pd.DataFrame | None` | Build a DataFrame of per-particle isotopic ratio data for CSV export. |
| `_correct_per_replicate` | `(self, df, ratios, eff_cfg, e1, e2, sources)` | Apply per-replicate exponential correction. |
| `_compute_replicate_ref_ratio` | `(self, sample_name, ref_num_label, ref_den_label)` | Compute the reference ratio for a specific replicate sample. |
| `_ratio_from_time_series` | `(self, pw, sample_ts, ref_num_label, ref_den_label)` | Args: |
| `_build_labels` | `(self, cfg, sample_name = None)` | Args: |
| `_add_scatter` | `(self, pi, x, y, cfg, color, color_values = None)` | Args: |
| `_add_inset_colorbar` | `(self, pi, cfg, vmin, vmax)` | Args: |
| `_add_poisson_ci` | `(self, pi, cfg, mean_ratio, color, x_data = None, sample_name = None)` | Args: |
| `_make_legend_proxy` | `(self, color, style = 'solid', width = 2)` | Args: |
| `_add_reference_lines` | `(self, pi, cfg, ratios_linear, legend_items, sample_name = None)` | Args: |
| `_apply_labels_and_font` | `(self, pi, cfg, x_label = None, y_label = None, sample_name = None)` | Args: |
| `_draw_single` | `(self, pi, plot_data, cfg)` | Args: |
| `_draw_combined` | `(self, pi, plot_data, cfg)` | Args: |
| `_draw_subplots` | `(self, plot_data, cfg)` | Args: |
| `_draw_side_by_side` | `(self, plot_data, cfg)` | Args: |
| `_draw_single_on_plot` | `(self, pi, edf, cfg, color, sample_name)` | Args: |

### `IsotopicRatioPlotNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `_auto_configure_elements` | `(self)` |  |
| `_get_elements` | `(self) → list` | Returns: |
| `extract_plot_data` | `(self)` | Returns: |

## Functions

### `_mass_of`

```python
def _mass_of(label: str) → float | None
```

Extract mass number from an isotope label like '206Pb', '203Tl'.
Delegates to extract_mass_and_element from utils_sort.


**Returns:**

- `Mass number as float, or None if not found.`

**Args:**

- `label (str): Label text.`

### `_strip_batch_suffix`

```python
def _strip_batch_suffix(sample_name: str) → str
```

Strip batch window suffix like ' [W1]' from a sample name.

BatchSampleSelectorNode renames samples as  ``"<orig> [W<n>]"``.
This helper recovers the original name so we can look it up in the
source window's ``sample_particle_data``.

>>> _strip_batch_suffix("NIST610 [W2]")
'NIST610'
>>> _strip_batch_suffix("plain_sample")
'plain_sample'

**Args:**

- `sample_name (str): The sample name.`

**Returns:**

- `str: Result of the operation.`

### `make_jet_colormap`

```python
def make_jet_colormap()
```

Create a jet-like PyQtGraph ColorMap for scatter color dimension.

**Returns:**

- `object: Result of the operation.`

### `get_overall_mean_signal`

```python
def get_overall_mean_signal(parent_window, formatted_label: str) → float | None
```


**Args:**

- `parent_window (Any): The parent window.`
- `formatted_label (str): The formatted label.`

**Returns:**

- `float | None: Result of the operation.`

### `compute_ratio_from_mean_signals`

```python
def compute_ratio_from_mean_signals(parent_window, num_label: str, den_label: str) → tuple
```


**Args:**

- `parent_window (Any): The parent window.`
- `num_label (str): The num label.`
- `den_label (str): The den label.`

**Returns:**

- `tuple: Result of the operation.`

### `get_all_isotope_labels`

```python
def get_all_isotope_labels(parent_window) → list
```


**Args:**

- `parent_window (Any): The parent window.`

**Returns:**

- `list: Result of the operation.`

### `compute_exponential_correction`

```python
def compute_exponential_correction(r_measured: np.ndarray, m_num: float, m_den: float, ref_certified: float, ref_measured: float, m_ref_num: float, m_ref_den: float) → np.ndarray
```


**Args:**

- `r_measured (np.ndarray): The r measured.`
- `m_num (float): The m num.`
- `m_den (float): The m den.`
- `ref_certified (float): The ref certified.`
- `ref_measured (float): The ref measured.`
- `m_ref_num (float): The m ref num.`
- `m_ref_den (float): The m ref den.`

**Returns:**

- `np.ndarray: Result of the operation.`

### `apply_isotope_correction`

```python
def apply_isotope_correction(r_measured: np.ndarray, config: dict) → np.ndarray
```


**Args:**

- `r_measured (np.ndarray): The r measured.`
- `config (dict): Configuration dictionary.`

**Returns:**

- `np.ndarray: Result of the operation.`

### `_find_particles_for_sample`

```python
def _find_particles_for_sample(sample_name, dk, node = None, parent_window = None)
```

Find unfiltered particles for a sample.

Prefer window sources (unfiltered) over node input (may be isotope-filtered).

FIX (batch windows): When sample_name contains a batch suffix like
" [W1]", we also search all open windows using the *original* name
so that particles from any batch source window can be found.

**Args:**

- `sample_name (Any): The sample name.`
- `dk (Any): The dk.`
- `node (Any): Tree or graph node.`
- `parent_window (Any): The parent window.`

**Returns:**

- `list: Result of the operation.`

### `get_correction_factor`

```python
def get_correction_factor(config: dict) → float
```


**Args:**

- `config (dict): Configuration dictionary.`

**Returns:**

- `float: Result of the operation.`

### `build_equation_text`

```python
def build_equation_text(config: dict, sample_name: str = None) → str
```


**Args:**

- `config (dict): Configuration dictionary.`
- `sample_name (str): The sample name.`

**Returns:**

- `str: Result of the operation.`

### `_default_sample_correction`

```python
def _default_sample_correction() → dict
```


**Returns:**

- `dict: Result of the operation.`

### `get_sample_correction_config`

```python
def get_sample_correction_config(cfg: dict, sample_name: str = None) → dict
```


**Args:**

- `cfg (dict): The cfg.`
- `sample_name (str): The sample name.`

**Returns:**

- `dict: Result of the operation.`

### `poisson_ratio_sigma`

```python
def poisson_ratio_sigma(R: float, lambda_B: np.ndarray) → np.ndarray
```


**Args:**

- `R (float): The R.`
- `lambda_B (np.ndarray): The lambda B.`

**Returns:**

- `np.ndarray: Result of the operation.`

### `poisson_ci_curves`

```python
def poisson_ci_curves(R: float, x_range: np.ndarray, k: float = 2.0)
```


**Args:**

- `R (float): The R.`
- `x_range (np.ndarray): The x range.`
- `k (float): The k.`

**Returns:**

- `tuple: Result of the operation.`
