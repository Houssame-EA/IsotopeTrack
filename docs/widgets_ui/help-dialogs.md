# `help_dialogs.py`

---

## Classes

### `SPICPToFMSSimulator`

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

| Method | Signature | Description |
|--------|-----------|-------------|
| `_temporal_profile` | `(self, dwell_us)` | Compute the lognormal temporal probability vector for distributing |
| `generate` | `(self, acq_time_s=60.0, dwell_us=76.71, lambda_bg=1.1, n_particles=300` |  |

### `InteractiveEquationVisualizer` *(extends `QWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Initialise the simulator visualiser with controls, trace plot, and histogram. |
| `_build_ui` | `(self)` | Build the two-column layout: controls scroll area on the left, plots on the right. |
| `_grp_acquisition` | `(self)` | Build the Acquisition Parameters group box with dwell/time spinboxes and sliders. |
| `_grp_background` | `(self)` | Build the Background group box with the lambda_bg spinbox and slider. |
| `_grp_particles` | `(self)` | Build the Particles group box with particle count and size-distribution controls. |
| `_grp_detection` | `(self)` | Build the Detection Method group box with method selector, alpha, and sigma controls. |
| `_sl_to_spin` | `(self, spin, val)` | Slider moved -> update spinbox (silently) then schedule update. |
| `_spin_to_sl` | `(sl, val)` | Spinbox changed -> update slider (silently). Schedule already fired. |
| `_alpha_moved` | `(self, v)` | Convert the log-scale slider position to an alpha value and sync the spinbox. |
| `_schedule` | `(self)` | Restart the debounce timer so the simulation runs after a short idle period. |
| `_run_simulation` | `(self)` | Generate a new simulated signal, compute the threshold, and refresh all plots. |
| `_update_plots` | `(self)` | Redraw both the signal trace and the intensity histogram. |
| `_draw_trace` | `(self)` | Render the time-domain signal trace with threshold, LOD, and detected events. |
| `_draw_histogram` | `(self)` | Histogram of DETECTED events only (signal > threshold). |
| `_update_stats` | `(self)` | Compute and display detection statistics (TP, FP, FN, detection rate). |
| `_calc_threshold` | `(self, method, bg, alpha, manual, sigma)` | Compute the detection threshold for the selected method. |

### `PeakIntegrationVisualizer` *(extends `QWidget`)*

Interactive visualizer showing three peak integration methods:
  - Background: integrate from where signal crosses background level.
  - Threshold: integrate only the region above the detection threshold.
  - Midpoint: integrate from where signal crosses (background + threshold) / 2.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Initialise the peak integration visualiser with method controls and a plot. |
| `_gen_data` | `(self)` | Generate a fixed synthetic Gaussian peak with Poisson-like noise for demonstration. |
| `update_visualization` | `(self)` | Recompute integration bounds for the current method and redraw the plot. |

### `IterativeThresholdVisualizer` *(extends `QWidget`)*

The algorithm is a fixed-point iteration:
    T_{n+1} = f(mean(signal[signal < T_n]))

Aitken acceleration uses three consecutive iterates to extrapolate
directly to the fixed point:
    T_accel = T0 - (T1 - T0)^2 / (T2 - 2*T1 + T0)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Initialise the iterative threshold visualiser with parameter controls and convergence plots. |
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
| `__init__` | `(self, parent=None)` | Initialise the watershed splitting visualiser with peak and criteria controls. |
| `_update` | `(self)` | Regenerate the merged peak signal and redraw both before/after watershed plots. |

### `HelpManager`

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Initialise the HelpManager and store dialog references. |
| `show_user_guide` | `(self)` | Show the user guide dialog. |
| `show_detection_methods` | `(self)` | Show the Detection Methods dialog, creating it on first call. |
| `show_calibration_methods` | `(self)` | Show the Calibration Methods dialog, creating it on first call. |

### `_LUTHeatmapWidget` *(extends `QWidget`)*

Colour-coded threshold grid loaded directly from cpln_quantiles.npz.

Improvements over the original:
- Fully theme-aware (dark-mode safe) — no hardcoded light colours.
- Heatmap grid is horizontally centred inside a scroll area.
- Row *and* column of the selected cell are highlighted with a subtle
  accent ring so the user can trace λ and σ at a glance.
- The info bar at the top of the heatmap sub-tab is now inside this
  widget so it re-reads the theme when the dialog is re-shown.
- A compact "selected cell" details strip lives below the grid.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Build the interactive heatmap grid with alpha dropdown, centred grid, and details strip. |
| `_theme_colours` | `(self)` | Return current palette convenience shorthand. |
| `_draw` | `(self)` | Rebuild the full heatmap grid for the currently selected alpha level. |
| `_make_click_handler` | `(self, cell)` | Return a mousePressEvent function bound to *cell*. |
| `_select_cell` | `(self, cell)` | Handle a cell click: highlight its row/column and update the details strip. |
| `_reset_cell_style` | `(self, cell)` | Restore a cell to its default (unselected) stylesheet. |

### `_LUTProfileWidget` *(extends `QWidget`)*

Threshold vs λ loaded directly from cpln_quantiles.npz.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Build the λ-profile plot from cpln_quantiles.npz at a fixed sigma of 0.47. |

### `DetectionMethodsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Initialise the Detection Methods dialog with all five sub-tabs. |
| `apply_theme` | `(self)` | Reapply the palette-aware QSS whenever the theme changes. |
| `showEvent` | `(self, event)` | Reapply the theme each time the dialog becomes visible. |
| `_tab_simulator` | `(self)` | Build the Signal Simulator sub-tab containing the interactive visualiser. |
| `_tab_integration` | `(self)` | Build the Peak Integration sub-tab with method description and visualiser. |
| `_tab_iterative` | `(self)` | Build the Iterative Threshold sub-tab containing the convergence visualiser. |
| `_tab_watershed` | `(self)` | Build the Watershed Splitting sub-tab containing the splitting visualiser. |
| `_tab_lut` | `(self)` | CPLN lookup table — Heatmap and λ Profile sub-tabs. |
| `_lut_sub_heatmap` | `(self)` | Build the Heatmap sub-tab with the interactive threshold grid and references. |
| `_lut_sub_profile` | `(self)` | Build the λ Profile sub-tab with the threshold-vs-lambda line chart. |

### `CalibrationMethodsDialog` *(extends `QDialog`)*

Dialog displaying calibration method descriptions and equations.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Initialise the Calibration Methods dialog with Overview, Ionic, and Transport tabs. |
| `apply_theme` | `(self)` | Reapply the palette-aware QSS whenever the theme changes. |
| `showEvent` | `(self, event)` | Reapply the theme each time the dialog becomes visible. |
| `_img` | `(self, path, w=600, h=400)` | Load and scale an image resource into a QLabel. |
| `_scroll` | `(self, *widgets)` | Wrap an arbitrary number of widgets inside a scrollable area. |
| `_tab_ionic` | `(self)` | Build the Sensitivity tab: intro, figure, and the LaTeX equations |
| `_topic_tab` | `(self, topic_key)` | Build a scrollable tab from one equations-reference topic, with |
| `_equations_widget` | `(self, topic_key)` | Safely build the equations widget for one topic. |
| `_tab_transport` | `(self)` | Build the Transport Rate tab with all three method equations. |

### `AboutDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Initialise the About dialog with version info and app icon. |
| `apply_theme` | `(self)` | Reapply the palette-aware QSS whenever the theme changes. |
| `showEvent` | `(self, event)` | Reapply the theme each time the dialog becomes visible. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_resource_path` | `(relative_path)` | Resolve a resource path relative to the app bundle or source root. |
| `_slider` | `(lo, hi, val)` | Create a horizontal QSlider with the given range and initial value. |
| `_help_dialog_qss` | `() → str` | Shared QSS for help/info dialogs — palette-aware. |
| `_lut_load` | `()` | Load cpln_quantiles.npz from the app resource folder. |
| `_lut_color_for` | `(v, mn, mx)` | Map a value to a blue-white-red colour string + luminance. |
| `_lut_info` | `(html, bg='#eaf4fb', border='#2980b9')` | Create a styled info QLabel with a left accent border, theme-aware text colour. |
| `_lut_eq` | `(html)` | Create a monospaced equation QLabel using theme bg/border colours. |
| `_lut_ref` | `(text)` | Create a small muted reference citation QLabel. |
| `_lut_section` | `(title)` | Create a section heading QLabel styled with the current theme text colour. |
| `_lut_hline` | `()` | Create a horizontal divider QFrame using the theme border colour. |
| `_lut_scroll` | `(widgets)` | Wrap a list of widgets in a vertical scroll area suitable for LUT sub-tabs. |
| `_styled_label` | `(html, bg=None, border=None)` | Rich-text section label — clean prose, no decorative box. |
| `_equation_label` | `(html)` | Equation block — subtle left accent bar, no full box. |
