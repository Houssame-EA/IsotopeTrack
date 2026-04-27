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
import loading.vitesse_loading
import pyqtgraph as pg
from widget.numeric_table import NumericTableWidgetItem
from widget.custom_plot_widget import EnhancedPlotWidget
from processing.peak_detection import PeakDetection
from pathlib import Path
import json
from loading.data_thread import DataProcessThread


from calibration_methods.te_common import (
    BASE_STYLESHEET, PLOT_STYLES,
    create_scrollable_container, export_table_to_csv,
    populate_detection_row, read_detection_row, apply_global_method,
    plot_detection_results, highlight_particle, snr_to_color,
    number_method_transport_rate,
    base_stylesheet, show_data_source_dialog,
)
from theme import theme

try:
    from loading.import_csv_dialogs import CSVStructureDialog, CSVDataProcessThread, show_csv_structure_dialog
except ImportError:
    CSVStructureDialog = None
    CSVDataProcessThread = None
    show_csv_structure_dialog = None
    

class CollapsibleSection(QWidget):
    """
    A themed collapsible panel.  Click the header bar to expand / collapse.
    Use ``collapse(status)`` to fold it programmatically and show a summary
    string; use ``expand()`` to re-open it.
    """

    def __init__(self, title: str, parent=None):
        """
        Args:
            title (str): Window or dialog title.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self._expanded = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 4)
        outer.setSpacing(0)

        # ── header ──────────────────────────────────────────────────────
        self._header = QWidget()
        self._header.setObjectName("collapsibleHeader")
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.mousePressEvent = lambda _e: self.toggle()

        hrow = QHBoxLayout(self._header)
        hrow.setContentsMargins(12, 8, 12, 8)
        hrow.setSpacing(8)

        self._arrow = QLabel("▼")
        self._arrow.setObjectName("collapsibleArrow")
        self._arrow.setFixedWidth(14)

        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("collapsibleTitle")

        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("collapsibleStatus")

        hrow.addWidget(self._arrow)
        hrow.addWidget(self._title_lbl)
        hrow.addSpacing(16)
        hrow.addWidget(self._status_lbl, 1)

        outer.addWidget(self._header)

        # ── content ─────────────────────────────────────────────────────
        self.content_widget = QWidget()
        self.content_widget.setObjectName("collapsibleContent")
        outer.addWidget(self.content_widget)

    # ── public API ──────────────────────────────────────────────────────

    def toggle(self):
        self._expanded = not self._expanded
        self.content_widget.setVisible(self._expanded)
        self._arrow.setText("▼" if self._expanded else "▶")

    def collapse(self, status: str = ""):
        """
        Args:
            status (str): Status message string.
        """
        if status:
            self._status_lbl.setText(status)
        if self._expanded:
            self._expanded = False
            self.content_widget.setVisible(False)
            self._arrow.setText("▶")

    def expand(self):
        if not self._expanded:
            self._expanded = True
            self.content_widget.setVisible(True)
            self._arrow.setText("▼")

    def set_status(self, text: str):
        """
        Args:
            text (str): Text string.
        """
        self._status_lbl.setText(text)

    @property
    def is_expanded(self):
        """
        Returns:
            object: Result of the operation.
        """
        return self._expanded


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that ignores mouse-wheel events to prevent accidental changes."""
    def wheelEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        event.ignore()


class NoWheelIntSpinBox(QSpinBox):
    """QSpinBox that ignores mouse-wheel events to prevent accidental changes."""
    def wheelEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        event.ignore()


class NoWheelComboBox(QComboBox):
    """QComboBox that ignores mouse-wheel events to prevent accidental changes."""
    def wheelEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        event.ignore()


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
        self._exclusion_regions_by_sample = {}
        self.current_highlighted_particle = None
        self.sample_name_to_folder = {}

        self.periodic_table_widget = None
        self.selected_isotopes = {}
        
        self.csv_config = None 
        self.pending_csv_processing = False
        
        self.initUI()
        self.apply_theme()
        self._theme_cleanup = theme.connect_theme(self.apply_theme)
        self.destroyed.connect(lambda *_: self._theme_cleanup())

    def apply_theme(self, *_):
        """Re-apply the themed stylesheet and refresh dynamic labels.
        Args:
            *_ (Any): Additional positional arguments.
        """
        p = theme.palette

        section_qss = f"""
            QWidget#collapsibleHeader {{
                background-color: {p.accent}18;
                border-radius: 6px;
                border-left: 3px solid {p.accent};
            }}
            QWidget#collapsibleHeader:hover {{
                background-color: {p.accent}28;
            }}
            QLabel#collapsibleArrow {{
                color: {p.accent};
                font-size: 10px;
                font-weight: bold;
            }}
            QLabel#collapsibleTitle {{
                color: {p.text_primary};
                font-weight: 700;
                font-size: 13px;
                letter-spacing: 0.3px;
            }}
            QLabel#collapsibleStatus {{
                color: {p.accent};
                font-size: 11px;
            }}
            QLabel#panelHeader {{
                color: {p.text_primary};
                font-weight: 700;
                font-size: 12px;
                padding-bottom: 4px;
                border-bottom: 1px solid {p.accent}40;
            }}
        """
        self.setStyleSheet(base_stylesheet(p) + section_qss)
        for attr in ("plot_widget",):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.setBackground(p.plot_bg)
                except Exception:
                    pass
        for attr in ("folder_status_label", "element_selection_label"):
            lbl = getattr(self, attr, None)
            if lbl is None:
                continue
            if lbl.property("statusOk"):
                lbl.setObjectName("statusOk")
            else:
                lbl.setObjectName("statusMuted")
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

    def initUI(self):
        """
        Build the single-page collapsible layout.

        Four collapsible sections flow top-to-bottom:
          1. Sample Data      – auto-collapses after load
          2. Element Selection – auto-collapses after pick
          3. Detection Parameters + Detect button
          4. Results & Calibration (side-by-side) – auto-expands after detection

        A persistent Signal Visualization plot sits between sections 3 and 4.
        """
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root = QVBoxLayout(central_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(16, 12, 16, 16)
        page_layout.setSpacing(6)

        # ── 1. Samples ───────────────────────────────────────────────────
        self.samples_section = CollapsibleSection("1 ·  Sample Data")
        self._build_samples_content()
        page_layout.addWidget(self.samples_section)

        # ── 2. Element Selection ─────────────────────────────────────────
        self.element_section = CollapsibleSection("2 ·  Element Selection")
        self._build_element_content()
        page_layout.addWidget(self.element_section)

        # ── 3. Detection Parameters ──────────────────────────────────────
        self.detection_section = CollapsibleSection("3 ·  Detection Parameters")
        self._build_detection_content()
        page_layout.addWidget(self.detection_section)

        # ── Signal Visualization (always visible) ─────────────────────────
        self._build_plot(page_layout)

        # ── 4. Results & Calibration ──────────────────────────────────────
        self.results_section = CollapsibleSection("4 ·  Results & Calibration")
        self._build_results_calibration_content()
        page_layout.addWidget(self.results_section)

        page_layout.addStretch()
        scroll.setWidget(page)
        root.addWidget(scroll)

        self.setWindowTitle("Number Method — Transport Rate Calibration")
        self.setMinimumSize(1200, 900)

        
    def _build_samples_content(self):
        """Populate the Samples collapsible section."""
        w = self.samples_section.content_widget
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(8)

        hint = QLabel(
            "Select multiple folders containing particle analysis data. "
            "Each folder represents one sample."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hintLabel")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        folder_button = QPushButton("Select Sample Folders")
        folder_button.clicked.connect(self.select_folders)
        folder_button.setMaximumWidth(210)

        self.folder_status_label = QLabel("No folders selected")
        self.folder_status_label.setObjectName("statusMuted")
        self.folder_status_label.setProperty("statusOk", False)

        btn_row.addWidget(folder_button)
        btn_row.addWidget(self.folder_status_label)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.sample_table = QTableWidget()
        self.sample_table.setColumnCount(3)
        self.sample_table.setHorizontalHeaderLabels(["Sample Name", "Folder Path", "Status"])
        self.sample_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.sample_table.horizontalHeader().setStretchLastSection(True)
        self.sample_table.setAlternatingRowColors(True)
        self.sample_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sample_table.setMinimumHeight(130)
        self.sample_table.setMaximumHeight(200)
        layout.addWidget(self.sample_table)
    
    def _build_element_content(self):
        """Populate the Element Selection collapsible section."""
        w = self.element_section.content_widget
        layout = QHBoxLayout(w)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self.element_button = QPushButton("Open Periodic Table")
        self.element_button.clicked.connect(self.show_periodic_table)
        self.element_button.setMaximumWidth(200)
        self.element_button.setEnabled(False)

        self.element_selection_label = QLabel("Selected Element: None")
        self.element_selection_label.setObjectName("statusMuted")
        self.element_selection_label.setProperty("statusOk", False)

        layout.addWidget(QLabel("Element:"))
        layout.addWidget(self.element_button)
        layout.addWidget(self.element_selection_label)
        layout.addStretch()

    def _build_detection_content(self):
        """Populate the Detection Parameters collapsible section."""
        w = self.detection_section.content_widget
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(8)

        hint = QLabel(
            "Configure detection parameters per sample. "
            "Click a row to preview its signal in the plot below."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hintLabel")
        layout.addWidget(hint)

        global_row = QHBoxLayout()
        global_method_combo = NoWheelComboBox()
        global_method_combo.addItems(["Manual", "Compound Poisson LogNormal"])
        global_method_combo.setCurrentText("Compound Poisson LogNormal")
        apply_global_button = QPushButton("Apply to All Samples")
        apply_global_button.clicked.connect(
            lambda: self.apply_global_detection_params(global_method_combo.currentText())
        )
        global_row.addWidget(QLabel("Global Method:"))
        global_row.addWidget(global_method_combo)
        global_row.addWidget(apply_global_button)
        global_row.addStretch()
        layout.addLayout(global_row)

        self.detection_params_table = QTableWidget()
        self.detection_params_table.setColumnCount(12)
        headers = [
            'Sample Name', 'Element', 'Detection Method', 'Manual Threshold',
            'Min Points', 'Alpha', 'Sigma', 'Iterative',
            'Window Size', 'Integration Method', 'Split Method', 'Valley Ratio',
        ]
        self.detection_params_table.setHorizontalHeaderLabels(headers)

        tooltips = {
            6:  "Sigma for Compound Poisson LogNormal threshold calculation",
            7:  "Enable iterative background estimation (recommended)",
            8:  "Enable / set a custom rolling-window size for background estimation",
            9:  "How particle counts are integrated (Background / Threshold / Midpoint)",
            10: "Peak-splitting algorithm applied to overlapping particles",
            11: "Valley-to-peak ratio for 1D Watershed splitting (lower = fewer splits)",
        }
        for col, tip in tooltips.items():
            item = self.detection_params_table.horizontalHeaderItem(col)
            if item:
                item.setToolTip(tip)

        column_widths = [150, 120, 130, 120, 100, 100, 75, 75, 175, 140, 130, 105]
        for i, width in enumerate(column_widths):
            self.detection_params_table.setColumnWidth(i, width)

        self.detection_params_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.detection_params_table.setAlternatingRowColors(True)
        self.detection_params_table.setMinimumHeight(150)
        self.detection_params_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.detection_params_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.detection_params_table.itemSelectionChanged.connect(
            self.on_detection_params_selection_changed
        )
        layout.addWidget(self.detection_params_table)

        self.detect_button = QPushButton("Detect Particles for All Samples")
        self.detect_button.clicked.connect(self.detect_particles_all_samples)
        self.detect_button.setMinimumHeight(40)
        self.detect_button.setEnabled(False)
        layout.addWidget(self.detect_button)

    def _build_plot(self, parent_layout):
        """Add the always-visible signal visualization plot to parent_layout.
        Args:
            parent_layout (Any): Layout to which widgets are added.
        """
        plot_group = QGroupBox("Signal Visualization")
        plot_layout = QVBoxLayout(plot_group)
        plot_layout.setSpacing(6)

        controls_row = QHBoxLayout()
        self.sample_combo = NoWheelComboBox()
        self.sample_combo.currentTextChanged.connect(self.update_sample_visualization)
        self.visualization_status_label = QLabel(
            "Click on a sample row above to preview its signal"
        )
        self.visualization_status_label.setObjectName("hintLabel")
        controls_row.addWidget(QLabel("Sample:"))
        controls_row.addWidget(self.sample_combo)
        controls_row.addWidget(self.visualization_status_label)
        controls_row.addStretch()
        plot_layout.addLayout(controls_row)

        self.plot_widget = EnhancedPlotWidget()
        self.plot_widget.setBackground(theme.palette.plot_bg)
        self.plot_widget.setMinimumHeight(280)
        plot_layout.addWidget(self.plot_widget)

        try:
            self.plot_widget.exclusionRegionsChanged.connect(
                self._on_exclusion_regions_changed)
        except Exception as e:
            print(f"Could not connect exclusionRegionsChanged: {e}")

        parent_layout.addWidget(plot_group)

    def _build_results_calibration_content(self):
        """
        Populate the Results & Calibration collapsible section.
        Detection results (left panel) and calibration (right panel) sit
        side-by-side in a resizable QSplitter.
        """
        w = self.results_section.content_widget
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── LEFT: Detection Results ──────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 8, 0)
        ll.setSpacing(6)

        left_header = QLabel("Detection Results")
        left_header.setObjectName("panelHeader")
        ll.addWidget(left_header)

        left_hint = QLabel("Click a particle row to zoom in on it in the plot above.")
        left_hint.setObjectName("hintLabel")
        left_hint.setWordWrap(True)
        ll.addWidget(left_hint)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels([
            'Sample Name', 'Peak Start (s)', 'Peak End (s)', 'Total Counts'
        ])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        self.results_table.itemSelectionChanged.connect(self.highlight_selected_particle)
        self.results_table.setMinimumHeight(220)
        ll.addWidget(self.results_table)

        export_btn = QPushButton("Export Results to CSV")
        export_btn.clicked.connect(self.export_results_to_csv)
        ll.addWidget(export_btn, alignment=Qt.AlignRight)

        # ── RIGHT: Calibration ───────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 0, 0)
        rl.setSpacing(6)

        right_header = QLabel("Transport Rate Calibration")
        right_header.setObjectName("panelHeader")
        rl.addWidget(right_header)

        right_hint = QLabel(
            "Default values: 100 nm diameter, 400 ng/L. "
            "Modify as needed for your calibration standards."
        )
        right_hint.setObjectName("hintLabel")
        right_hint.setWordWrap(True)
        rl.addWidget(right_hint)

        self.calibration_data_table = QTableWidget()
        self.calibration_data_table.setColumnCount(7)
        self.calibration_data_table.setHorizontalHeaderLabels([
            'Sample Name', 'Particles', 'Diameter (nm)',
            'Conc. (ng/L)', 'Acq. Time (s)', 'Density (g/cm³)', 'Use',
        ])
        for i, w_col in enumerate([130, 80, 90, 90, 80, 100, 45]):
            self.calibration_data_table.setColumnWidth(i, w_col)
        self.calibration_data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.calibration_data_table.setAlternatingRowColors(True)
        self.calibration_data_table.setMinimumHeight(160)
        rl.addWidget(self.calibration_data_table)

        btn_row = QHBoxLayout()
        auto_fill_btn = QPushButton("Auto-fill from Detection")
        auto_fill_btn.clicked.connect(self.auto_fill_calibration_data)
        calc_btn = QPushButton("Calculate Transport Rates")
        calc_btn.clicked.connect(self.calculate_transport_rates)
        calc_btn.setMinimumHeight(36)
        btn_row.addWidget(auto_fill_btn)
        btn_row.addWidget(calc_btn)
        rl.addLayout(btn_row)

        self.calibration_results_table = QTableWidget()
        self.calibration_results_table.setColumnCount(6)
        self.calibration_results_table.setHorizontalHeaderLabels([
            'Sample Name', 'Transport Rate (µL/s)', 'Particles/mL',
            'Particle Mass (fg)', 'Particle Volume (nm³)', 'Status',
        ])
        self.calibration_results_table.horizontalHeader().setStretchLastSection(True)
        self.calibration_results_table.setAlternatingRowColors(True)
        self.calibration_results_table.setMinimumHeight(120)
        rl.addWidget(self.calibration_results_table)

        self.summary_label = QLabel()
        self.summary_label.setObjectName("summaryPanel")
        self.summary_label.setWordWrap(True)
        self.summary_label.setAlignment(Qt.AlignCenter)
        rl.addWidget(self.summary_label)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([500, 500])
        layout.addWidget(splitter)
        
    def select_folders(self):
        """
        Enhanced folder/file selection matching main window structure.
        
        Displays a dialog allowing user to choose between NU folders with run.info files,
        data files in various formats (CSV, TXT, Excel), or TOFWERK .h5 files.
        """
        choice = show_data_source_dialog(self)
        if choice == "folder":
            self.select_nu_folders()
        elif choice == "csv":
            self.select_data_files()
        elif choice == "tofwerk":
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
                    if not loading.tofwerk_loading.is_tofwerk_file(h5_file):
                        raise ValueError(f"Not a valid TOFWERK file: {h5_file.name}")
                    
                    sample_name = h5_file.stem
                    
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
                status_item.setBackground(QColor(theme.palette.tier_low))
            else:
                status_item.setBackground(QColor(theme.palette.tier_critical))
                    
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
        self.folder_status_label.setObjectName("statusOk")
        self.folder_status_label.setProperty("statusOk", True)
        self.folder_status_label.style().unpolish(self.folder_status_label)
        self.folder_status_label.style().polish(self.folder_status_label)

        if valid_count > 0 and hasattr(self, 'samples_section'):
            names = [
                self.folder_data[f].get('sample_name', Path(f).name)
                for f in self.folder_paths
                if 'Loaded' in self.folder_data[f].get('status', '')
            ]
            preview = ', '.join(names[:3])
            if len(names) > 3:
                preview += f'  +{len(names) - 3} more'
            self.samples_section.collapse(f"{valid_count} samples  —  {preview}")

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
                        self.element_selection_label.setObjectName("statusOk")
                        self.element_selection_label.setProperty("statusOk", True)
                        self.element_selection_label.style().unpolish(self.element_selection_label)
                        self.element_selection_label.style().polish(self.element_selection_label)
                        
                        self.load_element_data_for_all_samples()
                        self.update_detection_parameters_table()
                        self.update_calibration_data_table()

                        if hasattr(self, 'element_section'):
                            self.element_section.collapse(
                                f"{first_element_symbol}  —  "
                                f"{int(round(first_isotope_mass))}{first_element_symbol}"
                                f"  ({abundance:.1f}%)"
                            )
            else:
                self.selected_element = None
                self.element_selection_label.setText("Selected Element: None")
                self.element_selection_label.setObjectName("statusMuted")
                self.element_selection_label.setProperty("statusOk", False)
                self.element_selection_label.style().unpolish(self.element_selection_label)
                self.element_selection_label.style().polish(self.element_selection_label)
                
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
                        
                        data, info, dwell_time = loading.tofwerk_loading.read_tofwerk_file(h5_path)
                        
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
                
                else:
                    try:
                        masses, signals, run_info = loading.vitesse_loading.read_nu_directory(
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

    # ── Exclusion region helpers (mirrors MainWindow logic) ──────────────

    def _visible_exclusion_entries_for(self, sample_name):
        """Return the list of exclusion entries stored for *sample_name*.

        Each entry is a dict ``{'bounds': (x0, x1), 'scope': 'sample',
        'element_key': None}``.  Returns an empty list when there are none.
        Args:
            sample_name (Any): The sample name.
        """
        return self._exclusion_regions_by_sample.get(sample_name, [])

    def _on_exclusion_regions_changed(self):
        """Sync the plot's current exclusion bands into the bookkeeping store.

        Called automatically whenever the user adds, removes, or resizes an
        exclusion band in the plot widget.  The updated store is later used by
        ``calculate_transport_rates`` to subtract excluded time from the
        effective acquisition window before computing particles/mL.
        """
        sample_name = self.sample_combo.currentText()
        if not sample_name:
            return
        try:
            plot_regions = self.plot_widget.get_exclusion_regions()
        except Exception as e:
            print(f"get_exclusion_regions failed: {e}")
            return

        new_store = []
        for lo, hi, scope in plot_regions:
            new_store.append({
                'bounds': (float(lo), float(hi)),
                'scope': 'sample',
                'element_key': None,
            })
        self._exclusion_regions_by_sample[sample_name] = new_store

    def _rebuild_plot_exclusion_regions(self):
        """Redraw the plot's exclusion bands from the bookkeeping store.

        Called after switching the displayed sample so that previously drawn
        bands are restored on the plot.
        """
        sample_name = self.sample_combo.currentText()
        if not sample_name:
            return
        entries = self._exclusion_regions_by_sample.get(sample_name, [])
        regions = [{'x0': e['bounds'][0], 'x1': e['bounds'][1]} for e in entries]
        try:
            try:
                self.plot_widget.exclusionRegionsChanged.disconnect(
                    self._on_exclusion_regions_changed)
            except Exception:
                pass
            self.plot_widget.set_exclusion_regions(regions)
        finally:
            try:
                self.plot_widget.exclusionRegionsChanged.connect(
                    self._on_exclusion_regions_changed)
            except Exception:
                pass

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
                    results['particles'],
                    results['lambda_bkgd'],
                    results['threshold'],
                    results['time_array']
                )
                self.visualization_status_label.setText(f"Showing detection results for: {sample_name}")
            else:
                self.plot_raw_signal_preview(folder_path, sample_name)
                self.visualization_status_label.setText(f"Showing raw signal preview for: {sample_name}")
            try:
                self._rebuild_plot_exclusion_regions()
            except Exception:
                pass
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
            pen=PLOT_STYLES['raw_signal'], 
            name='Raw Signal'
        )
        
        self.plot_widget.setBackground(theme.palette.plot_bg)
        self.plot_widget.showGrid(x=True, y=True, alpha=PLOT_STYLES['grid_alpha'])
        self.plot_widget.setLabel('left', 'Counts')
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.setTitle(f"Raw Signal Preview - {sample_name}")
        self.plot_widget.enableAutoRange()

    def update_detection_parameters_table(self):
        """
        Update detection parameters table with all samples.
        
        Populates the detection parameters table with default values for each sample
        including detection method, and threshold parameters.

        Returns:
            None
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
            populate_detection_row(self.detection_params_table, i, sample_name, display_label)

            # ── Col 6 : Sigma ──────────────────────────────────────────────
            sigma_spin = NoWheelDoubleSpinBox()
            sigma_spin.setRange(0.01, 2.0)
            sigma_spin.setDecimals(3)
            sigma_spin.setSingleStep(0.01)
            sigma_spin.setValue(0.55)
            sigma_spin.setToolTip(
                "Sigma for Compound Poisson LogNormal threshold calculation.\n"
                "Typical range: 0.3 – 0.8 depending on instrument noise."
            )
            self.detection_params_table.setCellWidget(i, 6, sigma_spin)

            # ── Col 7 : Iterative background ───────────────────────────────
            iterative_cb = QCheckBox()
            iterative_cb.setChecked(True)
            iterative_cb.setToolTip(
                "Enable iterative background estimation.\n"
                "Recommended for most data sets."
            )
            self.detection_params_table.setCellWidget(i, 7, iterative_cb)

            # ── Col 8 : Window Size (checkbox + spinbox) ───────────────────
            ws_container = QWidget()
            ws_layout = QHBoxLayout(ws_container)
            ws_layout.setContentsMargins(2, 2, 2, 2)
            ws_layout.setSpacing(3)

            ws_checkbox = QCheckBox()
            ws_checkbox.setChecked(False)
            ws_checkbox.setToolTip("Enable a custom rolling-window size for background estimation")

            ws_spinbox = NoWheelIntSpinBox()
            ws_spinbox.setRange(500, 100_000)
            ws_spinbox.setValue(5000)
            ws_spinbox.setSingleStep(100)
            ws_spinbox.setEnabled(False)
            ws_spinbox.setToolTip("Number of points used for the rolling background window")

            ws_checkbox.stateChanged.connect(ws_spinbox.setEnabled)
            ws_layout.addWidget(ws_checkbox)
            ws_layout.addWidget(ws_spinbox)
            self.detection_params_table.setCellWidget(i, 8, ws_container)

            # ── Col 9 : Integration Method ─────────────────────────────────
            integration_combo = NoWheelComboBox()
            integration_combo.addItems(["Background", "Threshold", "Midpoint"])
            integration_combo.setCurrentText("Background")
            integration_combo.setToolTip(
                "How particle signal is integrated:\n"
                "  Background – subtract background level\n"
                "  Threshold  – subtract threshold level\n"
                "  Midpoint   – subtract midpoint level"
            )
            self.detection_params_table.setCellWidget(i, 9, integration_combo)

            # ── Col 10 : Split Method ──────────────────────────────────────
            split_combo = NoWheelComboBox()
            split_combo.addItems(["No Splitting", "1D Watershed"])
            split_combo.setCurrentText("1D Watershed")
            split_combo.setToolTip(
                "Algorithm used to split overlapping peaks:\n"
                "  No Splitting – keep merged peaks as-is\n"
                "  1D Watershed – split at valleys between peaks"
            )
            self.detection_params_table.setCellWidget(i, 10, split_combo)

            # ── Col 11 : Valley Ratio ──────────────────────────────────────
            valley_spin = NoWheelDoubleSpinBox()
            valley_spin.setRange(0.01, 0.99)
            valley_spin.setDecimals(2)
            valley_spin.setSingleStep(0.05)
            valley_spin.setValue(0.50)
            valley_spin.setToolTip(
                "Valley-to-peak ratio for 1D Watershed splitting.\n"
                "Lower = only split very deep valleys (fewer splits).\n"
                "Higher = split shallower valleys (more splits).\n"
                "Default: 0.50"
            )
            valley_spin.setEnabled(split_combo.currentText() == "1D Watershed")
            split_combo.currentTextChanged.connect(
                lambda text, vs=valley_spin: vs.setEnabled(text == "1D Watershed")
            )
            self.detection_params_table.setCellWidget(i, 11, valley_spin)
        
        self.detect_button.setEnabled(True)

    def apply_global_detection_params(self, method):
        """
        Apply global detection method to all samples.
        
        Args:
            method (str): Detection method name to apply to all sample rows.

        Returns:
            None
        """
        apply_global_method(self.detection_params_table, method)
            
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
                
                _, lambda_bkgd, threshold, mean_signal, threshold_data = self.peak_detector.detect_peaks_with_poisson(
                    signal,
                    alpha=params['alpha'],
                    method=params['method'],
                    manual_threshold=params['manual_threshold'],
                    element_thresholds={},
                    current_sample=None,
                    sigma=params.get('sigma', 0.55),
                    iterative=params.get('iterative', True),
                    use_window_size=params.get('use_window_size', False),
                    window_size=params.get('window_size', 5000),
                )

                particles = self.peak_detector.find_particles(
                    time_array,
                    signal,
                    lambda_bkgd,
                    threshold,
                    min_continuous_points=params['min_continuous'],
                    integration_method=params.get('integration_method', "Background"),
                    split_method=params.get('split_method', "1D Watershed"),
                    sigma=params.get('sigma', 0.55),
                    min_valley_ratio=params.get('valley_ratio', 0.50),
                )
                
                self.detection_results[folder_path] = {
                    'sample_name': sample_name,
                    'particles': particles,
                    'signal': signal,
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
        Get detection parameters for a specific sample row.

        Args:
            row (int): Row index in the detection parameters table.

        Returns:
            dict: Keys include 'method', 'manual_threshold', 'min_continuous',
                  'alpha', 'sigma', 'iterative', 'use_window_size', 'window_size',
                  'integration_method', 'split_method', 'valley_ratio'.
        """
        params = read_detection_row(self.detection_params_table, row)

        # ── Col 6 : Sigma ──────────────────────────────────────────────────
        sigma_w = self.detection_params_table.cellWidget(row, 6)
        params['sigma'] = sigma_w.value() if sigma_w is not None else 0.55

        # ── Col 7 : Iterative ──────────────────────────────────────────────
        iter_w = self.detection_params_table.cellWidget(row, 7)
        params['iterative'] = iter_w.isChecked() if iter_w is not None else True

        # ── Col 8 : Window Size ────────────────────────────────────────────
        ws_container = self.detection_params_table.cellWidget(row, 8)
        if ws_container is not None:
            ws_cb = ws_container.findChild(QCheckBox)
            ws_sb = ws_container.findChild(QSpinBox)
            params['use_window_size'] = ws_cb.isChecked() if ws_cb is not None else False
            params['window_size'] = ws_sb.value() if ws_sb is not None else 5000
        else:
            params['use_window_size'] = False
            params['window_size'] = 5000

        # ── Col 9 : Integration Method ─────────────────────────────────────
        int_w = self.detection_params_table.cellWidget(row, 9)
        params['integration_method'] = (
            int_w.currentText() if int_w is not None else "Background"
        )

        # ── Col 10 : Split Method ──────────────────────────────────────────
        split_w = self.detection_params_table.cellWidget(row, 10)
        params['split_method'] = (
            split_w.currentText() if split_w is not None else "1D Watershed"
        )

        # ── Col 11 : Valley Ratio ──────────────────────────────────────────
        valley_w = self.detection_params_table.cellWidget(row, 11)
        params['valley_ratio'] = valley_w.value() if valley_w is not None else 0.50

        return params

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
                
                color = snr_to_color(height_threshold_ratio)
                
                for item in [sample_item, start_item, end_item, counts_item]:
                    item.setBackground(color)
                
                self.results_table.setItem(row_position, 0, sample_item)
                self.results_table.setItem(row_position, 1, start_item)
                self.results_table.setItem(row_position, 2, end_item)
                self.results_table.setItem(row_position, 3, counts_item)
        
        self.results_table.setSortingEnabled(True)
        self.results_table.sortItems(0, Qt.AscendingOrder)

        if hasattr(self, 'results_section'):
            n = self.results_table.rowCount()
            self.results_section.expand()
            self.results_section.set_status(f"{n} particle{'s' if n != 1 else ''} detected")

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
            particle (dict): Particle dictionary containing detection information.
            results (dict): Detection results dictionary for the sample.

        Returns:
            None
        """
        self.current_highlighted_particle = highlight_particle(
            self.plot_widget, particle,
            results['time_array'], results['signal'],
            self.current_highlighted_particle
        )

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
            results['particles'],
            results['lambda_bkgd'],
            results['threshold'],
            results['time_array']
        )

    def plot_sample_results(self, sample_name, signal, particles, lambda_bkgd, threshold, time_array):
        """
        Plot results for a specific sample.
        
        Args:
            sample_name (str): Display name of the sample.
            signal (np.ndarray): Raw signal array.
            particles (list[dict]): List of detected particle dictionaries.
            lambda_bkgd (float): Background level value.
            threshold (float): Detection threshold value.
            time_array (np.ndarray): Time array corresponding to signal data.

        Returns:
            None
        """
        self.current_highlighted_particle = None
        plot_detection_results(
            self.plot_widget, sample_name, signal,
            particles, lambda_bkgd, threshold, time_array,
            peak_detector=self.peak_detector
        )
        
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

                effective_time = acquisition_time_s
                for entry in self._visible_exclusion_entries_for(sample_name):
                    x0, x1 = entry['bounds']
                    x0 = max(x0, 0.0)
                    x1 = min(x1, acquisition_time_s)
                    if x1 > x0:
                        effective_time -= (x1 - x0)
                effective_time = max(effective_time, 0.0)

                result = number_method_transport_rate(
                    particles_detected, diameter_nm, concentration_ng_l,
                    effective_time, density_g_cm3
                )
                
                result_row = self.calibration_results_table.rowCount()
                self.calibration_results_table.insertRow(result_row)
                
                self.calibration_results_table.setItem(result_row, 0, QTableWidgetItem(sample_name))
                self.calibration_results_table.setItem(result_row, 1, QTableWidgetItem(f"{result['transport_rate_ul_s']:.6f}"))
                self.calibration_results_table.setItem(result_row, 2, QTableWidgetItem(f"{result['particles_per_ml']:.2f}"))
                self.calibration_results_table.setItem(result_row, 3, QTableWidgetItem(f"{result['particle_mass_fg']:.3f}"))
                self.calibration_results_table.setItem(result_row, 4, QTableWidgetItem(f"{result['particle_volume_nm3']:.3f}"))
                self.calibration_results_table.setItem(result_row, 5, QTableWidgetItem(result['status']))
                
                if result['status'] == "Success":
                    transport_rates.append(result['transport_rate_ul_s'])
                    successful_calculations.append({
                        'sample_name': sample_name,
                        'transport_rate': result['transport_rate_ul_s'],
                        'particles_detected': particles_detected,
                        'particle_mass_fg': result['particle_mass_fg'],
                        'particles_per_ml': result['particles_per_ml']
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

        Returns:
            None
        """
        export_table_to_csv(self.results_table, self)


if __name__ == '__main__':
    app = QApplication([])
    window = NumberMethodWidget()
    window.showMaximized()
    app.exec()