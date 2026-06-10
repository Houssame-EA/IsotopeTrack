import sys
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QLineEdit, QScrollArea,
                               QWidget, QFileDialog, QProgressBar, QLabel, QHBoxLayout, QComboBox, QSizePolicy,
                               QTableWidget, QDialog, QMessageBox, QCheckBox, QDoubleSpinBox, QTableWidgetItem,QRadioButton,
                            QGroupBox, QMenu, QTextEdit, QHeaderView, QListView, QTreeView, QAbstractItemView, QSpinBox,
                            QLayout, QFrame, QGridLayout)
from tools.parameters_table import (ParametersTableView,
                               COL_ELEMENT, COL_INCLUDE, COL_METHOD, COL_SIGMA,
                               COL_THRESHOLD, COL_MIN_CONT, COL_ALPHA, COL_ITERATIVE,
                               COL_WINDOW, COL_INTEG, COL_SPLIT, COL_VALLEY)
from PySide6.QtCore import (Qt, QTimer, QParallelAnimationGroup, QPropertyAnimation, QEasingCurve, QSize, QPoint,
                            QRect, QEvent, QEventLoop, QSettings, Signal)
from PySide6.QtGui import  QGuiApplication
import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QColor, QBrush, QAction, QActionGroup
from PySide6.QtWidgets import QWidget
import tools.dilution_utils
import json
from calibration_methods.ionic_CAL import IonicCalibrationWindow
from widget.periodic_table_widget import PeriodicTableWidget
from widget.custom_plot_widget import EnhancedPlotWidget, MzBarPlotWidget
from calibration_methods.TE import TransportRateCalibrationWindow
from widget.numeric_table import NumericTableWidgetItem
from widget.calibration_info import CalibrationInfoDialog
from loading.data_thread import DataProcessThread
from tools.Info_table import InfoTooltip
from processing.peak_detection import PeakDetection
from tools.info_file import FileInfoMenu
from widget.batch_parameters import BatchElementParametersDialog
from save_export.project_manager import ProjectManager
from widget.canvas_widgets import CanvasResultsDialog
from loading.SIA_manager import SingleIonDistributionManager
import qtawesome as qta
from tools.signal_selector_dialog import SignalSelectorDialog
import isobaric_correction as isobaric
from tools.logging_utils import logging_manager, log_user_action
import logging
from widget.colors import element_colors
from tools.theme import (
    theme,
    main_window_qss,
    sidebar_qss,
    edge_strip_qss,
    sidebar_logo_qss,
    sidebar_list_label_qss,
    calibration_panel_qss,
    sample_table_qss,
    parameters_table_qss,
    info_button_qss,
    theme_toggle_button_qss,
    sidebar_toggle_button_qss,
    primary_button_qss,
    progress_bar_qss,
    groupbox_qss,
    summary_label_qss,
    results_container_qss,
    results_header_qss,
    results_title_qss,
    perf_tip_qss,
    enhanced_checkbox_qss,
    results_table_qss,
    dialog_qss,
    tier_colors,
    table_header_label_qss,
    html_table_css,
)


def element_chip_qss(p) -> str:
    """Stylesheet for a single element chip in the quick-selector.

    ``p`` is a theme ``Palette``. The ``:checked`` state marks the element
    currently shown in the plot.
    """
    return (
        f"QPushButton{{"
        f"background:{p.bg_tertiary};color:{p.text_primary};"
        f"border:1px solid {p.border};border-radius:6px;"
        f"padding:4px 8px;font-weight:600;font-size:12px;}}"
        f"QPushButton:hover{{border-color:{p.accent};background:{p.bg_hover};}}"
        f"QPushButton:checked{{background:{p.accent};color:{p.text_inverse};"
        f"border:1px solid {p.accent};}}"
    )


from tools.element_picker import ElementGridPopup, ElementPicker

try:
    from loading.import_csv_dialogs import CSVStructureDialog, CSVDataProcessThread, show_csv_structure_dialog
except ImportError:
    CSVStructureDialog = None
    CSVDataProcessThread = None
    show_csv_structure_dialog = None
    
    
class NoWheelSpinBox(QDoubleSpinBox):
    """
    Custom QDoubleSpinBox that ignores mouse wheel events.
    
    Args:
        Inherits from QDoubleSpinBox
        
    Returns:
        None
    """
    def wheelEvent(self, event):
        """
        Ignore mouse wheel scroll events.
        
        Args:
            event: QWheelEvent object
            
        Returns:
            None
        """
        event.ignore()


class NoWheelIntSpinBox(QSpinBox):
    """
    Custom QSpinBox that ignores mouse wheel events.
    
    Args:
        Inherits from QSpinBox
        
    Returns:
        None
    """
    def wheelEvent(self, event):
        """
        Ignore mouse wheel scroll events.
        
        Args:
            event: QWheelEvent object
            
        Returns:
            None
        """
        event.ignore()


class NoWheelComboBox(QComboBox):
    """
    Custom QComboBox that ignores mouse wheel events.
    
    Args:
        Inherits from QComboBox
        
    Returns:
        None
    """
    def wheelEvent(self, event):
        """
        Ignore mouse wheel scroll events.
        
        Args:
            event: QWheelEvent object
            
        Returns:
            None
        """
        event.ignore()
        


    #----------------------------------------------------------------------------------------------------
    #---------------------------------------Initialization & setup---------------------------------------
    #----------------------------------------------------------------------------------------------------
     
class MainWindow(QMainWindow):
    def __init__(self):
        """
        Initialize the MainWindow for IsotopeTrack application.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        super().__init__()
        
        if not hasattr(self, 'logger'):
            self.logger = logging_manager.get_logger('MainWindow')
            self.user_action_logger = logging_manager.get_user_action_logger()
        
        self.logger.info("MainWindow initialization starting")
        self.user_action_logger.log_action('STARTUP', 'Application started')
            
        self.unsaved_changes = False
        self.folder_paths = []
        self.current_sample = None
        self.data = {}
        self.all_masses = None
        self.time_array = None
        self.average_counts = {}
        self.periodic_table_widget = None 
        self.selected_isotopes = {}
        self.current_element = None
        self.element_mass_map = {}
        self.detected_peaks = {}
        self.sample_status = {} 
        # --- Saturation (FWHM-based) filter state ----------------------
        _sat_settings = QSettings("IsotopeTrack", "IsotopeTrack")
        self.saturation_filter_enabled = False
        try:
            self.saturation_filter_ms = float(
                _sat_settings.value("filters/saturation_fwhm_ms", 1.5))
        except (TypeError, ValueError):
            self.saturation_filter_ms = 1.5
        self.saturation_highlight = _sat_settings.value(
            "filters/saturation_highlight", True, type=bool)
        try:
            self.saturation_min_snr = float(
                _sat_settings.value("filters/saturation_min_snr", 10.0))
        except (TypeError, ValueError):
            self.saturation_min_snr = 10.0
        try:
            self.saturation_flat_ratio = float(
                _sat_settings.value("filters/saturation_flat_ratio", 0.5))
        except (TypeError, ValueError):
            self.saturation_flat_ratio = 0.5
        try:
            self.saturation_top_frac = float(
                _sat_settings.value("filters/saturation_top_frac", 0.90))
        except (TypeError, ValueError):
            self.saturation_top_frac = 0.90
        self.saturation_top_frac = min(0.99, max(0.50, self.saturation_top_frac))
        # sample -> {(element, isotope): [particles removed by the filter]}
        self.saturation_filtered_peaks = {}
        # sample -> [multi-element particles removed by the filter]
        self.saturation_filtered_multi = {}
        # sample -> [(t0, t1), ...] merged saturated time windows
        self.saturation_windows = {}
        # sample -> total excluded time (s), for concentration correction
        self.saturation_excluded_time_s = {}
        self.animation = None
        self.animation_group = None
        self.overlap_threshold_percentage = 75.0
        self._global_sigma = 0.55
        self._sigma_mode   = 'global'
        self.sidebar_min_width = 150
        self.sidebar_max_width = 400
        try:
            _saved_w = int(QSettings("IsotopeTrack", "IsotopeTrack")
                           .value("ui/sidebar_width", 200))
        except (TypeError, ValueError):
            _saved_w = 200
        self.sidebar_width = max(self.sidebar_min_width,
                                 min(self.sidebar_max_width, _saved_w))
        self.sidebar_visible = True
        self.multi_element_particles = []
        self.sample_parameters = {}
        self.sample_detected_peaks = {}
        self.sample_dwell_times = {}
        self.sample_results_data = {}
        self.isotope_method_preferences = {}
        self.sample_particle_data = {}
        self.sample_analysis_dates = {}
        self.csv_config = None 
        self.pending_csv_processing = False
        self.current_data_source_type = None
        self._pending_csv_append_mode = False
        self._isobaric_raw_backup = {}   
        self.isobaric_applied = False 
        self.data_by_sample = {}
        self._exclusion_regions_by_sample = {}
        self.element_limits = {} 
        self.sia_manager = SingleIonDistributionManager(self)
        self.element_thresholds = {}
        self.time_array_by_sample = {}
        self.sample_dilutions = {}
        self.canvas_results_dialog = None
        self._current_plot_mode = 'time'
        self.sample_run_info = {}
        self._display_label_to_element = {}
        self.element_parameter_hashes = {} 
        self._formatted_label_cache = {}
        self._element_data_cache = {}
        self.project_manager = ProjectManager(self)
        self.detection_states = {}  
        self.needs_initial_detection = set() 
        self.peak_detector = PeakDetection()  
        self.sample_method_info = {}
        self.sample_to_folder_map = {}
        self.transport_rate_methods = ["Liquid weight", "Number based", "Mass based"]
        self.element_mass_fractions = {}
        self.element_densities = {}
        self.element_molecular_weights = {}  
        self.sample_mass_fractions = {}
        self.sample_densities = {}
        self.sample_molecular_weights = {} 
        self.selected_transport_rate_methods = self.transport_rate_methods.copy()  
        self.average_transport_rate = 0
        self.calibration_results = {
            "Liquid weight": {},
            "Number based": {},
            "Mass based": {},
            "Ionic Calibration": {}}
        self.setup_window_size()
        self.create_central_widget()
        self.create_menu_bar()
        self.create_status_bar()
        theme.themeChanged.connect(self.apply_theme)
        self.apply_theme()

        self.initialize_help_manager()
        self.transport_rate_window = None
        self.ionic_calibration_window = None
        
        if not hasattr(QApplication.instance(), 'main_windows'):
            QApplication.instance().main_windows = []
        if not hasattr(QApplication.instance(), '_window_counter'):
            QApplication.instance()._window_counter = 0
        QApplication.instance()._window_counter += 1
        self.window_number = QApplication.instance()._window_counter
        self._project_filepath = None
        QApplication.instance().main_windows.append(self)
        self.update_window_title()
        from tools.update_checker import UpdateChecker
        self._update_checker = UpdateChecker(self)
        _app = QApplication.instance()
        if not getattr(_app, '_update_check_done', False):
            _app._update_check_done = True
            QTimer.singleShot(4000, lambda: self._update_checker.check(silent=True))

    def update_window_title(self, filepath=None):
        """
        Update the window title to reflect the current project state.

        When no project is saved the title reads
        "IsotopeTrack — Window N (Unnamed)".  After a save or load the
        project filename replaces the unnamed placeholder.

        Args:
            filepath (str | None): Path to the project file that was just
                saved or loaded.  Pass None to keep the current filepath or
                to show the unnamed title on a fresh window.

        Returns:
            None
        """
        if filepath is not None:
            self._project_filepath = filepath
        if self._project_filepath:
            name = Path(self._project_filepath).stem
            self.setWindowTitle(f"IsotopeTrack — Window {self.window_number} ({name})")
        else:
            self.setWindowTitle(f"IsotopeTrack — Window {self.window_number} (Unnamed)")

    def setup_window_size(self):
        """
        Configure initial window size and position.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        screen = QGuiApplication.primaryScreen().availableGeometry()

        window_width = int(screen.width() * 0.8)
        window_height = int(screen.height() * 0.8)
        self.resize(window_width, window_height)
        self.center_on_screen()
        
    def initialize_help_manager(self):
        """
        Initialize help dialog manager.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        from tools.help_dialogs import HelpManager
        self.help_manager = HelpManager(self)
        
    def center_on_screen(self):
        """
        Center window on screen.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        screen = QGuiApplication.primaryScreen().availableGeometry()
        window_geometry = self.frameGeometry()
        window_geometry.moveCenter(screen.center())
        self.move(window_geometry.topLeft())
        
    def reset_data_structures(self):
        """
        Reset all data structures before loading a saved project.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.selected_isotopes = {}
        self.data_by_sample = {}
        self._exclusion_regions_by_sample = {}
        self.time_array_by_sample = {}
        self.sample_parameters = {}
        self.sample_detected_peaks = {}
        self.sample_dwell_times = {}
        self.sample_results_data = {}
        self.isotope_method_preferences = {}
        self.sample_particle_data = {}
        self.sample_analysis_dates = {}
        self.sample_to_folder_map = {}
        self.element_thresholds = {}
        self.element_limits = {}
        self.sample_dilutions = {}
        self.sample_run_info = {}
        self.sample_method_info = {}
        
        self.element_mass_fractions = {}
        self.element_densities = {}
        self.element_molecular_weights = {} 
        self.sample_mass_fractions = {}
        self.sample_densities = {}
        self.sample_molecular_weights = {}
        
        self.current_sample = None
        self.data = {}
        self.time_array = None
        self.detected_peaks = {}
        

        self.sample_table.setRowCount(0)
        self.parameters_table.setRowCount(0)
        self.results_table.setRowCount(0)
        self.multi_element_table.setRowCount(0)
        
        self.plot_widget.clear()
    #----------------------------------------------------------------------------------------------------------
    #------------------------------------UI creation - main layout --------------------------------------------
    #----------------------------------------------------------------------------------------------------------
    def open_isobaric_correction(self):
        if not self.selected_isotopes or not self.data_by_sample:
            QMessageBox.warning(self, "Isobaric Correction", "Load data and select elements first.")
            return
        from widget.isobaric_correction_dialog import IsobaricCorrectionDialog
        IsobaricCorrectionDialog(self).exec()
        
    def create_central_widget(self):
        """
        Create and configure the central widget with main UI layout.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar_container = QWidget()
        self.sidebar_container.setObjectName("sidebarContainer")
        sidebar_container_layout = QHBoxLayout(self.sidebar_container)
        sidebar_container_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_container_layout.setSpacing(0)

        self.edge_strip = QWidget()
        self.edge_strip.setFixedWidth(25)
        self.edge_strip.setCursor(Qt.PointingHandCursor)

        import weakref as _wr
        self.edge_strip.mousePressEvent = (
            lambda e, _ref=_wr.ref(self): _ref() and _ref().toggle_sidebar()
        )
        del _wr
        self.edge_strip.hide()
        self.sidebar = self.create_sidebar()
        sidebar_container_layout.addWidget(self.edge_strip)
        sidebar_container_layout.addWidget(self.sidebar)
        from PySide6.QtWidgets import QGridLayout, QSizePolicy
        self.sidebar_grip = QWidget()
        self.sidebar_grip.setObjectName("sidebarGrip")
        self.sidebar_grip.setFixedWidth(12)
        self.sidebar_grip.setCursor(Qt.SizeHorCursor)

        _grip_layout = QGridLayout(self.sidebar_grip)
        _grip_layout.setContentsMargins(0, 0, 0, 0)

        _grip_line = QWidget()
        _grip_line.setObjectName("gripLine")
        _grip_line.setFixedWidth(1)
        _grip_line.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        _grip_line.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        _grip_layout.addWidget(_grip_line, 0, 0, Qt.AlignHCenter)

        _grip_pill = QWidget()
        _grip_pill.setObjectName("gripPill")
        _grip_pill.setFixedSize(5, 40)
        _grip_pill.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        _grip_layout.addWidget(_grip_pill, 0, 0, Qt.AlignCenter)

        self._apply_sidebar_grip_style()
        self.sidebar_grip.mousePressEvent = self._sidebar_grip_press
        self.sidebar_grip.mouseMoveEvent = self._sidebar_grip_move
        self.sidebar_grip.mouseReleaseEvent = self._sidebar_grip_release
        sidebar_container_layout.addWidget(self.sidebar_grip)
        content_widget = QWidget()
        content_widget.setObjectName("contentWidget")
        content_layout = QVBoxLayout(content_widget)
        
        from PySide6.QtWidgets import QFrame
        scroll_area = QScrollArea()
        scroll_area.setObjectName("mainScrollArea")
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        plot_container = QWidget()
        plot_container.setObjectName("plotContainer")
        plot_container_layout = QHBoxLayout(plot_container)
        plot_container_layout.setContentsMargins(0, 0, 0, 0)
        plot_container_layout.setSpacing(0)

        plot_widget = self.create_plot_widget()
        plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plot_container_layout.addWidget(plot_widget)

        page_content = QWidget()
        page_content.setObjectName("pageContent")
        page_layout = QVBoxLayout(page_content)
        page_layout.addWidget(plot_container, stretch=3)

        self.summary_widget = self.create_summary_widget()
        page_layout.addWidget(self.summary_widget)

        page_layout.addWidget(self.create_control_panel(), stretch=1)
        results_container = self.create_results_container()
        page_layout.addWidget(results_container, stretch=1)

        scroll_area.setWidget(page_content)
        content_layout.addWidget(scroll_area)

        main_layout.addWidget(self.sidebar_container)
        main_layout.addWidget(content_widget, stretch=1)
        
    
    def compute_isobaric_corrections(self):
        """Derive every applicable correction from self.selected_isotopes.
 
        Reuses the periodic table's abundance data (get_element_by_symbol /
        get_elements). A correction is 'enabled' only when a clean monitor of
        the interferent is itself among the selected isotopes.
        """
        if not getattr(self, 'periodic_table_widget', None):
            return []
        if not getattr(self, 'selected_isotopes', None):
            return []
        return isobaric.build_all_corrections(
            self.selected_isotopes,
            self.periodic_table_widget.get_element_by_symbol,
            self.periodic_table_widget.get_elements,
        )
 
    # ---- PREVIEW: compute IN vs OUT, change nothing ----
    def preview_isobaric_correction(self, sample_name=None, corrections=None):
        """Return per-channel before/after for the in/out plot. No mutation.
 
        Returns a dict keyed by analyte mass:
            { analyte_mass: {'raw': ndarray, 'corrected': ndarray,
                             'equation': str, 'label': str} }
        Empty dict means nothing to preview (no overlap, or monitor missing).
        """
        sample_name = sample_name or getattr(self, 'current_sample', None)
        if sample_name is None or sample_name not in self.data_by_sample:
            return {}
 
        if corrections is None:
            corrections = self.compute_isobaric_corrections()
        corrections = [c for c in corrections if c.enabled]
        if not corrections:
            return {}
 
        sample_data = self.data_by_sample[sample_name]
        corrected_channels = isobaric.correct_sample_channels(
            sample_data, corrections, self.find_closest_isotope)
 
        eqs_by_channel = {}
        labels_by_channel = {}
        for c in corrections:
            akey = self.find_closest_isotope(c.analyte_mass)
            eqs_by_channel.setdefault(akey, []).append(c.equation_text())
            labels_by_channel[akey] = c.analyte_label
 
        preview = {}
        for akey, corrected in corrected_channels.items():
            preview[akey] = {
                'raw': np.asarray(sample_data[akey], dtype=float),
                'corrected': corrected,
                'equation': "\n".join(eqs_by_channel.get(akey, [])),
                'label': labels_by_channel.get(akey, str(akey)),
            }
        return preview
 
    # ---- APPLY: commit the correction (corrected signal becomes the data) ----
    def apply_isobaric_correction(self, sample_names=None, corrections=None):
        """Overwrite the working signal with the corrected signal.
 
        Raw channels are stashed in self._isobaric_raw_backup so revert works.
        Applies to all loaded samples by default so every sample is consistent.
        Returns the number of channels changed.
        """
        if corrections is None:
            corrections = self.compute_isobaric_corrections()
        corrections = [c for c in corrections if c.enabled]
        if not corrections:
            return 0
 
        if sample_names is None:
            sample_names = list(self.data_by_sample.keys())
 
        if not hasattr(self, '_isobaric_raw_backup'):
            self._isobaric_raw_backup = {}
 
        changed = 0
        for sname in sample_names:
            sample_data = self.data_by_sample.get(sname)
            if not sample_data:
                continue
            corrected_channels = isobaric.correct_sample_channels(
                sample_data, corrections, self.find_closest_isotope)
            if not corrected_channels:
                continue
 
            backup = self._isobaric_raw_backup.setdefault(sname, {})
            for akey, corrected in corrected_channels.items():
                if akey not in backup:                 # keep the ORIGINAL raw
                    backup[akey] = np.asarray(sample_data[akey], dtype=float).copy()
                sample_data[akey] = corrected
                changed += 1
 
            if sname == getattr(self, 'current_sample', None):
                self.data = sample_data
 
        if changed:
            self.isobaric_applied = True
        return changed
 
    # ---- REVERT: undo an apply, restore raw ----
    def revert_isobaric_correction(self):
        """Restore the raw signal everywhere a correction was applied."""
        backup = getattr(self, '_isobaric_raw_backup', {})
        for sname, channels in backup.items():
            sample_data = self.data_by_sample.get(sname)
            if not sample_data:
                continue
            for akey, raw in channels.items():
                sample_data[akey] = raw
            if sname == getattr(self, 'current_sample', None):
                self.data = sample_data
        self._isobaric_raw_backup = {}
        self.isobaric_applied = False
        
    
    def create_sidebar(self):
        """
        Create sidebar with calibration and sample management tools.
        
        Args:
            self: MainWindow instance
            
        Returns:
            QWidget: Configured sidebar widget
        """
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(self.sidebar_width)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(0)
        sidebar_layout.setContentsMargins(0, 6, 6, 6)
        header_container = QWidget()
        header_container.setFixedHeight(60)
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(5, 0, 5, 0)
        header_layout.setSpacing(10)

        logo = QLabel("Tools")
        self._sidebar_logo = logo
        logo.setStyleSheet(sidebar_logo_qss(theme.palette))
        header_layout.addWidget(logo)

        self.toggle_button = QPushButton()
        self.toggle_button.setIconSize(QSize(24, 24))
        self.toggle_button.setFixedSize(32, 32)
        self.toggle_button.clicked.connect(self.toggle_sidebar)
        header_layout.addWidget(self.toggle_button, alignment=Qt.AlignVCenter)
        
        sidebar_layout.addWidget(header_container)

        self._sidebar_icon_buttons = []

        calibration_group = QGroupBox("Calibration")
        calibration_layout = QVBoxLayout(calibration_group)
        calibration_layout.setSpacing(0)
        calibration_layout.setContentsMargins(5, 0, 5, 5)

        transport_rate_button = QPushButton("Transport Rate")
        self._sidebar_icon_buttons.append((transport_rate_button, 'fa6s.scale-balanced'))
        transport_rate_button.clicked.connect(self.open_transport_rate_calibration)
        calibration_layout.addWidget(transport_rate_button)

        sensitivity_button = QPushButton("Sensitivity")
        self._sidebar_icon_buttons.append((sensitivity_button, 'fa6s.chart-line'))
        sensitivity_button.clicked.connect(self.open_ionic_calibration)
        calibration_layout.addWidget(sensitivity_button)

        self.show_calibration_button = QPushButton("Show Calibration Info")
        self._sidebar_icon_buttons.append((self.show_calibration_button, 'fa6s.eye'))
        self.show_calibration_button.clicked.connect(self.show_calibration_info)
        calibration_layout.addWidget(self.show_calibration_button)

        sidebar_layout.addWidget(calibration_group)
        
        samples_group = QGroupBox("Samples")
        samples_layout = QVBoxLayout(samples_group)
        samples_layout.setSpacing(0)
        samples_layout.setContentsMargins(0, 10, 0, 0)
        
        import_button = QPushButton("Import Data")
        self._sidebar_icon_buttons.append((import_button, 'fa6s.file-import'))
        import_button.clicked.connect(self.select_folder)
        samples_layout.addWidget(import_button)

        elements_button = QPushButton("Add/Edit Elements")
        self._sidebar_icon_buttons.append((elements_button, 'fa6s.plus-minus'))
        elements_button.clicked.connect(self.show_periodic_table)
        samples_layout.addWidget(elements_button)

        results_button = QPushButton("Results")
        self._sidebar_icon_buttons.append((results_button, 'fa6s.table-list'))
        results_button.clicked.connect(self.show_results)
        samples_layout.addWidget(results_button)

        export_button = QPushButton("Export")
        self._sidebar_icon_buttons.append((export_button, 'fa6s.file-export'))
        export_button.clicked.connect(self.export_data)
        samples_layout.addWidget(export_button)
        

        sample_list_label = QLabel("Sample List")
        self._sample_list_label = sample_list_label
        sample_list_label.setStyleSheet(sidebar_list_label_qss(theme.palette))
        samples_layout.addWidget(sample_list_label)

        self.sample_table = self.create_sample_table()
        samples_layout.addWidget(self.sample_table)

        sidebar_layout.addWidget(samples_group)

        self.calibration_info_panel = QTextEdit()
        self.calibration_info_panel.setReadOnly(True)
        self.calibration_info_panel.setAcceptRichText(True)
        self.calibration_info_panel.setVisible(False) 
        sidebar_layout.addWidget(self.calibration_info_panel)

        sidebar_layout.addStretch()
        return sidebar
    
    def create_menu_bar(self):
        """
        Create application menu bar with actions.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        menu_bar = self.menuBar() 
        
        self._menu_icon_items = []

        def _ma(icon_name, text, slot, shortcut=None):
            """Create a menu action, register it for retinting, return it.
            Args:
                icon_name (Any): The icon name.
                text (Any): Text string.
                slot (Any): The slot.
                shortcut (Any): The shortcut.
            Returns:
                object: Result of the operation.
            """
            action = QAction(text, self)
            if shortcut:
                action.setShortcut(shortcut)
            action.triggered.connect(slot)
            self._menu_icon_items.append((action, icon_name))
            return action

        new_window_action = _ma('fa6s.window-restore', "New Window",
                                self.open_new_window, shortcut="Cmd+N")
        open_action = _ma('fa6s.folder-open', "Import Data", self.select_folder)
        save_action = _ma('fa6s.floppy-disk', "Save Project", self.save_project)
        load_action = _ma('fa6s.folder-open', "Load Project", self.load_project)
        export_action = _ma('fa6s.file-export', "Export", self.export_data)
        exit_action = _ma('fa6s.right-from-bracket', "Exit", self.close_all_windows)

        file_menu = menu_bar.addMenu("File")
        self._menu_icon_items.append((file_menu, 'fa6s.scale-balanced'))
        file_menu.addAction(new_window_action)
        file_menu.addSeparator()
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addAction(load_action)
        file_menu.addAction(export_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
                
        tools_menu = menu_bar.addMenu("Tools")
        self._menu_icon_items.append((tools_menu, 'fa6s.wrench'))

        periodic_action = _ma('fa6s.atom', "Add/Edit Element PT", self.show_periodic_table)
        ionic_action = _ma('fa6s.gear', "Sensitivity", self.open_ionic_calibration)
        mass_fraction_action = _ma('fa6s.calculator', "Mass Fraction Calculator",
                                   self.open_mass_fraction_calculator)
        dilution_action = _ma('fa6s.flask', "Dilution Factor",
                              self.open_dilution_factor_dialog)
        
        isobaric_action = _ma('fa6s.eraser', "Isobaric Correction", self.open_isobaric_correction)
        tools_menu.addAction(isobaric_action)

        tools_menu.addAction(periodic_action)
        tools_menu.addAction(mass_fraction_action)
        tools_menu.addAction(ionic_action)
        tools_menu.addAction(dilution_action)

        view_menu = menu_bar.addMenu("View")
        self._menu_icon_items.append((view_menu, 'fa6s.eye'))

        sidebar_action = _ma('fa6s.bars', "Toggle Sidebar", self.toggle_sidebar)
        view_menu.addAction(sidebar_action)
        
        view_menu.addSeparator()
        log_action = _ma('fa6s.file-lines', "Show Application Log", self.show_log_window)
        view_menu.addAction(log_action)

        self._theme_menu_action = QAction("Toggle Dark Mode", self)
        self._theme_menu_action.setCheckable(True)
        self._theme_menu_action.triggered.connect(theme.toggle)

        self._follow_system_action = QAction("System Theme", self)
        self._follow_system_action.setCheckable(True)
        self._follow_system_action.setChecked(theme.follow_system)
        self._follow_system_action.triggered.connect(
            lambda checked: theme.set_follow_system(checked)
        )

        self.theme_group = QActionGroup(self)
        self.theme_group.addAction(self._theme_menu_action)
        self.theme_group.addAction(self._follow_system_action)
        self.theme_group.setExclusive(True) 

        view_menu.addSeparator()
        view_menu.addAction(self._theme_menu_action)
        view_menu.addAction(self._follow_system_action)

        self._theme_follow_system_slot = (
            lambda _: self._follow_system_action.setChecked(theme.follow_system)
        )
        theme.themeChanged.connect(self._theme_follow_system_slot)
            
        help_menu = menu_bar.addMenu("Help")
        self._menu_icon_items.append((help_menu, 'fa6s.circle-question'))
        
        guide_action = _ma('fa6s.book', "User Guide", self.show_user_guide)
        detection_action = _ma('fa6s.magnifying-glass', "Detection Methods",
                               self.show_detection_methods)
        calibration_action = _ma('fa6s.sliders', "Calibration Methods",
                                 self.show_calibration_methods)
        about_action = _ma('fa6s.circle-info', "About IsotopeTrack",
                           self.show_about_dialog)
        update_action = _ma('fa6s.cloud-arrow-down', "Check for Updates…",
                           lambda: self._update_checker.check(silent=False))

        help_menu.addAction(guide_action)
        help_menu.addAction(detection_action)
        help_menu.addAction(calibration_action)
        help_menu.addSeparator()
        help_menu.addAction(update_action)
        help_menu.addAction(about_action)

    def open_new_window(self):
        """
        Returns:
            None
        """
        self.user_action_logger.log_action('NEW_WINDOW', 'Opened new analysis window')
        
        new_window = MainWindow()
        new_window.showMaximized()
        new_window.raise_()
        new_window.activateWindow()
        
        self.status_label.setText("Opened new analysis window")

    def close_all_windows(self):
        """
        Close all open windows and quit application.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.user_action_logger.log_action('CLICK', 'Close all windows and quit')
        app = QApplication.instance()
        if hasattr(app, 'main_windows'):
            for window in app.main_windows:
                window.close()
        app.quit()
        
    def create_status_bar(self):
        """
        Create application status bar with progress indicator.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        status_bar = self.statusBar()
        
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(10)
        
        self.status_label = QLabel("Ready")
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.status_label, 1)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setFixedWidth(400)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar, 0)
        
        status_bar.addPermanentWidget(container, 1)

    # ------------------------------------------------------------------ #
    # Theme application
    # ------------------------------------------------------------------ #

    def apply_theme(self):
        """
        Apply the currently-active theme palette to every styled widget
        in MainWindow. Called once on startup and re-called whenever the
        user toggles the theme.

        This is the single source of truth for styling — all inline
        stylesheets have been removed from widget creation methods.
        """
        _was_maximized = self.isMaximized() or self.isFullScreen()
        _saved_size = self.size()

        p = theme.palette

        self.setStyleSheet(main_window_qss(p))

        # --- pyqtgraph global background / foreground -----------------------
        try:
            pg.setConfigOption('background', p.plot_bg)
            pg.setConfigOption('foreground', p.plot_fg)
            if hasattr(self, 'plot_widget') and self.plot_widget is not None:
                self.plot_widget.setBackground(p.plot_bg)
        except Exception as e:
            self.logger.debug(f"Could not apply pyqtgraph theme: {e}")

        # --- Sidebar and its members ---------------------------------------
        if hasattr(self, 'sidebar'):
            self.sidebar.setStyleSheet(sidebar_qss(p))
        if hasattr(self, 'edge_strip'):
            self.edge_strip.setStyleSheet(edge_strip_qss(p))
        self._apply_sidebar_grip_style()
        if hasattr(self, '_sidebar_logo'):
            self._sidebar_logo.setStyleSheet(sidebar_logo_qss(p))
        if hasattr(self, '_sample_list_label'):
            self._sample_list_label.setStyleSheet(sidebar_list_label_qss(p))
        if hasattr(self, 'calibration_info_panel'):
            self.calibration_info_panel.setStyleSheet(calibration_panel_qss(p))

        for btn, icon_name in getattr(self, '_sidebar_icon_buttons', []):
            btn.setIcon(qta.icon(icon_name, color=p.text_on_sidebar))

        if hasattr(self, 'toggle_button'):
            arrow_icon = 'fa6s.arrow-left' if self.sidebar_visible else 'fa6s.arrow-right'
            self.toggle_button.setIcon(qta.icon(arrow_icon, color=p.text_on_sidebar))
            self.toggle_button.setStyleSheet(sidebar_toggle_button_qss(p))

        # --- Sample table (lives inside the sidebar) -----------------------
        if hasattr(self, 'sample_table'):
            self.sample_table.setStyleSheet(sample_table_qss(p))

        # --- Menu icons ----------------------------------------------------
        for item, icon_name in getattr(self, '_menu_icon_items', []):
            item.setIcon(qta.icon(icon_name, color=p.text_primary))

        # --- Theme toggle button (sun / moon) ------------------------------
        if hasattr(self, 'theme_toggle_button'):
            icon_name = 'fa6s.sun' if theme.is_dark else 'fa6s.moon'
            self.theme_toggle_button.setIcon(qta.icon(icon_name, color=p.accent))
            self.theme_toggle_button.setIconSize(QSize(18, 18))
            self.theme_toggle_button.setStyleSheet(theme_toggle_button_qss(p))
            self.theme_toggle_button.setToolTip(
                "Switch to light mode" if theme.is_dark else "Switch to dark mode"
            )
        if hasattr(self, '_theme_menu_action'):
            self._theme_menu_action.setText(
                "Switch to Light Mode" if theme.is_dark else "Switch to Dark Mode"
            )

        if hasattr(self, 'info_button'):
            self.info_button.setIcon(qta.icon('fa6s.circle-info', color=p.accent))
            self.info_button.setStyleSheet(info_button_qss(p))

        if hasattr(self, '_view_btn_time') and hasattr(self, '_view_btn_mz'):
            _toggle_qss = (
                f"QPushButton{{"
                f"background:{p.bg_tertiary};color:{p.text_primary};"
                f"border:1px solid {p.border};border-radius:4px;"
                f"padding:3px 14px;font-weight:500;}}"
                f"QPushButton:hover{{background:{p.bg_hover};"
                f"border-color:{p.accent};}}"
                f"QPushButton:checked{{background:{p.accent};"
                f"color:{p.text_inverse};border:none;font-weight:600;}}"
            )
            self._view_btn_time.setStyleSheet(_toggle_qss)
            self._view_btn_mz.setStyleSheet(_toggle_qss)
            if hasattr(self, '_mz_pg_widget'):
                self._mz_pg_widget.setBackground(p.plot_bg)
                if getattr(self, '_current_plot_mode', 'time') == 'mz':
                    self._update_mz_plot()

        if hasattr(self, 'progress_bar'):
            self.progress_bar.setStyleSheet(progress_bar_qss(p))

        for gb in getattr(self, '_themed_groupboxes', []):
            gb.setStyleSheet(groupbox_qss(p))

        if hasattr(self, 'parameters_table'):
            self.parameters_table.setStyleSheet(parameters_table_qss(p))

        primary_style = primary_button_qss(p)
        for btn, icon_name in getattr(self, '_primary_buttons', []):
            btn.setStyleSheet(primary_style)
            btn.setIcon(qta.icon(icon_name, color=p.text_inverse))

        if hasattr(self, 'summary_label'):
            self.summary_label.setStyleSheet(summary_label_qss(p))

        if hasattr(self, '_results_container'):
            self._results_container.setStyleSheet(results_container_qss(p))
        if hasattr(self, '_results_header_widget'):
            self._results_header_widget.setStyleSheet(results_header_qss(p))
        if hasattr(self, '_results_title_label'):
            self._results_title_label.setStyleSheet(results_title_qss(p))
        if hasattr(self, '_perf_tip_label'):
            self._perf_tip_label.setStyleSheet(perf_tip_qss(p))

        checkbox_style = enhanced_checkbox_qss(p)
        for cb in getattr(self, '_enhanced_checkboxes', []):
            cb.setStyleSheet(checkbox_style)

        rt_style = results_table_qss(p)
        if hasattr(self, 'results_table'):
            self.results_table.setStyleSheet(rt_style)
            self.results_table.setAlternatingRowColors(True)
        if hasattr(self, 'multi_element_table'):
            self.multi_element_table.setStyleSheet(rt_style)
            self.multi_element_table.setAlternatingRowColors(True)

        if hasattr(self, '_element_header_label'):
            if theme.is_dark:
                bg, fg = p.bg_tertiary, p.accent
            else:
                bg, fg = self._element_header_colors
            self._element_header_label.setStyleSheet(
                table_header_label_qss(p, bg, fg)
            )
        if hasattr(self, '_particle_header_label'):
            if theme.is_dark:
                bg, fg = p.bg_tertiary, "#eb9c4a"
            else:
                bg, fg = self._particle_header_colors
            self._particle_header_label.setStyleSheet(
                table_header_label_qss(p, bg, fg)
            )

        last_args = getattr(self, '_last_summary_args', None)
        if last_args is not None:
            try:
                self.update_element_summary(*last_args)
            except Exception as e:
                self.logger.debug(f"Could not refresh summary on theme change: {e}")

        if hasattr(self, '_dataviz_title'):
            self._dataviz_title.setStyleSheet(
                f"font-weight: bold; font-size: 14px; color: {p.text_secondary};"
            )

        if hasattr(self, 'element_picker'):
            self.element_picker.set_chip_style(element_chip_qss(p))
            self.element_picker.apply_button_style(p)

        from tools.parameters_table import ParametersModel, _SIGMA_HIGHLIGHT_LIGHT, _SIGMA_HIGHLIGHT_DARK
        ParametersModel.sigma_hl_color = (
            _SIGMA_HIGHLIGHT_DARK if theme.is_dark else _SIGMA_HIGHLIGHT_LIGHT
        )
        if hasattr(self, 'parameters_table'):
            self.parameters_table.viewport().update()

        if not _was_maximized:
            self.resize(_saved_size)

        self.logger.info(f"Theme applied: {p.name}")

    def create_plot_widget(self):
        """
        Create plot widget for data visualization with an inline Time / m/z toggle.

        Args:
            self: MainWindow instance

        Returns:
            QGroupBox: Plot widget container
        """
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(14, 0, 8, 0)
        header.setSpacing(8)

        self._dataviz_title = QLabel("Data Visualization")
        self._dataviz_title.setObjectName("dataVizTitle")
        self._dataviz_title.setStyleSheet(
            f"font-weight: bold; font-size: 14px; color: {theme.palette.text_secondary};"
        )
        header.addWidget(self._dataviz_title, 0, Qt.AlignVCenter)
        header.addStretch()
        self.element_picker = ElementPicker(columns=7)
        self.element_picker.setFixedHeight(28)
        self.element_picker.set_chip_style(element_chip_qss(theme.palette))
        self.element_picker.apply_button_style(theme.palette)
        self.element_picker.elementActivated.connect(
            self._on_element_selector_activated
        )
        header.addWidget(self.element_picker, 0, Qt.AlignVCenter)

        self._view_btn_time = QPushButton("Time")
        self._view_btn_mz   = QPushButton("m/z")
        for btn in (self._view_btn_time, self._view_btn_mz):
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.PointingHandCursor)
        self._view_btn_time.setChecked(True)
        self._view_btn_time.clicked.connect(lambda: self.switch_plot_view('time'))
        self._view_btn_mz.clicked.connect(lambda: self.switch_plot_view('mz'))
        header.addWidget(self._view_btn_time)
        header.addWidget(self._view_btn_mz)

        self.info_button = QPushButton()
        self.info_button.setIcon(qta.icon('fa6s.circle-info', color=theme.palette.accent))
        self.info_button.setFixedSize(28, 28)
        self.info_button.setToolTip("Sample information")
        self.info_button.setCursor(Qt.PointingHandCursor)
        self.info_button.clicked.connect(self.toggle_info)
        header.addWidget(self.info_button)

        self.theme_toggle_button = QPushButton()
        self.theme_toggle_button.setFixedSize(28, 28)
        self.theme_toggle_button.setCursor(Qt.PointingHandCursor)
        self.theme_toggle_button.setToolTip("Toggle light / dark mode")
        self.theme_toggle_button.clicked.connect(theme.toggle)
        header.addWidget(self.theme_toggle_button)

        wrapper_layout.addLayout(header)

        group_box = QGroupBox("")
        group_box.setObjectName("plotCard")
        self._themed_groupboxes = getattr(self, '_themed_groupboxes', [])
        self._themed_groupboxes.append(group_box)
        layout = QVBoxLayout(group_box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        from PySide6.QtWidgets import QStackedWidget
        self._plot_stack = QStackedWidget()

        self.plot_widget = EnhancedPlotWidget(self)
        self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_widget.setMinimumHeight(400)
        try:
            self.plot_widget.exclusionRegionsChanged.connect(
                self._on_exclusion_regions_changed)
        except Exception as e:
            self.logger.debug(f"Could not connect exclusionRegionsChanged: {e}")
        self._plot_stack.addWidget(self.plot_widget)

        self._mz_pg_widget = MzBarPlotWidget(self)
        self._mz_pg_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._mz_pg_widget.setMinimumHeight(400)
        self._plot_stack.addWidget(self._mz_pg_widget)

        layout.addWidget(self._plot_stack)
        wrapper_layout.addWidget(group_box)
        return wrapper
    
    def create_control_panel(self):
        """
        Create control panel for particle detection parameters.
        
        Args:
            self: MainWindow instance
            
        Returns:
            QGroupBox: Control panel widget
        """
        group_box = QGroupBox("Particle peak detection parameters")
        self._themed_groupboxes = getattr(self, '_themed_groupboxes', [])
        self._themed_groupboxes.append(group_box)
        
        main_layout = QVBoxLayout(group_box)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 15, 10, 10)
        
        first_row_layout = QHBoxLayout()
        
        search_label = QLabel("Search:")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter elements...")
        self.search_box.textChanged.connect(self.filter_table)
        first_row_layout.addWidget(search_label)
        first_row_layout.addWidget(self.search_box)
        
        first_row_layout.addSpacing(20)
        
        sigma_label = QLabel("Sigma:")
        self.sigma_spinbox = NoWheelSpinBox()
        self.sigma_spinbox.setRange(0.01, 2.0)
        self.sigma_spinbox.setDecimals(3)
        self.sigma_spinbox.setValue(0.55)
        self.sigma_spinbox.setSingleStep(0.01)
        self.sigma_spinbox.setToolTip(
            "Global sigma value for the Compound Poisson LogNormal calculation.\n"
            "In 'Global' mode this applies to every isotope.\n"
            "In 'Per-Isotope' mode it is used as fallback for isotopes without SIA data."
        )
        self.sigma_spinbox.setFixedWidth(80)
        self.sigma_spinbox.valueChanged.connect(self.on_sigma_changed)

        self.sigma_global_radio     = QRadioButton("Global")
        self.sigma_per_isotope_radio = QRadioButton("Per-Isotope")
        self.sigma_global_radio.setChecked(True)
        self.sigma_global_radio.setToolTip(
            "Apply one sigma value to every isotope."
        )
        self.sigma_per_isotope_radio.setToolTip(
            "Use per-isotope sigma from the SIA (falls back to global for unmatched isotopes).\n"
            "You can also edit each isotope's sigma directly in the table."
        )
        self.sigma_global_radio.toggled.connect(self._on_sigma_mode_changed)

        first_row_layout.addWidget(sigma_label)
        first_row_layout.addWidget(self.sigma_spinbox)
        first_row_layout.addWidget(self.sigma_global_radio)
        first_row_layout.addWidget(self.sigma_per_isotope_radio)
        
        first_row_layout.addSpacing(20)

        sid_label = QLabel("Single-Ion Distribution:")
        first_row_layout.addWidget(sid_label)

        self.sia_manager.create_sia_buttons(first_row_layout)
                
        first_row_layout.addStretch()  
        
        main_layout.addLayout(first_row_layout)
        self.parameters_table = ParametersTableView()
        self.parameters_table.setMinimumHeight(180)
        self.parameters_table.cellClicked.connect(self.parameters_table_clicked)
        self.parameters_table.installEventFilter(self)
        self.parameters_table.setFocusPolicy(Qt.StrongFocus)
        self.parameters_table._model.cellChanged.connect(self._on_param_model_changed)
        main_layout.addWidget(self.parameters_table)


        button_layout = QHBoxLayout()

        self._primary_buttons = []

        self.batch_edit_button = QPushButton("Batch Edit Parameters")
        self._primary_buttons.append((self.batch_edit_button, 'fa6s.list-check'))
        self.batch_edit_button.clicked.connect(self.open_batch_parameters_dialog)
        button_layout.addWidget(self.batch_edit_button)
        
    
        self.show_all_signals_button = QPushButton("Multi-Signal View")
        self._primary_buttons.append((self.show_all_signals_button, 'fa6s.chart-column'))
        self.show_all_signals_button.setToolTip("Open multi-signal display with particle detection")
        self.show_all_signals_button.clicked.connect(self.show_signal_selector)
        button_layout.addWidget(self.show_all_signals_button)
                
        self.detect_button = QPushButton("Detect Peaks")
        self._primary_buttons.append((self.detect_button, 'fa6s.bolt'))
        self.detect_button.clicked.connect(self.detect_particles)
        
        button_layout.addWidget(self.detect_button)

        self.saturation_filter_button = QPushButton()
        self._primary_buttons.append((self.saturation_filter_button, 'fa6s.filter'))
        self.saturation_filter_button.setCheckable(True)
        self.saturation_filter_button.setToolTip(
            "Exclude events recorded under non-linear detector response.\n"
            "Detection is based on peak shape: when any isotope shows a wide,\n"
            "flat-topped peak, that time window is excluded for ALL isotopes\n"
            "(results, summary, exports), and the excluded time is subtracted\n"
            "from the analysis time used for concentrations.\n\n"
            "Left-click: toggle the filter on/off.\n"
            "Right-click: customize the criteria and highlighting."
        )
        self.saturation_filter_button.toggled.connect(self.on_saturation_filter_toggled)
        self.saturation_filter_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.saturation_filter_button.customContextMenuRequested.connect(
            self.show_saturation_filter_menu)
        button_layout.addWidget(self.saturation_filter_button)
        self._update_saturation_button_text()
        main_layout.addLayout(button_layout)
        
        self.showing_all_signals = False

        self.update_parameters_table()

        return group_box
    
    def create_summary_widget(self):
        """
        Create widget for particle summary statistics display.
        
        Args:
            self: MainWindow instance
            
        Returns:
            QGroupBox: Summary statistics widget
        """
        group_box = QGroupBox("Particle summary statistics")
        self._themed_groupboxes.append(group_box)
        
        layout = QVBoxLayout(group_box)
        
        self.summary_label = QLabel("Select an element to view summary statistics")
        self.summary_label.setTextFormat(Qt.RichText)
        self.summary_label.setAlignment(Qt.AlignCenter)
        self.summary_label.setWordWrap(True)
        self.summary_label.setMinimumHeight(70) 
        
        layout.addWidget(self.summary_label)
        
        return group_box
        
    #----------------------------------------------------------------------------------------------------------
    #------------------------------------UI creation - Tables and results --------------------------------------------
    #----------------------------------------------------------------------------------------------------------
        
    def create_results_container(self):
        """
        Create container for results display with element and particle tables.
        
        Args:
            self: MainWindow instance
            
        Returns:
            QWidget: Container widget with results display elements
        """
        container = QWidget()
        self._results_container = container
        layout = QVBoxLayout(container)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(8)
        header_widget = QWidget()
        self._results_header_widget = header_widget
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(15, 12, 15, 12)
        header_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("Results Display")
        self._results_title_label = title_label
        title_row.addWidget(title_label)
        
        title_row.addStretch()

        perf_tip = QLabel("Tip: Keep tables unchecked for better performance during analysis")
        self._perf_tip_label = perf_tip
        title_row.addWidget(perf_tip)
        
        header_layout.addLayout(title_row)
        checkboxes_layout = QHBoxLayout()
        checkboxes_layout.setContentsMargins(0, 5, 0, 0)
        checkboxes_layout.setSpacing(20)
        self.show_element_results_checkbox = self.create_enhanced_checkbox(
            "Single Element Results", 
            "Show detailed results for individual element detection.\n"
            "Note: Updating this table can slow down analysis when processing many peaks."
        )
        
        self.show_particle_results_checkbox = self.create_enhanced_checkbox(
            "Multi-Element Particles", 
            "Show particles containing multiple elements.\n"
            "Note: This table updates after particle detection and can be resource-intensive."
        )
        
        checkboxes_layout.addWidget(self.show_element_results_checkbox)
        checkboxes_layout.addWidget(self.show_particle_results_checkbox)
        checkboxes_layout.addStretch()
        
        header_layout.addLayout(checkboxes_layout)
        layout.addWidget(header_widget)
        self.element_results_container = QWidget()
        element_layout = QVBoxLayout(self.element_results_container)
        element_layout.setContentsMargins(0, 5, 0, 0)
        
        element_header = self.create_table_header("Single Element Results", "#e3f2fd", "#1976d2")
        self._element_header_label = element_header
        self._element_header_colors = ("#e3f2fd", "#1976d2")
        element_layout.addWidget(element_header)
        element_layout.addWidget(self.create_results_table())
        
        self.particle_results_container = QWidget()
        particle_layout = QVBoxLayout(self.particle_results_container)
        particle_layout.setContentsMargins(0, 5, 0, 0)
        
        particle_header = self.create_table_header("Multi-Element Particle Results", "#e4cbb8", "#eb7318")
        self._particle_header_label = particle_header
        self._particle_header_colors = ("#e4cbb8", "#eb7318")
        particle_layout.addWidget(particle_header)
        particle_layout.addWidget(self.create_multi_element_table())
        self.element_results_container.setVisible(False)
        self.particle_results_container.setVisible(False)
        
        layout.addWidget(self.element_results_container)
        layout.addWidget(self.particle_results_container)
        
        self.show_element_results_checkbox.toggled.connect(self.toggle_element_results)
        self.show_particle_results_checkbox.toggled.connect(self.toggle_particle_results)
        
        return container

    def create_sample_table(self):
        """
        Create sample list table widget.
        
        Args:
            self: MainWindow instance
            
        Returns:
            QTableWidget: Configured sample table
        """
        self.sample_table = QTableWidget()
        self.sample_table.setColumnCount(2)
        self.sample_table.setHorizontalHeaderLabels(['Sample Name', 'Status'])
        self.sample_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sample_table.itemClicked.connect(self.on_sample_selected)
        self.sample_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sample_table.customContextMenuRequested.connect(self.show_sample_context_menu)
        
        self.sample_table.keyPressEvent = self.sample_table_key_press
        self.sample_table.setFocusPolicy(Qt.StrongFocus)
        
        return self.sample_table
    
    def create_results_table(self):
        """
        Create table for single element detection results.
        
        Args:
            self: MainWindow instance
            
        Returns:
            QTableWidget: Configured results table
        """
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        headers = [
            'Element', 'Peak Start (s)', 'Peak End (s)', 'Total Counts',
            'Peak Height (counts)', 'Height/Threshold'
        ]
        self.results_table.setHorizontalHeaderLabels(headers)
        self.results_table.hideColumn(0)
        
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setMinimumHeight(200)
        self.results_table.itemSelectionChanged.connect(self.highlight_selected_particle)
        self.results_table.setSortingEnabled(True)
        return self.results_table
    
    def create_multi_element_table(self):
        """
        Create table for multi-element particle results.
        
        Args:
            self: MainWindow instance
            
        Returns:
            QTableWidget: Configured multi-element table
        """
        self.multi_element_table = QTableWidget()
        self.multi_element_table.setMinimumHeight(200)
        self.multi_element_table.setSortingEnabled(True)
        self.multi_element_table.itemSelectionChanged.connect(self.highlight_multi_element_particle)
        return self.multi_element_table
    
    def create_table_header(self, title, bg_color, text_color):
        """
        Create styled header label for tables.
        
        Args:
            self: MainWindow instance
            title (str): Header text
            bg_color (str): Background color (hex)
            text_color (str): Text color (hex)
            
        Returns:
            QLabel: Styled header label
        """
        header = QLabel(title)
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 16px;
                font-weight: bold;
                color: {text_color};
                padding: 12px 15px;
                background-color: {bg_color};
                border-radius: 6px;
                border: #FFFFFF;
            }}
        """)
        return header

    def create_enhanced_checkbox(self, text, tooltip):
        """
        Create styled checkbox with custom appearance.
        
        Args:
            self: MainWindow instance
            text (str): Checkbox label text
            tooltip (str): Tooltip text
            
        Returns:
            QCheckBox: Configured checkbox widget
        """
        checkbox = QCheckBox(text)
        if not hasattr(self, '_enhanced_checkboxes'):
            self._enhanced_checkboxes = []
        self._enhanced_checkboxes.append(checkbox)
        checkbox.setStyleSheet(enhanced_checkbox_qss(theme.palette))
        checkbox.setToolTip(tooltip)
        checkbox.setChecked(False)
        
        return checkbox
    
    #----------------------------------------------------------------------------------------------------------
    #------------------------------------UI interations --------------------------------------------
    #----------------------------------------------------------------------------------------------------------
   
    def toggle_sidebar(self):
        """
        Animate sidebar visibility toggle.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        current_width = self.sidebar.maximumWidth()
        if getattr(self, 'animation_group', None) is not None:
            try:
                self.animation_group.stop()
                self.animation_group.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.animation_group = None

        opening = not self.sidebar_visible
        target_width = self.sidebar_width if opening else 0

        self.user_action_logger.log_action(
            'CLICK',
            'Sidebar expanded' if opening else 'Sidebar collapsed',
            {'action': 'expand' if opening else 'collapse'})

        if opening:
            self.sidebar.show()
            self.toggle_button.show()
            self.toggle_button.setIcon(qta.icon('fa6s.arrow-left', color=theme.palette.text_on_sidebar))
            self.edge_strip.hide()
            if hasattr(self, 'sidebar_grip'):
                self.sidebar_grip.show()
        else:
            self.toggle_button.hide()
            self.edge_strip.show()
            if hasattr(self, 'sidebar_grip'):
                self.sidebar_grip.hide()

        span = max(1, self.sidebar_width)
        fraction = abs(target_width - current_width) / span
        duration = max(120, int(240 * fraction))
        easing = QEasingCurve.OutCubic

        self.animation = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self.animation.setDuration(duration)
        self.animation.setEasingCurve(easing)
        self.animation.setStartValue(current_width)
        self.animation.setEndValue(target_width)

        self.animation_max = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self.animation_max.setDuration(duration)
        self.animation_max.setEasingCurve(easing)
        self.animation_max.setStartValue(current_width)
        self.animation_max.setEndValue(target_width)

        self.animation_group = QParallelAnimationGroup()
        self.animation_group.addAnimation(self.animation)
        self.animation_group.addAnimation(self.animation_max)
        self.animation_group.finished.connect(self.on_animation_finished)
        self.animation_group.start()

        self.sidebar_visible = opening

    def _apply_sidebar_grip_style(self):
        """Style the resize grip's divider line and pill holder for the theme."""
        if not hasattr(self, 'sidebar_grip'):
            return
        p = theme.palette
        self.sidebar_grip.setStyleSheet(
            "QWidget#sidebarGrip { background-color: transparent; }"
            f"QWidget#gripLine {{ background-color: {p.accent}; }}"
            f"QWidget#gripPill {{ background-color: {p.text_muted}; border-radius: 2px; }}"
        )

    def _sidebar_grip_press(self, event):
        """Begin a sidebar resize drag."""
        if event.button() == Qt.LeftButton:
            self._grip_dragging = True
            event.accept()

    def _sidebar_grip_move(self, event):
        """Resize the sidebar live while dragging the grip."""
        if not getattr(self, '_grip_dragging', False):
            return
        left = self.sidebar.mapToGlobal(QPoint(0, 0)).x()
        new_width = int(event.globalPosition().x()) - left
        new_width = max(self.sidebar_min_width,
                        min(self.sidebar_max_width, new_width))
        self.sidebar_width = new_width
        self.sidebar.setFixedWidth(new_width)
        event.accept()

    def _sidebar_grip_release(self, event):
        """End a sidebar resize drag and remember the chosen width."""
        self._grip_dragging = False
        try:
            QSettings("IsotopeTrack", "IsotopeTrack").setValue(
                "ui/sidebar_width", self.sidebar_width)
        except Exception:
            pass
        event.accept()

    def on_animation_finished(self):
        """
        Clean up after sidebar animation completes.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        if not self.sidebar_visible:
            self.sidebar.hide()
            self.toggle_button.hide()  
            self.edge_strip.show()  
        else:
            self.toggle_button.show() 
            self.edge_strip.hide()  
        
        self.animation = None
        self.animation_max = None
        if getattr(self, 'animation_group', None) is not None:
            try:
                self.animation_group.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.animation_group = None
        
    def toggle_info(self):
        """
        Toggle visibility of sample information tooltip.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        if not hasattr(self, 'info_tooltip'):
            self.info_tooltip = InfoTooltip(self)
            self.info_tooltip.set_trigger_widget(self.info_button)
            
        if self.info_tooltip.isVisible():
            self.info_tooltip.hide()
        else:
            active_samples = len(self.data_by_sample) if hasattr(self, 'data_by_sample') else 0
            total_elements = sum(len(isotopes) for isotopes in self.selected_isotopes.values()) if self.selected_isotopes else 0
            accuracy = self.calculate_accuracy()

            analysis_date_info = None
            if self.current_sample and self.current_sample in self.sample_analysis_dates:
                analysis_date_info = self.sample_analysis_dates[self.current_sample]

            self.info_tooltip.update_stats(
                active_samples, 
                total_elements, 
                accuracy, 
                analysis_date_info 
            )
            
            self.info_tooltip.update_sample_content(
                self.current_sample,
                self.selected_isotopes,
                getattr(self, 'detected_peaks', {}),
                getattr(self, 'multi_element_particles', []),
                periodic_table_widget=self.periodic_table_widget
            )

            button_pos = self.info_button.mapToGlobal(self.info_button.rect().topLeft())
            tooltip_pos = QPoint(button_pos.x() - self.info_tooltip.width() - 10, button_pos.y())
            self.info_tooltip.move(tooltip_pos)
            self.info_tooltip.show()

    def hide_info_tooltip(self, event):
        """
        Hide the information tooltip.
        
        Args:
            self: MainWindow instance
            event: QEvent object
            
        Returns:
            None
        """
        if hasattr(self, 'info_tooltip'):
            self.info_tooltip.hide()
            
    def toggle_fullscreen(self):
        """
        Toggle fullscreen mode.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        if self.isFullScreen():
            self.exit_fullscreen()

    def exit_fullscreen(self):
        """
        Exit fullscreen mode.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.showNormal()
        self.status_label.setText("Exited fullscreen mode")

    def keyPressEvent(self, event):
        """
        Handle keyboard events.
        
        Args:
            self: MainWindow instance
            event: QKeyEvent object
            
        Returns:
            None
        """
        if event.key() == Qt.Key_F11:
            self.toggle_fullscreen()
        elif event.key() == Qt.Key_Escape and self.isFullScreen():
            self.exit_fullscreen()
        else:
            super().keyPressEvent(event)
                
    def resizeEvent(self, event):
        """
        Handle window resize events.
        
        Args:
            self: MainWindow instance
            event: QResizeEvent object
            
        Returns:
            None
        """
        super().resizeEvent(event)
        if hasattr(self, 'sidebar') and getattr(self, 'sidebar_visible', True):
            self.sidebar.setFixedWidth(self.sidebar_width)
        
        if hasattr(self, 'content_area'):
            self.content_area.setSizes([int(self.height() * 0.7), int(self.height() * 0.3)])
            
        
    #----------------------------------------------------------------------------------------------------------
    #------------------------------------Data loading and import --------------------------------------------
    #----------------------------------------------------------------------------------------------------------

    def _has_loaded_samples(self):
        """
        Check whether any sample data is currently loaded in this window.

        Args:
            self: MainWindow instance

        Returns:
            bool: True if at least one sample is registered, False otherwise.
        """
        return bool(getattr(self, 'sample_to_folder_map', None)) or \
               bool(getattr(self, 'data_by_sample', None))

    def _probe_masses(self, paths, source_type):
        """
        Quickly probe the mass list of the first accessible path.

        Used before deciding whether a new set of files can be appended to the
        current session. For NU and TOFWERK this calls ``get_masses_only``
        without loading the full signals. CSV is handled separately because
        masses come from the structure-dialog config.

        Args:
            self: MainWindow instance
            paths (list): Candidate data paths (folders or files)
            source_type (str): One of "nu", "tofwerk", "csv"

        Returns:
            np.ndarray | None: Array of masses from the first readable path,
            or None if none could be probed.
        """
        if not paths or source_type == "csv":
            return None
        for p in paths:
            try:
                masses = DataProcessThread.get_masses_only(str(p))
                if masses is not None and len(masses) > 0:
                    return np.asarray(masses, dtype=float)
            except Exception:
                continue
        return None

    def _prepare_for_load(self, source_type, paths, new_masses=None):
        """
        Decide how to handle a new load request against the current session.

        If nothing is loaded yet, behaves as a fresh load. Otherwise checks
        source-type compatibility (offers "open in new window" on mismatch)
        and mass-range compatibility (offers Ignore / New Window / Cancel on
        mismatch).

        Args:
            self: MainWindow instance
            source_type (str): "nu", "tofwerk", or "csv"
            paths (list): Paths the user is trying to load
            new_masses (np.ndarray | None): Probed masses, if already known

        Returns:
            tuple[bool, bool]: (proceed, append_mode). If proceed is False
            the caller must return immediately without loading.
        """
        if not self._has_loaded_samples():
            return True, False

        if new_masses is None and paths:
            new_masses = self._probe_masses(paths, source_type)

        current_type = getattr(self, 'current_data_source_type', None)

        if current_type and current_type != source_type:
            type_labels = {"nu": "NU folders", "tofwerk": "TOFWERK (.h5)", "csv": "CSV/Excel"}
            cur_label = type_labels.get(current_type, current_type.upper())
            new_label = type_labels.get(source_type, source_type.upper())
            resp = QMessageBox.question(
                self,
                "Different file type",
                f"The currently loaded data is of type {cur_label}, but the files "
                f"you are trying to add are of type {new_label}.\n\n"
                "Different file types can't be mixed in the same window.\n\n"
                "Open the new files in a separate analysis window?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if resp == QMessageBox.Yes:
                self._open_in_new_window(paths, source_type)
            return False, False

        if (new_masses is not None and len(new_masses) > 0
                and getattr(self, 'all_masses', None)):
            current = np.asarray(self.all_masses, dtype=float)
            new = np.asarray(new_masses, dtype=float)
            tol = 0.5
            c_min, c_max = float(current.min()), float(current.max())
            n_min, n_max = float(new.min()), float(new.max())
            range_diff = max(abs(c_min - n_min), abs(c_max - n_max))
            overlap = int(sum(1 for nm in new if np.min(np.abs(current - nm)) <= tol))
            overlap_ratio = overlap / len(new) if len(new) else 0.0

            if range_diff > 1.0 or overlap_ratio < 0.5:
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowTitle("Different mass range")
                msg.setText(
                    "The new data has a different mass range than the currently loaded data.\n\n"
                    f"Loaded:  {c_min:.2f} – {c_max:.2f} u  ({len(current)} masses)\n"
                    f"New:     {n_min:.2f} – {n_max:.2f} u  ({len(new)} masses)\n"
                    f"Common:  {overlap}/{len(new)} masses match within ±{tol} u\n\n"
                    "What would you like to do?"
                )
                btn_ignore = msg.addButton("Ignore and Add", QMessageBox.AcceptRole)
                btn_window = msg.addButton("Open in New Window", QMessageBox.ActionRole)
                btn_cancel = msg.addButton("Cancel", QMessageBox.RejectRole)
                msg.setDefaultButton(btn_cancel)
                msg.exec()
                clicked = msg.clickedButton()
                if clicked is btn_ignore:
                    return True, True
                elif clicked is btn_window:
                    self._open_in_new_window(paths, source_type)
                    return False, False
                else:
                    return False, False

        return True, True

    def _open_in_new_window(self, paths, source_type):
        """
        Open a fresh MainWindow and auto-load the given paths into it.

        Args:
            self: MainWindow instance
            paths (list): Paths to load
            source_type (str): "nu", "tofwerk", or "csv"

        Returns:
            None
        """
        try:
            new_window = MainWindow()
            new_window.showMaximized()
            new_window.raise_()
            new_window.activateWindow()

            paths_copy = list(paths)

            def _dispatch():
                try:
                    if source_type == "nu":
                        new_window.process_folders(paths_copy)
                    elif source_type == "tofwerk":
                        new_window.process_tofwerk_files(paths_copy)
                    elif source_type == "csv":
                        new_window.handle_csv_import(paths_copy)
                except Exception as exc:
                    self.logger.error(f"Error loading into new window: {exc}")

            QTimer.singleShot(150, _dispatch)
            self.status_label.setText("Opened files in a new window")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open new window: {e}")
            self.logger.error(f"Error opening new window: {e}")

    def _load_selected_isotopes_for_new_samples(self, sample_names):
        """
        Load currently-selected isotopes for samples added in append mode.

        Without this step, samples appended after isotopes were already picked
        would stay empty until the user toggled an isotope in the periodic
        table. CSV samples are skipped because they go through their own
        processing pipeline.

        Args:
            self: MainWindow instance
            sample_names (list): Names of newly added samples

        Returns:
            None
        """
        if not sample_names or not self.selected_isotopes:
            return

        masses_to_load = []
        for isotopes in self.selected_isotopes.values():
            masses_to_load.extend(isotopes)
        if not masses_to_load:
            return
        pending = [
            (name, self.sample_to_folder_map.get(name)) for name in sample_names
        ]
        pending = [
            (name, fp) for name, fp in pending
            if fp and not str(fp).endswith('.csv')
        ]
        if not pending:
            return

        total = len(pending)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        for i, (sample_name, folder_path) in enumerate(pending):
            self.status_label.setText(
                f"Loading data for new sample {i+1}/{total}: {sample_name}")
            QApplication.processEvents()
            try:
                thread = DataProcessThread(folder_path, masses_to_load, sample_name)
                thread.finished.connect(self.handle_new_elements_finished)
                thread.error.connect(self.handle_error)

                def _on_thread_progress(value, _i=i):
                    overall = ((_i + value / 100.0) / total) * 100.0
                    self.progress_bar.setValue(int(overall))
                    QApplication.processEvents()
                thread.progress.connect(_on_thread_progress)

                loop = QEventLoop()
                thread.finished.connect(loop.quit)
                thread.error.connect(loop.quit)
                thread.start()
                loop.exec()

                try:
                    thread.progress.disconnect()
                    thread.finished.disconnect()
                    thread.error.disconnect()
                except (RuntimeError, TypeError):
                    pass
                thread.deleteLater()
            except Exception as e:
                self.logger.error(
                    f"Error loading selected isotopes for {sample_name}: {e}")

        self.progress_bar.setValue(100)
        self.status_label.setText(f"Loaded data for {total} new sample(s)")
        self.progress_bar.setVisible(False)


    @log_user_action('MENU', 'File -> Open Folder')
    def select_folder(self):
        """
        Show dialog to select data source type and load data.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Data Source")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(350)
        dialog.setStyleSheet(dialog_qss(theme.palette))
        layout = QVBoxLayout(dialog)

        _p = theme.palette

        instruction = QLabel("Choose your data source type:")
        instruction.setStyleSheet(
            f"font-size: 14px; font-weight: bold; margin: 10px; color: {_p.text_primary};"
        )
        layout.addWidget(instruction)

        folder_radio = QRadioButton("NU Folders (with run.info files)", dialog)
        csv_radio = QRadioButton("Data Files (*.csv *.txt *.xls *.xlsx *.xlsm *.xlsb)", dialog)
        tofwerk_radio = QRadioButton("TOFWERK Files (*.h5)", dialog)
        folder_radio.setChecked(True)
        
        radio_layout = QVBoxLayout()
        radio_layout.addWidget(folder_radio)
        radio_layout.addWidget(csv_radio)
        radio_layout.addWidget(tofwerk_radio)
        layout.addLayout(radio_layout)

        desc_style = f"color: {_p.text_secondary}; margin-left: 20px; font-size: 11px;"

        folder_desc = QLabel("• Select folders containing NU instrument data with run.info files\n• Supports multiple folders for batch processing")
        folder_desc.setStyleSheet(desc_style)
        
        csv_desc = QLabel("• Select Data Files (*.csv *.txt *.xls *.xlsx *.xlsm *.xlsb) with mass spectrometry data\n• Configure column mappings and time settings")
        csv_desc.setStyleSheet(desc_style)
        
        tofwerk_desc = QLabel("• Select TOFWERK .h5 files from TofDAQ acquisitions\n• Supports multiple files for batch processing")
        tofwerk_desc.setStyleSheet(desc_style)
        
        layout.addWidget(folder_desc)
        layout.addWidget(csv_desc)
        layout.addWidget(tofwerk_desc)
        layout.addStretch()

        button_box = QHBoxLayout()
        ok_button = QPushButton("Continue", dialog)
        cancel_button = QPushButton("Cancel", dialog)

        cancel_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {_p.bg_tertiary};
                color: {_p.text_primary};
                border: 1px solid {_p.border};
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {_p.bg_hover};
                border: 1px solid {_p.accent};
            }}
        """)

        ok_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {_p.success};
                color: {_p.text_inverse};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {_p.accent_hover};
            }}
        """)
        
        button_box.addStretch()
        button_box.addWidget(ok_button)
        button_box.addWidget(cancel_button)
        layout.addLayout(button_box)

        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)

        if dialog.exec() == QDialog.Accepted:
            if folder_radio.isChecked():
                self.select_folders()
            elif csv_radio.isChecked():
                self.select_csv_files()
            else:
                self.select_tofwerk_files()
                
    def get_unique_sample_name(self, base_name):
        """
        Generate a unique sample name by appending a number if name already exists.
        
        Args:
            self: MainWindow instance
            base_name (str): Original sample name
            
        Returns:
            str: Unique sample name with number suffix if necessary
        """
        if base_name not in self.sample_to_folder_map:
            return base_name
        
        counter = 1
        while True:
            new_name = f"{base_name} ({counter})"
            if new_name not in self.sample_to_folder_map:
                return new_name
            counter += 1
                    
    def select_folders(self):
        """
        Select NU folders for data loading.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.user_action_logger.log_action('FILE_OP', 'Open multiple NU folders dialog')
        try:
            file_dialog = QFileDialog(self)
            file_dialog.setFileMode(QFileDialog.Directory)
            file_dialog.setOption(QFileDialog.DontUseNativeDialog, True)
            
            list_view = file_dialog.findChild(QListView)
            tree_view = file_dialog.findChild(QTreeView)
            
            if list_view:
                list_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
            if tree_view:
                tree_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
            
            if file_dialog.exec() == QDialog.Accepted:
                selected_paths = file_dialog.selectedFiles()
                
                if not selected_paths:
                    return

                self.user_action_logger.log_file_operation(
                    'OPEN',
                    ', '.join(selected_paths[:3]) + ('…' if len(selected_paths) > 3 else ''),
                    {'folder_count': len(selected_paths)})
                self.process_folders(selected_paths)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error selecting folders: {str(e)}")
            
    def check_data_source_accessible(self, path):
        """
        Check if a data source path is still accessible.
        
        Args:
            self: MainWindow instance
            path: Path to data source (folder or file)
            
        Returns:
            bool: True if accessible, False otherwise
        """
        try:
            path_obj = Path(path)
            
            if not path_obj.exists():
                return False
            
            if path_obj.is_dir():
                try:
                    list(path_obj.iterdir())
                    return True
                except (PermissionError, OSError):
                    return False
            
            elif path_obj.is_file():
                try:
                    with open(path_obj, 'rb') as f:
                        f.read(1)  
                    return True
                except (PermissionError, OSError, IOError):
                    return False
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking accessibility of {path}: {str(e)}")
            return False

    def verify_all_data_sources(self):
        """
        Verify that all loaded data sources are still accessible.
        
        Args:
            self: MainWindow instance
            
        Returns:
            tuple: (all_accessible: bool, inaccessible_samples: list)
        """
        inaccessible_samples = []
        
        for sample_name, source_path in self.sample_to_folder_map.items():
            if not self.check_data_source_accessible(source_path):
                inaccessible_samples.append((sample_name, str(source_path)))
        
        return len(inaccessible_samples) == 0, inaccessible_samples

    def prompt_reconnect_data_source(self, inaccessible_samples):
        """
        Prompt user to reconnect inaccessible data sources.
        
        Args:
            self: MainWindow instance
            inaccessible_samples: List of (sample_name, path) tuples
            
        Returns:
            bool: True if user wants to reconnect, False to cancel
        """
        from PySide6.QtWidgets import QMessageBox, QTextEdit, QVBoxLayout, QDialog, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Data Sources Not Accessible")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout(dialog)
        
        message = QLabel(
            "<b>Some data sources are no longer accessible.</b><br><br>"
            "This usually happens when an external drive is disconnected. "
            "Adding new elements requires access to the original data files.<br><br>"
            "<b>Inaccessible data sources:</b>"
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_list = ""
        for sample_name, path in inaccessible_samples:
            text_list += f"• {sample_name}\n  Path: {path}\n\n"
        text_edit.setPlainText(text_list)
        text_edit.setMaximumHeight(200)
        layout.addWidget(text_edit)
        
        instruction = QLabel(
            "<b>To add new elements:</b><br>"
            "1. Reconnect the external drive or make the data accessible<br>"
            "2. Click 'Retry' to check accessibility again<br>"
            "3. Or click 'Cancel' to abort adding new elements"
        )
        instruction.setWordWrap(True)
        layout.addWidget(instruction)
        
        button_layout = QHBoxLayout()
        retry_button = QPushButton("Retry")
        cancel_button = QPushButton("Cancel")
        
        retry_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(retry_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        return dialog.exec() == QDialog.Accepted
    
    def rebuild_isotope_dict_from_set(self, isotope_set):
        """
        Rebuild isotope dictionary from a set of (element, isotope) tuples.
        
        Args:
            self: MainWindow instance
            isotope_set: Set of (element, isotope) tuples
            
        Returns:
            dict: Dictionary mapping element to list of isotopes
        """
        isotope_dict = {}
        for element, isotope in isotope_set:
            if element not in isotope_dict:
                isotope_dict[element] = []
            isotope_dict[element].append(isotope)
        return isotope_dict
                    
    def select_csv_files(self):
        """
        Select CSV/Excel files for data loading.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.user_action_logger.log_action('FILE_OP', 'Open CSV / Excel files dialog')
        try:
            if not CSVStructureDialog:
                QMessageBox.critical(self, "Import Error", 
                    "File import functionality is not available. Please ensure the import_csv_dialogs.py file is present.")
                return
                
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Select Data Files",
                "",
                "Data Files (*.csv *.txt *.xls *.xlsx *.xlsm *.xlsb);;CSV Files (*.csv);;Text Files (*.txt);;Excel Files (*.xls *.xlsx *.xlsm *.xlsb);;All Files (*)"
            )
            
            if file_paths:
                self.user_action_logger.log_file_operation(
                    'OPEN', f'{len(file_paths)} CSV/Excel file(s)',
                    {'files': [str(p) for p in file_paths[:5]]})
                self.handle_csv_import(file_paths)
                
        except Exception as e:
            self.logger.error(f"Error selecting files: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error selecting files: {str(e)}")
                
    def select_tofwerk_files(self):
        """
        Select TOFWERK .h5 files for processing.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.user_action_logger.log_action('FILE_OP', 'Open TOFWERK .h5 files dialog')
        try:
            h5_files, _ = QFileDialog.getOpenFileNames(
                self,
                "Select TOFWERK .h5 Files",
                "",
                "TOFWERK Files (*.h5);;All Files (*)"
            )
            
            if h5_files:
                self.user_action_logger.log_file_operation(
                    'OPEN', f'{len(h5_files)} TOFWERK .h5 file(s)',
                    {'files': [str(p) for p in h5_files[:5]]})
                self.process_tofwerk_files(h5_files)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error selecting TOFWERK files: {str(e)}")
            
    def process_folders(self, folder_paths):
        """
        Process selected NU folders.
        
        Args:
            self: MainWindow instance
            folder_paths (list): List of folder paths
            
        Returns:
            None
        """
        self.log_status(f"Processing {len(folder_paths)} folders")

        probe = self._probe_masses(folder_paths, "nu")
        proceed, append_mode = self._prepare_for_load("nu", folder_paths, probe)
        if not proceed:
            return

        newly_added_samples = []

        if not append_mode:
            self.folder_paths = []
            self.sample_to_folder_map.clear()
            self.data_by_sample.clear()
            self.time_array_by_sample.clear()
            self.current_sample = None
            self.all_masses = None
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        overlay = QWidget(self)
        overlay.setGeometry(self.rect())
        overlay.setStyleSheet("background-color: rgba(0, 0, 0, 50);")
        overlay.show()
        
        try:
            total_paths = len(folder_paths)
            all_masses_from_folders = (
                list(self.all_masses) if (append_mode and self.all_masses) else []
            )
            
            for i, path in enumerate(folder_paths):
                progress = int((i / total_paths) * 50)
                self.progress_bar.setValue(progress)
                self.status_label.setText(f"Processing folder {i+1}/{total_paths}: {Path(path).name}")
                QApplication.processEvents()
                
                try:
                    run_info_path = Path(path) / "run.info"
                    if run_info_path.exists():
                        with open(run_info_path, "r") as fp:
                            run_info = json.load(fp)
                        sample_name = run_info.get("SampleName", Path(path).name)
                        sample_name = self.get_unique_sample_name(sample_name)
                                            
                        masses = DataProcessThread.get_masses_only(str(path))
                        all_masses_from_folders.extend(masses)
                        if self.all_masses is None:
                            self.all_masses = masses
                        self.folder_paths.append(path)
                        self.sample_to_folder_map[sample_name] = path
                        newly_added_samples.append(sample_name)
                        
                        self.status_label.setText(f"Successfully loaded {sample_name} ({i+1}/{total_paths})")
                        
                except Exception as e:
                    QMessageBox.warning(self, "Warning", 
                        f"Error loading folder: {Path(path).name}\n{str(e)}")
                    self.logger.error(f"Error loading folder {Path(path).name}: {str(e)}")
                    continue
            if all_masses_from_folders:
                unique_masses = sorted(list(set(all_masses_from_folders)))
                self.all_masses = unique_masses
            for i, path in enumerate(self.folder_paths):
                progress = 50 + int((i / len(self.folder_paths)) * 50)
                self.progress_bar.setValue(progress)
                sample_name = next((name for name, p in self.sample_to_folder_map.items() if p == path), Path(path).name)
                self.status_label.setText(f"Finalizing sample {i+1}/{len(self.folder_paths)}: {sample_name}")
                QApplication.processEvents()
            
            self.progress_bar.setValue(100)
            self.status_label.setText(f"Successfully loaded {len(self.folder_paths)} folder(s)")
            overlay.hide()
            overlay.deleteLater()

            self.current_data_source_type = "nu"

            if append_mode and newly_added_samples and self.selected_isotopes:
                self.status_label.setText("Loading selected isotopes for new samples...")
                QApplication.processEvents()
                self._load_selected_isotopes_for_new_samples(newly_added_samples)

            if self.periodic_table_widget and self.all_masses:
                self.periodic_table_widget.update_available_masses(self.all_masses)
                self.periodic_table_widget.validate_selections_against_new_range()
            if self.all_masses is not None:
                self.show_periodic_table_after_load()
            else:
                raise ValueError("No valid data was loaded")         
        except Exception as e:
            if 'overlay' in locals():
                overlay.hide()
                overlay.deleteLater()
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "Error", f"Error processing folders: {str(e)}")
            self.logger.error(f"Error processing folders: {str(e)}")
    
    def process_csv_files_with_isotopes(self, selected_isotopes):
        """
        Process CSV files with selected isotopes.
        
        Args:
            self: MainWindow instance
            selected_isotopes (dict): Dictionary of selected isotopes
            
        Returns:
            None
        """
        try:
            if not self.csv_config: 
                raise ValueError("No CSV configuration available")
                    
            filtered_config = self.filter_csv_config_by_isotopes(self.csv_config, selected_isotopes)
            
            if not any(file_config['mappings'] for file_config in filtered_config['files']):
                QMessageBox.warning(self, "No Matching Isotopes", 
                                "None of the selected isotopes match the configured CSV columns.")
                return

            append_mode = bool(getattr(self, '_pending_csv_append_mode', False))

            if not append_mode:
                self.sample_to_folder_map.clear()
                self.data_by_sample.clear()
                self.time_array_by_sample.clear()
                self.current_sample = None
            else:
                already_loaded_paths = {
                    str(p) for p in self.sample_to_folder_map.values()
                }
                filtered_config = dict(filtered_config)
                filtered_config['files'] = [
                    fc for fc in filtered_config['files']
                    if str(fc.get('path', '')) not in already_loaded_paths
                ]
                if not filtered_config['files']:
                    self.status_label.setText(
                        "All selected CSV files are already loaded")
                    self._pending_csv_append_mode = False
                    return
            
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("Processing CSV files...")


            if getattr(self, 'csv_thread', None) is not None:
                if self.csv_thread.isRunning():
                    self.csv_thread.quit()
                    self.csv_thread.wait(3000) 
                try:
                    self.csv_thread.progress.disconnect()
                    self.csv_thread.finished.disconnect()
                    self.csv_thread.error.disconnect()
                except (RuntimeError, TypeError):
                    pass
                self.csv_thread.deleteLater()
                self.csv_thread = None
            
            self.csv_thread = CSVDataProcessThread(filtered_config, self)
            self.csv_thread.progress.connect(self.update_progress)
            self.csv_thread.finished.connect(self.handle_csv_finished)
            self.csv_thread.error.connect(self.handle_error)
            self.csv_thread.start()

            self._pending_csv_append_mode = False
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "Error", f"Error processing CSV files: {str(e)}")
            self.logger.error(f"Error processing CSV files: {str(e)}")

    def process_tofwerk_files(self, h5_file_paths):
        """
        Process selected TOFWERK .h5 files.
        
        Args:
            self: MainWindow instance
            h5_file_paths (list): List of .h5 file paths
            
        Returns:
            None
        """
        try:
            self.log_status(f"Processing {len(h5_file_paths)} TOFWERK files")

            probe = self._probe_masses(h5_file_paths, "tofwerk")
            proceed, append_mode = self._prepare_for_load("tofwerk", h5_file_paths, probe)
            if not proceed:
                return

            newly_added_samples = []

            if not append_mode:
                self.folder_paths = []
                self.sample_to_folder_map.clear()
                self.data_by_sample.clear()
                self.time_array_by_sample.clear()
                self.current_sample = None
                self.all_masses = None
            
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            overlay = QWidget(self)
            overlay.setGeometry(self.rect())
            overlay.setStyleSheet("background-color: rgba(0, 0, 0, 50);")
            overlay.show()
            
            try:
                total_files = len(h5_file_paths)
                all_masses_from_files = (
                    list(self.all_masses) if (append_mode and self.all_masses) else []
                )
                
                for i, h5_path in enumerate(h5_file_paths):
                    progress = int((i / total_files) * 50)
                    self.progress_bar.setValue(progress)
                    h5_file = Path(h5_path)
                    self.status_label.setText(f"Processing TOFWERK file {i+1}/{total_files}: {h5_file.name}")
                    QApplication.processEvents()
                    
                    try:
                        sample_name = h5_file.stem
                        sample_name = self.get_unique_sample_name(sample_name)

                        masses = DataProcessThread.get_masses_only(str(h5_path))
                        if masses is not None:
                            all_masses_from_files.extend(masses)
                            if self.all_masses is None:
                                self.all_masses = masses
                            self.folder_paths.append(h5_path)
                            self.sample_to_folder_map[sample_name] = h5_path
                            newly_added_samples.append(sample_name)
                            
                            self.status_label.setText(f"Successfully loaded {sample_name} ({i+1}/{total_files})")
                        else:
                            self.logger.warning(f"Could not extract masses from {h5_file.name}")
                            
                    except Exception as e:
                        QMessageBox.warning(self, "Warning", 
                            f"Error loading TOFWERK file: {h5_file.name}\n{str(e)}")
                        self.logger.error(f"Error loading TOFWERK file {h5_file.name}: {str(e)}")
                        continue
                
                if all_masses_from_files:
                    unique_masses = sorted(list(set(all_masses_from_files)))
                    self.all_masses = unique_masses
                
                for i, h5_path in enumerate(self.folder_paths):
                    progress = 50 + int((i / len(self.folder_paths)) * 50)
                    self.progress_bar.setValue(progress)
                    sample_name = next((name for name, p in self.sample_to_folder_map.items() if p == h5_path), Path(h5_path).stem)
                    self.status_label.setText(f"Finalizing TOFWERK file {i+1}/{len(self.folder_paths)}: {sample_name}")
                    QApplication.processEvents()
                
                self.progress_bar.setValue(100)
                self.status_label.setText(f"Successfully loaded {len(self.folder_paths)} TOFWERK file(s)")
                
            finally:
                overlay.hide()
                overlay.deleteLater()

            self.current_data_source_type = "tofwerk"

            if append_mode and newly_added_samples and self.selected_isotopes:
                self.status_label.setText("Loading selected isotopes for new samples...")
                QApplication.processEvents()
                self._load_selected_isotopes_for_new_samples(newly_added_samples)

            if self.periodic_table_widget and self.all_masses:
                self.periodic_table_widget.update_available_masses(self.all_masses)
                self.periodic_table_widget.validate_selections_against_new_range()
            
            if self.all_masses is not None:
                self.show_periodic_table_after_load()
            else:
                raise ValueError("No valid TOFWERK data was loaded")
                
        except Exception as e:
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "Error", f"Error processing TOFWERK files: {str(e)}")
            self.logger.error(f"Error processing TOFWERK files: {str(e)}")

    def handle_csv_import(self, file_paths):
        """
        Handle CSV file import with configuration.
        
        Args:
            self: MainWindow instance
            file_paths (list): List of CSV file paths
            
        Returns:
            None
        """
        try:
            config = show_csv_structure_dialog(file_paths, self)
            if not config:
                return

            proposed_masses = []
            for file_config in config.get('files', []):
                for mapping in file_config.get('mappings', {}).values():
                    isotope = mapping.get('isotope', {})
                    if 'mass' in isotope:
                        proposed_masses.append(isotope['mass'])
            proposed_masses = (
                np.asarray(sorted(set(proposed_masses)), dtype=float)
                if proposed_masses else None
            )

            proceed, append_mode = self._prepare_for_load(
                "csv", file_paths, proposed_masses)
            if not proceed:
                return

            if append_mode and self.csv_config and self.csv_config.get('files'):
                merged_config = dict(self.csv_config)
                merged_config['files'] = list(self.csv_config.get('files', [])) \
                                         + list(config.get('files', []))
                self.csv_config = merged_config
            else:
                self.csv_config = config

            self._pending_csv_append_mode = append_mode
            self.pending_csv_processing = True
            self.extract_masses_from_csv_config(config, append_mode=append_mode)
            self.current_data_source_type = "csv"
            self.show_periodic_table_after_load()
            
        except Exception as e:
            QMessageBox.critical(self, "CSV Import Error", f"Error importing CSV files: {str(e)}")
            self.logger.error(f"Error importing CSV files: {str(e)}")

    def extract_masses_from_csv_config(self, config, append_mode=False):
        """
        Extract available masses from CSV configuration.
        
        Args:
            self: MainWindow instance
            config (dict): CSV configuration dictionary
            append_mode (bool): If True, merge with existing masses instead of
                replacing them. Default False.
            
        Returns:
            None
        """
        masses = []
        for file_config in config['files']:
            for mapping in file_config['mappings'].values():
                isotope = mapping['isotope']
                masses.append(isotope['mass'])

        if append_mode and self.all_masses:
            combined = sorted(set(list(self.all_masses) + masses))
            self.all_masses = combined
        else:
            self.all_masses = sorted(list(set(masses)))
            self.folder_paths = []

    def filter_csv_config_by_isotopes(self, config, selected_isotopes):
        """
        Filter CSV configuration to include only selected isotopes.
        
        Args:
            self: MainWindow instance
            config (dict): CSV configuration dictionary
            selected_isotopes (dict): Dictionary of selected isotopes
            
        Returns:
            dict: Filtered configuration dictionary
        """
        filtered_config = config.copy()
        filtered_config['files'] = []
        
        selected_masses = set()
        for element, isotopes in selected_isotopes.items():
            for isotope in isotopes:
                selected_masses.add(isotope)
        
        for file_config in config['files']:
            filtered_file_config = file_config.copy()
            filtered_file_config['mappings'] = {}
            
            for mapping_key, mapping in file_config['mappings'].items():
                isotope_mass = mapping['isotope']['mass']
                if isotope_mass in selected_masses:
                    filtered_file_config['mappings'][mapping_key] = mapping
            
            filtered_config['files'].append(filtered_file_config)
        
        return filtered_config

    #----------------------------------------------------------------------------------------------------------
    #------------------------------------data processing and handling --------------------------------------------
    #----------------------------------------------------------------------------------------------------------
   
    def handle_thread_finished(self, data, run_info, time_array, sample_name, analysis_datetime=None):
        """
        Handle completion of data processing thread.
        
        Args:
            self: MainWindow instance
            data (dict): Processed mass data dictionary
            run_info (dict): Run information dictionary
            time_array (ndarray): Time array
            sample_name (str): Sample name
            analysis_datetime (str, optional): Analysis datetime string
            
        Returns:
            None
        """
        try:
            if sample_name not in self.data_by_sample:
                self.data_by_sample[sample_name] = {}
            
            self.data_by_sample[sample_name] = data.copy()
            self.time_array_by_sample[sample_name] = time_array.copy()
            self.needs_initial_detection.add(sample_name)

            if run_info:
                self.sample_run_info[sample_name] = run_info.copy()
                
                folder_path = self.sample_to_folder_map.get(sample_name)
                if folder_path:
                    try:
                        method_files = list(Path(folder_path).glob("*.method"))
                        if method_files:
                            with open(method_files[0], "r") as fp:
                                method_info = json.load(fp)
                                self.sample_method_info[sample_name] = method_info
                    except Exception as e:
                        print(f"Could not load method info for {sample_name}: {str(e)}")

            if analysis_datetime:
                try:
                    from datetime import datetime
                    datetime_obj = datetime.fromisoformat(analysis_datetime.replace('Z', '+00:00'))
                    formatted_date = datetime_obj.strftime("%Y-%m-%d")
                    formatted_time = datetime_obj.strftime("%H:%M:%S")
                    self.sample_analysis_dates[sample_name] = {
                        'date': formatted_date,
                        'time': formatted_time,
                        'raw': analysis_datetime
                    }
                except Exception as e:
                    self.logger.error(f"Error parsing datetime: {str(e)}")
                    self.sample_analysis_dates[sample_name] = {
                        'date': analysis_datetime,
                        'time': '',
                        'raw': analysis_datetime
                    }

            if sample_name == self.current_sample:
                self.data = self.data_by_sample[sample_name]
                self.time_array = self.time_array_by_sample[sample_name]
                
                self.update_parameters_table(force=False)
                current_row = self.parameters_table.currentRow()
                if current_row >= 0:
                    self.parameters_table_clicked(current_row, 0)
            
            if run_info and "SegmentInfo" in run_info:
                seg = run_info["SegmentInfo"][0]
                acqtime = seg["AcquisitionPeriodNs"] * 1e-9
                accumulations = run_info["NumAccumulations1"] * run_info["NumAccumulations2"]
                dwell_time_ms = acqtime * accumulations * 1000
            elif len(time_array) > 1:
                dwell_time_ms = np.mean(np.diff(time_array)) * 1000
            else:
                dwell_time_ms = 0.0
                
            self.sample_dwell_times[sample_name] = dwell_time_ms

            self.status_label.setText(f"Processed data for {sample_name}")

        except Exception as e:
            self.logger.error(f"Error processing data for {sample_name}: {str(e)}")       
    
    def handle_csv_finished(self, data, run_info, time_array, sample_name, datetime_str):
        """
        Handle completion of CSV file processing.
        
        Args:
            self: MainWindow instance
            data (dict): Processed data dictionary
            run_info (dict): Run information dictionary
            time_array (ndarray): Time array
            sample_name (str): Sample name
            datetime_str (str): Datetime string
            
        Returns:
            None
        """
        try:
            self.data_by_sample[sample_name] = data.copy()
            self.time_array_by_sample[sample_name] = time_array.copy()
            self.needs_initial_detection.add(sample_name)
            
            self.sample_run_info[sample_name] = run_info.copy()
            
            csv_file_path = run_info.get('OriginalFile', sample_name)
            self.sample_to_folder_map[sample_name] = csv_file_path
            
            if datetime_str:
                self.sample_analysis_dates[sample_name] = {
                    'date': datetime_str,
                    'time': '',
                    'raw': datetime_str
                }
            
            self.sample_dwell_times[sample_name] = run_info.get('DwellTimeMs', 10.0)
            
            self.update_sample_table()
            
            if self.current_sample is None and sample_name in self.data_by_sample:
                self.current_sample = sample_name
                self.data = self.data_by_sample[sample_name]
                self.time_array = self.time_array_by_sample[sample_name]
                
                self.update_parameters_table(force=False)
                if self.sample_table.rowCount() > 0:
                    self.sample_table.selectRow(0)
                    item = self.sample_table.item(0, 0)
                    if item:
                        self.on_sample_selected(item)
            
            self.status_label.setText(f"CSV sample '{sample_name}' processed successfully")
            
            expected_files = len(self.csv_config['files']) if self.csv_config else 0
            processed_files = len([s for s in self.sample_to_folder_map.values() if str(s).endswith('.csv')])
            
            if processed_files >= expected_files:
                self.progress_bar.setVisible(False)
                self.pending_csv_processing = False
                self.csv_config = None
                self.status_label.setText(f"All CSV files processed successfully ({processed_files} samples)")
            
        except Exception as e:
            self.status_label.setText(f"Error processing CSV data for {sample_name}: {str(e)}")
            self.logger.error(f"Error processing CSV data for {sample_name}: {str(e)}")     
    
    def handle_new_elements_finished(self, new_data, run_info, time_array, sample_name, analysis_datetime=None):
        """
        Handle completion of new element processing.
        
        Args:
            self: MainWindow instance
            new_data (dict): New mass data dictionary
            run_info (dict): Run information dictionary
            time_array (ndarray): Time array
            sample_name (str): Sample name
            analysis_datetime (str, optional): Analysis datetime string
            
        Returns:
            None
        """
        try:
            if sample_name in self.data_by_sample:
                self.data_by_sample[sample_name].update(new_data)
            else:
                self.data_by_sample[sample_name] = new_data.copy()
                self.time_array_by_sample[sample_name] = time_array.copy()
            
            if sample_name not in self.sample_run_info and run_info:
                self.sample_run_info[sample_name] = run_info.copy()
                
            if analysis_datetime and sample_name not in self.sample_analysis_dates:
                try:
                    from datetime import datetime
                    datetime_obj = datetime.fromisoformat(analysis_datetime.replace('Z', '+00:00'))
                    formatted_date = datetime_obj.strftime("%Y-%m-%d")
                    formatted_time = datetime_obj.strftime("%H:%M:%S")
                    self.sample_analysis_dates[sample_name] = {
                        'date': formatted_date,
                        'time': formatted_time,
                        'raw': analysis_datetime
                    }
                except Exception as e:
                    self.logger.error(f"Error parsing datetime: {str(e)}")
                    self.sample_analysis_dates[sample_name] = {
                        'date': analysis_datetime,
                        'time': '',
                        'raw': analysis_datetime
                    }
            
            if sample_name == self.current_sample:
                self.data.update(new_data)
                
                self.update_parameters_table(force=False)
                current_row = self.parameters_table.currentRow()
                if current_row >= 0:
                    self.parameters_table_clicked(current_row, 0)
            
            if sample_name not in self.sample_dwell_times and run_info:
                if "SegmentInfo" in run_info:
                    seg = run_info["SegmentInfo"][0]
                    acqtime = seg["AcquisitionPeriodNs"] * 1e-9
                    accumulations = run_info["NumAccumulations1"] * run_info["NumAccumulations2"]
                    dwell_time_ms = acqtime * accumulations * 1000
                    self.sample_dwell_times[sample_name] = dwell_time_ms
            
            self.status_label.setText(f"Added new elements to {sample_name}")
            
        except Exception as e:
            self.logger.error(f"Error merging new elements for {sample_name}: {str(e)}")
        
    def handle_error(self, error_message):
        """
        Handle errors from data processing threads.
        
        Args:
            self: MainWindow instance
            error_message (str): Error message
            
        Returns:
            None
        """
        self.log_status(f"Error: {error_message}", 'error')
        
        self.progress_bar.setVisible(False)
        self.detect_button.setEnabled(True) 
        QMessageBox.critical(self, "Error", f"An error occurred: {error_message}")

    def display_data(self, new_data, run_info, time_array, sample_name):
        """
        Display processed data in UI.
        
        Args:
            self: MainWindow instance
            new_data (dict): Processed data dictionary
            run_info (dict): Run information dictionary
            time_array (ndarray): Time array
            sample_name (str): Sample name
            
        Returns:
            None
        """
        self.handle_thread_finished(new_data, run_info, time_array, sample_name)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Data processed successfully!")
        self.detect_button.setEnabled(True)

        if sample_name not in self.data_by_sample:
            self.data_by_sample[sample_name] = {}
        
        self.data_by_sample[sample_name] = new_data.copy()
        self.time_array_by_sample[sample_name] = time_array.copy()

        if sample_name == self.current_sample:
            self.data = self.data_by_sample[sample_name]
            self.time_array = self.time_array_by_sample[sample_name]
            
            self.update_parameters_table(force=False)

            current_row = self.parameters_table.currentRow()
            if current_row >= 0:
                self.parameters_table_clicked(current_row, 0)
                
    #----------------------------------------------------------------------------------------------------------
    #------------------------------------sample management--------------------------------------------
    #----------------------------------------------------------------------------------------------------------
   
    
    def on_sample_selected(self, item):
        """
        Handle sample selection from sample table.
        
        Args:
            self: MainWindow instance
            item: QTableWidgetItem that was selected
            
        Returns:
            None
        """
        if not item:
            return
        
        sample_name = self.sample_table.item(item.row(), 0).text()
        
        self.user_action_logger.log_action(
            'SAMPLE_SELECT',
            f"Selected sample: {sample_name}",
            context={
                'previous_sample': getattr(self, 'current_sample', None),
                'new_sample': sample_name
            }
        )
                
        self.save_current_parameters()
        
        currently_selected_element = None
        currently_selected_isotope = None
        if hasattr(self, 'current_element') and hasattr(self, 'current_isotope'):
            currently_selected_element = self.current_element
            currently_selected_isotope = self.current_isotope
        
        row = item.row()
        sample_name = self.sample_table.item(row, 0).text()
        
        self.current_sample = sample_name
        
        self.load_or_initialize_parameters(sample_name)
        
        if hasattr(self, 'sigma_spinbox'):
            self.sigma_spinbox.blockSignals(True)
            self.sigma_spinbox.setValue(getattr(self, '_global_sigma', 0.55))
            self.sigma_spinbox.blockSignals(False)
            
        if sample_name in self.data_by_sample:
            self.data = self.data_by_sample[sample_name]
            self.time_array = self.time_array_by_sample[sample_name]

            try:
                self._rebuild_plot_exclusion_regions()
            except Exception as e:
                self.logger.debug(f"Could not restore exclusion regions: {e}")
            
            if sample_name in self.sample_detected_peaks:
                self.detected_peaks = self.sample_detected_peaks[sample_name]
            else:
                self.detected_peaks = {}
                
            self.update_parameters_table(force=False)
            
            self.restore_results_tables(sample_name)
            
            if hasattr(self, 'showing_all_signals') and self.showing_all_signals:
                self.plot_all_signals()
            else:
                if currently_selected_element and currently_selected_isotope:
                    found_row = -1
                    for row in range(self.parameters_table.rowCount()):
                        element_item = self.parameters_table.item(row, 0)
                        if element_item:
                            display_label = element_item.text()
                            element_key = f"{currently_selected_element}-{currently_selected_isotope:.4f}"
                            if self.get_formatted_label(element_key) == display_label:
                                found_row = row
                                break
                    
                    if found_row >= 0:
                        self.parameters_table.selectRow(found_row)
                        self.parameters_table_clicked(found_row, 0)
                    else:
                        self.parameters_table.selectRow(0)
                        self.parameters_table_clicked(0, 0)
                else:
                    if self.parameters_table.rowCount() > 0:
                        self.parameters_table.selectRow(0)
                        self.parameters_table_clicked(0, 0)
            
            if hasattr(self, 'info_tooltip') and self.info_tooltip.isVisible():
                active_samples = len(self.data_by_sample)
                total_elements = sum(len(isotopes) for isotopes in self.selected_isotopes.values()) if self.selected_isotopes else 0
                accuracy = self.calculate_accuracy()
                
                analysis_date_info = None
                if sample_name in self.sample_analysis_dates:
                    analysis_date_info = self.sample_analysis_dates[sample_name]
                
                self.info_tooltip.update_stats(
                    active_samples,
                    total_elements,
                    accuracy,
                    analysis_date_info
                )
                
                self.info_tooltip.update_sample_content(
                    sample_name,
                    self.selected_isotopes,
                    self.detected_peaks,
                    getattr(self, 'multi_element_particles', []),
                    periodic_table_widget=self.periodic_table_widget
                )

    def update_sample_table(self):
        """
        Update sample table with all loaded samples.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.sample_table.setRowCount(0)
        
        for sample_name, source_path in self.sample_to_folder_map.items():
            row = self.sample_table.rowCount()
            self.sample_table.insertRow(row)
            
            name_item = QTableWidgetItem(sample_name)
            
            is_csv = str(source_path).lower().endswith('.csv')
            status = "Loaded (CSV)" if is_csv else "Loaded (Folder)"
            status_item = QTableWidgetItem(status)
            
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            
            self.sample_table.setItem(row, 0, name_item)
            self.sample_table.setItem(row, 1, status_item)
            
    def show_sample_context_menu(self, position):
        """
        Show context menu for sample table.
        
        Args:
            self: MainWindow instance
            position: QPoint position for menu
            
        Returns:
            None
        """
        row = self.sample_table.rowAt(position.y())
        if row >= 0:
            sample_name = self.sample_table.item(row, 0).text()
            
            menu = QMenu(self)
            
            info_action = menu.addAction("Show Method Information")
            info_action.setIcon(qta.icon('fa6s.barcode', color=theme.palette.accent))
            info_action.triggered.connect(lambda: FileInfoMenu.show_file_info(
                sample_name, 
                self.sample_run_info.get(sample_name),
                self.sample_method_info.get(sample_name),
                self.time_array_by_sample.get(sample_name),
                self.all_masses,
                self
            ))
            
            menu.addSeparator()
            
            remove_action = menu.addAction("Remove Sample")
            remove_action.setIcon(qta.icon('fa6s.file-circle-minus', color=theme.palette.danger))
            remove_action.triggered.connect(lambda: self.remove_sample(sample_name))
            
            if self.sample_table.rowCount() > 1:
                remove_all_action = menu.addAction("Remove All Samples")
                remove_all_action.setIcon(qta.icon('fa6s.file-circle-xmark', color=theme.palette.danger))
                remove_all_action.triggered.connect(self.remove_all_samples)

            _p = theme.palette
            menu.setStyleSheet(f"""
                QMenu {{
                    background-color: {_p.bg_secondary};
                    color: {_p.text_primary};
                    border: 1px solid {_p.border};
                    border-radius: 4px;
                    padding: 4px;
                }}
                QMenu::item {{
                    padding: 8px 20px;
                    border-radius: 3px;
                }}
                QMenu::item:selected {{
                    background-color: {_p.accent_soft};
                    color: {_p.text_primary};
                }}
                QMenu::separator {{
                    height: 1px;
                    background-color: {_p.border_subtle};
                    margin: 4px 0px;
                }}
            """)
            
            menu.exec(self.sample_table.viewport().mapToGlobal(position))
            
    def remove_sample(self, sample_name):
        """
        Remove sample and all associated data.
        
        Args:
            self: MainWindow instance
            sample_name (str): Name of sample to remove
            
        Returns:
            None
        """
        reply = QMessageBox.question(
            self, 
            'Remove Sample',
            f'Are you sure you want to remove sample "{sample_name}"?\n\n'
            'This will permanently delete all associated data including:\n'
            '• Raw data\n'
            '• Detection results\n'
            '• Parameters\n'
            '• Calibration data\n\n'
            'This action cannot be undone.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return

        self.user_action_logger.log_action(
            'DATA_OP', f'Removed sample: {sample_name}',
            {'sample': sample_name,
             'was_current': sample_name == self.current_sample,
             'remaining': len(self.sample_to_folder_map) - 1})
        try:
            was_current_sample = (sample_name == self.current_sample)
            
            data_structures_to_clean = [
                ('sample_to_folder_map', self.sample_to_folder_map),
                ('data_by_sample', self.data_by_sample),
                ('time_array_by_sample', self.time_array_by_sample),
                ('sample_parameters', self.sample_parameters),
                ('sample_detected_peaks', self.sample_detected_peaks),
                ('sample_dwell_times', self.sample_dwell_times),
                ('sample_results_data', self.sample_results_data),
                ('sample_particle_data', self.sample_particle_data),
                ('sample_analysis_dates', self.sample_analysis_dates),
                ('element_thresholds', self.element_thresholds),
                ('sample_run_info', self.sample_run_info),
                ('sample_method_info', self.sample_method_info),
                ('saturation_filtered_peaks', self.saturation_filtered_peaks),
                ('saturation_filtered_multi', self.saturation_filtered_multi),
                ('saturation_windows', self.saturation_windows),
                ('saturation_excluded_time_s', self.saturation_excluded_time_s)
            ]
            
            removed_count = 0
            for structure_name, structure in data_structures_to_clean:
                if sample_name in structure:
                    del structure[sample_name]
                    removed_count += 1
            
            if hasattr(self, 'element_limits') and sample_name in self.element_limits:
                del self.element_limits[sample_name]
                removed_count += 1

            self.clear_element_caches()

            if hasattr(self, 'detection_states'):
                self.detection_states.pop(sample_name, None)
                removed_count += 1
            if hasattr(self, 'sample_status'):
                self.sample_status.pop(sample_name, None)
                removed_count += 1
            if hasattr(self, 'needs_initial_detection'):
                self.needs_initial_detection.discard(sample_name)
            
            self.update_sample_table()
            
            if was_current_sample:
                self.current_sample = None
                self.data = {}
                self.time_array = None
                self.detected_peaks = {}
                
                if self.sample_table.rowCount() > 0:
                    first_item = self.sample_table.item(0, 0)
                    if first_item:
                        self.sample_table.selectRow(0)
                        self.on_sample_selected(first_item)
                else:
                    self.clear_all_displays()
            
            self.status_label.setText(f"Removed sample '{sample_name}' and cleaned {removed_count} data structures")
            
            self.unsaved_changes = True
            
            QMessageBox.information(
                self, 
                "Sample Removed", 
                f"Sample '{sample_name}' has been successfully removed.\n\n"
                f"Cleaned {removed_count} data structures from memory."
            )
            
        except Exception as e:
            error_msg = f"Error removing sample '{sample_name}': {str(e)}"
            self.status_label.setText(error_msg)
            QMessageBox.critical(self, "Removal Error", error_msg)
            print(f"Error in remove_sample: {str(e)}")

    def remove_all_samples(self):
        """
        Remove all samples and reset application.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        reply = QMessageBox.question(
            self, 
            'Remove All Samples',
            'Are you sure you want to remove ALL samples?\n\n'
            'This will permanently delete all data and reset the application.\n'
            'This action cannot be undone.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                _removed_count = len(self.sample_to_folder_map)
                self.user_action_logger.log_action(
                    'DATA_OP', f'Removed all samples ({_removed_count})',
                    {'count': _removed_count,
                     'samples': list(self.sample_to_folder_map.keys())})
                self.reset_data_structures()
                
                self.status_label.setText("All samples removed. Application reset.")
                
                self.unsaved_changes = True
                
                QMessageBox.information(self, "All Samples Removed", "All samples have been removed and the application has been reset.")
                
            except Exception as e:
                error_msg = f"Error removing all samples: {str(e)}"
                self.status_label.setText(error_msg)
                QMessageBox.critical(self, "Removal Error", error_msg)        
            
    def sample_table_key_press(self, event):
        """
        Handle keyboard navigation in sample table.
        
        Args:
            self: MainWindow instance
            event: QKeyEvent object
            
        Returns:
            None
        """
        current_row = self.sample_table.currentRow()
        
        if event.key() == Qt.Key_Up:
            if current_row > 0:
                self.sample_table.setCurrentCell(current_row - 1, 0)
                item = self.sample_table.item(current_row - 1, 0)
                self.on_sample_selected(item)
        elif event.key() == Qt.Key_Down:
            if current_row < self.sample_table.rowCount() - 1:
                self.sample_table.setCurrentCell(current_row + 1, 0)
                item = self.sample_table.item(current_row + 1, 0)
                self.on_sample_selected(item)
        elif event.key() == Qt.Key_Tab:
            self.parameters_table.setFocus()
            if self.parameters_table.currentRow() < 0 and self.parameters_table.rowCount() > 0:
                self.parameters_table.setCurrentCell(0, 0)
                self.parameters_table_clicked(0, 0)
        else:
            QTableWidget.keyPressEvent(self.sample_table, event)
        
    #----------------------------------------------------------------------------------------------------------
    #------------------------------------element isotope selection--------------------------------------------
    #----------------------------------------------------------------------------------------------------------
   
    @log_user_action('DIALOG_OPEN', 'Opened periodic table')
    def show_periodic_table(self):
        """
        Display periodic table for element selection.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.user_action_logger.log_dialog_open('Periodic Table', 'Element Selection')
        if self.all_masses is None or len(self.all_masses) == 0:
            QMessageBox.warning(
                self,
                "No Data Loaded",
                "Please load data files first before opening the periodic table."
            )
            return
            
        if not self.periodic_table_widget:
            self.periodic_table_widget = PeriodicTableWidget()
            self.periodic_table_widget.selection_confirmed.connect(self.handle_isotopes_selected)
            
            self.periodic_table_widget.update_available_masses(self.all_masses)
            
            if self.selected_isotopes:
                self._update_periodic_table_selections()
        
        self.periodic_table_widget.show()
        self.periodic_table_widget.raise_()
                           
    def show_periodic_table_after_load(self):
        """
        Show periodic table after data is loaded.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        if not self.periodic_table_widget:
            self.periodic_table_widget = PeriodicTableWidget()
            self.periodic_table_widget.selection_confirmed.connect(self.handle_isotopes_selected)
        if hasattr(self, 'all_masses') and self.all_masses:
            self.periodic_table_widget.update_available_masses(self.all_masses)
        
        self.periodic_table_widget.show()
        self.periodic_table_widget.raise_()
        self.update_sample_table()                   
                        
    def handle_isotopes_selected(self, selected_isotopes):
        """
        Handle confirmed isotope selections from periodic table.
        
        Args:
            self: MainWindow instance
            selected_isotopes (dict): Dictionary of selected isotopes by element
            
        Returns:
            None
        """
        try:
            self.clear_element_caches()
            self._display_label_to_element.clear()
            
            is_project_loading = (
                hasattr(self, '_loading_project') and 
                getattr(self, '_loading_project', False)
            )
            
            if self.pending_csv_processing and self.csv_config:
                self.process_csv_files_with_isotopes(selected_isotopes)
            
            if not is_project_loading:
                self.progress_bar.setVisible(True)
                self.progress_bar.setValue(0)
                self.status_label.setText("Processing element changes...")
                QApplication.processEvents()
            
            old_isotopes = set()
            old_isotopes_dict = {}
            for element, isotopes in self.selected_isotopes.items():
                old_isotopes_dict[element] = list(isotopes)
                for isotope in isotopes:
                    old_isotopes.add((element, isotope))
            
            new_isotopes = set()
            for element, isotopes in selected_isotopes.items():
                for isotope in isotopes:
                    new_isotopes.add((element, isotope))
            
            newly_added = new_isotopes - old_isotopes
            removed_isotopes = old_isotopes - new_isotopes
            
            self.selected_isotopes = selected_isotopes.copy()
                
            if removed_isotopes:
                self.status_label.setText("Removing deselected elements...")
                QApplication.processEvents()
                
                for sample_name in self.data_by_sample:
                    sample_data = self.data_by_sample[sample_name]
                    for element, isotope in removed_isotopes:
                        mass_to_remove = None
                        for mass in list(sample_data.keys()):
                            if abs(mass - isotope) < 0.001:
                                mass_to_remove = mass
                                break
                        if mass_to_remove is not None:
                            del sample_data[mass_to_remove]
                    
                    if sample_name in self.sample_detected_peaks:
                        peaks_to_remove = [(e, i) for e, i in removed_isotopes if (e, i) in self.sample_detected_peaks[sample_name]]
                        for peak_key in peaks_to_remove:
                            del self.sample_detected_peaks[sample_name][peak_key]
                    
                    if sample_name in self.element_thresholds:
                        thresholds_to_remove = [f"{e}-{i:.4f}" for e, i in removed_isotopes]
                        for threshold_key in thresholds_to_remove:
                            if threshold_key in self.element_thresholds[sample_name]:
                                del self.element_thresholds[sample_name][threshold_key]
                
                self._on_isotopes_removed(removed_isotopes)
            
            if newly_added and self.folder_paths and not self.pending_csv_processing:
                all_accessible, inaccessible_samples = self.verify_all_data_sources()
                
                if not all_accessible:
                    self.status_label.setText("Data sources not accessible. Please reconnect external drives.")
                    self.progress_bar.setVisible(False)
                    
                    while not all_accessible:
                        retry = self.prompt_reconnect_data_source(inaccessible_samples)
                        
                        if not retry:
                            QMessageBox.warning(
                                self,
                                "Operation Cancelled",
                                "New elements were not added because data sources are not accessible.\n\n"
                                "Please reconnect your data sources and try again."
                            )
                            
                            self.selected_isotopes = old_isotopes_dict.copy()
                            
                            self.progress_bar.setVisible(False)
                            self.update_parameters_table()
                            
                            if self.periodic_table_widget:
                                self._update_periodic_table_selections()
                            
                            self.status_label.setText("Element addition cancelled - data sources not accessible")
                            return
                        
                        all_accessible, inaccessible_samples = self.verify_all_data_sources()
                        
                        if all_accessible:
                            self.status_label.setText("All data sources are now accessible. Proceeding...")
                            self.progress_bar.setVisible(True)
                            QApplication.processEvents()
                            break
                
                for sample_name in self.data_by_sample.keys():
                    for element, isotope in newly_added:
                        element_key = f"{element}-{isotope:.4f}"
                        self.mark_element_changed(sample_name, element_key)
                        
                self.progress_bar.setValue(20)
                self.status_label.setText(f"Processing {len(newly_added)} new elements...")
                QApplication.processEvents()
                
                new_masses_to_process = [isotope for element, isotope in newly_added]
                
                if new_masses_to_process:
                    total_samples = len(self.sample_to_folder_map)
                    for i, (sample_name, folder_path) in enumerate(self.sample_to_folder_map.items()):
                        if str(folder_path).endswith('.csv'):
                            continue
                        
                        if not self.check_data_source_accessible(folder_path):
                            QMessageBox.critical(
                                self,
                                "Data Source Lost",
                                f"Lost access to data source for sample '{sample_name}' during processing.\n\n"
                                f"Path: {folder_path}\n\n"
                                "Please reconnect the drive and try again."
                            )
                            
                            self.selected_isotopes = old_isotopes_dict.copy()
                            self.progress_bar.setVisible(False)
                            self.update_parameters_table()
                            
                            if self.periodic_table_widget:
                                self._update_periodic_table_selections()
                            
                            return
                            
                        try:
                            progress = 20 + int((i / total_samples) * 80)
                            self.progress_bar.setValue(progress)
                            self.status_label.setText(f"Adding new elements to sample {i+1}/{total_samples}: {sample_name}")
                            QApplication.processEvents()
                            
                            thread = DataProcessThread(folder_path, new_masses_to_process, sample_name)
                            thread.finished.connect(self.handle_new_elements_finished)
                            thread.error.connect(self.handle_error)

                            def _elem_progress(value, _i=i, _tot=total_samples):
                                overall = 20 + ((_i + value / 100.0) / max(1, _tot)) * 80
                                self.progress_bar.setValue(int(overall))
                                QApplication.processEvents()
                            thread.progress.connect(_elem_progress)
                            
                            loop = QEventLoop()
                            thread.finished.connect(loop.quit)
                            thread.error.connect(loop.quit)
                            thread.start()
                            loop.exec()

                            try:
                                thread.progress.disconnect()
                                thread.finished.disconnect()
                                thread.error.disconnect()
                            except (RuntimeError, TypeError):
                                pass
                            thread.deleteLater()
                                
                        except Exception as e:
                            self.logger.error(f"Error processing sample {sample_name}: {str(e)}")
                            continue
            
            if not self.pending_csv_processing:
                self.progress_bar.setValue(100)
                self.progress_bar.setVisible(False)
                
                if newly_added:
                    self.status_label.setText(f"Added {len(newly_added)} new elements")
                elif removed_isotopes:
                    self.status_label.setText(f"Removed {len(removed_isotopes)} elements")
                else:
                    self.status_label.setText("Element selection updated")
            else:
                self.status_label.setText("Processing CSV files with selected isotopes...")
            
            QApplication.processEvents()
            
            self.update_parameters_table()
            
            if not self.current_sample and self.data_by_sample:
                first_sample = next(iter(self.data_by_sample.keys()))
                self.current_sample = first_sample
                self.data = self.data_by_sample[first_sample]
                self.time_array = self.time_array_by_sample[first_sample]
            
            if self.current_sample:
                if self.sample_table.rowCount() > 0:
                    self.sample_table.selectRow(0)
                    item = self.sample_table.item(0, 0)
                    if item:
                        self.sample_table.itemClicked.disconnect()
                        self.on_sample_selected(item)
                        self.sample_table.itemClicked.connect(self.on_sample_selected)
                
                if self.parameters_table.rowCount() > 0:
                    self.parameters_table.selectRow(0)
                    self.parameters_table_clicked(0, 0)
                    
            self._build_element_lookup_cache()
            
        except Exception as e:
            self.logger.error(f"Error in handle_isotopes_selected: {str(e)}")
            self.progress_bar.setVisible(False)
            
        self.unsaved_changes = True
            
    def handle_isotopes_selection_from_calibration(self, selected_isotopes):
        """
        Handle isotope selections from ionic calibration window.
        
        Args:
            self: MainWindow instance
            selected_isotopes (dict): Dictionary of selected isotopes by element
            
        Returns:
            None
        """
        try:
            self.clear_element_caches()
            self._display_label_to_element.clear()
            
            is_project_loading = (
                hasattr(self, '_loading_project') and 
                getattr(self, '_loading_project', False)
            )
            
            if not is_project_loading:
                self.progress_bar.setVisible(True)
                self.progress_bar.setValue(0)
                self.status_label.setText("Processing selected elements from calibration...")
                QApplication.processEvents()
            
            old_isotopes = set()
            old_isotopes_dict = {}
            for element, isotopes in self.selected_isotopes.items():
                old_isotopes_dict[element] = list(isotopes)
                for isotope in isotopes:
                    old_isotopes.add((element, isotope))
            
            new_isotopes = set()
            for element, isotopes in selected_isotopes.items():
                for isotope in isotopes:
                    new_isotopes.add((element, isotope))
            
            newly_added = new_isotopes - old_isotopes
            removed_isotopes = old_isotopes - new_isotopes
            
            self.selected_isotopes = selected_isotopes.copy()
                
            if removed_isotopes:
                self.status_label.setText("Removing deselected elements...")
                QApplication.processEvents()
                
                for sample_name in self.data_by_sample:
                    sample_data = self.data_by_sample[sample_name]
                    for element, isotope in removed_isotopes:
                        mass_to_remove = None
                        for mass in list(sample_data.keys()):
                            if abs(mass - isotope) < 0.001:
                                mass_to_remove = mass
                                break
                        if mass_to_remove is not None:
                            del sample_data[mass_to_remove]
                    
                    if sample_name in self.sample_detected_peaks:
                        peaks_to_remove = [(e, i) for e, i in removed_isotopes if (e, i) in self.sample_detected_peaks[sample_name]]
                        for peak_key in peaks_to_remove:
                            del self.sample_detected_peaks[sample_name][peak_key]
                    
                    if sample_name in self.element_thresholds:
                        thresholds_to_remove = [f"{e}-{i:.4f}" for e, i in removed_isotopes]
                        for threshold_key in thresholds_to_remove:
                            if threshold_key in self.element_thresholds[sample_name]:
                                del self.element_thresholds[sample_name][threshold_key]
                
                self._on_isotopes_removed(removed_isotopes)
            
            if newly_added and self.folder_paths and not self.pending_csv_processing:
                all_accessible, inaccessible_samples = self.verify_all_data_sources()
                
                if not all_accessible:
                    self.status_label.setText("Data sources not accessible. Please reconnect external drives.")
                    self.progress_bar.setVisible(False)
                    
                    while not all_accessible:
                        retry = self.prompt_reconnect_data_source(inaccessible_samples)
                        
                        if not retry:
                            QMessageBox.warning(
                                self,
                                "Operation Cancelled",
                                "New elements were not added because data sources are not accessible.\n\n"
                                "Please reconnect your data sources and try again."
                            )
                            
                            self.selected_isotopes = old_isotopes_dict.copy()
                            
                            self.progress_bar.setVisible(False)
                            self.update_parameters_table()
                            
                            if hasattr(self, 'ionic_calibration_window') and self.ionic_calibration_window:
                                self.ionic_calibration_window.selected_isotopes = old_isotopes_dict.copy()
                                self.ionic_calibration_window.update_periodic_table()
                            
                            self.status_label.setText("Element addition cancelled - data sources not accessible")
                            return
                        
                        all_accessible, inaccessible_samples = self.verify_all_data_sources()
                        
                        if all_accessible:
                            self.status_label.setText("All data sources are now accessible. Proceeding...")
                            self.progress_bar.setVisible(True)
                            QApplication.processEvents()
                            break
                
                for sample_name in self.data_by_sample.keys():
                    for element, isotope in newly_added:
                        element_key = f"{element}-{isotope:.4f}"
                        self.mark_element_changed(sample_name, element_key)
                        
                self.progress_bar.setValue(20)
                self.status_label.setText(f"Processing {len(newly_added)} new elements...")
                QApplication.processEvents()
                
                new_masses_to_process = [isotope for element, isotope in newly_added]
                
                if new_masses_to_process:
                    total_samples = len(self.sample_to_folder_map)
                    for i, (sample_name, folder_path) in enumerate(self.sample_to_folder_map.items()):
                        if str(folder_path).endswith('.csv'):
                            continue
                        
                        if not self.check_data_source_accessible(folder_path):
                            QMessageBox.critical(
                                self,
                                "Data Source Lost",
                                f"Lost access to data source for sample '{sample_name}' during processing.\n\n"
                                f"Path: {folder_path}\n\n"
                                "Please reconnect the drive and try again."
                            )
                            
                            self.selected_isotopes = old_isotopes_dict.copy()
                            self.progress_bar.setVisible(False)
                            self.update_parameters_table()
                            
                            if hasattr(self, 'ionic_calibration_window') and self.ionic_calibration_window:
                                self.ionic_calibration_window.selected_isotopes = old_isotopes_dict.copy()
                                self.ionic_calibration_window.update_periodic_table()
                            
                            return
                            
                        try:
                            progress = 20 + int((i / total_samples) * 80)
                            self.progress_bar.setValue(progress)
                            self.status_label.setText(f"Adding new elements to sample {i+1}/{total_samples}: {sample_name}")
                            QApplication.processEvents()
                            
                            thread = DataProcessThread(folder_path, new_masses_to_process, sample_name)
                            thread.finished.connect(self.handle_new_elements_finished)
                            thread.error.connect(self.handle_error)

                            def _elem_progress(value, _i=i, _tot=total_samples):
                                overall = 20 + ((_i + value / 100.0) / max(1, _tot)) * 80
                                self.progress_bar.setValue(int(overall))
                                QApplication.processEvents()
                            thread.progress.connect(_elem_progress)
                            
                            loop = QEventLoop()
                            thread.finished.connect(loop.quit)
                            thread.error.connect(loop.quit)
                            thread.start()
                            loop.exec()

                            try:
                                thread.progress.disconnect()
                                thread.finished.disconnect()
                                thread.error.disconnect()
                            except (RuntimeError, TypeError):
                                pass
                            thread.deleteLater()
                                
                        except Exception as e:
                            self.logger.error(f"Error processing sample {sample_name}: {str(e)}")
                            continue
            
            if not self.pending_csv_processing:
                self.progress_bar.setValue(100)
                self.progress_bar.setVisible(False)
                
                if newly_added:
                    self.status_label.setText(f"Added {len(newly_added)} new elements")
                elif removed_isotopes:
                    self.status_label.setText(f"Removed {len(removed_isotopes)} elements")
                else:
                    self.status_label.setText("Element selection updated")
            else:
                self.status_label.setText("Processing CSV files with selected isotopes...")
            
            QApplication.processEvents()
            
            self.update_parameters_table()
            
            if not self.current_sample and self.data_by_sample:
                first_sample = next(iter(self.data_by_sample.keys()))
                self.current_sample = first_sample
                self.data = self.data_by_sample[first_sample]
                self.time_array = self.time_array_by_sample[first_sample]
            
            if self.current_sample:
                if self.sample_table.rowCount() > 0:
                    self.sample_table.selectRow(0)
                    item = self.sample_table.item(0, 0)
                    if item:
                        self.sample_table.itemClicked.disconnect()
                        self.on_sample_selected(item)
                        self.sample_table.itemClicked.connect(self.on_sample_selected)
                
                if self.parameters_table.rowCount() > 0:
                    self.parameters_table.selectRow(0)
                    self.parameters_table_clicked(0, 0)
                    
            self._build_element_lookup_cache()
            
        except Exception as e:
            self.logger.error(f"Error in handle_isotopes_selection_from_calibration: {str(e)}")
            self.progress_bar.setVisible(False)
            
        self.unsaved_changes = True
                                            
    def find_closest_isotope(self, target_mass):
        """
        Find closest isotope mass in loaded data.
        
        Args:
            self: MainWindow instance
            target_mass (float): Target isotope mass
            
        Returns:
            float or None: Closest mass key in data dictionary
        """
        if not self.data:
            return None
        return min(self.data.keys(), key=lambda x: abs(x - target_mass))                   
                        
    def get_formatted_label(self, element_key):
        """
        Get proper isotope label from periodic table data with caching.
        
        Args:
            self: MainWindow instance
            element_key (str): Element identifier (e.g., "Au-197.0000")
            
        Returns:
            str: Formatted isotope label (e.g., "197Au")
        """
        if element_key in self._formatted_label_cache:
            return self._formatted_label_cache[element_key]
            
        try:
            element, mass = element_key.split('-')
            mass = float(mass)
            
            if element not in self._element_data_cache:
                if self.periodic_table_widget:
                    element_data = self.periodic_table_widget.get_element_by_symbol(element)
                    self._element_data_cache[element] = element_data
                else:
                    self._element_data_cache[element] = None
            
            element_data = self._element_data_cache[element]
            
            if element_data:
                isotope = next((iso for iso in element_data['isotopes'] 
                              if isinstance(iso, dict) and abs(iso['mass'] - mass) < 0.001), None)
                if isotope and 'label' in isotope:
                    formatted_label = isotope['label']
    
                    self._formatted_label_cache[element_key] = formatted_label
                    return formatted_label

            formatted_label = f"{round(mass)}{element}"
            self._formatted_label_cache[element_key] = formatted_label
            return formatted_label
            
        except Exception as e:
            self.logger.warning(f"Error formatting element label for {element_key}: {str(e)}")
            return element_key
                       
    def clear_element_caches(self):
        """
        Clear element-related caches when data changes.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self._formatted_label_cache.clear()
        self._element_data_cache.clear()   
        
    def _build_element_lookup_cache(self):
        """
        Build fast lookup cache for element display labels.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self._display_label_to_element.clear()
        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                element_key = f"{element}-{isotope:.4f}"
                display_label = self.get_formatted_label(element_key)
                self._display_label_to_element[display_label] = (element, isotope, element_key)  
     
    def _build_element_conversion_cache(self):
        """
        Build cache for element count to mass conversions.
        
        Args:
            self: MainWindow instance
            
        Returns:
            dict: Cache mapping display labels to conversion data with keys:
                - 'element_key' (str): Element identifier
                - 'conversion_factor' (float or None): Counts to mass conversion factor
        """
        cache = {}
        
        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                element_key = f"{element}-{isotope:.4f}"
                display_label = self.get_formatted_label(element_key)
                
                conversion_factor = None
                if ("Ionic Calibration" in self.calibration_results and 
                    element_key in self.calibration_results["Ionic Calibration"]):
                    
                    cal_data = self.calibration_results["Ionic Calibration"][element_key]
                    
                    preferred_method = self.isotope_method_preferences.get(element_key, 'Force through zero')
                    method_map = {
                        'Force through zero': 'zero',
                        'Simple linear': 'simple',
                        'Weighted': 'weighted',
                        'Manual': 'manual'
                    }
                    method_key = method_map.get(preferred_method, 'zero')
                    
                    method_data = cal_data.get(method_key)
                    if not method_data:
                        method_data = cal_data.get('weighted', cal_data.get('simple', cal_data.get('zero', cal_data.get('manual',{}))))
                    
                    if method_data and 'slope' in method_data and self.average_transport_rate > 0:
                        slope = method_data['slope']
                        conversion_factor = slope / (self.average_transport_rate * 1000)
                
                cache[display_label] = {
                    'element_key': element_key,
                    'conversion_factor': conversion_factor
                }
        
        return cache
                
    def _update_periodic_table_selections(self):
        """
        Update periodic table with current isotope selections.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        for element_symbol, isotopes in self.selected_isotopes.items():
            if element_symbol in self.periodic_table_widget.buttons:
                button = self.periodic_table_widget.buttons[element_symbol]
                if button.isotope_display:
                    for isotope in isotopes:
                        button.isotope_display.select_preferred_isotope(isotope)     
                        
    #----------------------------------------------------------------------------------------------------------
    #------------------------------------detection parameters--------------------------------------------
    #----------------------------------------------------------------------------------------------------------
                        
    def update_parameters_table(self, force=True):
        """
        Rebuild the detection-parameters table.

        Wrapped so that painting is suppressed during the rebuild and so that
        redundant rebuilds triggered by the same user action are skipped when
        nothing relevant has changed. Pass force=False to allow skipping.
        """
        try:
            signature = (
                self.current_sample,
                tuple(sorted(
                    (element, float(isotope))
                    for element, isotopes in self.selected_isotopes.items()
                    for isotope in isotopes
                )),
                getattr(self, '_sigma_mode', 'global'),
                len(getattr(self, 'detected_peaks', {}) or {}),
            )
        except Exception:
            signature = None

        if signature is not None:
            if not force and signature == getattr(self, '_param_table_signature', None):
                return
            self._param_table_signature = signature

        if hasattr(self, 'logger'):
            self.logger.debug("update_parameters_table: rebuilding (force=%s)", force)

        self.parameters_table.setUpdatesEnabled(False)
        try:
            self._populate_parameters_table()
        finally:
            self.parameters_table.setUpdatesEnabled(True)

    def _populate_parameters_table(self):
        """
        Populate detection parameters table with element-specific settings.
        Uses model.populate() — no widgets are created, so no HWND/DWM cost.
        """
        saved_params = self.sample_parameters.get(self.current_sample, {})

        if self.current_sample and self.current_sample in self.data_by_sample:
            current_sample_data = self.data_by_sample[self.current_sample]
            filtered = {}
            for element, isotopes in self.selected_isotopes.items():
                with_data = [
                    iso for iso in isotopes
                    if any(abs(dm - iso) < 0.001 for dm in current_sample_data)
                ]
                if with_data:
                    filtered[element] = with_data
            isotopes_to_show = filtered
        else:
            isotopes_to_show = self.selected_isotopes

        element_items = sorted(
            [
                (f"{element}-{isotope:.4f}", float(isotope))
                for element, isotopes in isotopes_to_show.items()
                for isotope in isotopes
            ],
            key=lambda x: x[1],
        )

        global_s = getattr(self, '_global_sigma', 0.55)

        rows = []
        for element_key, _ in element_items:
            sp = saved_params.get(element_key, {})
            sigma = sp.get('sigma', global_s)
            rows.append({
                'element_label':    self.get_formatted_label(element_key),
                'element_key':      element_key,
                'include':          sp.get('include', True),
                'method':           sp.get('method', 'CPLN table'),
                'sigma':            sigma,
                '_sigma_highlighted': abs(sigma - global_s) > 1e-4,
                'manual_threshold': sp.get('manual_threshold', 10.0),
                'min_continuous':   float(sp.get('min_continuous', 1)),
                'alpha':            sp.get('alpha', 0.000001),
                'iterative':        sp.get('iterative', True),
                'use_window_size':  sp.get('use_window_size', False),
                'window_size':      int(sp.get('window_size', 5000)),
                'integration_method': sp.get('integration_method', 'Background'),
                'split_method':     sp.get('split_method', '1D Watershed'),
                'valley_ratio':     sp.get('valley_ratio', 0.50),
            })

        self.parameters_table.populate(rows)

        self._build_element_lookup_cache()
        self.color_parameters_table_rows()

        if hasattr(self, 'element_picker'):
            self.element_picker.set_elements(
                [(ek, self.get_formatted_label(ek)) for ek, _ in element_items]
            )
            cur_key = self._current_element_key()
            if cur_key:
                self.element_picker.set_current_key(cur_key, emit=False)

    def color_parameters_table_rows(self):
        """
        Highlight parameter table rows red when >=90% of that element's
        detected particles are in the critical SNR tier (SNR <= 1.1).
        Requires at least 10 particles to trigger; fewer than 10 are ignored.
        """
        if not hasattr(self, 'detected_peaks') or not self.detected_peaks:
            return

        tiers = tier_colors(theme.palette)
        red_bg = QBrush(QColor(tiers['critical']))
        red_fg = QBrush(QColor(tiers['text']))

        for row in range(self.parameters_table.rowCount()):
            label_item = self.parameters_table.item(row, 0)
            if not label_item:
                continue
            display_label = label_item.text()

            particles = None
            for element, isotopes in self.selected_isotopes.items():
                for isotope in isotopes:
                    element_key = f"{element}-{isotope:.4f}"
                    if self.get_formatted_label(element_key) == display_label:
                        particles = self.detected_peaks.get((element, isotope))
                        break
                if particles is not None:
                    break

            total = len(particles) if particles else 0
            highlight_red = (
                total >= 10 and
                sum(1 for p in particles if p.get('SNR', 0) <= 1.1) / total * 100 >= 90
            )

            if highlight_red:
                self.parameters_table.set_row_colors(row, bg=red_bg, fg=red_fg)
            else:
                self.parameters_table.set_row_colors(row, bg=QBrush(), fg=QBrush())

    def load_or_initialize_parameters(self, sample_name):
        """
        Load or initialize detection parameters for sample.
        
        Args:
            self: MainWindow instance
            sample_name (str): Name of sample
            
        Returns:
            None
        """
        if sample_name not in self.sample_parameters:
            self.sample_parameters[sample_name] = {}

            if hasattr(self, 'sigma_spinbox'):
                current_sigma = self.sigma_spinbox.value()
            elif hasattr(self, '_global_sigma'):
                current_sigma = self._global_sigma
            else:
                current_sigma = 0.55
            
            for element, isotopes in self.selected_isotopes.items():
                for isotope in isotopes:
                    element_key = f"{element}-{isotope:.4f}"
                    
                    self.sample_parameters[sample_name][element_key] = {
                        'include': True,
                        'method': "CPLN table",
                        'manual_threshold': 10.0,
                        'min_continuous': 1,
                        'alpha': 0.000001,
                        'integration_method': "Background",
                        'iterative': True, 
                        'max_iterations': 4,  
                        'sigma': current_sigma,  
                        'use_window_size': False,  
                        'window_size': 5000,
                        'split_method': "1D Watershed",
                        'valley_ratio': 0.50,
                    }
        else:
            if hasattr(self, 'sigma_spinbox'):
                self.sigma_spinbox.blockSignals(True)
                self.sigma_spinbox.setValue(getattr(self, '_global_sigma', 0.55))
                self.sigma_spinbox.blockSignals(False)
        
        
    def save_current_parameters(self):
        """Save current table parameters back to sample_parameters dict."""
        if not self.current_sample:
            return

        current_params = {}
        for row in range(self.parameters_table.rowCount()):
            d = self.parameters_table.get_row_params(row)
            element_key = d.get('element_key', '')
            if not element_key:
                continue
            current_params[element_key] = {
                'include':            d.get('include', True),
                'method':             d.get('method', 'CPLN table'),
                'manual_threshold':   d.get('manual_threshold', 10.0),
                'min_continuous':     d.get('min_continuous', 1),
                'alpha':              d.get('alpha', 0.000001),
                'iterative':          d.get('iterative', True),
                'max_iterations':     4,
                'sigma':              d.get('sigma', getattr(self, '_global_sigma', 0.55)),
                'use_window_size':    d.get('use_window_size', False),
                'window_size':        d.get('window_size', 5000),
                'integration_method': d.get('integration_method', 'Background'),
                'split_method':       d.get('split_method', '1D Watershed'),
                'valley_ratio':       d.get('valley_ratio', 0.50),
            }

        self.sample_parameters[self.current_sample] = current_params

    def update_parameter_ranges(self, row, method):
        """No-op: enabled states are now derived by the delegate from model data."""
        pass

    def get_element_parameters(self, row):
        """Get detection parameters from model row (replaces cellWidget reads)."""
        d = self.parameters_table.get_row_params(row)
        return {
            'element':            d.get('element_label', ''),
            'include':            d.get('include', True),
            'method':             d.get('method', 'CPLN table'),
            'manual_threshold':   d.get('manual_threshold', 10.0),
            'min_continuous':     d.get('min_continuous', 1),
            'alpha':              d.get('alpha', 0.000001),
            'iterative':          d.get('iterative', True),
            'use_window_size':    d.get('use_window_size', False),
            'window_size':        d.get('window_size', 5000),
            'integration_method': d.get('integration_method', 'Background'),
            'split_method':       d.get('split_method', '1D Watershed'),
            'valley_ratio':       d.get('valley_ratio', 0.50),
            'sigma':              d.get('sigma', getattr(self, '_global_sigma', 0.55)),
        }

    def _on_param_model_changed(self, row: int, col: int):
        """
        Called when the user edits any cell in the parameters table.
        Routes to the correct handler based on which column changed.
        """
        if getattr(self, '_suppress_model_callbacks', False):
            return
        if col == COL_SIGMA:
            value = self.parameters_table.get_row_params(row).get(
                'sigma', getattr(self, '_global_sigma', 0.55))
            self._on_per_element_sigma_changed(row, value)
        else:
            self.on_parameter_changed(row)
        
    def on_parameter_changed(self, row):
        """
        Handle parameter change in table.
        
        Args:
            self: MainWindow instance
            row (int): Table row index
            
        Returns:
            None
        """
        if not self.current_sample:
            return
            
        element_item = self.parameters_table.item(row, 0)
        if element_item:
            element_name = element_item.text()
            parameters = self.get_element_parameters(row)
            
            self.user_action_logger.log_action(
                'PARAMETER_CHANGE',
                f"Changed parameters for {element_name}",
                context={
                    'element': element_name,
                    'sample': self.current_sample,
                    'new_parameters': parameters
                }
            )
            return
            
        display_label = element_item.text()
        
        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                element_key = f"{element}-{isotope:.4f}"
                if self.get_formatted_label(element_key) == display_label:
                    self.mark_element_changed(self.current_sample, element_key)
                    break
        
        self.save_current_parameters()
        self.unsaved_changes = True

        
    def _on_element_selector_activated(self, element_key):
        """Switch the plotted element when a chip in the quick-selector is
        activated (clicked or reached with the arrow keys).

        Routes through the existing ``parameters_table_clicked`` logic by
        finding the matching table row, so plotting, results and summary all
        update exactly as they do on a table click.
        """
        if getattr(self, 'showing_all_signals', False):
            return
        target_label = self.get_formatted_label(element_key)
        for row in range(self.parameters_table.rowCount()):
            item = self.parameters_table.item(row, 0)
            if item is not None and item.text() == target_label:
                self.parameters_table.selectRow(row)
                self.parameters_table_clicked(row, 0)
                break

    def parameters_table_clicked(self, row, column):
        """
        Handle click on parameters table row.
        
        Args:
            self: MainWindow instance
            row (int): Clicked row index
            column (int): Clicked column index
            
        Returns:
            None
        """
        if row >= 0:
            if hasattr(self, 'showing_all_signals') and self.showing_all_signals:
                return

            current_x_range = None
            current_y_range = None
            if hasattr(self.plot_widget, 'viewRect'):
                try:
                    view_rect = self.plot_widget.viewRect()
                    current_x_range = [view_rect.left(), view_rect.right()]
                    current_y_range = [view_rect.top(), view_rect.bottom()]
                except:
                    pass
                    
            element_item = self.parameters_table.item(row, 0)
            if element_item:
                display_label = element_item.text()
                
                if display_label in self._display_label_to_element:
                    element, isotope, element_key = self._display_label_to_element[display_label]
                    self.current_element = element
                    self.current_isotope = isotope

                    if hasattr(self, 'element_picker'):
                        self.element_picker.set_current_key(element_key, emit=False)

                    isotope_key = self.find_closest_isotope(isotope)
                    if isotope_key is not None and isotope_key in self.data:
                        self.results_table.setRowCount(0)
                        
                        signal = self.data[isotope_key]
                        
                        params = self.get_element_parameters(row)
                        
                        if (element, isotope) in self.detected_peaks:
                            detected_particles = self.detected_peaks[(element, isotope)]
                            
                            try:
                                stored_values = self.element_thresholds[self.current_sample][element_key]
                                lambda_bkgd = stored_values.get('background', 0)
                                threshold = stored_values.get('threshold', 0)
                            except KeyError:
                                lambda_bkgd = 0
                                threshold = 0
                            
                            self.plot_results(
                                element_key,
                                signal,
                                detected_particles,
                                lambda_bkgd,
                                threshold,
                                preserve_view_range=(current_x_range, current_y_range)
                            )
                            
                            self.update_results_table(
                                detected_particles,
                                signal,
                                element,
                                isotope
                            )
                            self.update_element_summary(element, isotope, detected_particles)
                        else:
                            self.plot_widget.clear()
                            self.plot_widget.plot(
                                self.time_array,
                                signal,
                                pen='b',
                                name=f'Raw Signal {display_label}'
                            )
                            
                            if current_x_range and current_y_range:
                                try:
                                    self.plot_widget.setXRange(current_x_range[0], current_x_range[1], padding=0)
                                    self.plot_widget.setYRange(current_y_range[1], current_y_range[0], padding=0)
                                except:
                                    self.plot_widget.enableAutoRange()
                            else:
                                self.plot_widget.enableAutoRange()

                            try:
                                self._rebuild_plot_exclusion_regions()
                            except Exception as e:
                                self.logger.debug(f"Could not restore exclusion regions after raw plot: {e}")
                    return
                
    def toggle_manual_threshold_input(self, row, method):
        """No-op: threshold cell enabled state is derived by the delegate from method."""
        pass

    def toggle_window_size_parameters(self, row, state):
        """No-op: window size enabled state is derived by the delegate from use_window_size."""
        pass
        
    def open_batch_parameters_dialog(self):
        """
        Open dialog for batch editing element parameters.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.user_action_logger.log_dialog_open('Batch Parameters', 'Batch Parameters Dialog')
        if not self.selected_isotopes:
            QMessageBox.warning(self, "No Elements", "Please select elements first.")
            return
            
        elements = {}
        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                element_key = f"{element}-{isotope:.4f}"
                display_label = self.get_formatted_label(element_key)
                elements[element_key] = display_label
        
        current_parameters = self.sample_parameters.get(self.current_sample, {})
        
        all_samples = list(self.sample_to_folder_map.keys())
        
        dialog = BatchElementParametersDialog(
            self, 
            elements, 
            current_parameters,
            all_samples
        )
        
        if dialog.exec() == QDialog.Accepted:
            selected_elements = dialog.selected_elements
            parameters = dialog.get_parameters()
            selected_samples = dialog.get_selected_samples()
            
            if not selected_samples:
                selected_samples = [self.current_sample]

            self.user_action_logger.log_action(
                'PARAMETER_CHANGE', 'Batch parameters applied',
                {'elements': list(selected_elements),
                 'sample_count': len(selected_samples),
                 'method': parameters.get('method', 'unknown')})
            
            for sample_name in selected_samples:
                if sample_name not in self.sample_parameters:
                    self.sample_parameters[sample_name] = {}
                    
                for element_key in selected_elements:
                    self.sample_parameters[sample_name][element_key] = parameters.copy()
            
            if self.current_sample in selected_samples:
                self.update_parameters_table()
            
            QMessageBox.information(
                self, 
                "Parameters Updated", 
                f"Updated parameters for {len(selected_elements)} elements across {len(selected_samples)} samples."
            )
            
    def filter_table(self):
        """
        Filter parameters table based on search text.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        search_text = self.search_box.text().lower()
        for row in range(self.parameters_table.rowCount()):
            match = False
            for col in range(self.parameters_table.columnCount()):
                item = self.parameters_table.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break
            self.parameters_table.setRowHidden(row, not match)
            
    def on_sigma_changed(self, value):
        """Update sigma value for all samples and elements (Global mode)."""
        self._global_sigma = value
        per_isotope_mode   = getattr(self, '_sigma_mode', 'global') == 'per_isotope'

        for sample_name in self.sample_parameters:
            for element_key, el_params in self.sample_parameters[sample_name].items():
                if per_isotope_mode:
                    if not el_params.get('_sigma_from_sia', False):
                        el_params['sigma'] = value
                else:
                    el_params['sigma'] = value
                self.mark_element_changed(sample_name, element_key)

        self._suppress_model_callbacks = True
        try:
            with self.parameters_table._model.bulk_update():
                for row in range(self.parameters_table.rowCount()):
                    d = self.parameters_table.get_row_params(row)
                    if per_isotope_mode:
                        display_label = d.get('element_label', '')
                        for element, isotopes in self.selected_isotopes.items():
                            for isotope in isotopes:
                                element_key = f"{element}-{isotope:.4f}"
                                if self.get_formatted_label(element_key) == display_label:
                                    el_params = self.sample_parameters.get(
                                        self.current_sample, {}).get(element_key, {})
                                    if not el_params.get('_sigma_from_sia', False):
                                        self.parameters_table.set_row_field(row, 'sigma', value)
                                        self.parameters_table.set_row_field(row, '_sigma_highlighted', False)
                                    break
                    else:
                        self.parameters_table.set_row_field(row, 'sigma', value)
                        self.parameters_table.set_row_field(row, '_sigma_highlighted', False)
        finally:
            self._suppress_model_callbacks = False

        self.save_current_parameters()
        self.unsaved_changes = True
        total_elements = sum(len(params) for params in self.sample_parameters.values())
        total_samples  = len(self.sample_parameters)
        self.status_label.setText(
            f"Updated sigma to {value:.3f} for {total_elements} elements across {total_samples} samples"
        )

    def _on_sigma_mode_changed(self, global_checked):
        """Handle toggling between Global and Per-Isotope sigma modes."""
        self._sigma_mode = 'global' if global_checked else 'per_isotope'
        per_isotope_mode = not global_checked

        if not per_isotope_mode:
            self._suppress_model_callbacks = True
            try:
                with self.parameters_table._model.bulk_update():
                    for row in range(self.parameters_table.rowCount()):
                        self.parameters_table.set_row_field(row, 'sigma', self._global_sigma)
                        self.parameters_table.set_row_field(row, '_sigma_highlighted', False)
            finally:
                self._suppress_model_callbacks = False

            for sample_name in self.sample_parameters:
                for element_key, el_params in self.sample_parameters[sample_name].items():
                    el_params['sigma'] = self._global_sigma
                    el_params['_sigma_from_sia'] = False
                    self.mark_element_changed(sample_name, element_key)
            self.save_current_parameters()
            self.status_label.setText(
                f"Sigma mode: Global ({self._global_sigma:.3f} applied to all isotopes)"
            )
        else:
            if self.sia_manager.is_sia_loaded() and self.sia_manager.per_mass_distributions:
                self.sia_manager._assign_per_mass_sigma()
                self.update_parameters_table()
                self.status_label.setText(
                    "Sigma mode: Per-Isotope (SIA sigmas applied; edit cells to override)"
                )
            else:
                self.status_label.setText(
                    "Sigma mode: Per-Isotope (edit sigma cells directly; load SIA for auto-assignment)"
                )

        self.unsaved_changes = True

    def _on_per_element_sigma_changed(self, row, value):
        """Handle a per-element sigma edit — update model highlight and sample_parameters."""
        if not self.current_sample:
            return

        d = self.parameters_table.get_row_params(row)
        display_label = d.get('element_label', '')
        if not display_label:
            return

        global_s     = getattr(self, '_global_sigma', 0.55)
        highlighted  = abs(value - global_s) > 1e-4

        self._suppress_model_callbacks = True
        try:
            self.parameters_table.set_row_field(row, '_sigma_highlighted', highlighted)
        finally:
            self._suppress_model_callbacks = False

        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                element_key = f"{element}-{isotope:.4f}"
                if self.get_formatted_label(element_key) == display_label:
                    el_params = self.sample_parameters.get(
                        self.current_sample, {}).get(element_key)
                    if el_params is not None:
                        el_params['sigma'] = value
                        el_params['_sigma_from_sia'] = highlighted
                        self.mark_element_changed(self.current_sample, element_key)

                    self.save_current_parameters()
                    self.unsaved_changes = True
                    self.status_label.setText(
                        f"Sigma for {display_label} updated to {value:.3f}"
                    )
                    return

    #----------------------------------------------------------------------------------------------------------
    #------------------------------------peak detection and analysis--------------------------------------------
    #----------------------------------------------------------------------------------------------------------

    def _current_element_key(self):
        """element_key string for the currently displayed element, or None.
        Returns:
            None
        """
        el = getattr(self, 'current_element', None)
        iso = getattr(self, 'current_isotope', None)
        if el is None or iso is None:
            return None
        try:
            return f"{el}-{iso:.4f}"
        except Exception:
            return None

    def _visible_exclusion_entries_for(self, sample_name, element_key):
        """Entries that should be drawn on the plot right now.

        - 'sample'-scope regions are always shown (they apply to every element).
        - 'element'-scope regions are only shown when element_key matches the
          region's stored element_key, so each element's exclusion bands are
          private to that element and don't appear while viewing other elements.
        Args:
            sample_name (Any): The sample name.
            element_key (Any): The element key.
        Returns:
            list: Result of the operation.
        """
        entries = self._exclusion_regions_by_sample.get(sample_name, [])
        return [
            e for e in entries
            if e.get('scope') == 'sample'
            or e.get('element_key') == element_key
        ]

    def _rebuild_plot_exclusion_regions(self):
        """Redraw the plot's exclusion bands from the bookkeeping store.

        Only needed on sample switch — element switches preserve bands
        automatically via the plot widget's clear() override (which
        detaches and re-attaches the same region objects instead of
        destroying and recreating them). Safe to call with no current
        sample (it just clears the plot's bands).
        """
        sample = getattr(self, 'current_sample', None)
        element_key = self._current_element_key()
        visible = (self._visible_exclusion_entries_for(sample, element_key)
                   if sample else [])

        try:
            self.plot_widget.exclusionRegionsChanged.disconnect(
                self._on_exclusion_regions_changed)
        except Exception:
            pass
        try:
            self.plot_widget.set_exclusion_regions(visible)
        finally:
            try:
                self.plot_widget.exclusionRegionsChanged.connect(
                    self._on_exclusion_regions_changed)
            except Exception:
                pass

    def _on_exclusion_regions_changed(self):
        """Sync the plot's current bands back into the bookkeeping store.

        The plot owns the authoritative geometry (drag / resize happens
        there), but scope and element tagging live in MainWindow. Since
        all regions are visible at all times, the plot's region list
        maps 1-to-1 (positionally) onto the store. Dragged / resized
        bands keep their existing element_key; new bands inherit the
        current element context; bands whose scope was retagged via the
        context menu update their element_key accordingly.
        """
        sample = getattr(self, 'current_sample', None)
        if not sample:
            return
        try:
            plot_regions = self.plot_widget.get_exclusion_regions()
        except Exception as e:
            self.logger.debug(f"get_exclusion_regions failed: {e}")
            return

        element_key = self._current_element_key()
        old_all = self._exclusion_regions_by_sample.get(sample, [])

        new_store = []
        for i, (lo, hi, scope) in enumerate(plot_regions):
            if i < len(old_all):
                prev = old_all[i]
                new_store.append({
                    'bounds': (float(lo), float(hi)),
                    'scope': scope,
                    'element_key': (None if scope == 'sample'
                                    else (prev.get('element_key')
                                          or element_key)),
                })
            else:
                new_store.append({
                    'bounds': (float(lo), float(hi)),
                    'scope': scope,
                    'element_key': (None if scope == 'sample'
                                    else element_key),
                })

        self._exclusion_regions_by_sample[sample] = new_store
        
    @log_user_action('CLICK', 'Clicked detect peaks button')
    def detect_particles(self):
        """
        Run particle detection, honouring per-sample / per-element
        exclusion regions.

        Masking strategy per sample:
          - A 'sample'-scope band masks every isotope in the sample.
          - An 'element'-scope band masks only the signal array of its
            tagged element_key.
        Excluded indices are filled with the median of the kept portion
        of that signal — this keeps the iterative background estimator
        in peak_detection.py unbiased, and guarantees no peak in the
        band can cross the threshold. Originals are always restored,
        even on exception. As a safety net, any detected peak whose
        centre time still landed inside one of its applicable bands is
        dropped from the results.
        Returns:
            object: Result of the operation.
        """
        self.user_action_logger.log_analysis_step(
            'Peak Detection Started',
            parameters={
                'sample': self.current_sample,
                'elements': list(self.selected_isotopes.keys()) if self.selected_isotopes else []
            }
        )
        self.save_current_parameters()
        if hasattr(self, 'sigma_spinbox'):
            current_sigma = self.sigma_spinbox.value()
            for sample_name in self.sample_parameters:
                for element_key in self.sample_parameters[sample_name]:
                    existing_sigma = self.sample_parameters[sample_name][element_key].get('sigma')
                    # Only fill missing sigmas as fallback — never override stored values
                    if existing_sigma is None:
                        self.sample_parameters[sample_name][element_key]['sigma'] = current_sigma

        backups = {}
        exclusion_map = getattr(self, '_exclusion_regions_by_sample', {}) or {}

        def _element_key_to_isotope_key(sample_name, element_key):
            """
            Args:
                sample_name (Any): The sample name.
                element_key (Any): The element key.
            Returns:
                object: Result of the operation.
            """
            try:
                _el, iso_str = element_key.rsplit('-', 1)
                iso = float(iso_str)
            except Exception:
                return None
            return self.find_closest_isotope(iso)

        for sname, entries in exclusion_map.items():
            if not entries or sname not in self.data_by_sample:
                continue
            time_arr = self.time_array_by_sample.get(sname)
            if time_arr is None:
                continue
            time_arr = np.asarray(time_arr)

            sample_bands = [e['bounds'] for e in entries
                            if e.get('scope') == 'sample']
            per_isotope_extra = {}
            for e in entries:
                if e.get('scope') == 'sample':
                    continue
                ek = e.get('element_key')
                if not ek:
                    continue
                ik = _element_key_to_isotope_key(sname, ek)
                if ik is None:
                    continue
                per_isotope_extra.setdefault(ik, []).append(e['bounds'])

            if not sample_bands and not per_isotope_extra:
                continue

            original = self.data_by_sample[sname]
            masked = {}
            any_change = False
            for isotope_key, sig in original.items():
                arr = np.asarray(sig)
                bands = list(sample_bands)
                bands.extend(per_isotope_extra.get(isotope_key, []))
                if not bands or len(arr) != len(time_arr):
                    masked[isotope_key] = sig
                    continue
                mask = np.ones(len(time_arr), dtype=bool)
                for x0, x1 in bands:
                    mask &= ~((time_arr >= x0) & (time_arr <= x1))
                if mask.all():
                    masked[isotope_key] = sig
                    continue
                new_sig = arr.astype(float, copy=True)
                kept = new_sig[mask]
                fill = float(np.median(kept)) if kept.size else 0.0
                new_sig[~mask] = fill
                masked[isotope_key] = new_sig
                any_change = True

            if any_change:
                backups[sname] = original
                self.data_by_sample[sname] = masked
                if sname == self.current_sample:
                    self.data = masked

        try:
            if hasattr(self.peak_detector, 'incremental_enabled') and self.peak_detector.incremental_enabled:
                result = self.peak_detector.detect_particles_incremental(self)
            else:
                result = self.peak_detector.detect_particles(self)
        finally:
            for sname, original in backups.items():
                self.data_by_sample[sname] = original
                if sname == self.current_sample:
                    self.data = original


        for sname, entries in exclusion_map.items():
            if not entries:
                continue
            time_arr = self.time_array_by_sample.get(sname)
            detected = self.sample_detected_peaks.get(sname)
            if time_arr is None or not detected:
                continue
            time_arr = np.asarray(time_arr)
            n = len(time_arr)

            sample_bands = [e['bounds'] for e in entries
                            if e.get('scope') == 'sample']
            per_ek_extra = {}
            for e in entries:
                if e.get('scope') == 'sample':
                    continue
                ek = e.get('element_key')
                if ek:
                    per_ek_extra.setdefault(ek, []).append(e['bounds'])

            for key, particles in list(detected.items()):
                if not particles:
                    continue
                try:
                    el, iso = key
                    ek_here = f"{el}-{iso:.4f}"
                except Exception:
                    ek_here = None
                bands = list(sample_bands)
                if ek_here:
                    bands.extend(per_ek_extra.get(ek_here, []))
                if not bands:
                    continue

                kept = []
                for p in particles:
                    if p is None:
                        continue
                    left = int(p.get('left_idx', 0))
                    right = int(min(p.get('right_idx', left), n - 1))
                    if left < 0 or left >= n:
                        kept.append(p); continue
                    t_centre = 0.5 * (time_arr[left] + time_arr[right])
                    if not any(x0 <= t_centre <= x1 for x0, x1 in bands):
                        kept.append(p)
                detected[key] = kept

        if getattr(self, 'saturation_filter_enabled', False):
            if self.current_sample:
                self.saturation_filtered_peaks.pop(self.current_sample, None)
                self.saturation_filtered_multi.pop(self.current_sample, None)
                self.saturation_windows.pop(self.current_sample, None)
                self.saturation_excluded_time_s.pop(self.current_sample, None)
            n_sat = self.apply_saturation_filter()
            if n_sat:
                excl_ms = self.get_saturation_excluded_time() * 1000.0
                self.status_label.setText(
                    f"Non-linearity filter: {n_sat} particle event(s) excluded "
                    f"(FWHM > {self.saturation_filter_ms:g} ms), "
                    f"{excl_ms:.1f} ms removed from the analysis time")
            self._refresh_after_saturation_change()

        return result
        
    def process_single_sample(self, sample_name):
        """
        Process particle detection for single sample.
        
        Args:
            self: MainWindow instance
            sample_name (str): Sample name
            
        Returns:
            Detection results
        """
        return self.peak_detector.process_single_sample(self, sample_name)
        
    def detect_peaks_with_poisson(self, signal, alpha=0.000001, 
         sample_name=None, element_key=None, method="CPLN table",
            manual_threshold=10.0):
        """
        Detect peaks using Poisson-based methods.
        
        Args:
            self: MainWindow instance
            signal (ndarray): Signal data array
            alpha (float): Significance level
            sample_name (str, optional): Sample name
            element_key (str, optional): Element identifier
            method (str): Detection method name
            manual_threshold (float): Manual threshold value
            
        Returns:
            Detection results
        """
        return self.peak_detector.detect_peaks_with_poisson(
            signal, alpha, 
            sample_name, element_key, method, manual_threshold, 
            self.element_thresholds, self.current_sample
        )

    def find_particles(self, time, raw_signal, lambda_bkgd, threshold, 
            min_continuous_points=1, integration_method="Background",
            split_method="1D Watershed", sigma=0.55, min_valley_ratio=0.50):
        """
        Find individual particles in signal.
        
        Args:
            self: MainWindow instance
            time (ndarray): Time array
            raw_signal (ndarray): Raw signal array
            lambda_bkgd (float): Background level
            threshold (float): Detection threshold
            min_width (int): Minimum particle width
            min_continuous_points (int): Minimum continuous points
            integration_method (str): Integration method name
            min_valley_ratio (float): Valley-to-peak ratio for watershed splitting
            
        Returns:
            List of particle dictionaries
        """
        return self.peak_detector.find_particles(
            time, raw_signal, lambda_bkgd, threshold,
            min_continuous_points=min_continuous_points,
            integration_method=integration_method,
            split_method=split_method,
            sigma=sigma,
            min_valley_ratio=min_valley_ratio,
        )

    def process_multi_element_particles(self, all_particles):
        """
        Process and identify multi-element particles.
        
        Args:
            self: MainWindow instance
            all_particles (list): List of all detected particles
            
        Returns:
            None
        """
        self.multi_element_particles = self.peak_detector.process_multi_element_particles(
            all_particles, self.time_array, self.sample_detected_peaks, 
            self.selected_isotopes, self.get_formatted_label, 
            self.current_sample, self.element_thresholds, self.parameters_table,
            min_overlap_percentage=self.overlap_threshold_percentage
        )
    
    def mark_element_changed(self, sample_name, element_key):
        """
        Mark element as having changed parameters.
        
        Args:
            self: MainWindow instance
            sample_name (str): Sample name
            element_key (str): Element identifier
            
        Returns:
            None
        """
        if sample_name not in self.detection_states:
            self.detection_states[sample_name] = {}
        self.detection_states[sample_name][element_key] = 'changed'
        
    def get_parameter_hash(self, sample_name, element_key):
        """
        Generate hash of current parameters for change detection.
        
        Args:
            self: MainWindow instance
            sample_name (str): Sample name
            element_key (str): Element identifier
            
        Returns:
            str: MD5 hash of parameters
        """
        import hashlib
        
        params = self.sample_parameters.get(sample_name, {}).get(element_key, {})
        param_str = str(sorted(params.items()))
        return hashlib.md5(param_str.encode()).hexdigest()

    #----------------------------------------------------------------------------------------------------------
    #------------------------------------results display--------------------------------------------
    #----------------------------------------------------------------------------------------------------------

    def update_results_table(self, detected_particles, signal, element, isotope):
        """
        Update single element results table with detection results.
        
        Args:
            self: MainWindow instance
            detected_particles (list): List of detected particle dictionaries
            signal (ndarray): Signal data array
            element (str): Element symbol
            isotope (float): Isotope mass
            
        Returns:
            None
        """
        if not (hasattr(self, 'show_element_results_checkbox') and self.show_element_results_checkbox.isChecked()):
            return  
            
        header = self.results_table.horizontalHeader()
        current_sort_column = header.sortIndicatorSection()
        current_sort_order = header.sortIndicatorOrder()
        was_sorting_enabled = self.results_table.isSortingEnabled()
        
        self.results_table.setSortingEnabled(False)
        
        selected_rows = set()
        for item in self.results_table.selectedItems():
            selected_rows.add(item.row())
        
        self.results_table.setRowCount(0)
        self.results_table.setColumnCount(6)
        
        headers = [
            'Element', 'Peak Start (s)', 'Peak End (s)', 'Total Counts',
            'Peak Height (counts)', 'Height/Threshold'
        ]
        self.results_table.setHorizontalHeaderLabels(headers)
        self.results_table.hideColumn(0)
        
        element_key = f"{element}-{isotope:.4f}"
        display_label = self.get_formatted_label(element_key)
        
        for particle in detected_particles:
            if particle is None:
                continue
                
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            
            snr = particle.get('SNR', particle['max_height'] / particle.get('threshold', 1))
            
            items = [
                QTableWidgetItem(display_label),
                NumericTableWidgetItem(f"{self.time_array[particle['left_idx']]:.4f}"),
                NumericTableWidgetItem(f"{self.time_array[particle['right_idx']]:.4f}"),
                NumericTableWidgetItem(f"{particle['total_counts']:.0f}"),
                NumericTableWidgetItem(f"{particle['max_height']:.0f}"),
                NumericTableWidgetItem(f"{snr:.2f}")
            ]
            
            tiers = tier_colors(theme.palette)
            text_qcolor = QColor(tiers['text'])

            for col, item in enumerate(items):
                if col > 0:
                    if snr <= 1.1:
                        item.setBackground(QBrush(QColor(tiers['critical'])))
                    elif snr <= 1.2:
                        item.setBackground(QBrush(QColor(tiers['high'])))
                    elif snr <= 1.5:
                        item.setBackground(QBrush(QColor(tiers['medium'])))
                    else:
                        item.setBackground(QBrush(QColor(tiers['low'])))
                    item.setForeground(QBrush(text_qcolor))
                        
                self.results_table.setItem(row, col, item)
        
        if was_sorting_enabled:
            self.results_table.setSortingEnabled(True)
            
            if (current_sort_column >= 0 and 
                current_sort_column < self.results_table.columnCount()):
                self.results_table.sortItems(current_sort_column, current_sort_order)
        
        if selected_rows:
            for row in selected_rows:
                if row < self.results_table.rowCount():
                    for col in range(self.results_table.columnCount()):
                        item = self.results_table.item(row, col)
                        if item:
                            item.setSelected(True)

    def update_multi_element_table(self):
        """
        Update multi-element particle results table.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        if not (hasattr(self, 'show_particle_results_checkbox') and self.show_particle_results_checkbox.isChecked()):
            return
            
        header = self.multi_element_table.horizontalHeader()
        current_sort_column = header.sortIndicatorSection()
        current_sort_order = header.sortIndicatorOrder()
        was_sorting_enabled = self.multi_element_table.isSortingEnabled()
        
        self.multi_element_table.setSortingEnabled(False)
        
        selected_rows = set()
        for item in self.multi_element_table.selectedItems():
            selected_rows.add(item.row())
        
        self.multi_element_table.clear()
        self.multi_element_table.setRowCount(len(self.multi_element_particles))
        
        included_elements = []
        for row in range(self.parameters_table.rowCount()):
            include_checkbox = self.parameters_table.cellWidget(row, 1)
            if include_checkbox.isChecked():
                element_item = self.parameters_table.item(row, 0)
                if element_item:
                    included_elements.append(element_item.text())
        
        headers = ['Particle #', 'Start Time (s)', 'End Time (s)'] + included_elements
        self.multi_element_table.setColumnCount(len(headers))
        self.multi_element_table.setHorizontalHeaderLabels(headers)

        for i, particle in enumerate(self.multi_element_particles):
            self.multi_element_table.setItem(i, 0, NumericTableWidgetItem(str(i+1)))
            self.multi_element_table.setItem(i, 1, NumericTableWidgetItem(f"{particle['start_time']:.6f}"))
            self.multi_element_table.setItem(i, 2, NumericTableWidgetItem(f"{particle['end_time']:.6f}"))
            
            for j, element_key in enumerate(included_elements, start=3):
                counts = particle['elements'].get(element_key, 0)
                self.multi_element_table.setItem(i, j, NumericTableWidgetItem(f"{counts:.0f}"))

        self.multi_element_table.resizeColumnsToContents()
        
        if was_sorting_enabled:
            self.multi_element_table.setSortingEnabled(True)
            
            if (current_sort_column >= 0 and 
                current_sort_column < self.multi_element_table.columnCount()):
                self.multi_element_table.sortItems(current_sort_column, current_sort_order)
        
        if selected_rows:
            for row in selected_rows:
                if row < self.multi_element_table.rowCount():
                    for col in range(self.multi_element_table.columnCount()):
                        item = self.multi_element_table.item(row, col)
                        if item:
                            item.setSelected(True)
                            
    def toggle_element_results(self, checked):
        """
        Show or hide single element results table.
        
        Args:
            self: MainWindow instance
            checked (bool): Checkbox state
            
        Returns:
            None
        """
        self.element_results_container.setVisible(checked)
        
        if checked:
            if (hasattr(self, 'current_element') and hasattr(self, 'current_isotope') and 
                (self.current_element, self.current_isotope) in self.detected_peaks):
                
                detected_particles = self.detected_peaks[(self.current_element, self.current_isotope)]
                
                isotope_key = self.find_closest_isotope(self.current_isotope)
                if isotope_key is not None and isotope_key in self.data:
                    signal = self.data[isotope_key]
                    self.update_results_table(detected_particles, signal, self.current_element, self.current_isotope)
            
            self.status_label.setText("Single element results table enabled")
        else:
            self.status_label.setText("Single element results table disabled (better performance)")

    def toggle_particle_results(self, checked):
        """
        Show or hide multi-element particle results table.
        
        Args:
            self: MainWindow instance
            checked (bool): Checkbox state
            
        Returns:
            None
        """
        self.particle_results_container.setVisible(checked)
        
        if checked:
            if hasattr(self, 'multi_element_particles') and self.multi_element_particles:
                
                self.update_multi_element_table()
            
            self.status_label.setText("Multi-element particle results table enabled")
        else:
            self.status_label.setText("Multi-element particle results table disabled (better performance)")
        
    def restore_results_tables(self, sample_name):
        """
        Restore results tables for selected sample.
        
        Args:
            self: MainWindow instance
            sample_name (str): Sample name
            
        Returns:
            None
        """
        if hasattr(self, 'show_element_results_checkbox') and self.show_element_results_checkbox.isChecked():
            if sample_name in self.sample_results_data:
                results_data = self.sample_results_data[sample_name]
                self.results_table.setRowCount(len(results_data))
                for row, row_data in enumerate(results_data):
                    for col, value in enumerate(row_data):
                        item = QTableWidgetItem(str(value))
                        self.results_table.setItem(row, col, item)
            else:
                self.results_table.setRowCount(0)
        
        if hasattr(self, 'show_particle_results_checkbox') and self.show_particle_results_checkbox.isChecked():
            if sample_name in self.sample_particle_data:
                self.multi_element_particles = self.sample_particle_data[sample_name]
                self.update_multi_element_table()
            else:
                self.multi_element_table.setRowCount(0)  
    
    def update_element_summary(self, element, isotope, detected_particles):
        """
        Update summary statistics for selected element.
        
        Args:
            self: MainWindow instance
            element (str): Element symbol
            isotope (float): Isotope mass
            detected_particles (list): List of detected particle dictionaries
            
        Returns:
            None
        """
        self._last_summary_args = (element, isotope, detected_particles)

        element_key = f"{element}-{isotope:.4f}"
        display_label = self.get_formatted_label(element_key)
        particle_count = len(detected_particles) if detected_particles else 0
        
        if detected_particles and particle_count > 0:
            valid_particles = [p for p in detected_particles if p is not None]
            total_counts = sum(p.get('total_counts', 0) for p in valid_particles)
            mean_counts = total_counts / len(valid_particles) if valid_particles else 0
            
            sorted_counts = sorted([p.get('total_counts', 0) for p in valid_particles])
            median_counts = sorted_counts[len(sorted_counts)//2] if sorted_counts else 0
        else:
            total_counts = 0.00000
            mean_counts = 0.00000
            median_counts = 0.00000
            
        total_mass_fg = 0.00000
        mean_mass_fg = 0.00000
        median_mass_fg = 0.00000

        isotope_key = self.find_closest_isotope(isotope)
        overall_mean_signal = 0.00000
        background_signal = 0.00000
        threshold_counts = 0.00000
        
        if isotope_key and isotope_key in self.data:
            overall_mean_signal = float(np.mean(self.data[isotope_key]))
        
        if (self.current_sample in self.element_thresholds and 
            element_key in self.element_thresholds[self.current_sample]):
            threshold_data = self.element_thresholds[self.current_sample][element_key]
            background_signal = threshold_data.get('background', 0.00000)
            threshold_counts = threshold_data.get('threshold', 0.00000)
            background_signal = float(np.mean(background_signal))
            threshold_counts  = float(np.mean(threshold_counts))
        mass_values = []
        if (hasattr(self, 'average_transport_rate') and 
            self.average_transport_rate > 0 and 
            "Ionic Calibration" in self.calibration_results and
            element_key in self.calibration_results["Ionic Calibration"]):

            cal_data = self.calibration_results["Ionic Calibration"][element_key]
            
            preferred_method = self.isotope_method_preferences.get(element_key, 'Force through zero')
            method_map = {
                'Force through zero': 'zero',
                'Simple linear': 'simple',
                'Weighted': 'weighted',
                'Manual': 'manual'
            }
            method_key = method_map.get(preferred_method, 'zero')
                
            method_data = cal_data.get(method_key)
            if not method_data:
                method_data = cal_data.get('weighted', cal_data.get('simple', cal_data.get('zero', cal_data.get('manual',{}))))
            
            if method_data and 'slope' in method_data:
                slope = method_data['slope']
                conversion_factor = slope / (self.average_transport_rate * 1000)
                
                if conversion_factor > 0:
                    if detected_particles and valid_particles:
                        for particle in valid_particles:
                            counts = particle.get('total_counts', 0)
                            mass_fg = counts / conversion_factor
                            mass_values.append(mass_fg)

                        if mass_values:
                            total_mass_fg = sum(mass_values)
                            mean_mass_fg = total_mass_fg / len(mass_values)
                            sorted_mass = sorted(mass_values)
                            median_mass_fg = sorted_mass[len(sorted_mass)//2]
        
        sample = getattr(self, 'current_sample', None)
        particles_per_ml = self.particles_per_ml(sample, particle_count, element_key) if sample else 0.00000
        
        total_particles_all_elements = 0
        if hasattr(self, 'detected_peaks') and self.detected_peaks:
            for (elem, iso), particles in self.detected_peaks.items():
                total_particles_all_elements += len([p for p in particles if p is not None])
        
        percentage_of_all = (particle_count / total_particles_all_elements * 100) if total_particles_all_elements > 0 else 0.00000
        
        summary_html = f"""
        <style>{html_table_css(theme.palette)}</style>
        <table>
            <tr>
                <th>Element</th>
                <th>Total Particles</th>
                <th>Particles/mL</th>
                <th>Total Counts</th>
                <th>Mean Counts</th>
                <th>Median Counts</th>
                <th>Total Mass (fg)</th>
                <th>Mean Mass (fg)</th>
                <th>Median Mass (fg)</th>
                <th>Mean Signal (counts)</th>
                <th>Background (counts)</th>
                <th>Threshold (counts)</th>
                <th>% of All Elements</th>
            </tr>
            <tr{' class="no-particles"' if particle_count == 0 else ''}>
                <td>{display_label}</td>
                <td>{particle_count}</td>
                <td>{particles_per_ml:.5f}</td>
                <td>{total_counts:.5f}</td>
                <td>{mean_counts:.5f}</td>
                <td>{median_counts:.5f}</td>
                <td>{total_mass_fg:.5f}</td>
                <td>{mean_mass_fg:.5f}</td>
                <td>{median_mass_fg:.5f}</td>
                <td>{overall_mean_signal:.5f}</td>
                <td>{background_signal:.5f}</td>
                <td>{threshold_counts:.5f}</td>
                <td>{percentage_of_all:.5f}%</td>
            </tr>
        </table>
        """
        self.summary_label.setText(summary_html)                                
   
    @log_user_action('CLICK', 'Opened results dialog')
    def rebuild_particle_data(self, sample_name=None):
        """
        Rebuild the multi-element particle list of a sample from the
        current per-isotope detection results.

        The multi-element particle data shown in the Results dialog is a
        cache derived from sample_detected_peaks at detection time. When
        the per-isotope peaks change (for example after the detector
        non-linearity filter excludes events), this cache becomes stale.
        Calling this method regenerates it so the Results dialog and the
        exports reflect the current, filtered particles.

        Args:
            sample_name (str): Sample to rebuild. Defaults to the
                current sample.

        Returns:
            None
        """
        sname = sample_name or self.current_sample
        if not sname or sname not in self.sample_detected_peaks:
            return
        time_array = self.time_array_by_sample.get(sname)
        if time_array is None:
            return

        all_particles = []
        sample_data = self.data_by_sample.get(sname, {})
        for (element, isotope), particles in self.sample_detected_peaks[sname].items():
            if not particles:
                continue
            isotope_key = self.find_closest_isotope(isotope)
            if isotope_key and isotope_key in sample_data:
                signal = sample_data[isotope_key]
                all_particles.append({
                    'element': element,
                    'isotope': isotope,
                    'signal': signal,
                    'clusters': [(p['left_idx'], p['right_idx'])
                                 for p in particles if p],
                })

        try:
            rebuilt = self.peak_detector.process_multi_element_particles(
                all_particles, time_array,
                {sname: self.sample_detected_peaks[sname]},
                self.selected_isotopes, self.get_formatted_label,
                sname, {sname: self.element_thresholds.get(sname, {})},
                self.parameters_table,
                min_overlap_percentage=self.overlap_threshold_percentage)
            self.sample_particle_data[sname] = rebuilt
            if sname == self.current_sample:
                self.multi_element_particles = rebuilt
        except Exception as e:
            self.logger.debug(f"Particle data rebuild failed for {sname}: {e}")

    def show_results(self):
        """
        Display particle detection results in canvas dialog.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        if not self.current_sample or not self.sample_particle_data.get(self.current_sample):
            self.user_action_logger.log_action('ERROR', 'Attempted to show results with no data')
            QMessageBox.warning(self, "No Data", "No particle data available. Please run particle detection first.")
            return
        
        element_cache = self._build_element_conversion_cache()

        if getattr(self, 'saturation_filter_enabled', False):
            for sample_name in list(self.sample_particle_data.keys()):
                self.rebuild_particle_data(sample_name)

        all_samples_with_data = [sample for sample in self.sample_particle_data.keys() 
                                if self.sample_particle_data[sample]]
        
        if len(all_samples_with_data) > 1:
            from PySide6.QtWidgets import QProgressDialog
            progress = QProgressDialog("Calculating mass data for all samples...", "Cancel", 
                                    0, len(all_samples_with_data), self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            for i, sample_name in enumerate(all_samples_with_data):
                progress.setValue(i)
                progress.setLabelText(f"Processing {sample_name}...")
                QApplication.processEvents()
                
                if progress.wasCanceled():
                    break
                    
                particles = self.sample_particle_data[sample_name]
                self._calculate_mass_data_optimized(particles, element_cache)
            
            progress.close()
        else:
            particles = self.sample_particle_data[self.current_sample]
            if len(particles) > 1000:
                from PySide6.QtWidgets import QProgressDialog
                progress = QProgressDialog("Calculating mass data...", "Cancel", 0, len(particles), self)
                progress.setWindowModality(Qt.WindowModal)
                progress.show()
            else:
                progress = None
            
            self._calculate_mass_data_optimized(particles, element_cache, progress)
            
            if progress:
                progress.close()
        
        if self.canvas_results_dialog is None:
            self.canvas_results_dialog = CanvasResultsDialog(self)
        self.canvas_results_dialog.showMaximized()
        self.canvas_results_dialog.raise_() 
        self.canvas_results_dialog.activateWindow()
        self.maybe_prompt_dilution()
        
    
                
    #----------------------------------------------------------------------------------------------------------
    #------------------------------------visualization--------------------------------------------
    #----------------------------------------------------------------------------------------------------------
   
    def plot_results(self, mass, signal, particles, lambda_bkgd, threshold, preserve_view_range=None):
        """
        Plot detection results with peaks and thresholds.
        
        Uses collinear point removal for fast rendering of large signals.
        
        Args:
            self: MainWindow instance
            mass (str): Element mass identifier
            signal (ndarray): Raw signal array
            particles (list): List of detected particles
            lambda_bkgd (float): Background level
            threshold (float): Detection threshold
            preserve_view_range (tuple, optional): Tuple of (x_range, y_range) to preserve zoom
            
        Returns:
            None
        """
        self.plot_widget.clear()
        
        display_label = self.get_formatted_label(mass)

        STYLES = {
            'raw_signal': pg.mkPen(color=(30, 144, 255), width=1),
            'background': pg.mkPen(color=(128, 128, 128), style=Qt.DashLine, width=1),
            'threshold': pg.mkPen(color=(220, 20, 60), style=Qt.DashLine, width=1),
            'peaks': {'symbol': 'o', 'size': 18, 'brush': 'r', 'pen': 'match'}, 
        }
        
        time_array = self.time_array
        if isinstance(lambda_bkgd, np.ndarray):
            background_line = lambda_bkgd
            threshold_line = threshold
        else:
            background_line = np.full_like(time_array, lambda_bkgd)
            threshold_line = np.full_like(time_array, threshold)
        
        plot_data = [
            (time_array, signal, STYLES['raw_signal'], f'Mass {display_label}'),
            (time_array, background_line, STYLES['background'], 'Background Level'),
            (time_array, threshold_line, STYLES['threshold'], 'Detection Threshold'),
        ]
        
        _STYLE_MAP = {
            'Solid': Qt.SolidLine, 'Dash': Qt.DashLine, 'Dot': Qt.DotLine,
            'Dash-Dot': Qt.DashDotLine, 'Dash-Dot-Dot': Qt.DashDotDotLine,
        }
        _SYM_MAP = {
            'Circle': 'o', 'Square': 's', 'Triangle Up': 't',
            'Triangle Down': 't1', 'Diamond': 'd', 'Plus': '+',
            'Cross': 'x', 'Star': 'star', 'Pentagon': 'p', 'Hexagon': 'h',
        }
        _saved_traces  = getattr(self.plot_widget, '_trace_settings',   {})
        _saved_scatter = getattr(self.plot_widget, '_scatter_settings', {})

        for x, y, pen, name in plot_data:
            keep = np.diff(y, n=2, append=np.inf, prepend=np.inf) != 0
            pen.setCosmetic(True)
            curve = pg.PlotCurveItem(
                x=x[keep],
                y=y[keep],
                pen=pen,
                name=name,
                skipFiniteCheck=True,
            )
            if name in _saved_traces:
                s = _saved_traces[name]
                _p = pg.mkPen(
                    QColor(s['color']),
                    width=s.get('width', 1),
                    style=_STYLE_MAP.get(s.get('style', 'Solid'), Qt.SolidLine),
                )
                _p.setCosmetic(True)
                curve.setPen(_p)
            self.plot_widget.addItem(curve)

        legend = self.plot_widget.addLegend(offset=(10, 10))
        legend.setParentItem(self.plot_widget.graphicsItem())
        self.plot_widget.legend = legend
        if hasattr(self.plot_widget, '_style_legend'):
            self.plot_widget._style_legend(legend)

        if particles:
            integ_times   = []
            integ_heights = []
            peak_times    = []
            peak_heights  = []

            for p in particles:
                if p is None:
                    continue
                left_idx  = p['left_idx']
                right_idx = p['right_idx']
                end   = min(right_idx + 1, len(signal), len(time_array))
                start = min(left_idx, end)
                if start >= end:
                    continue

                p_method = p.get('integration_method', 'Background')
                if np.isscalar(lambda_bkgd):
                    bkgd_l   = lambda_bkgd
                    thresh_l = threshold
                else:
                    bkgd_l   = lambda_bkgd[start:end]
                    thresh_l = (threshold[start:end]
                                if not np.isscalar(threshold) else threshold)
                if p_method == 'Threshold':
                    integ_level = thresh_l
                elif p_method == 'Midpoint':
                    integ_level = (np.asarray(bkgd_l) + np.asarray(thresh_l)) / 2.0
                else:
                    integ_level = bkgd_l

                s_region = signal[start:end]
                above    = s_region > integ_level
                valid    = np.arange(start, end)[above]
                integ_times.extend(time_array[valid].tolist())
                integ_heights.extend(signal[valid].tolist())

                peak_local  = int(np.argmax(s_region))
                peak_global = start + peak_local
                peak_times.append(float(time_array[peak_global]))
                peak_heights.append(float(signal[peak_global]))

            if integ_times:
                scatter_integ = pg.ScatterPlotItem(
                    x=np.array(integ_times),
                    y=np.array(integ_heights),
                    symbol='o',
                    size=5,
                    brush=pg.mkBrush(255, 165, 0, 200),  
                    pen=pg.mkPen(None),
                    name='Integrated Particles',
                )
                scatter_integ._role               = 'particle_integration'
                scatter_integ._legend_representative = True
                if 'Integrated Particles' in _saved_scatter:
                    ss = _saved_scatter['Integrated Particles']
                    scatter_integ.setSymbol(_SYM_MAP.get(ss.get('symbol', 'Circle'), 'o'))
                    scatter_integ.setSize(ss.get('size', 5))
                    scatter_integ.setBrush(pg.mkBrush(QColor(ss['color'])))
                self.plot_widget.addItem(scatter_integ)

            if peak_times:
                scatter_peak = pg.ScatterPlotItem(
                    x=np.array(peak_times),
                    y=np.array(peak_heights),
                    symbol='o',
                    size=9,
                    brush=pg.mkBrush(46, 204, 113, 240), 
                    pen=pg.mkPen(None),
                    name='Peak Maximum',
                )
                scatter_peak._role               = 'peak_maximum'
                scatter_peak._legend_representative = True
                if 'Peak Maximum' in _saved_scatter:
                    ss = _saved_scatter['Peak Maximum']
                    scatter_peak.setSymbol(_SYM_MAP.get(ss.get('symbol', 'Circle'), 'o'))
                    scatter_peak.setSize(ss.get('size', 9))
                    scatter_peak.setBrush(pg.mkBrush(QColor(ss['color'])))
                self.plot_widget.addItem(scatter_peak)

        # --- Saturation filter highlight ------------------------------
        if (getattr(self, 'saturation_filter_enabled', False)
                and getattr(self, 'saturation_highlight', True)):
            f_key = None
            if (getattr(self, 'current_element', None) is not None
                    and getattr(self, 'current_isotope', None) is not None):
                f_key = (self.current_element, self.current_isotope)
            filtered = []
            if f_key is not None:
                filtered = (self.saturation_filtered_peaks
                            .get(self.current_sample, {})
                            .get(f_key, []))
            if filtered:
                fx, fy = [], []
                for p in filtered:
                    if p is None:
                        continue
                    left = int(p.get('left_idx', 0))
                    right = int(p.get('right_idx', left))
                    end = min(right + 1, len(signal), len(time_array))
                    start = min(max(left, 0), end)
                    if start >= end:
                        continue
                    peak_global = start + int(np.argmax(signal[start:end]))
                    fx.append(float(time_array[peak_global]))
                    fy.append(float(signal[peak_global]))
                if fx:
                    scatter_filt = pg.ScatterPlotItem(
                        x=np.array(fx),
                        y=np.array(fy),
                        symbol='o',
                        size=12,
                        brush=pg.mkBrush(220, 20, 60, 255),
                        pen=pg.mkPen('w', width=1),
                        name='Non-linear (filtered)',
                    )
                    scatter_filt.setZValue(10)
                    scatter_filt._role = 'saturation_filtered'
                    scatter_filt._legend_representative = True
                    self.plot_widget.addItem(scatter_filt)
        
        for sample, label in legend.items:
            label.setText(label.text, size='20pt')
        self.plot_widget.setLabel('left', 'Counts')
        self.plot_widget.setLabel('bottom', 'Time (s)')
        if hasattr(self.plot_widget, 'apply_theme'):
            self.plot_widget.apply_theme()
        self.plot_widget.setMouseEnabled(x=True, y=True)
        
        if preserve_view_range and preserve_view_range[0] and preserve_view_range[1]:
            try:
                x_range, y_range = preserve_view_range
                self.plot_widget.setXRange(x_range[0], x_range[1], padding=0)
                self.plot_widget.setYRange(y_range[1], y_range[0], padding=0)
            except Exception as e:
                self.logger.debug(f"Error restoring view range: {e}")
                self.plot_widget.enableAutoRange()
        else:
            self.plot_widget.enableAutoRange()

        try:
            self._rebuild_plot_exclusion_regions()
        except Exception as e:
            self.logger.debug(f"Could not restore exclusion regions after plot_results: {e}")

        if getattr(self, '_current_plot_mode', 'time') == 'mz':
            try:
                self._update_mz_plot()
            except Exception as e:
                self.logger.debug(f"Could not refresh m/z view: {e}")

    def show_mass_spectrum_popup(self):
        """
        Open a floating window showing the mean signal intensity for every
        selected isotope in the current sample as a bar chart (mass spectrum).

        Each bar represents one isotope; bar height = mean signal over the
        entire acquisition.  Bars are coloured per-element using the same
        palette as the main time-scan plot.  Clicking a bar (or its label)
        jumps the main plot to that isotope's time scan.

        Args:
            None  (reads self.selected_isotopes / self.data / self.current_sample)

        Returns:
            None
        """
        self.user_action_logger.log_dialog_open('Mass Spectrum', 'Mass Spectrum Popup')
        if not self.current_sample or not self.data or not self.selected_isotopes:
            QMessageBox.information(
                self,
                "No Data",
                "Please load data and select elements before viewing the mass spectrum."
            )
            return

        masses, mean_cts, std_cts, labels, element_keys = [], [], [], [], []

        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                closest = self.find_closest_isotope(isotope)
                if closest is None or closest not in self.data:
                    continue
                sig = np.asarray(self.data[closest], dtype=float)
                ek  = f"{element}-{isotope:.4f}"
                masses.append(float(isotope))
                mean_cts.append(float(np.mean(sig)))
                std_cts.append(float(np.std(sig)))
                labels.append(self.get_formatted_label(ek))
                element_keys.append(ek)

        if not masses:
            QMessageBox.information(
                self,
                "No Signal Data",
                "No signal data found for the selected elements."
            )
            return

        order      = np.argsort(masses)
        mean_cts   = np.array(mean_cts)[order]
        std_cts    = np.array(std_cts)[order]
        labels     = [labels[i]       for i in order]
        element_keys = [element_keys[i] for i in order]
        x          = np.arange(len(labels), dtype=float)

        from widget.colors import element_colors as _ec
        bar_colors = [
            _ec[i % len(_ec)][0] for i in range(len(labels))
        ]

        p = theme.palette
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Mass Spectrum — {self.current_sample}")
        dialog.setMinimumSize(700, 460)
        dialog.setStyleSheet(dialog_qss(p))

        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setContentsMargins(12, 12, 12, 12)
        dlg_layout.setSpacing(8)

        title_label = QLabel(
            f"Mean Signal Intensity per isotope   ·   sample: <b>{self.current_sample}</b>"
        )
        title_label.setStyleSheet(
            f"font-size:13px; color:{p.text_primary}; padding:2px 0;"
        )
        dlg_layout.addWidget(title_label)

        pg_widget = pg.PlotWidget()
        pg_widget.setBackground(p.plot_bg)
        pg_widget.setMinimumHeight(340)
        dlg_layout.addWidget(pg_widget)

        for i, (xi, height, color) in enumerate(zip(x, mean_cts, bar_colors)):
            bar = pg.BarGraphItem(
                x=[xi], height=[height], width=0.65,
                brush=pg.mkBrush(color),
                pen=pg.mkPen(p.plot_fg, width=0.6)
            )
            pg_widget.addItem(bar)

            err_pen = pg.mkPen(p.plot_fg, width=1.2)
            cap_w   = 0.12
            top = height + std_cts[i]
            pg_widget.plot([xi - cap_w, xi + cap_w], [top, top], pen=err_pen)
            pg_widget.plot([xi, xi], [height, top],  pen=err_pen)

        ax = pg_widget.getAxis('bottom')
        ax.setTicks([list(zip(x, labels))])
        ax.setStyle(tickFont=pg.QtGui.QFont("Arial", 9))
        pg_widget.setLabel('left',   'Mean Signal (counts)', color=p.plot_fg)
        pg_widget.setLabel('bottom', 'Isotope',                  color=p.plot_fg)
        pg_widget.getAxis('left').setTextPen(p.plot_fg)
        pg_widget.getAxis('bottom').setTextPen(p.plot_fg)
        pg_widget.enableAutoRange()

        hint = QLabel(
            "💡  Click an isotope label in the main parameters table to jump to its time scan."
        )
        hint.setStyleSheet(
            f"font-size:11px; color:{p.text_secondary}; padding:2px 0;"
        )
        dlg_layout.addWidget(hint)

        stats = QTableWidget(len(labels), 3)
        stats.setHorizontalHeaderLabels(["Isotope", "Mean (cts)", "Std (cts)"])
        stats.horizontalHeader().setStretchLastSection(True)
        stats.verticalHeader().setVisible(False)
        stats.setMaximumHeight(160)
        stats.setEditTriggers(QTableWidget.NoEditTriggers)
        stats.setSelectionBehavior(QTableWidget.SelectRows)
        stats.setStyleSheet(results_table_qss(p))

        for row_i, (lbl, mn, sd) in enumerate(zip(labels, mean_cts, std_cts)):
            stats.setItem(row_i, 0, QTableWidgetItem(lbl))
            stats.setItem(row_i, 1, QTableWidgetItem(f"{mn:.2f}"))
            stats.setItem(row_i, 2, QTableWidgetItem(f"{sd:.2f}"))

        dlg_layout.addWidget(stats)

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(dialog.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        dlg_layout.addLayout(btn_row)

        dialog.exec()


    # ------------------------------------------------------------------
    # Inline m/z view helpers
    # ------------------------------------------------------------------

    def switch_plot_view(self, mode: str):
        """
        Switch the main plot area between the time-domain trace ('time')
        and the inline isotope bar chart ('mz').

        Args:
            mode (str): 'time' or 'mz'

        Returns:
            None
        """
        self.user_action_logger.log_action(
            'CLICK', f'Switched plot view to {mode!r}',
            {'mode': mode, 'sample': self.current_sample})
        self._current_plot_mode = mode
        self._view_btn_time.setChecked(mode == 'time')
        self._view_btn_mz.setChecked(mode == 'mz')

        if mode == 'mz':
            self._plot_stack.setCurrentIndex(1)
            self._update_mz_plot()
        else:
            self._plot_stack.setCurrentIndex(0)

    def _update_mz_plot(self):
        """"
        Double-click editing is handled entirely by MzBarPlotWidget:
          • Double-click title       → TitleEditorDialog
          • Double-click left axis   → AxisLabelEditorDialog('left')
          • Double-click bottom axis → AxisLabelEditorDialog('bottom')
          • Double-click a bar       → BarEditorDialog (fill color)
          • Double-click empty area  → BackgroundEditorDialog
          • Right-click              → 'Plot Settings…'

        Args:
            None

        Returns:
            None
        """
        pw = self._mz_pg_widget
        pw.clear()

        p = theme.palette
        pw.setBackground(p.plot_bg)

        if not self.current_sample or not self.data or not self.selected_isotopes:
            placeholder = pg.TextItem(
                "No data — load a sample and select elements first",
                color=p.text_secondary,
                anchor=(0.5, 0.5),
            )
            pw.addItem(placeholder)
            placeholder.setPos(0, 0)
            pw.setXRange(-1, 1, padding=0.5)
            pw.setYRange(-1, 1, padding=0.5)
            pw.set_bar_meta([])
            return

        masses, mean_cts, std_cts, labels = [], [], [], []

        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                closest = self.find_closest_isotope(isotope)
                if closest is None or closest not in self.data:
                    continue
                sig = np.asarray(self.data[closest], dtype=float)
                ek  = f"{element}-{isotope:.4f}"
                masses.append(float(isotope))
                mean_cts.append(float(np.mean(sig)))
                std_cts.append(float(np.std(sig)))
                labels.append(self.get_formatted_label(ek))

        if not masses:
            pw.set_bar_meta([])
            return

        order    = np.argsort(masses)
        mean_cts = np.array(mean_cts)[order]
        std_cts  = np.array(std_cts)[order]
        labels   = [labels[i] for i in order]
        x        = np.arange(len(labels), dtype=float)

        from widget.colors import element_colors as _ec
        default_colors = [_ec[i % len(_ec)][0] for i in range(len(labels))]

        saved_colors = {m['label']: m['color'] for m in pw._bar_meta}

        # ── Draw bars + error caps ───────────────────────────────────────
        err_pen = pg.mkPen(p.plot_fg, width=1.2)
        cap_w   = 0.12
        new_meta = []

        for i, (xi, height, std) in enumerate(zip(x, mean_cts, std_cts)):
            label = labels[i]
            color = saved_colors.get(label, default_colors[i])

            bar = pg.BarGraphItem(
                x=[xi], height=[height], width=0.65,
                brush=pg.mkBrush(color),
                pen=pg.mkPen(p.plot_fg, width=0.6),
            )
            pw.addItem(bar)

            top = height + std
            pw.plot([xi - cap_w, xi + cap_w], [top, top], pen=err_pen)
            pw.plot([xi, xi],                 [height, top], pen=err_pen)

            new_meta.append({
                'x':        float(xi),
                'height':   float(height),
                'label':    label,
                'color':    color,
                'bar_item': bar,
            })

        pw.set_bar_meta(new_meta)

        # ── Axes ─────────────────────────────────────────────────────────
        tick_font = pg.QtGui.QFont("Times New Roman", 11)
        tick_font.setBold(True)

        ax_bottom = pw.getAxis('bottom')
        ax_bottom.setTicks([list(zip(x, labels))])
        ax_bottom.setStyle(tickFont=tick_font, tickTextOffset=8, tickLength=8)
        ax_bottom.setTextPen(p.plot_fg)
        ax_bottom.setPen(p.plot_fg)

        ax_left = pw.getAxis('left')
        ax_left.setStyle(tickFont=tick_font, tickTextOffset=8, tickLength=8)
        ax_left.setTextPen(p.plot_fg)
        ax_left.setPen(p.plot_fg)
        ax_left.enableAutoSIPrefix(False)

        pw.setLabel('left',   'Mean Signal', units='counts',
                    color=p.plot_fg, font='bold 16pt Times New Roman')
        pw.setLabel('bottom', 'Isotope',
                    color=p.plot_fg, font='bold 16pt Times New Roman')
        pw.enableAutoRange()

    def highlight_selected_particle(self):
        """
        Highlight selected particle from single element results table.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        selected_rows = self.results_table.selectedItems()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        
        element_item = self.results_table.item(row, 0)
        start_item = self.results_table.item(row, 1)
        end_item = self.results_table.item(row, 2)
        
        display_label = element_item.text()
        start_time = float(start_item.text())
        end_time = float(end_item.text())
        
        for item in self.plot_widget.items():
            if isinstance(item, pg.PlotDataItem) and item.name() in ['Highlighted Peak']:
                self.plot_widget.removeItem(item)
                
        if hasattr(self, 'current_element') and hasattr(self, 'current_isotope'):
            if (self.current_element, self.current_isotope) in self.detected_peaks:
                self.update_element_summary(
                    self.current_element,
                    self.current_isotope,
                    self.detected_peaks[(self.current_element, self.current_isotope)]
                )

        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                element_key = f"{element}-{isotope:.4f}"
                if self.get_formatted_label(element_key) == display_label:
                    closest_mass = self.find_closest_isotope(isotope)
                    if closest_mass is not None and closest_mass in self.data:
                        signal = self.data[closest_mass]
                        start_index = np.argmin(np.abs(self.time_array - start_time))
                        end_index = np.argmin(np.abs(self.time_array - end_time))

                        self.plot_widget.plot(
                            self.time_array[start_index:end_index+1], 
                            signal[start_index:end_index+1], 
                            pen=pg.mkPen('r', width=1),
                            name='Highlighted Peak'
                        )

                        particle_duration = end_time - start_time
                        padding = 0.5 * particle_duration
                        self.plot_widget.setXRange(start_time - padding, end_time + padding)

                        y_min = np.min(signal[start_index:end_index+1])
                        y_max = np.max(signal[start_index:end_index+1])
                        y_range = y_max - y_min
                        self.plot_widget.setYRange(y_min - 0.1 * y_range, y_max + 0.1 * y_range)
                        return
                    
    def highlight_multi_element_particle(self):
        """
        Highlight and display selected multi-element particle.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        selected_rows = self.multi_element_table.selectedItems()
        if not selected_rows:
            return

        self.plot_widget.clear()

        row = selected_rows[0].row()
        start_time = float(self.multi_element_table.item(row, 1).text())
        end_time = float(self.multi_element_table.item(row, 2).text())
        particle_number = self.multi_element_table.item(row, 0).text()

        particle_duration = end_time - start_time
        padding = max(0.3 * particle_duration, 0.05)  
        view_start = start_time - padding
        view_end = end_time + padding
        
        region = pg.LinearRegionItem(
            [start_time, end_time], 
            movable=False, 
            brush=pg.mkBrush(100, 150, 200, 30), 
            pen=pg.mkPen(100, 150, 200, 80, width=1, style=Qt.DashLine)
        )
        self.plot_widget.addItem(region)
        
        start_line = pg.InfiniteLine(
            pos=start_time, 
            angle=90, 
            pen=pg.mkPen(70, 70, 70, 150, width=1.5, style=Qt.DashLine)
        )
        end_line = pg.InfiniteLine(
            pos=end_time, 
            angle=90, 
            pen=pg.mkPen(70, 70, 70, 150, width=1.5, style=Qt.DashLine)
        )
        self.plot_widget.addItem(start_line)
        self.plot_widget.addItem(end_line)

        max_signal = float('-inf')
        min_signal = float('inf')

        start_index = max(0, np.argmin(np.abs(self.time_array - view_start)))
        end_index = min(len(self.time_array) - 1, np.argmin(np.abs(self.time_array - view_end)))
        
        legend = self.plot_widget.addLegend(offset=(15, 120))
        self.plot_widget.legend = legend
        if hasattr(self.plot_widget, '_style_legend'):
            self.plot_widget._style_legend(legend)
        
        element_data = {}
        color_index = 0
        hover_tooltips = []

        for col in range(3, self.multi_element_table.columnCount()):
            header_item = self.multi_element_table.horizontalHeaderItem(col)
            if not header_item:
                continue
                
            display_label = header_item.text()
            cell_item = self.multi_element_table.item(row, col)
            
            if not cell_item or not cell_item.text() or float(cell_item.text()) <= 0:
                continue  
                
            counts = float(cell_item.text())

            found = False
            for element, isotopes in self.selected_isotopes.items():
                if found:
                    break
                for isotope in isotopes:
                    element_key = f"{element}-{isotope:.4f}"
                    if self.get_formatted_label(element_key) == display_label:
                        color_info = element_colors.get(color_index % len(element_colors), 
                                                    ('#2E86AB', '#87CEEB', 'Steel Blue'))
                        primary_color, light_color, color_name = color_info
                        color_index += 1
                        
                        closest_mass = self.find_closest_isotope(isotope)
                        
                        if closest_mass in self.data:
                            signal = self.data[closest_mass]
                            
                            view_section = signal[start_index:end_index+1]
                            time_section = self.time_array[start_index:end_index+1]
                            
                            section_max = np.max(view_section)
                            section_min = np.min(view_section)
                            max_signal = max(max_signal, section_max)
                            min_signal = min(min_signal, section_min)
                            
                            background_val = 0
                            threshold_val = 0
                            try:
                                if (self.current_sample in self.element_thresholds and 
                                    element_key in self.element_thresholds[self.current_sample]):
                                    thresholds = self.element_thresholds[self.current_sample][element_key]
                                    background_val = thresholds.get('background', 0)
                                    threshold_val = thresholds.get('threshold', 0)
                            except:
                                pass
                            
                            element_data[display_label] = {
                                'signal': view_section,
                                'color': primary_color,
                                'light_color': light_color,
                                'max': section_max,
                                'counts': counts,
                                'element': element,
                                'isotope': isotope,
                                'background': background_val,
                                'threshold': threshold_val
                            }

                            plot_curve = self.plot_widget.plot(
                                time_section,
                                view_section,
                                pen=pg.mkPen(primary_color, width=1),
                                name=f"{display_label} ({counts:.0f} counts)",
                                antialias=True
                            )
                
                            if (element, isotope) in self.detected_peaks:
                                peak_data = {'x': [], 'y': [], 'info': []}
                                integ_data = {'x': [], 'y': []}
                                
                                for particle in self.detected_peaks[(element, isotope)]:
                                    if particle is None:
                                        continue
                                        
                                    particle_start = self.time_array[particle['left_idx']]
                                    particle_end = self.time_array[particle['right_idx']]

                                    if (particle_start <= end_time and particle_end >= start_time):
                                        peak_idx = particle['left_idx'] + np.argmax(signal[particle['left_idx']:particle['right_idx']+1])
                                        peak_x = self.time_array[peak_idx]
                                        peak_y = signal[peak_idx]
                                        
                                        peak_data['x'].append(peak_x)
                                        peak_data['y'].append(peak_y)
                                        
                                        # ── Collect integrated points for this particle ──
                                        p_left   = particle['left_idx']
                                        p_right  = particle['right_idx']
                                        p_method = particle.get('integration_method', 'Background')
                                        end_i    = min(p_right + 1, len(signal), len(self.time_array))
                                        start_i  = min(p_left, end_i)
                                        if start_i < end_i:
                                            if p_method == 'Threshold':
                                                integ_level = threshold_val
                                            elif p_method == 'Midpoint':
                                                integ_level = (background_val + threshold_val) / 2.0
                                            else:
                                                integ_level = background_val
                                            s_region = signal[start_i:end_i]
                                            above    = s_region > integ_level
                                            valid    = np.arange(start_i, end_i)[above]
                                            integ_data['x'].extend(self.time_array[valid].tolist())
                                            integ_data['y'].extend(signal[valid].tolist())
                                        
                                        snr = particle.get('SNR', peak_y / particle.get('threshold', 1))
                                        hover_info = (
                                            f"Element: {display_label}\n"
                                            f"Peak Height: {peak_y:.0f} counts\n"
                                            f"SNR: {snr:.2f}\n"
                                            f"Background: {background_val:.1f} counts\n"
                                            f"Threshold: {threshold_val:.1f} counts"
                                        )
                                        peak_data['info'].append(hover_info)
                                
                                # ── Integrated points (element colour, small, under peak markers) ──
                                if integ_data['x']:
                                    _qc = QColor(light_color)
                                    scatter_integ = pg.ScatterPlotItem(
                                        x=np.array(integ_data['x']),
                                        y=np.array(integ_data['y']),
                                        symbol='o',
                                        size=5,
                                        brush=pg.mkBrush(_qc.red(), _qc.green(), _qc.blue(), 180),
                                        pen=pg.mkPen(None),
                                    )
                                    self.plot_widget.addItem(scatter_integ)

                                if peak_data['x']:
                                    class HoverScatter(pg.ScatterPlotItem):
                                        def __init__(self, parent_widget, hover_texts, *args, **kwargs):
                                            super().__init__(*args, **kwargs)
                                            self.parent_widget = parent_widget
                                            self.hover_texts = hover_texts
                                            self.hover_label = None
                                            
                                        def hoverEvent(self, ev):
                                            if ev.isExit():
                                                if self.hover_label:
                                                    self.parent_widget.removeItem(self.hover_label)
                                                    self.hover_label = None
                                                return
                                                
                                            pos = ev.pos()
                                            pts = self.pointsAt(pos)
                                            
                                            if len(pts) > 0:
                                                point_index = 0
                                                for i, point in enumerate(self.data):
                                                    if point in pts:
                                                        point_index = i
                                                        break
                                                
                                                if point_index < len(self.hover_texts):
                                                    if self.hover_label:
                                                        self.parent_widget.removeItem(self.hover_label)
                                                    
                                                    self.hover_label = pg.TextItem(
                                                        html=f"""
                                                        <div style='
                                                            background: rgba(255, 255, 255, 240);
                                                            padding: 8px 12px;
                                                            border: 2px solid {primary_color};
                                                            border-radius: 6px;
                                                            font-family: "Segoe UI", Arial, sans-serif;
                                                            font-size: 10px;
                                                            color: #333;
                                                            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
                                                        '>
                                                            {self.hover_texts[point_index].replace(chr(10), '<br>')}
                                                        </div>
                                                        """,
                                                        anchor=(0, 1)
                                                    )
                                                    
                                                    point_pos = pts[0].pos()
                                                    self.hover_label.setPos(point_pos.x(), point_pos.y() + 50)
                                                    self.parent_widget.addItem(self.hover_label)
                                    
                                    scatter = HoverScatter(
                                        self.plot_widget,
                                        peak_data['info'],
                                        x=peak_data['x'],
                                        y=peak_data['y'],
                                        symbol='o',
                                        size=12,
                                        brush=pg.mkBrush(primary_color),
                                        pen=pg.mkPen(255, 255, 255, 200, width=1),
                                        hoverable=True,
                                        hoverPen=pg.mkPen(255, 255, 255, 255, width=3),
                                        hoverBrush=pg.mkBrush(primary_color)
                                    )
                                    self.plot_widget.addItem(scatter)
                        
                            try:
                                if ((element, isotope) in self.detected_peaks and 
                                    self.current_sample in self.element_thresholds and 
                                    element_key in self.element_thresholds[self.current_sample]):
                                    
                                    thresholds = self.element_thresholds[self.current_sample][element_key]
                                    threshold = thresholds.get('threshold', 0)
                                    
                                    if threshold > 0:
                                        self.plot_widget.plot(
                                            [view_start, view_end],
                                            [threshold, threshold],
                                            pen=pg.mkPen(primary_color, width=1, style=Qt.DotLine),
                                            alpha=0.6
                                        )
                            except Exception as e:
                                pass
                                
                        found = True
                        break

        self.plot_widget.setXRange(view_start, view_end, padding=0)

        if max_signal > min_signal:
            y_range = max_signal - min_signal
            y_padding = 0.1 * y_range
            y_min = max(0, min_signal - y_padding)
            y_max = max_signal + y_padding
            self.plot_widget.setYRange(y_min, y_max, padding=0)
        else:
            self.plot_widget.enableAutoRange()
        
        if element_data:
            info_lines = [f"<b>Particle #{particle_number} Composition</b>"]
            info_lines.append(f"<b>Duration:</b> {particle_duration*1000:.2f} ms")
            info_lines.append("")
            
            sorted_elements = sorted(element_data.items(), key=lambda x: x[1]['counts'], reverse=True)
            
            for label, data in sorted_elements:
                info_lines.append(
                    f"<span style='color: {data['color']}; font-weight: bold;'>●</span> "
                    f"<b>{label}:</b> {data['counts']:.0f} counts"
                )
            
            info_text = "<br>".join(info_lines)
            
            info_label = pg.TextItem(
                html=f"""
                <div style='
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 rgba(255, 255, 255, 240), 
                        stop:1 rgba(248, 248, 248, 240));
                    padding: 12px 15px;
                    border: 1px solid rgba(200, 200, 200, 180);
                    border-radius: 8px;
                    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
                    font-family: "Segoe UI", Arial, sans-serif;
                    font-size: 11px;
                    line-height: 1.4;
                '>
                    {info_text}
                </div>
                """,
                anchor=(0, 0)
            )
            
            info_x = view_start + 0.02 * (view_end - view_start)
            info_y = y_min + 0.6 * (y_max - y_min) if 'y_max' in locals() and 'y_min' in locals() else min_signal + 0.6 * (max_signal - min_signal)
            info_label.setPos(info_x, info_y)
            self.plot_widget.addItem(info_label)

        self.plot_widget.showGrid(x=False, y=False)
        self.plot_widget.setLabel('left', 'Counts')
        self.plot_widget.setLabel('bottom', 'Time (s)')
        if hasattr(self.plot_widget, 'apply_theme'):
            self.plot_widget.apply_theme()

        self.plot_widget.setMouseEnabled(x=True, y=True)
        self.plot_widget.enableAutoRange(enable=False)
        
        try:
            highlight_region = pg.LinearRegionItem(
                [start_time, end_time], 
                movable=False, 
                brush=pg.mkBrush(255, 215, 0, 80)
            )
            self.plot_widget.addItem(highlight_region)
            
            QTimer.singleShot(1500, lambda: self.plot_widget.removeItem(highlight_region))
        except:
            pass
                    
    def show_signal_selector(self):
        """
        Display signal selector dialog for multi-signal view.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.user_action_logger.log_dialog_open('Signal Selector', 'Multi-Signal View')
        if not self.selected_isotopes:
            QMessageBox.warning(self, "No Elements", "Please select elements first.")
            return
            
        if not self.current_sample or not self.data:
            QMessageBox.warning(self, "No Data", "Please load data first.")
            return
        
        dialog = SignalSelectorDialog(self, self)
        dialog.exec()
    
    def toggle_all_signals(self):
        """
        Toggle between single and multi-signal view.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.showing_all_signals = self.show_all_signals_button.isChecked()
        
        if self.showing_all_signals:
            self.show_signal_selector()
            self.show_all_signals_button.setChecked(False)
            self.showing_all_signals = False
        else:
            current_row = self.parameters_table.currentRow()
            if current_row >= 0:
                self.parameters_table_clicked(current_row, 0)
                    
    #----------------------------------------------------------------------------------------------------------
    #------------------------------------calibration--------------------------------------------
    #----------------------------------------------------------------------------------------------------------
   
    def open_transport_rate_calibration(self):
        """
        Open transport rate calibration window.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.user_action_logger.log_dialog_open('Transport Rate Calibration', 'Calibration Window')
    
        all_methods = ["Liquid weight", "Number based", "Mass based"]
        
        if not self.transport_rate_window:
            self.transport_rate_window = TransportRateCalibrationWindow(
                selected_methods=all_methods, 
                parent=self
            )
            self.transport_rate_window.calibration_completed.connect(self.handle_calibration_result)
        else:
            self.transport_rate_window.selected_methods = all_methods
            self.transport_rate_window.method_combo.clear()
            self.transport_rate_window.method_combo.addItems(all_methods)
        
        self.transport_rate_window.showMaximized() 
        self.transport_rate_window.raise_()
                       
    def show_calibration_info(parent):
        """
        Display enhanced calibration information dialog.
        
        Args:
            parent: Parent window
            
        Returns:
            None
        """
        if not hasattr(parent, 'calibration_results'):
            parent.calibration_results = {}
        if not hasattr(parent, 'selected_transport_rate_methods'):
            parent.selected_transport_rate_methods = []
        if not hasattr(parent, 'isotope_method_preferences'):
            parent.isotope_method_preferences = {}
            
        dialog = CalibrationInfoDialog(
            parent.calibration_results,
            parent.selected_transport_rate_methods,
            parent.isotope_method_preferences,
            parent
        )
        
        if dialog.exec() == QDialog.Accepted:
            parent.selected_transport_rate_methods = dialog.selected_methods
            parent.average_transport_rate = dialog.average_transport_rate
            parent.update_calibration_display()
            parent.update_calculations()

    def handle_calibration_result(self, method, calibration_data):
        """
        Process calibration results from calibration windows.
        
        Args:
            self: MainWindow instance
            method (str): Calibration method name
            calibration_data (dict): Calibration data dictionary
            
        Returns:
            None
        """
        if method == "Ionic Calibration":
            self.calibration_results["Ionic Calibration"] = calibration_data["results"]
            self.isotope_method_preferences = calibration_data["method_preferences"]

            if hasattr(self, 'average_transport_rate') and self.average_transport_rate > 0:
                self.calculate_mass_limits()
                
        elif method in ["Weight Method", "Particle Method", "Mass Method"]:
            self.calibration_results[method] = {'transport_rate': calibration_data}
            
            if method not in self.selected_transport_rate_methods:
                self.selected_transport_rate_methods.append(method)
                
            self.calculate_average_transport_rate() 

            if "Ionic Calibration" in self.calibration_results:
                self.calculate_mass_limits()
                            
                if self.current_sample and self.current_sample in self.element_thresholds:
                    for element_key, data in self.element_thresholds[self.current_sample].items():
                        if 'LOD_counts' in data:
                            if "Ionic Calibration" in self.calibration_results:
                                ionic_data = self.calibration_results["Ionic Calibration"]
                                if element_key in ionic_data:
                                    try:
                                        cal_data = ionic_data[element_key]
                                        method_data = cal_data.get('weighted', cal_data.get('simple', cal_data.get('zero', cal_data.get('manual',{}))))
                                        if method_data and 'slope' in method_data:
                                            slope = method_data['slope']
                                            lod_counts = data['LOD_counts']
                                            density = cal_data.get('density')
                                            
                            
                                            conversion_factor = slope / (self.average_transport_rate * 1000)
                                            
                                            mdl = lod_counts / conversion_factor
                                            mql = mdl * (10/3)
                                            
                                            if density and density > 0:
                                                sdl = self.mass_to_diameter(mdl, density)
                                                sql = self.mass_to_diameter(mql, density)
                                            else:
                                                sdl = float('nan')
                                                sql = float('nan')
                                                
                                            if element_key not in self.element_limits:
                                                self.element_limits[element_key] = {}
                                                
                                            self.element_limits[element_key].update({
                                                'MDL': mdl,
                                                'MQL': mql,
                                                'SDL': sdl,
                                                'SQL': sql,
                                            })
                                    except Exception as e:
                                        self.logger.error(f"Error calculating limits for {element_key}: {str(e)}")

        self.update_calibration_display()   
    
    def open_ionic_calibration(self):
        """
        Open ionic calibration window for sensitivity calibration.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.user_action_logger.log_dialog_open('Ionic Calibration', 'Calibration Window')
    
        if not self.ionic_calibration_window:
            self.ionic_calibration_window = IonicCalibrationWindow(self)
            self.ionic_calibration_window.calibration_completed.connect(self.handle_calibration_result)
            self.ionic_calibration_window.method_preference_changed.connect(self.update_method_preferences)
            self.ionic_calibration_window.isotopes_selection_changed.connect(self.handle_isotopes_selection_from_calibration)
        
        self.ionic_calibration_window.selected_isotopes = self.selected_isotopes.copy()
        
        if hasattr(self, 'all_masses') and self.all_masses is not None:
            self.ionic_calibration_window.all_masses = self.all_masses
            self.ionic_calibration_window.update_periodic_table()
        
        self.ionic_calibration_window.update_table_columns()
        self.ionic_calibration_window.update_plot_isotope_combo()
        
        if hasattr(self, 'calibration_results') and "Ionic Calibration" in self.calibration_results:
            self.ionic_calibration_window.calibration_results = self.calibration_results["Ionic Calibration"]
            self.ionic_calibration_window.update_element_isotope_combo()
            if self.ionic_calibration_window.element_isotope_combo.count() > 0:
                self.ionic_calibration_window.element_isotope_combo.setCurrentIndex(0)
                self.ionic_calibration_window.display_selected_calibration(
                    self.ionic_calibration_window.element_isotope_combo.currentText()
                )
        self.ionic_calibration_window.showMaximized()
        self.ionic_calibration_window.raise_()     
        
    def calculate_average_transport_rate(self):
        """
        Calculate average transport rate from selected methods.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        total_rate = 0
        count = 0
        
        for method in self.selected_transport_rate_methods:
            if method in self.calibration_results and 'transport_rate' in self.calibration_results[method]:
                total_rate += self.calibration_results[method]['transport_rate']
                count += 1
        
        self.average_transport_rate = total_rate / count if count > 0 else 0
        
        if "Ionic Calibration" in self.calibration_results and self.average_transport_rate > 0:
            self.calculate_mass_limits()
            
            if (self.current_sample and 
                self.current_sample in self.sample_particle_data and 
                self.sample_particle_data[self.current_sample]):
                
                element_cache = self._build_element_conversion_cache()
                particles = self.sample_particle_data[self.current_sample]
                self._calculate_mass_data_optimized(particles, element_cache)
                
    def update_calibration_display(self):
        """
        Update calibration information display panel.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        display_text = "Transport Rate Calibration:\n\n"
        
        display_text += "{:<20} {:<20} {:<10}\n".format("Method", "Transport Rate (µL/s)", "Use")
        display_text += "-" * 50 + "\n"
        
        for method in ["Weight Method", "Particle Method", "Mass Method"]:
            if method in self.calibration_results and 'transport_rate' in self.calibration_results[method]:
                rate = self.calibration_results[method]['transport_rate']
                selected = method in self.selected_transport_rate_methods
                display_text += "{:<20} {:<20.4f} {:<10}\n".format(
                    method, rate, "✓" if selected else ""
                )
            else:
                display_text += "{:<20} {:<20} {:<10}\n".format(
                    method, "Not calibrated", ""
                )
        
        display_text += f"\nAverage Transport Rate: {self.average_transport_rate:.4f} µL/s\n\n"
        
        display_text += f"""
        <style>{html_table_css(theme.palette)}</style>
        <br>Ionic Calibration:<br><br>
        <table>
        <tr>
            <th>Isotope</th>
            <th>Slope (cps/conc)</th>
            <th>BEC</th>
            <th>LOD</th>
            <th>LOQ</th>
            <th>R-squared</th>
            <th>LOD (counts)</th>
        </tr>
        """
        
        ionic_data = self.calibration_results.get("Ionic Calibration", {})
        threshold_data = self.element_thresholds.get(self.current_sample, {})
        
        element_data = []
        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                element_key = f"{element}-{isotope:.4f}"
                display_label = self.get_formatted_label(element_key)
                element_data.append((isotope, display_label, element_key))
        element_data.sort()
        
        for _, display_label, element_key in element_data:
            cal_data = ionic_data.get(element_key, {})
            
            preferred_method = self.isotope_method_preferences.get(element_key, 'Force through zero')
            method_map = {
                'Force through zero': 'zero',
                'Simple linear': 'simple',
                'Weighted': 'weighted',
                'Manual': 'manual',
            }
            method_key = method_map.get(preferred_method, 'zero')
            
            method_data = cal_data.get(method_key, cal_data.get('zero', {}))
            
            thresholds = threshold_data.get(element_key, {})
            
            r_squared = method_data.get('r_squared', 0) if method_data else 0
            row_class = ' class="warning"' if r_squared < 0.9 else ''
            
            display_text += f"<tr{row_class}>"
            display_text += f"<td>{display_label}</td>"
            
            if method_data:
                display_text += f"<td>{method_data.get('slope', 'N/A'):.2e}</td>"
                display_text += f"<td>{method_data.get('bec', 'N/A'):.2e}</td>"
                display_text += f"<td>{method_data.get('lod', 'N/A'):.2e}</td>"
                display_text += f"<td>{method_data.get('loq', 'N/A'):.2e}</td>"
                display_text += f"<td>{r_squared:.4f}</td>"
            else:
                display_text += "<td>Not calibrated</td>" * 5
            
            lod_counts = thresholds.get('LOD_counts', 'N/A')
            display_text += f"<td>{lod_counts:.2f}</td>" if isinstance(lod_counts, (int, float)) else "<td>Not calculated</td>"
            
            display_text += "</tr>"
        
        display_text += "</table>"
        
        self.calibration_info_panel.setHtml(display_text)
        
    def update_method_preferences(self, preferences):
        """
        Update calibration method preferences without recalculation.
        
        Args:
            self: MainWindow instance
            preferences (dict): Method preferences dictionary
            
        Returns:
            None
        """
        self.isotope_method_preferences = preferences
        
        self.update_calibration_display()
        
    def calculate_mass_limits(self):
        """
        Calculate mass detection limits for all elements.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        if not hasattr(self, 'average_transport_rate') or self.average_transport_rate <= 0:
            self.element_limits = {}
            return
        
        dwell_time_sec = self.sample_dwell_times.get(self.current_sample, 0) / 1000.0
        
        for element_key, data in self.element_thresholds.get(self.current_sample, {}).items():
            try:
                lod_counts = data.get('LOD_MDL') 
                if not lod_counts:
                    lod_counts = max(0, data.get('threshold', 0) - data.get('background', 0))
                background_counts = data.get('background', 0)
                
                if not lod_counts or lod_counts <= 0:
                    continue

                cal_data = self.calibration_results.get("Ionic Calibration", {}).get(element_key)
                if not cal_data:
                    continue

                preferred_method = self.isotope_method_preferences.get(element_key, 'Force through zero')
                method_map = {
                    'Force through zero': 'zero',
                    'Simple linear': 'simple',
                    'Weighted': 'weighted',
                    'Manual': 'manual'
                }
                method_key = method_map.get(preferred_method, 'zero')
                
                method_data = cal_data.get(method_key)
                if not method_data:
                    method_data = cal_data.get('weighted', cal_data.get('simple', cal_data.get('zero', cal_data.get('manual',{}))))
                
                if not method_data:
                    continue

                slope = method_data.get('slope')
                if not slope or slope <= 0:
                    continue

                conversion_factor = slope / (self.average_transport_rate * 1000)

                if dwell_time_sec > 0:
                    background_cps = background_counts / dwell_time_sec
                    background_sd_cps = np.sqrt(background_counts) / dwell_time_sec
                else:
                    background_cps = background_counts
                    background_sd_cps = np.sqrt(background_counts)

                background_ppt = (background_cps / slope * 1000) if slope > 0 else 0
                background_sd_ppt = (background_sd_cps / slope * 1000) if slope > 0 else 0

                mdl = lod_counts / conversion_factor
                mql = mdl * (10/3)

                density = cal_data.get('density')
                if density and density > 0:
                    sdl = self.mass_to_diameter(mdl, density)
                    sql = self.mass_to_diameter(mql, density)
                else:
                    sdl = float('nan')
                    sql = float('nan')

                if self.current_sample not in self.element_limits:
                    self.element_limits[self.current_sample] = {}
                if element_key not in self.element_limits[self.current_sample]:
                    self.element_limits[self.current_sample][element_key] = {}

                self.element_limits[self.current_sample][element_key].update({
                    'MDL': mdl,
                    'MQL': mql,
                    'SDL': sdl,
                    'SQL': sql,
                    'background_ppt': background_ppt,
                    'background_sd_ppt': background_sd_ppt,
                    'background_cps': background_cps
                })

            except Exception as e:
                self.logger.error(f"Error calculating limits for {element_key}: {str(e)}")
                continue
            
    #----------------------------------------------------------------------------------------------------------
    #------------------------------------mass fraction and calculation--------------------------------------------
    #----------------------------------------------------------------------------------------------------------
   
    def open_mass_fraction_calculator(self):
        """
        Open mass fraction calculator dialog.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.user_action_logger.log_dialog_open('Mass Fraction Calculator', 'Calculator')
        if not self.selected_isotopes:
            QMessageBox.warning(self, "No Elements Selected", 
                            "Please select elements from the periodic table first.")
            return
        
        try:
            from tools.mass_fraction_calculator import MassFractionCalculator
            calculator = MassFractionCalculator(
                self.selected_isotopes, 
                self.periodic_table_widget, 
                self
            )
            calculator.mass_fractions_updated.connect(self.handle_mass_fractions_updated)
            calculator.exec()
        except ImportError:
            QMessageBox.critical(self, "Import Error", 
                            "Mass fraction calculator not available. Please ensure mass_fraction_calculator.py is in the same directory.")
            self.logger.error("Mass fraction calculator module not found. Please ensure it is in the same directory as mainwindow.py.")

    def handle_mass_fractions_updated(self, data):
        """
        Handle mass fraction updates from calculator.
        
        Args:
            self: MainWindow instance
            data (dict): Dictionary containing:
                - 'mass_fractions' (dict): Element mass fractions
                - 'densities' (dict): Element densities
                - 'molecular_weights' (dict): Element molecular weights
                - 'apply_to_all' (bool): Apply globally flag
                - 'selected_samples' (list): List of selected sample names
            
        Returns:
            None
        """
        mass_fractions = data['mass_fractions']
        densities = data['densities']
        molecular_weights = data.get('molecular_weights', {})
        apply_to_all = data['apply_to_all']
        selected_samples = data.get('selected_samples', [])
        
        if apply_to_all:
            self.element_mass_fractions = mass_fractions.copy()
            self.element_densities = densities.copy()
            self.element_molecular_weights = molecular_weights.copy()
            
            if "Ionic Calibration" in self.calibration_results:
                for element, density in densities.items():
                    molecular_weight = molecular_weights.get(element)
                    for element_key in self.calibration_results["Ionic Calibration"]:
                        if element_key.startswith(element + "-"):
                            self.calibration_results["Ionic Calibration"][element_key]['density'] = density
                            if molecular_weight:
                                self.calibration_results["Ionic Calibration"][element_key]['molecular_weight'] = molecular_weight
            
            self.status_label.setText(f"Updated mass fractions and molecular weights for {len(mass_fractions)} elements (applied to all samples)")
        else:
            for sample_name in selected_samples:
                if sample_name not in self.sample_mass_fractions:
                    self.sample_mass_fractions[sample_name] = {}
                if sample_name not in self.sample_densities:
                    self.sample_densities[sample_name] = {}
                if not hasattr(self, 'sample_molecular_weights'):
                    self.sample_molecular_weights = {}
                if sample_name not in self.sample_molecular_weights:
                    self.sample_molecular_weights[sample_name] = {}
                    
                self.sample_mass_fractions[sample_name].update(mass_fractions.copy())
                self.sample_densities[sample_name].update(densities.copy())
                self.sample_molecular_weights[sample_name].update(molecular_weights.copy())
            
            sample_count = len(selected_samples)
            self.status_label.setText(f"Updated mass fractions and molecular weights for {len(mass_fractions)} elements (applied to {sample_count} selected samples)")
        
        if hasattr(self, 'average_transport_rate') and self.average_transport_rate > 0:
            self.calculate_mass_limits()
        
        if (self.current_sample and 
            self.current_sample in self.sample_particle_data and 
            self.sample_particle_data[self.current_sample]):
            
            element_cache = self._build_element_conversion_cache()
            particles = self.sample_particle_data[self.current_sample]
            self._calculate_mass_data_optimized(particles, element_cache)
            
            self.status_label.setText(f"Recalculated particle masses with new mass fractions and molecular weights")
        
        self.unsaved_changes = True
            
    def get_molecular_weight(self, element_key, sample_name=None):
        """
        Get molecular weight for element compound.
        
        Args:
            self: MainWindow instance
            element_key (str): Element identifier (e.g., "Au-197.0000")
            sample_name (str, optional): Sample name for sample-specific lookup
            
        Returns:
            float or None: Molecular weight in g/mol
        """
        element = element_key.split('-')[0]
        
        if (sample_name and 
            hasattr(self, 'sample_molecular_weights') and 
            sample_name in self.sample_molecular_weights):
            molecular_weight = self.sample_molecular_weights[sample_name].get(element)
            if molecular_weight and molecular_weight > 0:
                return molecular_weight
        
        if (hasattr(self, 'element_molecular_weights') and 
            element in self.element_molecular_weights):
            molecular_weight = self.element_molecular_weights[element]
            if molecular_weight and molecular_weight > 0:
                return molecular_weight
        
        if self.periodic_table_widget:
            element_data = self.periodic_table_widget.get_element_by_symbol(element)
            if element_data:
                atomic_mass = float(element_data.get('mass', 0))
                return atomic_mass
        
        return None

    def get_mass_fraction(self, element_key, sample_name=None):
        """
        Get mass fraction for element in compound.
        
        Args:
            self: MainWindow instance
            element_key (str): Element identifier (e.g., "Au-197.0000")
            sample_name (str, optional): Sample name for sample-specific lookup
            
        Returns:
            float: Mass fraction (0.0-1.0), defaults to 1.0 for pure element
        """
        element = element_key.split('-')[0]
        
        if sample_name and sample_name in self.sample_mass_fractions:
            fraction = self.sample_mass_fractions[sample_name].get(element)
            if fraction is not None:
                return fraction
        
        if element in self.element_mass_fractions:
            return self.element_mass_fractions[element]
        
        return 1.0
    
    
    def get_element_density(self, element_key, sample_name=None):
        """
        Get density for element compound.
        
        Args:
            self: MainWindow instance
            element_key (str): Element identifier (e.g., "Au-197.0000")
            sample_name (str, optional): Sample name for sample-specific lookup
            
        Returns:
            float or None: Density in g/cm³
        """
        element = element_key.split('-')[0]
        
        if sample_name and sample_name in self.sample_densities:
            density = self.sample_densities[sample_name].get(element)
            if density:
                return density
        
        if element in self.element_densities:
            return self.element_densities[element]
        
        if self.periodic_table_widget:
            element_data = self.periodic_table_widget.get_element_by_symbol(element)
            if element_data:
                return element_data.get('density', None)
        
        return None
    
    def mass_to_diameter(self, mass_fg, density):
        """
        Convert mass to spherical particle diameter.
        
        Args:
            self: MainWindow instance
            mass_fg (float): Mass in femtograms
            density (float): Density in g/cm³
            
        Returns:
            float: Diameter in nanometers
        """
        if mass_fg <= 0 or density <= 0:
            return float('nan')
        mass_g = mass_fg * 1e-15
        diameter_cm = ((6 * mass_g) / (np.pi * density)) ** (1/3)
        return diameter_cm * 1e7

    def get_sample_dilution(self, sample_name):
        """
        Return the dilution factor stored for a sample.

        Args:
            sample_name (str): Sample identifier.

        Returns:
            float: Dilution factor, defaulting to 1.0 when unset.
        """
        return tools.dilution_utils.get_sample_dilution(self, sample_name)

    def set_sample_dilution(self, sample_name, factor):
        """
        Store the dilution factor for a sample.

        Args:
            sample_name (str): Sample identifier.
            factor (float): Dilution factor to store.

        Returns:
            None
        """
        tools.dilution_utils.set_sample_dilution(self, sample_name, factor)

    def effective_volume_ml(self, sample_name, element_key=None):
        """
        Return the analyzed sample volume in millilitres for a sample.

        Args:
            sample_name (str): Sample identifier.
            element_key (str): Optional element key for element scope exclusions.

        Returns:
            float: Effective analyzed volume in millilitres. Manual
            exclusion regions and the time windows flagged by the
            detector non-linearity filter are both subtracted exactly
            inside tools.dilution_utils.
        """
        return tools.dilution_utils.effective_volume_ml(self, sample_name, element_key)

    def particles_per_ml(self, sample_name, particle_count, element_key=None, apply_dilution=True):
        """
        Return the particle number concentration in particles per millilitre.

        Args:
            sample_name (str): Sample identifier.
            particle_count (int): Number of particles for the quantity of interest.
            element_key (str): Optional element key for element scope exclusions.
            apply_dilution (bool): Multiply by the sample dilution factor when True.

        Returns:
            float: Concentration in particles per millilitre.
        """
        return tools.dilution_utils.particles_per_ml(
            self, sample_name, particle_count, element_key, apply_dilution)

    def has_transport_rate(self):
        """
        Report whether a transport rate calibration is available.

        Returns:
            bool: True when an average transport rate greater than zero exists.
        """
        return tools.dilution_utils.has_transport_rate(self)

    def open_dilution_factor_dialog(self):
        """
        Open the per sample dilution factor editor dialog.

        Returns:
            None
        """
        tools.dilution_utils.open_dilution_factor_dialog(self)

    def maybe_prompt_dilution(self):
        """
        Show the one time dilution correction prompt when appropriate.

        Returns:
            None
        """
        tools.dilution_utils.maybe_prompt_dilution(self)

    def update_calculations(self):
        """
        Update calculations after transport rate changes.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        pass
    
    def _calculate_mass_data_optimized(self, particles, element_cache, progress=None, process_all_samples=False):
        """
        Calculate comprehensive mass, mole, and diameter data for particles.
        
        Args:
            self: MainWindow instance
            particles (list): List of particle dictionaries
            element_cache (dict): Pre-built element conversion cache
            progress (QProgressDialog, optional): Progress dialog for UI updates
            process_all_samples (bool): Whether to process particles from all samples
            
        Returns:
            None
        """
        if process_all_samples:
            all_particles = []
            for sample_name, sample_particles in self.sample_particle_data.items():
                if sample_particles:
                    for particle in sample_particles:
                        particle['_source_sample'] = sample_name
                        all_particles.append(particle)
            particles = all_particles
        
        for i, particle in enumerate(particles):
            if progress and i % 100 == 0:
                progress.setValue(i)
                if progress.wasCanceled():
                    return
                QApplication.processEvents()
            
            sample_name = particle.get('_source_sample', self.current_sample)
            
            if 'element_mass_fg' not in particle:
                particle['element_mass_fg'] = {}
            if 'element_moles_fmol' not in particle:
                particle['element_moles_fmol'] = {}
            if 'particle_mass_fg' not in particle:
                particle['particle_mass_fg'] = {}
            if 'particle_moles_fmol' not in particle:
                particle['particle_moles_fmol'] = {}
            if 'element_diameter_nm' not in particle:
                particle['element_diameter_nm'] = {}
            if 'particle_diameter_nm' not in particle:
                particle['particle_diameter_nm'] = {}
            if 'mass_fractions_used' not in particle:
                particle['mass_fractions_used'] = {}
            if 'densities_used' not in particle:
                particle['densities_used'] = {}
            if 'molar_masses' not in particle:
                particle['molar_masses'] = {}
            
            if 'mass_fg' not in particle:
                particle['mass_fg'] = {}
                
            total_element_mass_fg = 0
            total_element_moles_fmol = 0
            total_particle_mass_fg = 0
            total_particle_moles_fmol = 0
                    
            for element_display, counts in particle['elements'].items():
                if counts <= 0:
                    continue
                    
                if element_display in element_cache:
                    cache_entry = element_cache[element_display]
                    conversion_factor = cache_entry['conversion_factor']
                    element_key = cache_entry['element_key']
                    
                    element = element_key.split('-')[0]          
                    isotope = float(element_key.split('-')[1])  
                    if self.periodic_table_widget:
                        element_data = self.periodic_table_widget.get_element_by_symbol(element)
                        if element_data:
                            atomic_mass = float(element_data.get('mass', isotope))  
        
                    
                    mass_fraction = self.get_mass_fraction(element_key, sample_name)
                    element_density = None
                    compound_density = self.get_element_density(element_key, sample_name)
                    
                    if self.periodic_table_widget:
                        element_data = self.periodic_table_widget.get_element_by_symbol(element)
                        if element_data:
                            element_density = element_data.get('density')
                    
                    particle['mass_fractions_used'][element_display] = mass_fraction
                    particle['densities_used'][element_display] = {
                        'element_density': element_density,
                        'compound_density': compound_density
                    }
                    particle['molar_masses'][element_display] = atomic_mass
                    
                    if conversion_factor and conversion_factor > 0 and atomic_mass > 0:
                        
                        element_mass_fg = counts / conversion_factor
                        element_moles_fmol = element_mass_fg / atomic_mass
                        
                        particle['element_mass_fg'][element_display] = element_mass_fg
                        particle['element_moles_fmol'][element_display] = element_moles_fmol
                        
                        particle_mass_fg = element_mass_fg / mass_fraction
                        
                        compound_molecular_weight = self.get_molecular_weight(element_key, sample_name)
                    
                        
                        if compound_molecular_weight and compound_molecular_weight > 0:
                            particle_moles_fmol = particle_mass_fg / compound_molecular_weight
                        else:
                            particle_moles_fmol = element_moles_fmol
                                    
                        particle['particle_mass_fg'][element_display] = particle_mass_fg
                        particle['particle_moles_fmol'][element_display] = particle_moles_fmol


                        if element_density and element_density > 0:
                            element_diameter_nm = self.mass_to_diameter(element_mass_fg, element_density)
                            if not np.isnan(element_diameter_nm):
                                particle['element_diameter_nm'][element_display] = element_diameter_nm
                            else:
                                particle['element_diameter_nm'][element_display] = 0
                        else:
                            particle['element_diameter_nm'][element_display] = 0
                        
                        if compound_density and compound_density > 0:
                            particle_diameter_nm = self.mass_to_diameter(particle_mass_fg, compound_density)
                            if not np.isnan(particle_diameter_nm):
                                particle['particle_diameter_nm'][element_display] = particle_diameter_nm
                            else:
                                particle['particle_diameter_nm'][element_display] = 0
                        else:
                            particle['particle_diameter_nm'][element_display] = particle['element_diameter_nm'][element_display]
                        
                        particle['mass_fg'][element_display] = particle_mass_fg
                        
                        total_element_mass_fg += element_mass_fg
                        total_element_moles_fmol += element_moles_fmol
                        total_particle_mass_fg += particle_mass_fg
                        total_particle_moles_fmol += particle_moles_fmol
                        
                    else:
                        particle['element_mass_fg'][element_display] = 0
                        particle['element_moles_fmol'][element_display] = 0
                        particle['particle_mass_fg'][element_display] = 0
                        particle['particle_moles_fmol'][element_display] = 0
                        particle['element_diameter_nm'][element_display] = 0
                        particle['particle_diameter_nm'][element_display] = 0
                        particle['mass_fg'][element_display] = 0
            
            particle['totals'] = {
                'total_element_mass_fg': total_element_mass_fg,
                'total_element_moles_fmol': total_element_moles_fmol,
                'total_particle_mass_fg': total_particle_mass_fg,
                'total_particle_moles_fmol': total_particle_moles_fmol
            }
            
            if total_element_mass_fg > 0:
                particle['mass_percentages'] = {}
                particle['mole_percentages'] = {}
                
                for element_display in particle['elements'].keys():
                    if element_display in particle['element_mass_fg']:
                        element_mass = particle['element_mass_fg'][element_display]
                        element_moles = particle['element_moles_fmol'][element_display]
                        
                        mass_percent = (element_mass / total_element_mass_fg * 100) if total_element_mass_fg > 0 else 0
                        mole_percent = (element_moles / total_element_moles_fmol * 100) if total_element_moles_fmol > 0 else 0
                        
                        particle['mass_percentages'][element_display] = mass_percent
                        particle['mole_percentages'][element_display] = mole_percent
        
        if progress:
            progress.setValue(len(particles))
            
    #----------------------------------------------------------------------------------------------------------
    #------------------------------------progress and status--------------------------------------------
    #----------------------------------------------------------------------------------------------------------
     
    def update_progress(self, value):
        """
        Update progress bar value.
        
        Args:
            self: MainWindow instance
            value (int): Progress value (0-100)
            
        Returns:
            None
        """
        self.progress_bar.setValue(value)
                    
    def update_sample_progress(self, thread_progress, sample_name, current_sample, total_samples):
        """
        Update progress bar for sample processing.
        
        Args:
            self: MainWindow instance
            thread_progress (int): Thread progress percentage (0-100)
            sample_name (str): Sample name
            current_sample (int): Current sample number (1-based)
            total_samples (int): Total number of samples
            
        Returns:
            None
        """
        sample_increment = 100 / total_samples
        thread_contribution = (thread_progress / 100) * sample_increment
        base_progress = sample_increment * (current_sample - 1)
        overall_progress = int(base_progress + thread_contribution)
        self.progress_bar.setValue(overall_progress)
        self.status_label.setText(f"Processing sample {current_sample}/{total_samples}: {sample_name} ({thread_progress}%)")
        QApplication.processEvents()  
        
    def update_element_progress(self, thread_progress, sample_name, current_sample, total_samples):
        """
        Update progress bar during element processing.
        
        Args:
            self: MainWindow instance
            thread_progress (int): Thread progress percentage (0-100)
            sample_name (str): Current sample name
            current_sample (int): Current sample number (1-based)
            total_samples (int): Total number of samples
            
        Returns:
            None
        """
        sample_increment = 100 / total_samples
        thread_contribution = (thread_progress / 100) * sample_increment
        base_progress = sample_increment * (current_sample - 1)
        overall_progress = int(base_progress + thread_contribution)
        self.progress_bar.setValue(overall_progress)
        self.status_label.setText(f"Processing elements for sample {current_sample}/{total_samples}: {sample_name} ({thread_progress}%)")
        QApplication.processEvents() 
          
    def log_status(self, message, level='info', context=None):
        """
        Update status bar and log message with context.
        
        Args:
            self: MainWindow instance
            message (str): Status message to display
            level (str): Log level - 'info', 'error', 'warning', or 'debug'
            context (dict): Optional context dictionary
            
        Returns:
            None
        """
        self.status_label.setText(message)
        
        if hasattr(self, 'logger'):
            if context is None:
                context = {}
                if hasattr(self, 'current_sample') and self.current_sample:
                    context['current_sample'] = self.current_sample
                if hasattr(self, 'selected_isotopes') and self.selected_isotopes:
                    context['element_count'] = sum(len(isotopes) for isotopes in self.selected_isotopes.values())
            
            if level == 'error':
                record = logging.LogRecord(
                    name=self.logger.name, level=logging.ERROR, pathname='', lineno=0,
                    msg=message, args=(), exc_info=None
                )
            elif level == 'warning':
                record = logging.LogRecord(
                    name=self.logger.name, level=logging.WARNING, pathname='', lineno=0,
                    msg=message, args=(), exc_info=None
                )
            elif level == 'debug':
                record = logging.LogRecord(
                    name=self.logger.name, level=logging.DEBUG, pathname='', lineno=0,
                    msg=message, args=(), exc_info=None
                )
            else:
                record = logging.LogRecord(
                    name=self.logger.name, level=logging.INFO, pathname='', lineno=0,
                    msg=message, args=(), exc_info=None
                )
            
            record.context = context
            self.logger.handle(record)
            
    #----------------------------------------------------------------------------------------------------------
    #------------------------------------project management--------------------------------------------
    #----------------------------------------------------------------------------------------------------------
    
    @log_user_action('MENU', 'File -> Save Project')
    def save_project(self):
        """
        Save current project to file.
        
        Args:
            self: MainWindow instance
            
        Returns:
            bool: True if save was successful
        """
        self.user_action_logger.log_menu_action('File', 'Save Project')
        result = self.project_manager.save_project()
        
        self.user_action_logger.log_file_operation(
            'Project Save', 
            'project.itp', 
            success=result
        )
        return result

    @log_user_action('MENU', 'File -> Load Project')
    def load_project(self, filepath: str | None=None):
        """
        Load project from file.
        
        Args:
            self: MainWindow instance
            filepath: Filepath of the project. If None, the project manager will
             take charge of it.
            
        Returns:
            bool: True if load was successful
        """
        self.user_action_logger.log_menu_action('File', 'Load Project')
        result = self.project_manager.load_project(filepath=filepath)
        
        self.user_action_logger.log_file_operation(
            'Project Load',
            'project file',
            success=result
        )
        return result
    
    # ------------------------------------------------------------------
    # Detector non-linearity (saturation) filter
    # ------------------------------------------------------------------
    def _update_saturation_button_text(self):
        """
        Refresh the non-linearity filter button caption with the current
        state and FWHM threshold.

        Returns:
            None
        """
        if not hasattr(self, 'saturation_filter_button'):
            return
        state = "ON" if self.saturation_filter_enabled else "OFF"
        self.saturation_filter_button.setText(
            f"Non-linearity Filter: {state} (FWHM > {self.saturation_filter_ms:g} ms)")

    def _particle_fwhm_s(self, particle, time_arr, signal=None):
        """
        Return the FWHM of a particle event in seconds.

        The value computed during detection ('fwhm_s') is preferred. If
        it is absent, the FWHM is recomputed from the signal above a
        local background estimate. When neither is possible the method
        returns 0.0 so the particle is never flagged from an unreliable
        width estimate.

        Args:
            particle (dict): Particle dictionary.
            time_arr (ndarray): Sample time axis in seconds.
            signal (ndarray): Optional raw signal for recomputation.

        Returns:
            float: FWHM in seconds, or 0.0 when it cannot be determined.
        """
        fwhm = particle.get('fwhm_s')
        if fwhm is not None:
            try:
                return float(fwhm)
            except (TypeError, ValueError):
                pass
        try:
            n = len(time_arr)
            left = max(0, min(int(particle.get('left_idx', 0)), n - 1))
            right = max(left, min(int(particle.get('right_idx', left)), n - 1))
            if signal is None or right <= left:
                return 0.0
            region = np.asarray(signal[left:right + 1], dtype=float)
            apex = int(np.argmax(region))
            edge = min(3, len(region))
            bkgd = float(np.median(
                np.concatenate((region[:edge], region[-edge:]))))
            if region[apex] <= bkgd:
                return 0.0
            half = bkgd + 0.5 * (region[apex] - bkgd)
            i = apex
            while i > 0 and region[i - 1] > half:
                i -= 1
            j = apex
            while j < len(region) - 1 and region[j + 1] > half:
                j += 1
            dwell = float(time_arr[1] - time_arr[0]) if n > 1 else 0.0
            return float(time_arr[left + j] - time_arr[left + i]) + dwell
        except Exception:
            return 0.0

    def _particle_apex_time(self, particle, time_arr):
        """
        Return the apex time of a particle event in seconds.

        Args:
            particle (dict): Particle dictionary.
            time_arr (ndarray): Sample time axis in seconds.

        Returns:
            float: Apex time, or 0.0 when it cannot be determined.
        """
        t = particle.get('peak_time')
        if t is not None:
            try:
                return float(t)
            except (TypeError, ValueError):
                pass
        try:
            n = len(time_arr)
            left = max(0, min(int(particle.get('left_idx', 0)), n - 1))
            right = max(left, min(int(particle.get('right_idx', left)), n - 1))
            return float(time_arr[(left + right) // 2])
        except Exception:
            return 0.0

    def _particle_flat_ratio(self, particle, time_arr, signal):
        """
        Return the flat-top index of a peak: the width at the configured
        top level (default 90 percent of max above local background)
        divided by the FWHM.

        A healthy single-particle transient narrows sharply toward the
        apex (Gaussian reference at the 90 percent level: 0.39). A peak
        recorded under non-linear detector response stays wide at the
        top, pushing the ratio toward 1. The top width is measured
        between the outermost crossings within the event, so a mid-peak
        dip cannot hide the plateau.

        Args:
            particle (dict): Particle dictionary.
            time_arr (ndarray): Sample time axis in seconds.
            signal (ndarray): Raw signal of the isotope.

        Returns:
            float: Width ratio, or 0.0 when it cannot be computed.
        """
        try:
            if signal is None:
                return 0.0
            n = len(time_arr)
            left = max(0, min(int(particle.get('left_idx', 0)), n - 1))
            right = max(left, min(int(particle.get('right_idx', left)), n - 1))
            if right <= left:
                return 0.0
            region = np.asarray(signal[left:right + 1], dtype=float)
            apex_val = float(np.max(region))
            edge = min(3, len(region))
            bkgd = float(np.median(
                np.concatenate((region[:edge], region[-edge:]))))
            if apex_val <= bkgd:
                return 0.0
            dwell = float(time_arr[1] - time_arr[0]) if n > 1 else 0.0
            frac = min(0.99, max(0.50, float(
                getattr(self, 'saturation_top_frac', 0.90))))
            lvl = bkgd + frac * (apex_val - bkgd)
            idx = np.where(region >= lvl)[0]
            if len(idx) == 0:
                return 0.0
            w_top = float(time_arr[left + idx[-1]]
                          - time_arr[left + idx[0]]) + dwell
            fwhm = self._particle_fwhm_s(particle, time_arr, signal)
            return w_top / fwhm if fwhm > 0 else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def _merge_time_windows(windows):
        """
        Merge overlapping time intervals into their sorted union.

        Args:
            windows (list): List of (t0, t1) tuples in seconds.

        Returns:
            list: Sorted, non-overlapping (t0, t1) tuples.
        """
        if not windows:
            return []
        windows = sorted(windows)
        merged = [list(windows[0])]
        for t0, t1 in windows[1:]:
            if t0 <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], t1)
            else:
                merged.append([t0, t1])
        return [(a, b) for a, b in merged]

    def apply_saturation_filter(self, samples=None):
        """
        Particle-level filtering of detector non-linearity events,
        re-evaluated from scratch for each sample.

        The evaluation is a full re-assessment: previously filtered
        particles are first merged back (entries whose isotope is no
        longer selected are discarded), then two passes run. Pass 1
        flags a time window for every peak, on any isotope, that is
        large (SNR at or above the minimum), wide (FWHM above the
        threshold) and flat-topped (top-width ratio at or above the
        minimum). Pass 2 moves every particle whose apex falls inside a
        flagged window, on all isotopes, plus every overlapping
        multi-element particle, out of the results. Because each call
        starts fresh, removing an isotope from the selection and
        re-applying drops the windows that isotope was responsible for.

        The union duration of the flagged windows is stored per sample
        in self.saturation_excluded_time_s and is subtracted from the
        analysis time when particle number concentrations are computed.

        Args:
            samples (list): Optional list of samples to evaluate.
                Defaults to every sample with detection results.

        Returns:
            int: Number of particle events excluded after this call.
        """
        max_s = float(self.saturation_filter_ms) / 1000.0
        target = samples if samples is not None else list(self.sample_detected_peaks.keys())
        n_removed = 0

        for sname in target:
            detected = self.sample_detected_peaks.get(sname)
            time_arr = self.time_array_by_sample.get(sname)
            if detected is None or time_arr is None:
                continue
            time_arr = np.asarray(time_arr)
            n = len(time_arr)
            sample_data = self.data_by_sample.get(sname, {})

            def _signal_for(key):
                try:
                    _el, iso = key
                    ik = self.find_closest_isotope(iso)
                    return sample_data.get(ik) if ik is not None else None
                except Exception:
                    return None

            old_store = self.saturation_filtered_peaks.pop(sname, {})
            for key, removed in old_store.items():
                if key in detected and removed:
                    merged = list(detected[key]) + list(removed)
                    merged.sort(key=lambda p: p.get('left_idx', 0) if p else 0)
                    detected[key] = merged
            old_multi = self.saturation_filtered_multi.pop(sname, None)
            if old_multi and sname == self.current_sample:
                merged = list(getattr(self, 'multi_element_particles', [])) + list(old_multi)
                merged.sort(key=lambda mp: mp.get('start_time', 0.0))
                self.multi_element_particles = merged
            self.saturation_windows.pop(sname, None)
            self.saturation_excluded_time_s.pop(sname, None)

            windows = []
            for key, particles in detected.items():
                sig = None
                sig_loaded = False
                for p in particles or []:
                    if p is None:
                        continue
                    snr = p.get('SNR')
                    if snr is not None and float(snr) < self.saturation_min_snr:
                        continue
                    if not sig_loaded:
                        sig = _signal_for(key)
                        sig_loaded = True
                    if self._particle_fwhm_s(p, time_arr, sig) <= max_s:
                        continue
                    if (sig is not None and self.saturation_flat_ratio > 0
                            and self._particle_flat_ratio(p, time_arr, sig)
                            < self.saturation_flat_ratio):
                        continue
                    left = max(0, min(int(p.get('left_idx', 0)), n - 1))
                    right = max(left, min(int(p.get('right_idx', left)), n - 1))
                    windows.append((float(time_arr[left]),
                                    float(time_arr[right])))
            windows = self._merge_time_windows(windows)
            self.saturation_windows[sname] = windows
            self.saturation_excluded_time_s[sname] = float(
                sum(t1 - t0 for t0, t1 in windows))
            if not windows:
                continue

            store = self.saturation_filtered_peaks.setdefault(sname, {})
            for key, particles in list(detected.items()):
                if not particles:
                    continue
                kept, removed = [], []
                for p in particles:
                    if p is None:
                        continue
                    t_apex = self._particle_apex_time(p, time_arr)
                    if any(t0 <= t_apex <= t1 for t0, t1 in windows):
                        removed.append(p)
                    else:
                        kept.append(p)
                if removed:
                    detected[key] = kept
                    store.setdefault(key, []).extend(removed)
                    n_removed += len(removed)

            if sname == self.current_sample and getattr(self, 'multi_element_particles', None):
                kept, removed = [], []
                for mp in self.multi_element_particles:
                    try:
                        s = float(mp.get('start_time', 0.0))
                        e = float(mp.get('end_time', s))
                    except (TypeError, ValueError):
                        s = e = 0.0
                    if any(s <= t1 and e >= t0 for t0, t1 in windows):
                        removed.append(mp)
                    else:
                        kept.append(mp)
                if removed:
                    self.multi_element_particles = kept
                    self.saturation_filtered_multi.setdefault(
                        sname, []).extend(removed)
                    n_removed += len(removed)

        return n_removed

    def restore_saturation_filtered(self, samples=None):
        """
        Merge previously filtered particles back into the detection
        results in time order. Entries whose isotope is no longer
        present in the detection results are discarded rather than
        resurrected.

        Args:
            samples (list): Optional list of samples to restore.
                Defaults to every sample with filtered particles.

        Returns:
            int: Number of particle events restored.
        """
        target = samples if samples is not None else list(self.saturation_filtered_peaks.keys())
        n_restored = 0

        for sname in list(target):
            store = self.saturation_filtered_peaks.get(sname)
            if not store:
                continue
            detected = self.sample_detected_peaks.setdefault(sname, {})
            for key, removed in store.items():
                if not removed or key not in detected:
                    continue
                merged = list(detected.get(key, [])) + list(removed)
                merged.sort(key=lambda p: p.get('left_idx', 0) if p else 0)
                detected[key] = merged
                n_restored += len(removed)
            self.saturation_filtered_peaks.pop(sname, None)
            self.saturation_windows.pop(sname, None)
            self.saturation_excluded_time_s.pop(sname, None)

        for sname in (samples if samples is not None
                      else list(self.saturation_filtered_multi.keys())):
            removed = self.saturation_filtered_multi.pop(sname, None)
            if not removed:
                continue
            n_restored += len(removed)
            if sname == self.current_sample:
                merged = list(getattr(self, 'multi_element_particles', [])) + list(removed)
                merged.sort(key=lambda mp: mp.get('start_time', 0.0))
                self.multi_element_particles = merged

        if self.current_sample in self.sample_detected_peaks:
            self.detected_peaks = self.sample_detected_peaks[self.current_sample]

        return n_restored

    def get_saturation_excluded_time(self, sample_name=None):
        """
        Return the total time excluded by the non-linearity filter for a
        sample, in seconds. This duration is subtracted from the
        analysis time when computing particle number concentrations so
        the result stays unbiased.

        Args:
            sample_name (str): Sample identifier. Defaults to the
                current sample.

        Returns:
            float: Excluded time in seconds, 0.0 when the filter is off.
        """
        sname = sample_name or self.current_sample
        if not self.saturation_filter_enabled:
            return 0.0
        return float(self.saturation_excluded_time_s.get(sname, 0.0))

    def _on_isotopes_removed(self, removed_isotopes):
        """
        Keep the non-linearity filter consistent after isotopes are
        removed from the selection: stored filtered particles of the
        removed isotopes are dropped, and the filter is re-evaluated so
        windows that were flagged by a removed isotope disappear and the
        particles of the remaining isotopes inside them are restored.

        Args:
            removed_isotopes (set): Set of (element, isotope) tuples.

        Returns:
            None
        """
        if not removed_isotopes:
            return
        for store in self.saturation_filtered_peaks.values():
            for key in list(store.keys()):
                if key in removed_isotopes:
                    del store[key]
        if self.saturation_filter_enabled:
            n = self.apply_saturation_filter()
            self.status_label.setText(
                f"Non-linearity filter re-evaluated: {n} particle event(s) excluded")
            self._refresh_after_saturation_change()

    def _sync_saturation_filter_ui(self):
        """
        Synchronize the non-linearity filter button with the current
        state, without re-triggering the filter. Used after a project is
        loaded.

        Returns:
            None
        """
        if not hasattr(self, 'saturation_filter_button'):
            return
        self.saturation_filter_button.blockSignals(True)
        self.saturation_filter_button.setChecked(bool(self.saturation_filter_enabled))
        self.saturation_filter_button.blockSignals(False)
        self._update_saturation_button_text()

    def on_saturation_filter_toggled(self, checked):
        """
        Toggle the detector non-linearity filter on or off.

        Args:
            checked (bool): New button state.

        Returns:
            None
        """
        self.saturation_filter_enabled = bool(checked)
        if checked:
            n = self.apply_saturation_filter()
            excl_ms = self.get_saturation_excluded_time() * 1000.0
            msg = (f"Non-linearity filter ON (FWHM > {self.saturation_filter_ms:g} ms): "
                   f"{n} particle event(s) excluded, "
                   f"{excl_ms:.1f} ms removed from the analysis time")
        else:
            n = self.restore_saturation_filtered()
            msg = f"Non-linearity filter OFF: {n} particle event(s) restored"
        self.status_label.setText(msg)
        self.user_action_logger.log_action(
            'ANALYSIS', 'Non-linearity filter toggled',
            {'enabled': self.saturation_filter_enabled,
             'threshold_ms': self.saturation_filter_ms,
             'affected_particles': n})
        self._update_saturation_button_text()
        self.unsaved_changes = True
        self._refresh_after_saturation_change()

    def show_saturation_filter_menu(self, pos):
        """
        Show the right-click menu of the non-linearity filter button.

        Args:
            pos (QPoint): Local position of the context menu request.

        Returns:
            None
        """
        menu = QMenu(self)

        configure_action = QAction("Configure filter…", self)
        configure_action.triggered.connect(self.configure_saturation_filter)
        menu.addAction(configure_action)

        highlight_action = QAction("Highlight filtered particles in plot", self)
        highlight_action.setCheckable(True)
        highlight_action.setChecked(self.saturation_highlight)

        def _set_highlight(state):
            self.saturation_highlight = bool(state)
            QSettings("IsotopeTrack", "IsotopeTrack").setValue(
                "filters/saturation_highlight", self.saturation_highlight)
            self._refresh_after_saturation_change()

        highlight_action.toggled.connect(_set_highlight)
        menu.addAction(highlight_action)

        menu.addSeparator()
        n_filtered = sum(
            len(plist)
            for store in self.saturation_filtered_peaks.values()
            for plist in store.values())
        excl_ms = self.get_saturation_excluded_time() * 1000.0
        info_action = QAction(
            f"Excluded: {n_filtered} event(s), "
            f"{excl_ms:.1f} ms of analysis time (current sample)", self)
        info_action.setEnabled(False)
        menu.addAction(info_action)

        menu.exec(self.saturation_filter_button.mapToGlobal(pos))

    def configure_saturation_filter(self):
        """
        Open the settings dialog of the non-linearity filter. The
        criteria are the maximum peak FWHM, the minimum SNR, the
        minimum flat-top width ratio and the level at which the top
        width is measured. The filter is re-evaluated immediately when
        it is enabled.

        Returns:
            None
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Detector Non-linearity Filter Settings")
        layout = QVBoxLayout(dialog)

        info = QLabel(
            "Events recorded under non-linear detector response are\n"
            "identified from the peak shape: the response stays wide at\n"
            "the top instead of narrowing like a normal particle\n"
            "transient. When any isotope shows such a peak, the whole\n"
            "time window of the event is excluded for ALL isotopes, and\n"
            "the excluded time is subtracted from the analysis time used\n"
            "for particle number concentrations.")
        info.setWordWrap(True)
        layout.addWidget(info)

        row = QHBoxLayout()
        row.addWidget(QLabel("Maximum peak FWHM:"))
        spin = QDoubleSpinBox()
        spin.setRange(0.001, 100000.0)
        spin.setDecimals(3)
        spin.setSuffix(" ms")
        spin.setValue(self.saturation_filter_ms)
        row.addWidget(spin)
        row.addStretch()
        layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Minimum peak SNR to flag:"))
        snr_spin = QDoubleSpinBox()
        snr_spin.setRange(1.0, 100000.0)
        snr_spin.setDecimals(1)
        snr_spin.setToolTip(
            "Non-linearity events are large by definition. Peaks below\n"
            "this signal-to-threshold ratio are never flagged, even if\n"
            "their width estimate is noisy.")
        snr_spin.setValue(self.saturation_min_snr)
        row2.addWidget(snr_spin)
        row2.addStretch()
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Minimum flat-top ratio (W_top/FWHM):"))
        flat_spin = QDoubleSpinBox()
        flat_spin.setRange(0.0, 1.0)
        flat_spin.setSingleStep(0.05)
        flat_spin.setDecimals(2)
        flat_spin.setToolTip(
            "Healthy transients narrow sharply toward the apex (Gaussian\n"
            "at the 90 percent level: 0.39); a non-linear response stays\n"
            "wide at the top (ratio toward 1). Set to 0 to disable.")
        flat_spin.setValue(self.saturation_flat_ratio)
        row3.addWidget(flat_spin)
        row3.addStretch()
        layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Top width measured at (% of max):"))
        frac_spin = QDoubleSpinBox()
        frac_spin.setRange(50.0, 99.0)
        frac_spin.setSingleStep(5.0)
        frac_spin.setDecimals(0)
        frac_spin.setSuffix(" %")
        frac_spin.setToolTip(
            "Level at which the top width is measured. 90 percent gives\n"
            "the best shape discrimination at short dwell times; lower\n"
            "levels make the ratio larger and noisier for narrow peaks\n"
            "(Gaussian reference: 0.39 at 90, 0.57 at 80). Adjust the\n"
            "flat-top ratio threshold accordingly if you change this.")
        frac_spin.setValue(self.saturation_top_frac * 100.0)
        row4.addWidget(frac_spin)
        row4.addStretch()
        layout.addLayout(row4)

        highlight_cb = QCheckBox("Highlight filtered particles in the plot")
        highlight_cb.setChecked(self.saturation_highlight)
        layout.addWidget(highlight_cb)

        buttons = QHBoxLayout()
        buttons.addStretch()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        self.saturation_filter_ms = float(spin.value())
        self.saturation_min_snr = float(snr_spin.value())
        self.saturation_flat_ratio = float(flat_spin.value())
        self.saturation_top_frac = float(frac_spin.value()) / 100.0
        self.saturation_highlight = highlight_cb.isChecked()
        settings = QSettings("IsotopeTrack", "IsotopeTrack")
        settings.setValue("filters/saturation_fwhm_ms", self.saturation_filter_ms)
        settings.setValue("filters/saturation_min_snr", self.saturation_min_snr)
        settings.setValue("filters/saturation_flat_ratio", self.saturation_flat_ratio)
        settings.setValue("filters/saturation_top_frac", self.saturation_top_frac)
        settings.setValue("filters/saturation_highlight", self.saturation_highlight)

        self.user_action_logger.log_action(
            'ANALYSIS', 'Non-linearity filter configured',
            {'threshold_ms': self.saturation_filter_ms,
             'min_snr': self.saturation_min_snr,
             'flat_ratio': self.saturation_flat_ratio,
             'top_frac': self.saturation_top_frac,
             'highlight': self.saturation_highlight})

        if self.saturation_filter_enabled:
            n = self.apply_saturation_filter()
            self.status_label.setText(
                f"Non-linearity filter updated (FWHM > {self.saturation_filter_ms:g} ms): "
                f"{n} particle event(s) excluded")
            self.unsaved_changes = True
        self._update_saturation_button_text()
        self._refresh_after_saturation_change()

    def _refresh_after_saturation_change(self):
        """
        Refresh the plot, the results tables and the summary of the
        currently displayed element after the non-linearity filter
        changed.

        Returns:
            None
        """
        try:
            if (self.current_element is not None and
                    getattr(self, 'current_isotope', None) is not None and
                    (self.current_element, self.current_isotope) in self.detected_peaks):
                element_key = f"{self.current_element}-{self.current_isotope:.4f}"
                isotope_key = self.find_closest_isotope(self.current_isotope)
                if isotope_key is not None and isotope_key in self.data:
                    signal = self.data[isotope_key]
                    particles = self.detected_peaks[(self.current_element, self.current_isotope)]
                    try:
                        stored = self.element_thresholds[self.current_sample][element_key]
                        lambda_bkgd = stored.get('background', 0)
                        threshold = stored.get('threshold', 0)
                    except KeyError:
                        lambda_bkgd = 0
                        threshold = 0
                    view = None
                    try:
                        vr = self.plot_widget.viewRect()
                        view = ([vr.left(), vr.right()], [vr.top(), vr.bottom()])
                    except Exception:
                        pass
                    self.plot_results(element_key, signal, particles,
                                      lambda_bkgd, threshold,
                                      preserve_view_range=view)
                    self.update_results_table(particles, signal,
                                              self.current_element,
                                              self.current_isotope)
                    self.update_element_summary(self.current_element,
                                                self.current_isotope,
                                                particles)
        except Exception as e:
            self.logger.debug(f"Non-linearity filter refresh (element view) failed: {e}")

        try:
            self.rebuild_particle_data(self.current_sample)
        except Exception as e:
            self.logger.debug(f"Non-linearity filter refresh (particle data) failed: {e}")

        try:
            self.update_multi_element_table()
        except Exception as e:
            self.logger.debug(f"Non-linearity filter refresh (multi-element) failed: {e}")

    def export_data(self):
        """
        Export all data using external export utility.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.user_action_logger.log_action(
            'FILE_OP', 'Export data triggered',
            {'sample_count': len(self.sample_to_folder_map),
             'current_sample': self.current_sample})
        from save_export.export_utils import export_data
        export_data(self)

    def closeEvent(self, event):
        """
        Handle application close event with unsaved changes check.
        
        Args:
            self: MainWindow instance
            event: QCloseEvent object
            
        Returns:
            None
        """
        if self.unsaved_changes:
            reply = QMessageBox.question(
                self, 
                'Save Project?',
                'You have unsaved changes. Would you like to save your project before closing?',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )       
            if reply == QMessageBox.Save:
                saved = self.save_project()
                if not saved:
                    event.ignore()
                    return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        
        for timer in self.findChildren(QTimer):
            timer.stop()

        try:
            theme.themeChanged.disconnect(self.apply_theme)
        except (RuntimeError, TypeError):
            pass 

        if hasattr(self, '_theme_follow_system_slot'):
            try:
                theme.themeChanged.disconnect(self._theme_follow_system_slot)
            except (RuntimeError, TypeError):
                pass


        if getattr(self, 'periodic_table_widget', None) is not None:
            self.periodic_table_widget.close()
            self.periodic_table_widget = None

        if getattr(self, 'transport_rate_window', None) is not None:
            self.transport_rate_window.close()
            self.transport_rate_window = None

        if getattr(self, 'ionic_calibration_window', None) is not None:
            self.ionic_calibration_window.close()
            self.ionic_calibration_window = None

        if getattr(self, 'canvas_results_dialog', None):
            self.canvas_results_dialog.close()
            self.canvas_results_dialog = None

        if getattr(self, 'csv_thread', None) is not None:
            if self.csv_thread.isRunning():
                self.csv_thread.quit()
                self.csv_thread.wait(3000)   
            self.csv_thread = None

        app = QApplication.instance()
        if hasattr(app, 'main_windows'):
            try:
                app.main_windows.remove(self)
            except ValueError:
                pass
        
        if not getattr(app, 'main_windows', []):
            app.quit()

        event.accept()
        
    #----------------------------------------------------------------------------------------------------------
    #------------------------------------help and documentation--------------------------------------------
    #----------------------------------------------------------------------------------------------------------
        
    def show_user_guide(self):
        """
        Display user guide dialog.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.help_manager.show_user_guide()
        
    def show_detection_methods(self):
        """
        Display detection methods information dialog.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.help_manager.show_detection_methods()
        
    def show_calibration_methods(self):
        """
        Display calibration methods information dialog.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.help_manager.show_calibration_methods()
        
    def show_about_dialog(self):
        """
        Display about application dialog.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        from tools.help_dialogs import AboutDialog
        dialog = AboutDialog(self)
        dialog.exec()    
                     
    def show_log_window(self):
        """
        Open the application log viewer window.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        try:
            logging_manager.show_log_window(self)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open log window: {str(e)}")

    #----------------------------------------------------------------------------------------------------------
    #------------------------------------utility functions--------------------------------------------
    #----------------------------------------------------------------------------------------------------------
                    
    def eventFilter(self, obj, event):
        """
        Handle keyboard navigation for tables.
        
        Args:
            self: MainWindow instance
            obj: Object receiving event
            event: QEvent object
            
        Returns:
            bool: True if event was handled, False otherwise
        """
        if event.type() == QEvent.KeyPress:
            if obj == self.sample_table:
                if event.key() == Qt.Key_Up or event.key() == Qt.Key_Down:
                    current_row = self.sample_table.currentRow()
                    new_row = current_row
                    
                    if event.key() == Qt.Key_Up and current_row > 0:
                        new_row = current_row - 1
                    elif event.key() == Qt.Key_Down and current_row < self.sample_table.rowCount() - 1:
                        new_row = current_row + 1
                        
                    if new_row != current_row:
                        self.sample_table.setCurrentCell(new_row, 0)
                        item = self.sample_table.item(new_row, 0)
                        if item:
                            self.on_sample_selected(item)
                        return True
                        
                elif event.key() == Qt.Key_Tab:
                    self.parameters_table.setFocus()
                    if self.parameters_table.currentRow() < 0 and self.parameters_table.rowCount() > 0:
                        self.parameters_table.setCurrentCell(0, 0)
                        self.parameters_table_clicked(0, 0)
                    return True
                    
            elif obj == self.parameters_table:
                if event.key() == Qt.Key_Up or event.key() == Qt.Key_Down:
                    current_row = self.parameters_table.currentRow()
                    new_row = current_row
                    
                    if event.key() == Qt.Key_Up and current_row > 0:
                        new_row = current_row - 1
                    elif event.key() == Qt.Key_Down and current_row < self.parameters_table.rowCount() - 1:
                        new_row = current_row + 1
                        
                    if new_row != current_row:
                        self.parameters_table.setCurrentCell(new_row, 0)
                        self.parameters_table_clicked(new_row, 0)
                        return True
                        
                elif event.key() == Qt.Key_Tab and event.modifiers() & Qt.ShiftModifier:
                    self.sample_table.setFocus()
                    return True
        
        return super().eventFilter(obj, event)

    def get_snr_color(self, snr):
        """
        Get color code based on signal-to-noise ratio.
        
        Args:
            self: MainWindow instance
            snr (float): Signal-to-noise ratio
            
        Returns:
            Color value for visualization
        """
        return self.peak_detector.get_snr_color(snr)

    def calculate_accuracy(self):
        """
        Calculate suspected percentage using SNR criteria.
        
        Args:
            self: MainWindow instance
            
        Returns:
            float: Suspected percentage (0-100)
        """
        if not hasattr(self, 'detected_peaks') or not self.detected_peaks:
            return 0
            
        total_peaks = 0
        strong_peaks = 0
        
        for (element, isotope), peaks in self.detected_peaks.items():
            peak_count = len(peaks)
            total_peaks += peak_count
            
            strong_peaks += sum(1 for p in peaks if p.get('SNR', 0) >= 2.5)
        
        if total_peaks == 0:
            return 0
            
        strong_percentage = (strong_peaks / total_peaks * 100)
        Suspected_percentage = 100 - strong_percentage
        
        return round(Suspected_percentage, 1)
                                        
    def clear_all_displays(self):
        """
        Clear all display elements when no samples available.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.parameters_table.setRowCount(0)
        self.results_table.setRowCount(0)
        self.multi_element_table.setRowCount(0)
        
        self.plot_widget.clear()
        
        if hasattr(self, 'summary_label'):
            self.summary_label.setText("No samples loaded. Please import data to begin analysis.")
        
        self.status_label.setText("No samples available. Please load data to continue.")


if __name__ == "__main__":
    """
    initializes MainWindow, and starts event loop.
    """
    from PySide6.QtCore import Qt, QCoreApplication
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    from PySide6 import QtWebEngineWidgets
    app = QApplication(sys.argv)
    theme.sync_with_system()       
    main_window = MainWindow()
    main_window.showMaximized()
    sys.exit(app.exec())