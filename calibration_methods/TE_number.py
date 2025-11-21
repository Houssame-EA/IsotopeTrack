import numpy as np
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QLineEdit, QComboBox, QMessageBox, QFileDialog,
                               QTableWidget, QTableWidgetItem, QSplitter, QHeaderView,
                               QDoubleSpinBox, QGroupBox, QFormLayout, QSpinBox,
                               QMainWindow, QScrollArea, QApplication, QTabWidget, 
                               QCheckBox, QDialog, QFrame, QProgressBar, QGridLayout,
                               QListView, QTreeView, QAbstractItemView, QProgressDialog, 
                               QRadioButton, QListWidget)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QIcon, QColor
from widget.periodic_table_widget import PeriodicTableWidget
import data_loading.vitesse_loading
import pyqtgraph as pg
from widget.numeric_table import NumericTableWidgetItem
from widget.custom_plot_widget import EnhancedPlotWidget
from processing.peak_detection import PeakDetection 
import csv
from pathlib import Path
import json
from data_loading.data_thread import DataProcessThread 
import data_loading.tofwerk_loading
try:
    from data_loading.import_csv_dialogs import CSVStructureDialog, CSVDataProcessThread, show_csv_structure_dialog
except ImportError:
    CSVStructureDialog = None
    CSVDataProcessThread = None
    show_csv_structure_dialog = None
    

class NumberMethodWidget(QMainWindow):
    calibration_completed = Signal(str, float)
    
    def __init__(self, parent=None):
        """
        Initialize the Number Method Widget for particle-based calibration.
        
        Args:
            parent: Parent widget for this window
        """
        super().__init__(parent)
        self.peak_detector = PeakDetection()

        self.folder_paths = []
        self.folder_data = {}  
        self.all_masses = None
        self.selected_element = None
        self.detection_results = {}  
        self.calibration_samples = {} 
        self.current_highlighted_particle = None
        self.sample_name_to_folder = {}

        self.periodic_table_widget = None
        self.selected_isotopes = {}
        
        self.csv_config = None 
        self.pending_csv_processing = False
        
        self.initUI()
        
    def initUI(self):
        """
        Initialize and configure the user interface.
        
        Sets up stylesheets, creates tab widget with three tabs for data management,
        detection/analysis, and calibration.
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
                background-color: #e9ecef;
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
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        
        self.create_data_management_tab()
        self.create_analysis_results_tab()
        self.create_calibration_tab()
        
        main_layout.addWidget(self.tab_widget)
        
        self.setWindowTitle("Particle Method Analysis")
        self.setMinimumSize(1100, 800)

        
    def create_data_management_tab(self):
        """
        Create the data management tab for folder selection and sample overview.
        
        Sets up folder/file selection interface, sample overview table, and element
        selection controls within a scrollable area.
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
        
        folder_group = QGroupBox("1. Sample Data Selection")
        folder_layout = QVBoxLayout(folder_group)
        folder_layout.setSpacing(10)
        
        instruction_label = QLabel(
            "Select multiple folders containing particle analysis data. Each folder represents one sample."
        )
        instruction_label.setWordWrap(True)
        instruction_label.setStyleSheet("color: #6c757d; font-style: italic;")
        folder_layout.addWidget(instruction_label)
        
        folder_button_layout = QHBoxLayout()
        folder_button = QPushButton("Select Sample Folders")
        folder_button.clicked.connect(self.select_folders)
        folder_button.setMaximumWidth(200)
        
        self.folder_status_label = QLabel("No folders selected")
        self.folder_status_label.setStyleSheet("font-weight: bold; color: #6c757d;")
        
        folder_button_layout.addWidget(folder_button)
        folder_button_layout.addWidget(self.folder_status_label)
        folder_button_layout.addStretch()
        
        folder_layout.addLayout(folder_button_layout)
        
        self.sample_table = QTableWidget()
        self.sample_table.setColumnCount(3)
        self.sample_table.setHorizontalHeaderLabels(["Sample Name", "Folder Path", "Status"])
        self.sample_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.sample_table.horizontalHeader().setStretchLastSection(True)
        self.sample_table.setAlternatingRowColors(True)
        self.sample_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sample_table.setMinimumHeight(200)
        
        folder_layout.addWidget(self.sample_table)
        
        scroll_layout.addWidget(folder_group)
        
        element_group = QGroupBox("2. Element Selection")
        element_layout = QVBoxLayout(element_group)
        element_layout.setSpacing(10)
        
        element_selection_layout = QHBoxLayout()
        
        self.element_button = QPushButton("Open Periodic Table")
        self.element_button.clicked.connect(self.show_periodic_table)
        self.element_button.setMaximumWidth(200)
        self.element_button.setEnabled(False)
        
        self.element_selection_label = QLabel("Selected Element: None")
        self.element_selection_label.setStyleSheet("font-weight: bold; color: #6c757d;")
        
        element_selection_layout.addWidget(QLabel("Element:"))
        element_selection_layout.addWidget(self.element_button)
        element_selection_layout.addWidget(self.element_selection_label)
        element_selection_layout.addStretch()
        
        element_layout.addLayout(element_selection_layout)
        
        scroll_layout.addWidget(element_group)
        
        scroll_layout.addStretch()
        
        layout.addWidget(scroll)
        
        self.tab_widget.addTab(data_tab, "Data Management")
    
    def create_analysis_results_tab(self):
        """
        Create combined detection setup and analysis results tab.
        
        Sets up detection parameter configuration table, sample visualization plot,
        and detection results table with particle highlighting functionality.
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
        global_method_combo.addItems(["Currie", "Formula_C", "Compound Poisson LogNormal", "Manual"])
        global_method_combo.setCurrentText("Compound Poisson LogNormal")
        
        apply_global_button = QPushButton("Apply to All Samples")
        apply_global_button.clicked.connect(lambda: self.apply_global_detection_params(global_method_combo.currentText()))
        
        global_controls_layout.addWidget(QLabel("Global Method:"))
        global_controls_layout.addWidget(global_method_combo)
        global_controls_layout.addWidget(apply_global_button)
        global_controls_layout.addStretch()
        
        detection_layout.addLayout(global_controls_layout)
        
        self.detection_params_table = QTableWidget()
        self.detection_params_table.setColumnCount(9)
        headers = ['Sample Name', 'Element', 'Detection Method', 'Manual Threshold', 'Apply Smoothing', 
                  'Window Length', 'Smoothing Iterations', 'Min Points', 'Alpha']
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
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels([
            'Sample Name', 'Peak Start (s)', 'Peak End (s)', 'Total Counts'
        ])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        self.results_table.itemSelectionChanged.connect(self.highlight_selected_particle)
        self.results_table.setMinimumHeight(250)
        
        results_layout.addWidget(self.results_table)
        
        export_button = QPushButton("Export Results to CSV")
        export_button.clicked.connect(self.export_results_to_csv)
        export_button.setMaximumWidth(200)
        results_layout.addWidget(export_button, alignment=Qt.AlignRight)
        
        scroll_layout.addWidget(results_group)
        scroll_layout.addStretch()
        
        layout.addWidget(scroll)
        self.tab_widget.addTab(analysis_tab, "Detection & Analysis")

    def create_calibration_tab(self):
        """
        Create enhanced calibration tab with multiple sample support.
        
        Sets up calibration data table with particle properties, calculation controls,
        results display table, and summary statistics section.
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
        
        calib_data_group = QGroupBox("1. Sample Calibration Data")
        calib_data_layout = QVBoxLayout(calib_data_group)
        calib_data_layout.setSpacing(10)
        
        instruction_label = QLabel(
            "Calibration parameters are automatically filled when samples are loaded and detection is completed. "
            "Default values: 100nm particle diameter, 400 ng/L concentration. "
            "Modify values as needed for your specific calibration standards."
        )
        instruction_label.setWordWrap(True)
        instruction_label.setStyleSheet("color: #6c757d; font-style: italic;")
        calib_data_layout.addWidget(instruction_label)
        
        self.calibration_data_table = QTableWidget()
        self.calibration_data_table.setColumnCount(7)
        self.calibration_data_table.setHorizontalHeaderLabels([
            'Sample Name', 'Particles Detected', 'Particle Diameter (nm)', 
            'Concentration (ng/L)', 'Acquisition Time (s)', 'Element Density (g/cm³)', 'Use for Calibration'
        ])
        
        calibration_column_widths = [150, 120, 130, 130, 120, 130, 120]
        for i, width in enumerate(calibration_column_widths):
            self.calibration_data_table.setColumnWidth(i, width)
        
        self.calibration_data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.calibration_data_table.setAlternatingRowColors(True)
        self.calibration_data_table.setMinimumHeight(200)
        
        calib_data_layout.addWidget(self.calibration_data_table)
        
        scroll_layout.addWidget(calib_data_group)
        
        calc_group = QGroupBox("2. Transport Rate Calculation")
        calc_layout = QVBoxLayout(calc_group)
        calc_layout.setSpacing(10)
        
        calculate_button = QPushButton("Calculate Transport Rates")
        calculate_button.clicked.connect(self.calculate_transport_rates)
        calculate_button.setMinimumHeight(40)
        
        calc_layout.addWidget(calculate_button)
        
        self.calibration_results_table = QTableWidget()
        self.calibration_results_table.setColumnCount(6)
        self.calibration_results_table.setHorizontalHeaderLabels([
            'Sample Name', 'Transport Rate (µL/s)', 'Particles/mL', 'Particle Mass (fg)',
            'Particle Volume (nm³)', 'Calculation Status'
        ])
        self.calibration_results_table.horizontalHeader().setStretchLastSection(True)
        self.calibration_results_table.setAlternatingRowColors(True)
        self.calibration_results_table.setMinimumHeight(150)
        
        calc_layout.addWidget(self.calibration_results_table)
        
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("""
            background-color: #e8f4f8; 
            border-radius: 4px; 
            padding: 15px; 
            font-weight: bold;
            font-size: 14px;
        """)
        self.summary_label.setWordWrap(True)
        self.summary_label.setAlignment(Qt.AlignCenter)
        calc_layout.addWidget(self.summary_label)
        
        scroll_layout.addWidget(calc_group)
        scroll_layout.addStretch()
        
        layout.addWidget(scroll)
        self.tab_widget.addTab(calibration_tab, "Calibration")
        
    def select_folders(self):
        """
        Enhanced folder/file selection matching main window structure.
        
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
            self.folder_paths = []
            self.folder_data = {}
            self.sample_name_to_folder = {}
            
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
                    
                    # Get masses only
                    try:
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
            
            self.folder_paths = valid_files
            
            if all_masses_from_files:
                self.all_masses = sorted(list(set(all_masses_from_files)))
            else:
                self.all_masses = []
            
            progress.setValue(90)
            progress.setLabelText("Updating interface...")
            QApplication.processEvents()
            
            self.update_sample_table()
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
            self.folder_paths = []
            self.folder_data = {}
            self.sample_name_to_folder = {}

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
                    
                self.handle_folder_import(selected_paths)
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error selecting folders: {str(e)}")

    def select_data_files(self):
        """
        Handle data file selection for CSV, TXT, and Excel formats.
        
        Opens file dialog for selecting multiple data files and initiates
        CSV import process with structure configuration.
        """
        try:
            if not show_csv_structure_dialog:
                QMessageBox.critical(self, "Import Error", 
                    "Data file import functionality is not available. Please ensure the import_csv_dialogs.py file is present.")
                return
                    
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Select Data Files for Particle Analysis",
                "",
                "Data Files (*.csv *.txt *.xls *.xlsx *.xlsm *.xlsb);;CSV Files (*.csv);;Text Files (*.txt);;Excel Files (*.xls *.xlsx *.xlsm *.xlsb);;All Files (*)"
            )
            
            if file_paths:
                self.handle_csv_import(file_paths)
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error selecting data files: {str(e)}")
        
    
    def handle_folder_import(self, selected_paths):
        """
        Handle folder import - simplified logic without mass validation.
        
        Args:
            selected_paths: List of folder paths to import
            
        Validates folders, extracts run.info data, and initializes folder_data structure
        for each valid sample.
        """
        try:
            self.folder_paths = []
            self.folder_data = {}
            self.sample_name_to_folder = {}
            
            progress = QProgressDialog("Processing selected folders...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            QApplication.processEvents()
            
            progress.setLabelText("Validating folders...")
            progress.setValue(10)
            QApplication.processEvents()
            
            valid_folders = []
            all_masses_from_folders = []
            
            for i, folder_path in enumerate(selected_paths):
                if progress.wasCanceled():
                    return
                    
                folder_progress = 10 + int((i / len(selected_paths)) * 70)
                progress.setValue(folder_progress)
                progress.setLabelText(f"Checking {Path(folder_path).name}...")
                QApplication.processEvents()
                
                try:
                    run_info_path = Path(folder_path) / "run.info"
                    if not run_info_path.exists():
                        raise FileNotFoundError(f"run.info not found in {folder_path}")
                    
                    with open(run_info_path, "r") as fp:
                        run_info = json.load(fp)
                    
                    sample_name = run_info.get("SampleName", Path(folder_path).name)
                    
                    try:
                        masses = DataProcessThread.get_masses_only(str(folder_path))
                        all_masses_from_folders.extend(masses)
                    except Exception as mass_error:
                        print(f"Warning: Could not get masses from {folder_path}: {mass_error}")
                        masses = []
                    
                    self.folder_data[folder_path] = {
                        'masses': masses,
                        'status': 'Loaded',
                        'sample_name': sample_name,
                        'data_loaded': False
                    }
                    
                    self.sample_name_to_folder[sample_name] = folder_path
                    valid_folders.append(folder_path)
                    
                except Exception as e:
                    sample_name = Path(folder_path).name
                    self.folder_data[folder_path] = {
                        'status': f'Error: {str(e)}',
                        'sample_name': sample_name,
                        'data_loaded': False
                    }
                    self.sample_name_to_folder[sample_name] = folder_path
                    
                    print(f"Warning: Error loading {sample_name}: {str(e)}")
                    continue
            
            progress.setValue(80)
            progress.setLabelText("Finalizing setup...")
            QApplication.processEvents()
            
            if not valid_folders:
                raise ValueError("No valid folders were found. Please check that the selected folders contain run.info files.")
            
            self.folder_paths = valid_folders
            
            if all_masses_from_folders:
                self.all_masses = sorted(list(set(all_masses_from_folders)))
            else:
                self.all_masses = []
            
            progress.setValue(90)
            progress.setLabelText("Updating interface...")
            QApplication.processEvents()
            
            self.update_sample_table()
            self.enable_ui_elements()
            
            progress.setValue(100)
            progress.close()
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(
                self,
                "Import Error",
                f"Error importing folders: {str(e)}"
            )
            self.folder_paths = []
            self.folder_data = {}
            self.sample_name_to_folder = {}
            
    def handle_csv_import(self, file_paths):
        """
        Handle CSV file import with configuration dialog.
        
        Args:
            file_paths: List of CSV file paths to import
            
        Shows CSV structure configuration dialog and initiates the import process
        with selected isotopes.
        """
        try:
            config = show_csv_structure_dialog(file_paths, self)
            
            if config:
                self.csv_config = config
                self.pending_csv_processing = True
                
                self.extract_masses_from_csv_config(config)
                
                self.show_periodic_table_after_csv_config()
            
        except Exception as e:
            QMessageBox.critical(self, "CSV Import Error", f"Error importing CSV files: {str(e)}")

    def extract_masses_from_csv_config(self, config):
        """
        Extract available masses from CSV configuration.
        
        Args:
            config: CSV configuration dictionary containing file mappings
            
        Collects all unique isotope masses from the CSV configuration and stores
        them in all_masses for periodic table display.
        """
        masses = []
        
        for file_config in config['files']:
            for mapping in file_config['mappings'].values():
                isotope = mapping['isotope']
                masses.append(isotope['mass'])
        
        self.all_masses = sorted(list(set(masses)))
        
        self.folder_paths = []

    def show_periodic_table_after_csv_config(self):
        """
        Show periodic table after CSV configuration.
        
        Creates or updates the periodic table widget with available masses from
        CSV configuration and displays it for isotope selection.
        """
        if not self.periodic_table_widget:
            self.periodic_table_widget = PeriodicTableWidget()
            self.periodic_table_widget.selection_confirmed.connect(self.handle_isotopes_selected)
        
        if hasattr(self, 'all_masses') and self.all_masses:
            self.periodic_table_widget.update_available_masses(self.all_masses)
        
        self.periodic_table_widget.show()
        self.periodic_table_widget.raise_()

    def process_csv_files_with_isotopes(self, selected_isotopes):
        """
        Process CSV files with selected isotopes.
        
        Args:
            selected_isotopes: Dictionary mapping element symbols to selected isotope masses
            
        Filters CSV configuration to include only selected isotopes and initiates
        background processing thread.
        """
        try:
            if not self.csv_config:
                raise ValueError("No CSV configuration available")
            
            filtered_config = self.filter_csv_config_by_isotopes(self.csv_config, selected_isotopes)
            
            if not any(file_config['mappings'] for file_config in filtered_config['files']):
                QMessageBox.warning(self, "No Matching Isotopes", 
                                "None of the selected isotopes match the configured CSV columns.")
                return
            
            self.sample_name_to_folder = {}
            self.folder_data = {}
            self.folder_paths = []
            
            progress = QProgressDialog("Processing CSV files...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            
            self.csv_thread = CSVDataProcessThread(filtered_config, self)
            self.csv_thread.progress.connect(progress.setValue)
            self.csv_thread.finished.connect(self.handle_csv_finished)
            self.csv_thread.error.connect(self.handle_csv_error)
            self.csv_thread.start()
            
            while self.csv_thread.isRunning():
                QApplication.processEvents()
                if progress.wasCanceled():
                    self.csv_thread.terminate()
                    break
            
            progress.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error processing CSV files: {str(e)}")

    def filter_csv_config_by_isotopes(self, config, selected_isotopes):
        """
        Filter CSV configuration to only include selected isotopes.
        
        Args:
            config: Original CSV configuration dictionary
            selected_isotopes: Dictionary mapping element symbols to selected isotope masses
            
        Returns:
            Filtered configuration containing only mappings for selected isotopes
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

    def handle_csv_finished(self, data, run_info, time_array, sample_name, datetime_str):
        """
        Handle completion of CSV processing.
        
        Args:
            data: Dictionary mapping masses to signal arrays
            run_info: Run information dictionary
            time_array: Time array for the data
            sample_name: Name of the sample
            datetime_str: Analysis datetime string
            
        Converts CSV data to internal format and updates UI when all files are processed.
        """
        try:
            csv_file_path = run_info.get('OriginalFile', sample_name)
            
            self.folder_data[csv_file_path] = {
                'masses': list(data.keys()),
                'status': 'Loaded',
                'sample_name': sample_name,
                'data_loaded': True,
                'isotope_signal': None,
                'time_array': time_array.copy(),
                'dwell_time': run_info.get('DwellTimeMs', 10.0) / 1000.0,
                'total_acquisition_time': time_array[-1] if len(time_array) > 0 else 0,
                'csv_data': data.copy(),
                'run_info': run_info.copy()
            }
            
            self.sample_name_to_folder[sample_name] = csv_file_path
            self.folder_paths.append(csv_file_path)
            
            print(f"CSV sample '{sample_name}' processed successfully")
            
            expected_files = len(self.csv_config['files']) if self.csv_config else 0
            processed_files = len([s for s in self.sample_name_to_folder.values() if str(s).endswith('.csv')])
            
            if processed_files >= expected_files:
                self.pending_csv_processing = False
                self.csv_config = None
                
                self.update_sample_table()
                self.enable_ui_elements()
                
                print(f"All CSV files processed successfully ({processed_files} samples)")
                
        except Exception as e:
            print(f"Error processing CSV data for {sample_name}: {str(e)}")

    def handle_csv_error(self, error_message):
        """
        Handle CSV processing errors.
        
        Args:
            error_message: Error message from CSV processing thread
            
        Displays error dialog and resets CSV processing state.
        """
        QMessageBox.critical(self, "CSV Processing Error", f"Error processing CSV file: {error_message}")
        self.pending_csv_processing = False
        self.csv_config = None
    
    def update_sample_table(self):
        """
        Update the sample overview table - supports folders, CSV files, and TOFWERK files.
        
        Populates the sample table with sample names, paths, and status information,
        with appropriate icons and color coding for different data sources.
        """
        self.sample_table.setRowCount(len(self.folder_paths))
        
        for i, folder_path in enumerate(self.folder_paths):
            sample_name = self.folder_data[folder_path].get('sample_name', Path(folder_path).name)
            
            sample_item = QTableWidgetItem(sample_name)
            sample_item.setFlags(sample_item.flags() & ~Qt.ItemIsEditable)
            self.sample_table.setItem(i, 0, sample_item)
            
            if str(folder_path).lower().endswith(('.csv', '.txt', '.xls', '.xlsx', '.xlsm', '.xlsb')):
                path_display = f"📄 {Path(folder_path).name}"
            elif str(folder_path).lower().endswith('.h5'):
                path_display = f"⚗️ {Path(folder_path).name}"
            else:
                path_display = f"📁 {str(folder_path)}"
                
            path_item = QTableWidgetItem(path_display)
            path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
            self.sample_table.setItem(i, 1, path_item)
            
            status = self.folder_data[folder_path].get('status', 'Unknown')
            if 'csv_data' in self.folder_data[folder_path]:
                status += " (CSV)"
            elif self.folder_data[folder_path].get('is_tofwerk'):
                status += " (TOFWERK)"
            elif status == 'Loaded':
                status += " (Folder)"
                
            status_item = QTableWidgetItem(status)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            
            if 'Loaded' in status:
                status_item.setBackground(QColor(200, 255, 200))
            else:
                status_item.setBackground(QColor(255, 200, 200))
                    
            self.sample_table.setItem(i, 2, status_item)
        
        valid_count = len([f for f in self.folder_paths if 'Loaded' in self.folder_data[f].get('status', '')])
        csv_count = len([f for f in self.folder_paths if 'csv_data' in self.folder_data[f]])
        tofwerk_count = len([f for f in self.folder_paths if self.folder_data[f].get('is_tofwerk')])
        folder_count = valid_count - csv_count - tofwerk_count
        
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
        valid samples for visualization.
        """
        self.element_button.setEnabled(True)
        
        self.sample_combo.clear()
        for folder_path in self.folder_paths:
            if self.folder_data[folder_path].get('status') == 'Loaded':
                sample_name = self.folder_data[folder_path].get('sample_name', Path(folder_path).name)
                self.sample_combo.addItem(sample_name, folder_path)

    def show_periodic_table(self):
        """
        Show periodic table - handle case where masses aren't loaded yet.
        
        Attempts to retrieve available masses if not already loaded, then displays
        the periodic table widget for element and isotope selection.
        """
        if (not self.all_masses or len(self.all_masses) == 0) and self.folder_paths:
            try:
                for folder_path in self.folder_paths:
                    if self.folder_data[folder_path].get('status') == 'Loaded':
                        try:
                            masses = DataProcessThread.get_masses_only(str(folder_path))
                            if masses:
                                self.all_masses = sorted(list(set(masses)))
                                break
                        except Exception as e:
                            print(f"Could not get masses from {folder_path}: {e}")
                            continue
            except Exception as e:
                print(f"Error getting masses for periodic table: {e}")
        
        if not self.all_masses or len(self.all_masses) == 0:
            QMessageBox.warning(
                self,
                "No Mass Data",
                "Could not determine available masses from the loaded folders.\n"
                "The periodic table will show all elements, but isotope availability may not be accurate."
            )
            self.all_masses = []
                
        if not self.periodic_table_widget:
            self.periodic_table_widget = PeriodicTableWidget()
            self.periodic_table_widget.selection_confirmed.connect(self.handle_isotopes_selected)
            
            if self.all_masses:
                self.periodic_table_widget.update_available_masses(self.all_masses)
                
            if self.selected_isotopes:
                self._update_periodic_table_selections()
        
        self.periodic_table_widget.show()
        self.periodic_table_widget.raise_()
            
    def handle_isotopes_selected(self, selected_isotopes):
        """
        Handle isotope selection from periodic table - supports both folders and CSV.
        
        Args:
            selected_isotopes: Dictionary mapping element symbols to lists of selected isotope masses
            
        Processes isotope selection differently for CSV files (triggering file processing)
        versus folders (loading element data directly).
        """
        try:
            self.selected_isotopes = selected_isotopes
            
            if self.pending_csv_processing and self.csv_config:
                self.process_csv_files_with_isotopes(selected_isotopes)
                return
            
            if selected_isotopes:
                first_element_symbol = next(iter(selected_isotopes.keys()))
                first_isotope_mass = selected_isotopes[first_element_symbol][0]
                
                if self.periodic_table_widget:
                    element_data = self.periodic_table_widget.get_element_by_symbol(first_element_symbol)
                    if element_data:
                        self.selected_element = element_data.copy()
                        self.selected_element['selected_isotope'] = first_isotope_mass
                        self.selected_element['selected_isotopes'] = [first_isotope_mass]
                        
                        isotope_data = next((iso for iso in element_data['isotopes'] 
                                        if isinstance(iso, dict) and iso['mass'] == first_isotope_mass), None)
                        abundance = isotope_data.get('abundance', 0) if isotope_data else 0
                        
                        self.element_selection_label.setText(
                            f"Selected Element: {first_element_symbol} - {int(round(first_isotope_mass))}{first_element_symbol} ({abundance:.1f}%)"
                        )
                        self.element_selection_label.setStyleSheet("font-weight: bold; color: #28a745;")
                        
                        self.load_element_data_for_all_samples()
                        self.update_detection_parameters_table()
                        self.update_calibration_data_table()
            else:
                self.selected_element = None
                self.element_selection_label.setText("Selected Element: None")
                self.element_selection_label.setStyleSheet("font-weight: bold; color: #6c757d;")
                
        except Exception as e:
            QMessageBox.critical(self, "Selection Error", f"Error processing isotope selection: {str(e)}")
            
    def _update_periodic_table_selections(self):
        """
        Helper method to efficiently update periodic table selections.
        
        Updates the periodic table widget to reflect currently selected isotopes
        for all selected elements.
        """
        for element_symbol, isotopes in self.selected_isotopes.items():
            if element_symbol in self.periodic_table_widget.buttons:
                button = self.periodic_table_widget.buttons[element_symbol]
                if button.isotope_display:
                    for isotope in isotopes:
                        button.isotope_display.select_preferred_isotope(isotope)
                        
    def load_element_data_for_all_samples(self):
        """
        Load element data for all samples - supports NU folders, CSV files, and TOFWERK files.
        
        Extracts signal data for the selected isotope from all valid samples, handling
        NU folder data, CSV file data, and TOFWERK file data appropriately.
        """
        if not self.selected_element or 'selected_isotope' not in self.selected_element:
            return
            
        selected_mass = self.selected_element['selected_isotope']
        
        progress = QProgressDialog("Loading element data for all samples...", "Cancel", 
                                0, len(self.folder_paths), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(500)
        
        for i, folder_path in enumerate(self.folder_paths):
            progress.setValue(i)
            sample_name = self.folder_data[folder_path].get('sample_name', Path(folder_path).name)
            progress.setLabelText(f"Processing {sample_name}...")
            QApplication.processEvents()
            
            if progress.wasCanceled():
                break
                
            if self.folder_data[folder_path].get('status') != 'Loaded':
                continue
                
            try:
                if 'csv_data' in self.folder_data[folder_path]:
                    csv_data = self.folder_data[folder_path]['csv_data']
                    time_array = self.folder_data[folder_path]['time_array']
                    
                    closest_mass = min(csv_data.keys(), key=lambda x: abs(x - selected_mass))
                    
                    if abs(closest_mass - selected_mass) < 1.0:
                        isotope_signal = csv_data[closest_mass]
                        
                        self.folder_data[folder_path].update({
                            'isotope_signal': isotope_signal,
                            'mass_index': list(csv_data.keys()).index(closest_mass),
                        })
                    else:
                        raise ValueError(f"No matching isotope found for mass {selected_mass}")
                
                elif self.folder_data[folder_path].get('is_tofwerk'):
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
                            'isotope_signal': isotope_signal,
                            'time_array': time_array,
                            'dwell_time': dwell_time,
                            'mass_index': mass_index,
                            'selected_mass': closest_mass,
                            'total_acquisition_time': time_array[-1] + dwell_time if len(time_array) > 0 else 0,
                            'data_loaded': True
                        })
                        
                        if not self.all_masses:
                            self.all_masses = sorted(list(masses))
                        
                    except Exception as load_error:
                        raise ValueError(f"Error loading TOFWERK data: {str(load_error)}")
                
                # Handle NU folder data
                else:
                    try:
                        masses, signals, run_info = data_loading.vitesse_loading.read_nu_directory(
                            path=folder_path,
                            autoblank=True,
                            raw=False
                        )
                        
                        mass_index = np.argmin(np.abs(masses - selected_mass))
                        closest_mass = masses[mass_index]
                        
                        if abs(closest_mass - selected_mass) > 1.0:
                            raise ValueError(f"No suitable isotope found for mass {selected_mass:.4f}. Closest available: {closest_mass:.4f}")
                        
                        isotope_signal = signals[:, mass_index]
                        
                        acqtime = run_info["SegmentInfo"][0]["AcquisitionPeriodNs"] * 1e-9
                        accumulations = run_info["NumAccumulations1"] * run_info["NumAccumulations2"]
                        dwell_time = acqtime * accumulations
                        time_array = np.arange(len(isotope_signal)) * dwell_time
                        
                        self.folder_data[folder_path].update({
                            'isotope_signal': isotope_signal,
                            'time_array': time_array,
                            'dwell_time': dwell_time,
                            'mass_index': mass_index,
                            'selected_mass': closest_mass,
                            'total_acquisition_time': time_array[-1] + dwell_time if len(time_array) > 0 else 0,
                            'data_loaded': True
                        })
                        
                        if not self.all_masses:
                            self.all_masses = sorted(list(masses))
                        
                    except Exception as load_error:
                        raise ValueError(f"Error loading data from folder: {str(load_error)}")
                    
            except Exception as e:
                error_msg = f"Error loading data for {sample_name}: {str(e)}"
                print(error_msg)
                QMessageBox.warning(self, "Data Loading Error", error_msg)
                self.folder_data[folder_path]['status'] = f'Error: {str(e)}'
                continue
        
        progress.setValue(len(self.folder_paths))
        
        self.update_sample_table()

    def on_detection_params_selection_changed(self):
        """
        Handle selection change in detection parameters table to show sample preview.
        
        Displays either raw signal or detection results for the selected sample row
        in the visualization plot.
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
            print(f"Debug: Could not find data for sample '{sample_name}'. Available samples: {list(self.sample_name_to_folder.keys())}")

    def plot_raw_signal_preview(self, folder_path, sample_name):
        """
        Plot raw signal preview for a sample.
        
        Args:
            folder_path: Path to the sample folder or file
            sample_name: Display name of the sample
            
        Displays the raw isotope signal without any detection processing.
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

    def update_detection_parameters_table(self):
        """
        Update detection parameters table with all samples.
        
        Populates the detection parameters table with default values for each sample
        including detection method, smoothing options, and threshold parameters.
        """
        if not self.selected_element:
            return
            
        valid_samples = [f for f in self.folder_paths if self.folder_data[f].get('status') == 'Loaded']
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
        Enable/disable smoothing parameters.
        
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
            
    def detect_particles_all_samples(self):
        """
        Detect particles for all samples with individual parameters.
        
        Performs particle detection on all valid samples using configured parameters
        from the detection table, stores results, and updates UI tables.
        """
        if not self.selected_element:
            QMessageBox.warning(self, "Detection Error", "Please select an element first.")
            return
            
        valid_samples = [f for f in self.folder_paths if self.folder_data[f].get('status') == 'Loaded']
        if not valid_samples:
            QMessageBox.warning(self, "Detection Error", "No valid samples available.")
            return
        
        self.detection_results.clear()
        
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
                
            except Exception as e:
                QMessageBox.warning(self, "Detection Error", 
                                  f"Error processing {sample_name}: {str(e)}")
                continue
        
        progress.setValue(len(valid_samples))
        
        self.update_results_table()
        self.auto_fill_calibration_data()
        
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
                'method': 'Compound Poisson LogNormal',
                'manual_threshold': 10.0,
                'apply_smoothing': False,
                'smooth_window': 3,
                'iterations': 1,
                'min_continuous': 1,
                'alpha': 0.000001
            }

    def update_results_table(self):
        """
        Update results table with all detection results (simplified to 4 columns).
        
        Populates the results table with detected particles from all samples,
        color-coded by signal-to-noise ratio for quality assessment.
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
                
                if height_threshold_ratio >= 3.0:
                    color = QColor(144, 238, 144)
                elif height_threshold_ratio >= 2.0:
                    color = QColor(255, 255, 224)
                elif height_threshold_ratio >= 1.0:
                    color = QColor(255, 239, 213)
                else:
                    color = QColor(255, 200, 200)
                
                for item in [sample_item, start_item, end_item, counts_item]:
                    item.setBackground(color)
                
                self.results_table.setItem(row_position, 0, sample_item)
                self.results_table.setItem(row_position, 1, start_item)
                self.results_table.setItem(row_position, 2, end_item)
                self.results_table.setItem(row_position, 3, counts_item)
        
        self.results_table.setSortingEnabled(True)
        self.results_table.sortItems(0, Qt.AscendingOrder)

    def highlight_selected_particle(self):
        """
        Zoom in on selected particle in plot.
        
        Retrieves particle data from selected table row, switches to the appropriate
        sample, and zooms the plot to highlight the selected particle.
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
            
        Draws a red highlight over the selected particle signal in the visualization.
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
        
        Displays detection results for the currently selected sample in the
        sample combo box.
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
            
        Creates comprehensive visualization showing raw signal, smoothed signal,
        background, threshold, and detected particles with SNR color coding.
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
        
    def update_calibration_data_table(self):
        """
        Update calibration data table with sample information and default values.
        
        Populates the calibration table with sample information, default particle
        properties (100nm diameter, 400ng/L concentration), and element density.
        """
        if not self.selected_element:
            return
            
        valid_samples = [f for f in self.folder_paths if self.folder_data[f].get('status') == 'Loaded']
        self.calibration_data_table.setRowCount(len(valid_samples))
        
        for i, folder_path in enumerate(valid_samples):
            sample_name = self.folder_data[folder_path].get('sample_name', Path(folder_path).name)
            
            sample_item = QTableWidgetItem(sample_name)
            sample_item.setFlags(sample_item.flags() & ~Qt.ItemIsEditable)
            self.calibration_data_table.setItem(i, 0, sample_item)
            
            particles_item = QTableWidgetItem("0")
            particles_item.setFlags(particles_item.flags() & ~Qt.ItemIsEditable)
            self.calibration_data_table.setItem(i, 1, particles_item)
            
            diameter_item = QTableWidgetItem("100")
            self.calibration_data_table.setItem(i, 2, diameter_item)
            
            concentration_item = QTableWidgetItem("400")
            self.calibration_data_table.setItem(i, 3, concentration_item)
            
            acq_time = self.folder_data[folder_path].get('total_acquisition_time', 0)
            acq_time_item = QTableWidgetItem(f"{acq_time:.2f}")
            acq_time_item.setFlags(acq_time_item.flags() & ~Qt.ItemIsEditable)
            self.calibration_data_table.setItem(i, 4, acq_time_item)
            
            density = self.selected_element.get('density', 0)
            density_item = QTableWidgetItem(f"{density:.4f}")
            self.calibration_data_table.setItem(i, 5, density_item)
            
            use_checkbox = QCheckBox()
            use_checkbox.setChecked(True)
            self.calibration_data_table.setCellWidget(i, 6, use_checkbox)

    def auto_fill_calibration_data(self):
        """
        Automatically fill calibration data from detection results.
        
        Updates the particle count column in the calibration table with the
        number of detected particles for each sample.
        """
        if not self.detection_results:
            return
        
        for row in range(self.calibration_data_table.rowCount()):
            sample_item = self.calibration_data_table.item(row, 0)
            if not sample_item:
                continue
                
            sample_name = sample_item.text()
            
            for folder_path, results in self.detection_results.items():
                if results['sample_name'] == sample_name:
                    particle_count = results['particle_count']
                    particles_item = QTableWidgetItem(str(particle_count))
                    particles_item.setFlags(particles_item.flags() & ~Qt.ItemIsEditable)
                    self.calibration_data_table.setItem(row, 1, particles_item)
                    break

    def calculate_transport_rates(self):
        """
        Calculate transport rates for all selected samples.
        
        Performs particle-based transport rate calculations using particle properties
        and concentration data, displays results in the results table, and emits
        the average transport rate via signal.
        """
        if not self.selected_element:
            QMessageBox.warning(self, "Calculation Error", "Please select an element first.")
            return
        
        self.calibration_results_table.setRowCount(0)
        transport_rates = []
        successful_calculations = []
        
        for row in range(self.calibration_data_table.rowCount()):
            use_checkbox = self.calibration_data_table.cellWidget(row, 6)
            if not use_checkbox or not use_checkbox.isChecked():
                continue
            
            try:
                sample_name = self.calibration_data_table.item(row, 0).text()
                particles_detected = int(self.calibration_data_table.item(row, 1).text())
                diameter_nm = float(self.calibration_data_table.item(row, 2).text())
                concentration_ng_l = float(self.calibration_data_table.item(row, 3).text())
                acquisition_time_s = float(self.calibration_data_table.item(row, 4).text())
                density_g_cm3 = float(self.calibration_data_table.item(row, 5).text())
                
                diameter_m = diameter_nm * 1e-9
                density_kg_m3 = density_g_cm3 * 1000
                
                particle_volume_m3 = (4/3) * np.pi * (diameter_m/2)**3
                particle_volume_nm3 = particle_volume_m3 * 1e27
                
                particle_mass_kg = particle_volume_m3 * density_kg_m3
                particle_mass_fg = particle_mass_kg * 1e18
                
                particles_per_liter = concentration_ng_l / (particle_mass_kg * 1e12)
                particles_per_ml = particles_per_liter / 1000
                
                if particles_per_ml > 0 and acquisition_time_s > 0:
                    transport_rate_ml_s = particles_detected / (particles_per_ml * acquisition_time_s)
                    transport_rate_ul_s = transport_rate_ml_s * 1000
                    status = "Success"
                else:
                    transport_rate_ul_s = 0
                    status = "Error: Invalid parameters"
                
                result_row = self.calibration_results_table.rowCount()
                self.calibration_results_table.insertRow(result_row)
                
                self.calibration_results_table.setItem(result_row, 0, QTableWidgetItem(sample_name))
                self.calibration_results_table.setItem(result_row, 1, QTableWidgetItem(f"{transport_rate_ul_s:.6f}"))
                self.calibration_results_table.setItem(result_row, 2, QTableWidgetItem(f"{particles_per_ml:.2f}"))
                self.calibration_results_table.setItem(result_row, 3, QTableWidgetItem(f"{particle_mass_fg:.3f}"))
                self.calibration_results_table.setItem(result_row, 4, QTableWidgetItem(f"{particle_volume_nm3:.3f}"))
                self.calibration_results_table.setItem(result_row, 5, QTableWidgetItem(status))
                
                if status == "Success":
                    transport_rates.append(transport_rate_ul_s)
                    successful_calculations.append({
                        'sample_name': sample_name,
                        'transport_rate': transport_rate_ul_s,
                        'particles_detected': particles_detected,
                        'particle_mass_fg': particle_mass_fg,
                        'particles_per_ml': particles_per_ml
                    })
                
            except Exception as e:
                result_row = self.calibration_results_table.rowCount()
                self.calibration_results_table.insertRow(result_row)
                
                try:
                    sample_name = self.calibration_data_table.item(row, 0).text()
                except:
                    sample_name = f"Sample {row+1}"
                
                self.calibration_results_table.setItem(result_row, 0, QTableWidgetItem(sample_name))
                self.calibration_results_table.setItem(result_row, 1, QTableWidgetItem("Error"))
                self.calibration_results_table.setItem(result_row, 2, QTableWidgetItem("Error"))
                self.calibration_results_table.setItem(result_row, 3, QTableWidgetItem("Error"))
                self.calibration_results_table.setItem(result_row, 4, QTableWidgetItem("Error"))
                self.calibration_results_table.setItem(result_row, 5, QTableWidgetItem(f"Error: {str(e)}"))
        
        if transport_rates:
            mean_rate = np.mean(transport_rates)
            std_rate = np.std(transport_rates)
            rsd_percent = (std_rate / mean_rate) * 100 if mean_rate > 0 else 0
            
            summary_text = f"""
            <div style="text-align: center;">
                <h3>Transport Rate Calibration Summary</h3>
                <table style="margin: auto; border-collapse: collapse;">
                    <tr><td style="padding: 5px; font-weight: bold;">Samples Used:</td><td style="padding: 5px;">{len(transport_rates)}</td></tr>
                    <tr><td style="padding: 5px; font-weight: bold;">Average Transport Rate:</td><td style="padding: 5px; color: blue;">{mean_rate:.6f} ± {std_rate:.6f} µL/s</td></tr>
                    <tr><td style="padding: 5px; font-weight: bold;">Relative Standard Deviation:</td><td style="padding: 5px;">{rsd_percent:.2f}%</td></tr>
                    <tr><td style="padding: 5px; font-weight: bold;">Range:</td><td style="padding: 5px;">{min(transport_rates):.6f} - {max(transport_rates):.6f} µL/s</td></tr>
                </table>
            </div>
            """
            
            self.summary_label.setText(summary_text)
            
            self.calibration_completed.emit("Particle Method", mean_rate)
            
        else:
            self.summary_label.setText("<div style='text-align: center; color: red;'><h3>No successful calculations</h3></div>")

    def export_results_to_csv(self):
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
    window = NumberMethodWidget()
    window.showMaximized()
    app.exec()