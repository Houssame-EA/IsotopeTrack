import json
from pathlib import Path
import numpy as np
from scipy import stats
import pyqtgraph as pg
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget, QGridLayout,
                               QLabel, QComboBox, QMessageBox, QFileDialog, QTabWidget,
                               QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
                               QDoubleSpinBox, QGroupBox, QFormLayout, QDialog, QMenu,
                               QListView, QAbstractItemView, QTreeView, QSpinBox, QApplication, QScrollArea, QListWidget,QRadioButton,
                               QMainWindow, QFrame, QProgressBar, QSplitter, QProgressDialog, QLineEdit)
from PySide6.QtGui import QFont, QColor, QIcon, QDoubleValidator
from PySide6.QtCore import Qt, Signal
import loading.vitesse_loading
from widget.periodic_table_widget import PeriodicTableWidget
from widget.numeric_table import NumericTableWidgetItem
from widget.custom_plot_widget import EnhancedPlotWidget
from processing.peak_detection import PeakDetection


from calibration_methods.te_common import (
    BASE_STYLESHEET, PLOT_STYLES, HISTOGRAM_COLORS,
    NumericDelegate,
    create_scrollable_container, export_table_to_csv,
    populate_detection_row, read_detection_row, apply_global_method,
    plot_detection_results, highlight_particle, snr_to_color,
    particle_mass_from_diameter,
    base_stylesheet, show_data_source_dialog,
)
from theme import theme

class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that ignores mouse-wheel to prevent accidental changes."""
    def wheelEvent(self, event): event.ignore()

class NoWheelIntSpinBox(QSpinBox):
    """QSpinBox that ignores mouse-wheel to prevent accidental changes."""
    def wheelEvent(self, event): event.ignore()

class NoWheelComboBox(QComboBox):
    """QComboBox that ignores mouse-wheel to prevent accidental changes."""
    def wheelEvent(self, event): event.ignore()


class CollapsibleSection(QWidget):
    """Themed collapsible panel. Click header to expand/collapse."""

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

        self.content_widget = QWidget()
        self.content_widget.setObjectName("collapsibleContent")
        outer.addWidget(self.content_widget)

    def toggle(self):
        self._expanded = not self._expanded
        self.content_widget.setVisible(self._expanded)
        self._arrow.setText("▼" if self._expanded else "▶")

    def collapse(self, status: str = ""):
        """
        Args:
            status (str): Status message string.
        """
        if status: self._status_lbl.setText(status)
        if self._expanded:
            self._expanded = False
            self.content_widget.setVisible(False)
            self._arrow.setText("▶")

    def expand(self):
        if not self._expanded:
            self._expanded = True
            self.content_widget.setVisible(True)
            self._arrow.setText("▼")

    def set_status(self, text: str): self._status_lbl.setText(text)

    @property
    def is_expanded(self): return self._expanded


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
 
        self.setStyleSheet(base_stylesheet(theme.palette))
        
        layout = QVBoxLayout(self)
        
        self.periodic_table = PeriodicTableWidget()
        self.periodic_table.selection_confirmed.connect(self.on_selection_confirmed)
        self.periodic_table.isotope_selected.connect(self.on_isotope_selected)
        layout.addWidget(self.periodic_table)
        
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

        # ── Exclusion regions — particle detection plot ──────────────────
        self._exclusion_regions_by_sample = {}

        # ── Exclusion regions — ionic calibration plot ───────────────────
        self._ionic_cal_exclusions_element = {}
        self._ionic_cal_exclusions_sample  = {}
        self._current_ionic_cal_folder      = None
        self._current_ionic_cal_isotope_key = None

        self.default_button_style = ""
        self.modified_button_style = ""
        
        self.initUI()
        self.apply_theme()
        self._theme_cleanup = theme.connect_theme(self.apply_theme)
        self.destroyed.connect(lambda *_: self._theme_cleanup())
    
    def apply_theme(self, *_):
        """Re-apply themed stylesheet; refresh plots and dynamic labels.
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
            QWidget#collapsibleHeader:hover {{ background-color: {p.accent}28; }}
            QLabel#collapsibleArrow {{ color: {p.accent}; font-size: 10px; font-weight: bold; }}
            QLabel#collapsibleTitle {{ color: {p.text_primary}; font-weight: 700; font-size: 13px; }}
            QLabel#collapsibleStatus {{ color: {p.accent}; font-size: 11px; }}
            QLabel#panelHeader {{
                color: {p.text_primary}; font-weight: 700; font-size: 12px;
                padding-bottom: 4px; border-bottom: 1px solid {p.accent}40;
            }}
        """
        self.setStyleSheet(base_stylesheet(p) + section_qss)
        for attr in (
            "plot_widget", "regression_plot", "calibration_raw_plot",
            "diameter_distribution_plot",
        ):
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

    def _mark_button_modified(self, button, modified=True):
        """Toggle the 'warning' look on a button to indicate unsaved /
        modified state.  Uses the themed #warningBtn object name so the
        color follows light/dark themes.
        Args:
            button (Any): The button.
            modified (Any): The modified.
        """
        if button is None:
            return
        if modified:
            button.setObjectName("warningBtn")
        else:
            button.setObjectName("")
        button.style().unpolish(button)
        button.style().polish(button)

    def initUI(self):
        """Single-page collapsible layout replacing the 5-tab structure."""
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

        self.samples_section = CollapsibleSection("1 ·  Sample Data")
        self._build_samples_content()
        page_layout.addWidget(self.samples_section)

        self.element_section = CollapsibleSection("2 ·  Element Selection")
        self._build_element_content()
        page_layout.addWidget(self.element_section)

        self.detection_section = CollapsibleSection("3 ·  Detection Parameters")
        self._build_detection_content()
        page_layout.addWidget(self.detection_section)

        self._build_plot(page_layout)

        self.results_section = CollapsibleSection("4 ·  Detection Results")
        self._build_detection_results_content()
        page_layout.addWidget(self.results_section)

        self.calibration_section = CollapsibleSection("5 ·  Ionic Calibration")
        self._build_ionic_calibration_content()
        page_layout.addWidget(self.calibration_section)

        self.analysis_section = CollapsibleSection("6 ·  Mass Analysis & Transport Rate")
        self._build_analysis_results_content()
        page_layout.addWidget(self.analysis_section)

        page_layout.addStretch()
        scroll.setWidget(page)
        root.addWidget(scroll)

        self.setWindowTitle("Mass Method Calibration")
        self.setMinimumSize(1200, 900)

        self.periodic_table_dialog = PeriodicTableDialog(self)
        self.periodic_table_dialog.element_selected.connect(self.on_element_selected)
        self.calibration_folder_paths = []
        self.calibration_results = {}
        self.ignore_concentration_item_changed = False
        
    def _build_samples_content(self):
        """Section 1 — sample folder selection."""
        w = self.samples_section.content_widget
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(8)

        hint = QLabel("Select multiple folders containing particle analysis data. Each folder represents one sample.")
        hint.setWordWrap(True)
        hint.setObjectName("hintLabel")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        folder_button = QPushButton("Select Particle Folders")
        folder_button.clicked.connect(self.select_particle_folders)
        folder_button.setMaximumWidth(210)
        btn_row.addWidget(folder_button)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.folder_list = QListWidget()
        self.folder_list.setAlternatingRowColors(True)
        self.folder_list.itemClicked.connect(self.on_folder_selected)
        self.folder_list.setMinimumHeight(120)
        self.folder_list.setMaximumHeight(180)
        layout.addWidget(self.folder_list)

        self.folder_status_label = QLabel("No folders selected")
        self.folder_status_label.setObjectName("statusMuted")
        self.folder_status_label.setProperty("statusOk", False)
        layout.addWidget(self.folder_status_label)

    def _build_element_content(self):
        """Section 2 — element / isotope selection."""
        w = self.element_section.content_widget
        layout = QHBoxLayout(w)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self.element_selection_label = QLabel("Selected Element: None")
        self.element_selection_label.setObjectName("statusMuted")
        self.element_selection_label.setProperty("statusOk", False)

        self.element_button = QPushButton("Open Periodic Table")
        self.element_button.clicked.connect(self.show_periodic_table)
        self.element_button.setMaximumWidth(200)
        self.element_button.setEnabled(False)

        hint = QLabel("Right-click an element to select specific isotopes.")
        hint.setObjectName("hintLabel")

        layout.addWidget(QLabel("Element:"))
        layout.addWidget(self.element_button)
        layout.addWidget(self.element_selection_label)
        layout.addSpacing(16)
        layout.addWidget(hint)
        layout.addStretch()
    
    def _build_detection_content(self):
        """Section 3 — 12-column detection parameters + detect button."""
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
        self.detection_params_table.setHorizontalHeaderLabels([
            'Sample Name', 'Element', 'Detection Method', 'Manual Threshold',
            'Min Points', 'Alpha', 'Sigma', 'Iterative',
            'Window Size', 'Integration Method', 'Split Method', 'Valley Ratio',
        ])
        for col, tip in {
            6:  "Sigma for Compound Poisson LogNormal",
            7:  "Enable iterative background estimation (recommended)",
            8:  "Enable / set rolling-window size for background",
            9:  "Integration baseline: Background / Threshold / Midpoint",
            10: "Peak-splitting algorithm for overlapping particles",
            11: "Valley-to-peak ratio for 1D Watershed (lower = fewer splits)",
        }.items():
            item = self.detection_params_table.horizontalHeaderItem(col)
            if item: item.setToolTip(tip)

        for i, w_col in enumerate([150, 120, 130, 120, 100, 100, 75, 75, 175, 140, 130, 105]):
            self.detection_params_table.setColumnWidth(i, w_col)
        self.detection_params_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.detection_params_table.setAlternatingRowColors(True)
        self.detection_params_table.setMinimumHeight(150)
        self.detection_params_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.detection_params_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.detection_params_table.itemSelectionChanged.connect(self.on_detection_params_selection_changed)
        layout.addWidget(self.detection_params_table)

        self.detect_button = QPushButton("Detect Particles for All Samples")
        self.detect_button.clicked.connect(self.detect_particles_all_samples)
        self.detect_button.setMinimumHeight(40)
        self.detect_button.setEnabled(False)
        layout.addWidget(self.detect_button)

    def _build_plot(self, parent_layout):
        """Always-visible signal visualization plot.
        Args:
            parent_layout (Any): Layout to which widgets are added.
        """
        plot_group = QGroupBox("Signal Visualization")
        plot_layout = QVBoxLayout(plot_group)
        plot_layout.setSpacing(6)

        controls_row = QHBoxLayout()
        self.sample_combo = NoWheelComboBox()
        self.sample_combo.currentTextChanged.connect(self.update_sample_visualization)
        self.visualization_status_label = QLabel("Click a sample row above to preview its signal")
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
            print(f"Could not connect plot exclusionRegionsChanged: {e}")
        parent_layout.addWidget(plot_group)

    def _build_detection_results_content(self):
        """Section 4 — results table (left) | file info table (right)."""
        w = self.results_section.content_widget
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 8, 0)
        ll.setSpacing(6)
        left_hdr = QLabel("Detection Results")
        left_hdr.setObjectName("panelHeader")
        ll.addWidget(left_hdr)
        ll.addWidget(self._hint("Click a particle row to zoom in on it in the plot above."))
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
        ll.addWidget(self.results_table)
        export_btn = QPushButton("Export Data to CSV")
        export_btn.clicked.connect(self.export_to_csv)
        ll.addWidget(export_btn, alignment=Qt.AlignRight)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 0, 0)
        rl.setSpacing(6)
        right_hdr = QLabel("File Information")
        right_hdr.setObjectName("panelHeader")
        rl.addWidget(right_hdr)
        self.file_info_table = QTableWidget()
        self.file_info_table.setColumnCount(4)
        self.file_info_table.setHorizontalHeaderLabels([
            'File Name', 'Diameter (nm)', 'Density (g/cm³)', 'Avg Total Count'
        ])
        self.file_info_table.horizontalHeader().setStretchLastSection(True)
        self.file_info_table.setAlternatingRowColors(True)
        self.file_info_table.setMinimumHeight(200)
        rl.addWidget(self.file_info_table)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([600, 400])
        layout.addWidget(splitter)

    @staticmethod
    def _hint(text: str) -> QLabel:
        """Convenience: create a styled hint label.
        Args:
            text (str): Text string.
        Returns:
            QLabel: Result of the operation.
        """
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setObjectName("hintLabel")
        return lbl
    
    def _build_analysis_results_content(self):
        """Section 6 — Mass Analysis regression + Transport Rate + Diameter Distribution."""
        w = self.analysis_section.content_widget
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(10)

        # ── Regression plot ────────────────────────────────────────────
        reg_hdr = QLabel("Particle Mass Analysis")
        reg_hdr.setObjectName("panelHeader")
        layout.addWidget(reg_hdr)

        self.regression_plot = pg.PlotWidget()
        self.regression_plot.setBackground(theme.palette.plot_bg)
        self.regression_plot.setLabel('left', 'Average Counts')
        self.regression_plot.setLabel('bottom', 'Particle Mass (fg)')
        self.regression_plot.showGrid(x=True, y=True, alpha=0.3)
        self.regression_plot.setMinimumHeight(280)
        layout.addWidget(self.regression_plot)

        self.calculate_button = QPushButton("Calculate Mass and Regression")
        self.calculate_button.clicked.connect(self.calculate_mass_and_regression)
        self.calculate_button.setMinimumHeight(40)
        layout.addWidget(self.calculate_button)

        # ── Transport rate ─────────────────────────────────────────────
        tr_hdr = QLabel("Calibrated Transport Rate")
        tr_hdr.setObjectName("panelHeader")
        layout.addWidget(tr_hdr)

        self.transport_rate_table = QTableWidget()
        self.transport_rate_table.setColumnCount(4)
        self.transport_rate_table.setHorizontalHeaderLabels([
            "Particle Calibration Slope", "Ionic Calibration Slope",
            "Calibrated Transport Rate (μL/s)", "R² (Ionic Calibration)",
        ])
        self.transport_rate_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.transport_rate_table.setAlternatingRowColors(True)
        layout.addWidget(self.transport_rate_table)

        calc_tr_btn = QPushButton("Calculate Transport Rate")
        calc_tr_btn.clicked.connect(self.calculate_transport_rate)
        calc_tr_btn.setMinimumHeight(40)
        layout.addWidget(calc_tr_btn)

        # ── Diameter distribution ──────────────────────────────────────
        diam_hdr = QLabel("Particle Size Distribution")
        diam_hdr.setObjectName("panelHeader")
        layout.addWidget(diam_hdr)

        self.diameter_distribution_plot = pg.PlotWidget()
        self.diameter_distribution_plot.setBackground(theme.palette.plot_bg)
        self.diameter_distribution_plot.setLabel('left', 'Frequency')
        self.diameter_distribution_plot.setLabel('bottom', 'Diameter (nm)')
        self.diameter_distribution_plot.showGrid(x=True, y=True, alpha=0.3)
        self.diameter_distribution_plot.setMinimumHeight(280)
        layout.addWidget(self.diameter_distribution_plot)
    
    def _build_ionic_calibration_content(self):
        """Section 5 — Ionic calibration setup + visualization."""
        w = self.calibration_section.content_widget
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(8)

        # ── Setup controls ─────────────────────────────────────────────
        setup_hdr = QLabel("Ionic Calibration Setup")
        setup_hdr.setObjectName("panelHeader")
        layout.addWidget(setup_hdr)

        folder_controls = QHBoxLayout()
        folder_button = QPushButton("Select Calibration Folders")
        folder_button.clicked.connect(self.select_calibration_folders)
        folder_button.setMaximumWidth(250)
        folder_controls.addWidget(folder_button)
        auto_fill_btn = QPushButton("Auto-Fill Concentrations")
        auto_fill_btn.clicked.connect(self.auto_fill_concentrations)
        auto_fill_btn.setToolTip("Auto-detect concentrations from sample names")
        folder_controls.addWidget(auto_fill_btn)
        fill_m1_btn = QPushButton("Fill Selected with -1")
        fill_m1_btn.clicked.connect(self.set_selected_cells_to_minus_one)
        fill_m1_btn.setToolTip("Fill selected cells with -1 to exclude from calibration")
        folder_controls.addWidget(fill_m1_btn)
        folder_controls.addStretch()
        layout.addLayout(folder_controls)

        layout.addWidget(self._hint(
            "Select folders containing ionic standard solutions. "
            "Enter concentrations or use auto-fill. Set to -1 to exclude."
        ))

        self.concentration_table = QTableWidget()
        self.concentration_table.setColumnCount(3)
        self.concentration_table.setHorizontalHeaderLabels(["Sample", "Concentration [ppb]", "Unit"])
        self.concentration_table.setMinimumHeight(200)
        self.concentration_table.setAlternatingRowColors(True)
        self.concentration_table.setColumnWidth(0, 200)
        self.concentration_table.setColumnWidth(1, 150)
        self.concentration_table.setColumnWidth(2, 100)
        self.concentration_table.horizontalHeader().setStretchLastSection(True)
        self.concentration_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.concentration_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.concentration_table.customContextMenuRequested.connect(self.show_concentration_context_menu)
        self.concentration_table.cellClicked.connect(self.on_concentration_table_clicked)
        layout.addWidget(self.concentration_table)

        method_row = QHBoxLayout()
        method_row.addWidget(QLabel("Calibration Method:"))
        self.calibration_method_combo = QComboBox()
        self.calibration_method_combo.addItems(['Force through zero', 'Simple linear', 'Weighted'])
        self.calibration_method_combo.setCurrentText('Force through zero')
        method_row.addWidget(self.calibration_method_combo)
        method_row.addStretch()
        layout.addLayout(method_row)

        calibrate_btn = QPushButton("Calculate Calibration")
        calibrate_btn.clicked.connect(self.calculate_calibration)
        calibrate_btn.setMinimumHeight(40)
        layout.addWidget(calibrate_btn)

        # ── Visualization ──────────────────────────────────────────────
        vis_hdr = QLabel("Sample Data Visualization")
        vis_hdr.setObjectName("panelHeader")
        layout.addWidget(vis_hdr)

        vis_controls = QHBoxLayout()
        vis_controls.addWidget(QLabel("Selected Sample:"))
        self.calibration_sample_label = QLabel("Click a sample row above to view its data")
        self.calibration_sample_label.setObjectName("hintLabel")
        vis_controls.addWidget(self.calibration_sample_label)
        vis_controls.addStretch()
        self.view_toggle_button = QPushButton("📈 Show Calibration")
        self.view_toggle_button.clicked.connect(self.toggle_calibration_view)
        self.view_toggle_button.setMaximumWidth(150)
        self.view_toggle_button.setEnabled(False)
        vis_controls.addWidget(self.view_toggle_button)
        layout.addLayout(vis_controls)

        self.calibration_raw_plot = EnhancedPlotWidget()
        self.calibration_raw_plot.setBackground(theme.palette.plot_bg)
        self.calibration_raw_plot.setLabel('left', 'Counts')
        self.calibration_raw_plot.setLabel('bottom', 'Time (s)')
        self.calibration_raw_plot.showGrid(x=True, y=True, alpha=0.3)
        self.calibration_raw_plot.setMinimumHeight(250)
        layout.addWidget(self.calibration_raw_plot)

        try:
            self.calibration_raw_plot.exclusionRegionsChanged.connect(
                self._on_ionic_calibration_exclusion_changed)
        except Exception as e:
            print(f"Could not connect calibration_raw_plot exclusionRegionsChanged: {e}")
        

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
        self.folder_status_label.setObjectName("statusOk")
        self.folder_status_label.setProperty("statusOk", True)
        self.folder_status_label.style().unpolish(self.folder_status_label)
        self.folder_status_label.style().polish(self.folder_status_label)

        if valid_count > 0 and hasattr(self, 'samples_section'):
            names = [
                self.folder_data[f].get('sample_name', Path(f).name)
                for f in self.particle_folder_paths
                if self.folder_data[f].get('status') == 'Loaded'
            ]
            preview = ', '.join(names[:3])
            if len(names) > 3:
                preview += f'  +{len(names) - 3} more'
            self.samples_section.collapse(f"{valid_count} samples  —  {preview}")

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
            self.element_selection_label.setObjectName("statusOk")
            self.element_selection_label.setProperty("statusOk", True)
            self.element_selection_label.style().unpolish(self.element_selection_label)
            self.element_selection_label.style().polish(self.element_selection_label)
            
            self.load_element_data_for_all_samples()
            self.update_detection_parameters_table()

            if hasattr(self, 'element_section'):
                sym  = element['symbol']
                mass = int(round(element.get('selected_isotope', 0)))
                abun = abundance if 'abundance' in dir() else 0
                self.element_section.collapse(
                    f"{sym}  —  {mass}{sym}"
                    + (f"  ({abun:.1f}%)" if abun else "")
                )
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
                    masses, signals, run_info = loading.vitesse_loading.read_nu_directory(
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
        method selection, thresholds and statistical parameters.

        Returns:
            None
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
            populate_detection_row(self.detection_params_table, i, sample_name, display_label)

            # ── Col 6: Sigma ───────────────────────────────────────────
            sigma_spin = NoWheelDoubleSpinBox()
            sigma_spin.setRange(0.01, 2.0); sigma_spin.setDecimals(3)
            sigma_spin.setSingleStep(0.01); sigma_spin.setValue(0.55)
            sigma_spin.setToolTip("Sigma for Compound Poisson LogNormal threshold")
            self.detection_params_table.setCellWidget(i, 6, sigma_spin)

            # ── Col 7: Iterative ───────────────────────────────────────
            iter_cb = QCheckBox(); iter_cb.setChecked(True)
            iter_cb.setToolTip("Enable iterative background estimation (recommended)")
            self.detection_params_table.setCellWidget(i, 7, iter_cb)

            # ── Col 8: Window Size ─────────────────────────────────────
            ws_container = QWidget()
            ws_layout = QHBoxLayout(ws_container)
            ws_layout.setContentsMargins(2, 2, 2, 2); ws_layout.setSpacing(3)
            ws_cb = QCheckBox(); ws_cb.setChecked(False)
            ws_cb.setToolTip("Enable custom rolling-window for background")
            ws_sb = NoWheelIntSpinBox()
            ws_sb.setRange(500, 100_000); ws_sb.setValue(5000)
            ws_sb.setSingleStep(100); ws_sb.setEnabled(False)
            ws_cb.stateChanged.connect(ws_sb.setEnabled)
            ws_layout.addWidget(ws_cb); ws_layout.addWidget(ws_sb)
            self.detection_params_table.setCellWidget(i, 8, ws_container)

            # ── Col 9: Integration Method ──────────────────────────────
            int_combo = NoWheelComboBox()
            int_combo.addItems(["Background", "Threshold", "Midpoint"])
            self.detection_params_table.setCellWidget(i, 9, int_combo)

            # ── Col 10: Split Method ───────────────────────────────────
            split_combo = NoWheelComboBox()
            split_combo.addItems(["No Splitting", "1D Watershed"])
            split_combo.setCurrentText("1D Watershed")
            self.detection_params_table.setCellWidget(i, 10, split_combo)

            # ── Col 11: Valley Ratio ───────────────────────────────────
            valley_spin = NoWheelDoubleSpinBox()
            valley_spin.setRange(0.01, 0.99); valley_spin.setDecimals(2)
            valley_spin.setSingleStep(0.05); valley_spin.setValue(0.50)
            valley_spin.setToolTip("Valley-to-peak ratio for 1D Watershed splitting")
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

    # ── Exclusion region helpers — particle detection plot ───────────────

    def _visible_exclusion_entries_for(self, sample_name):
        """Return stored exclusion entries for *sample_name* (empty list if none).
        Args:
            sample_name (Any): The sample name.
        Returns:
            object: Result of the operation.
        """
        return self._exclusion_regions_by_sample.get(sample_name, [])

    def _on_exclusion_regions_changed(self):
        """Sync particle-detection plot bands into the bookkeeping store."""
        sample_name = self.sample_combo.currentText()
        if not sample_name:
            return
        try:
            plot_regions = self.plot_widget.get_exclusion_regions()
        except Exception as e:
            print(f"get_exclusion_regions failed: {e}")
            return
        self._exclusion_regions_by_sample[sample_name] = [
            {'bounds': (float(lo), float(hi)), 'scope': 'sample', 'element_key': None}
            for lo, hi, _sc in plot_regions
        ]

    def _rebuild_plot_exclusion_regions(self):
        """Redraw particle-detection exclusion bands when switching sample."""
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

    # ── Exclusion region helpers — ionic calibration plot ────────────────

    def _on_ionic_calibration_exclusion_changed(self):
        """Persist ionic-calibration plot bands into the time-exclusion dicts."""
        folder      = self._current_ionic_cal_folder
        isotope_key = self._current_ionic_cal_isotope_key
        if not folder or not isotope_key:
            return
        try:
            regions = self.calibration_raw_plot.get_exclusion_regions()
        except Exception as e:
            print(f"calibration_raw_plot.get_exclusion_regions failed: {e}")
            return

        elem_regions   = [(float(lo), float(hi)) for lo, hi, sc in regions if sc == 'element']
        sample_regions = [(float(lo), float(hi)) for lo, hi, sc in regions if sc == 'sample']

        key = (folder, isotope_key)
        if elem_regions:
            self._ionic_cal_exclusions_element[key] = elem_regions
        else:
            self._ionic_cal_exclusions_element.pop(key, None)

        if sample_regions:
            self._ionic_cal_exclusions_sample[folder] = sample_regions
        else:
            self._ionic_cal_exclusions_sample.pop(folder, None)

    def _restore_ionic_calibration_exclusions(self, folder_path, isotope_key):
        """Reload stored ionic-calibration exclusion bands onto the plot.
        Args:
            folder_path (Any): The folder path.
            isotope_key (Any): The isotope key.
        """
        key = (folder_path, isotope_key)
        elem_regions   = self._ionic_cal_exclusions_element.get(key, [])
        sample_regions = self._ionic_cal_exclusions_sample.get(folder_path, [])
        combined = ([(lo, hi, 'element') for lo, hi in elem_regions] +
                    [(lo, hi, 'sample')  for lo, hi in sample_regions])
        try:
            self.calibration_raw_plot.set_exclusion_regions(combined)
        except Exception as e:
            print(f"set_exclusion_regions failed: {e}")

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
            pen=PLOT_STYLES['raw_signal'], 
            name='Raw Signal'
        )
        
        self.plot_widget.setBackground(theme.palette.plot_bg)
        self.plot_widget.showGrid(x=True, y=True, alpha=PLOT_STYLES['grid_alpha'])
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
                        is_tofwerk = cached_data.get('is_tofwerk', False)
                        
                        mass_index = np.argmin(np.abs(masses - element_mass))
                        element_symbol = self.selected_element.get('symbol', '')
                        isotope_key = f"{element_symbol}-{element_mass}"

                        if is_tofwerk:
                            dwell_time = cached_data['dwell_time']
                            if hasattr(folder_signals.dtype, 'names') and folder_signals.dtype.names:
                                isotope_signal = folder_signals[folder_signals.dtype.names[mass_index]]
                            else:
                                isotope_signal = folder_signals[:, mass_index]
                        else:
                            run_info = cached_data['run_info']
                            acqtime = run_info["SegmentInfo"][0]["AcquisitionPeriodNs"] * 1e-9
                            accumulations = run_info["NumAccumulations1"] * run_info["NumAccumulations2"]
                            dwell_time = acqtime * accumulations
                            isotope_signal = folder_signals[:, mass_index]

                        time_values = np.arange(len(isotope_signal)) * dwell_time
                        time_mask = np.ones(len(time_values), dtype=bool)
                        for lo, hi in self._ionic_cal_exclusions_element.get(
                                (folder_path, isotope_key), []):
                            time_mask &= ~((time_values >= lo) & (time_values <= hi))
                        for lo, hi in self._ionic_cal_exclusions_sample.get(folder_path, []):
                            time_mask &= ~((time_values >= lo) & (time_values <= hi))
                        if not time_mask.any():
                            continue

                        unit_combo = self.concentration_table.cellWidget(i, 2)
                        unit = unit_combo.currentText() if unit_combo else "ppb"
                        conc_ppb = self.convert_concentration_to_ppb(conc, unit)
                        
                        avg_count_per_second = np.mean(isotope_signal[time_mask]) / dwell_time
                        
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
        Get detection parameters for a specific sample row.

        Args:
            row (int): Row index in the detection parameters table.

        Returns:
            dict: Keys include 'method', 'manual_threshold', 'min_continuous',
                  'alpha', 'sigma', 'iterative', 'use_window_size', 'window_size',
                  'integration_method', 'split_method', 'valley_ratio'.
        """
        params = read_detection_row(self.detection_params_table, row)

        sigma_w = self.detection_params_table.cellWidget(row, 6)
        iter_w  = self.detection_params_table.cellWidget(row, 7)
        ws_cont = self.detection_params_table.cellWidget(row, 8)
        int_w   = self.detection_params_table.cellWidget(row, 9)
        split_w = self.detection_params_table.cellWidget(row, 10)
        val_w   = self.detection_params_table.cellWidget(row, 11)

        params['sigma']             = sigma_w.value()        if sigma_w  is not None else 0.55
        params['iterative']         = iter_w.isChecked()     if iter_w   is not None else True

        ws_cb = ws_cont.findChild(QCheckBox) if ws_cont is not None else None
        ws_sb = ws_cont.findChild(QSpinBox)  if ws_cont is not None else None
        params['use_window_size']   = ws_cb.isChecked() if ws_cb is not None else False
        params['window_size']       = ws_sb.value()     if ws_sb is not None else 5000

        params['integration_method']= int_w.currentText()   if int_w   is not None else "Background"
        params['split_method']      = split_w.currentText()  if split_w is not None else "1D Watershed"
        params['valley_ratio']      = val_w.value()          if val_w   is not None else 0.50

        return params

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
                
                color = snr_to_color(height_threshold_ratio)
                
                for item in [sample_item, start_item, end_item, counts_item, height_item]:
                    item.setBackground(color)
                
                self.results_table.setItem(row_position, 0, sample_item)
                self.results_table.setItem(row_position, 1, start_item)
                self.results_table.setItem(row_position, 2, end_item)
                self.results_table.setItem(row_position, 3, counts_item)
                self.results_table.setItem(row_position, 4, height_item)
        
        self.results_table.setSortingEnabled(True)
        self.results_table.sortItems(0, Qt.AscendingOrder)

        if hasattr(self, 'results_section'):
            n = self.results_table.rowCount()
            self.results_section.expand()
            self.results_section.set_status(
                f"{n} particle{'s' if n != 1 else ''} detected"
            )

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

                if hasattr(self, 'detection_section'):
                    self.detection_section.expand()

    def calculate_particle_mass(self, diameter, density):
        """
        Calculate the mass of a spherical particle in femtograms.
        
        Args:
            diameter (float): Particle diameter in nanometers.
            density (float): Particle density in g/cm³.
            
        Returns:
            float: Particle mass in femtograms.
        """
        return particle_mass_from_diameter(diameter, density)['mass_fg']
    
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

            if hasattr(self, 'analysis_section'):
                self.analysis_section.expand()

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
        choice = show_data_source_dialog(self)
        if choice == "folder":
            self.select_calibration_nu_folders()
        elif choice == "csv":
            self.select_calibration_data_files()
        elif choice == "tofwerk":
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
                    if not loading.tofwerk_loading.is_tofwerk_file(h5_file):
                        raise ValueError(f"Not a valid TOFWERK file: {h5_file.name}")
                    
                    sample_name = h5_file.stem
                    
                    data, info, dwell_time = loading.tofwerk_loading.read_tofwerk_file(h5_path)
                    
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
                        
                    masses, signals, run_info = loading.vitesse_loading.read_nu_directory(path)
                    
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
        from loading.import_csv_dialogs import show_csv_calibration_dialog
        
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
        choice = show_data_source_dialog(self)
        if choice == "folder":
            self.select_nu_folders()
        elif choice == "csv":
            self.select_data_files()
        elif choice == "tofwerk":
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
                    if not loading.tofwerk_loading.is_tofwerk_file(h5_file):
                        raise ValueError(f"Not a valid TOFWERK file: {h5_file.name}")
                    
                    sample_name = h5_file.stem
                    
                    try:
                        from loading.data_thread import DataProcessThread
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
                    masses, signals, run_info = loading.vitesse_loading.read_nu_directory(
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
        from loading.import_csv_dialogs import show_csv_structure_dialog, CSVDataProcessThread
        
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
            
            from loading.import_csv_dialogs import CSVDataProcessThread
            
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
        Uses EnhancedPlotWidget so the user can draw time-exclusion bands
        that will be respected by calculate_calibration (mirrors ionic_CAL.py).
        
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
            
            element_symbol = self.selected_element['symbol']
            isotope_key = f"{element_symbol}-{element_mass}"
            
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
            
            isotope_label = f"{int(round(element_mass))}{element_symbol}"
            self.calibration_raw_plot.setLabel('left', 'Counts')
            self.calibration_raw_plot.setLabel('bottom', 'Time (s)')
            
            source_type = "TOFWERK" if is_tofwerk else cached_data.get('source_type', 'NU').upper()
            self.calibration_raw_plot.setTitle(f"Raw Data - {sample_name} ({isotope_label}) [{source_type}]")

            self._current_ionic_cal_folder      = folder_path
            self._current_ionic_cal_isotope_key = isotope_key

            self._restore_ionic_calibration_exclusions(folder_path, isotope_key)

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
                masses, _, _ = loading.vitesse_loading.read_nu_directory(folder, max_integ_files=1)
                
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

                    element_symbol = self.selected_element.get('symbol', '')
                    isotope_key = f"{element_symbol}-{element_mass}"
                    
                    if is_tofwerk:
                        dwell_time = cached_data['dwell_time']
                        
                        if hasattr(folder_signals.dtype, 'names') and folder_signals.dtype.names:
                            field_name = folder_signals.dtype.names[mass_index]
                            isotope_signal = folder_signals[field_name]
                        else:
                            isotope_signal = folder_signals[:, mass_index]
                        
                    else:
                        run_info = cached_data['run_info']
                        acqtime = run_info["SegmentInfo"][0]["AcquisitionPeriodNs"] * 1e-9
                        accumulations = run_info["NumAccumulations1"] * run_info["NumAccumulations2"]
                        dwell_time = acqtime * accumulations
                        isotope_signal = folder_signals[:, mass_index]

                    time_values = np.arange(len(isotope_signal)) * dwell_time
                    time_mask = np.ones(len(time_values), dtype=bool)
                    for lo, hi in self._ionic_cal_exclusions_element.get(
                            (folder_path, isotope_key), []):
                        time_mask &= ~((time_values >= lo) & (time_values <= hi))
                    for lo, hi in self._ionic_cal_exclusions_sample.get(folder_path, []):
                        time_mask &= ~((time_values >= lo) & (time_values <= hi))
                    if not time_mask.any():
                        continue

                    avg_count_per_second = np.mean(isotope_signal[time_mask]) / dwell_time
                    
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
        
        colors = HISTOGRAM_COLORS    
        
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

        Returns:
            None
        """
        export_table_to_csv(self.results_table, self)
    

if __name__ == '__main__':
    app = QApplication([])
    window = MassMethodWidget()
    window.showMaximized()
    app.exec()