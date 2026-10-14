import weakref
import numpy as np
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QFileDialog, QMessageBox,
                               QRadioButton, QButtonGroup, QComboBox,
                               QCheckBox, QWidget, QFrame, QTableWidget,
                               QTableWidgetItem, QHeaderView, QAbstractItemView)
from PySide6.QtCore import Qt, QThread, QObject, Signal, Slot
from PySide6.QtGui import QFont, QPen, QColor
import pyqtgraph as pg
import qtawesome as qta
from scipy import stats
from scipy.special import gammainc
import traceback

import loading.vitesse_loading
import loading.tofwerk_loading
from loading import sia_stats
from processing.peak_detection import erfinv
import csv

from tools.theme import theme, dialog_qss
import logging
_itk_log = logging.getLogger("IsotopeTrack.loading.SIA_manager")


# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_SIGMA    = 0.55
POI2_LOW         = 1e-5
POI2_HIGH        = 1e-3
QUANTILE_TARGET  = 0.9999
PER_MASS_MIN_PTS = 10
PER_MASS_BINS    = 50      

_QQ_LINE_COLOR   = QColor(220, 50, 50)        


# ─── Helpers ──────────────────────────────────────────────────────────────────

def lognormal_pdf_scipy(x: np.ndarray, mu: float, sigma: float) -> np.ndarray:
    """
    Lognormal probability density function via scipy.

    Args:
        x     (np.ndarray): Input values.
        mu    (float):      Log-scale mean parameter.
        sigma (float):      Log-scale standard deviation parameter.

    Returns:
        np.ndarray: PDF values evaluated at x.
    """
    return stats.lognorm.pdf(x, s=sigma, scale=np.exp(mu))


def _compute_poi2(signals: np.ndarray) -> np.ndarray:
    """
    Compute the poi2 filter array from a 2-D signal matrix.
    Called exactly once per load and passed downstream — never recomputed.

    Args:
        signals (np.ndarray): Signal array of shape (n_acquisitions, n_masses).

    Returns:
        np.ndarray: poi2 values of shape (n_masses,).
    """
    pzeros = np.count_nonzero(signals, axis=0) / signals.shape[0]
    return gammainc(3, pzeros)


def _weighted_stats(values: np.ndarray, weights: np.ndarray) -> tuple:
    """
    Compute weighted mean, weighted standard deviation, and lognormal sigma
    from histogram bin centres and counts.

    Args:
        values  (np.ndarray): Bin centre values.
        weights (np.ndarray): Bin counts (need not be normalised).

    Returns:
        tuple:
            mean  (float): Weighted mean.
            std   (float): Weighted standard deviation.
            sigma (float): Lognormal sigma derived from the coefficient of variation.
    """
    w     = weights / weights.sum()
    mean  = np.dot(w, values)
    var   = np.dot(w, (values - mean) ** 2)
    std   = np.sqrt(var)
    cv    = std / mean if mean > 0 else 0.0
    sigma = np.sqrt(np.log(1.0 + cv ** 2)) if cv > 0 else DEFAULT_SIGMA
    return mean, std, sigma


def _build_histogram(data: np.ndarray, n_bins: int) -> tuple:
    """
    Build a histogram from 1-D positive data.

    Args:
        data   (np.ndarray): 1-D array of positive values.
        n_bins (int):        Number of bins.

    Returns:
        tuple:
            centres (np.ndarray): Bin centre values of shape (n_bins,).
            counts  (np.ndarray): Bin counts of shape (n_bins,).
    """
    counts, edges = np.histogram(data, bins=n_bins)
    centres       = 0.5 * (edges[:-1] + edges[1:])
    return centres, counts


# ─── Worker ───────────────────────────────────────────────────────────────────

class SIAWorker(QObject):
    """Worker — processes SIA data in a background thread."""

    progress      = Signal(int)
    status_update = Signal(str)
    finished      = Signal(dict)
    error         = Signal(str)

    def __init__(self):
        """Initialise the SIA worker.

        Args:
            None
        """
        super().__init__()
        self._should_stop = False

    # ── public slots ──────────────────────────────────────────────────────────

    @Slot(str, str)
    def process_sia_data(self, data_path: str, file_type: str = "nu"):
        """Entry point — dispatch to the correct instrument handler.

        Args:
            data_path (str): Path to a Nu Vitesse folder or TOFWERK .h5 file.
            file_type (str): Instrument type — ``'nu'`` or ``'tofwerk'``.
        """
        try:
            self._should_stop = False
            path = Path(data_path)

            if file_type == "nu":
                self._process_nu(path)
            elif file_type == "tofwerk":
                self._process_tofwerk(path)
            else:
                self.error.emit(f"Unknown file type: {file_type}")

        except Exception as e:
            _itk_log.exception("Handled exception in process_sia_data")
            self.error.emit(f"Error processing single-ion distribution: {e}")
            _itk_log.error(f"SIAWorker error:\n{traceback.format_exc()}")

    @Slot()
    def stop_processing(self):
        """Request cancellation of the current processing run.

        Args:
            None
        """
        self._should_stop = True

    # ── Nu Vitesse ────────────────────────────────────────────────────────────

    def _process_nu(self, path: Path):
        """Load and process a Nu Vitesse data folder.

        Args:
            path (Path): Path to the Nu Vitesse folder containing ``run.info``.
        """
        if not (path / "run.info").exists():
            self.error.emit(
                "Selected folder does not contain run.info file.\n"
                "Please select a Nu Vitesse data folder."
            )
            return

        self._emit(10, "Loading Nu Vitesse data...")
        if self._should_stop: return

        self._emit(20, "Reading Nu directory...")
        masses, signals, run_info = loading.vitesse_loading.read_nu_directory(
            path=str(path), max_integ_files=None, autoblank=True, raw=True
        )
        if self._should_stop: return

        self._emit(50, "Calculating single-ion distribution...")
        single_ion_dist = loading.vitesse_loading.single_ion_distribution(
            counts=signals, bins="auto"
        )
        if self._should_stop: return

        self._emit(70, "Processing distribution statistics...")
        run_info['InstrumentType'] = 'Nu Vitesse'

        signals_2d = np.atleast_2d(signals) if signals.ndim == 1 else signals
        poi2       = _compute_poi2(signals_2d)

        result = self._build_result(single_ion_dist, str(path), run_info,
                                    masses, signals_2d, poi2)
        if self._should_stop: return

        self.progress.emit(100)
        self.finished.emit(result)

    # ── TOFWERK ───────────────────────────────────────────────────────────────

    def _process_tofwerk(self, path: Path):
        """Load and process a TOFWERK .h5 file.

        Args:
            path (Path): Path to the TOFWERK HDF5 file.
        """
        if not path.exists():
            self.error.emit("Selected file does not exist.")
            return
        if not loading.tofwerk_loading.is_tofwerk_file(path):
            self.error.emit("Selected file is not a valid TOFWERK .h5 file.")
            return

        self._emit(10, "Loading TOFWERK data...")
        if self._should_stop: return

        self._emit(20, "Reading TOFWERK file...")
        try:
            import h5py
            with h5py.File(path, "r") as h5:
                if "PeakData" in h5["PeakData"]:
                    data = h5["PeakData"]["PeakData"][...]
                else:
                    data = loading.tofwerk_loading.integrate_tof_data(h5, idx=None)

                factor            = loading.tofwerk_loading.factor_extraction_to_acquisition(h5)
                data             *= factor
                single_ion_signal = float(h5["FullSpectra"].attrs["Single Ion Signal"][0])
                masses            = h5["PeakData"]["PeakTable"]["mass"].astype(np.float32)
                signals           = data * single_ion_signal

                run_info = {
                    "SampleName"          : path.stem,
                    "AnalysisDateTime"    : "Unknown",
                    "AverageSingleIonArea": single_ion_signal,
                    "InstrumentType"      : "TOFWERK",
                    "TotalAcquisitions"   : data.shape[0],
                }
        except Exception as e:
            _itk_log.exception("Handled exception in _process_tofwerk")
            self.error.emit(f"Error reading TOFWERK file: {e}")
            return

        if self._should_stop: return

        self._emit(50, "Calculating single-ion distribution...")
        poi2       = _compute_poi2(signals)
        valid_mask = (poi2 > POI2_LOW) & (poi2 < POI2_HIGH)
        positive   = signals[:, valid_mask][signals[:, valid_mask] > 0]

        counts, edges   = np.histogram(positive, bins="auto")
        centres         = 0.5 * (edges[:-1] + edges[1:])
        single_ion_dist = np.stack((centres, counts), axis=1)

        if self._should_stop: return

        self._emit(70, "Processing distribution statistics...")
        result = self._build_result(single_ion_dist, str(path), run_info,
                                    masses, signals, poi2)
        if self._should_stop: return

        self.progress.emit(100)
        self.finished.emit(result)

    # ── shared result builder ─────────────────────────────────────────────────

    def _build_result(
        self,
        single_ion_dist : np.ndarray,
        data_path       : str,
        run_info        : dict,
        masses          : np.ndarray,
        signals         : np.ndarray,
        poi2            : np.ndarray,
    ) -> dict:
        """
        Build the full result dictionary from pre-computed inputs.
        poi2 is accepted as a parameter — never recomputed here.

        Args:
            single_ion_dist (np.ndarray): Overall distribution array of shape (N, 2)
                                          with columns [bin_centre, count].
            data_path       (str):        Path to the source file or folder.
            run_info        (dict):       Instrument metadata dict.
            masses          (np.ndarray): Mass array of shape (n_masses,).
            signals         (np.ndarray): Signal matrix of shape (n_acq, n_masses).
            poi2            (np.ndarray): Pre-computed poi2 array of shape (n_masses,).

        Returns:
            dict: Result dictionary with keys:
                - ``'single_ion_distribution_data'`` (np.ndarray)
                - ``'single_ion_source_folder'``      (str)
                - ``'per_mass_distributions'``        (dict)
                - ``'single_ion_info'``               (dict)
        """
        avg_sia = float(run_info.get("AverageSingleIonArea", 1.0))
        if avg_sia <= 0 or not np.isfinite(avg_sia):
            avg_sia = 1.0

        instrument_type = run_info.get("InstrumentType", "Unknown")

        sig_vals                      = single_ion_dist[:, 0]
        raw_w                         = single_ion_dist[:, 1]
        mean_sig, std_sig, calc_sigma = _weighted_stats(sig_vals, raw_w)
        weights                       = raw_w / raw_w.sum()

        masses = np.atleast_1d(masses).flatten()
        poi2   = np.atleast_1d(poi2).flatten()
        n      = min(len(masses), len(poi2), signals.shape[1] if signals.ndim > 1 else 1)
        masses = masses[:n]
        poi2   = poi2[:n]

        valid_indices = np.where((poi2 > POI2_LOW) & (poi2 < POI2_HIGH))[0]
        per_mass      = {}

        for i in valid_indices:
            if self._should_stop:
                break
            try:
                col = signals[:, i] if signals.ndim > 1 else signals
                pos = col[col > 0]
                if len(pos) < PER_MASS_MIN_PTS:
                    continue

                centres, counts = _build_histogram(pos, PER_MASS_BINS)
                if counts.sum() == 0:
                    continue

                m_mean, m_std, m_sigma = _weighted_stats(centres, counts)

                mass_key = f"{masses[i]:.4f}"

                per_mass[mass_key] = {
                    'distribution': np.stack((centres, counts), axis=1),
                    'mass'        : float(masses[i]),
                    'mean_signal' : m_mean,
                    'std_signal'  : m_std,
                    'sigma'       : m_sigma,
                    'num_points'  : int(len(pos)),
                }
            except (ValueError, ArithmeticError, IndexError, KeyError) as e:
                _itk_log.exception("Handled exception in _build_result")
                _itk_log.error(f"Warning: failed to process mass {masses[i]}: {e}")

        sample_name = run_info.get("SampleName", Path(data_path).name)

        return {
            'single_ion_distribution_data': single_ion_dist,
            'single_ion_source_folder'    : data_path,
            'per_mass_distributions'      : per_mass,
            'single_ion_info'             : {
                'source_folder'          : data_path,
                'sample_name'            : sample_name,
                'instrument_type'        : instrument_type,
                'total_counts'           : float(np.sum(signals)),
                'num_acquisitions'       : signals.shape[0],
                'num_masses'             : len(masses),
                'mass_range'             : (float(masses.min()), float(masses.max())),
                'distribution_points'    : len(single_ion_dist),
                'mean_signal'            : mean_sig,
                'std_signal'             : std_sig,
                'calculated_sigma'       : calc_sigma,
                'analysis_datetime'      : run_info.get("AnalysisDateTime", "Unknown"),
                'signal_values'          : sig_vals.copy(),
                'weights'                : weights.copy(),
                'average_single_ion_area': avg_sia,
                'num_valid_masses'       : len(per_mass),
            },
        }

    # ── private helper ────────────────────────────────────────────────────────

    def _emit(self, pct: int, msg: str):
        """Emit progress and status signals together.

        Args:
            pct (int): Progress percentage (0–100).
            msg (str): Status message string.
        """
        self.progress.emit(pct)
        self.status_update.emit(msg)


# ─── Manager ──────────────────────────────────────────────────────────────────

class SingleIonDistributionManager(QObject):
    """Unified SIA Manager — Nu Vitesse + TOFWERK."""

    def __init__(self, main_window):
        """Initialise the SIA manager.

        Args:
            main_window (object): Reference to the application main window.
        """
        super().__init__(main_window)

        self._main_window_ref = weakref.ref(main_window)

        self.single_ion_distribution_data = None
        self.single_ion_source_folder     = None
        self.single_ion_info              = {}
        self.per_mass_distributions       = {}

        self._overlay_info              = None
        self._overlay_per_mass          = {}
        self._overlay_distribution_data = None

        self.upload_sid_button = None
        self.info_sid_button   = None
        self.clear_sid_button  = None

        self.sia_thread     = None
        self.sia_worker     = None
        self._is_processing = False

        self._loading_overlay = False

        self._exclude_outliers = False
        self._effective_sigma  = None
        self._sigma_source     = "overall"

        self._current_qq_mass_key = None

        self._live_dialogs = []

        self._isotope_index = None
        self._history       = None
        self.sigma_source_label = None

        theme.themeChanged.connect(self._on_theme_changed)

    # ── weak-reference property ───────────────────────────────────────────────

    @property
    def main_window(self):
        """Return the parent MainWindow, or None if it has been destroyed."""
        return self._main_window_ref()

    # ── themed message box helper ─────────────────────────────────────────────

    def _themed_msgbox(self, kind: str, parent, title: str, text: str,
                       buttons=None, default_button=None):
        """Show a QMessageBox styled to the active theme palette.
        Args:
            kind (str): The kind.
            parent (Any): Parent widget or object.
            title (str): Window or dialog title.
            text (str): Text string.
            buttons (Any): The buttons.
            default_button (Any): The default button.
        """
        box = QMessageBox(parent)
        box.setWindowTitle(title)
        box.setText(text)
        icon_map = {
            'information': QMessageBox.Information,
            'warning'    : QMessageBox.Warning,
            'critical'   : QMessageBox.Critical,
            'question'   : QMessageBox.Question,
        }
        box.setIcon(icon_map.get(kind, QMessageBox.NoIcon))
        box.setStyleSheet(dialog_qss(theme.palette))
        if buttons is not None:
            box.setStandardButtons(buttons)
        if default_button is not None:
            box.setDefaultButton(default_button)
        return box.exec()

    # ── theme helpers ─────────────────────────────────────────────────────────

    def _on_theme_changed(self, _name: str):
        """Restyle owned widgets and any live dialogs when the theme changes."""
        if self.upload_sid_button is not None:
            self._style_upload_button(self.is_sia_loaded())
        self._refresh_source_label()

        alive = []
        for dlg in self._live_dialogs:
            try:
                dlg.setStyleSheet(dialog_qss(theme.palette))
                for card in dlg.findChildren(QFrame):
                    if card.property("_sia_info_card"):
                        card.setStyleSheet(self._info_card_qss())
                for lbl in dlg.findChildren(QLabel):
                    if lbl.property("_sia_info_html"):
                        info = lbl.property("_sia_info_data")
                        if info is not None:
                            lbl.setText(self._create_info_html(info))
                for pw in dlg.findChildren(pg.PlotWidget):
                    self._restyle_plot_widget(pw)
                sigma_pw = getattr(self, '_plot_sigma', None)
                if sigma_pw is not None and sigma_pw.window() is dlg and sigma_pw.isVisible():
                    self._update_sigma_comparison_plot(
                        sigma_pw, exclude_outliers=getattr(self, '_exclude_outliers', False))
                redraw = getattr(dlg, '_sia_redraw', None)
                if callable(redraw):
                    redraw()
                alive.append(dlg)
            except RuntimeError:
                _itk_log.exception("Handled exception in _on_theme_changed")
                continue
        self._live_dialogs = alive

    @staticmethod
    def _loaded_button_qss() -> str:
        """QSS for the upload button once a SIA has been loaded."""
        p = theme.palette
        ok = QColor(p.success)
        soft = f"rgba({ok.red()}, {ok.green()}, {ok.blue()}, 40)"
        strong = f"rgba({ok.red()}, {ok.green()}, {ok.blue()}, 70)"
        return f"""
            QPushButton {{
                background-color: {soft};
                border: 1px solid {p.success};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {strong};
            }}
        """

    def _style_upload_button(self, loaded):
        """Show the upload button in its loaded or empty state.

        Args:
            loaded (bool): True when a SIA is loaded.
        """
        p = theme.palette
        if loaded:
            self.upload_sid_button.setStyleSheet(self._loaded_button_qss())
            self.upload_sid_button.setIcon(qta.icon('fa6s.folder-open', color=p.success))
        else:
            self.upload_sid_button.setStyleSheet("")
            self.upload_sid_button.setIcon(qta.icon('fa6s.folder-open', color=p.accent))

    @staticmethod
    def _point_color(alpha=255):
        """Scatter point colour that stays readable on the current plot background.

        Args:
            alpha (int): Opacity from 0 to 255.

        Returns:
            QColor: Light blue in dark mode, deeper blue in light mode.
        """
        col = QColor('#64b5f6') if theme.palette.name == "dark" else QColor('#1e63c6')
        col.setAlpha(alpha)
        return col

    @staticmethod
    def _info_card_qss() -> str:
        """QSS for the information card at the top of the SIA dialog."""
        p = theme.palette
        return f"""
            QFrame#siaInfoCard {{
                background-color: {p.bg_secondary};
                border: 1px solid {p.border_subtle};
                border-radius: 8px;
            }}
            QFrame#siaInfoCard QLabel {{
                background: transparent;
                border: none;
            }}
        """

    @staticmethod
    def _restyle_plot_widget(pw):
        """Re-apply plot background and axis colors from the active palette."""
        p = theme.palette
        try:
            pw.setBackground(p.plot_bg)
            pi = pw.getPlotItem()
            axis_pen   = QPen(QColor(p.plot_fg), 2)
            text_color = QColor(p.plot_fg)
            for name in ('left', 'bottom', 'top', 'right'):
                ax = pi.getAxis(name)
                ax.setPen(axis_pen)
                ax.setTextPen(text_color)
            left_lbl   = pi.getAxis('left').labelText or ''
            bottom_lbl = pi.getAxis('bottom').labelText or ''
            pw.setLabel('left',   left_lbl,   color=p.plot_fg,
                        font='bold 20pt Times New Roman')
            pw.setLabel('bottom', bottom_lbl, color=p.plot_fg,
                        font='bold 20pt Times New Roman')
        except Exception:
            _itk_log.exception("Handled exception in _restyle_plot_widget")

    def _register_dialog(self, dialog):
        """Track a dialog so it gets restyled on theme change."""
        self._live_dialogs.append(dialog)
        dialog.destroyed.connect(
            lambda _=None, d=dialog: self._live_dialogs.remove(d)
            if d in self._live_dialogs else None
        )

    # ── UI buttons ────────────────────────────────────────────────────────────

    def create_sia_buttons(self, parent_layout):
        """Create and add the three SIA control buttons to a layout.

        Args:
            parent_layout (QLayout): Layout to which the buttons are added.
        """
        self.upload_sid_button = QPushButton()
        self.upload_sid_button.setIcon(qta.icon('fa6s.folder-open', color="#2196F3"))
        self.upload_sid_button.setToolTip("Upload single-ion distribution from Nu Vitesse or TOFWERK")
        self.upload_sid_button.setFixedSize(32, 32)
        self.upload_sid_button.clicked.connect(self.upload_single_ion_distribution)

        self.info_sid_button = QPushButton()
        self.info_sid_button.setIcon(qta.icon('fa6s.circle-info', color="#4CAF50"))
        self.info_sid_button.setToolTip("Show single-ion distribution information")
        self.info_sid_button.setFixedSize(32, 32)
        self.info_sid_button.setEnabled(False)
        self.info_sid_button.clicked.connect(self.show_single_ion_info)

        self.clear_sid_button = QPushButton()
        self.clear_sid_button.setIcon(qta.icon('fa6s.trash', color="#f44336"))
        self.clear_sid_button.setToolTip("Clear loaded single-ion distribution")
        self.clear_sid_button.setFixedSize(32, 32)
        self.clear_sid_button.setEnabled(False)
        self.clear_sid_button.clicked.connect(self.clear_single_ion_distribution)

        for btn in (self.upload_sid_button, self.info_sid_button, self.clear_sid_button):
            parent_layout.addWidget(btn)

        self.sigma_source_label = QLabel("")
        self.sigma_source_label.setObjectName("sigmaSourceLabel")
        self.sigma_source_label.setVisible(False)
        parent_layout.addWidget(self.sigma_source_label)
        sb = getattr(self.main_window, 'sigma_spinbox', None)
        if sb is not None:
            sb.valueChanged.connect(lambda _v: self._refresh_source_label())

    # ── sigma in use ──────────────────────────────────────────────────────────

    def get_effective_sigma(self) -> float:
        """Return the sigma the application should use from the loaded SIA.

        This is the overall SIA sigma, or the weighted mean of the per-mass
        sigma values when outliers are excluded.

        Returns:
            float: Sigma in use, or ``DEFAULT_SIGMA`` without a SIA.
        """
        if not self.is_sia_loaded():
            return DEFAULT_SIGMA
        sigma, source = sia_stats.effective_sigma(
            self.single_ion_info.get('calculated_sigma', DEFAULT_SIGMA),
            self.per_mass_distributions, self._exclude_outliers)
        self._effective_sigma = sigma
        self._sigma_source = source
        return sigma

    def _sigma_mode_is_per_isotope(self) -> bool:
        """Whether the main window is in per-isotope sigma mode."""
        return getattr(self.main_window, '_sigma_mode', 'global') == 'per_isotope'

    def _apply_sigma(self, value: float):
        """Put a sigma into the Sigma box and push it to every sample.

        The box is set without signals and the main window's
        ``on_sigma_changed`` is then called once, so samples are updated
        even when the value shown does not change.

        Args:
            value (float): Sigma to apply.
        """
        mw = self.main_window
        sb = getattr(mw, 'sigma_spinbox', None)
        if sb is None:
            return
        sb.blockSignals(True)
        sb.setValue(float(value))
        sb.blockSignals(False)
        if hasattr(mw, 'on_sigma_changed') and hasattr(mw, 'parameters_table'):
            mw.on_sigma_changed(sb.value())
        if self._sigma_mode_is_per_isotope() and self.per_mass_distributions:
            self._assign_per_mass_sigma(quiet=True)
        self._refresh_source_label()

    def set_exclude_outliers(self, exclude: bool):
        """Exclude or include per-mass outliers and update the sigma in use.

        Args:
            exclude (bool): True to exclude outliers.
        """
        self._exclude_outliers = bool(exclude)
        if self.is_sia_loaded():
            self._apply_sigma(self.get_effective_sigma())

    def _source_label_qss(self) -> str:
        """QSS for the small label that says where sigma comes from."""
        p = theme.palette
        return (f"QLabel#sigmaSourceLabel {{ color: {p.text_muted}; "
                f"background: transparent; font-size: 11px; }}")

    def _source_text(self) -> str:
        """Short text describing where the sigma in the Sigma box comes from."""
        if not self.is_sia_loaded():
            return ""
        info = self.single_ion_info
        sigma = self.get_effective_sigma()
        date = sia_stats.parse_datetime(info.get('analysis_datetime'))
        parts = [f"SIA {info.get('sample_name', '')}"]
        if date is not None:
            parts.append(date.strftime('%Y-%m-%d'))
        if self._sigma_source == 'per_mass_mean':
            summary = sia_stats.summarize_per_mass(self.per_mass_distributions, True)
            n_out = summary['n_outliers'] if summary else 0
            parts.append(f"per-mass mean, {n_out} outlier{'s' if n_out != 1 else ''} excluded")
        sb = getattr(self.main_window, 'sigma_spinbox', None)
        if sb is not None and abs(sb.value() - round(sigma, sb.decimals())) > 10 ** -sb.decimals() / 2:
            return f"σ edited by hand (SIA σ = {sigma:.3f})"
        return " · ".join(parts)

    def _refresh_source_label(self):
        """Update the label next to the SIA buttons."""
        lbl = self.sigma_source_label
        if lbl is None:
            return
        try:
            text = self._source_text()
            lbl.setStyleSheet(self._source_label_qss())
            lbl.setText(text)
            lbl.setToolTip("Where the σ in the Sigma box comes from" if text else "")
            lbl.setVisible(bool(text))
        except RuntimeError:
            self.sigma_source_label = None

    # ── isotope labels ────────────────────────────────────────────────────────

    def _isotopes(self):
        """Natural isotopes of the periodic table, built once."""
        if self._isotope_index is None:
            try:
                info = getattr(self.main_window, 'periodic_table_info', None)
                if info is not None:
                    elements = list(info.elements.values())
                else:
                    from widget.periodic_table_widget import PeriodicTableWidget
                    elements = PeriodicTableWidget.create_elements_data()
                self._isotope_index = sia_stats.isotope_index(elements)
            except Exception:
                _itk_log.exception("Handled exception in _isotopes")
                self._isotope_index = []
        return self._isotope_index

    def _selected_labels(self):
        """Labels such as ``'56Fe'`` for the isotopes selected for analysis."""
        out = []
        for el, masses in (getattr(self.main_window, 'selected_isotopes', {}) or {}).items():
            for m in masses:
                try:
                    out.append(f"{int(round(float(m)))}{el}")
                except (TypeError, ValueError):
                    continue
        return out

    def mass_label(self, mass: float) -> str:
        """Label an m/z value with its isotopes, analysed isotopes first.

        Args:
            mass (float): m/z.

        Returns:
            str: For example ``'⁵⁶Fe'``.
        """
        return sia_stats.mass_label(mass, self._isotopes(), self._selected_labels())

    def isotope_text(self, mass: float) -> str:
        """Plain isotope list for an m/z value, e.g. ``'58Ni / 58Fe'``.

        Args:
            mass (float): m/z.

        Returns:
            str: Isotope labels joined by ``' / '``, or an empty string.
        """
        return " / ".join(sia_stats.isotopes_at_mass(
            self._isotopes(), mass, preferred=self._selected_labels()))

    # ── history ───────────────────────────────────────────────────────────────

    def history(self):
        """The SIA history store, opened on first use."""
        if self._history is None:
            self._history = sia_stats.SIAHistory()
        return self._history

    def _record_history(self):
        """Add the loaded SIA to the history.

        Returns:
            dict | None: Result of :meth:`sia_stats.SIAHistory.record`.
        """
        try:
            entry = sia_stats.history_entry(
                self.single_ion_info, self.per_mass_distributions,
                self.single_ion_source_folder)
            return self.history().record(entry)
        except Exception:
            _itk_log.exception("Handled exception in _record_history")
            return None

    @staticmethod
    def _history_message(result) -> str:
        """Sentence for the load message about how this SIA compares to earlier ones."""
        if not result:
            return ""
        n_prev = result.get('n_previous', 0)
        if n_prev < sia_stats.MIN_HISTORY_FOR_LIMITS:
            return (f"\n\nSIA history: {n_prev} earlier session(s); limits need at least "
                    f"{sia_stats.MIN_HISTORY_FOR_LIMITS}.")
        names = {'sigma': 'σ', 'average_single_ion_area': 'Mean single-ion area'}
        lines = []
        for key, name in names.items():
            status = result.get(key)
            if status == 'action':
                lines.append(f"{name} is beyond ±3 SD of the earlier sessions.")
            elif status == 'warn':
                lines.append(f"{name} is beyond ±2 SD of the earlier sessions.")
        if not lines:
            return f"\n\nSIA history: within the usual range of {n_prev} earlier sessions."
        return "\n\nSIA history: " + " ".join(lines) + " Open History in the SIA window to check."

    # ── project state ─────────────────────────────────────────────────────────

    def export_state(self):
        """SIA data to store in a project file.

        Returns:
            dict | None: State dictionary, or None without a SIA.
        """
        if not self.is_sia_loaded():
            return None
        return {
            'version': 1,
            'single_ion_distribution_data': self.single_ion_distribution_data,
            'single_ion_source_folder': self.single_ion_source_folder,
            'single_ion_info': self.single_ion_info,
            'per_mass_distributions': self.per_mass_distributions,
            'exclude_outliers': self._exclude_outliers,
        }

    def import_state(self, state):
        """Restore SIA data saved with a project.

        The Sigma box and the per-element sigma values come from the
        project itself, so they are not changed here.

        Args:
            state (dict | None): Output of :meth:`export_state`.
        """
        if not state:
            return
        try:
            self.single_ion_distribution_data = state['single_ion_distribution_data']
            self.single_ion_source_folder     = state.get('single_ion_source_folder')
            self.single_ion_info              = dict(state.get('single_ion_info') or {})
            self.per_mass_distributions       = dict(state.get('per_mass_distributions') or {})
            self._exclude_outliers            = bool(state.get('exclude_outliers', False))
            if self.info_sid_button is not None:
                self._update_ui_after_load()
        except (KeyError, TypeError):
            _itk_log.exception("Handled exception in import_state")

    # ── upload flow ───────────────────────────────────────────────────────────

    def upload_single_ion_distribution(self):
        """Prompt the user to choose an instrument type, then open the
        appropriate file/folder picker and start background processing.

        Args:
            None
        """
        if self._is_processing:
            self._themed_msgbox('information', self.main_window, "Processing in Progress", "SIA processing is already in progress. Please wait.")
            return

        msg = QMessageBox(self.main_window)
        msg.setWindowTitle("Select Data Type")
        msg.setText("What type of data do you want to load for SIA calculation?")
        msg.setInformativeText(
            "Nu Vitesse: Folder containing run.info\n"
            "TOFWERK: Single .h5 file"
        )
        msg.setStyleSheet(dialog_qss(theme.palette))
        nu_btn     = msg.addButton("Nu Vitesse Folder", QMessageBox.ActionRole)
        tof_btn    = msg.addButton("TOFWERK .h5 File",  QMessageBox.ActionRole)
        cancel_btn = msg.addButton(QMessageBox.Cancel)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == cancel_btn:
            return

        if clicked == nu_btn:
            folder = QFileDialog.getExistingDirectory(
                self.main_window, "Select Nu Vitesse Folder with run.info",
                "", QFileDialog.ShowDirsOnly
            )
            if folder:
                self._start_sia_processing(folder, "nu")

        elif clicked == tof_btn:
            file_path, _ = QFileDialog.getOpenFileName(
                self.main_window, "Select TOFWERK .h5 File",
                "", "HDF5 Files (*.h5 *.hdf5);;All Files (*.*)"
            )
            if file_path:
                self._start_sia_processing(file_path, "tofwerk")

    def upload_overlay_distribution(self):
        """Load a second SIA dataset for overlay comparison.
        Follows the same instrument-selection flow but stores results
        in the overlay slots instead of the primary ones.

        Args:
            None
        """
        if self._is_processing:
            self._themed_msgbox('information', self.main_window, "Processing in Progress", "SIA processing is already in progress. Please wait.")
            return

        msg = QMessageBox(self.main_window)
        msg.setWindowTitle("Select Overlay Data Type")
        msg.setText("Load a second SIA for comparison overlay.")
        msg.setInformativeText(
            "Nu Vitesse: Folder containing run.info\n"
            "TOFWERK: Single .h5 file"
        )
        msg.setStyleSheet(dialog_qss(theme.palette))
        nu_btn     = msg.addButton("Nu Vitesse Folder", QMessageBox.ActionRole)
        tof_btn    = msg.addButton("TOFWERK .h5 File",  QMessageBox.ActionRole)
        cancel_btn = msg.addButton(QMessageBox.Cancel)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == cancel_btn:
            return

        self._loading_overlay = True

        if clicked == nu_btn:
            folder = QFileDialog.getExistingDirectory(
                self.main_window, "Select Nu Vitesse Folder (Overlay)",
                "", QFileDialog.ShowDirsOnly
            )
            if folder:
                self._start_sia_processing(folder, "nu")
            else:
                self._loading_overlay = False

        elif clicked == tof_btn:
            file_path, _ = QFileDialog.getOpenFileName(
                self.main_window, "Select TOFWERK .h5 File (Overlay)",
                "", "HDF5 Files (*.h5 *.hdf5);;All Files (*.*)"
            )
            if file_path:
                self._start_sia_processing(file_path, "tofwerk")
            else:
                self._loading_overlay = False

    def _start_sia_processing(self, data_path: str, file_type: str = "nu"):
        """Spawn a QThread, move a SIAWorker onto it, and start processing.

        Args:
            data_path (str): Path to the Nu Vitesse folder or TOFWERK .h5 file.
            file_type (str): ``'nu'`` or ``'tofwerk'``.
        """
        try:
            self._is_processing = True
            self.upload_sid_button.setEnabled(False)
            self.upload_sid_button.setText("Processing...")
            self.main_window.progress_bar.setVisible(True)
            self.main_window.progress_bar.setValue(0)

            self.sia_thread = QThread()
            self.sia_worker = SIAWorker()
            self.sia_worker.moveToThread(self.sia_thread)

            self.sia_thread.started.connect(
                lambda: self.sia_worker.process_sia_data(data_path, file_type)
            )
            self.sia_worker.progress.connect(self._on_progress,      Qt.QueuedConnection)
            self.sia_worker.status_update.connect(self._on_status,   Qt.QueuedConnection)
            self.sia_worker.finished.connect(self._on_finished,      Qt.QueuedConnection)
            self.sia_worker.error.connect(self._on_error,            Qt.QueuedConnection)

            self.sia_worker.finished.connect(self.sia_thread.quit,   Qt.QueuedConnection)
            self.sia_worker.error.connect(self.sia_thread.quit,      Qt.QueuedConnection)
            self.sia_thread.finished.connect(self.sia_worker.deleteLater)
            self.sia_thread.finished.connect(self.sia_thread.deleteLater)
            self.sia_thread.finished.connect(self._on_thread_cleanup)

            self.sia_thread.start()

        except Exception as e:
            _itk_log.exception("Handled exception in _start_sia_processing")
            self._reset_processing_state()
            msg = f"Error starting SIA thread: {e}"
            self.main_window.status_label.setText(msg)
            self._themed_msgbox('critical', self.main_window, "Thread Error", msg)

    # ── thread callbacks ──────────────────────────────────────────────────────

    def _on_progress(self, value: int):
        """Forward a progress value to the main-window progress bar.

        Args:
            value (int): Progress percentage (0–100).
        """
        self.main_window.progress_bar.setValue(value)

    def _on_status(self, text: str):
        """Forward a status string to the main-window status label.

        Args:
            text (str): Status message to display.
        """
        self.main_window.status_label.setText(text)

    def _on_finished(self, result: dict):
        """Store results, update UI, and notify the user on successful processing.
        Routes to overlay storage if ``_loading_overlay`` is True.

        Args:
            result (dict): Result dictionary emitted by SIAWorker.finished.
        """
        try:
            if self._loading_overlay:
    
                self._overlay_distribution_data = None
                self._overlay_info              = None
                self._overlay_per_mass          = {}

                self._overlay_distribution_data = result['single_ion_distribution_data']
                self._overlay_info              = result['single_ion_info']
                self._overlay_per_mass          = result.get('per_mass_distributions', {})
                self._loading_overlay           = False

                ov = self._overlay_info
                self.main_window.status_label.setText(
                    f"Overlay SIA loaded: {ov['sample_name']}, "
                    f"σ = {ov['calculated_sigma']:.3f}"
                )
                self._themed_msgbox(
                    'information', self.main_window, "Overlay Loaded",
                    f"Overlay SIA loaded successfully!\n\n"
                    f"Instrument: {ov['instrument_type']}\n"
                    f"Source: {ov['sample_name']}\n"
                    f"σ = {ov['calculated_sigma']:.3f}\n\n"
                    f"Open the SIA info dialog to see both distributions."
                )
            else:
                self.single_ion_distribution_data = result['single_ion_distribution_data']
                self.single_ion_source_folder     = result['single_ion_source_folder']
                self.single_ion_info              = result['single_ion_info']
                self.per_mass_distributions       = result.get('per_mass_distributions', {})
                self._exclude_outliers            = False

                self._update_ui_after_load()
                self._apply_sigma(self.get_effective_sigma())
                self._apply_sia_to_all_samples()
                history = self._record_history()
                self._show_success_message(history)

                info = self.single_ion_info
                self.main_window.status_label.setText(
                    f"SIA loaded from {info['instrument_type']}: {info['sample_name']}, "
                    f"σ = {info['calculated_sigma']:.3f}"
                )
        except Exception as e:
            _itk_log.exception("Handled exception in _on_finished")
            msg = f"Error processing SIA results: {e}"
            self.main_window.status_label.setText(msg)
            self._themed_msgbox('critical', self.main_window, "Results Error", msg)
        finally:
            self._reset_processing_state()

    def _on_error(self, msg: str):
        """Handle a processing error emitted by the worker.

        Args:
            msg (str): Human-readable error message.
        """
        self._loading_overlay = False
        self._reset_processing_state()
        self.main_window.status_label.setText(f"SIA Error: {msg}")
        self._themed_msgbox('critical', self.main_window, "SIA Processing Error", msg)

    def _on_thread_cleanup(self):
        """Disconnect worker signals and nullify thread/worker references after
        the thread has finished.

        Without disconnecting, the signal slots keep bound-method references to
        the worker, preventing it from being garbage-collected even after
        ``sia_worker = None`` is assigned.

        Args:
            None
        """
        if self.sia_worker is not None:
            for sig in (
                self.sia_worker.finished,
                self.sia_worker.error,
                self.sia_worker.progress,
                self.sia_worker.status_update,
            ):
                try:
                    sig.disconnect()
                except RuntimeError:
                    _itk_log.exception("Handled exception in _on_thread_cleanup")

        self.sia_thread = None
        self.sia_worker = None

    def _reset_processing_state(self):
        """Restore the upload button and hide the progress bar.

        Args:
            None
        """
        self._is_processing = False
        self.upload_sid_button.setEnabled(True)
        self.upload_sid_button.setText("")
        self.main_window.progress_bar.setVisible(False)

    # ── post-load UI helpers ──────────────────────────────────────────────────

    def _update_ui_after_load(self):
        """Enable the SIA buttons and show where sigma comes from.

        Args:
            None
        """
        self.info_sid_button.setEnabled(True)
        self.clear_sid_button.setEnabled(True)
        self._style_upload_button(True)
        self._refresh_source_label()

    def _apply_sia_to_all_samples(self):
        """Trigger a parameters-table refresh so all samples reflect the new SIA.

        Args:
            None
        """
        if hasattr(self.main_window, 'parameters_table'):
            self.main_window.update_parameters_table()

    def _show_success_message(self, history=None):
        """Display a QMessageBox summarising the loaded SIA.

        Args:
            history (dict | None): Result of recording the SIA in the history.
        """
        info = self.single_ion_info
        kind = 'information'
        if history and 'action' in (history.get('sigma'), history.get('average_single_ion_area')):
            kind = 'warning'

        self._themed_msgbox(
            kind, self.main_window, "Success",
            f"Single-ion distribution loaded successfully!\n\n"
            f"Instrument: {info['instrument_type']}\n"
            f"Source: {info['sample_name']}\n"
            f"Distribution points: {info['distribution_points']}\n"
            f"Calculated σ: {info['calculated_sigma']:.3f}\n"
            f"Mean signal: {info['mean_signal']:.1f} counts\n\n"
            f"Applied real single-ion distribution to analysis"
            f"{self._history_message(history)}"
        )

    # ── info dialog ───────────────────────────────────────────────────────────

    def show_single_ion_info(self):
        """Open the SIA information dialog with plot and optional per-mass
        controls, export buttons, overlay toggle, and outlier exclusion.

        Args:
            None
        """
        if self.single_ion_distribution_data is None:
            self._themed_msgbox('warning', self.main_window, "No Data", "No single-ion distribution loaded.")
            return

        info   = self.single_ion_info
        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("Single-Ion Distribution Information")
        dialog.setMinimumSize(1000, 800)
        dialog.setStyleSheet(dialog_qss(theme.palette))
        self._register_dialog(dialog)
        layout = QVBoxLayout(dialog)

        card = QFrame()
        card.setObjectName("siaInfoCard")
        card.setProperty("_sia_info_card", True)
        card.setStyleSheet(self._info_card_qss())
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(14, 10, 14, 10)
        lbl = QLabel(self._create_info_html(info))
        lbl.setTextFormat(Qt.RichText)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignTop)
        lbl.setProperty("_sia_info_html", True)
        lbl.setProperty("_sia_info_data", info)
        card_lay.addWidget(lbl)
        layout.addWidget(card)

        toolbar = QHBoxLayout()

        export_csv_btn = QPushButton("Export CSV")
        export_csv_btn.setIcon(qta.icon('fa6s.file-csv', color="#2196F3"))
        export_csv_btn.setToolTip("Export per-mass sigma table to CSV")
        export_csv_btn.clicked.connect(lambda: self._export_per_mass_csv(dialog))
        toolbar.addWidget(export_csv_btn)

        export_plot_btn = QPushButton("Export Plot")
        export_plot_btn.setIcon(qta.icon('fa6s.image', color="#9C27B0"))
        export_plot_btn.setToolTip("Export current plot as SVG or PNG")
        toolbar.addWidget(export_plot_btn)

        qq_btn = QPushButton("Q-Q Plot")
        qq_btn.setIcon(qta.icon('fa6s.chart-line', color="#009688"))
        qq_btn.setToolTip("Show lognormal Q-Q plot for the current distribution")
        qq_btn.clicked.connect(lambda: self._show_qq_dialog(info, dialog))
        toolbar.addWidget(qq_btn)

        overlay_btn = QPushButton("Load Overlay")
        overlay_btn.setIcon(qta.icon('fa6s.layer-group', color="#FF9800"))
        overlay_btn.setToolTip("Load a second SIA for comparison overlay")
        overlay_btn.clicked.connect(self.upload_overlay_distribution)
        toolbar.addWidget(overlay_btn)

        clear_overlay_btn = QPushButton("Clear Overlay")
        clear_overlay_btn.setIcon(qta.icon('fa6s.xmark', color="#f44336"))
        clear_overlay_btn.setToolTip("Remove overlay SIA data")
        clear_overlay_btn.clicked.connect(lambda: self._clear_overlay(dialog))
        clear_overlay_btn.setEnabled(self._overlay_info is not None)
        toolbar.addWidget(clear_overlay_btn)

        history_btn = QPushButton("History")
        history_btn.setIcon(qta.icon('fa6s.clock-rotate-left', color=theme.palette.accent))
        history_btn.setToolTip("σ and mean single-ion area of earlier sessions")
        history_btn.clicked.connect(lambda: self.show_history_dialog(dialog))
        toolbar.addWidget(history_btn)

        toolbar.addStretch()

        assign_sigma_btn = QPushButton("Assign Per-Mass σ")
        assign_sigma_btn.setIcon(qta.icon('fa6s.bullseye', color="#E91E63"))
        assign_sigma_btn.setToolTip(
            "Assign each element's sigma from its closest matching per-mass SIA"
        )
        assign_sigma_btn.clicked.connect(self._assign_per_mass_sigma)
        assign_sigma_btn.setEnabled(bool(self.per_mass_distributions))
        toolbar.addWidget(assign_sigma_btn)

        layout.addLayout(toolbar)

        # ── per-mass controls ─────────────────────────────────────────────
        if self.per_mass_distributions:
            ctrl = QHBoxLayout()
            self.view_toggle = QCheckBox("View individual mass")
            ctrl.addWidget(self.view_toggle)

            self.mass_selector = QComboBox()
            self.mass_selector.setEnabled(False)
            self.mass_selector.setMinimumWidth(200)

            for mass_val, mass_key in sorted(
                (d['mass'], k) for k, d in self.per_mass_distributions.items()
            ):
                self.mass_selector.addItem(self.mass_label(mass_val), mass_key)

            ctrl.addWidget(QLabel("Select mass:"))
            ctrl.addWidget(self.mass_selector)
            ctrl.addStretch()
            layout.addLayout(ctrl)

            vtype = QHBoxLayout()
            self.view_type_group     = QButtonGroup()
            self.radio_distribution  = QRadioButton("Individual Distribution")
            self.radio_sigma_compare = QRadioButton("Sigma Comparison")
            self.radio_distribution.setChecked(True)
            for rb in (self.radio_distribution, self.radio_sigma_compare):
                rb.setEnabled(False)
                self.view_type_group.addButton(rb)
            vtype.addWidget(QLabel("View Type:"))
            vtype.addWidget(self.radio_distribution)
            vtype.addWidget(self.radio_sigma_compare)

            self.outlier_checkbox = QCheckBox("Exclude outliers from global σ")
            self.outlier_checkbox.setChecked(self._exclude_outliers)
            self.outlier_checkbox.setToolTip(
                "Use the weighted mean of the per-mass σ values without the outlier masses\n"
                f"(modified z-score above {sia_stats.ROBUST_Z_LIMIT}) as the σ for the analysis."
            )
            vtype.addWidget(self.outlier_checkbox)

            vtype.addStretch()
            layout.addLayout(vtype)

        # ── plots: main distribution ─────────────────────────────────────
        plot_container = QVBoxLayout()
        layout.addLayout(plot_container)

        self._plot_overall = self._create_sia_plot(info, None)
        self._plot_mass    = self._create_sia_plot(info, None)
        self._plot_sigma   = self._create_sigma_comparison_plot(info)

        for pw in (self._plot_overall, self._plot_mass, self._plot_sigma):
            plot_container.addWidget(pw)

        self._plot_mass.hide()
        self._plot_sigma.hide()

        def _export_visible_plot():
            """Determine which plot widget is currently visible and export it.

            Args:
                None
            """
            if self._plot_sigma.isVisible():
                self._export_plot(self._plot_sigma, dialog)
            elif self._plot_mass.isVisible():
                self._export_plot(self._plot_mass, dialog)
            else:
                self._export_plot(self._plot_overall, dialog)

        export_plot_btn.clicked.connect(_export_visible_plot)

        if self.per_mass_distributions:
            def _refresh():
                """Refresh the visible plot based on current toggle/selector state.

                Args:
                    None
                """
                if self.view_toggle.isChecked():
                    self.mass_selector.setEnabled(True)
                    self.radio_distribution.setEnabled(True)
                    self.radio_sigma_compare.setEnabled(True)

                    if self.radio_sigma_compare.isChecked():
                        self._current_qq_mass_key = None
                        self._plot_overall.hide()
                        self._plot_mass.hide()
                        self._update_sigma_comparison_plot(
                            self._plot_sigma,
                            exclude_outliers=self.outlier_checkbox.isChecked()
                        )
                        self._plot_sigma.show()
                    else:
                        mass_key = self.mass_selector.currentData()
                        self._current_qq_mass_key = mass_key
                        self._update_sia_plot(self._plot_mass, info, mass_key)
                        self._plot_overall.hide()
                        self._plot_sigma.hide()
                        self._plot_mass.show()
                else:
                    self._current_qq_mass_key = None
                    self.mass_selector.setEnabled(False)
                    self.radio_distribution.setEnabled(False)
                    self.radio_sigma_compare.setEnabled(False)
                    self._plot_mass.hide()
                    self._plot_sigma.hide()
                    self._plot_overall.show()

            self.view_toggle.stateChanged.connect(_refresh)
            self.mass_selector.currentIndexChanged.connect(
                lambda: _refresh() if (
                    self.view_toggle.isChecked() and
                    self.radio_distribution.isChecked()
                ) else None
            )
            self.radio_distribution.toggled.connect(
                lambda: _refresh() if self.view_toggle.isChecked() else None
            )
            def _on_outliers(_state):
                """Apply the outlier choice to σ, then redraw.

                Args:
                    _state (int): Check state from the signal.
                """
                self.set_exclude_outliers(self.outlier_checkbox.isChecked())
                if self.view_toggle.isChecked() and self.radio_sigma_compare.isChecked():
                    _refresh()

            self.outlier_checkbox.stateChanged.connect(_on_outliers)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)
        for btn in dialog.findChildren(QPushButton):
            btn.setAutoDefault(False)
        dialog.show()

    # ── plot helpers ──────────────────────────────────────────────────────────

    def _create_info_html(self, info: dict) -> str:
        """
        Build the HTML shown in the information card of the dialog.

        Args:
            info (dict): ``single_ion_info`` dictionary.

        Returns:
            str: HTML string with a title and one row of labelled values.
        """
        p = theme.palette
        cells = [
            ("Sample", info['sample_name']),
            ("Calculated σ (SIA)", f"{info['calculated_sigma']:.3f}"),
            ("Distribution points", f"{info['distribution_points']}"),
            ("Mean signal", f"{info['mean_signal']:.1f} counts"),
        ]
        tds = "".join(
            f'<td style="padding:4px 28px 0 0;">'
            f'<div style="color:{p.text_muted};font-size:9pt;">{name}</div>'
            f'<div style="color:{p.text_primary};font-size:12pt;font-weight:600;">{value}</div>'
            f'</td>'
            for name, value in cells
        )
        return (
            f'<div style="color:{p.text_secondary};font-weight:600;font-size:10pt;">'
            f'Single-Ion Distribution</div>'
            f'<table style="border-collapse:collapse;"><tr>{tds}</tr></table>'
        )

    @staticmethod
    def _annot(text: str) -> str:
        """
        Wrap a plain-text string in the standard annotation HTML style
        used on pyqtgraph TextItems throughout the SIA plots.

        Args:
            text (str): Plain text (may contain ``<br/>`` for line breaks).

        Returns:
            str: HTML-formatted annotation string.
        """
        fg = theme.palette.plot_fg
        return (
            f'<div style="font-size:18pt;font-family:Times New Roman;'
            f'font-weight:bold;color:{fg};">{text}</div>'
        )

    @staticmethod
    def _make_plot_widget(left_label: str, bottom_label: str) -> pg.PlotWidget:
        """
        Create a styled PlotWidget with shared axis and font settings.
        All plot methods call this factory to avoid duplicated styling code.

        Args:
            left_label   (str): Y-axis label text.
            bottom_label (str): X-axis label text.

        Returns:
            pg.PlotWidget: Configured plot widget ready for data.
        """
        from widget.custom_plot_widget import CustomPlotItem

        cpi = CustomPlotItem()
        pw  = pg.PlotWidget(plotItem=cpi)
        cpi.plot_widget = pw

        pw.persistent_dialog_settings = {}
        pw.custom_settings             = {}
        pw.custom_axis_labels = {
            'left'  : {'text': left_label,   'units': None},
            'bottom': {'text': bottom_label, 'units': None},
        }

        p = theme.palette
        pw.setBackground(p.plot_bg)
        pi = pw.getPlotItem()

        axis_pen   = QPen(QColor(p.plot_fg), 2)
        text_color = QColor(p.plot_fg)
        tick_font  = QFont('Times New Roman', 20)
        tick_font.setBold(True)

        for name in ('left', 'bottom', 'top', 'right'):
            ax = pi.getAxis(name)
            ax.setPen(axis_pen)
            ax.setTextPen(text_color)
            ax.setStyle(tickFont=tick_font, tickTextOffset=10, tickLength=10)

        pw.setLabel('left',   left_label,   color=p.plot_fg, font='bold 20pt Times New Roman')
        pw.setLabel('bottom', bottom_label, color=p.plot_fg, font='bold 20pt Times New Roman')
        pi.getAxis('top').setStyle(showValues=False)
        pi.getAxis('right').setStyle(showValues=False)
        pi.showGrid(x=False, y=False)
        pw.setMinimumHeight(400)
        return pw

    def _create_sia_plot(self, info: dict, mass_key) -> pg.PlotWidget:
        """
        Create a new SIA distribution plot widget and populate it.

        Args:
            info     (dict):      ``single_ion_info`` dictionary.
            mass_key (str | None): Key into ``per_mass_distributions`` for a
                                   specific mass, or ``None`` for the overall
                                   distribution.

        Returns:
            pg.PlotWidget: Populated distribution plot widget.
        """
        pw = self._make_plot_widget('Probability Density', 'Counts')
        self._update_sia_plot(pw, info, mass_key)
        return pw

    def _update_sia_plot(self, pw: pg.PlotWidget, info: dict, mass_key):
        """Redraw a SIA distribution plot in place without recreating the widget.
        Called on every mass-selector or toggle change.

        Now includes overlay support: if overlay data is loaded, draws the
        overlay distribution in a semi-transparent blue behind the primary.

        Args:
            pw       (pg.PlotWidget): Existing plot widget to update.
            info     (dict):          ``single_ion_info`` dictionary.
            mass_key (str | None):    Key into ``per_mass_distributions``, or
                                      ``None`` for the overall distribution.
        """
        pw.clear()

        if mass_key is not None and self.per_mass_distributions:
            md          = self.per_mass_distributions[mass_key]
            sig_raw     = md['distribution'][:, 0]
            raw_weights = md['distribution'][:, 1]
            mean_signal = md['mean_signal']
            calc_sigma  = md['sigma']
        else:
            sig_raw     = info['signal_values']
            raw_weights = info['weights']
            mean_signal = info['mean_signal']
            calc_sigma  = info['calculated_sigma']

        avg_sia  = info.get('average_single_ion_area', 1.0)
        sig_vals = sig_raw / avg_sia
        step     = np.mean(np.diff(sig_vals)) if len(sig_vals) > 1 else 1.0
        w_norm   = raw_weights / (raw_weights.sum() * step)

        # ── overlay distribution (drawn first, behind primary) ────────────
        if self._overlay_info is not None and mass_key is None:
            ov_info = self._overlay_info
            ov_raw  = ov_info['signal_values']
            ov_w    = ov_info['weights']
            ov_sia  = ov_info.get('average_single_ion_area', 1.0)
            ov_vals = ov_raw / ov_sia
            ov_step = np.mean(np.diff(ov_vals)) if len(ov_vals) > 1 else 1.0
            ov_norm = ov_w / (ov_w.sum() * ov_step)

            pw.addItem(pg.BarGraphItem(
                x=ov_vals, height=ov_norm, width=ov_step * 0.9,
                brush=pg.mkBrush(100, 149, 237, 100),
                pen=pg.mkPen(QColor(100, 149, 237), width=1)
            ))

            try:
                ov_mean  = ov_info['mean_signal']
                ov_sigma = ov_info['calculated_sigma']
                mu_ov    = np.log(ov_mean) - 0.5 * ov_sigma ** 2 - np.log(ov_sia)
                x_ov     = np.linspace(0.01, ov_vals.max() * 1.5, 500)
                y_ov     = lognormal_pdf_scipy(x_ov, mu_ov, ov_sigma)
                pw.plot(x_ov, y_ov,
                        pen=pg.mkPen(color=QColor(100, 149, 237), width=2, style=Qt.DashLine))
            except Exception:
                _itk_log.exception("Handled exception in _update_sia_plot")

            ov_txt = pg.TextItem(
                anchor=(1, 0),
                html=f'<div style="font-size:14pt;font-family:Times New Roman;'
                     f'color:rgb(100,149,237);font-weight:bold;">'
                     f'Overlay: {ov_info["sample_name"]} '
                     f'(σ={ov_info["calculated_sigma"]:.2f})</div>'
            )
            ov_txt.setPos(sig_vals.max() * 1.2, w_norm.max() * 0.85)
            pw.addItem(ov_txt)

        # ── primary distribution ──────────────────────────────────────────
        pw.addItem(pg.BarGraphItem(
            x=sig_vals, height=w_norm, width=step * 0.9,
            brush=pg.mkBrush(220, 220, 220, 255),
            pen=pg.mkPen('k', width=1)
        ))

        try:
            mu_adc = np.log(mean_signal) - 0.5 * calc_sigma ** 2
            mu_ion = mu_adc - np.log(avg_sia)
            x_fit  = np.linspace(0.01, sig_vals.max() * 1.5, 500)
            y_fit  = lognormal_pdf_scipy(x_fit, mu_ion, calc_sigma)
            pw.plot(x_fit, y_fit, pen=pg.mkPen(color='r', width=2.5))
        except Exception as e:
            _itk_log.exception("Handled exception in _update_sia_plot")
            _itk_log.error(f"Lognormal fit failed: {e}")

        q_val = self._calc_quantile(mean_signal, calc_sigma, avg_sia,
                                    sig_vals, raw_weights)
        if q_val is not None:
            pw.addItem(pg.InfiniteLine(
                pos=q_val, angle=90,
                pen=pg.mkPen(color='r', width=2, style=Qt.DotLine)
            ))
            q_txt = pg.TextItem(
                anchor=(0.5, 0),
                html=f'<div style="font-size:20pt;font-family:Times New Roman;'
                     f'font-weight:bold;color:{theme.palette.plot_fg};">0.9999<sup>th</sup> quantile</div>'
            )
            q_txt.setPos(q_val, w_norm.max())
            pw.addItem(q_txt)

        mass_line = ""
        if mass_key is not None and self.per_mass_distributions:
            mass_line = (f'<br/><span style="font-size:14pt;font-weight:normal;">'
                         f'{self.mass_label(self.per_mass_distributions[mass_key]["mass"])}</span>')
        s_txt = pg.TextItem(
            anchor=(0, 1),
            html=f'<div style="font-size:20pt;font-family:Times New Roman;'
                 f'font-weight:bold;color:{theme.palette.plot_fg};">σ = {calc_sigma:.2f}{mass_line}</div>'
        )
        s_txt.setPos(sig_vals[int(len(sig_vals) * 0.15)], w_norm.max() * 0.95)
        pw.addItem(s_txt)

        pw.setXRange(0, sig_vals.max() * 1.3)
        pw.setYRange(0, w_norm.max() * 1.15)

    # ── Q-Q plot ──────────────────────────────────────────────────────────────

    def _create_qq_plot(self, info: dict, mass_key) -> pg.PlotWidget:
        """
        Create a new lognormal Q-Q plot widget and populate it.

        Args:
            info     (dict):      ``single_ion_info`` dictionary.
            mass_key (str | None): Key into ``per_mass_distributions`` for a
                                   specific mass, or ``None`` for the overall
                                   distribution.

        Returns:
            pg.PlotWidget: Populated Q-Q plot widget.
        """
        pw = self._make_plot_widget('Observed Quantiles',
                                    'Theoretical Quantiles (Lognormal)')
        self._update_qq_plot(pw, info, mass_key)
        return pw

    def _update_qq_plot(self, pw: pg.PlotWidget, info: dict, mass_key):
        """Draw a Q-Q plot: theoretical lognormal quantiles on x,
        observed quantiles on y.  Points on the diagonal = model fits.

        Args:
            pw       (pg.PlotWidget): Existing plot widget to update.
            info     (dict):          ``single_ion_info`` dictionary.
            mass_key (str | None):    Key into ``per_mass_distributions``, or
                                      ``None`` for the overall distribution.
        """
        pw.clear()

        if mass_key is not None and self.per_mass_distributions:
            md          = self.per_mass_distributions[mass_key]
            sig_raw     = md['distribution'][:, 0]
            raw_weights = md['distribution'][:, 1]
            mean_signal = md['mean_signal']
            calc_sigma  = md['sigma']
        else:
            sig_raw     = info['signal_values']
            raw_weights = info.get('raw_counts', info['weights'])
            mean_signal = info['mean_signal']
            calc_sigma  = info['calculated_sigma']

        avg_sia  = info.get('average_single_ion_area', 1.0)
        sig_vals = sig_raw / avg_sia

        try:
            mu_adc = np.log(mean_signal) - 0.5 * calc_sigma ** 2
            mu_ion = mu_adc - np.log(avg_sia)

            order  = np.argsort(sig_vals)
            x_sort = sig_vals[order]
            w_sort = raw_weights[order]
            ecdf   = np.cumsum(w_sort)
            ecdf  /= ecdf[-1]

            theoretical = stats.lognorm.ppf(ecdf, s=calc_sigma,
                                            scale=np.exp(mu_ion))

            mask = (np.isfinite(theoretical) & np.isfinite(x_sort)
                    & (ecdf > 0.005) & (ecdf < 0.995))
            obs  = x_sort[mask]
            theo = theoretical[mask]

            pw.addItem(pg.ScatterPlotItem(
                x=theo, y=obs,
                symbol='o', size=8,
                pen=pg.mkPen(self._point_color().darker(120), width=1),
                brush=pg.mkBrush(self._point_color(180)),
            ))

            lo = min(theo.min(), obs.min())
            hi = max(theo.max(), obs.max())
            pw.plot([lo, hi], [lo, hi],
                    pen=pg.mkPen(color=_QQ_LINE_COLOR, width=2,
                                 style=Qt.DashLine))

            t = pg.TextItem(
                anchor=(0, 0),
                html=self._annot(f'σ = {calc_sigma:.3f}')
            )
            t.setPos(lo + (hi - lo) * 0.05, hi - (hi - lo) * 0.05)
            pw.addItem(t)

            pw.setXRange(lo * 0.9, hi * 1.1)
            pw.setYRange(lo * 0.9, hi * 1.1)

        except Exception as e:
            _itk_log.exception("Handled exception in _update_qq_plot")
            t = pg.TextItem(anchor=(0.5, 0.5),
                            html=self._annot(f'Q-Q plot unavailable: {e}'))
            t.setPos(0.5, 0.5)
            pw.addItem(t)

    def _show_qq_dialog(self, info: dict, parent: QWidget):
        """Open a separate dialog showing a lognormal Q-Q plot for the
        currently visible distribution (overall or per-mass).

        The plot shows theoretical lognormal quantiles on the X-axis and
        observed quantiles on the Y-axis, with a 1:1 diagonal reference
        line and σ annotation.

        Args:
            info   (dict):    ``single_ion_info`` dictionary.
            parent (QWidget): Parent widget for the dialog.
        """
        mass_key = self._current_qq_mass_key

        if mass_key is not None and self.per_mass_distributions:
            md         = self.per_mass_distributions[mass_key]
            title_text = f"Q-Q Plot — m/z {md['mass']:.4f}"
        else:
            title_text = "Q-Q Plot — Overall Distribution"

        # ── build dialog ──────────────────────────────────────────────────
        dlg = QDialog(parent)
        dlg.setWindowTitle(title_text)
        dlg.setMinimumSize(700, 650)
        dlg.setStyleSheet(dialog_qss(theme.palette))
        self._register_dialog(dlg)
        lay = QVBoxLayout(dlg)

        pw = self._create_qq_plot(info, mass_key)
        pw.setMinimumHeight(500)
        lay.addWidget(pw)

        # ── bottom row: export + close ────────────────────────────────────
        btn_row = QHBoxLayout()

        export_btn = QPushButton("Export Plot")
        export_btn.setIcon(qta.icon('fa6s.image', color="#9C27B0"))
        export_btn.clicked.connect(lambda: self._export_plot(pw, dlg))
        btn_row.addWidget(export_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(close_btn)

        lay.addLayout(btn_row)
        for btn in dlg.findChildren(QPushButton):
            btn.setAutoDefault(False)
        dlg.show()

    def show_history_dialog(self, parent=None):
        """Open the SIA history: σ and mean single-ion area per session.

        Both values are plotted against the acquisition date with the mean
        and the ±2 SD / ±3 SD limits of all recorded sessions. Points beyond
        2 SD are orange, beyond 3 SD red; the SIA currently loaded is ringed.
        Sessions can be removed from the history or exported to CSV.

        Args:
            parent (QWidget | None): Parent widget for the dialog.
        """
        hist = self.history()
        dlg = QDialog(parent or self.main_window)
        dlg.setWindowTitle("SIA History")
        dlg.setMinimumSize(980, 760)
        dlg.setStyleSheet(dialog_qss(theme.palette))
        self._register_dialog(dlg)
        lay = QVBoxLayout(dlg)

        card = QFrame()
        card.setObjectName("siaInfoCard")
        card.setProperty("_sia_info_card", True)
        card.setStyleSheet(self._info_card_qss())
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(14, 10, 14, 10)
        summary_lbl = QLabel()
        summary_lbl.setTextFormat(Qt.RichText)
        summary_lbl.setWordWrap(True)
        card_lay.addWidget(summary_lbl)
        lay.addWidget(card)

        sigma_pw = pg.PlotWidget(axisItems={'bottom': pg.DateAxisItem()})
        area_pw  = pg.PlotWidget(axisItems={'bottom': pg.DateAxisItem()})
        for pw in (sigma_pw, area_pw):
            pw.setMinimumHeight(200)
            pw.getPlotItem().getAxis('left').enableAutoSIPrefix(False)
            lay.addWidget(pw)
        area_pw.setXLink(sigma_pw)

        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(
            ["Date", "Sample", "Instrument", "σ", "Mean single-ion area", "Masses", "Source"])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.setMinimumHeight(150)
        lay.addWidget(table)

        btn_row = QHBoxLayout()
        remove_btn = QPushButton("Remove selected")
        remove_btn.setIcon(qta.icon('fa6s.trash', color=theme.palette.danger))
        remove_btn.setToolTip("Delete the selected sessions from the history")
        export_btn = QPushButton("Export CSV")
        export_btn.setIcon(qta.icon('fa6s.file-csv', color="#2196F3"))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(remove_btn)
        btn_row.addWidget(export_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        current_key = None
        if self.is_sia_loaded():
            current_key = sia_stats.history_entry(
                self.single_ion_info, self.per_mass_distributions,
                self.single_ion_source_folder)['key']

        def _draw_series(pw, entries, field, title):
            """Draw one control chart.

            Args:
                pw (pg.PlotWidget): Target plot.
                entries (list[dict]): History records, oldest first.
                field (str): Record field to plot.
                title (str): Y-axis title.
            """
            p = theme.palette
            pw.clear()
            pw.setBackground(p.plot_bg)
            pi = pw.getPlotItem()
            fg = QColor(p.plot_fg)
            for name in ('left', 'bottom'):
                ax = pi.getAxis(name)
                ax.setPen(pg.mkPen(fg, width=1))
                ax.setTextPen(fg)
            pi.setLabel('left', title, color=p.plot_fg, **{'font-size': '11pt'})
            pts = [(sia_stats.parse_datetime(e.get('date')), e.get(field), e)
                   for e in entries]
            pts = [(d.timestamp(), v, e) for d, v, e in pts
                   if d is not None and v is not None and np.isfinite(v)]
            if not pts:
                return
            xs = np.array([x for x, _, _ in pts])
            ys = np.array([y for _, y, _ in pts])
            limits = sia_stats.control_limits(ys)
            if limits is not None:
                for pos, style, alpha in ((limits['mean'], Qt.SolidLine, 220),
                                          (limits['warn'][0], Qt.DashLine, 170),
                                          (limits['warn'][1], Qt.DashLine, 170),
                                          (limits['action'][0], Qt.DotLine, 170),
                                          (limits['action'][1], Qt.DotLine, 170)):
                    col = QColor(p.text_muted)
                    col.setAlpha(alpha)
                    pw.addItem(pg.InfiniteLine(pos=pos, angle=0,
                                               pen=pg.mkPen(col, width=1.5, style=style)))
            if len(xs) > 1:
                line_col = self._point_color(110)
                pw.plot(xs, ys, pen=pg.mkPen(line_col, width=1.5))
            colors = {'ok': self._point_color(), 'unknown': self._point_color(),
                      'warn': QColor(p.warning), 'action': QColor(p.danger)}
            spots = []
            for x, y, e in pts:
                status = sia_stats.classify(y, limits)
                col = colors[status]
                is_current = e.get('key') == current_key
                tip = (f"{e.get('date', '')[:16].replace('T', ' ')}\n"
                       f"{e.get('sample_name', '')}\n{title}: {y:.4g}")
                spots.append({
                    'pos': (x, y), 'size': 14 if is_current else 10, 'data': tip,
                    'pen': pg.mkPen(QColor(p.plot_fg) if is_current else col,
                                    width=2.5 if is_current else 1.5),
                    'brush': pg.mkBrush(col)})
            scatter = pg.ScatterPlotItem(hoverable=True, tip=lambda x, y, data: data)
            scatter.addPoints(spots)
            pw.addItem(scatter)
            pad = max(86400.0, (xs.max() - xs.min()) * 0.05)
            pw.setXRange(xs.min() - pad, xs.max() + pad, padding=0)

        def _fill():
            """Rebuild the summary, both charts and the table from the history."""
            p = theme.palette
            entries = hist.sorted_entries()
            n = len(entries)
            if n:
                first = entries[0].get('date', '')[:10]
                last = entries[-1].get('date', '')[:10]
                span = f"{first} to {last}" if first != last else first
            else:
                span = "no sessions yet"
            summary_lbl.setText(
                f'<div style="color:{p.text_secondary};font-weight:600;font-size:10pt;">'
                f'SIA history</div>'
                f'<div style="color:{p.text_primary};font-size:12pt;font-weight:600;">'
                f'{n} session{"s" if n != 1 else ""} · {span}</div>'
                f'<div style="color:{p.text_muted};font-size:9pt;">'
                f'Every SIA you load is added here. Lines show the mean, ±2 SD (dashed) '
                f'and ±3 SD (dotted) of all sessions; orange points are beyond 2 SD, '
                f'red beyond 3 SD. Limits need at least '
                f'{sia_stats.MIN_HISTORY_FOR_LIMITS} sessions.</div>')
            _draw_series(sigma_pw, entries, 'sigma', 'σ')
            _draw_series(area_pw, entries, 'average_single_ion_area', 'Mean single-ion area')
            table.setRowCount(0)
            for e in reversed(entries):
                row = table.rowCount()
                table.insertRow(row)
                values = [e.get('date', '')[:16].replace('T', ' '), e.get('sample_name', ''),
                          e.get('instrument', ''), f"{e.get('sigma', float('nan')):.4f}",
                          f"{e.get('average_single_ion_area', float('nan')):.4g}",
                          str(e.get('num_valid_masses', '')), e.get('source', '')]
                for col, text in enumerate(values):
                    item = QTableWidgetItem(text)
                    item.setData(Qt.UserRole, e.get('key'))
                    if col == 6:
                        item.setToolTip(text)
                    table.setItem(row, col, item)
            remove_btn.setEnabled(n > 0)
            export_btn.setEnabled(n > 0)

        def _remove():
            """Delete the selected sessions after confirmation."""
            keys = {table.item(i.row(), 0).data(Qt.UserRole)
                    for i in table.selectionModel().selectedRows()}
            if not keys:
                return
            ok = self._themed_msgbox(
                'question', dlg, "Remove Sessions",
                f"Remove {len(keys)} session{'s' if len(keys) != 1 else ''} from the SIA history?",
                buttons=QMessageBox.Yes | QMessageBox.No, default_button=QMessageBox.No)
            if ok != QMessageBox.Yes:
                return
            for key in keys:
                hist.remove(key)
            _fill()

        def _export():
            """Write the history to a CSV file."""
            path, _ = QFileDialog.getSaveFileName(
                dlg, "Export SIA History", "sia_history.csv",
                "CSV Files (*.csv);;All Files (*.*)")
            if not path:
                return
            try:
                with open(path, 'w', newline='', encoding='utf-8') as fh:
                    writer = csv.writer(fh)
                    writer.writerow(['date', 'date_from_file', 'sample_name', 'instrument',
                                     'sigma', 'average_single_ion_area', 'mean_signal',
                                     'num_valid_masses', 'source', 'recorded_at'])
                    for e in hist.sorted_entries():
                        writer.writerow([e.get('date', ''), e.get('date_from_file', ''),
                                         e.get('sample_name', ''), e.get('instrument', ''),
                                         e.get('sigma', ''), e.get('average_single_ion_area', ''),
                                         e.get('mean_signal', ''), e.get('num_valid_masses', ''),
                                         e.get('source', ''), e.get('recorded_at', '')])
            except OSError as exc:
                self._themed_msgbox('critical', dlg, "Export Error", f"Failed to export CSV: {exc}")

        remove_btn.clicked.connect(_remove)
        export_btn.clicked.connect(_export)
        dlg._sia_redraw = _fill
        _fill()
        for btn in dlg.findChildren(QPushButton):
            btn.setAutoDefault(False)
        dlg.show()
        return dlg

    @staticmethod
    def _calc_quantile(
        mean_signal : float,
        sigma       : float,
        avg_sia     : float,
        sig_vals    : np.ndarray,
        weights     : np.ndarray,
    ):
        """
        Compute the ``QUANTILE_TARGET`` quantile in normalised signal units.
        Tries the analytical lognormal formula first; falls back to an
        empirical estimate from the histogram if the formula fails.

        Args:
            mean_signal (float):      Weighted mean signal in raw ADC counts.
            sigma       (float):      Lognormal sigma parameter.
            avg_sia     (float):      Average single-ion area for normalisation.
            sig_vals    (np.ndarray): Normalised bin centre values.
            weights     (np.ndarray): Bin counts (need not be normalised).

        Returns:
            float | None: Quantile value in normalised units, or ``None`` if
                          both methods fail.
        """
        try:
            mu_adc = np.log(mean_signal) - 0.5 * sigma ** 2
            q_adc  = np.exp(mu_adc + np.sqrt(2.0 * sigma ** 2) *
                            erfinv(2.0 * QUANTILE_TARGET - 1.0))
            q = q_adc / avg_sia
            if np.isfinite(q) and q > 0:
                return q
        except (ArithmeticError, ValueError, FloatingPointError):
            _itk_log.exception("Handled exception in _calc_quantile")

        try:
            cw  = np.cumsum(weights)
            cw /= cw[-1]
            idx = np.searchsorted(cw, QUANTILE_TARGET)
            q   = sig_vals[min(idx, len(sig_vals) - 1)]
            if np.isfinite(q) and q > 0:
                return q
        except (ArithmeticError, ValueError, IndexError):
            _itk_log.exception("Handled exception in _calc_quantile")

        return None

    def _create_sigma_comparison_plot(self, info: dict) -> pg.PlotWidget:
        """
        Build the sigma-vs-mass scatter plot with mean and ±1 SD / ±2 SD
        reference lines, outlier colouring, and interactive click-to-select.

        Args:
            info (dict): ``single_ion_info`` dictionary (used only for the
                         widget factory; data comes from ``per_mass_distributions``).

        Returns:
            pg.PlotWidget: Sigma comparison plot widget.
        """
        pw = self._make_plot_widget('Sigma (σ)', 'Mass (m/z)')
        pw.getPlotItem().getAxis('left').enableAutoSIPrefix(False)
        self._update_sigma_comparison_plot(pw, exclude_outliers=self._exclude_outliers)
        return pw

    def _update_sigma_comparison_plot(self, pw: pg.PlotWidget,
                                      exclude_outliers: bool = False):
        """Redraw the sigma comparison scatter plot in place.

        Each mass is drawn with its standard error. The mean line is the
        mean weighted by event count, outliers are flagged with the
        modified z-score and shown in red, and a weighted straight line of σ
        against m/z is drawn with its slope and p-value. The ±2 SD label
        reports a Shapiro–Wilk test on the σ values.

        Args:
            pw               (pg.PlotWidget): Existing sigma plot widget.
            exclude_outliers (bool):          If ``True``, the mean, SD and
                                              trend leave the outliers out.
        """
        pw.clear()

        summary = sia_stats.summarize_per_mass(self.per_mass_distributions, exclude_outliers)
        if summary is None:
            return

        masses   = summary['masses']
        sigmas   = summary['sigmas']
        se       = summary['se']
        outliers = summary['outliers']
        mean_s   = summary['mean']
        sd_s     = summary['sd'] if np.isfinite(summary['sd']) else 0.0

        normality_label = "±2 SD"
        if len(sigmas) >= 8:
            try:
                _, sw_p = stats.shapiro(sigmas)
                if sw_p >= 0.05:
                    normality_label = "±2 SD (~95%)"
                else:
                    normality_label = f"±2 SD (Shapiro p={sw_p:.3f})"
            except Exception:
                _itk_log.exception("Handled exception in _update_sigma_comparison_plot")

        pal = theme.palette
        dark = pal.name == "dark"
        mean_col = QColor(pal.plot_fg)
        sd1_col = QColor(150, 150, 150)
        sd2_col = QColor(110, 110, 110) if dark else QColor(185, 185, 185)
        point_col = self._point_color()
        out_col = QColor(pal.danger)
        trend_col = QColor('#f5a623') if dark else QColor('#d9822b')
        for pos, style, col, w in [
            (mean_s,          Qt.SolidLine, mean_col, 2),
            (mean_s + sd_s,   Qt.DashLine,  sd1_col, 2),
            (mean_s - sd_s,   Qt.DashLine,  sd1_col, 2),
            (mean_s + 2*sd_s, Qt.DotLine,   sd2_col, 2),
            (mean_s - 2*sd_s, Qt.DotLine,   sd2_col, 2),
        ]:
            pw.addItem(pg.InfiniteLine(
                pos=pos, angle=0,
                pen=pg.mkPen(color=col, width=w, style=style)
            ))

        x_lo, x_hi = masses.min() * 0.99, masses.max() * 1.01
        trend = summary['trend']
        if trend is not None:
            xs = np.array([x_lo, x_hi])
            pw.plot(xs, trend['intercept'] + trend['slope'] * xs,
                    pen=pg.mkPen(color=trend_col, width=2, style=Qt.DashDotLine))

        has_se = np.isfinite(se)
        if has_se.any():
            err_col = QColor(point_col)
            err_col.setAlpha(150)
            pw.addItem(pg.ErrorBarItem(
                x=masses[has_se], y=sigmas[has_se],
                top=se[has_se], bottom=se[has_se], beam=0,
                pen=pg.mkPen(err_col, width=1.5)))

        tips = []
        for m, sg, e, n, out in zip(masses, sigmas, se, summary['n'], outliers):
            lines = [self.mass_label(m),
                     f"σ = {sg:.4f}" + (f" ± {e:.4f}" if np.isfinite(e) else ""),
                     f"{int(n):,} single-ion events"]
            if out:
                lines.append("Outlier")
            tips.append("\n".join(lines))

        def _tip(x, y, data):
            """Tooltip text for a hovered point.

            Args:
                x (float): Point x.
                y (float): Point y.
                data (str): Text stored with the point.
            """
            return data

        for mask, col, size in ((~outliers, point_col, 10), (outliers, out_col, 12)):
            idx = np.where(mask)[0]
            if not len(idx):
                continue
            scatter = pg.ScatterPlotItem(
                x=masses[idx], y=sigmas[idx], data=[tips[i] for i in idx],
                symbol='o', size=size, hoverable=True, tip=_tip,
                hoverSize=size + 4,
                pen=pg.mkPen(col, width=2),
                brush=pg.mkBrush(col.red(), col.green(), col.blue(), 170 if size == 10 else 190)
            )
            scatter.sigClicked.connect(lambda plot, pts: self._on_sigma_scatter_clicked(pts))
            pw.addItem(scatter)

        tnr = "font-family:Times New Roman;font-size:18pt;"

        def _txt(html: str, x: float, y: float, anchor=(0, 1)):
            """Add a TextItem at a given position.

            Args:
                html   (str):   HTML content for the label.
                x      (float): X position in data coordinates.
                y      (float): Y position in data coordinates.
                anchor (tuple): (horizontal, vertical) anchor fractions.
            """
            t = pg.TextItem(anchor=anchor, html=html)
            t.setPos(x, y)
            pw.addItem(t)

        lo_err = np.where(has_se, sigmas - np.nan_to_num(se), sigmas)
        hi_err = np.where(has_se, sigmas + np.nan_to_num(se), sigmas)
        y_lo = min(lo_err.min(), mean_s - 2*sd_s)
        y_hi = max(hi_err.max(), mean_s + 2*sd_s)
        span = max(y_hi - y_lo, 1e-9)
        y_lo -= 0.12 * span
        y_hi += 0.34 * span
        pw.setXRange(x_lo, x_hi, padding=0)
        pw.setYRange(y_lo, y_hi, padding=0)

        suffix = " (excl. outliers)" if summary['excluded'] else ""
        header = (f'<span style="color:{mean_col.name()};font-weight:bold;">'
                  f'Weighted mean σ = {mean_s:.3f}{suffix}</span>')
        if summary['n_outliers']:
            n_out = summary['n_outliers']
            header += (f'<span style="color:{out_col.name()};font-weight:bold;">'
                       f'&nbsp;&nbsp;·&nbsp;&nbsp;{n_out} outlier{"s" if n_out > 1 else ""} flagged</span>')
        if trend is not None:
            p = trend['p_value']
            p_txt = f"p = {p:.3f}" if np.isfinite(p) and p >= 0.001 else "p < 0.001"
            header += (f'<br/><span style="color:{trend_col.name()};font-size:15pt;">'
                       f'Trend: {trend["slope"] * 100:+.4f} σ per 100 m/z ({p_txt})</span>')
        _txt(f'<div style="{tnr}">{header}</div>', x_lo + 0.01 * (x_hi - x_lo), y_hi, (0, 0))
        _txt(f'<div style="{tnr}color:{sd1_col.name()};">+1 SD</div>',
             masses[-1], mean_s + sd_s, (1, 1))
        _txt(f'<div style="{tnr}color:{sd1_col.name()};">-1 SD</div>',
             masses[-1], mean_s - sd_s, (1, 0))
        _txt(f'<div style="{tnr}color:{pal.plot_fg};">{normality_label}</div>',
             masses[-1], mean_s + 2*sd_s, (1, 1))
        _txt(f'<div style="{tnr}color:{pal.plot_fg};">{normality_label}</div>',
             masses[-1], mean_s - 2*sd_s, (1, 0))

    def _on_sigma_scatter_clicked(self, points):
        """Handle a click on a point in the sigma scatter plot.
        Switches the view to show the clicked mass's individual distribution.

        Args:
            points (list): List of clicked SpotItem objects from pyqtgraph.
        """
        if not points or not hasattr(self, 'view_toggle'):
            return

        try:
            pt   = points[0]
            mass = pt.pos().x()

            best_key  = None
            best_diff = float('inf')
            for key, d in self.per_mass_distributions.items():
                diff = abs(d['mass'] - mass)
                if diff < best_diff:
                    best_diff = diff
                    best_key  = key

            if best_key is None:
                return

            self.view_toggle.setChecked(True)
            self.radio_distribution.setChecked(True)

            for i in range(self.mass_selector.count()):
                if self.mass_selector.itemData(i) == best_key:
                    self.mass_selector.setCurrentIndex(i)
                    break
        except Exception as e:
            _itk_log.exception("Handled exception in _on_sigma_scatter_clicked")
            _itk_log.error(f"Sigma scatter click handler error: {e}")

    # ── export functionality ──────────────────────────────────────────────────

    def _export_per_mass_csv(self, parent: QWidget):
        """Export per-mass sigma data to a CSV file via a save-file dialog.

        Columns: mass, isotopes, mean_signal, std_signal, sigma, sigma_se,
        num_points, outlier

        Args:
            parent (QWidget): Parent widget for the file dialog.
        """
        if not self.per_mass_distributions:
            self._themed_msgbox('warning', parent, "No Data", "No per-mass distributions to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            parent, "Export Per-Mass Sigma CSV",
            "per_mass_sigma.csv", "CSV Files (*.csv);;All Files (*.*)"
        )
        if not path:
            return

        try:
            summary = sia_stats.summarize_per_mass(self.per_mass_distributions)
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'mass', 'isotopes', 'mean_signal', 'std_signal', 'sigma',
                    'sigma_se', 'num_points', 'outlier'
                ])
                for i, key in enumerate(summary['keys']):
                    r = self.per_mass_distributions[key]
                    se = summary['se'][i]
                    writer.writerow([
                        f"{r['mass']:.4f}",
                        self.isotope_text(r['mass']),
                        f"{r['mean_signal']:.4f}",
                        f"{r['std_signal']:.4f}",
                        f"{r['sigma']:.4f}",
                        f"{se:.4f}" if np.isfinite(se) else "",
                        r['num_points'],
                        "yes" if summary['outliers'][i] else "no",
                    ])

            self._themed_msgbox('information', parent, "Export Complete", f"Per-mass sigma data exported to:\n{path}")
        except Exception as e:
            _itk_log.exception("Handled exception in _export_per_mass_csv")
            self._themed_msgbox('critical', parent, "Export Error", f"Failed to export CSV: {e}")

    def _export_plot(self, pw: pg.PlotWidget, parent: QWidget):
        """Export a PlotWidget to SVG or PNG via a save-file dialog.

        Args:
            pw     (pg.PlotWidget): The plot widget to export.
            parent (QWidget):       Parent widget for the file dialog.
        """
        path, selected_filter = QFileDialog.getSaveFileName(
            parent, "Export Plot",
            "sia_plot.svg",
            "SVG Files (*.svg);;PNG Files (*.png);;All Files (*.*)"
        )
        if not path:
            return

        try:
            import pyqtgraph.exporters as exporters

            if path.lower().endswith('.png'):
                exporter = exporters.ImageExporter(pw.getPlotItem())
                exporter.parameters()['width'] = 1600
            else:
                exporter = exporters.SVGExporter(pw.getPlotItem())

            exporter.export(path)
            self._themed_msgbox('information', parent, "Export Complete", f"Plot exported to:\n{path}")
        except Exception as e:
            _itk_log.exception("Handled exception in _export_plot")
            self._themed_msgbox('critical', parent, "Export Error", f"Failed to export plot: {e}")

    # ── per-mass sigma assignment ─────────────────────────────────────────────

    def _assign_per_mass_sigma(self, quiet: bool = False):
        """Assign each element's sigma from its closest per-mass SIA.

        An element takes the σ of the nearest per-mass distribution within
        ``sia_stats.MASS_MATCH_TOL`` m/z. It gets the σ in use instead (see
        :meth:`get_effective_sigma`) when no mass is close enough, or when
        the closest mass is an outlier and outliers are excluded.

        Updates the ``sample_parameters`` dict on the main window and
        refreshes the parameters table.

        Args:
            quiet (bool): Skip the message boxes.
        """
        if not self.per_mass_distributions:
            if not quiet:
                self._themed_msgbox('warning', self.main_window, "No Per-Mass Data", "No per-mass distributions available for assignment.")
            return

        if not hasattr(self.main_window, 'sample_parameters'):
            if not quiet:
                self._themed_msgbox('warning', self.main_window, "No Samples", "No samples loaded to assign sigma values to.")
            return

        summary      = sia_stats.summarize_per_mass(self.per_mass_distributions, self._exclude_outliers)
        outlier_keys = {k for k, o in zip(summary['keys'], summary['outliers']) if o}
        global_sigma = self.get_effective_sigma()
        assigned     = 0
        fallback     = 0

        for sample in self.main_window.sample_parameters.values():
            for el_name, el_params in sample.items():
                try:
                    target_mass = float(el_name.split('-')[1])
                except (ValueError, IndexError):
                    _itk_log.exception("Handled exception in _assign_per_mass_sigma")
                    target_mass = None

                match = None
                if target_mass is not None:
                    match = sia_stats.nearest_per_mass(self.per_mass_distributions, target_mass)
                if match is not None and self._exclude_outliers and match[0] in outlier_keys:
                    match = None

                if match is None:
                    el_params['sigma']           = global_sigma
                    el_params['_sigma_from_sia'] = False
                    fallback += 1
                else:
                    el_params['sigma']           = float(match[1]['sigma'])
                    el_params['_sigma_from_sia'] = True
                    assigned += 1

        if hasattr(self.main_window, 'parameters_table'):
            self.main_window.update_parameters_table()

        if quiet:
            return

        msg = QMessageBox(self.main_window)
        msg.setWindowTitle("Per-Mass σ Assigned")
        msg.setText(
            f"Assigned per-mass σ to {assigned} element(s).\n"
            f"Fell back to global σ ({global_sigma:.3f}) for {fallback} element(s)."
        )
        msg.setIcon(QMessageBox.Information)
        msg.setStyleSheet(dialog_qss(theme.palette))
        msg.exec()

    # ── overlay helpers ───────────────────────────────────────────────────────

    def _clear_overlay(self, dialog: QDialog):
        """Clear the overlay SIA data and refresh the current dialog view.

        Args:
            dialog (QDialog): The parent SIA info dialog to refresh.
        """
        self._overlay_info              = None
        self._overlay_per_mass          = {}
        self._overlay_distribution_data = None

        self.main_window.status_label.setText("Overlay SIA cleared.")

        if hasattr(self, '_plot_overall') and self._plot_overall.isVisible():
            self._update_sia_plot(
                self._plot_overall, self.single_ion_info, None
            )

    # ── clear ─────────────────────────────────────────────────────────────────

    def clear_single_ion_distribution(self):
        """Prompt the user to confirm, then clear all SIA data and reset sigma.

        Args:
            None
        """
        if self._is_processing:
            self._themed_msgbox('information', self.main_window, "Processing in Progress", "Cannot clear SIA while processing.")
            return

        confirm = self._themed_msgbox(
            'question', self.main_window, "Clear Single-Ion Distribution",
            f"Are you sure you want to clear the loaded single-ion distribution?\n\n"
            f"This will reset σ to default value ({DEFAULT_SIGMA})",
            buttons=QMessageBox.Yes | QMessageBox.No,
            default_button=QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        self._clear_sia_data()
        self._update_ui_after_clear()
        self._themed_msgbox('information', self.main_window, "Cleared", f"Single-ion distribution cleared.\n\nσ reset to {DEFAULT_SIGMA}")

    def _clear_sia_data(self):
        """Reset all stored SIA data (primary and overlay) and restore sigma to
        ``DEFAULT_SIGMA`` for every sample/element in the parameters table.

        Args:
            None
        """
        self.single_ion_distribution_data = None
        self.single_ion_source_folder     = None
        self.single_ion_info              = {}
        self.per_mass_distributions       = {}
        self._exclude_outliers            = False

        self._overlay_info              = None
        self._overlay_per_mass          = {}
        self._overlay_distribution_data = None

        for sample in getattr(self.main_window, 'sample_parameters', {}).values():
            for el in sample.values():
                el['sigma'] = DEFAULT_SIGMA
                el['_sigma_from_sia'] = False

        self._apply_sigma(DEFAULT_SIGMA)

        if hasattr(self.main_window, 'parameters_table'):
            self.main_window.update_parameters_table()

    def _update_ui_after_clear(self):
        """Disable info/clear buttons and reset the upload button style after clear.

        Args:
            None
        """
        self.info_sid_button.setEnabled(False)
        self.clear_sid_button.setEnabled(False)
        self._style_upload_button(False)
        self.main_window.status_label.setText(f"SIA cleared. σ reset to {DEFAULT_SIGMA}")

    # ── public API ────────────────────────────────────────────────────────────

    def is_sia_loaded(self) -> bool:
        """
        Check whether a single-ion distribution is currently loaded.

        Args:
            None

        Returns:
            bool: ``True`` if distribution data is loaded, ``False`` otherwise.
        """
        return self.single_ion_distribution_data is not None

    def get_sia_info(self) -> dict:
        """
        Return a copy of the current SIA info dictionary.

        Args:
            None

        Returns:
            dict: Copy of ``single_ion_info``, or an empty dict if not loaded.
        """
        return self.single_ion_info.copy() if self.single_ion_info else {}

    def get_calculated_sigma(self) -> float:
        """
        Return the sigma value derived from the loaded SIA.

        Args:
            None

        Returns:
            float: Calculated sigma, or ``DEFAULT_SIGMA`` if no SIA is loaded.
        """
        return self.single_ion_info.get('calculated_sigma', DEFAULT_SIGMA)

    def get_per_mass_sigma(self, target_mass: float,
                           tolerance: float = sia_stats.MASS_MATCH_TOL) -> float:
        """
        Look up the per-mass sigma for a given target mass.
        Falls back to the sigma in use (see :meth:`get_effective_sigma`)
        when no per-mass distribution lies within ``tolerance`` m/z, or when
        the closest one is an excluded outlier.

        Args:
            target_mass (float): Target mass in amu (m/z).
            tolerance   (float): Maximum mass difference to accept a match.

        Returns:
            float: Per-mass sigma if a match exists, otherwise the sigma in
                   use or ``DEFAULT_SIGMA``.
        """
        match = sia_stats.nearest_per_mass(self.per_mass_distributions, target_mass, tolerance)
        if match is None:
            return self.get_effective_sigma()
        if self._exclude_outliers:
            summary = sia_stats.summarize_per_mass(self.per_mass_distributions, True)
            if match[0] in {k for k, o in zip(summary['keys'], summary['outliers']) if o}:
                return self.get_effective_sigma()
        return float(match[1]['sigma'])

    def is_overlay_loaded(self) -> bool:
        """
        Check whether overlay SIA data is loaded.

        Args:
            None

        Returns:
            bool: ``True`` if overlay data is loaded, ``False`` otherwise.
        """
        return self._overlay_info is not None

    def stop_processing(self):
        """Request the background worker to stop and reset the UI.

        Args:
            None
        """
        if self._is_processing and self.sia_worker:
            self.sia_worker.stop_processing()
            self._reset_processing_state()

    def cleanup(self):
        """Gracefully stop the worker thread and release all references.
        Should be called when the parent window is closing.

        Args:
            None
        """
        if self.sia_thread and self.sia_thread.isRunning():
            if self.sia_worker:
                self.sia_worker.stop_processing()
            self.sia_thread.quit()
            self.sia_thread.wait(3000)

        if self.sia_worker is not None:
            for sig in (
                self.sia_worker.finished,
                self.sia_worker.error,
                self.sia_worker.progress,
                self.sia_worker.status_update,
            ):
                try:
                    sig.disconnect()
                except RuntimeError:
                    _itk_log.exception("Handled exception in cleanup")

        try:
            theme.themeChanged.disconnect(self._on_theme_changed)
        except RuntimeError:
            _itk_log.exception("Handled exception in cleanup")

        self.sia_thread     = None
        self.sia_worker     = None
        self._is_processing = False