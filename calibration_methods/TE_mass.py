import json
import csv
from pathlib import Path
import numpy as np
from scipy import stats
import pyqtgraph as pg
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget, QGridLayout,
                               QLabel, QComboBox, QMessageBox, QFileDialog, QTabWidget,
                               QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
                               QDoubleSpinBox, QGroupBox, QFormLayout, QDialog, QMenu,
                               QListView, QAbstractItemView, QTreeView, QSpinBox, QApplication, QScrollArea, QListWidget,QRadioButton,
                               QMainWindow, QFrame, QProgressBar, QSplitter, QProgressDialog, QStyledItemDelegate, QLineEdit)
from PySide6.QtGui import QFont, QColor, QIcon, QDoubleValidator
from PySide6.QtCore import Qt, Signal
import data_loading.vitesse_loading
from widget.periodic_table_widget import PeriodicTableWidget
from widget.numeric_table import NumericTableWidgetItem
from widget.custom_plot_widget import EnhancedPlotWidget
from processing.peak_detection import PeakDetection
import data_loading.tofwerk_loading


class NumericDelegate(QStyledItemDelegate):
    """Custom delegate for numeric input in table cells"""
    
    def createEditor(self, parent, option, index):
        """
        Create a line edit widget with numeric validation for table cell editing.
        
        Args:
            parent: Parent widget for the editor
            option: Style option for the item
            index: Model index of the item being edited
            
        Returns:
            QLineEdit: Line edit widget configured with double validator
        """
        editor = QLineEdit(parent)
        editor.setValidator(QDoubleValidator())
        return editor

class PeriodicTableDialog(QDialog):
    element_selected = Signal(dict)
    
    def __init__(self, parent=None):
        """
        Initialize the Periodic Table Dialog for element selection.
        
        Args:
            parent: Parent widget for this dialog
        """
        super().__init__(parent)
        self.setWindowTitle("Select Element")
        self.setModal(True)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QLabel {
                color: #495057;
                font-weight: bold;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0069d9;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        self.status_label = QLabel("Loading data...")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.periodic_table = PeriodicTableWidget()
        self.periodic_table.selection_confirmed.connect(self.on_selection_confirmed)
        self.periodic_table.isotope_selected.connect(self.on_isotope_selected)
        layout.addWidget(self.periodic_table)
        
        instruction_frame = QFrame()
        instruction_frame.setFrameShape(QFrame.StyledPanel)
        instruction_frame.setStyleSheet("background-color: #e9ecef; border-radius: 4px; padding: 10px;")
        instruction_layout = QVBoxLayout(instruction_frame)
        
        instruction_title = QLabel("Instructions")
        instruction_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        instruction_layout.addWidget(instruction_title)
        
        instruction_text = QLabel(
            "• Click an element to select it\n"
            "• Right-click for isotope selection\n"
            "• Available masses are highlighted\n"
            "• Click 'Confirm Selection' when ready"
        )
        instruction_layout.addWidget(instruction_text)
        
        layout.addWidget(instruction_frame)
        
        self.resize(800, 600)
        
        self.periodic_table.setEnabled(False)
    
    def on_selection_confirmed(self, selected_data):
        """
        Handle when user confirms their element selection.
        
        Args:
            selected_data: Dictionary mapping element symbols to selected isotope masses
        """
        if selected_data:
            element_symbol = next(iter(selected_data.keys()))
            isotope_masses = selected_data[element_symbol]
            
            element = next((e for e in self.periodic_table.get_elements() 
                          if e['symbol'] == element_symbol), None)
            
            if element and isotope_masses:
                element['selected_isotope'] = isotope_masses[0]
                self.element_selected.emit(element)
                self.accept()
    
    def on_isotope_selected(self, symbol, mass, abundance):
        """
        Track individual isotope selections.
        
        Args:
            symbol: Element symbol
            mass: Isotope mass
            abundance: Natural abundance percentage
        """
        pass
    
    def update_available_masses(self, masses):
        """
        Update the periodic table with available masses.
        
        Args:
            masses: List of available mass values from loaded data
        """
        self.periodic_table.update_available_masses(masses)
        self.periodic_table.setEnabled(True)
        self.status_label.setText("Ready - Select an element")

class MassMethodWidget(QMainWindow):
    calibration_completed = Signal(str, float)
    
    def __init__(self, parent=None):
        """
        Initialize the Mass Method Widget for mass-based calibration.
        
        Args:
            parent: Parent widget for this window
        """
        super().__init__(parent)
        
        self.peak_detector = PeakDetection()
        
        self.particle_folder_paths = []
        self.folder_path = ""
        self.default_diameter = 100
        self.default_density = 0
        self.current_data = {}
        self.detected_particles = {}
        self.detection_params = {}
        self.folder_avg_counts = {}
        self.folder_diameters = {}
        self.folder_densities = {}
        self.calibration_folder_paths = []
        
        self.folder_data = {}  
        self.detection_results = {} 
        self.calibration_data_cache = {}
        self.current_calibration_view = "raw"
        self.sample_name_to_folder = {} 
        self.selected_element = None
        self.all_masses = None
        
        self.current_highlighted_particle = None
        
        self.default_button_style = ""
        self.modified_button_style = """
            QPushButton {
                background-color: #ffc107;
                color: #212529;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """
        
        self.initUI()
    
    def initUI(self):
        """
        Initialize and configure the user interface.
        
        Sets up stylesheets, creates tab widget with five tabs for data selection,
        detection, calibration, analysis, and results.
        """
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #f8f9fa;
                color: #212529;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0069d9;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
            }
            QTableWidget {
                border: 1px solid #dee2e6;
                background-color: white;
                alternate-background-color: #f8f9fa;
            }
            QHeaderView::section {
                background-color: #e9ecef;
                padding: 6px;
                border: none;
                border-right: 1px solid #dee2e6;
                border-bottom: 1px solid #dee2e6;
            }
            QLabel {
                color: #495057;
            }
            QTabWidget::pane {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                background-color: white;
            }
            QTabBar::tab {
                border: 1px solid #dee2e6;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #ced4da;
            }
            QListWidget {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                background-color: white;
                alternate-background-color: #f8f9fa;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        
        self.create_data_tab()
        self.create_detection_tab()
        self.create_calibration_tab()
        self.create_analysis_tab()
        self.create_results_tab()
        
        main_layout.addWidget(self.tab_widget)
        
        self.setWindowTitle("Mass Method Calibration")
        self.setMinimumSize(1100, 800)
        
    def create_data_tab(self):
        """
        Create the Data Selection tab.
        
        Sets up folder selection controls, folder list display, element selection button,
        and periodic table dialog within a scrollable area.
        """
        data_tab = QWidget()
        layout = QVBoxLayout(data_tab)
        layout.setSpacing(15)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        container = QWidget()
        scroll_layout = QVBoxLayout(container)
        scroll_layout.setSpacing(15)
        scroll.setWidget(container)
        
        folder_group = QGroupBox("1. Particle Data Folders")
        folder_layout = QVBoxLayout(folder_group)
        
        instruction_label = QLabel(
            "Select multiple folders containing particle analysis data. Each folder represents one sample."
        )
        instruction_label.setWordWrap(True)
        instruction_label.setStyleSheet("color: #6c757d; font-style: italic;")
        folder_layout.addWidget(instruction_label)
        
        folder_button = QPushButton("Select Particle Folders")
        folder_button.setIcon(QIcon.fromTheme("folder-open"))
        folder_button.clicked.connect(self.select_particle_folders)
        folder_button.setMaximumWidth(200)
        folder_layout.addWidget(folder_button)
        
        self.folder_list = QListWidget()
        self.folder_list.setAlternatingRowColors(True)
        self.folder_list.itemClicked.connect(self.on_folder_selected)
        self.folder_list.setMinimumHeight(150)
        folder_layout.addWidget(QLabel("Selected Folders:"))
        folder_layout.addWidget(self.folder_list)
        
        self.folder_status_label = QLabel("No folders selected")
        self.folder_status_label.setStyleSheet("font-weight: bold; color: #6c757d;")
        folder_layout.addWidget(self.folder_status_label)
        
        scroll_layout.addWidget(folder_group)
        
        element_group = QGroupBox("2. Element Selection")
        element_layout = QVBoxLayout(element_group)
        
        self.element_selection_label = QLabel("Selected Element: None")
        self.element_selection_label.setStyleSheet("font-weight: bold; color: #6c757d;")
        element_layout.addWidget(self.element_selection_label)
        
        self.element_button = QPushButton("Open Periodic Table")
        self.element_button.clicked.connect(self.show_periodic_table)
        self.element_button.setMaximumWidth(200)
        self.element_button.setEnabled(False)
        element_layout.addWidget(self.element_button)
        
        help_label = QLabel(
            "Select an element from the periodic table to analyze. "
            "Right-click on an element to select specific isotopes."
        )
        help_label.setStyleSheet("color: #6c757d; font-style: italic;")
        help_label.setWordWrap(True)
        element_layout.addWidget(help_label)
        
        scroll_layout.addWidget(element_group)
        
        scroll_layout.addStretch()
        
        layout.addWidget(scroll)
        
        self.tab_widget.addTab(data_tab, "Data Selection")
        
        self.periodic_table_dialog = PeriodicTableDialog(self)
        self.periodic_table_dialog.element_selected.connect(self.on_element_selected)
    
    def create_detection_tab(self):
        """
        Create enhanced detection tab with individual sample parameters.
        
        Sets up detection configuration table, sample visualization plot, results table,
        and file information display within a scrollable layout.
        """
        detection_tab = QWidget()
        layout = QVBoxLayout(detection_tab)
        layout.setSpacing(15)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        container = QWidget()
        scroll_layout = QVBoxLayout(container)
        scroll_layout.setSpacing(15)
        scroll.setWidget(container)
        
        detection_group = QGroupBox("Detection Configuration")
        detection_layout = QVBoxLayout(detection_group)
        detection_layout.setSpacing(10)
        
        instruction_label = QLabel(
            "Configure detection parameters for each sample. Click anywhere on a sample row to preview its signal. "
            "Parameters can be set individually or applied to all samples at once."
        )
        instruction_label.setWordWrap(True)
        instruction_label.setStyleSheet("color: #6c757d; font-style: italic;")
        detection_layout.addWidget(instruction_label)
        
        global_controls_layout = QHBoxLayout()
        
        global_method_combo = QComboBox()
        global_method_combo.addItems(["Currie", "Formula_C", "Manual","Compound Poisson LogNormal"])
        global_method_combo.setCurrentText("Compound Poisson LogNormal")
        
        apply_global_button = QPushButton("Apply to All Samples")
        apply_global_button.clicked.connect(lambda: self.apply_global_detection_params(global_method_combo.currentText()))
        
        global_controls_layout.addWidget(QLabel("Global Method:"))
        global_controls_layout.addWidget(global_method_combo)
        global_controls_layout.addWidget(apply_global_button)
        global_controls_layout.addStretch()
        
        detection_layout.addLayout(global_controls_layout)
        
        self.detection_params_table = QTableWidget()
        self.detection_params_table.setColumnCount(11)
        headers = ['Sample Name', 'Element', 'Detection Method', 'Manual Threshold', 'Apply Smoothing', 
                  'Window Length', 'Smoothing Iterations', 'Min Points', 'Alpha', "iteration", "Window size"]
        self.detection_params_table.setHorizontalHeaderLabels(headers)
        
        column_widths = [150, 120, 130, 120, 100, 100, 120, 100, 120]
        for i, width in enumerate(column_widths):
            self.detection_params_table.setColumnWidth(i, width)
        
        self.detection_params_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.detection_params_table.setAlternatingRowColors(True)
        self.detection_params_table.setMinimumHeight(150)
        
        self.detection_params_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.detection_params_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.detection_params_table.itemSelectionChanged.connect(self.on_detection_params_selection_changed)
        
        detection_layout.addWidget(self.detection_params_table)
        
        self.detect_button = QPushButton("Detect Particles for All Samples")
        self.detect_button.clicked.connect(self.detect_particles_all_samples)
        self.detect_button.setMinimumHeight(40)
        self.detect_button.setEnabled(False)
        
        detection_layout.addWidget(self.detect_button)
        
        scroll_layout.addWidget(detection_group)
        
        sample_selection_group = QGroupBox("Sample Visualization")
        sample_selection_layout = QVBoxLayout(sample_selection_group)
        
        sample_controls_layout = QHBoxLayout()
        
        self.sample_combo = QComboBox()
        self.sample_combo.currentTextChanged.connect(self.update_sample_visualization)
        
        self.visualization_status_label = QLabel("Click on any sample row above to preview its signal")
        self.visualization_status_label.setStyleSheet("color: #6c757d; font-style: italic;")
        
        sample_controls_layout.addWidget(QLabel("Current Sample:"))
        sample_controls_layout.addWidget(self.sample_combo)
        sample_controls_layout.addWidget(self.visualization_status_label)
        sample_controls_layout.addStretch()
        
        sample_selection_layout.addLayout(sample_controls_layout)
        
        self.plot_widget = EnhancedPlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setMinimumHeight(300)
        sample_selection_layout.addWidget(self.plot_widget)
        
        scroll_layout.addWidget(sample_selection_group)
        
        results_group = QGroupBox("Detection Results Summary")
        results_layout = QVBoxLayout(results_group)
        results_layout.setSpacing(10)
        
        results_instruction = QLabel(
            "Click on a particle row to zoom in on that specific particle in the plot above."
        )
        results_instruction.setWordWrap(True)
        results_instruction.setStyleSheet("color: #6c757d; font-style: italic;")
        results_layout.addWidget(results_instruction)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            'Sample Name', 'Peak Start (s)', 'Peak End (s)', 'Total Counts', 'Peak Height (counts)'
        ])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        self.results_table.itemSelectionChanged.connect(self.highlight_selected_particle)
        self.results_table.setMinimumHeight(200)
        
        results_layout.addWidget(self.results_table)
        
        export_button = QPushButton("Export Data to CSV")
        export_button.clicked.connect(self.export_to_csv)
        export_button.setMaximumWidth(200)
        results_layout.addWidget(export_button, alignment=Qt.AlignRight)
        
        scroll_layout.addWidget(results_group)
        
        info_group = QGroupBox("File Information")
        info_layout = QVBoxLayout(info_group)
        
        self.file_info_table = QTableWidget()
        self.file_info_table.setColumnCount(4)
        self.file_info_table.setHorizontalHeaderLabels([
            'File Name', 'Diameter (nm)', 'Density (g/cm³)', 'Avg Total Count'
        ])
        self.file_info_table.horizontalHeader().setStretchLastSection(True)
        self.file_info_table.setAlternatingRowColors(True)
        self.file_info_table.setMinimumHeight(150)
        info_layout.addWidget(self.file_info_table)
        
        scroll_layout.addWidget(info_group)
        
        scroll_layout.addStretch()
        
        layout.addWidget(scroll)
        
        self.tab_widget.addTab(detection_tab, "Particle Detection")
    
    def create_analysis_tab(self):
        """
        Create the Mass Analysis tab.
        
        Sets up regression plot widget and calculation button for particle mass analysis
        within a scrollable layout.
        """
        analysis_tab = QWidget()
        layout = QVBoxLayout(analysis_tab)
        layout.setSpacing(15)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        container = QWidget()
        scroll_layout = QVBoxLayout(container)
        scroll_layout.setSpacing(15)
        scroll.setWidget(container)
        
        regression_group = QGroupBox("1. Particle Mass Analysis")
        regression_layout = QVBoxLayout(regression_group)
        
        self.regression_plot = pg.PlotWidget()
        self.regression_plot.setBackground('w')
        self.regression_plot.setLabel('left', 'Average Counts')
        self.regression_plot.setLabel('bottom', 'Particle Mass (fg)')
        self.regression_plot.showGrid(x=True, y=True, alpha=0.3)
        self.regression_plot.setMinimumHeight(300)
        regression_layout.addWidget(self.regression_plot)
        
        self.calculate_button = QPushButton("Calculate Mass and Regression")
        self.calculate_button.clicked.connect(self.calculate_mass_and_regression)
        self.calculate_button.setMinimumHeight(40)
        regression_layout.addWidget(self.calculate_button)
        
        scroll_layout.addWidget(regression_group)
        
        scroll_layout.addStretch()
        
        layout.addWidget(scroll)
        
        self.tab_widget.addTab(analysis_tab, "Mass Analysis")
    
    def create_calibration_tab(self):
        """
        Create the enhanced Ionic Calibration tab with auto-fill and method selection.
        
        Sets up calibration folder selection, concentration table with auto-fill functionality,
        calibration method selection, and dual-view visualization (raw data and calibration plot).
        """
        calibration_tab = QWidget()
        layout = QVBoxLayout(calibration_tab)
        layout.setSpacing(15)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        container = QWidget()
        scroll_layout = QVBoxLayout(container)
        scroll_layout.setSpacing(15)
        scroll.setWidget(container)
        
        ionic_group = QGroupBox("1. Ionic Calibration Setup")
        ionic_layout = QVBoxLayout(ionic_group)
        
        folder_controls_layout = QHBoxLayout()
        folder_button = QPushButton("Select Calibration Folders")
        folder_button.clicked.connect(self.select_calibration_folders)
        folder_button.setMaximumWidth(250)
        folder_controls_layout.addWidget(folder_button)
        
        auto_fill_btn = QPushButton("Auto-Fill Concentrations")
        auto_fill_btn.clicked.connect(self.auto_fill_concentrations)
        auto_fill_btn.setToolTip("Attempt to auto-detect concentrations from sample names")
        auto_fill_btn.setMaximumWidth(200)
        folder_controls_layout.addWidget(auto_fill_btn)
        
        fill_minus_one_btn = QPushButton("Fill Selected with -1")
        fill_minus_one_btn.clicked.connect(self.set_selected_cells_to_minus_one)
        fill_minus_one_btn.setToolTip("Fill selected cells with -1 (exclude from calibration)")
        fill_minus_one_btn.setMaximumWidth(180)
        folder_controls_layout.addWidget(fill_minus_one_btn)
        
        folder_controls_layout.addStretch()
        ionic_layout.addLayout(folder_controls_layout)
        
        instructions = QLabel(
            "Select folders containing ionic standard solutions of different concentrations. "
            "Enter concentrations or use auto-fill. Set to -1 to exclude from calibration."
        )
        instructions.setStyleSheet("color: #6c757d; font-style: italic;")
        instructions.setWordWrap(True)
        ionic_layout.addWidget(instructions)
        
        self.concentration_table = QTableWidget()
        self.concentration_table.setColumnCount(3)
        self.concentration_table.setHorizontalHeaderLabels(["Sample", "Concentration [ppb]", "Unit"])
        self.concentration_table.setMinimumHeight(250)
        self.concentration_table.setAlternatingRowColors(True)
        
        self.concentration_table.setColumnWidth(0, 200)
        self.concentration_table.setColumnWidth(1, 150)
        self.concentration_table.setColumnWidth(2, 100)
        self.concentration_table.horizontalHeader().setStretchLastSection(True)
        
        self.concentration_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.concentration_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.concentration_table.customContextMenuRequested.connect(self.show_concentration_context_menu)
        
        self.concentration_table.cellClicked.connect(self.on_concentration_table_clicked)
        
        ionic_layout.addWidget(self.concentration_table)
        
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Calibration Method:"))
        self.calibration_method_combo = QComboBox()
        self.calibration_method_combo.addItems(['Force through zero', 'Simple linear', 'Weighted'])
        self.calibration_method_combo.setCurrentText('Force through zero')
        method_layout.addWidget(self.calibration_method_combo)
        method_layout.addStretch()
        ionic_layout.addLayout(method_layout)
        
        calibrate_button = QPushButton("Calculate Calibration")
        calibrate_button.clicked.connect(self.calculate_calibration)
        calibrate_button.setMinimumHeight(40)
        ionic_layout.addWidget(calibrate_button)
        
        scroll_layout.addWidget(ionic_group)
        
        visualization_group = QGroupBox("2. Sample Data Visualization")
        visualization_layout = QVBoxLayout(visualization_group)

        sample_controls_layout = QHBoxLayout()
        sample_controls_layout.addWidget(QLabel("Selected Sample:"))
        self.calibration_sample_label = QLabel("Click on any sample row above to view its data")
        self.calibration_sample_label.setStyleSheet("color: #6c757d; font-style: italic;")
        sample_controls_layout.addWidget(self.calibration_sample_label)

        sample_controls_layout.addStretch()

        self.view_toggle_button = QPushButton("📈 Show Calibration")
        self.view_toggle_button.clicked.connect(self.toggle_calibration_view)
        self.view_toggle_button.setMaximumWidth(150)
        self.view_toggle_button.setEnabled(False)
        sample_controls_layout.addWidget(self.view_toggle_button)

        visualization_layout.addLayout(sample_controls_layout)

        self.calibration_raw_plot = pg.PlotWidget()
        self.calibration_raw_plot.setBackground('w')
        self.calibration_raw_plot.setLabel('left', 'Counts')
        self.calibration_raw_plot.setLabel('bottom', 'Time (s)')
        self.calibration_raw_plot.showGrid(x=True, y=True, alpha=0.3)
        self.calibration_raw_plot.setMinimumHeight(250)
        visualization_layout.addWidget(self.calibration_raw_plot)

        scroll_layout.addWidget(visualization_group)
                        
        scroll_layout.addStretch()
        
        layout.addWidget(scroll)
        
        self.tab_widget.addTab(calibration_tab, "Ionic Calibration")
        
        self.calibration_folder_paths = []
        self.calibration_results = {}
        self.ignore_concentration_item_changed = False
        
    def create_results_tab(self):
        """
        Create the Transport Rate Results tab.
        
        Sets up transport rate calculation table, diameter distribution plot,
        and related controls within a scrollable layout.
        """
        results_tab = QWidget()
        layout = QVBoxLayout(results_tab)
        layout.setSpacing(15)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        container = QWidget()
        scroll_layout = QVBoxLayout(container)
        scroll_layout.setSpacing(15)
        scroll.setWidget(container)
        
        transport_rate_group = QGroupBox("1. Calibrated Transport Rate")
        transport_rate_layout = QVBoxLayout(transport_rate_group)
        
        self.transport_rate_table = QTableWidget()
        self.transport_rate_table.setColumnCount(4)
        self.transport_rate_table.setHorizontalHeaderLabels([
            "Particle Calibration Slope",
            "Ionic Calibration Slope",
            "Calibrated Transport Rate (μL/s)",
            "R² (Ionic Calibration)"
        ])
        self.transport_rate_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.transport_rate_table.setAlternatingRowColors(True)
        transport_rate_layout.addWidget(self.transport_rate_table)
        
        calculate_transport_button = QPushButton("Calculate Transport Rate")
        calculate_transport_button.clicked.connect(self.calculate_transport_rate)
        calculate_transport_button.setMinimumHeight(40)
        transport_rate_layout.addWidget(calculate_transport_button)
        
        scroll_layout.addWidget(transport_rate_group)
        
        diameter_group = QGroupBox("2. Particle Size Distribution")
        diameter_layout = QVBoxLayout(diameter_group)
        
        self.diameter_distribution_plot = pg.PlotWidget()
        self.diameter_distribution_plot.setBackground('w')
        self.diameter_distribution_plot.setLabel('left', 'Frequency')
        self.diameter_distribution_plot.setLabel('bottom', 'Diameter (nm)')
        self.diameter_distribution_plot.showGrid(x=True, y=True, alpha=0.3)
        self.diameter_distribution_plot.setMinimumHeight(300)
        diameter_layout.addWidget(self.diameter_distribution_plot)
        
        scroll_layout.addWidget(diameter_group)
        
        scroll_layout.addStretch()
        
        layout.addWidget(scroll)
        
        self.tab_widget.addTab(results_tab, "Results")

    def show_periodic_table(self):
        """
        Show the periodic table dialog for element selection.
        
        Updates available masses in the dialog if they have changed since last display.
        """
        if (self.all_masses and 
            (not hasattr(self.periodic_table_dialog, 'all_masses') or 
            self.periodic_table_dialog.all_masses != self.all_masses)):
            
            self.periodic_table_dialog.update_available_masses(self.all_masses)
        
        self.periodic_table_dialog.show()
        self.periodic_table_dialog.raise_()
    
    def update_folder_list(self):
        """
        Update the folder list widget with selected folders - supports folders, CSV, and TOFWERK.
        
        Populates the list with sample names and status, updates the status label
        with count of valid samples, with appropriate icons for different data sources.
        """
        self.folder_list.clear()
        valid_count = 0
        csv_count = 0
        tofwerk_count = 0
        folder_count = 0
        
        for folder in self.particle_folder_paths:
            sample_name = self.folder_data[folder].get('sample_name', Path(folder).name)
            status = self.folder_data[folder].get('status', 'Unknown')
            
            if str(folder).lower().endswith(('.csv', '.txt', '.xls', '.xlsx', '.xlsm', '.xlsb')):
                icon = "📄"
                if status == 'Loaded':
                    csv_count += 1
            elif self.folder_data[folder].get('is_tofwerk'):
                icon = "⚗️"
                if status == 'Loaded':
                    tofwerk_count += 1
            else:
                icon = "📁"
                if status == 'Loaded':
                    folder_count += 1
                
            if status == 'Loaded':
                valid_count += 1
                    
            self.folder_list.addItem(f"{icon} {sample_name} - {status}")
        
        status_parts = []
        if folder_count > 0:
            status_parts.append(f"{folder_count} folders")
        if csv_count > 0:
            status_parts.append(f"{csv_count} CSV files")
        if tofwerk_count > 0:
            status_parts.append(f"{tofwerk_count} TOFWERK files")
        
        status_text = f"{valid_count} valid samples loaded"
        if status_parts:
            status_text += f" ({', '.join(status_parts)})"
        
        self.folder_status_label.setText(status_text)
        self.folder_status_label.setStyleSheet("font-weight: bold; color: #28a745;")

    def enable_ui_elements(self):
        """
        Enable UI elements after successful folder loading.
        
        Enables element selection button and populates sample combo box with
        loaded sample data.
        """
        self.element_button.setEnabled(True)
        
        self.sample_combo.clear()
        for folder_path in self.particle_folder_paths:
            if self.folder_data[folder_path].get('status') == 'Loaded':
                sample_name = self.folder_data[folder_path].get('sample_name', Path(folder_path).name)
                self.sample_combo.addItem(sample_name, folder_path)

    def on_element_selected(self, element):
        """
        Handle element selection from periodic table.
        
        Args:
            element: Dictionary containing element data with isotope information
            
        Stores selected element, updates default density, loads element data for all samples,
        and updates detection parameters table.
        """
        self.selected_element = element
        
        if 'density' in element and element['density'] > 0:
            self.default_density = element['density']
        
        if 'selected_isotope' in element:
            selected_mass = element['selected_isotope']
            isotope_data = next((iso for iso in element['isotopes'] 
                            if isinstance(iso, dict) and iso['mass'] == selected_mass), None)
            abundance = isotope_data.get('abundance', 0) if isotope_data else 0
            
            self.element_selection_label.setText(
                f"Selected Element: {element['symbol']} - {int(round(selected_mass))}{element['symbol']} ({abundance:.1f}%)"
            )
            self.element_selection_label.setStyleSheet("font-weight: bold; color: #28a745;")
            
            self.load_element_data_for_all_samples()
            self.update_detection_parameters_table()
        else:
            if element['isotopes']:
                if isinstance(element['isotopes'][0], dict):
                    self.selected_element['selected_isotope'] = element['isotopes'][0]['mass']
                else:
                    self.selected_element['selected_isotope'] = element['isotopes'][0]
                self.load_element_data_for_all_samples()

    def load_element_data_for_all_samples(self):
        """
        Load element data for all samples - supports NU folders, CSV files, and TOFWERK files.
        
        Extracts isotope signal data for the selected element from all valid sample folders,
        calculates time arrays, and stores processed data for detection.
        """
        if not self.selected_element or 'selected_isotope' not in self.selected_element:
            return
            
        selected_mass = self.selected_element['selected_isotope']
        
        progress = QProgressDialog("Loading element data for all samples...", "Cancel", 
                                0, len(self.particle_folder_paths), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(500)
        
        for i, folder_path in enumerate(self.particle_folder_paths):
            progress.setValue(i)
            sample_name = self.folder_data[folder_path].get('sample_name', Path(folder_path).name)
            progress.setLabelText(f"Processing {sample_name}...")
            QApplication.processEvents()
            
            if progress.wasCanceled():
                break
                
            if self.folder_data[folder_path].get('status') != 'Loaded':
                continue
                
            try:
                if self.folder_data[folder_path].get('is_tofwerk'):
                    try:
                        h5_path = Path(folder_path)
                        
                        data, info, dwell_time = data_loading.tofwerk_loading.read_tofwerk_file(h5_path)
                        
                        if 'mass' in info.dtype.names:
                            masses = info['mass']
                        else:
                            masses = np.array([float(label.decode() if isinstance(label, bytes) else label) 
                                            for label in info['label']])
                        mass_index = np.argmin(np.abs(masses - selected_mass))
                        closest_mass = masses[mass_index]
                        
                        if abs(closest_mass - selected_mass) > 1.0:
                            raise ValueError(f"No suitable isotope found for mass {selected_mass:.4f}. Closest available: {closest_mass:.4f}")
                        
                        if hasattr(data.dtype, 'names') and data.dtype.names:
                            field_name = data.dtype.names[mass_index]
                            isotope_signal = data[field_name]
                        else:
                            isotope_signal = data[:, mass_index]
                        
                        time_array = np.arange(len(isotope_signal)) * dwell_time
                        
                        self.folder_data[folder_path].update({
                            'full_masses': masses,
                            'isotope_signal': isotope_signal,
                            'time_array': time_array,
                            'dwell_time': dwell_time,
                            'mass_index': mass_index,
                            'total_acquisition_time': time_array[-1] + dwell_time if len(time_array) > 0 else 0
                        })
                        
                    except Exception as load_error:
                        raise ValueError(f"Error loading TOFWERK data: {str(load_error)}")
                
                else:
                    masses, signals, run_info = data_loading.vitesse_loading.read_nu_directory(
                        path=folder_path,
                        autoblank=True,
                        raw=False
                    )
                    
                    mass_index = np.argmin(np.abs(masses - selected_mass))
                    
                    isotope_signal = signals[:, mass_index]
                    
                    acqtime = run_info["SegmentInfo"][0]["AcquisitionPeriodNs"] * 1e-9
                    accumulations = run_info["NumAccumulations1"] * run_info["NumAccumulations2"]
                    dwell_time = acqtime * accumulations
                    time_array = np.arange(len(isotope_signal)) * dwell_time
                    
                    self.folder_data[folder_path].update({
                        'full_masses': masses,
                        'full_signals': signals,
                        'isotope_signal': isotope_signal,
                        'time_array': time_array,
                        'dwell_time': dwell_time,
                        'mass_index': mass_index,
                        'total_acquisition_time': time_array[-1] + dwell_time if len(time_array) > 0 else 0
                    })
                    
            except Exception as e:
                QMessageBox.warning(self, "Data Loading Error", 
                                f"Error loading data for {sample_name}: {str(e)}")
        
        progress.setValue(len(self.particle_folder_paths))
        
    

    def update_detection_parameters_table(self):
        """
        Update detection parameters table with all samples.
        
        Populates table with default detection parameters for each valid sample including
        method selection, thresholds, smoothing options, and statistical parameters.
        """
        if not self.selected_element:
            return
            
        valid_samples = [f for f in self.particle_folder_paths if self.folder_data[f].get('status') == 'Loaded']
        self.detection_params_table.setRowCount(len(valid_samples))
        
        element = self.selected_element
        isotope = self.selected_element['selected_isotope']
        display_label = f"{int(round(isotope))}{element['symbol']}"
        
        for i, folder_path in enumerate(valid_samples):
            sample_name = self.folder_data[folder_path].get('sample_name', Path(folder_path).name)
            
            sample_item = QTableWidgetItem(sample_name)
            sample_item.setFlags(sample_item.flags() & ~Qt.ItemIsEditable)
            self.detection_params_table.setItem(i, 0, sample_item)
            
            element_item = QTableWidgetItem(display_label)
            element_item.setFlags(element_item.flags() & ~Qt.ItemIsEditable)
            self.detection_params_table.setItem(i, 1, element_item)
            
            method_combo = QComboBox()
            method_combo.addItems(["Currie", "Formula_C", "Compound Poisson LogNormal", "Manual"])
            method_combo.setCurrentText("Compound Poisson LogNormal")
            self.detection_params_table.setCellWidget(i, 2, method_combo)
            
            manual_threshold = QDoubleSpinBox()
            manual_threshold.setRange(0.0, 999999.0)
            manual_threshold.setDecimals(2)
            manual_threshold.setValue(10.0)
            manual_threshold.setEnabled(False)
            self.detection_params_table.setCellWidget(i, 3, manual_threshold)
            
            smoothing_checkbox = QCheckBox()
            smoothing_checkbox.setChecked(False)
            self.detection_params_table.setCellWidget(i, 4, smoothing_checkbox)
            
            window_spin = QSpinBox()
            window_spin.setRange(3, 51)
            window_spin.setValue(3)
            window_spin.setSingleStep(2)
            self.detection_params_table.setCellWidget(i, 5, window_spin)
            
            iterations_spin = QSpinBox()
            iterations_spin.setRange(1, 10)
            iterations_spin.setValue(1)
            self.detection_params_table.setCellWidget(i, 6, iterations_spin)
            
            min_points_spin = QSpinBox()
            min_points_spin.setRange(1, 50)
            min_points_spin.setValue(1)
            self.detection_params_table.setCellWidget(i, 7, min_points_spin)
            
            alpha_spin = QDoubleSpinBox()
            alpha_spin.setRange(0.00000001, 0.1)
            alpha_spin.setDecimals(8)
            alpha_spin.setValue(0.000001)
            alpha_spin.setSingleStep(0.000001)
            self.detection_params_table.setCellWidget(i, 8, alpha_spin)
            
            method_combo.currentTextChanged.connect(
                lambda text, row=i: self.detection_params_table.cellWidget(row, 3).setEnabled(text == "Manual"))
            smoothing_checkbox.stateChanged.connect(
                lambda state, row=i: self.toggle_smoothing_parameters(row, state))
        
        self.detect_button.setEnabled(True)

    def apply_global_detection_params(self, method):
        """
        Apply global detection method to all samples.
        
        Args:
            method: Detection method name to apply to all sample rows
        """
        for row in range(self.detection_params_table.rowCount()):
            method_combo = self.detection_params_table.cellWidget(row, 2)
            if method_combo:
                method_combo.setCurrentText(method)

    def toggle_smoothing_parameters(self, row, state):
        """
        Enable or disable smoothing parameters for a specific row.
        
        Args:
            row: Table row index
            state: Checkbox state (checked/unchecked)
        """
        window_spin = self.detection_params_table.cellWidget(row, 5)
        iterations_spin = self.detection_params_table.cellWidget(row, 6)
        
        if window_spin:
            window_spin.setEnabled(state)
        if iterations_spin:
            iterations_spin.setEnabled(state)

    def on_detection_params_selection_changed(self):
        """
        Handle selection change in detection parameters table to show sample preview.
        
        Updates sample combo box and displays either raw signal or detection results
        for the selected sample in the visualization plot.
        """
        current_row = self.detection_params_table.currentRow()
        
        if current_row < 0:
            self.visualization_status_label.setText("Click on any sample row above to preview its signal")
            return
            
        sample_item = self.detection_params_table.item(current_row, 0)
        if not sample_item:
            return
            
        sample_name = sample_item.text()
        
        folder_path = self.sample_name_to_folder.get(sample_name)
        
        if folder_path and folder_path in self.folder_data and 'isotope_signal' in self.folder_data[folder_path]:
            for i in range(self.sample_combo.count()):
                if self.sample_combo.itemData(i) == folder_path:
                    self.sample_combo.setCurrentIndex(i)
                    break
            
            if folder_path in self.detection_results:
                results = self.detection_results[folder_path]
                self.plot_sample_results(
                    results['sample_name'],
                    results['signal'],
                    results['smoothed_signal'],
                    results['particles'],
                    results['lambda_bkgd'],
                    results['threshold'],
                    results['time_array']
                )
                self.visualization_status_label.setText(f"Showing detection results for: {sample_name}")
            else:
                self.plot_raw_signal_preview(folder_path, sample_name)
                self.visualization_status_label.setText(f"Showing raw signal preview for: {sample_name}")
        else:
            self.visualization_status_label.setText(f"No signal data available for: {sample_name}")

    def plot_raw_signal_preview(self, folder_path, sample_name):
        """
        Plot raw signal preview for a sample.
        
        Args:
            folder_path: Path to the sample folder
            sample_name: Display name of the sample
        """
        self.plot_widget.clear()
        
        if 'isotope_signal' not in self.folder_data[folder_path]:
            self.visualization_status_label.setText(f"No isotope signal data available for: {sample_name}")
            return
            
        signal = self.folder_data[folder_path]['isotope_signal']
        time_array = self.folder_data[folder_path]['time_array']
        
        self.plot_widget.plot(
            x=time_array, 
            y=signal, 
            pen=pg.mkPen(color=(30, 144, 255), width=1), 
            name='Raw Signal'
        )
        
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.setLabel('left', 'Counts')
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.setTitle(f"Raw Signal Preview - {sample_name}")
        self.plot_widget.enableAutoRange()

    def detect_particles_all_samples(self):
        """
        Detect particles for all samples using PeakDetection class.
        
        Processes each valid sample with configured detection parameters, stores results
        in both new and legacy formats, and updates results and file info tables.
        """
        if not self.selected_element:
            QMessageBox.warning(self, "Detection Error", "Please select an element first.")
            return
            
        valid_samples = [f for f in self.particle_folder_paths if self.folder_data[f].get('status') == 'Loaded']
        if not valid_samples:
            QMessageBox.warning(self, "Detection Error", "No valid samples available.")
            return
        
        self.detection_results.clear()
        self.detected_particles.clear()
        self.folder_avg_counts.clear()
        
        self.results_table.setRowCount(0)
        self.results_table.clearContents()
        
        progress = QProgressDialog("Detecting particles...", "Cancel", 0, len(valid_samples), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(500)
        
        for i, folder_path in enumerate(valid_samples):
            progress.setValue(i)
            sample_name = self.folder_data[folder_path].get('sample_name', Path(folder_path).name)
                
            progress.setLabelText(f"Processing {sample_name}...")
            QApplication.processEvents()
            
            if progress.wasCanceled():
                break
            
            try:
                params = self.get_sample_detection_parameters(i)
                
                signal = self.folder_data[folder_path]['isotope_signal']
                time_array = self.folder_data[folder_path]['time_array']
                
                smoothed_signal, lambda_bkgd, threshold, mean_signal, threshold_data = self.peak_detector.detect_peaks_with_poisson(
                    signal,
                    window_length=params['smooth_window'],
                    iterations=params['iterations'],
                    alpha=params['alpha'],
                    apply_smoothing=params['apply_smoothing'],
                    method=params['method'],
                    manual_threshold=params['manual_threshold'],
                    element_thresholds={},
                    current_sample=None
                )
                
                particles = self.peak_detector.find_particles(
                    time_array,
                    smoothed_signal,
                    signal,
                    lambda_bkgd,
                    threshold,
                    min_continuous_points=params['min_continuous'],
                    apply_smoothing=params['apply_smoothing'],
                    integration_method="Background"
                )
                
                self.detection_results[folder_path] = {
                    'sample_name': sample_name,
                    'particles': particles,
                    'signal': signal,
                    'smoothed_signal': smoothed_signal,
                    'time_array': time_array,
                    'lambda_bkgd': lambda_bkgd,
                    'threshold': threshold,
                    'mean_signal': mean_signal,
                    'params': params,
                    'particle_count': len(particles) if particles else 0
                }
                
                self.detected_particles[folder_path] = particles
                if particles:
                    total_counts = [p['total_counts'] for p in particles if p and 'total_counts' in p and p['total_counts'] > 0]
                    if total_counts:
                        self.folder_avg_counts[folder_path] = np.mean(total_counts)
                    else:
                        self.folder_avg_counts[folder_path] = 0
                else:
                    self.folder_avg_counts[folder_path] = 0
                
            except Exception as e:
                QMessageBox.warning(self, "Detection Error", 
                                  f"Error processing {sample_name}: {str(e)}")
                continue
        
        progress.setValue(len(valid_samples))
        
        self.update_results_table()
        self.update_file_info_table()

    def toggle_calibration_view(self):
        """
        Toggle between raw data view and calibration view.
        
        Switches the calibration plot display between showing individual sample raw data
        and the overall calibration curve with statistics.
        """
        try:
            if self.current_calibration_view == "raw":
                self.current_calibration_view = "calibration"
                if hasattr(self, 'view_toggle_button') and self.view_toggle_button is not None:
                    self.view_toggle_button.setText("📊 Show Raw Data")
                self.show_calibration_plot_in_raw_area()
            else:
                self.current_calibration_view = "raw"
                if hasattr(self, 'view_toggle_button') and self.view_toggle_button is not None:
                    self.view_toggle_button.setText("📈 Show Calibration")
                self.refresh_current_raw_data_view()
        except RuntimeError as e:
            print(f"Warning: Widget access error in toggle: {e}")
            self.current_calibration_view = "raw"

    def show_calibration_plot_in_raw_area(self):
        """
        Show the calibration plot in the raw data plot area.
        
        Displays calibration curve with data points, regression line, and statistics
        using calculated ionic calibration results.
        """
        if not hasattr(self, 'ionic_calibration_slope') or not hasattr(self, 'ionic_calibration_intercept'):
            QMessageBox.warning(self, "No Calibration", "Please calculate calibration first.")
            self.current_calibration_view = "raw"
            self.view_toggle_button.setText("📈 Show Calibration")
            return
            
        self.calibration_raw_plot.clear()
        
        concentrations = []
        signals = []
        
        if 'selected_isotope' in self.selected_element:
            element_mass = self.selected_element['selected_isotope']
        else:
            element_mass = self.selected_element['isotopes'][0]
        
        for i in range(self.concentration_table.rowCount()):
            concentration_item = self.concentration_table.item(i, 1)
            if concentration_item:
                try:
                    conc = float(concentration_item.text())
                    if conc == -1:
                        continue
                        
                    folder_path = self.calibration_folder_paths[i]
                    if folder_path in self.calibration_data_cache and self.calibration_data_cache[folder_path].get('status') == 'Loaded':
                        cached_data = self.calibration_data_cache[folder_path]
                        
                        masses = cached_data['masses']
                        folder_signals = cached_data['signals']
                        run_info = cached_data['run_info']
                        
                        mass_index = np.argmin(np.abs(masses - element_mass))
                        
                        acqtime = run_info["SegmentInfo"][0]["AcquisitionPeriodNs"] * 1e-9
                        accumulations = run_info["NumAccumulations1"] * run_info["NumAccumulations2"]
                        dwell_time = acqtime * accumulations
                        
                        unit_combo = self.concentration_table.cellWidget(i, 2)
                        unit = unit_combo.currentText() if unit_combo else "ppb"
                        conc_ppb = self.convert_concentration_to_ppb(conc, unit)
                        
                        avg_count_per_second = np.mean(folder_signals[:, mass_index]) / dwell_time
                        
                        concentrations.append(conc_ppb)
                        signals.append(avg_count_per_second)
                        
                except (ValueError, KeyError, AttributeError):
                    continue
        
        if concentrations and signals:
            concentrations = np.array(concentrations)
            signals = np.array(signals)
            
            scatter = pg.ScatterPlotItem(
                concentrations, signals, 
                size=10, 
                brush=pg.mkBrush(30, 30, 255, 200),
                pen=pg.mkPen(30, 30, 255),
                symbol='o'
            )
            self.calibration_raw_plot.addItem(scatter)

            x_range = np.linspace(0, max(concentrations) * 1.1, 100)
            y_fit = self.ionic_calibration_slope * x_range + self.ionic_calibration_intercept
            line = self.calibration_raw_plot.plot(x_range, y_fit, pen=pg.mkPen('r', width=2))

            stats_text = (f"Slope: {self.ionic_calibration_slope:.2e} cps/ppb\n"
                        f"Intercept: {self.ionic_calibration_intercept:.2e} cps\n"
                        f"R² = {self.ionic_calibration_r_squared:.4f}")
            
            text_item = pg.TextItem(stats_text, anchor=(0, 1), color='k')
            text_item.setPos(max(concentrations) * 0.6, max(signals) * 0.9)
            self.calibration_raw_plot.addItem(text_item)

            self.calibration_raw_plot.setLabel('left', 'Signal (cps)')
            self.calibration_raw_plot.setLabel('bottom', 'Concentration (ppb)')
            self.calibration_raw_plot.setTitle("Ionic Calibration Results")
        else:
            self.calibration_raw_plot.setTitle("No calibration data available")

    def refresh_current_raw_data_view(self):
        """
        Refresh the current raw data view for the last selected sample.
        
        Redisplays raw data for the currently selected row in the concentration table.
        """
        current_row = self.concentration_table.currentRow()
        if current_row >= 0:
            self.on_concentration_table_clicked(current_row, 0)
        else:
            self.calibration_raw_plot.clear()
            self.calibration_raw_plot.setLabel('left', 'Counts')
            self.calibration_raw_plot.setLabel('bottom', 'Time (s)')
            self.calibration_raw_plot.setTitle("Raw Data")

    def get_sample_detection_parameters(self, row):
        """
        Get detection parameters for a specific sample.
        
        Args:
            row: Row index in the detection parameters table
            
        Returns:
            Dictionary containing all detection parameters for the sample
        """
        try:
            method_widget = self.detection_params_table.cellWidget(row, 2)
            manual_threshold_widget = self.detection_params_table.cellWidget(row, 3)
            smoothing_widget = self.detection_params_table.cellWidget(row, 4)
            window_widget = self.detection_params_table.cellWidget(row, 5)
            iterations_widget = self.detection_params_table.cellWidget(row, 6)
            min_points_widget = self.detection_params_table.cellWidget(row, 7)
            alpha_widget = self.detection_params_table.cellWidget(row, 8)
            
            if not all([method_widget, manual_threshold_widget, smoothing_widget, 
                       window_widget, iterations_widget, min_points_widget, alpha_widget]):
                raise ValueError(f"Missing widgets in row {row}")
            
            return {
                'method': method_widget.currentText(),
                'manual_threshold': manual_threshold_widget.value(),
                'apply_smoothing': smoothing_widget.isChecked(),
                'smooth_window': window_widget.value(),
                'iterations': iterations_widget.value(),
                'min_continuous': min_points_widget.value(),
                'alpha': alpha_widget.value()
            }
        except Exception as e:
            print(f"Error getting parameters for row {row}: {e}")
            return {
                'method': 'Compound_Poisson',
                'manual_threshold': 10.0,
                'apply_smoothing': False,
                'smooth_window': 3,
                'iterations': 1,
                'min_continuous': 1,
                'alpha': 0.000001
            }

    def update_results_table(self):
        """
        Update results table with all detection results.
        
        Populates table with detected particles from all samples, includes color coding
        based on signal-to-noise ratio for quality assessment.
        """
        self.results_table.setSortingEnabled(False)
        
        self.results_table.setRowCount(0)
        self.results_table.clearContents()
        
        for folder_path, results in self.detection_results.items():
            sample_name = results['sample_name']
            particles = results['particles']
            time_array = results['time_array']
            threshold = results['threshold']
            
            if not particles:
                continue
                
            for particle in particles:
                if particle is None:
                    continue
                    
                row_position = self.results_table.rowCount()
                self.results_table.insertRow(row_position)
                
                start_time = time_array[particle['left_idx']]
                end_time = time_array[particle['right_idx']]
                
                height_threshold_ratio = particle['max_height'] / threshold if threshold > 0 else 0
                
                sample_item = NumericTableWidgetItem(str(sample_name))
                sample_item.setData(Qt.UserRole, {'folder_path': folder_path, 'particle': particle})
                
                start_item = NumericTableWidgetItem(f"{start_time:.4f}")
                start_item.setData(Qt.UserRole, {'folder_path': folder_path, 'particle': particle})
                
                end_item = NumericTableWidgetItem(f"{end_time:.4f}")
                end_item.setData(Qt.UserRole, {'folder_path': folder_path, 'particle': particle})
                
                counts_item = NumericTableWidgetItem(f"{particle['total_counts']:.0f}")
                counts_item.setData(Qt.UserRole, {'folder_path': folder_path, 'particle': particle})
                
                height_item = NumericTableWidgetItem(f"{particle['max_height']:.0f}")
                height_item.setData(Qt.UserRole, {'folder_path': folder_path, 'particle': particle})
                
                if height_threshold_ratio >= 3.0:
                    color = QColor(144, 238, 144)
                elif height_threshold_ratio >= 2.0:
                    color = QColor(255, 255, 224)
                elif height_threshold_ratio >= 1.0:
                    color = QColor(255, 239, 213)
                else:
                    color = QColor(255, 200, 200)
                
                for item in [sample_item, start_item, end_item, counts_item, height_item]:
                    item.setBackground(color)
                
                self.results_table.setItem(row_position, 0, sample_item)
                self.results_table.setItem(row_position, 1, start_item)
                self.results_table.setItem(row_position, 2, end_item)
                self.results_table.setItem(row_position, 3, counts_item)
                self.results_table.setItem(row_position, 4, height_item)
        
        self.results_table.setSortingEnabled(True)
        self.results_table.sortItems(0, Qt.AscendingOrder)

    def highlight_selected_particle(self):
        """
        Zoom in on selected particle in plot.
        
        Retrieves particle data from selected table row, switches to appropriate sample,
        zooms plot to particle location, and highlights the particle.
        """
        selected_items = self.results_table.selectedItems()
        if not selected_items:
            return
            
        item_data = selected_items[0].data(Qt.UserRole)
        if not item_data:
            return
            
        folder_path = item_data['folder_path']
        particle = item_data['particle']
        
        for i in range(self.sample_combo.count()):
            if self.sample_combo.itemData(i) == folder_path:
                self.sample_combo.setCurrentIndex(i)
                break
        
        self.update_sample_visualization()
        
        if folder_path in self.detection_results:
            results = self.detection_results[folder_path]
            time_array = results['time_array']
            
            start_time = time_array[particle['left_idx']]
            end_time = time_array[particle['right_idx']]
            duration = end_time - start_time
            padding = max(duration * 2, 5.0)
            
            zoom_start = max(0, start_time - padding)
            zoom_end = min(time_array[-1], end_time + padding)
            
            self.plot_widget.setXRange(zoom_start, zoom_end, padding=0)
            
            self.highlight_particle_in_plot(particle, results)

    def highlight_particle_in_plot(self, particle, results):
        """
        Add highlighting to a specific particle in the plot.
        
        Args:
            particle: Particle dictionary containing detection information
            results: Detection results dictionary for the sample
        """
        if hasattr(self, 'current_highlighted_particle') and self.current_highlighted_particle:
            self.plot_widget.removeItem(self.current_highlighted_particle)
        
        time_array = results['time_array']
        signal = results['signal']
        
        start_idx = particle['left_idx']
        end_idx = particle['right_idx']
        
        particle_times = time_array[start_idx:end_idx+1]
        particle_signal = signal[start_idx:end_idx+1]
        
        highlight_region = pg.PlotCurveItem(
            x=particle_times,
            y=particle_signal,
            pen=pg.mkPen(color=(255, 0, 0), width=3),
            name='Selected Particle'
        )
        
        self.plot_widget.addItem(highlight_region)
        self.current_highlighted_particle = highlight_region

    def update_sample_visualization(self):
        """
        Update visualization for selected sample.
        
        Displays detection results for the currently selected sample in the combo box.
        """
        if not self.detection_results:
            return
            
        current_data = self.sample_combo.currentData()
        if not current_data or current_data not in self.detection_results:
            return
            
        results = self.detection_results[current_data]
        
        self.plot_sample_results(
            results['sample_name'],
            results['signal'],
            results['smoothed_signal'],
            results['particles'],
            results['lambda_bkgd'],
            results['threshold'],
            results['time_array']
        )

    def plot_sample_results(self, sample_name, signal, smoothed_signal, particles, lambda_bkgd, threshold, time_array):
        """
        Plot results for a specific sample.
        
        Args:
            sample_name: Display name of the sample
            signal: Raw signal array
            smoothed_signal: Smoothed signal array
            particles: List of detected particle dictionaries
            lambda_bkgd: Background level value
            threshold: Detection threshold value
            time_array: Time array corresponding to signal data
        """
        self.plot_widget.clear()
        
        self.current_highlighted_particle = None
        
        STYLES = {
            'raw_signal': pg.mkPen(color=(30, 144, 255), width=1),
            'smoothed_signal': pg.mkPen(color=(34, 139, 34), width=1),
            'background': pg.mkPen(color=(128, 128, 128), style=Qt.DashLine, width=1.5),
            'threshold': pg.mkPen(color=(220, 20, 60), style=Qt.DashLine, width=1.5),
            'peaks': {'symbol': 't', 'size': 12, 'brush': 'r', 'pen': 'r'},
            'grid': {'alpha': 0.2}
        }
        
        plot_data = [
            (time_array, signal, STYLES['raw_signal'], 'Raw Signal'),
            (time_array, smoothed_signal, STYLES['smoothed_signal'], 'Smoothed Signal'),
            (time_array, [lambda_bkgd] * len(time_array), STYLES['background'], 'Background Level'),
            (time_array, [threshold] * len(time_array), STYLES['threshold'], 'Detection Threshold')
        ]
        
        for x, y, pen, name in plot_data:
            self.plot_widget.plot(x=x, y=y, pen=pen, name=name)
        
        if particles:
            peak_data = {
                'times': [],
                'heights': [],
                'snr': []
            }
            
            for p in particles:
                if p is not None:
                    peak_idx = np.argmax(signal[p['left_idx']:p['right_idx']+1])
                    peak_data['times'].append(time_array[p['left_idx'] + peak_idx])
                    peak_height = p['max_height']
                    peak_data['heights'].append(peak_height)
                    peak_data['snr'].append(peak_height / threshold if threshold > 0 else 0)
            
            scatter = pg.ScatterPlotItem(
                x=peak_data['times'],
                y=peak_data['heights'],
                symbol=STYLES['peaks']['symbol'],
                size=STYLES['peaks']['size'],
                brush=[pg.mkBrush(self.peak_detector.get_snr_color(snr)) for snr in peak_data['snr']],
                pen=STYLES['peaks']['pen'],
                name='Detected Peaks'
            )
            self.plot_widget.addItem(scatter)
        
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True, alpha=STYLES['grid']['alpha'])
        
        self.plot_widget.setLabel('left', 'Counts')
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.setTitle(f"Particle Detection Results - {sample_name}")
        
        self.plot_widget.setMouseEnabled(x=True, y=True)
        self.plot_widget.enableAutoRange()

    def update_file_info_table(self):
        """
        Update file info table with improved average count display.
        
        Populates table with sample names, particle diameters, densities, and average counts
        for all processed samples.
        """
        try:
            self.file_info_table.setRowCount(len(self.particle_folder_paths))
            self.file_info_table.setColumnCount(4)
            self.file_info_table.setHorizontalHeaderLabels([
                'File Name', 'Diameter (nm)', 'Density (g/cm³)', 'Avg Total Count'
            ])
            
            for row, folder_path in enumerate(self.particle_folder_paths):
                folder_name = self.folder_data[folder_path].get('sample_name', Path(folder_path).name)
                self.file_info_table.setItem(row, 0, QTableWidgetItem(folder_name))
                
                diameter = self.folder_diameters.get(folder_path, self.default_diameter)
                density = self.folder_densities.get(folder_path, self.default_density)
                self.file_info_table.setItem(row, 1, QTableWidgetItem(str(diameter)))
                self.file_info_table.setItem(row, 2, QTableWidgetItem(str(density)))
                
                avg_count = self.folder_avg_counts.get(folder_path, 0)
                if avg_count > 0:
                    count_item = QTableWidgetItem(f"{avg_count:.2f}")
                else:
                    count_item = QTableWidgetItem("N/A")
                self.file_info_table.setItem(row, 3, count_item)
            
            self.file_info_table.resizeColumnsToContents()
            self.file_info_table.setAlternatingRowColors(True)
            
        except Exception as e:
            print(f"Error updating file info table: {str(e)}")

    def on_folder_selected(self, item):
        """
        Handle folder selection from the list.
        
        Args:
            item: Selected list widget item
            
        Shows periodic table if no element selected, otherwise updates detection
        parameters table and switches to Detection tab.
        """
        if not self.particle_folder_paths:
            return
            
        selected_index = self.folder_list.row(item)
        if selected_index < len(self.particle_folder_paths):
            self.folder_path = self.particle_folder_paths[selected_index]
            
            if not hasattr(self, 'selected_element'):
                self.show_periodic_table()
            else:
                sample_name = self.folder_data[self.folder_path].get('sample_name', Path(self.folder_path).name)
                for row in range(self.detection_params_table.rowCount()):
                    item = self.detection_params_table.item(row, 0)
                    if item and item.text() == sample_name:
                        self.detection_params_table.selectRow(row)
                        break
                
                self.tab_widget.setCurrentIndex(1)

    def calculate_particle_mass(self, diameter, density):
        """
        Calculate the mass of a spherical particle in femtograms.
        
        Args:
            diameter: Particle diameter in nanometers
            density: Particle density in g/cm³
            
        Returns:
            Particle mass in femtograms
        """
        radius = diameter / 2 * 1e-7
        volume = (4/3) * np.pi * (radius ** 3)
        mass = volume * density
        return mass * 1e15
    
    def calculate_mass_and_regression(self):
        """
        Calculate mass and perform regression analysis.
        
        Processes particle data to calculate masses, performs linear regression analysis,
        and displays results in the regression plot. Handles both single-folder and
        multi-folder regression scenarios.
        """
        if self.file_info_table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "Please detect particles first.")
            return

        masses = []
        counts = []
        folders = []

        progress_dialog = QDialog(self)
        progress_dialog.setWindowTitle("Calculating Regression")
        progress_layout = QVBoxLayout(progress_dialog)
        
        progress_label = QLabel("Processing folder data...")
        progress_layout.addWidget(progress_label)
        
        progress_bar = QProgressBar()
        progress_bar.setRange(0, self.file_info_table.rowCount())
        progress_layout.addWidget(progress_bar)
        
        progress_dialog.setModal(True)
        progress_dialog.show()
        QApplication.processEvents()

        try:
            for row in range(self.file_info_table.rowCount()):
                progress_bar.setValue(row + 1)
                QApplication.processEvents()
                
                diameter = float(self.file_info_table.item(row, 1).text())
                density = float(self.file_info_table.item(row, 2).text())
                avg_total_count_item = self.file_info_table.item(row, 3)
                
                if avg_total_count_item and avg_total_count_item.text() and avg_total_count_item.text() != "N/A":
                    avg_total_count = float(avg_total_count_item.text())
                    folder_name = self.file_info_table.item(row, 0).text()

                    if avg_total_count > 0:
                        mass = self.calculate_particle_mass(diameter, density)
                        masses.append(mass)
                        counts.append(avg_total_count)
                        folders.append(folder_name)

            if len(masses) == 0:
                progress_dialog.close()
                QMessageBox.warning(self, "Insufficient Data", "No valid data points for regression.")
                return

            is_single_folder = len(set(folders)) == 1

            self.tab_widget.setCurrentIndex(3)
            
            self.regression_plot.clear()

            if is_single_folder:
                progress_label.setText("Calculating single-folder regression...")
                QApplication.processEvents()
                
                mass = masses[0]
                count = counts[0]
                slope = count / mass
                
                plot_masses = np.array([0, mass])
                plot_counts = np.array([0, count])
                
                scatter = pg.ScatterPlotItem(plot_masses, plot_counts, size=10, brush=pg.mkBrush(30, 30, 255, 200))
                self.regression_plot.addItem(scatter)
                
                line = self.regression_plot.plot(plot_masses, slope * plot_masses, pen=pg.mkPen('r', width=2))
                
                text = pg.TextItem(f"Slope: {slope:.2e}", anchor=(0, 1), color='k')
                text.setFont(QFont("Arial", 12))
                self.regression_plot.addItem(text)
                text.setPos(mass * 0.6, count * 0.9)
                
                self.regression_plot.setXRange(-mass * 0.05, mass * 1.05)
                self.regression_plot.setYRange(-count * 0.05, count * 1.05)
                
                progress_dialog.close()
                
                QMessageBox.information(self, "Regression Results", f"Slope: {slope:.2e}")
                self.particle_calibration_slope = slope

            else:
                progress_label.setText("Calculating multi-folder regression...")
                QApplication.processEvents()
                
                masses = np.array(masses)
                counts = np.array(counts)

                sort_indices = np.argsort(masses)
                masses = masses[sort_indices]
                counts = counts[sort_indices]

                masses = np.insert(masses, 0, 0)
                counts = np.insert(counts, 0, 0)

                slope, intercept, r_value, _, _ = stats.linregress(masses, counts)

                scatter = pg.ScatterPlotItem(masses, counts, size=10, brush=pg.mkBrush(30, 30, 255, 200))
                self.regression_plot.addItem(scatter)

                line = self.regression_plot.plot(masses, slope * masses + intercept, pen=pg.mkPen('r', width=2))
                text = pg.TextItem(f"Slope: {slope:.2e}\nR²: {r_value**2:.4f}", anchor=(0, 1), color='k')
                text.setFont(QFont("Arial", 12))
                self.regression_plot.addItem(text)
                text.setPos(masses[-1] * 0.6, counts[-1] * 0.9)

                self.regression_plot.setXRange(-masses[-1] * 0.05, masses[-1] * 1.05)
                self.regression_plot.setYRange(-counts[-1] * 0.05, counts[-1] * 1.05)

                progress_dialog.close()
                
                self.particle_calibration_slope = slope

            self.regression_plot.setLabel('left', 'Average Counts')
            self.regression_plot.setLabel('bottom', 'Particle Mass (fg)')
            self.regression_plot.showGrid(x=True, y=True, alpha=0.3)
            
        except Exception as e:
            progress_dialog.close()
            QMessageBox.critical(self, "Regression Error", f"Error during regression calculation: {str(e)}")
    
    def select_calibration_folders(self):
        """
        Enhanced calibration folder selection dialog matching particle folder approach.
        
        Opens dialog allowing selection of NU folders, data files, or TOFWERK files for 
        ionic calibration, with multi-selection support and validation.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Calibration Data Source")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(450)
        layout = QVBoxLayout(dialog)

        instruction = QLabel("Choose your calibration data source type:")
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
        
        csv_desc = QLabel("• Select Data Files with ionic standard solutions\n• Configure column mappings and concentration settings")
        csv_desc.setStyleSheet("color: #666; margin-left: 20px; font-size: 11px;")
        
        tofwerk_desc = QLabel("• Select TOFWERK .h5 files from TofDAQ acquisitions\n• Supports multiple calibration standard files")
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
                self.select_calibration_nu_folders()
            elif csv_radio.isChecked():
                self.select_calibration_data_files()
            else:  
                self.select_calibration_tofwerk_files()
                
    def select_calibration_nu_folders(self):
        """
        Handle NU folder selection for ionic calibration.
        
        Opens file dialog with multi-selection enabled for choosing multiple
        NU instrument folders containing run.info files.
        """
        try:
            file_dialog = QFileDialog(self)
            file_dialog.setFileMode(QFileDialog.Directory)
            file_dialog.setOption(QFileDialog.DontUseNativeDialog, True)
            file_dialog.setWindowTitle("Select Calibration Data Folders")
            
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
                
                # Validate that folders contain run.info
                valid_paths = []
                for path in selected_paths:
                    run_info_path = Path(path) / "run.info"
                    if run_info_path.exists():
                        valid_paths.append(path)
                    else:
                        QMessageBox.warning(self, "Invalid Folder", 
                                        f"Folder '{Path(path).name}' does not contain run.info file.")
                
                if valid_paths:
                    self.process_calibration_folder_selection(valid_paths)
                        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error selecting folders: {str(e)}")
            
    def select_calibration_data_files(self):
        """
        Handle data file selection for ionic calibration.
        
        Opens file dialog for selecting multiple data files (CSV, TXT, Excel formats)
        and initiates CSV import process with calibration-specific configuration.
        """
        try:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Select Calibration Data Files",
                "",
                "Data Files (*.csv *.txt *.xls *.xlsx *.xlsm *.xlsb);;CSV Files (*.csv);;Text Files (*.txt);;Excel Files (*.xls *.xlsx *.xlsm *.xlsb);;All Files (*)"
            )
            
            if file_paths:
                self.process_calibration_csv_selection(file_paths)
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error selecting data files: {str(e)}")

    def select_calibration_tofwerk_files(self):
        """
        Handle TOFWERK .h5 file selection for ionic calibration.
        
        Opens file dialog for selecting multiple TOFWERK files and initiates
        TOFWERK calibration import process.
        """
        try:
            h5_files, _ = QFileDialog.getOpenFileNames(
                self,
                "Select TOFWERK .h5 Files for Calibration",
                "",
                "TOFWERK Files (*.h5);;All Files (*)"
            )
            
            if h5_files:
                self.handle_calibration_tofwerk_import(h5_files)
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error selecting TOFWERK files: {str(e)}")

    def handle_calibration_tofwerk_import(self, h5_file_paths):
        """
        Handle TOFWERK .h5 file import for ionic calibration.
        
        Args:
            h5_file_paths: List of .h5 file paths to import for calibration
            
        Processes TOFWERK calibration files, caches data, and updates concentration table.
        """
        try:
            progress = QProgressDialog("Processing TOFWERK calibration files...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            QApplication.processEvents()
            
            self.calibration_folder_paths = []
            self.calibration_data_cache = {}
            
            total_files = len(h5_file_paths)
            
            for i, h5_path in enumerate(h5_file_paths):
                if progress.wasCanceled():
                    break
                    
                file_progress = 10 + int((i / total_files) * 70)
                progress.setValue(file_progress)
                h5_file = Path(h5_path)
                progress.setLabelText(f"Processing {h5_file.name} ({i+1}/{total_files})...")
                QApplication.processEvents()
                
                try:
                    if not data_loading.tofwerk_loading.is_tofwerk_file(h5_file):
                        raise ValueError(f"Not a valid TOFWERK file: {h5_file.name}")
                    
                    sample_name = h5_file.stem
                    
                    data, info, dwell_time = data_loading.tofwerk_loading.read_tofwerk_file(h5_path)
                    
                    if 'mass' in info.dtype.names:
                        masses = info['mass']
                    else:
                        masses = np.array([float(label.decode() if isinstance(label, bytes) else label) 
                                        for label in info['label']])
                    
                    virtual_path = f"tofwerk_calibration_{i}_{sample_name}"
                    self.calibration_folder_paths.append(virtual_path)
                    
                    run_info = {
                        'SampleName': sample_name,
                        'AnalysisDateTime': 'TOFWERK Import',
                        'source_type': 'tofwerk',
                        'SegmentInfo': [{
                            'AcquisitionPeriodNs': dwell_time * 1e9
                        }],
                        'NumAccumulations1': 1,
                        'NumAccumulations2': 1
                    }
                    
                    self.calibration_data_cache[virtual_path] = {
                        'masses': masses,
                        'signals': data,
                        'run_info': run_info,
                        'sample_name': sample_name,
                        'status': 'Loaded',
                        'source_type': 'tofwerk',
                        'dwell_time': dwell_time,
                        'is_tofwerk': True
                    }
                    
                except Exception as e:
                    sample_name = h5_file.stem
                    virtual_path = f"tofwerk_calibration_{i}_{sample_name}"
                    self.calibration_folder_paths.append(virtual_path)
                    
                    self.calibration_data_cache[virtual_path] = {
                        'status': f'Error: {str(e)}',
                        'sample_name': sample_name,
                        'source_type': 'tofwerk',
                        'is_tofwerk': True
                    }
                    QMessageBox.warning(self, "TOFWERK Loading Error", 
                                    f"Error loading {h5_file.name}: {str(e)}")
            
            progress.setValue(90)
            progress.setLabelText("Updating concentration table...")
            QApplication.processEvents()
            
            self.update_concentration_table()
            
            progress.setValue(100)
            progress.close()
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(self, "TOFWERK Import Error", 
                            f"Error importing TOFWERK calibration files: {str(e)}")
            self.calibration_folder_paths = []
            self.calibration_data_cache = {}

    def process_calibration_folder_selection(self, selected_paths):
        """
        Process selected calibration folders.
        
        Args:
            selected_paths: List of folder paths to process
            
        Validates folders, loads data, caches it for later use, and updates
        the concentration table.
        """
        try:
            if self.all_masses is not None:
                valid_folders = self.validate_calibration_folders(selected_paths)
                if not valid_folders:
                    QMessageBox.warning(self, "Validation Error", 
                                    "No valid calibration folders found. Please ensure folders have compatible mass ranges.")
                    return
                selected_paths = valid_folders

            progress = QProgressDialog("Processing calibration data folders...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()

            self.calibration_folder_paths = selected_paths
            self.calibration_data_cache = {}

            total_paths = len(selected_paths)
            
            for i, path in enumerate(selected_paths):
                progress.setValue(int((i / total_paths) * 90))
                folder_name = Path(path).name
                progress.setLabelText(f"Loading {folder_name} ({i+1}/{total_paths})...")
                QApplication.processEvents()
                
                if progress.wasCanceled():
                    break
                    
                try:
                    run_info_path = Path(path) / "run.info"
                    if run_info_path.exists():
                        with open(run_info_path, "r") as fp:
                            run_info = json.load(fp)
                        sample_name = run_info.get("SampleName", Path(path).name)
                    else:
                        sample_name = Path(path).name
                        
                    masses, signals, run_info = data_loading.vitesse_loading.read_nu_directory(path)
                    
                    self.calibration_data_cache[path] = {
                        'masses': masses,
                        'signals': signals,
                        'run_info': run_info,
                        'sample_name': sample_name,
                        'status': 'Loaded',
                        'source_type': 'folder'
                    }
                    
                except Exception as e:
                    sample_name = Path(path).name
                    self.calibration_data_cache[path] = {
                        'status': f'Error: {str(e)}',
                        'sample_name': sample_name,
                        'source_type': 'folder'
                    }
                    QMessageBox.warning(self, "Loading Error", 
                                    f"Error loading {folder_name}: {str(e)}")

            progress.setValue(90)
            progress.setLabelText("Updating concentration table...")
            QApplication.processEvents()

            self.update_concentration_table()

            progress.setValue(100)
            progress.close()

        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(self, "Error", f"Error processing calibration folders: {str(e)}")
            self.calibration_folder_paths = []
            self.calibration_data_cache = {}

    def process_calibration_csv_selection(self, file_paths):
        """
        Process selected calibration CSV files.
        
        Args:
            file_paths: List of CSV file paths to process
            
        Shows CSV calibration dialog and processes files with configuration.
        """
        from data_loading.import_csv_dialogs import show_csv_calibration_dialog
        
        config = show_csv_calibration_dialog(file_paths, self)
        
        if config:
            self.process_calibration_csv_import(config)

    def process_calibration_csv_import(self, config):
        """
        Process calibration CSV import with given configuration.
        
        Args:
            config: CSV configuration dictionary with file paths and settings
            
        Loads CSV data, converts to compatible format, caches data, and updates
        concentration table.
        """
        try:
            progress = QProgressDialog("Importing calibration CSV data...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            self.calibration_folder_paths = []
            self.calibration_data_cache = {}
            
            total_files = len(config['file_paths'])
            
            for i, file_path in enumerate(config['file_paths']):
                progress.setValue(int((i / total_files) * 90))
                file_name = Path(file_path).name
                progress.setLabelText(f"Processing {file_name} ({i+1}/{total_files})...")
                QApplication.processEvents()
                
                if progress.wasCanceled():
                    break
                    
                try:
                    import pandas as pd
                    df = pd.read_csv(
                        file_path,
                        delimiter=config['delimiter'],
                        header=config['header_row']
                    )
                    
                    time_array = df[config['time_column']].values
                    
                    masses = []
                    signals_list = []
                    
                    for col in df.columns:
                        if col != config['time_column']:
                            try:
                                mass = float(col)
                                masses.append(mass)
                                signals_list.append(df[col].values)
                            except ValueError:
                                continue
                    
                    masses = np.array(masses)
                    signals = np.column_stack(signals_list) if signals_list else np.array([])
                    
                    sample_name = Path(file_path).stem
                    run_info = {
                        'SampleName': sample_name,
                        'AnalysisDateTime': 'CSV Import',
                        'source_type': 'csv',
                        'SegmentInfo': [{
                            'AcquisitionPeriodNs': 1e9
                        }],
                        'NumAccumulations1': 1,
                        'NumAccumulations2': 1
                    }
                    
                    virtual_path = f"csv_calibration_{i}_{sample_name}"
                    self.calibration_folder_paths.append(virtual_path)
                    
                    self.calibration_data_cache[virtual_path] = {
                        'masses': masses,
                        'signals': signals,
                        'run_info': run_info,
                        'sample_name': sample_name,
                        'status': 'Loaded',
                        'source_type': 'csv',
                        'time_array': time_array,
                        'concentration': config.get('concentrations', {}).get(file_path, -1)
                    }
                    
                except Exception as e:
                    sample_name = Path(file_path).stem
                    virtual_path = f"csv_calibration_{i}_{sample_name}"
                    self.calibration_folder_paths.append(virtual_path)
                    
                    self.calibration_data_cache[virtual_path] = {
                        'status': f'Error: {str(e)}',
                        'sample_name': sample_name,
                        'source_type': 'csv'
                    }
                    QMessageBox.warning(self, "CSV Loading Error", 
                                    f"Error loading {file_name}: {str(e)}")

            progress.setValue(90)
            progress.setLabelText("Updating concentration table...")
            QApplication.processEvents()

            self.update_concentration_table()

            progress.setValue(100)
            progress.close()

        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(self, "CSV Import Error", f"Error importing calibration CSV: {str(e)}")
            self.calibration_folder_paths = []
            self.calibration_data_cache = {}
        
    def select_particle_folders(self):
        """
        Enhanced folder/file selection matching number method structure.
        
        Displays a dialog allowing user to choose between NU folders with run.info files,
        data files in various formats (CSV, TXT, Excel), or TOFWERK .h5 files.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Data Source")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(450)
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
        
        csv_desc = QLabel("• Select Data Files with mass spectrometry data\n• Configure column mappings and time settings for particle analysis")
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
                self.select_nu_folders()
            elif csv_radio.isChecked():
                self.select_data_files()
            else:  
                self.select_tofwerk_files()
                
    def select_nu_folders(self):
        """
        Handle NU folder selection for particle analysis.
        
        Opens file dialog with multi-selection enabled for choosing multiple
        NU instrument folders containing run.info files.
        """
        try:
            file_dialog = QFileDialog(self)
            file_dialog.setFileMode(QFileDialog.Directory)
            file_dialog.setOption(QFileDialog.DontUseNativeDialog, True)
            file_dialog.setWindowTitle("Select Particle Data Folders")
            
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
                    
                self.process_folder_selection(selected_paths)
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error selecting folders: {str(e)}")
            
    def select_tofwerk_files(self):
        """
        Handle TOFWERK .h5 file selection for particle analysis.
        
        Opens file dialog for selecting multiple TOFWERK files and initiates
        TOFWERK import process.
        """
        try:
            h5_files, _ = QFileDialog.getOpenFileNames(
                self,
                "Select TOFWERK .h5 Files for Particle Analysis",
                "",
                "TOFWERK Files (*.h5);;All Files (*)"
            )
            
            if h5_files:
                self.handle_tofwerk_import(h5_files)
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error selecting TOFWERK files: {str(e)}")
            
    def handle_tofwerk_import(self, h5_file_paths):
        """
        Handle TOFWERK .h5 file import for particle analysis.
        
        Args:
            h5_file_paths: List of .h5 file paths to import
            
        Processes TOFWERK files and updates UI accordingly.
        """
        try:
            progress = QProgressDialog("Processing TOFWERK files...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            QApplication.processEvents()
            
            valid_files = []
            all_masses_from_files = []
            
            total_files = len(h5_file_paths)
            
            for i, h5_path in enumerate(h5_file_paths):
                if progress.wasCanceled():
                    return
                    
                file_progress = 10 + int((i / total_files) * 70)
                progress.setValue(file_progress)
                h5_file = Path(h5_path)
                progress.setLabelText(f"Checking {h5_file.name}...")
                QApplication.processEvents()
                
                try:
                    if not data_loading.tofwerk_loading.is_tofwerk_file(h5_file):
                        raise ValueError(f"Not a valid TOFWERK file: {h5_file.name}")
                    
                    sample_name = h5_file.stem
                    
                    try:
                        from data_loading.data_thread import DataProcessThread
                        masses = DataProcessThread.get_masses_only(str(h5_path))
                        all_masses_from_files.extend(masses)
                    except Exception as mass_error:
                        print(f"Warning: Could not get masses from {h5_path}: {mass_error}")
                        masses = []
                    
                    self.folder_data[h5_path] = {
                        'masses': masses,
                        'status': 'Loaded',
                        'sample_name': sample_name,
                        'data_loaded': False,
                        'is_tofwerk': True
                    }
                    
                    self.sample_name_to_folder[sample_name] = h5_path
                    valid_files.append(h5_path)
                    
                except Exception as e:
                    sample_name = h5_file.stem
                    self.folder_data[h5_path] = {
                        'status': f'Error: {str(e)}',
                        'sample_name': sample_name,
                        'data_loaded': False,
                        'is_tofwerk': True
                    }
                    self.sample_name_to_folder[sample_name] = h5_path
                    
                    print(f"Warning: Error loading {sample_name}: {str(e)}")
                    continue
            
            progress.setValue(80)
            progress.setLabelText("Finalizing setup...")
            QApplication.processEvents()
            
            if not valid_files:
                raise ValueError("No valid TOFWERK files were found.")
            
            self.particle_folder_paths.extend(valid_files)
            
            if all_masses_from_files:
                if self.all_masses:
                    self.all_masses = sorted(list(set(self.all_masses + all_masses_from_files)))
                else:
                    self.all_masses = sorted(list(set(all_masses_from_files)))
            
            progress.setValue(90)
            progress.setLabelText("Updating interface...")
            QApplication.processEvents()
            
            self.update_folder_list()
            self.enable_ui_elements()
            
            progress.setValue(100)
            progress.close()
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(
                self,
                "Import Error",
                f"Error importing TOFWERK files: {str(e)}"
            )

    def process_folder_selection(self, selected_paths):
        """
        Process selected folders.
        
        Args:
            selected_paths: List of folder paths to process
            
        Validates folders, loads data, checks mass consistency, and updates UI.
        """
        try:
            progress = QProgressDialog("Processing particle data folders...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            
            self.particle_folder_paths = []
            self.folder_data = {}
            self.sample_name_to_folder = {}

            total_paths = len(selected_paths)
            valid_folders = []
            all_masses_sets = []
            
            for i, path in enumerate(selected_paths):
                progress.setValue(int((i / total_paths) * 90))
                folder_name = Path(path).name
                progress.setLabelText(f"Processing {folder_name} ({i+1}/{total_paths})...")
                QApplication.processEvents()
                
                if progress.wasCanceled():
                    break
                    
                try:
                    masses, signals, run_info = data_loading.vitesse_loading.read_nu_directory(
                        path=path,
                        max_integ_files=1,
                        autoblank=False,
                        raw=False
                    )
                    
                    all_masses_sets.append(set(masses))
                    
                    sample_name = run_info.get("SampleName", Path(path).name)
                    
                    self.folder_data[path] = {
                        'masses': masses,
                        'signals': signals,
                        'run_info': run_info,
                        'status': 'Loaded',
                        'sample_name': sample_name
                    }
                    
                    self.sample_name_to_folder[sample_name] = path
                    valid_folders.append(path)
                    
                except Exception as e:
                    sample_name = Path(path).name
                    self.folder_data[path] = {
                        'status': f'Error: {str(e)}',
                        'sample_name': sample_name
                    }
                    self.sample_name_to_folder[sample_name] = path
                    QMessageBox.warning(self, "Loading Error", 
                                    f"Error loading {folder_name}: {str(e)}")

            progress.setValue(90)
            progress.setLabelText("Validating mass consistency...")
            QApplication.processEvents()

            if len(all_masses_sets) > 1:
                first_masses = all_masses_sets[0]
                if not all(masses_set == first_masses for masses_set in all_masses_sets):
                    QMessageBox.warning(
                        self, 
                        "Mass Inconsistency", 
                        "Selected folders have different mass ranges. "
                        "All folders must have identical mass configurations for proper analysis."
                    )

            if all_masses_sets:
                self.all_masses = sorted(list(all_masses_sets[0]))
            self.particle_folder_paths = valid_folders

            progress.setValue(100)
            progress.close()

            self.update_folder_list()
            self.enable_ui_elements()

        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(self, "Error", f"Error processing folders: {str(e)}")
            self.particle_folder_paths = []
            self.folder_data = {}
            self.sample_name_to_folder = {}

    def process_csv_selection(self, file_paths):
        """
        Process selected CSV files.
        
        Args:
            file_paths: List of CSV file paths to process
            
        Shows CSV structure configuration dialog and initiates import.
        """
        from data_loading.import_csv_dialogs import show_csv_structure_dialog, CSVDataProcessThread
        
        config = show_csv_structure_dialog(file_paths, self)
        
        if config:
            self.process_csv_import(config)

    def process_csv_import(self, config):
        """
        Process CSV import with given configuration.
        
        Args:
            config: CSV configuration dictionary
            
        Starts background thread to process CSV files and handle results.
        """
        try:
            progress = QProgressDialog("Importing CSV data...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            from data_loading.import_csv_dialogs import CSVDataProcessThread
            
            self.csv_thread = CSVDataProcessThread(config)
            self.csv_thread.progress.connect(progress.setValue)
            self.csv_thread.finished.connect(self.handle_csv_import_finished)
            self.csv_thread.error.connect(self.handle_error)
            self.csv_thread.start()
            
        except Exception as e:
            progress.setVisible(False)
            QMessageBox.critical(self, "Import Error", f"Error importing CSV: {str(e)}")

    def handle_csv_import_finished(self, data, run_info, time_array, sample_name, analysis_datetime):
        """
        Handle completion of CSV import.
        
        Args:
            data: Dictionary mapping masses to signal arrays
            run_info: Run information dictionary
            time_array: Time array for the data
            sample_name: Name of the sample
            analysis_datetime: Analysis datetime string
            
        Converts CSV data to folder-compatible structure and updates UI.
        """
        try:
            folder_path = f"csv_{sample_name}"
            
            self.folder_data[folder_path] = {
                'masses': list(data.keys()),
                'signals': np.column_stack([data[mass] for mass in data.keys()]),
                'run_info': run_info,
                'status': 'Loaded',
                'sample_name': sample_name,
                'source_type': 'csv',
                'isotope_signal': None,
                'time_array': time_array
            }
            
            self.sample_name_to_folder[sample_name] = folder_path
            self.particle_folder_paths.append(folder_path)
            
            if self.all_masses is None:
                self.all_masses = sorted(list(data.keys()))
            
            self.update_folder_list()
            self.enable_ui_elements()
            
            self.folder_status_label.setText(f"Successfully imported CSV data for {sample_name}")
            
        except Exception as e:
            QMessageBox.critical(self, "CSV Import Error", f"Error processing CSV import: {str(e)}")

    def handle_error(self, error_message):
        """
        Handle errors from data processing threads.
        
        Args:
            error_message: Error message string
        """
        QMessageBox.critical(self, "Error", f"An error occurred: {error_message}")
                            
    def auto_fill_concentrations(self):
        """
        Automatically fill concentration values based on sample names.
        
        Attempts to extract concentration values from sample names using pattern
        matching for common formats and units.
        """
        if self.concentration_table.rowCount() == 0:
            QMessageBox.information(self, "Auto-Fill", "No samples available to auto-fill.")
            return
            
        self.ignore_concentration_item_changed = True
        filled_count = 0
        
        try:
            for row in range(self.concentration_table.rowCount()):
                sample_item = self.concentration_table.item(row, 0)
                if sample_item:
                    sample_name = sample_item.text()
                    concentration = self.extract_concentration_from_sample_name(sample_name)
                    
                    if concentration != "-1":
                        concentration_item = self.concentration_table.item(row, 1)
                        if not concentration_item or concentration_item.text() in ["-1", ""]:
                            self.concentration_table.setItem(row, 1, QTableWidgetItem(concentration))
                            filled_count += 1
        finally:
            self.ignore_concentration_item_changed = False

    def show_concentration_context_menu(self, position):
        """
        Show context menu for concentration table operations.
        
        Args:
            position: Position where context menu was requested
            
        Displays menu with options to set common concentration values or exclude cells.
        """
        menu = QMenu()
        
        set_minus_one_action = menu.addAction("Set to -1 (Exclude from Calibration)")
        set_zero_action = menu.addAction("Set to 0 (Blank)")
        
        menu.addSeparator()
        concentrations_menu = menu.addMenu("Set Concentration")
        
        common_concentrations = [0.1, 0.5, 1, 2, 5, 10, 20, 50, 100]
        conc_actions = {}
        
        for conc in common_concentrations:
            action = concentrations_menu.addAction(f"{conc} ppb")
            conc_actions[action] = conc
        
        action = menu.exec(self.concentration_table.viewport().mapToGlobal(position))
        
        if action == set_minus_one_action:
            self.set_selected_cells_to_minus_one()
        elif action == set_zero_action:
            self.set_selected_concentration_cells_to_value(0)
        elif action in conc_actions:
            self.set_selected_concentration_cells_to_value(conc_actions[action])

    def set_selected_cells_to_minus_one(self):
        """Set selected concentration cells to -1."""
        self.set_selected_concentration_cells_to_value(-1)

    def set_selected_concentration_cells_to_value(self, value):
        """
        Set selected concentration cells to a specific value.
        
        Args:
            value: Value to set in selected cells
        """
        selected_ranges = self.concentration_table.selectedRanges()
        if not selected_ranges:
            return
            
        self.ignore_concentration_item_changed = True
        try:
            for range_obj in selected_ranges:
                for row in range(range_obj.topRow(), range_obj.bottomRow() + 1):
                    for col in range(range_obj.leftColumn(), range_obj.rightColumn() + 1):
                        if col == 1:
                            self.concentration_table.setItem(row, col, QTableWidgetItem(f"{value}"))
        finally:
            self.ignore_concentration_item_changed = False

    def on_concentration_data_changed(self, item):
        """
        Handle data changes in the concentration table.
        
        Args:
            item: Table item that was changed
        """
        if not self.ignore_concentration_item_changed:
            pass

    def on_concentration_table_clicked(self, row, col):
        """
        Handle clicks on concentration table to show raw data.
        
        Args:
            row: Row index that was clicked
            col: Column index that was clicked
        """
        if row < 0 or row >= len(self.calibration_folder_paths):
            return
            
        folder_path = self.calibration_folder_paths[row]
        sample_item = self.concentration_table.item(row, 0)
        sample_name = sample_item.text() if sample_item else Path(folder_path).name
        
        self.show_calibration_sample_raw_data(folder_path, sample_name)

    def show_calibration_sample_raw_data(self, folder_path, sample_name):
        """
        Show raw data for a calibration sample using cached data.
        Supports NU folders, CSV files, and TOFWERK files.
        
        Args:
            folder_path: Path to the sample folder or virtual path
            sample_name: Display name of the sample
        """
        if not hasattr(self, 'selected_element') or not self.selected_element:
            self.calibration_sample_label.setText("Please select an element first")
            return
            
        if folder_path not in self.calibration_data_cache:
            self.calibration_sample_label.setText("Data not cached. Please reload calibration folders.")
            return
            
        cached_data = self.calibration_data_cache[folder_path]
        
        if cached_data.get('status') != 'Loaded':
            self.calibration_sample_label.setText(f"Error: {cached_data.get('status', 'Unknown error')}")
            return
        
        try:
            masses = cached_data['masses']
            signals = cached_data['signals']
            is_tofwerk = cached_data.get('is_tofwerk', False)
            
            if 'selected_isotope' in self.selected_element:
                element_mass = self.selected_element['selected_isotope']
            else:
                element_mass = self.selected_element['isotopes'][0]
            
            mass_index = np.argmin(np.abs(masses - element_mass))
            
            if is_tofwerk:
                dwell_time = cached_data['dwell_time']
                
                if hasattr(signals.dtype, 'names') and signals.dtype.names:
                    field_name = signals.dtype.names[mass_index]
                    isotope_signal = signals[field_name]
                else:
                    isotope_signal = signals[:, mass_index]
                
                time_array = np.arange(len(isotope_signal)) * dwell_time
                
            else:
                run_info = cached_data['run_info']
                isotope_signal = signals[:, mass_index]
                
                acqtime = run_info["SegmentInfo"][0]["AcquisitionPeriodNs"] * 1e-9
                accumulations = run_info["NumAccumulations1"] * run_info["NumAccumulations2"]
                dwell_time = acqtime * accumulations
                time_array = np.arange(len(isotope_signal)) * dwell_time
            
            self.calibration_raw_plot.clear()
            self.calibration_raw_plot.plot(
                x=time_array, 
                y=isotope_signal, 
                pen=pg.mkPen(color=(30, 144, 255), width=1), 
                name='Raw Signal'
            )
            
            element_symbol = self.selected_element['symbol']
            isotope_label = f"{int(round(element_mass))}{element_symbol}"
            self.calibration_raw_plot.setLabel('left', 'Counts')
            self.calibration_raw_plot.setLabel('bottom', 'Time (s)')
            
            source_type = "TOFWERK" if is_tofwerk else cached_data.get('source_type', 'NU').upper()
            self.calibration_raw_plot.setTitle(f"Raw Data - {sample_name} ({isotope_label}) [{source_type}]")
            
            avg_signal = np.mean(isotope_signal)
            self.calibration_sample_label.setText(f"{sample_name} - Avg: {avg_signal:.1f} counts [{source_type}]")
            
        except Exception as e:
            self.calibration_sample_label.setText(f"Error displaying data: {str(e)}")
            import traceback
            traceback.print_exc()
                                
    def extract_concentration_from_sample_name(self, sample_name):
        """
        Extract concentration value from sample name using flexible pattern matching.
        
        Args:
            sample_name: Sample name string to parse
            
        Returns:
            Concentration value as string, or "-1" if not found
        """
        import re
        
        sample_name_lower = sample_name.lower().strip()
        
        blank_patterns = ['blank', 'blanc', 'blk', 'background', 'bkg', 'zero']
        if any(pattern in sample_name_lower for pattern in blank_patterns):
            return "0"

        concentration_patterns = [
            (r'(\d+(?:\.\d+)?)\s*ppb', 'ppb'),
            (r'(\d+(?:\.\d+)?)\s*μg/l', 'ppb'),  
            (r'(\d+(?:\.\d+)?)\s*ug/l', 'ppb'),  
            (r'(\d+(?:\.\d+)?)\s*ppm', 'ppm'),
            (r'(\d+(?:\.\d+)?)\s*mg/l', 'ppm'), 
            (r'(\d+(?:\.\d+)?)\s*ppt', 'ppt'),
            (r'(\d+(?:\.\d+)?)\s*ng/l', 'ppt'),  
            (r'(\d+(?:\.\d+)?)\s*$', 'ppb'),
            (r'^(\d+(?:\.\d+)?)(?:\D|$)', 'ppb'),  
        ]
        
        for pattern, unit in concentration_patterns:
            matches = re.findall(pattern, sample_name_lower)
            if matches:
                try:
                    concentration_value = float(matches[0])
                    return str(concentration_value)
                except ValueError:
                    continue
        
        number_matches = re.findall(r'\b(\d+(?:\.\d+)?)\b', sample_name_lower)
        if number_matches:
            common_concentrations = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000]
            
            for match in number_matches:
                try:
                    value = float(match)
                    if value in common_concentrations or (0.01 <= value <= 10000):
                        return str(value)
                except ValueError:
                    continue
        
        return "-1"
                    
    def update_concentration_table(self):
        """
        Update the concentration table with selected folders.
        
        Populates table with sample names, empty concentration fields, and unit selectors.
        """
        self.concentration_table.setRowCount(len(self.calibration_folder_paths))
        
        numeric_delegate = NumericDelegate(self.concentration_table)
        self.concentration_table.setItemDelegateForColumn(1, numeric_delegate)
        
        for i, folder_path in enumerate(self.calibration_folder_paths):
            try:
                run_info_path = Path(folder_path) / "run.info"
                if run_info_path.exists():
                    with open(run_info_path, "r") as fp:
                        run_info = json.load(fp)
                    sample_name = run_info.get("SampleName", Path(folder_path).name)
                else:
                    sample_name = Path(folder_path).name
            except:
                sample_name = Path(folder_path).name
            
            sample_item = QTableWidgetItem(sample_name)
            sample_item.setFlags(sample_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            sample_item.setData(Qt.UserRole, folder_path)
            self.concentration_table.setItem(i, 0, sample_item)
            
            self.concentration_table.setItem(i, 1, QTableWidgetItem("-1"))
            
            unit_combo = QComboBox()
            unit_combo.addItems(["ppb", "ppm", "ppt", "ng/L", "µg/L", "mg/L"])
            unit_combo.setCurrentText("ppb")
            self.concentration_table.setCellWidget(i, 2, unit_combo)
        
        self.concentration_table.itemChanged.connect(self.on_concentration_data_changed)

    def validate_calibration_folders(self, folders):
        """
        Validate that calibration folders have compatible mass ranges.
        
        Args:
            folders: List of folder paths to validate
            
        Returns:
            List of valid folder paths with compatible mass ranges
        """
        valid_folders = []
        mass_tolerance = 0.1
        
        for folder in folders:
            try:
                masses, _, _ = data_loading.vitesse_loading.read_nu_directory(folder, max_integ_files=1)
                
                if len(masses) == len(self.all_masses):
                    mass_differences = np.abs(masses - self.all_masses)
                    if np.all(mass_differences <= mass_tolerance):
                        valid_folders.append(folder)
                    else:
                        print(f"Warning: Folder {Path(folder).name} has incompatible masses")
                else:
                    print(f"Warning: Folder {Path(folder).name} has different number of masses")
                    
            except Exception as e:
                print(f"Error validating folder {folder}: {e}")
                
        return valid_folders

    def calculate_calibration(self):
        """
        Calculate ionic calibration with multiple regression methods using cached data.
        Supports NU folders, CSV files, and TOFWERK files.
        
        Processes cached calibration data, performs selected regression method,
        and enables calibration visualization toggle.
        """
        if not hasattr(self, 'selected_element') or not self.selected_element:
            QMessageBox.warning(self, "Error", "Please select an element first.")
            return
            
        if self.concentration_table.rowCount() == 0:
            QMessageBox.warning(self, "Error", "Please select calibration folders first.")
            return

        progress = QProgressDialog("Calculating calibration...", None, 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(500)
        progress.setValue(10)
        QApplication.processEvents()

        try:
            concentrations = []
            signals = []
            valid_samples = []

            if 'selected_isotope' in self.selected_element:
                element_mass = self.selected_element['selected_isotope']
            else:
                element_mass = self.selected_element['isotopes'][0]

            progress.setValue(30)
            progress.setLabelText("Processing cached calibration data...")
            QApplication.processEvents()

            for i in range(self.concentration_table.rowCount()):
                folder_path = self.calibration_folder_paths[i]
                concentration_item = self.concentration_table.item(i, 1)
                unit_combo = self.concentration_table.cellWidget(i, 2)
                
                if not concentration_item or not unit_combo:
                    continue
                    
                try:
                    conc = float(concentration_item.text())
                    unit = unit_combo.currentText()
                    
                    if conc == -1:
                        continue
                    
                    conc_ppb = self.convert_concentration_to_ppb(conc, unit)
                    concentrations.append(conc_ppb)
                    
                    if folder_path not in self.calibration_data_cache:
                        progress.close()
                        QMessageBox.warning(self, "Error", f"Data not cached for row {i+1}. Please reload calibration folders.")
                        return
                        
                    cached_data = self.calibration_data_cache[folder_path]
                    if cached_data.get('status') != 'Loaded':
                        progress.close()
                        QMessageBox.warning(self, "Error", f"Invalid cached data for row {i+1}: {cached_data.get('status')}")
                        return
                    
                    masses = cached_data['masses']
                    folder_signals = cached_data['signals']
                    sample_name = cached_data['sample_name']
                    is_tofwerk = cached_data.get('is_tofwerk', False)

                    mass_index = np.argmin(np.abs(masses - element_mass))
                    
                    if is_tofwerk:
                        dwell_time = cached_data['dwell_time']
                        
                        if hasattr(folder_signals.dtype, 'names') and folder_signals.dtype.names:
                            field_name = folder_signals.dtype.names[mass_index]
                            isotope_signal = folder_signals[field_name]
                        else:
                            isotope_signal = folder_signals[:, mass_index]
                        
                        avg_count_per_second = np.mean(isotope_signal) / dwell_time
                        
                    else:
                        run_info = cached_data['run_info']
                        acqtime = run_info["SegmentInfo"][0]["AcquisitionPeriodNs"] * 1e-9
                        accumulations = run_info["NumAccumulations1"] * run_info["NumAccumulations2"]
                        dwell_time = acqtime * accumulations
                        
                        avg_count_per_second = np.mean(folder_signals[:, mass_index]) / dwell_time
                    
                    signals.append(avg_count_per_second)
                    valid_samples.append(sample_name)
                    
                except ValueError as e:
                    progress.close()
                    QMessageBox.warning(self, "Error", f"Invalid concentration for row {i+1}: {str(e)}")
                    return
                except Exception as e:
                    progress.close()
                    QMessageBox.warning(self, "Error", f"Failed to process cached data from row {i+1}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    return

            if len(concentrations) < 2:
                progress.close()
                QMessageBox.warning(self, "Insufficient Data", "Need at least 2 valid calibration points.")
                return

            progress.setValue(80)
            progress.setLabelText("Performing calibration calculation...")
            QApplication.processEvents()

            concentrations = np.array(concentrations)
            signals = np.array(signals)
            
            method = self.calibration_method_combo.currentText()
            results = self.perform_ionic_calibration(concentrations, signals, method)
            
            self.ionic_calibration_slope = results['slope']
            self.ionic_calibration_intercept = results['intercept']
            self.ionic_calibration_r_squared = results['r_squared']
            
            progress.setValue(90)
            progress.setLabelText("Updating plots...")
            QApplication.processEvents()
            
            progress.setValue(100)
            
            progress.close()
            
            if hasattr(self, 'view_toggle_button') and self.view_toggle_button is not None:
                try:
                    self.view_toggle_button.setEnabled(True)
                except RuntimeError:
                    print("Warning: Toggle button was deleted, skipping enable")
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(self, "Calibration Error", f"Error during calibration: {str(e)}")
            import traceback
            print("Full error traceback:")
            traceback.print_exc()

    def convert_concentration_to_ppb(self, value, unit):
        """
        Convert concentration to ppb.
        
        Args:
            value: Concentration value
            unit: Unit string (ppb, ppm, ppt, etc.)
            
        Returns:
            Concentration value in ppb
        """
        conversion_factors = {
            "ppt": 0.001,
            "ng/L": 0.001, 
            "ppb": 1.0,
            "µg/L": 1.0,
            "ppm": 1000.0,
            "mg/L": 1000.0
        }
        return value * conversion_factors.get(unit, 1.0)

    def perform_ionic_calibration(self, x, y, method):
        """
        Perform calibration using specified method.
        
        Args:
            x: Concentration array
            y: Signal array
            method: Calibration method name
            
        Returns:
            Dictionary containing slope, intercept, r_squared, and method
        """
        if method == "Force through zero":
            slope = np.sum(x * y) / np.sum(x * x)
            y_fit = slope * x
            ss_res = np.sum((y - y_fit)**2)
            ss_tot = np.sum(y**2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            intercept = 0
            
        elif method == "Simple linear":
            from scipy import stats
            slope, intercept, r_value, _, _ = stats.linregress(x, y)
            r_squared = r_value**2
            
        elif method == "Weighted":
            weights = 1 / (y + 1)
            weights = weights / np.sum(weights)
            
            W = np.diag(weights)
            X = np.vstack([x, np.ones(len(x))]).T
            try:
                coeffs = np.linalg.inv(X.T @ W @ X) @ X.T @ W @ y
                slope, intercept = coeffs[0], coeffs[1]
                
                y_fit = slope * x + intercept
                ss_res = np.sum(weights * (y - y_fit)**2)
                ss_tot = np.sum(weights * (y - np.mean(y))**2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            except:
                from scipy import stats
                slope, intercept, r_value, _, _ = stats.linregress(x, y)
                r_squared = r_value**2
        
        return {
            'slope': slope,
            'intercept': intercept,
            'r_squared': r_squared,
            'method': method
        }
            
    def calculate_transport_rate(self):
        """
        Calculate transport rate based on particle and ionic calibrations.
        
        Combines particle and ionic calibration slopes to determine transport rate,
        calculates particle size distributions, and updates results displays.
        """
        if not hasattr(self, 'particle_calibration_slope') or not hasattr(self, 'ionic_calibration_slope'):
            QMessageBox.warning(self, "Error", "Please perform both particle and ionic calibrations first.")
            return

        progress_dialog = QDialog(self)
        progress_dialog.setWindowTitle("Calculating Transport Rate")
        progress_layout = QVBoxLayout(progress_dialog)
        
        progress_label = QLabel("Calculating transport rate...")
        progress_layout.addWidget(progress_label)
        
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(20)
        progress_layout.addWidget(progress_bar)
        
        progress_dialog.setModal(True)
        progress_dialog.show()
        QApplication.processEvents()

        try:
            ionic_calibration_unit = self.concentration_table.cellWidget(0, 2).currentText()

            adjusted_ionic_slope = self.ionic_calibration_slope
            if ionic_calibration_unit in ["ppb", "µg/L"]:
                adjusted_ionic_slope /= 1000

            transport_rate = adjusted_ionic_slope / self.particle_calibration_slope

            conversion_factor = adjusted_ionic_slope / transport_rate
            
            self.calibration_completed.emit("Mass Method", transport_rate)

            self.transport_rate_table.setRowCount(0)

            self.transport_rate_table.insertRow(0)
            self.transport_rate_table.setItem(0, 0, QTableWidgetItem(f"{self.particle_calibration_slope:.2e} counts/fg"))
            self.transport_rate_table.setItem(0, 1, QTableWidgetItem(f"{self.ionic_calibration_slope:.2e} counts/s per {ionic_calibration_unit}"))
            self.transport_rate_table.setItem(0, 2, QTableWidgetItem(f"{transport_rate:.4f}"))
            self.transport_rate_table.setItem(0, 3, QTableWidgetItem(f"{self.ionic_calibration_r_squared:.4f}"))

            all_diameters = {}
            folder_count = len(self.particle_folder_paths)
            
            progress_label.setText("Calculating particle masses and diameters...")
            progress_bar.setValue(40)
            QApplication.processEvents()
            
            default_element_density = 0
            if hasattr(self, 'selected_element') and self.selected_element:
                default_element_density = self.selected_element.get('density', 0)
            
            for folder_index, folder_path in enumerate(self.particle_folder_paths):
                folder_name = Path(folder_path).name
                progress_label.setText(f"Processing folder {folder_index+1}/{folder_count}: {folder_name}")
                progress_bar.setValue(40 + (40 * folder_index // folder_count))
                QApplication.processEvents()
                
                if folder_path not in self.detected_particles or not self.detected_particles[folder_path]:
                    continue
                
                density = self.folder_densities.get(folder_path, self.default_density)
        
                if density <= 0:
                    density = default_element_density

                if density <= 0:
                    print(f"Warning: Skipping folder {folder_name} - no valid density available")
                    continue
                    
                folder_diameters = []
                
                particles = self.detected_particles[folder_path]
                for particle in particles:
                    if particle is None:
                        continue
                        
                    total_counts = particle['total_counts']
                    
                    if total_counts <= 0:
                        continue
                    
                    try:
                        mass_fg = total_counts / conversion_factor
                        
                        volume_cm3 = (mass_fg * 1e-15) / density
                        
                        if volume_cm3 <= 0:
                            continue
                            
                        diameter_nm = 2 * (3 * volume_cm3 / (4 * np.pi))**(1/3) * 1e7
                        
                        if diameter_nm > 0 and not np.isnan(diameter_nm) and not np.isinf(diameter_nm):
                            folder_diameters.append(diameter_nm)
                        
                    except (ZeroDivisionError, ValueError, OverflowError) as e:
                        print(f"Warning: Error calculating diameter for particle in {folder_name}: {e}")
                        continue
                        
                if folder_diameters:
                    all_diameters[folder_name] = folder_diameters
            
            progress_label.setText("Generating diameter distribution plot...")
            progress_bar.setValue(90)
            QApplication.processEvents()
            
            self.plot_multiple_diameter_distributions(all_diameters)
            
            progress_dialog.close()
            
            valid_folders = len(all_diameters)
            total_particles = sum(len(diameters) for diameters in all_diameters.values())
            
        except Exception as e:
            progress_dialog.close()
            QMessageBox.critical(self, "Transport Rate Error", f"Error calculating transport rate: {str(e)}")

    def plot_multiple_diameter_distributions(self, all_diameters):
        """
        Plot histogram of particle diameters for multiple files with statistics.
        
        Args:
            all_diameters: Dictionary mapping folder names to lists of particle diameters
            
        Creates overlaid histogram plot with color coding, legend, and statistics panel.
        """
        self.diameter_distribution_plot.clear()
        
        if not all_diameters:
            self.diameter_distribution_plot.setTitle("No particle data available")
            return
        
        colors = [(30, 144, 255, 180),   
                (50, 205, 50, 180),     
                (255, 69, 0, 180),      
                (147, 112, 219, 180),   
                (255, 215, 0, 180),     
                (0, 191, 255, 180),     
                (255, 127, 80, 180),    
                (32, 178, 170, 180)]    
        
        legend_items = []
        
        all_stats = {}
        combined_diameters = []
        
        global_min = float('inf')
        global_max = float('-inf')
        
        for folder_idx, (folder_name, diameters) in enumerate(all_diameters.items()):
            if not diameters:
                continue
                
            color_idx = folder_idx % len(colors)
            color = colors[color_idx]
            
            global_min = min(global_min, min(diameters))
            global_max = max(global_max, max(diameters))
            
            combined_diameters.extend(diameters)
            
            y, x = np.histogram(diameters, bins=30)
            x = (x[:-1] + x[1:]) / 2
            
            bargraph = pg.BarGraphItem(x=x, height=y, width=(x[1]-x[0])*0.8, brush=pg.mkBrush(*color), name=folder_name)
            self.diameter_distribution_plot.addItem(bargraph)
            
            legend_items.append((bargraph, folder_name))
            
            stats = {
                'mean': np.mean(diameters),
                'median': np.median(diameters),
                'std': np.std(diameters),
                'min': np.min(diameters),
                'max': np.max(diameters),
                'count': len(diameters),
                'p10': np.percentile(diameters, 10),
                'p90': np.percentile(diameters, 90)
            }
            all_stats[folder_name] = stats
        
        legend = self.diameter_distribution_plot.addLegend()
        for item, name in legend_items:
            legend.addItem(item, name)
        
        stats_text = "Size Distribution Statistics:\n\n"
        for folder_name, stats in all_stats.items():
            stats_text += f"{folder_name}:\n"
            stats_text += f"  Mean: {stats['mean']:.2f} nm\n"
            stats_text += f"  Median: {stats['median']:.2f} nm\n"
            stats_text += f"  Range: {stats['min']:.1f} - {stats['max']:.1f} nm\n"
            stats_text += f"  Count: {stats['count']}\n"
        
        text_item = pg.TextItem(
            text=stats_text,
            color='k',
            anchor=(1, 0),
            border=pg.mkPen('k'),
            fill=pg.mkBrush(255, 255, 255, 220)
        )
        self.diameter_distribution_plot.addItem(text_item)
        
        view_box = self.diameter_distribution_plot.getViewBox()
        view_range = view_box.viewRange()
        if view_range and len(view_range) >= 2:
            x_max = view_range[0][1]
            y_max = view_range[1][1]
            text_item.setPos(x_max - 20, y_max - 20)
        else:
            text_item.setPos(global_max, 0)
        
        self.diameter_distribution_plot.setLabel('left', 'Particles')
        self.diameter_distribution_plot.setLabel('bottom', 'Diameter (nm)')
        self.diameter_distribution_plot.setTitle("Particle Size Distribution (Multiple Files)")
        self.diameter_distribution_plot.showGrid(x=True, y=True, alpha=0.3)
        
        x_padding = (global_max - global_min) * 0.1
        self.diameter_distribution_plot.setXRange(global_min - x_padding, global_max + x_padding)

    def export_to_csv(self):
        """
        Export detection results to CSV file.
        
        Opens file dialog for saving location and writes all detection results
        from the results table to a CSV file.
        """
        if self.results_table.rowCount() == 0:
            QMessageBox.warning(self, "Export Error", "No results to export.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Detection Results", 
            "", 
            "CSV Files (*.csv)"
        )
        
        if not file_path:
            return
            
        if not file_path.endswith('.csv'):
            file_path += '.csv'
            
        try:
            with open(file_path, mode='w', newline='') as file:
                writer = csv.writer(file)
                
                headers = []
                for col in range(self.results_table.columnCount()):
                    headers.append(self.results_table.horizontalHeaderItem(col).text())
                writer.writerow(headers)
                
                for row in range(self.results_table.rowCount()):
                    row_data = []
                    for col in range(self.results_table.columnCount()):
                        item = self.results_table.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
                
            QMessageBox.information(self, "Export Successful", f"Results exported to {file_path}")
        
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error exporting results: {str(e)}")
    

if __name__ == '__main__':
    app = QApplication([])
    window = MassMethodWidget()
    window.showMaximized()
    app.exec()