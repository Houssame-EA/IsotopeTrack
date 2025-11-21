import sys
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QLineEdit, QScrollArea,
                               QWidget, QFileDialog, QProgressBar, QLabel, QHBoxLayout, QComboBox, QSizePolicy, 
                               QTableWidget, QDialog, QMessageBox, QCheckBox, QDoubleSpinBox, QTableWidgetItem,QRadioButton,
                            QGroupBox, QMenu, QTextEdit, QHeaderView, QListView, QTreeView, QAbstractItemView, QSpinBox)
from PySide6.QtCore import Qt, QTimer, QParallelAnimationGroup, QPropertyAnimation, QEasingCurve, QSize, QPoint,  QEvent
from PySide6.QtGui import  QGuiApplication
import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QColor, QBrush, QAction
from PySide6.QtWidgets import QWidget
import json
from calibration_methods.ionic_CAL import IonicCalibrationWindow
from widget.periodic_table_widget import PeriodicTableWidget
from widget.custom_plot_widget import EnhancedPlotWidget
from calibration_methods.TE import TransportRateCalibrationWindow
from widget.numeric_table import NumericTableWidgetItem
from widget.calibration_info import CalibrationInfoDialog
from data_loading.data_thread import DataProcessThread
from tools.Info_table import InfoTooltip
from processing.peak_detection import PeakDetection
from tools.info_file import FileInfoMenu
from widget.batch_parameters import BatchElementParametersDialog
from save_export.project_manager import ProjectManager
from widget.canvas_widgets import CanvasResultsDialog
from data_loading.SIA_manager import SingleIonDistributionManager
import qtawesome as qta
from tools.signal_selector_dialog import SignalSelectorDialog
from tools.logging_utils import logging_manager, log_user_action
import logging
from widget.colors import element_colors

try:
    from data_loading.import_csv_dialogs import CSVStructureDialog, CSVDataProcessThread, show_csv_structure_dialog
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
            
        self.setWindowTitle("IsotopeTrack")
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
        self.animation = None
        self.animation_group = None
        self.overlap_threshold_percentage = 50.0
        self._global_sigma = 0.47
        self.sidebar_width = 200
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
        self.data_by_sample = {}
        self.element_limits = {} 
        self.sia_manager = SingleIonDistributionManager(self)
        self.element_thresholds = {}
        self.time_array_by_sample = {}
        self.canvas_results_dialog = None
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
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f4f8;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f4f8;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #bdc3c7;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.initialize_help_manager()
        self.transport_rate_window = None
        self.ionic_calibration_window = None
        
        if not hasattr(QApplication.instance(), 'main_windows'):
            QApplication.instance().main_windows = []
        QApplication.instance().main_windows.append(self)
            
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
    
    
    def create_central_widget(self):
        """
        Create and configure the central widget with main UI layout.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar_container = QWidget()
        sidebar_container_layout = QHBoxLayout(self.sidebar_container)
        sidebar_container_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_container_layout.setSpacing(0)

        self.edge_strip = QWidget()
        self.edge_strip.setFixedWidth(25)
        self.edge_strip.setCursor(Qt.PointingHandCursor)
        self.edge_strip.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
            QWidget:hover {
                background-color: #3498db;
            }
        """)
        self.edge_strip.mousePressEvent = lambda e: self.toggle_sidebar()
        self.edge_strip.hide()
        self.sidebar = self.create_sidebar()
        sidebar_container_layout.addWidget(self.edge_strip)
        sidebar_container_layout.addWidget(self.sidebar)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        plot_container = QWidget()
        plot_container_layout = QHBoxLayout(plot_container)
        plot_container_layout.setContentsMargins(0, 0, 0, 0)
        plot_container_layout.setSpacing(0)

        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setAlignment(Qt.AlignTop | Qt.AlignRight)

        self.info_button = QPushButton()
        self.info_button.setIcon(qta.icon('fa6s.circle-info', color="#3498db"))
        self.info_button.setFixedSize(32, 32)
        self.info_button.setToolTip("Sample information")
        self.info_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffffff, stop:1 #ffffff);
                border-radius: 16px;
                padding: 4px;
            }
        """)
        self.info_button.setCursor(Qt.PointingHandCursor)
        self.info_button.clicked.connect(self.toggle_info)  
        info_layout.addWidget(self.info_button)

        plot_widget = self.create_plot_widget()
        plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plot_container_layout.addWidget(plot_widget)
        plot_container_layout.addWidget(info_container)

        page_content = QWidget()
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
        
    
    def create_sidebar(self):
        """
        Create sidebar with calibration and sample management tools.
        
        Args:
            self: MainWindow instance
            
        Returns:
            QWidget: Configured sidebar widget
        """
        sidebar = QWidget()
        sidebar.setStyleSheet("""
            QWidget {
                background-color: #2c3e50;
                color: #ecf0f1;
            }
            QPushButton {
                background-color: #34495e;
                color: #ecf0f1;
                text-align: left;
                padding: 15px;
                border: none;
                border-radius: 0;
            }
            QPushButton:hover {
                background-color: #4a6785;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 18px;
                border: 2px solid #4a6785;
                border-radius: 8px;
                margin-top: 1em;
                padding-top: 15px;
                color: #ecf0f1;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                padding: 0 10px;
                color: #3498db;
            }
        """)
        sidebar.setFixedWidth(self.sidebar_width)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(0)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        header_container = QWidget()
        header_container.setFixedHeight(60)
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(5, 0, 5, 0)
        header_layout.setSpacing(10)

        logo = QLabel("Tools")
        logo.setStyleSheet("font-size: 30px; color: #3498db; font-weight: bold;")
        header_layout.addWidget(logo)

        self.toggle_button = QPushButton()
        self.toggle_button.setIcon(qta.icon('fa6s.arrow-left', color="#ecf0f1"))
        self.toggle_button.setIconSize(QSize(24, 24))
        self.toggle_button.setFixedSize(32, 32)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                border-radius: 16px;
                padding: 4px;
                margin: 0px;
            }
        """)
        self.toggle_button.clicked.connect(self.toggle_sidebar)
        header_layout.addWidget(self.toggle_button, alignment=Qt.AlignVCenter)
        
        sidebar_layout.addWidget(header_container)

        calibration_group = QGroupBox("Calibration")
        calibration_layout = QVBoxLayout(calibration_group)
        calibration_layout.setSpacing(0)
        calibration_layout.setContentsMargins(5, 0, 5, 5)

        transport_rate_button = QPushButton("Transport Rate")
        transport_rate_button.setIcon(qta.icon('fa6s.scale-balanced', color="#ecf0f1"))
        transport_rate_button.clicked.connect(self.open_transport_rate_calibration)
        calibration_layout.addWidget(transport_rate_button)

        sensitivity_button = QPushButton("Sensitivity")
        sensitivity_button.setIcon(qta.icon('fa6s.chart-line', color="#ecf0f1"))
        sensitivity_button.clicked.connect(self.open_ionic_calibration)
        calibration_layout.addWidget(sensitivity_button)

        self.show_calibration_button = QPushButton("Show Calibration Info")
        self.show_calibration_button.setIcon(qta.icon('fa6s.eye', color="#ecf0f1"))
        self.show_calibration_button.clicked.connect(self.show_calibration_info)
        calibration_layout.addWidget(self.show_calibration_button)

        sidebar_layout.addWidget(calibration_group)
        
        samples_group = QGroupBox("Samples")
        samples_layout = QVBoxLayout(samples_group)
        samples_layout.setSpacing(0)
        samples_layout.setContentsMargins(0, 10, 0, 0)
        
        import_button = QPushButton("Import Data")
        import_button.setIcon(qta.icon('fa6s.file-import', color="#ecf0f1"))
        import_button.clicked.connect(self.select_folder)
        samples_layout.addWidget(import_button)

        elements_button = QPushButton("Add/Edit Elements")
        elements_button.setIcon(qta.icon('fa6s.plus-minus', color="#ecf0f1"))
        elements_button.clicked.connect(self.show_periodic_table)
        samples_layout.addWidget(elements_button)

        results_button = QPushButton("Results")
        results_button.setIcon(qta.icon('fa6s.table-list', color="#ecf0f1"))
        results_button.clicked.connect(self.show_results)
        samples_layout.addWidget(results_button)

        export_button = QPushButton("Export")
        export_button.setIcon(qta.icon('fa6s.file-export', color="#ecf0f1"))
        export_button.clicked.connect(self.export_data)
        samples_layout.addWidget(export_button)
        


        sample_list_label = QLabel("Sample List")
        sample_list_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                padding: 10px 15px 5px 15px;
                color: #bdc3c7;
            }
        """)
        samples_layout.addWidget(sample_list_label)

        self.sample_table = self.create_sample_table()
        samples_layout.addWidget(self.sample_table)

        sidebar_layout.addWidget(samples_group)

        self.calibration_info_panel = QTextEdit()
        self.calibration_info_panel.setReadOnly(True)
        self.calibration_info_panel.setAcceptRichText(True)
        self.calibration_info_panel.setStyleSheet("""
            QTextEdit {
                background-color: #34495e;
                color: #ecf0f1;
                border: none;
                padding: 10px;
            }
        """)
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
        
        new_window_action = QAction(qta.icon('fa6s.window-restore', color="#ecf0f1"), "New Window", self)
        new_window_action.setShortcut("Cmd+N")
        new_window_action.triggered.connect(self.open_new_window)
        
        open_action = QAction(qta.icon('fa6s.folder-open', color="#ecf0f1"), "Import Data", self)
        open_action.triggered.connect(self.select_folder)

        save_action = QAction(qta.icon('fa6s.floppy-disk', color="#ecf0f1"), "Save Project", self)
        save_action.triggered.connect(self.save_project)

        load_action = QAction(qta.icon('fa6s.folder-open', color="#ecf0f1"), "Load Project", self)
        load_action.triggered.connect(self.load_project)

        export_action = QAction(qta.icon('fa6s.file-export', color="#ecf0f1"), "Export", self)
        export_action.triggered.connect(self.export_data)

        exit_action = QAction(qta.icon('fa6s.right-from-bracket', color="#ecf0f1"), "Exit", self)
        exit_action.triggered.connect(self.close_all_windows)

        file_menu = menu_bar.addMenu("File")
        file_menu.setIcon(qta.icon('fa6s.scale-balanced', color="#ecf0f1"))
        file_menu.addAction(new_window_action)
        file_menu.addSeparator()
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addAction(load_action)
        file_menu.addAction(export_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
                
        tools_menu = menu_bar.addMenu("Tools")
        tools_menu.setIcon(qta.icon('fa6s.wrench', color="#ecf0f1"))

        periodic_action = QAction(qta.icon('fa6s.atom', color="#ecf0f1"), "Add/Edit Element PT", self)
        periodic_action.triggered.connect(self.show_periodic_table)

        ionic_action = QAction(qta.icon('fa6s.gear', color="#ecf0f1"), "Sensitivity", self)
        ionic_action.triggered.connect(self.open_ionic_calibration)
        
        mass_fraction_action = QAction(qta.icon('fa6s.calculator', color="#ecf0f1"),"Mass Fraction Calculator", self)
        mass_fraction_action.triggered.connect(self.open_mass_fraction_calculator)
        
        tools_menu.addAction(periodic_action)
        tools_menu.addAction(mass_fraction_action)
        tools_menu.addAction(ionic_action)

        view_menu = menu_bar.addMenu("View")
        view_menu.setIcon(qta.icon('fa6s.eye', color="#ecf0f1"))

        sidebar_action = QAction(qta.icon('fa6s.bars', color="#ecf0f1"), "Toggle Sidebar", self)
        sidebar_action.triggered.connect(self.toggle_sidebar)
        view_menu.addAction(sidebar_action)
        
        view_menu.addSeparator()
        log_action = QAction(qta.icon('fa6s.file-lines', color="#ecf0f1"), "Show Application Log", self)
        log_action.triggered.connect(self.show_log_window)
        view_menu.addAction(log_action)
            
        help_menu = menu_bar.addMenu("Help")
        help_menu.setIcon(qta.icon('fa6s.circle-question', color="#ecf0f1"))
        
        guide_action = QAction(qta.icon('fa6s.book', color="#ecf0f1"), "User Guide", self)
        guide_action.triggered.connect(self.show_user_guide)

        detection_action = QAction(qta.icon('fa6s.magnifying-glass', color="#ecf0f1"), "Detection Methods", self)
        detection_action.triggered.connect(self.show_detection_methods)

        calibration_action = QAction(qta.icon('fa6s.sliders', color="#ecf0f1"), "Calibration Methods", self)
        calibration_action.triggered.connect(self.show_calibration_methods)

        about_action = QAction(qta.icon('fa6s.circle-info', color="#ecf0f1"), "About IsotopeTrack", self)
        about_action.triggered.connect(self.show_about_dialog)

        help_menu.addAction(guide_action)
        help_menu.addAction(detection_action)
        help_menu.addAction(calibration_action)
        help_menu.addSeparator()
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
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                background-color: #ecf0f1;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3498db;
            }
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar, 0)
        
        status_bar.addPermanentWidget(container, 1)
        
    def create_plot_widget(self):
        """
        Create plot widget for data visualization.
        
        Args:
            self: MainWindow instance
            
        Returns:
            QGroupBox: Plot widget container
        """
        group_box = QGroupBox("Data Visualization")
        layout = QVBoxLayout(group_box)
        
        self.plot_widget = EnhancedPlotWidget(self)
        self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_widget.setMinimumHeight(400) 
        
        layout.addWidget(self.plot_widget)
        return group_box
    
    def create_control_panel(self):
        """
        Create control panel for particle detection parameters.
        
        Args:
            self: MainWindow instance
            
        Returns:
            QGroupBox: Control panel widget
        """
        group_box = QGroupBox("Particle peak detection parameters")
        group_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 1.2em;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                padding: 0 10px;
            }
        """)
        
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
        self.sigma_spinbox.setValue(0.47)
        self.sigma_spinbox.setSingleStep(0.01)
        self.sigma_spinbox.setToolTip("Sigma value (only influences compound Poisson calculation)")
        self.sigma_spinbox.setFixedWidth(80)
        self.sigma_spinbox.valueChanged.connect(self.on_sigma_changed)
        
        first_row_layout.addWidget(sigma_label)
        first_row_layout.addWidget(self.sigma_spinbox)
        
        first_row_layout.addSpacing(30)
        
        sid_label = QLabel("Single-Ion Distribution:")
        first_row_layout.addWidget(sid_label)

        self.sia_manager.create_sia_buttons(first_row_layout)
                
        first_row_layout.addStretch()  
        
        main_layout.addLayout(first_row_layout)
        self.parameters_table = QTableWidget()
        self.parameters_table.setColumnCount(8)
        headers = ['Element', 'Include','Detection Method', 'Smoothing Window Length', 
                'Smoothing iterations', 'Mimimum Point', 'Alpha']
        self.parameters_table.setHorizontalHeaderLabels(headers)
        self.parameters_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 5px;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 5px;
                min-height: 20px;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 7px 7px;
                border: 1px solid #cccccc;
                font-weight: bold;
                font-size: 12px;
                min-height: 25px;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1565c0;
            }
        """)
        
        self.parameters_table.verticalHeader().setDefaultSectionSize(45)
        column_widths = {
            0: 80,
            1: 50,
            2: 155,
            3: 130,
            4: 130,
            5: 150,
            6: 150,
            7: 100,
            8: 120,
        }
        
        
        for col, width in column_widths.items():
            self.parameters_table.setColumnWidth(col, width)
    
        self.parameters_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        
        for col, width in column_widths.items():
            self.parameters_table.horizontalHeader().setMinimumSectionSize(70)
        
        self.parameters_table.horizontalHeader().setStretchLastSection(True)
        
        self.parameters_table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        
    
        self.parameters_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.parameters_table.setAlternatingRowColors(True)
        self.parameters_table.verticalHeader().setVisible(False)
        self.parameters_table.setEditTriggers(QTableWidget.DoubleClicked)
        self.parameters_table.setMinimumHeight(180)
        
        self.parameters_table.cellClicked.connect(self.parameters_table_clicked)
        self.parameters_table.installEventFilter(self)
        self.parameters_table.setFocusPolicy(Qt.StrongFocus)
        main_layout.addWidget(self.parameters_table)


        button_layout = QHBoxLayout()
    
        button_style = """
            QPushButton {
                padding: 8px 15px;
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
            QPushButton:checked {
                background-color: #4CAF50;
            }
        """
        
        self.batch_edit_button = QPushButton("Batch Edit Parameters")
        self.batch_edit_button.setIcon(qta.icon('fa6s.list-check', color="#ffffff"))
        self.batch_edit_button.setStyleSheet(button_style)
        self.batch_edit_button.clicked.connect(self.open_batch_parameters_dialog)
        button_layout.addWidget(self.batch_edit_button)
        
    
        self.show_all_signals_button = QPushButton("Multi-Signal View")
        self.show_all_signals_button.setIcon(qta.icon('fa6s.chart-column', color="#ffffff"))
        self.show_all_signals_button.setStyleSheet(button_style)
        self.show_all_signals_button.setToolTip("Open multi-signal display with particle detection")
        self.show_all_signals_button.clicked.connect(self.show_signal_selector)
        button_layout.addWidget(self.show_all_signals_button)
                
        self.detect_button = QPushButton("Detect Peaks")
        self.detect_button.setIcon(qta.icon('fa6s.bolt', color="#ffffff"))
        self.detect_button.setStyleSheet(button_style)
        self.detect_button.clicked.connect(self.detect_particles)
        
        button_layout.addWidget(self.detect_button)
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
        group_box = QGroupBox("Particle Summary Statistics")
        group_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 1.2em;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                padding: 0 10px;
            }
        """)
        
        layout = QVBoxLayout(group_box)
        
        self.summary_label = QLabel("Select an element to view summary statistics")
        self.summary_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                padding: 10px;
                background-color: #f7f9fc;
                border-radius: 5px;
            }
        """)
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
        container.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(8)
        header_widget = QWidget()
        header_widget.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border-radius: 6px;
                border: 1px solid #e1e8ed;
            }
        """)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(15, 12, 15, 12)
        header_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("Results Display")
        
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding: 0px;
            }
        """)
        title_row.addWidget(title_label)
        
        title_row.addStretch()

        perf_tip = QLabel("💡 Tip: Keep tables unchecked for better performance during analysis")
        perf_tip.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #7f8c8d;
                font-style: italic;
                padding: 2px 8px;
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
            }
        """)
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
        element_layout.addWidget(element_header)
        element_layout.addWidget(self.create_results_table())
        
        self.particle_results_container = QWidget()
        particle_layout = QVBoxLayout(self.particle_results_container)
        particle_layout.setContentsMargins(0, 5, 0, 0)
        
        particle_header = self.create_table_header("Multi-Element Particle Results", "#e4cbb8", "#eb7318")
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
        self.sample_table.setStyleSheet("""
            QTableWidget {
                background-color: #34495e;
                color: #ecf0f1;
                border: none;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: #ecf0f1;
                padding: 5px;
                border: none;
            }
        """)
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

        checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 14px;
                font-weight: 500;
                padding: 8px 12px;
                color: #2c3e50;
                background-color: #ffffff;
                border: 2px solid #e1e8ed;
                border-radius: 8px;
                spacing: 8px;
            }
            QCheckBox:hover {
                background-color: #f8f9fa;
                border: 2px solid #3498db;
                color: #2980b9;
            }
            QCheckBox:checked {
                background-color: #e3f2fd;
                border: 2px solid #2196F3;
                color: #1565c0;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #bdc3c7;
                background-color: #ffffff;
            }
            QCheckBox::indicator:unchecked:hover {
                border: 2px solid #3498db;
                background-color: #ecf0f1;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #2196F3;
                background-color: #2196F3;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDQuNUw0LjUgOEwxMSAxIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
            }
            QCheckBox::indicator:checked:hover {
                background-color: #1976d2;
                border: 2px solid #1976d2;
            }
        """)

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
        if self.animation is not None and self.animation.state() == QPropertyAnimation.Running:
            return

        self.animation = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)

        self.animation_max = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self.animation_max.setDuration(250)
        self.animation_max.setEasingCurve(QEasingCurve.InOutCubic)

        if self.sidebar_visible:
            self.animation.setStartValue(self.sidebar_width)
            self.animation.setEndValue(0)
            self.animation_max.setStartValue(self.sidebar_width)
            self.animation_max.setEndValue(0)
            self.toggle_button.hide()
            self.edge_strip.show()
        else:
            self.animation.setStartValue(0)
            self.animation.setEndValue(self.sidebar_width)
            self.animation_max.setStartValue(0)
            self.animation_max.setEndValue(self.sidebar_width)
            self.sidebar.show()        
            self.toggle_button.show()
            self.toggle_button.setIcon(qta.icon('fa6s.arrow-left', color="#ecf0f1"))
            self.edge_strip.hide()

        self.animation_group = QParallelAnimationGroup()
        self.animation_group.addAnimation(self.animation)
        self.animation_group.addAnimation(self.animation_max)
        self.animation_group.finished.connect(self.on_animation_finished)
        self.animation_group.start()
        
        self.sidebar_visible = not self.sidebar_visible

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
        self.animation_group.finished.disconnect()
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
                getattr(self, 'multi_element_particles', [])
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
        if hasattr(self, 'sidebar'):
            self.sidebar.setFixedWidth(int(self.width() * 0.2))
        
        if hasattr(self, 'content_area'):
            self.content_area.setSizes([int(self.height() * 0.7), int(self.height() * 0.3)])
            
        
    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------Data loading and import --------------------------------------------
    #---------------------------------------------------------------------------------------------------------- 
   
   
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
        layout = QVBoxLayout(dialog)

        instruction = QLabel("Choose your data source type:")
        instruction.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px;")
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

        folder_desc = QLabel("• Select folders containing NU instrument data with run.info files\n• Supports multiple folders for batch processing")
        folder_desc.setStyleSheet("color: #666; margin-left: 20px; font-size: 11px;")
        
        csv_desc = QLabel("• Select Data Files (*.csv *.txt *.xls *.xlsx *.xlsm *.xlsb) with mass spectrometry data\n• Configure column mappings and time settings")
        csv_desc.setStyleSheet("color: #666; margin-left: 20px; font-size: 11px;")
        
        tofwerk_desc = QLabel("• Select TOFWERK .h5 files from TofDAQ acquisitions\n• Supports multiple files for batch processing")
        tofwerk_desc.setStyleSheet("color: #666; margin-left: 20px; font-size: 11px;")
        
        layout.addWidget(folder_desc)
        layout.addWidget(csv_desc)
        layout.addWidget(tofwerk_desc)
        layout.addStretch()

        button_box = QHBoxLayout()
        ok_button = QPushButton("Continue", dialog)
        cancel_button = QPushButton("Cancel", dialog)
        
        for btn in [ok_button, cancel_button]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #545b62;
                }
            """)
        
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
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
        try:
            h5_files, _ = QFileDialog.getOpenFileNames(
                self,
                "Select TOFWERK .h5 Files",
                "",
                "TOFWERK Files (*.h5);;All Files (*)"
            )
            
            if h5_files:
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
            all_masses_from_folders = [] 
            
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
            
            self.sample_to_folder_map.clear()
            self.data_by_sample.clear()
            self.time_array_by_sample.clear()
            self.current_sample = None
            
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("Processing CSV files...")
            
            self.csv_thread = CSVDataProcessThread(filtered_config, self)
            self.csv_thread.progress.connect(self.update_progress)
            self.csv_thread.finished.connect(self.handle_csv_finished)
            self.csv_thread.error.connect(self.handle_error)
            self.csv_thread.start()
            
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
                all_masses_from_files = []
                
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
            if config:
                self.csv_config = config
                self.pending_csv_processing = True
                self.extract_masses_from_csv_config(config)
                self.show_periodic_table_after_load()
            
        except Exception as e:
            QMessageBox.critical(self, "CSV Import Error", f"Error importing CSV files: {str(e)}")
            self.logger.error(f"Error importing CSV files: {str(e)}")

    def extract_masses_from_csv_config(self, config):
        """
        Extract available masses from CSV configuration.
        
        Args:
            self: MainWindow instance
            config (dict): CSV configuration dictionary
            
        Returns:
            None
        """
        masses = []
        for file_config in config['files']:
            for mapping in file_config['mappings'].values():
                isotope = mapping['isotope']
                masses.append(isotope['mass'])
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
                self.data = self.data_by_sample[sample_name].copy()
                self.time_array = self.time_array_by_sample[sample_name].copy()
                
                self.update_parameters_table()
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
                self.data = self.data_by_sample[sample_name].copy()
                self.time_array = self.time_array_by_sample[sample_name].copy()
                
                self.update_parameters_table()
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
                
                self.update_parameters_table()
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
            
            self.update_parameters_table()

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
        
        if (sample_name in self.sample_parameters and 
            self.sample_parameters[sample_name] and 
            hasattr(self, 'sigma_spinbox')):
            
            first_element_key = next(iter(self.sample_parameters[sample_name]))
            stored_sigma = self.sample_parameters[sample_name][first_element_key].get('sigma', 0.47)
            self.sigma_spinbox.setValue(stored_sigma)
            
        if sample_name in self.data_by_sample:
            self.data = self.data_by_sample[sample_name].copy()
            self.time_array = self.time_array_by_sample[sample_name].copy()
            
            if sample_name in self.sample_detected_peaks:
                self.detected_peaks = self.sample_detected_peaks[sample_name].copy()
            else:
                self.detected_peaks = {}
                
            self.update_parameters_table()
            
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
                    getattr(self, 'multi_element_particles', [])
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
            info_action.setIcon(qta.icon('fa6s.barcode', color="#3498db"))
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
            remove_action.setIcon(qta.icon('fa6s.file-circle-minus', color="#e74c3c"))
            remove_action.triggered.connect(lambda: self.remove_sample(sample_name))
            
            if self.sample_table.rowCount() > 1:
                remove_all_action = menu.addAction("Remove All Samples")
                remove_all_action.setIcon(qta.icon('fa6s.file-circle-xmark', color="#e74c3c"))
                remove_all_action.triggered.connect(self.remove_all_samples)
            
            menu.setStyleSheet("""
                QMenu {
                    background-color: white;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px;
                }
                QMenu::item {
                    padding: 8px 20px;
                    border-radius: 3px;
                }
                QMenu::item:selected {
                    background-color: #e3f2fd;
                    color: #1976d2;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #e0e0e0;
                    margin: 4px 0px;
                }
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
                ('sample_method_info', self.sample_method_info)
            ]
            
            removed_count = 0
            for structure_name, structure in data_structures_to_clean:
                if sample_name in structure:
                    del structure[sample_name]
                    removed_count += 1
            
            if hasattr(self, 'element_limits') and sample_name in self.element_limits:
                del self.element_limits[sample_name]
                removed_count += 1
            
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
                            thread.start()
                            
                            while thread.isRunning():
                                QApplication.processEvents()
                                
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
                self.data = self.data_by_sample[first_sample].copy()
                self.time_array = self.time_array_by_sample[first_sample].copy()
            
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
                            thread.start()
                            
                            while thread.isRunning():
                                QApplication.processEvents()
                                
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
                self.data = self.data_by_sample[first_sample].copy()
                self.time_array = self.time_array_by_sample[first_sample].copy()
            
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
                        
    def update_parameters_table(self):
        """
        Update detection parameters table with current sample data.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        self.parameters_table.setRowCount(0)
        self.parameters_table.setColumnCount(11)
        
        headers = ['Element', 'Include', 'Detection Method', 'Manual Threshold', 'Apply Smoothing', 
                'Window Length', 'Smoothing iterations', 'Min Points', 'Alpha (Error Rate)', 'Iterative', 'Window Size'] 
        self.parameters_table.setHorizontalHeaderLabels(headers)
        
        for col, tooltip in enumerate(['element', 'include in analysis', 
                            'detection method', 'manual threshold value (when Manual method selected)', 
                            'apply smoothing', 'smoothing window length', 
                            'smoothing iterations', 'minimum continuous dwell time points above the threshold', 
                            'Alpha', 'iterative background calculation (recommended)', 'window size for background calculation']): 
            item = self.parameters_table.horizontalHeaderItem(col)
            if item:
                item.setToolTip(tooltip) 

        saved_params = self.sample_parameters.get(self.current_sample, {})
        saved_status = self.sample_status.get(self.current_sample, {})

        if self.current_sample and self.current_sample in self.data_by_sample:
            current_sample_data = self.data_by_sample[self.current_sample]
            
            filtered_selected_isotopes = {}
            for element, isotopes in self.selected_isotopes.items():
                element_has_data = False
                element_isotopes_with_data = []
                
                for isotope in isotopes:
                    for data_mass in current_sample_data.keys():
                        if abs(data_mass - isotope) < 0.001: 
                            element_has_data = True
                            element_isotopes_with_data.append(isotope)
                            break

                if element_has_data:
                    filtered_selected_isotopes[element] = element_isotopes_with_data
            
            isotopes_to_show = filtered_selected_isotopes
        else:
            isotopes_to_show = self.selected_isotopes

        element_items = []
        for element, isotopes in isotopes_to_show.items():
            for isotope in isotopes:
                element_key = f"{element}-{isotope:.4f}"
                element_items.append((element_key, float(isotope)))

        element_items.sort(key=lambda x: x[1])

        for element_key, _ in element_items:
            row = self.parameters_table.rowCount()
            self.parameters_table.insertRow(row)
            
            saved_element_params = saved_params.get(element_key, {})
            saved_element_status = saved_status.get(element_key, {})
            
            display_label = self.get_formatted_label(element_key)

            element_item = QTableWidgetItem(display_label)
            element_item.setFlags(element_item.flags() & ~Qt.ItemIsEditable)
            self.parameters_table.setItem(row, 0, element_item)

            include_checkbox = QCheckBox()
            include_checkbox.setChecked(saved_element_params.get('include', True))
            self.parameters_table.setCellWidget(row, 1, include_checkbox)

            method_combo = NoWheelComboBox()
            method_combo.addItems(["Currie", "Formula_C", "Manual", "Compound Poisson LogNormal"])
            method_combo.setCurrentText(saved_element_params.get('method', "Compound Poisson LogNormal"))
            self.parameters_table.setCellWidget(row, 2, method_combo)

            manual_threshold_spinbox = NoWheelSpinBox()
            manual_threshold_spinbox.setRange(0.0, 999999.0)
            manual_threshold_spinbox.setDecimals(2)
            manual_threshold_spinbox.setValue(saved_element_params.get('manual_threshold', 10.0))
            manual_threshold_spinbox.setSingleStep(10.0)
            manual_threshold_spinbox.setEnabled(saved_element_params.get('method', "Compound Poisson LogNormal") == "Manual")
            self.parameters_table.setCellWidget(row, 3, manual_threshold_spinbox)

            smoothing_checkbox = QCheckBox()
            smoothing_checkbox.setChecked(saved_element_params.get('apply_smoothing', False))
            self.parameters_table.setCellWidget(row, 4, smoothing_checkbox)

            smooth_window = NoWheelSpinBox()
            smooth_window.setRange(3, 9)
            smooth_window.setValue(saved_element_params.get('smooth_window', 3))
            smooth_window.setSingleStep(2)
            self.parameters_table.setCellWidget(row, 5, smooth_window)

            iterations_spin = NoWheelSpinBox()
            iterations_spin.setRange(1, 10)
            iterations_spin.setValue(saved_element_params.get('iterations', 1))
            iterations_spin.setSingleStep(1)
            self.parameters_table.setCellWidget(row, 6, iterations_spin)

            min_continuous = NoWheelSpinBox()
            min_continuous.setRange(1, 5)
            min_continuous.setValue(saved_element_params.get('min_continuous', 1))
            min_continuous.setSingleStep(1)
            self.parameters_table.setCellWidget(row, 7, min_continuous)

            confidence_spin = NoWheelSpinBox()
            confidence_spin.setRange(0.00000001, 0.1)  
            confidence_spin.setDecimals(8)
            confidence_spin.setValue(saved_element_params.get('alpha', 0.000001))  
            confidence_spin.setSingleStep(0.000001)
            self.parameters_table.setCellWidget(row, 8, confidence_spin)
            
            iterative_checkbox = QCheckBox()
            iterative_checkbox.setChecked(saved_element_params.get('iterative', True))  
            iterative_checkbox.setToolTip("background calculation for more accurate thresholds")
            self.parameters_table.setCellWidget(row, 9, iterative_checkbox)
            
            window_size_container = QWidget()
            window_size_layout = QHBoxLayout(window_size_container)
            window_size_layout.setContentsMargins(2, 2, 2, 2)
            window_size_layout.setSpacing(2)
        
            window_size_checkbox = QCheckBox()
            window_size_checkbox.setChecked(saved_element_params.get('use_window_size', False))
            window_size_checkbox.setToolTip("Enable custom window size for background calculation")
            
            window_size_spinbox = NoWheelIntSpinBox()
            window_size_spinbox.setRange(500, 100000)
            window_size_spinbox.setValue(saved_element_params.get('window_size', 5000))
            window_size_spinbox.setSingleStep(100)
            window_size_spinbox.setEnabled(saved_element_params.get('use_window_size', False))
            
            if saved_element_params.get('use_window_size', False):
                window_size_container.setStyleSheet("QWidget { background-color: #E8F5E8; border-radius: 3px; }")
            else:
                window_size_container.setStyleSheet("QWidget { background-color: transparent; }")
            
            window_size_layout.addWidget(window_size_checkbox)
            window_size_layout.addWidget(window_size_spinbox)
            
            self.parameters_table.setCellWidget(row, 10, window_size_container)
            
            include_checkbox.stateChanged.connect(lambda state, r=row: self.on_parameter_changed(r))
            method_combo.currentTextChanged.connect(lambda text, r=row: self.on_parameter_changed(r))
            method_combo.currentTextChanged.connect(lambda text, r=row: self.toggle_manual_threshold_input(r, text))
            manual_threshold_spinbox.valueChanged.connect(lambda value, r=row: self.on_parameter_changed(r))
            smoothing_checkbox.stateChanged.connect(lambda state, r=row: self.on_parameter_changed(r))
            smooth_window.valueChanged.connect(lambda value, r=row: self.on_parameter_changed(r))
            iterations_spin.valueChanged.connect(lambda value, r=row: self.on_parameter_changed(r))
            min_continuous.valueChanged.connect(lambda value, r=row: self.on_parameter_changed(r))
            confidence_spin.valueChanged.connect(lambda value, r=row: self.on_parameter_changed(r))
            iterative_checkbox.stateChanged.connect(lambda state, r=row: self.on_parameter_changed(r))
            window_size_checkbox.stateChanged.connect(lambda state, r=row: self.toggle_window_size_parameters(r, state))
            window_size_spinbox.valueChanged.connect(lambda value, r=row: self.on_parameter_changed(r))

            smoothing_checkbox.stateChanged.connect(
                lambda state, row=row: self.toggle_smoothing_parameters(row, state))
            
        self._build_element_lookup_cache()
        
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
                current_sigma = 0.47
            
            for element, isotopes in self.selected_isotopes.items():
                for isotope in isotopes:
                    element_key = f"{element}-{isotope:.4f}"
                    
                    self.sample_parameters[sample_name][element_key] = {
                        'include': True,
                        'method': "Compound Poisson LogNormal",
                        'manual_threshold': 10.0,
                        'apply_smoothing': False,
                        'smooth_window': 3,
                        'iterations': 1,
                        'min_continuous': 1,
                        'alpha': 0.000001,
                        'integration_method': "Background",
                        'iterative': True, 
                        'max_iterations': 4,  
                        'sigma': current_sigma,  
                        'use_window_size': False,  
                        'window_size': 5000  
                    }
        else:
    
            if self.sample_parameters[sample_name]:
                first_element_key = next(iter(self.sample_parameters[sample_name]))
                stored_sigma = self.sample_parameters[sample_name][first_element_key].get('sigma', 0.47)
                if hasattr(self, 'sigma_spinbox'):
                    self.sigma_spinbox.valueChanged.disconnect()
                    self.sigma_spinbox.setValue(stored_sigma)
                    self.sigma_spinbox.valueChanged.connect(self.on_sigma_changed)
        
        self.update_parameters_table()   
        
    def save_current_parameters(self):
        """
        Save current detection parameters for active sample.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
        if not self.current_sample:
            return
                
        current_params = {}
        
        current_sigma = self.sigma_spinbox.value() if hasattr(self, 'sigma_spinbox') else 0.47
        
        for row in range(self.parameters_table.rowCount()):
            element_item = self.parameters_table.item(row, 0)
            if not element_item:
                continue

            display_label = element_item.text()
            
            for element, isotopes in self.selected_isotopes.items():
                for isotope in isotopes:
                    element_key = f"{element}-{isotope:.4f}"
                    if self.get_formatted_label(element_key) == display_label:
                        include_widget = self.parameters_table.cellWidget(row, 1)
                        method_widget = self.parameters_table.cellWidget(row, 2)
                        manual_threshold_widget = self.parameters_table.cellWidget(row, 3)
                        smoothing_widget = self.parameters_table.cellWidget(row, 4)
                        window_widget = self.parameters_table.cellWidget(row, 5)
                        iterations_widget = self.parameters_table.cellWidget(row, 6)
                        min_points_widget = self.parameters_table.cellWidget(row, 7)
                        confidence_widget = self.parameters_table.cellWidget(row, 8)
                        iterative_widget = self.parameters_table.cellWidget(row, 9)
                        window_size_container = self.parameters_table.cellWidget(row, 10)
                        
                        window_size_checkbox = window_size_container.findChild(QCheckBox)
                        window_size_spinbox = window_size_container.findChild(NoWheelIntSpinBox)
                        
                        current_params[element_key] = {
                            'include': include_widget.isChecked(),
                            'method': method_widget.currentText(),
                            'manual_threshold': manual_threshold_widget.value(),
                            'apply_smoothing': smoothing_widget.isChecked(),
                            'smooth_window': window_widget.value(),
                            'iterations': iterations_widget.value(),
                            'min_continuous': min_points_widget.value(),
                            'alpha': confidence_widget.value(),
                            'integration_method': 'Background',  
                            'iterative': iterative_widget.isChecked(),  
                            'max_iterations': 4, 
                            'sigma': current_sigma,
                            'use_window_size': window_size_checkbox.isChecked(),
                            'window_size': window_size_spinbox.value()
                        }

                        break

        self.sample_parameters[self.current_sample] = current_params

    def update_parameter_ranges(self, row, method):
        """
        Update parameter ranges based on detection method.
        
        Args:
            self: MainWindow instance
            row (int): Table row index
            method (str): Detection method name
            
        Returns:
            None
        """
        smooth_window_spin = self.parameters_table.cellWidget(row, 4)  
        iterations_s_spin = self.parameters_table.cellWidget(row, 5)    
        min_continuous_spin = self.parameters_table.cellWidget(row, 6)

        if method == "Compound Poisson Lognormal":
            smooth_window_spin.setRange(3, 9)
            smooth_window_spin.setValue(3)
            smooth_window_spin.setSuffix("")
            iterations_s_spin.setEnabled(True)
            min_continuous_spin.setEnabled(True)

    def get_element_parameters(self, row):
        """
        Get detection parameters from table row.
        
        Args:
            self: MainWindow instance
            row (int): Table row index
            
        Returns:
            dict: Dictionary of parameter values
        """
        window_size_container = self.parameters_table.cellWidget(row, 10)
        window_size_checkbox = window_size_container.findChild(QCheckBox)
        window_size_spinbox = window_size_container.findChild(NoWheelIntSpinBox)
        
        return {
            'element': self.parameters_table.item(row, 0).text(),
            'include': self.parameters_table.cellWidget(row, 1).isChecked(),
            'method': self.parameters_table.cellWidget(row, 2).currentText(),
            'manual_threshold': self.parameters_table.cellWidget(row, 3).value(),
            'apply_smoothing': self.parameters_table.cellWidget(row, 4).isChecked(),
            'smooth_window': self.parameters_table.cellWidget(row, 5).value(),
            'iterations': self.parameters_table.cellWidget(row, 6).value(),
            'min_continuous': self.parameters_table.cellWidget(row, 7).value(),
            'alpha': self.parameters_table.cellWidget(row, 8).value(),
            'iterative': self.parameters_table.cellWidget(row, 9).isChecked(),
            'use_window_size': window_size_checkbox.isChecked(),  
            'window_size': window_size_spinbox.value()        
        }    
        
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

    def toggle_smoothing_parameters(self, row, state):
        """
        Enable or disable smoothing parameters.
        
        Args:
            self: MainWindow instance
            row (int): Table row index
            state (int): Checkbox state
            
        Returns:
            None
        """
        smooth_window = self.parameters_table.cellWidget(row, 4)  
        iterations_s = self.parameters_table.cellWidget(row, 5)     
        
        smooth_window.setEnabled(state)
        iterations_s.setEnabled(state)
        
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
                    
                    isotope_key = self.find_closest_isotope(isotope)
                    if isotope_key is not None and isotope_key in self.data:
                        self.results_table.setRowCount(0)
                        
                        signal = self.data[isotope_key]
                        
                        params = self.get_element_parameters(row)
                        
                        if params['apply_smoothing']:
                            smoothed_signal = self.smooth_signal(
                                signal,
                                window_length=int(params['smooth_window']),
                                iterations=int(params['iterations'])
                            )
                        else:
                            smoothed_signal = signal.copy()
                        
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
                                smoothed_signal,
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
                    return
                
    def toggle_manual_threshold_input(self, row, method):
        """
        Enable or disable manual threshold input based on method.
        
        Args:
            self: MainWindow instance
            row (int): Table row index
            method (str): Detection method name
            
        Returns:
            None
        """
        manual_threshold_spinbox = self.parameters_table.cellWidget(row, 3)
        if manual_threshold_spinbox:
            manual_threshold_spinbox.setEnabled(method == "Manual")
            
            if method == "Manual":
                manual_threshold_spinbox.setStyleSheet("QDoubleSpinBox { background-color: #E8F5E8; }")
            else:
                manual_threshold_spinbox.setStyleSheet("")
                
    def toggle_window_size_parameters(self, row, state):
        """
        Enable or disable window size parameters.
        
        Args:
            self: MainWindow instance
            row (int): Table row index
            state (int): Checkbox state
            
        Returns:
            None
        """
        window_size_container = self.parameters_table.cellWidget(row, 10)
        if window_size_container:
            window_size_spinbox = window_size_container.findChild(NoWheelIntSpinBox)
            if window_size_spinbox:
                window_size_spinbox.setEnabled(state)
            if state:
                window_size_container.setStyleSheet("QWidget { background-color: #E8F5E8; border-radius: 3px; }")
            else:
                window_size_container.setStyleSheet("QWidget { background-color: transparent; }")
        
        self.on_parameter_changed(row)
        
    def open_batch_parameters_dialog(self):
        """
        Open dialog for batch editing element parameters.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
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
        """
        Update sigma value for all samples and elements.
        
        Args:
            self: MainWindow instance
            value (float): New sigma value
            
        Returns:
            None
        """
        for sample_name in self.sample_parameters:
            for element_key in self.sample_parameters[sample_name]:
                self.sample_parameters[sample_name][element_key]['sigma'] = value
                self.mark_element_changed(sample_name, element_key)
        
        self._global_sigma = value
        
        self.save_current_parameters()
        self.unsaved_changes = True
        total_elements = sum(len(params) for params in self.sample_parameters.values())
        total_samples = len(self.sample_parameters)
        self.status_label.setText(f"Updated sigma to {value:.3f} for {total_elements} elements across {total_samples} samples")

    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------peak detection and analysis--------------------------------------------
    #----------------------------------------------------------------------------------------------------------                     

    @log_user_action('CLICK', 'Clicked detect peaks button')
    def detect_particles(self):
        """
        Run particle detection.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None or detection results
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
                    
                    if existing_sigma is None:
                        self.sample_parameters[sample_name][element_key]['sigma'] = current_sigma
                    elif existing_sigma != current_sigma:
                        self.sample_parameters[sample_name][element_key]['sigma'] = current_sigma
                        self.mark_element_changed(sample_name, element_key)
        
        if hasattr(self.peak_detector, 'incremental_enabled') and self.peak_detector.incremental_enabled:
            return self.peak_detector.detect_particles_incremental(self)
        else:
            return self.peak_detector.detect_particles(self)
        
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
        
    def detect_peaks_with_poisson(self, signal, window_length=3, iterations=1, alpha=0.000001, 
            apply_smoothing=False, sample_name=None, element_key=None, method="Compound Poisson LogNormal",
            manual_threshold=10.0):
        """
        Detect peaks using Poisson-based methods.
        
        Args:
            self: MainWindow instance
            signal (ndarray): Signal data array
            window_length (int): Smoothing window length
            iterations (int): Smoothing iterations
            alpha (float): Significance level
            apply_smoothing (bool): Whether to apply smoothing
            sample_name (str, optional): Sample name
            element_key (str, optional): Element identifier
            method (str): Detection method name
            manual_threshold (float): Manual threshold value
            
        Returns:
            Detection results
        """
        return self.peak_detector.detect_peaks_with_poisson(
            signal, window_length, iterations, alpha, apply_smoothing, 
            sample_name, element_key, method, manual_threshold, 
            self.element_thresholds, self.current_sample
        )

    def find_particles(self, time, smoothed_signal, raw_signal, lambda_bkgd, threshold, min_width=3, 
                min_continuous_points=1, apply_smoothing=False, integration_method="Mid-point"):
        """
        Find individual particles in signal.
        
        Args:
            self: MainWindow instance
            time (ndarray): Time array
            smoothed_signal (ndarray): Smoothed signal array
            raw_signal (ndarray): Raw signal array
            lambda_bkgd (float): Background level
            threshold (float): Detection threshold
            min_width (int): Minimum particle width
            min_continuous_points (int): Minimum continuous points
            apply_smoothing (bool): Whether smoothing was applied
            integration_method (str): Integration method name
            
        Returns:
            List of particle dictionaries
        """
        return self.peak_detector.find_particles(
            time, smoothed_signal, raw_signal, lambda_bkgd, threshold, 
            min_width, min_continuous_points, apply_smoothing, integration_method
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

    def smooth_signal(self, signal, window_length=3, iterations=1):
        """
        Smooth signal using specified parameters.
        
        Args:
            self: MainWindow instance
            signal (ndarray): Signal array to smooth
            window_length (int): Smoothing window length
            iterations (int): Number of smoothing iterations
            
        Returns:
            ndarray: Smoothed signal array
        """
        return self.peak_detector.smooth_signal(signal, window_length, iterations)
    
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
            
            for col, item in enumerate(items):
                if col > 0:
                    if snr <= 1.1:
                        item.setBackground(QBrush(QColor(255, 200, 200))) 
                    elif snr <= 1.2:
                        item.setBackground(QBrush(QColor(255, 220, 200))) 
                    elif snr <= 1.5:
                        item.setBackground(QBrush(QColor(255, 255, 200))) 
                    else:
                        item.setBackground(QBrush(QColor(200, 255, 200))) 
                        
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
        
        particles_per_ml = 0.00000
        if hasattr(self, 'average_transport_rate') and self.average_transport_rate > 0 and self.time_array is not None:
            total_time = self.time_array[-1] - self.time_array[0]
            volume_ml = (self.average_transport_rate * total_time) / 1000
            particles_per_ml = particle_count / volume_ml if volume_ml > 0 else 0.00000
        
        total_particles_all_elements = 0
        if hasattr(self, 'detected_peaks') and self.detected_peaks:
            for (elem, iso), particles in self.detected_peaks.items():
                total_particles_all_elements += len([p for p in particles if p is not None])
        
        percentage_of_all = (particle_count / total_particles_all_elements * 100) if total_particles_all_elements > 0 else 0.00000
        
        summary_html = f"""
        <style>
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .no-particles {{ background-color: #fff3cd; }}
            .warning {{ background-color: #ffeb3b; }}
            .info {{ background-color: #e3f2fd; }}
        </style>
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
        
    #----------------------------------------------------------------------------------------------------------    
    #------------------------------------visualization--------------------------------------------
    #----------------------------------------------------------------------------------------------------------                     
   
    def plot_results(self, mass, signal, smoothed_signal, particles, lambda_bkgd, threshold, preserve_view_range=None):
        """
        Plot detection results with peaks and thresholds.
        
        Args:
            self: MainWindow instance
            mass (str): Element mass identifier
            signal (ndarray): Raw signal array
            smoothed_signal (ndarray): Smoothed signal array
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
            'smoothed_signal': pg.mkPen(color=(34, 139, 34), width=1),
            'background': pg.mkPen(color=(128, 128, 128), style=Qt.DashLine, width=1),
            'threshold': pg.mkPen(color=(220, 20, 60), style=Qt.DashLine, width=1),
            'peaks': {'symbol': 'o', 'size': 18, 'brush': 'r', 'pen': 'match'}, 

        }
        
        time_array = self.time_array
        background_line = np.full_like(time_array, lambda_bkgd)
        threshold_line = np.full_like(time_array, threshold)
        
        smoothing_applied = not np.array_equal(signal, smoothed_signal)
        
        plot_data = [
            (time_array, signal, STYLES['raw_signal'], f'Mass {display_label}'),
            (time_array, background_line, STYLES['background'], 'Background Level'),
            (time_array, threshold_line, STYLES['threshold'], 'Detection Threshold')
        ]
        
        if smoothing_applied:
            plot_data.insert(1, (time_array, smoothed_signal, STYLES['smoothed_signal'], 'Smoothed Signal'))
        
        for x, y, pen, name in plot_data:
            self.plot_widget.plot(x=x, y=y, pen=pen, name=name)
        
        if particles:
            peak_times = []
            peak_heights = []
            peak_snr = []
            
            for p in particles:
                if p is not None:
                    peak_idx = np.argmax(signal[p['left_idx']:p['right_idx']+1])
                    peak_times.append(time_array[p['left_idx'] + peak_idx])
                    peak_height = p['max_height']
                    peak_heights.append(peak_height)
                    peak_snr.append(peak_height / threshold if threshold > 0 else 0)
            
            scatter = pg.ScatterPlotItem(
                x=peak_times,
                y=peak_heights,
                symbol=STYLES['peaks']['symbol'],
                brush=[pg.mkBrush(self.get_snr_color(snr)) for snr in peak_snr],
                pen=[pg.mkPen(self.get_snr_color(snr), width=1) for snr in peak_snr], 
                name='Detected Peaks'
            )
            self.plot_widget.addItem(scatter)
        
        self.plot_widget.setBackground('w')
        
        legend = self.plot_widget.addLegend(
            offset=(10, 10),
            brush=pg.mkBrush(255, 255, 255, 150),
            pen=pg.mkPen(200, 200, 200, 100)
        )
        legend.setParentItem(self.plot_widget.graphicsItem())
        
        for sample, label in legend.items:
            label.setText(label.text, size='20pt')
        self.plot_widget.setLabel('left', 'Counts')
        self.plot_widget.setLabel('bottom', 'Time (s)')
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
        
        legend = self.plot_widget.addLegend(
            offset=(15, 120),
            brush=pg.mkBrush(255, 255, 255, 180),
            pen=pg.mkPen(150, 150, 150, 100)
        )
        
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
                                        
                                        snr = particle.get('SNR', peak_y / particle.get('threshold', 1))
                                        hover_info = (
                                            f"Element: {display_label}\n"
                                            f"Peak Height: {peak_y:.0f} counts\n"
                                            f"SNR: {snr:.2f}\n"
                                            f"Background: {background_val:.1f} counts\n"
                                            f"Threshold: {threshold_val:.1f} counts"
                                        )
                                        peak_data['info'].append(hover_info)
                                
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

        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', 'Counts', 
                                style={'color': '#333', 'font-size': '12px'})
        self.plot_widget.setLabel('bottom', 'Time (s)', 
                                style={'color': '#333', 'font-size': '12px'})
        
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
                    
    def show_signal_selector(self):
        """
        Display signal selector dialog for multi-signal view.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
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
        
        display_text += """
        <style>
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            .warning { background-color: #ffeb3b; }
        </style>
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
    def load_project(self):
        """
        Load project from file.
        
        Args:
            self: MainWindow instance
            
        Returns:
            bool: True if load was successful
        """
        self.user_action_logger.log_menu_action('File', 'Load Project')
        result = self.project_manager.load_project()
        
        self.user_action_logger.log_file_operation(
            'Project Load',
            'project file',
            success=result
        )
        return result
    
    def export_data(self):
        """
        Export all data using external export utility.
        
        Args:
            self: MainWindow instance
            
        Returns:
            None
        """
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
        
        app = QApplication.instance()
        if hasattr(app, 'main_windows'):
            try:
                app.main_windows.remove(self)
            except ValueError:
                pass
        
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
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.showMaximized()
    sys.exit(app.exec())