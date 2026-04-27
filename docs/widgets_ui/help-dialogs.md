# `help_dialogs.py`

---

## Classes

### `SPICPToFMSSimulator`

Physically realistic SP-ICP-ToF-MS signal generator.

Background — compound Poisson-lognormal per bin
------------------------------------------------
Each dwell bin receives N ~ Poisson(lambda_bg) ions, where each
ion contributes X_i ~ Lognormal(mu_sir, sigma_sir) with E[X_i]=1.
Bin signal = sum(X_i).  When N=0 the bin reads exactly zero,
producing the characteristic sparse, continuous-valued background
seen in real ToF data.

Particle peak width — derived automatically from dwell time
-----------------------------------------------------------
Ion cloud transit duration ~ 400 µs (fixed physical constant).

peak_bins = max(1, round(400 µs / dwell_µs))

Particle signal model (compound Poisson + lognormal temporal profile)
---------------------------------------------------------------------
For each nanoparticle:
1. Expected ion yield drawn from Lognormal(µ_size, sigma_size)
to represent polydisperse particle size distribution.
2. Actual detected ions  N ~ Poisson(expected_yield).
3. Each ion contributes  X_i ~ Lognormal(µ_sir, sigma_sir)
with E[X_i] = 1  (single-ion response distribution).
4. Ions are distributed across peak_bins via Multinomial(N, probs)
where probs follow a lognormal temporal envelope:
probs[k] ∝ LN_PDF(k + 0.5 | µ_temporal, σ_temporal)
This produces the asymmetric peak shape observed in real data:
sharp rise as the ion cloud enters the plasma, followed by a
longer lognormal tail.
5. Per-bin signal = sum of lognormal responses for ions in that bin.

The temporal profile parameters (σ_temporal=0.64, scale=3.08) were
fitted from real spICP-ToF-MS particle events measured at 204 µs
dwell time and are scaled proportionally for other dwell times.

Both background and particle signals share the same SIR distribution,
producing continuous-valued output identical in character to real
spICP-ToF-MS data.

| Method | Signature | Description |
|--------|-----------|-------------|
| `_temporal_profile` | `(self, dwell_us)` | Compute the lognormal temporal probability vector for distributing |
| `generate` | `(self, acq_time_s = 60.0, dwell_us = 76.71, lambda_bg = 1.1, n_particl` | Args: |

### `InteractiveEquationVisualizer` *(extends `QWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `_grp_acquisition` | `(self)` | Returns: |
| `_grp_background` | `(self)` | Returns: |
| `_grp_particles` | `(self)` | Returns: |
| `_grp_detection` | `(self)` | Returns: |
| `_sl_to_spin` | `(self, spin, val)` | Slider moved -> update spinbox (silently) then schedule update. |
| `_spin_to_sl` | `(sl, val)` | Spinbox changed -> update slider (silently). Schedule already fired. |
| `_alpha_moved` | `(self, v)` | Args: |
| `_schedule` | `(self)` |  |
| `_run_simulation` | `(self)` |  |
| `_update_plots` | `(self)` |  |
| `_draw_trace` | `(self)` |  |
| `_draw_histogram` | `(self)` | Histogram of DETECTED events only (signal > threshold). |
| `_update_stats` | `(self)` |  |
| `_calc_threshold` | `(self, method, bg, alpha, manual, sigma)` | Args: |

### `PeakIntegrationVisualizer` *(extends `QWidget`)*

Interactive visualizer showing three peak integration methods:
- Background: integrate from where signal crosses background level.
- Threshold: integrate only the region above the detection threshold.
- Midpoint: integrate from where signal crosses (background + threshold) / 2.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `_gen_data` | `(self)` |  |
| `update_visualization` | `(self)` |  |

### `IterativeThresholdVisualizer` *(extends `QWidget`)*

Interactive visualizer explaining the iterative background refinement
with Aitken delta-squared acceleration used in IsotopeTrack.

The algorithm is a fixed-point iteration:
T_{n+1} = f(mean(signal[signal < T_n]))

Aitken acceleration uses three consecutive iterates to extrapolate
directly to the fixed point:
T_accel = T0 - (T1 - T0)^2 / (T2 - 2*T1 + T0)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `_regenerate` | `(self)` | Generate new signal data and re-run iteration. |
| `_run_iteration` | `(self)` | Run the iterative threshold with and without Aitken, then plot. |

### `WatershedSplittingVisualizer` *(extends `QWidget`)*

Interactive visualizer for the 1D watershed peak splitting algorithm.

The algorithm detects merged (overlapping) particle events and splits them:
1. Find local maxima above the threshold in a contiguous region.
2. For each pair of adjacent maxima, find the valley minimum.
3. Check two criteria:
a) Valley depth ratio:  valley / min(peak_left, peak_right)  < valley_ratio
b) Prominence: both sub-peaks have prominence > threshold × min_prominence_factor
4. If both criteria are met, split at the valley minimum.

References
----------
Beucher, S. & Lantuéjoul, C. "Use of Watersheds in Contour Detection."
Int. Workshop on Image Processing, CCETT/IRISA, Rennes (1979).
Adapted to 1D peak splitting for spICP-ToF-MS by IsotopeTrack.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `_update` | `(self)` | Returns: |

### `HelpManager`

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `show_user_guide` | `(self)` | Show the user guide dialog. |
| `show_detection_methods` | `(self)` |  |
| `show_calibration_methods` | `(self)` |  |

### `DetectionMethodsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `apply_theme` | `(self)` |  |
| `showEvent` | `(self, event)` | Args: |
| `_tab_simulator` | `(self)` | Returns: |
| `_tab_integration` | `(self)` | Returns: |
| `_tab_iterative` | `(self)` | Returns: |
| `_tab_watershed` | `(self)` | Returns: |

### `CalibrationMethodsDialog` *(extends `QDialog`)*

Dialog displaying calibration method descriptions and equations.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Initialise the calibration methods dialog. |
| `apply_theme` | `(self)` |  |
| `showEvent` | `(self, event)` | Args: |
| `_img` | `(self, path, w = 600, h = 400)` | Load and scale an image resource into a QLabel. |
| `_scroll` | `(self, *widgets)` | Wrap an arbitrary number of widgets inside a scrollable area. |
| `_tab_overview` | `(self)` | Build the Overview tab content. |
| `_tab_ionic` | `(self)` | Build the Ionic Calibration tab with regression methods and FOM equations. |
| `_tab_transport` | `(self)` | Build the Transport Rate tab with all three method equations. |

### `AboutDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `apply_theme` | `(self)` |  |
| `showEvent` | `(self, event)` | Args: |

## Functions

### `get_resource_path`

```python
def get_resource_path(relative_path)
```


**Args:**

- `relative_path (Any): The relative path.`

**Returns:**

- `object: Result of the operation.`

### `_slider`

```python
def _slider(lo, hi, val)
```


**Args:**

- `lo (Any): The lo.`
- `hi (Any): The hi.`
- `val (Any): The val.`

**Returns:**

- `object: Result of the operation.`

### `_help_dialog_qss`

```python
def _help_dialog_qss() → str
```

Shared QSS for help/info dialogs — palette-aware.

**Returns:**

- `str: Result of the operation.`

### `_styled_label`

```python
def _styled_label(html, bg = None, border = None)
```

Rich-text section label — clean prose, no decorative box.

The old version wrapped each call in a colored, bordered panel. That
look was heavy and inconsistent (especially in dark mode). This
version ignores bg/border (kept for API compatibility with existing
callers) and returns a plain prose section that matches the User
Guide dialog.


**Args:**

- `html (str): HTML content for the label.`
- `bg: Ignored (kept for backwards compatibility).`
- `border: Ignored (kept for backwards compatibility).`


**Returns:**

- `QLabel: Rich-text label with no box.`

### `_equation_label`

```python
def _equation_label(html)
```

Equation block — subtle left accent bar, no full box.

Reads as an indented quote, matching the User Guide's clean prose
style instead of the old bordered cream panel.


**Args:**

- `html (str): HTML content containing the equation(s).`


**Returns:**

- `QLabel: Equation-styled label.`
