import csv
import numpy as np
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QFileDialog, QMessageBox,
                               QRadioButton, QButtonGroup, QComboBox,
                               QCheckBox, QSplitter, QWidget)
from PySide6.QtCore import Qt, QThread, QObject, Signal, Slot
from PySide6.QtGui import QFont, QPen, QColor
import pyqtgraph as pg
import qtawesome as qta
from scipy import stats
from scipy.special import gammainc
import traceback

import loading.vitesse_loading
import loading.tofwerk_loading
from processing.peak_detection import erf, erfinv

from theme import theme, dialog_qss


# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_SIGMA    = 0.55
POI2_LOW         = 1e-5
POI2_HIGH        = 1e-3
QUANTILE_TARGET  = 0.9999
PER_MASS_MIN_PTS = 10
PER_MASS_BINS    = 50      
OUTLIER_SD_MULT  = 2.0     

_QQ_POINT_COLOR  = QColor(65, 105, 225, 180)  
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
        """
        Initialise the SIA worker.

        Args:
            None

        Returns:
            None
        """
        super().__init__()
        self._should_stop = False

    # ── public slots ──────────────────────────────────────────────────────────

    @Slot(str, str)
    def process_sia_data(self, data_path: str, file_type: str = "nu"):
        """
        Entry point — dispatch to the correct instrument handler.

        Args:
            data_path (str): Path to a Nu Vitesse folder or TOFWERK .h5 file.
            file_type (str): Instrument type — ``'nu'`` or ``'tofwerk'``.

        Returns:
            None
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
            self.error.emit(f"Error processing single-ion distribution: {e}")
            print(f"SIAWorker error:\n{traceback.format_exc()}")

    @Slot()
    def stop_processing(self):
        """
        Request cancellation of the current processing run.

        Args:
            None

        Returns:
            None
        """
        self._should_stop = True

    # ── Nu Vitesse ────────────────────────────────────────────────────────────

    def _process_nu(self, path: Path):
        """
        Load and process a Nu Vitesse data folder.

        Args:
            path (Path): Path to the Nu Vitesse folder containing ``run.info``.

        Returns:
            None
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
        """
        Load and process a TOFWERK .h5 file.

        Args:
            path (Path): Path to the TOFWERK HDF5 file.

        Returns:
            None
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
            except Exception as e:
                print(f"Warning: failed to process mass {masses[i]}: {e}")

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
        """
        Emit progress and status signals together.

        Args:
            pct (int): Progress percentage (0–100).
            msg (str): Status message string.

        Returns:
            None
        """
        self.progress.emit(pct)
        self.status_update.emit(msg)


# ─── Manager ──────────────────────────────────────────────────────────────────

class SingleIonDistributionManager(QObject):
    """Unified SIA Manager — Nu Vitesse + TOFWERK."""

    def __init__(self, main_window):
        """
        Initialise the SIA manager.

        Args:
            main_window (object): Reference to the application main window.

        Returns:
            None
        """
        super().__init__(main_window)
        self.main_window = main_window

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

        self._current_qq_mass_key = None

        self._live_dialogs = []

        theme.themeChanged.connect(self._on_theme_changed)


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
        Returns:
            object: Result of the operation.
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
        """
        Restyle owned widgets and any live dialogs when the theme changes.
        Args:
            _name (str): The  name.
        """
        if self.upload_sid_button is not None:
            if self.is_sia_loaded():
                self.upload_sid_button.setStyleSheet(self._loaded_button_qss())
            else:
                self.upload_sid_button.setStyleSheet("")

        if hasattr(self, 'view_toggle') and self.view_toggle is not None:
            try:
                self.view_toggle.setStyleSheet(
                    f"font-weight: bold; font-size: 12pt; "
                    f"color: {theme.palette.text_primary};"
                )
            except RuntimeError:
                self.view_toggle = None

        alive = []
        for dlg in self._live_dialogs:
            try:
                dlg.setStyleSheet(dialog_qss(theme.palette))
                for btn in dlg.findChildren(QPushButton):
                    if btn.property("_sia_close_btn"):
                        btn.setStyleSheet(self._close_button_qss())
                for lbl in dlg.findChildren(QLabel):
                    if lbl.property("_sia_info_html"):
                        info = lbl.property("_sia_info_data")
                        if info is not None:
                            lbl.setText(self._create_info_html(info))
                for pw in dlg.findChildren(pg.PlotWidget):
                    self._restyle_plot_widget(pw)
                alive.append(dlg)
            except RuntimeError:
                continue
        self._live_dialogs = alive

    @staticmethod
    def _loaded_button_qss() -> str:
        """QSS for the upload button once a SIA has been loaded.
        Returns:
            str: Result of the operation.
        """
        p = theme.palette
        return f"""
            QPushButton {{
                background-color: {p.success};
                border: 2px solid {p.success};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {p.accent_hover};
            }}
        """

    @staticmethod
    def _close_button_qss() -> str:
        """QSS for the Close buttons in SIA dialogs.
        Returns:
            str: Result of the operation.
        """
        p = theme.palette
        return f"""
            QPushButton {{
                background-color: {p.bg_tertiary};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {p.bg_hover};
                border: 1px solid {p.accent};
            }}
        """

    @staticmethod
    def _restyle_plot_widget(pw):
        """Re-apply plot background and axis colors from the active palette.
        Args:
            pw (Any): The pw.
        """
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
            pass

    def _register_dialog(self, dialog):
        """Track a dialog so it gets restyled on theme change.
        Args:
            dialog (Any): Parent or target dialog.
        """
        self._live_dialogs.append(dialog)
        dialog.destroyed.connect(
            lambda _=None, d=dialog: self._live_dialogs.remove(d)
            if d in self._live_dialogs else None
        )

    # ── UI buttons ────────────────────────────────────────────────────────────

    def create_sia_buttons(self, parent_layout):
        """
        Create and add the three SIA control buttons to a layout.

        Args:
            parent_layout (QLayout): Layout to which the buttons are added.

        Returns:
            None
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

    # ── upload flow ───────────────────────────────────────────────────────────

    def upload_single_ion_distribution(self):
        """
        Prompt the user to choose an instrument type, then open the
        appropriate file/folder picker and start background processing.

        Args:
            None

        Returns:
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
        """
        Load a second SIA dataset for overlay comparison.
        Follows the same instrument-selection flow but stores results
        in the overlay slots instead of the primary ones.

        Args:
            None

        Returns:
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
        """
        Spawn a QThread, move a SIAWorker onto it, and start processing.

        Args:
            data_path (str): Path to the Nu Vitesse folder or TOFWERK .h5 file.
            file_type (str): ``'nu'`` or ``'tofwerk'``.

        Returns:
            None
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
            self._reset_processing_state()
            msg = f"Error starting SIA thread: {e}"
            self.main_window.status_label.setText(msg)
            self._themed_msgbox('critical', self.main_window, "Thread Error", msg)

    # ── thread callbacks ──────────────────────────────────────────────────────

    def _on_progress(self, value: int):
        """
        Forward a progress value to the main-window progress bar.

        Args:
            value (int): Progress percentage (0–100).

        Returns:
            None
        """
        self.main_window.progress_bar.setValue(value)

    def _on_status(self, text: str):
        """
        Forward a status string to the main-window status label.

        Args:
            text (str): Status message to display.

        Returns:
            None
        """
        self.main_window.status_label.setText(text)

    def _on_finished(self, result: dict):
        """
        Store results, update UI, and notify the user on successful processing.
        Routes to overlay storage if ``_loading_overlay`` is True.

        Args:
            result (dict): Result dictionary emitted by SIAWorker.finished.

        Returns:
            None
        """
        try:
            if self._loading_overlay:
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

                self._update_ui_after_load()
                self._apply_sia_to_all_samples()
                self._show_success_message()

                info = self.single_ion_info
                self.main_window.status_label.setText(
                    f"SIA loaded from {info['instrument_type']}: {info['sample_name']}, "
                    f"σ = {info['calculated_sigma']:.3f}"
                )
        except Exception as e:
            msg = f"Error processing SIA results: {e}"
            self.main_window.status_label.setText(msg)
            self._themed_msgbox('critical', self.main_window, "Results Error", msg)
        finally:
            self._reset_processing_state()

    def _on_error(self, msg: str):
        """
        Handle a processing error emitted by the worker.

        Args:
            msg (str): Human-readable error message.

        Returns:
            None
        """
        self._loading_overlay = False
        self._reset_processing_state()
        self.main_window.status_label.setText(f"SIA Error: {msg}")
        self._themed_msgbox('critical', self.main_window, "SIA Processing Error", msg)

    def _on_thread_cleanup(self):
        """
        Nullify thread and worker references after the thread has finished.

        Args:
            None

        Returns:
            None
        """
        self.sia_thread = None
        self.sia_worker = None

    def _reset_processing_state(self):
        """
        Restore the upload button and hide the progress bar.

        Args:
            None

        Returns:
            None
        """
        self._is_processing = False
        self.upload_sid_button.setEnabled(True)
        self.upload_sid_button.setText("")
        self.main_window.progress_bar.setVisible(False)

    # ── post-load UI helpers ──────────────────────────────────────────────────

    def _update_ui_after_load(self):
        """
        Update sigma spinbox and button states after a successful SIA load.
        Uses ``blockSignals`` to avoid triggering spurious valueChanged
        callbacks (fix #8).

        Args:
            None

        Returns:
            None
        """
        if hasattr(self.main_window, 'sigma_spinbox'):
            sb = self.main_window.sigma_spinbox
            sb.blockSignals(True)
            sb.setValue(self.single_ion_info['calculated_sigma'])
            sb.blockSignals(False)

        self.info_sid_button.setEnabled(True)
        self.clear_sid_button.setEnabled(True)
        self.upload_sid_button.setStyleSheet(self._loaded_button_qss())

    def _apply_sia_to_all_samples(self):
        """
        Trigger a parameters-table refresh so all samples reflect the new SIA.

        Args:
            None

        Returns:
            None
        """
        if hasattr(self.main_window, 'parameters_table'):
            self.main_window.update_parameters_table()

    def _show_success_message(self):
        """
        Display a QMessageBox summarising the loaded SIA.

        Args:
            None

        Returns:
            None
        """
        info = self.single_ion_info

        self._themed_msgbox(
            'information', self.main_window, "Success",
            f"Single-ion distribution loaded successfully!\n\n"
            f"Instrument: {info['instrument_type']}\n"
            f"Source: {info['sample_name']}\n"
            f"Distribution points: {info['distribution_points']}\n"
            f"Calculated σ: {info['calculated_sigma']:.3f}\n"
            f"Mean signal: {info['mean_signal']:.1f} counts\n\n"
            f"Applied real single-ion distribution to analysis"
        )

    # ── info dialog ───────────────────────────────────────────────────────────

    def show_single_ion_info(self):
        """
        Open the SIA information dialog with plot and optional per-mass
        controls, export buttons, overlay toggle, and outlier exclusion.

        Args:
            None

        Returns:
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

        lbl = QLabel(self._create_info_html(info))
        lbl.setTextFormat(Qt.RichText)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignTop)
        lbl.setMaximumHeight(240)
        lbl.setProperty("_sia_info_html", True)
        lbl.setProperty("_sia_info_data", info)
        layout.addWidget(lbl)

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
            self.view_toggle.setStyleSheet(
                f"font-weight: bold; font-size: 12pt; "
                f"color: {theme.palette.text_primary};"
            )
            ctrl.addWidget(self.view_toggle)

            self.mass_selector = QComboBox()
            self.mass_selector.setEnabled(False)
            self.mass_selector.setMinimumWidth(200)

            _mw_iso_map = {}
            if hasattr(self.main_window, 'selected_isotopes'):
                for _el, _isos in self.main_window.selected_isotopes.items():
                    for _iso_mass in _isos:
                        _mw_iso_map[float(_iso_mass)] = _el

            _MATCH_TOL = 2

            for mass_val, mass_key in sorted(
                (d['mass'], k) for k, d in self.per_mass_distributions.items()
            ):
                label = f"m/z {mass_val:.4f}"
                if _mw_iso_map:
                    _best_mw = min(_mw_iso_map, key=lambda m: abs(m - mass_val))
                    _diff = abs(_best_mw - mass_val)
                    if _diff <= _MATCH_TOL:
                        label += f"  →  {_mw_iso_map[_best_mw]}-{_best_mw:.0f}  (Δ {_diff:.3f})"
                self.mass_selector.addItem(label, mass_key)

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
            self.outlier_checkbox.setEnabled(False)
            self.outlier_checkbox.setToolTip(
                f"Recompute global σ excluding masses beyond ±{OUTLIER_SD_MULT} SD"
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
            """
            Determine which plot widget is currently visible and export it.

            Args:
                None

            Returns:
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
                """
                Refresh the visible plot based on current toggle/selector state.

                Args:
                    None

                Returns:
                    None
                """
                if self.view_toggle.isChecked():
                    self.mass_selector.setEnabled(True)
                    self.radio_distribution.setEnabled(True)
                    self.radio_sigma_compare.setEnabled(True)
                    self.outlier_checkbox.setEnabled(
                        self.radio_sigma_compare.isChecked()
                    )

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
                    self.outlier_checkbox.setEnabled(False)
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
            self.outlier_checkbox.stateChanged.connect(
                lambda: _refresh() if (
                    self.view_toggle.isChecked() and
                    self.radio_sigma_compare.isChecked()
                ) else None
            )

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        close_btn.setProperty("_sia_close_btn", True)
        close_btn.setStyleSheet(self._close_button_qss())
        layout.addWidget(close_btn)
        dialog.show()

    # ── plot helpers ──────────────────────────────────────────────────────────

    def _create_info_html(self, info: dict) -> str:
        """
        Build an HTML string for the information table in the dialog.

        Args:
            info (dict): ``single_ion_info`` dictionary.

        Returns:
            str: HTML-formatted table string.
        """
        p = theme.palette
        return f"""
        <h3 style="color:{p.text_primary};">Single-Ion Distribution Information</h3>
        <table style="width:100%;border-collapse:collapse;color:{p.text_primary};">
          <tr style="background-color:{p.bg_tertiary};">
            <td style="padding:8px;border:1px solid {p.border};"><b>Sample Name:</b></td>
            <td style="padding:8px;border:1px solid {p.border};">{info['sample_name']}</td>
          </tr>
          <tr style="background-color:{p.bg_secondary};">
            <td style="padding:8px;border:1px solid {p.border};"><b>Calculated σ (SIA):</b></td>
            <td style="padding:8px;border:1px solid {p.border};"><b>{info['calculated_sigma']:.3f}</b></td>
          </tr>
          <tr style="background-color:{p.bg_tertiary};">
            <td style="padding:8px;border:1px solid {p.border};"><b>Distribution Points:</b></td>
            <td style="padding:8px;border:1px solid {p.border};">{info['distribution_points']}</td>
          </tr>
          <tr style="background-color:{p.bg_secondary};">
            <td style="padding:8px;border:1px solid {p.border};"><b>Mean Signal:</b></td>
            <td style="padding:8px;border:1px solid {p.border};">{info['mean_signal']:.1f} counts</td>
          </tr>
        </table>
        """

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
        """
        Redraw a SIA distribution plot in place without recreating the widget.
        Called on every mass-selector or toggle change.

        Now includes overlay support: if overlay data is loaded, draws the
        overlay distribution in a semi-transparent blue behind the primary.

        Args:
            pw       (pg.PlotWidget): Existing plot widget to update.
            info     (dict):          ``single_ion_info`` dictionary.
            mass_key (str | None):    Key into ``per_mass_distributions``, or
                                      ``None`` for the overall distribution.

        Returns:
            None
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
                pass

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
            print(f"Lognormal fit failed: {e}")

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

        s_txt = pg.TextItem(
            anchor=(0, 1),
            html=f'<div style="font-size:20pt;font-family:Times New Roman;'
                 f'font-weight:bold;color:{theme.palette.plot_fg};">σ = {calc_sigma:.2f}</div>'
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
        """
        Draw a Q-Q plot: theoretical lognormal quantiles on x,
        observed quantiles on y.  Points on the diagonal = model fits.

        Args:
            pw       (pg.PlotWidget): Existing plot widget to update.
            info     (dict):          ``single_ion_info`` dictionary.
            mass_key (str | None):    Key into ``per_mass_distributions``, or
                                      ``None`` for the overall distribution.

        Returns:
            None
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
                pen=pg.mkPen(_QQ_POINT_COLOR.darker(120), width=1),
                brush=pg.mkBrush(_QQ_POINT_COLOR),
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
            t = pg.TextItem(anchor=(0.5, 0.5),
                            html=self._annot(f'Q-Q plot unavailable: {e}'))
            t.setPos(0.5, 0.5)
            pw.addItem(t)

    def _show_qq_dialog(self, info: dict, parent: QWidget):
        """
        Open a separate dialog showing a lognormal Q-Q plot for the
        currently visible distribution (overall or per-mass).

        The plot shows theoretical lognormal quantiles on the X-axis and
        observed quantiles on the Y-axis, with a 1:1 diagonal reference
        line and σ annotation.

        Args:
            info   (dict):    ``single_ion_info`` dictionary.
            parent (QWidget): Parent widget for the dialog.

        Returns:
            None
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
        close_btn.setProperty("_sia_close_btn", True)
        close_btn.setStyleSheet(self._close_button_qss())
        btn_row.addWidget(close_btn)

        lay.addLayout(btn_row)
        dlg.show()

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
        except Exception:
            pass

        try:
            cw  = np.cumsum(weights)
            cw /= cw[-1]
            idx = np.searchsorted(cw, QUANTILE_TARGET)
            q   = sig_vals[min(idx, len(sig_vals) - 1)]
            if np.isfinite(q) and q > 0:
                return q
        except Exception:
            pass

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
        self._update_sigma_comparison_plot(pw, exclude_outliers=False)
        return pw

    def _update_sigma_comparison_plot(self, pw: pg.PlotWidget,
                                      exclude_outliers: bool = False):
        """
        Redraw the sigma comparison scatter plot in place.
        Flags outliers in red and optionally recomputes global σ without them.
        Applies Shapiro–Wilk normality test to label ±2 SD lines correctly.

        Args:
            pw               (pg.PlotWidget): Existing sigma plot widget.
            exclude_outliers (bool):          If ``True``, recompute the mean σ
                                              excluding outlier masses.

        Returns:
            None
        """
        pw.clear()

        if not self.per_mass_distributions:
            return

        items  = sorted(
            (d['mass'], d['sigma'])
            for d in self.per_mass_distributions.values()
        )
        masses, sigmas = map(np.array, zip(*items))
        mean_s, std_s  = sigmas.mean(), sigmas.std()

        # ── outlier mask ──────────────────────────────────────────────────
        outlier_mask = np.abs(sigmas - mean_s) > OUTLIER_SD_MULT * std_s

        if exclude_outliers and outlier_mask.any():
            inliers    = sigmas[~outlier_mask]
            mean_s_eff = inliers.mean()
            std_s_eff  = inliers.std()
        else:
            mean_s_eff = mean_s
            std_s_eff  = std_s

        # ── Shapiro–Wilk normality test ───────────────────────────────────
        normality_label = "±2 SD"
        if len(sigmas) >= 8:
            try:
                _, sw_p = stats.shapiro(sigmas)
                if sw_p >= 0.05:
                    normality_label = "±2 SD (~95%)"
                else:
                    normality_label = f"±2 SD (Shapiro p={sw_p:.3f})"
            except Exception:
                pass

        # ── reference lines ───────────────────────────────────────────────
        for pos, style, col, w in [
            (mean_s_eff,             Qt.SolidLine, (100, 100, 100), 2),
            (mean_s_eff + std_s_eff, Qt.DashLine,  (128, 128, 128), 2),
            (mean_s_eff - std_s_eff, Qt.DashLine,  (128, 128, 128), 2),
            (mean_s_eff + 2*std_s_eff, Qt.DotLine, (180, 180, 180), 2),
            (mean_s_eff - 2*std_s_eff, Qt.DotLine, (180, 180, 180), 2),
        ]:
            pw.addItem(pg.InfiniteLine(
                pos=pos, angle=0,
                pen=pg.mkPen(color=col, width=w, style=style)
            ))

        # ── scatter points: inliers blue, outliers red ────────────────────
        inlier_idx  = np.where(~outlier_mask)[0]
        outlier_idx = np.where(outlier_mask)[0]

        scatter_inlier = pg.ScatterPlotItem(
            x=masses[inlier_idx], y=sigmas[inlier_idx],
            symbol='o', size=10,
            pen=pg.mkPen('b', width=2),
            brush=pg.mkBrush(65, 105, 225, 200)
        )
        pw.addItem(scatter_inlier)

        if len(outlier_idx) > 0:
            scatter_outlier = pg.ScatterPlotItem(
                x=masses[outlier_idx], y=sigmas[outlier_idx],
                symbol='o', size=12,
                pen=pg.mkPen('r', width=2),
                brush=pg.mkBrush(244, 67, 54, 200)
            )
            pw.addItem(scatter_outlier)

            scatter_outlier.sigClicked.connect(
                lambda plot, pts: self._on_sigma_scatter_clicked(pts)
            )

        scatter_inlier.sigClicked.connect(
            lambda plot, pts: self._on_sigma_scatter_clicked(pts)
        )

        # ── labels ────────────────────────────────────────────────────────
        tnr = "font-family:Times New Roman;font-size:18pt;"

        def _txt(html: str, x: float, y: float, anchor=(0, 1)):
            """
            Add a TextItem at a given position.

            Args:
                html   (str):   HTML content for the label.
                x      (float): X position in data coordinates.
                y      (float): Y position in data coordinates.
                anchor (tuple): (horizontal, vertical) anchor fractions.

            Returns:
                None
            """
            t = pg.TextItem(anchor=anchor, html=html)
            t.setPos(x, y)
            pw.addItem(t)

        suffix = " (excl. outliers)" if exclude_outliers and outlier_mask.any() else ""
        _txt(f'<div style="{tnr}font-weight:bold;color:rgb(100,100,100);">'
             f'Mean σ = {mean_s_eff:.3f}{suffix}</div>',
             masses[0], mean_s_eff * 1.02, (0, 2))
        _txt(f'<div style="{tnr}color:rgb(128,128,128);">+1 SD</div>',
             masses[-1], mean_s_eff + std_s_eff, (1, 1))
        _txt(f'<div style="{tnr}color:rgb(128,128,128);">-1 SD</div>',
             masses[-1], mean_s_eff - std_s_eff, (1, 0))
        _txt(f'<div style="{tnr}color:{theme.palette.plot_fg};">{normality_label}</div>',
             masses[-1], mean_s_eff + 2*std_s_eff, (1, 1))
        _txt(f'<div style="{tnr}color:{theme.palette.plot_fg};">{normality_label}</div>',
             masses[-1], mean_s_eff - 2*std_s_eff, (1, 0))

        if outlier_mask.any():
            n_out = outlier_mask.sum()
            _txt(f'<div style="{tnr}color:red;font-weight:bold;">'
                 f'{n_out} outlier{"s" if n_out > 1 else ""} flagged</div>',
                 masses[0], (mean_s_eff + 2*std_s_eff) * 1.05, (0, 0))

        pw.setXRange(masses.min() * 0.99, masses.max() * 1.01, padding=0)
        y_lo = min(sigmas.min(), mean_s_eff - 2*std_s_eff) * 0.9
        y_hi = max(sigmas.max(), mean_s_eff + 2*std_s_eff) * 1.1
        pw.setYRange(y_lo, y_hi, padding=0)

        self._exclude_outliers = exclude_outliers
        if exclude_outliers and outlier_mask.any():
            self._effective_sigma = mean_s_eff
        else:
            self._effective_sigma = mean_s

    def _on_sigma_scatter_clicked(self, points):
        """
        Handle a click on a point in the sigma scatter plot.
        Switches the view to show the clicked mass's individual distribution.

        Args:
            points (list): List of clicked SpotItem objects from pyqtgraph.

        Returns:
            None
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
            print(f"Sigma scatter click handler error: {e}")

    # ── export functionality ──────────────────────────────────────────────────

    def _export_per_mass_csv(self, parent: QWidget):
        """
        Export per-mass sigma data to a CSV file via a save-file dialog.

        Columns: mass, mean_signal, std_signal, sigma, num_points

        Args:
            parent (QWidget): Parent widget for the file dialog.

        Returns:
            None
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
            rows = sorted(
                self.per_mass_distributions.values(),
                key=lambda d: d['mass']
            )
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'mass', 'mean_signal', 'std_signal', 'sigma',
                    'num_points'
                ])
                for r in rows:
                    writer.writerow([
                        f"{r['mass']:.4f}",
                        f"{r['mean_signal']:.4f}",
                        f"{r['std_signal']:.4f}",
                        f"{r['sigma']:.4f}",
                        r['num_points'],
                    ])

            self._themed_msgbox('information', parent, "Export Complete", f"Per-mass sigma data exported to:\n{path}")
        except Exception as e:
            self._themed_msgbox('critical', parent, "Export Error", f"Failed to export CSV: {e}")

    def _export_plot(self, pw: pg.PlotWidget, parent: QWidget):
        """
        Export a PlotWidget to SVG or PNG via a save-file dialog.

        Args:
            pw     (pg.PlotWidget): The plot widget to export.
            parent (QWidget):       Parent widget for the file dialog.

        Returns:
            None
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
            self._themed_msgbox('critical', parent, "Export Error", f"Failed to export plot: {e}")

    # ── per-mass sigma assignment ─────────────────────────────────────────────

    def _assign_per_mass_sigma(self):
        """
        Assign each element's sigma from its closest matching per-mass SIA
        distribution. Falls back to the global calculated sigma if no
        per-mass match is within 0.5 amu of the element's target mass.

        Updates the ``sample_parameters`` dict on the main window and
        refreshes the parameters table.

        Args:
            None

        Returns:
            None
        """
        if not self.per_mass_distributions:
            self._themed_msgbox('warning', self.main_window, "No Per-Mass Data", "No per-mass distributions available for assignment.")
            return

        if not hasattr(self.main_window, 'sample_parameters'):
            self._themed_msgbox('warning', self.main_window, "No Samples", "No samples loaded to assign sigma values to.")
            return

        mass_sigma_pairs = np.array([
            (d['mass'], d['sigma'])
            for d in self.per_mass_distributions.values()
        ])
        avail_masses = mass_sigma_pairs[:, 0]
        avail_sigmas = mass_sigma_pairs[:, 1]

        global_sigma = self.single_ion_info.get('calculated_sigma', DEFAULT_SIGMA)
        assigned     = 0
        fallback     = 0
        max_gap      = 2

        for sample in self.main_window.sample_parameters.values():
            for el_name, el_params in sample.items():
                try:
                    target_mass = float(el_name.split('-')[1])
                except (ValueError, IndexError):
                    target_mass = None

                if target_mass is None:
                    el_params['sigma']          = global_sigma
                    el_params['_sigma_from_sia'] = False
                    fallback += 1
                    continue

                diffs  = np.abs(avail_masses - target_mass)
                best_i = np.argmin(diffs)

                if diffs[best_i] <= max_gap:
                    el_params['sigma']          = float(avail_sigmas[best_i])
                    el_params['_sigma_from_sia'] = True
                    assigned += 1
                else:
                    el_params['sigma']          = global_sigma
                    el_params['_sigma_from_sia'] = False
                    fallback += 1

        if hasattr(self.main_window, 'parameters_table'):
            self.main_window.update_parameters_table()

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
        """
        Clear the overlay SIA data and refresh the current dialog view.

        Args:
            dialog (QDialog): The parent SIA info dialog to refresh.

        Returns:
            None
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
        """
        Prompt the user to confirm, then clear all SIA data and reset sigma.

        Args:
            None

        Returns:
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
        """
        Reset all stored SIA data (primary and overlay) and restore sigma to
        ``DEFAULT_SIGMA`` for every sample/element in the parameters table.

        Uses ``blockSignals`` to avoid triggering spurious valueChanged
        callbacks (fix #8).

        Args:
            None

        Returns:
            None
        """
        self.single_ion_distribution_data = None
        self.single_ion_source_folder     = None
        self.single_ion_info              = {}
        self.per_mass_distributions       = {}

        self._overlay_info              = None
        self._overlay_per_mass          = {}
        self._overlay_distribution_data = None

        if hasattr(self.main_window, 'sigma_spinbox'):
            sb = self.main_window.sigma_spinbox
            sb.blockSignals(True)
            sb.setValue(DEFAULT_SIGMA)
            sb.blockSignals(False)

            for sample in self.main_window.sample_parameters.values():
                for el in sample.values():
                    el['sigma'] = DEFAULT_SIGMA

        if hasattr(self.main_window, 'parameters_table'):
            self.main_window.update_parameters_table()

    def _update_ui_after_clear(self):
        """
        Disable info/clear buttons and reset the upload button style after clear.

        Args:
            None

        Returns:
            None
        """
        self.info_sid_button.setEnabled(False)
        self.clear_sid_button.setEnabled(False)
        self.upload_sid_button.setStyleSheet("")
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
                           tolerance: float = 0.5) -> float:
        """
        Look up the per-mass sigma for a given target mass.
        Falls back to the global calculated sigma if no match is found
        within ``tolerance`` amu.

        Args:
            target_mass (float): Target mass in amu (m/z).
            tolerance   (float): Maximum mass difference to accept a match.

        Returns:
            float: Per-mass sigma if a match exists, otherwise global sigma
                   or ``DEFAULT_SIGMA``.
        """
        if not self.per_mass_distributions:
            return self.get_calculated_sigma()

        best_sigma = None
        best_diff  = float('inf')
        for d in self.per_mass_distributions.values():
            diff = abs(d['mass'] - target_mass)
            if diff < best_diff:
                best_diff  = diff
                best_sigma = d['sigma']

        if best_diff <= tolerance and best_sigma is not None:
            return best_sigma
        return self.get_calculated_sigma()

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
        """
        Request the background worker to stop and reset the UI.

        Args:
            None

        Returns:
            None
        """
        if self._is_processing and self.sia_worker:
            self.sia_worker.stop_processing()
            self._reset_processing_state()

    def cleanup(self):
        """
        Gracefully stop the worker thread and release all references.
        Should be called when the parent window is closing.

        Args:
            None

        Returns:
            None
        """
        if self.sia_thread and self.sia_thread.isRunning():
            if self.sia_worker:
                self.sia_worker.stop_processing()
            self.sia_thread.quit()
            self.sia_thread.wait(3000)

        self.sia_thread     = None
        self.sia_worker     = None
        self._is_processing = False