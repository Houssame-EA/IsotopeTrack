# `SIA_manager.py`

---

## Constants

| Name | Value |
|------|-------|
| `DEFAULT_SIGMA` | `0.55` |
| `POI2_LOW` | `1e-05` |
| `POI2_HIGH` | `0.001` |
| `QUANTILE_TARGET` | `0.9999` |
| `PER_MASS_MIN_PTS` | `10` |
| `PER_MASS_BINS` | `50` |
| `OUTLIER_SD_MULT` | `2.0` |
| `_QQ_POINT_COLOR` | `QColor(65, 105, 225, 180)` |
| `_QQ_LINE_COLOR` | `QColor(220, 50, 50)` |

## Classes

### `SIAWorker` *(extends `QObject`)*

Worker — processes SIA data in a background thread.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` | Initialise the SIA worker. |
| `process_sia_data` | `(self, data_path: str, file_type: str='nu')` | Entry point — dispatch to the correct instrument handler. |
| `stop_processing` | `(self)` | Request cancellation of the current processing run. |
| `_process_nu` | `(self, path: Path)` | Load and process a Nu Vitesse data folder. |
| `_process_tofwerk` | `(self, path: Path)` | Load and process a TOFWERK .h5 file. |
| `_build_result` | `(self, single_ion_dist: np.ndarray, data_path: str, run_info: dict, ma` | Build the full result dictionary from pre-computed inputs. |
| `_emit` | `(self, pct: int, msg: str)` | Emit progress and status signals together. |

### `SingleIonDistributionManager` *(extends `QObject`)*

Unified SIA Manager — Nu Vitesse + TOFWERK.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, main_window)` | Initialise the SIA manager. |
| `main_window` | `(self)` | Return the parent MainWindow, or None if it has been destroyed. |
| `_themed_msgbox` | `(self, kind: str, parent, title: str, text: str, buttons=None, default` | Show a QMessageBox styled to the active theme palette. |
| `_on_theme_changed` | `(self, _name: str)` | Restyle owned widgets and any live dialogs when the theme changes. |
| `_loaded_button_qss` | `() → str` | QSS for the upload button once a SIA has been loaded. |
| `_close_button_qss` | `() → str` | QSS for the Close buttons in SIA dialogs. |
| `_restyle_plot_widget` | `(pw)` | Re-apply plot background and axis colors from the active palette. |
| `_register_dialog` | `(self, dialog)` | Track a dialog so it gets restyled on theme change. |
| `create_sia_buttons` | `(self, parent_layout)` | Create and add the three SIA control buttons to a layout. |
| `upload_single_ion_distribution` | `(self)` | Prompt the user to choose an instrument type, then open the |
| `upload_overlay_distribution` | `(self)` | Load a second SIA dataset for overlay comparison. |
| `_start_sia_processing` | `(self, data_path: str, file_type: str='nu')` | Spawn a QThread, move a SIAWorker onto it, and start processing. |
| `_on_progress` | `(self, value: int)` | Forward a progress value to the main-window progress bar. |
| `_on_status` | `(self, text: str)` | Forward a status string to the main-window status label. |
| `_on_finished` | `(self, result: dict)` | Store results, update UI, and notify the user on successful processing. |
| `_on_error` | `(self, msg: str)` | Handle a processing error emitted by the worker. |
| `_on_thread_cleanup` | `(self)` | Disconnect worker signals and nullify thread/worker references after |
| `_reset_processing_state` | `(self)` | Restore the upload button and hide the progress bar. |
| `_update_ui_after_load` | `(self)` | Update sigma spinbox and button states after a successful SIA load. |
| `_apply_sia_to_all_samples` | `(self)` | Trigger a parameters-table refresh so all samples reflect the new SIA. |
| `_show_success_message` | `(self)` | Display a QMessageBox summarising the loaded SIA. |
| `show_single_ion_info` | `(self)` | Open the SIA information dialog with plot and optional per-mass |
| `_create_info_html` | `(self, info: dict) → str` | Build an HTML string for the information table in the dialog. |
| `_annot` | `(text: str) → str` | Wrap a plain-text string in the standard annotation HTML style |
| `_make_plot_widget` | `(left_label: str, bottom_label: str) → pg.PlotWidget` | Create a styled PlotWidget with shared axis and font settings. |
| `_create_sia_plot` | `(self, info: dict, mass_key) → pg.PlotWidget` | Create a new SIA distribution plot widget and populate it. |
| `_update_sia_plot` | `(self, pw: pg.PlotWidget, info: dict, mass_key)` | Redraw a SIA distribution plot in place without recreating the widget. |
| `_create_qq_plot` | `(self, info: dict, mass_key) → pg.PlotWidget` | Create a new lognormal Q-Q plot widget and populate it. |
| `_update_qq_plot` | `(self, pw: pg.PlotWidget, info: dict, mass_key)` | Draw a Q-Q plot: theoretical lognormal quantiles on x, |
| `_show_qq_dialog` | `(self, info: dict, parent: QWidget)` | Open a separate dialog showing a lognormal Q-Q plot for the |
| `_calc_quantile` | `(mean_signal: float, sigma: float, avg_sia: float, sig_vals: np.ndarra` | Compute the ``QUANTILE_TARGET`` quantile in normalised signal units. |
| `_create_sigma_comparison_plot` | `(self, info: dict) → pg.PlotWidget` | Build the sigma-vs-mass scatter plot with mean and ±1 SD / ±2 SD |
| `_update_sigma_comparison_plot` | `(self, pw: pg.PlotWidget, exclude_outliers: bool=False)` | Redraw the sigma comparison scatter plot in place. |
| `_on_sigma_scatter_clicked` | `(self, points)` | Handle a click on a point in the sigma scatter plot. |
| `_export_per_mass_csv` | `(self, parent: QWidget)` | Export per-mass sigma data to a CSV file via a save-file dialog. |
| `_export_plot` | `(self, pw: pg.PlotWidget, parent: QWidget)` | Export a PlotWidget to SVG or PNG via a save-file dialog. |
| `_assign_per_mass_sigma` | `(self)` | Assign each element's sigma from its closest matching per-mass SIA |
| `_clear_overlay` | `(self, dialog: QDialog)` | Clear the overlay SIA data and refresh the current dialog view. |
| `clear_single_ion_distribution` | `(self)` | Prompt the user to confirm, then clear all SIA data and reset sigma. |
| `_clear_sia_data` | `(self)` | Reset all stored SIA data (primary and overlay) and restore sigma to |
| `_update_ui_after_clear` | `(self)` | Disable info/clear buttons and reset the upload button style after clear. |
| `is_sia_loaded` | `(self) → bool` | Check whether a single-ion distribution is currently loaded. |
| `get_sia_info` | `(self) → dict` | Return a copy of the current SIA info dictionary. |
| `get_calculated_sigma` | `(self) → float` | Return the sigma value derived from the loaded SIA. |
| `get_per_mass_sigma` | `(self, target_mass: float, tolerance: float=0.5) → float` | Look up the per-mass sigma for a given target mass. |
| `is_overlay_loaded` | `(self) → bool` | Check whether overlay SIA data is loaded. |
| `stop_processing` | `(self)` | Request the background worker to stop and reset the UI. |
| `cleanup` | `(self)` | Gracefully stop the worker thread and release all references. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `lognormal_pdf_scipy` | `(x: np.ndarray, mu: float, sigma: float) → np.ndarray` | Lognormal probability density function via scipy. |
| `_compute_poi2` | `(signals: np.ndarray) → np.ndarray` | Compute the poi2 filter array from a 2-D signal matrix. |
| `_weighted_stats` | `(values: np.ndarray, weights: np.ndarray) → tuple` | Compute weighted mean, weighted standard deviation, and lognormal sigma |
| `_build_histogram` | `(data: np.ndarray, n_bins: int) → tuple` | Build a histogram from 1-D positive data. |
