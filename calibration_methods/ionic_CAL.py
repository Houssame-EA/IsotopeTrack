import sys
import json
import numpy as np
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                               QFileDialog, QMessageBox, QDialog, QListWidget, QListWidgetItem,
                               QListView, QAbstractItemView, QTreeView, QComboBox, QLabel,
                               QScrollArea, QSplitter, QGroupBox, QMenu, QTabWidget,
                               QToolBar, QStatusBar, QMainWindow, QFrame, QToolButton, QRadioButton, QDoubleSpinBox,
                               QLineEdit, QCheckBox, QProgressDialog)
from PySide6.QtCore import Qt, QSize, Signal, QTimer, QEvent
from PySide6.QtGui import QIcon, QKeySequence, QFont, QColor, QBrush, QPalette, QDoubleValidator, QAction, QShortcut
import loading.vitesse_loading
from widget.periodic_table_widget import PeriodicTableWidget
from widget.custom_plot_widget import BasicPlotWidget, CalibrationPlotWidget, EnhancedPlotWidget
import os
import pandas as pd
import qtawesome as qta
import loading.tofwerk_loading

from calibration_methods.te_common import (
    BASE_STYLESHEET, NumericDelegate, RETURN_BUTTON_STYLE,
    base_stylesheet, return_button_style,
)


from theme import theme

# ── user-action logging ──────────────────────────────────────────────────────
def _ual():
    """Return the UserActionLogger, or None if logging isn't ready.
    Returns:
        object: Result of the operation.
    """
    try:
        from tools.logging_utils import logging_manager
        return logging_manager.get_user_action_logger()
    except Exception:
        return None


def _build_ionic_qss(p) -> str:
    """Full stylesheet for the Ionic Calibration window, built from a
    theme Palette.  Covers main window, toolbar, tabs, tables, buttons,
    inputs, group boxes, scroll areas, and the status bar.
    Args:
        p (Any): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        /* Base window + widgets ---------------------------------------- */
        QMainWindow, QWidget {{
            background-color: {p.bg_primary};
            color: {p.text_primary};
        }}

        /* Toolbar ------------------------------------------------------ */
        QToolBar {{
            background-color: {p.bg_secondary};
            border: none;
            border-bottom: 1px solid {p.border};
            padding: 4px;
            spacing: 4px;
        }}
        QToolButton {{
            background-color: transparent;
            color: {p.text_primary};
            border: 1px solid transparent;
            border-radius: 4px;
            padding: 5px 8px;
        }}
        QToolButton:hover {{
            background-color: {p.bg_hover};
            border: 1px solid {p.border};
        }}
        QToolButton:pressed,
        QToolButton:checked {{
            background-color: {p.accent_soft};
            border: 1px solid {p.accent};
            color: {p.text_primary};
        }}

        /* Tabs --------------------------------------------------------- */
        QTabWidget::pane {{
            border: 1px solid {p.border};
            background-color: {p.bg_secondary};
            border-radius: 4px;
            top: -1px;
        }}
        /* The QTabBar itself — the strip the tabs sit on.  Without this
           the area to the right of the last tab shows the OS default
           (white on macOS). */
        QTabBar {{
            background-color: {p.bg_primary};
            qproperty-drawBase: 0;
        }}
        QTabWidget::tab-bar {{
            alignment: left;
        }}
        QTabBar::tab {{
            background-color: {p.bg_tertiary};
            color: {p.text_secondary};
            padding: 8px 16px;
            border: 1px solid {p.border};
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border-bottom: 1px solid {p.bg_secondary};
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {p.bg_hover};
            color: {p.text_primary};
        }}

        /* Tables ------------------------------------------------------- */
        QTableWidget {{
            background-color: {p.bg_secondary};
            alternate-background-color: {p.bg_tertiary};
            color: {p.text_primary};
            gridline-color: {p.border};
            border: 1px solid {p.border};
            border-radius: 4px;
            selection-background-color: {p.accent_soft};
            selection-color: {p.text_primary};
        }}
        QTableWidget::item {{
            padding: 4px 6px;
        }}
        QTableWidget::item:selected {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
        }}
        QHeaderView::section {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            padding: 6px;
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
            font-weight: bold;
        }}
        QTableCornerButton::section {{
            background-color: {p.bg_tertiary};
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
        }}

        /* Buttons (non-special — special ones use object names) ------- */
        QPushButton {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 6px 14px;
        }}
        QPushButton:hover {{
            background-color: {p.bg_hover};
            border: 1px solid {p.accent};
        }}
        QPushButton:pressed {{
            background-color: {p.accent_pressed};
            color: {p.text_inverse};
            border-color: {p.accent_pressed};
        }}
        QPushButton:disabled {{
            background-color: {p.bg_secondary};
            color: {p.text_muted};
            border: 1px solid {p.border_subtle};
        }}

        /* Inputs ------------------------------------------------------- */
        QLineEdit,
        QComboBox,
        QDoubleSpinBox,
        QSpinBox {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 4px 8px;
            selection-background-color: {p.accent};
            selection-color: {p.text_inverse};
        }}
        QLineEdit:focus,
        QComboBox:focus,
        QDoubleSpinBox:focus,
        QSpinBox:focus {{
            border: 1px solid {p.accent};
        }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox QAbstractItemView {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            selection-background-color: {p.accent_soft};
            selection-color: {p.text_primary};
            border: 1px solid {p.border};
            outline: 0;
        }}

        /* Check + radio indicators ------------------------------------ */
        QCheckBox, QRadioButton {{
            color: {p.text_primary};
            background-color: transparent;
            spacing: 6px;
        }}
        QCheckBox::indicator,
        QRadioButton::indicator {{
            width: 16px;
            height: 16px;
        }}
        QCheckBox::indicator:unchecked {{
            border: 1px solid {p.border};
            background-color: {p.bg_tertiary};
            border-radius: 3px;
        }}
        QCheckBox::indicator:checked {{
            border: 1px solid {p.accent};
            background-color: {p.accent};
            border-radius: 3px;
        }}
        QRadioButton::indicator:unchecked {{
            border: 2px solid {p.border};
            background-color: {p.bg_tertiary};
            border-radius: 9px;
        }}
        QRadioButton::indicator:checked {{
            border: 2px solid {p.accent};
            background-color: {p.accent};
            border-radius: 9px;
        }}

        /* Group boxes ------------------------------------------------- */
        QGroupBox {{
            color: {p.text_primary};
            background-color: {p.bg_secondary};
            border: 1px solid {p.border};
            border-radius: 6px;
            margin-top: 1em;
            padding-top: 10px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            padding: 0 8px;
        }}

        /* Scroll areas + scrollbars ----------------------------------- */
        QScrollArea {{
            background-color: transparent;
            border: none;
        }}
        QScrollBar:vertical {{
            background: {p.bg_primary};
            width: 10px;
            border: none;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {p.border};
            border-radius: 5px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {p.text_muted}; }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{
            background: {p.bg_primary};
            height: 10px;
            border: none;
            margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {p.border};
            border-radius: 5px;
            min-width: 20px;
        }}
        QScrollBar::handle:horizontal:hover {{ background: {p.text_muted}; }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{ width: 0; }}

        /* Menus, tooltips, splitters, status bar ---------------------- */
        QMenu {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            padding: 4px;
        }}
        QMenu::item {{ padding: 5px 20px; }}
        QMenu::item:selected {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
        }}
        QToolTip {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            padding: 4px;
        }}
        QSplitter::handle {{ background-color: {p.border}; }}
        QStatusBar {{
            background-color: {p.bg_secondary};
            color: {p.text_secondary};
            border-top: 1px solid {p.border};
        }}

        /* Named widgets (object-name-targeted) ------------------------ */
        QLabel#helpInfo {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
            padding: 10px;
            border-radius: 4px;
        }}
        QLabel#helpWarning {{
            background-color: {p.warning_bg};
            color: {p.text_primary};
            border: 1px solid {p.warning_border};
            padding: 10px;
            border-radius: 4px;
        }}
        QLabel#helpMuted {{
            color: {p.text_muted};
            margin-left: 20px;
            font-size: 11px;
        }}
        QLabel#dialogInstruction {{
            color: {p.text_primary};
            font-size: 14px;
            font-weight: bold;
            margin: 10px;
        }}
        QLabel#titleLabel {{
            color: {p.text_primary};
            font-size: 20px;
            font-weight: bold;
        }}
        QFrame#tableFrame {{
            background-color: {p.bg_secondary};
            border: 1px solid {p.border};
            border-radius: 4px;
        }}
        QPushButton#primaryBtn {{
            background-color: {p.success};
            color: {p.text_inverse};
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
            min-width: 80px;
        }}
        QPushButton#primaryBtn:hover {{
            background-color: {p.accent_hover};
        }}
        QPushButton#secondaryBtn {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
            min-width: 80px;
        }}
        QPushButton#secondaryBtn:hover {{
            background-color: {p.bg_hover};
            border-color: {p.accent};
        }}
    """


def _build_ionic_status_colors(p) -> dict:
    """Row-highlight colors used to indicate calibration method status in
    the results table.  Keeps the orange/green/blue semantics across light
    and dark themes — in dark mode they're muted so they don't blind the
    user while still being distinguishable at a glance.

    Keys:
        manual    — manual override (was #ffe6cc orange)
        auto      — auto-selected / best R² (was #e8f5e8 green)
        selected  — manually selected by user (was #e6f3ff blue)
        base      — neutral background for unhighlighted cells
        text      — foreground color that reads on all three backgrounds
    Args:
        p (Any): The p.
    Returns:
        dict: Result of the operation.
    """
    if p.name == "dark":
        return {
            "manual":   QColor("#5a3a2a"),
            "auto":     QColor("#2a4a2a"),
            "selected": QColor("#1f3a52"),
            "base":     QColor(p.bg_tertiary),
            "text":     QColor(p.text_primary),
        }
    return {
        "manual":   QColor("#ffe6cc"),
        "auto":     QColor("#e8f5e8"),
        "selected": QColor("#e6f3ff"),
        "base":     QColor("#f8f9fa"),
        "text":     QColor(p.text_primary),
    }


class IonicCalibrationWindow(QMainWindow):
    calibration_completed = Signal(str, dict)
    method_preference_changed = Signal(dict)
    isotopes_selection_changed = Signal(dict)
    
    def __init__(self, parent=None):
        """
        Initialize the Ionic Calibration Window.
        
        Args:
            parent: Parent widget, typically the main application window
        """
        super().__init__(parent)
        self.setWindowTitle("Ionic Calibration Analysis")
        
        self.parent_window = parent
        self.selected_isotopes = {}
        if parent and hasattr(parent, 'selected_isotopes'):
            self.selected_isotopes = parent.selected_isotopes.copy()
        
        self.folder_paths = []
        self.data = {}
        self.isotope_method_preferences = {}
        self.concentration_units = {
            'ppb': 1
        }
        self.base_unit = 'ppb'
        self.calibration_results = {}
        self.sensitivity_overrides = {}
        self.all_masses = None
        self.is_compressed_data = False 
        self.data_modified = False 
        self.periodic_table = PeriodicTableWidget()
        self.ignore_item_changed = False
        self.current_unit = 'ppb'
        self.last_selected_row = None
        self.last_selected_col = None


        self.excluded_points = {}

        self._outlier_indices_by_isotope = {}
        self._time_exclusions_element = {}
        self._time_exclusions_sample  = {}
        
        self.initUI()

        ual = _ual()
        if ual:
            ual.log_action('DIALOG_OPEN', 'Opened Ionic Calibration window',
                           {'has_parent': parent is not None,
                            'isotope_count': sum(len(v) for v in self.selected_isotopes.values())})

        if self.selected_isotopes:
            self.update_table_columns()
            self.update_element_isotope_combo()

    def initUI(self):
        """
        Initialize and configure the user interface.
        
        Sets up stylesheets, creates tab widget with three tabs (Data Management,
        Manual Sensitivity, Calibration Results), toolbar, and status bar.
        """

        self.apply_theme()
        self._theme_cleanup = theme.connect_theme(self.apply_theme)
        self.destroyed.connect(lambda *_: self._theme_cleanup())

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)
        
        header_layout = QHBoxLayout()

        title_label = QLabel("Ionic Calibration Analysis")
        title_label.setObjectName("titleLabel")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.return_button = QPushButton("Back to Main")
        self.return_button.setObjectName("returnButton")
        self.return_button.setFixedSize(150, 45)
        self._refresh_return_button()
        def _back_to_main():
            ual = _ual()
            if ual:
                ual.log_action('CLICK', 'Ionic Calibration — Back to Main')
            self.hide()
        self.return_button.clicked.connect(_back_to_main)
        header_layout.addWidget(self.return_button)
        
        main_layout.addLayout(header_layout)
                
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.setTabShape(QTabWidget.TabShape.Rounded)
        self.tab_widget.setDocumentMode(True)
        
        self.data_tab = QWidget()
        self.sensitivity_tab = QWidget()  
        self.calibration_tab = QWidget()
        
        self.setup_toolbar()
        
        self.setup_data_tab()
        self.setup_sensitivity_tab()
        self.setup_calibration_tab()
        
        self.tab_widget.addTab(self.data_tab, "Data Management")
        self.tab_widget.addTab(self.sensitivity_tab, "Manual Sensitivity")
        self.tab_widget.addTab(self.calibration_tab, "Calibration Results")
        
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")
        
        main_layout.addWidget(self.tab_widget)
        self.tab_widget.currentChanged.connect(self._log_tab_switch)

        self.resize(1280, 900)

        self.create_shortcuts()

    def apply_theme(self, *_):
        """Re-apply the full ionic-calibration stylesheet from the current
        theme palette.  Called on init and whenever the user toggles light/
        dark — any widgets that show dynamic colors (e.g. the results table
        status cells) are refreshed via refresh_status_colors().
        Args:
            *_ (Any): Additional positional arguments.
        """
        p = theme.palette
        self.setStyleSheet(_build_ionic_qss(p))
        self._status_colors = _build_ionic_status_colors(p)
        self._refresh_plot_label_colors()
        self._refresh_results_table_colors()
        self._refresh_return_button()

    def _refresh_return_button(self):
        """Apply the current theme's return-button style + a readable icon
        color.  The button widget may not exist yet on the first call from
        initUI — check before touching it.
        """
        btn = getattr(self, "return_button", None)
        if btn is None:
            return
        p = theme.palette
        btn.setStyleSheet(return_button_style(p))

        icon_color = "#ffffff" if p.name == "dark" else "#B81414"
        btn.setIcon(qta.icon('fa6s.house', color=icon_color))

    def _refresh_plot_label_colors(self):
        """Swap the pyqtgraph axis label color to the current theme's
        plot_fg.  No-op if the plot widget hasn't been created yet.
        """
        widget = getattr(self, "count_vs_time_widget", None)
        if widget is None:
            return
        try:
            fg = theme.palette.plot_fg
            for axis in ("bottom", "left"):
                try:
                    label = widget.getAxis(axis).label.toPlainText()
                except Exception:
                    label = ""
                widget.setLabel(axis, label, color=fg)
        except Exception:
            pass

    def _refresh_results_table_colors(self):
        """When the theme changes, any existing background QBrush() values
        on results-table items are stale.  Re-run display_results() to
        re-paint them with the new palette, if the data is available.
        """
        if not hasattr(self, "results_table"):
            return

        try:
            if getattr(self, "calibration_results", None):
                self.display_results()
        except Exception:
            pass

    def setup_toolbar(self):
        """
        Create and configure the main toolbar.
        
        Adds actions for loading folders, saving/loading sessions, calculating calibration,
        selecting elements, and unit selection combo box.
        """
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        load_action = QAction("Load Folders", self)
        load_action.setStatusTip("Load data folders")
        load_action.triggered.connect(self.load_folders)
        
        save_action = QAction("Save Session", self)
        save_action.setStatusTip("Save current session")
        save_action.triggered.connect(self.save_session)
        
        load_session_action = QAction("Load Session", self)
        load_session_action.setStatusTip("Load saved session")
        load_session_action.triggered.connect(self.load_session)
        
        calculate_action = QAction("Calculate", self)
        calculate_action.setStatusTip("Calculate calibration")
        calculate_action.triggered.connect(self.calculate_calibration)
        
        element_select_action = QAction("Select Elements", self)
        element_select_action.setStatusTip("Select elements and isotopes")
        element_select_action.triggered.connect(self.show_periodic_table)
        
        toolbar.addAction(load_action)
        toolbar.addAction(save_action)
        toolbar.addAction(load_session_action)
        toolbar.addSeparator()
        toolbar.addAction(calculate_action)
        toolbar.addAction(element_select_action)
        
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Unit:"))
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(['ppb'])
        self.unit_combo.currentTextChanged.connect(self.update_concentration_unit)
        toolbar.addWidget(self.unit_combo)
        
        self.save_action = save_action
        self.calculate_action = calculate_action

    def setup_data_tab(self):
        """
        Set up the Data Management tab.
        
        Creates table for calibration samples, controls for auto-fill and batch operations,
        and count vs time plot widget with sample selection controls.
        """
        layout = QVBoxLayout(self.data_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        help_label = QLabel(
            "Load folders containing calibration data, then set concentration values for each sample. "
            "Select elements from the periodic table to add columns. Use right-click for additional options."
        )
        help_label.setWordWrap(True)
        help_label.setObjectName("helpInfo")
        layout.addWidget(help_label)
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        data_table_group = QGroupBox("Calibration Samples")
        data_table_layout = QVBoxLayout(data_table_group)
        data_table_layout.setContentsMargins(10, 15, 10, 10)
        
        self.table = QTableWidget()
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Sample"])
        
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setDefaultSectionSize(50)    
        self.table.setColumnWidth(0, 200)
        
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.keyPressEvent = self.table_key_press_event
        
        numeric_delegate = NumericDelegate(self.table)
        self.table.setItemDelegateForColumn(0, numeric_delegate)
        
        self.table.itemChanged.connect(self.on_data_changed)
        self.table.cellClicked.connect(self.on_table_cell_clicked)
        
        table_frame = QFrame()
        table_frame.setFrameShape(QFrame.Shape.StyledPanel)
        table_frame.setObjectName("tableFrame")
        table_frame_layout = QVBoxLayout(table_frame)
        table_frame_layout.setContentsMargins(1, 1, 1, 1)
        table_frame_layout.addWidget(self.table)
        data_table_layout.addWidget(table_frame)
        
        table_buttons_layout = QHBoxLayout()
        
        fill_minus_one_btn = QPushButton("Fill Selected with -1")
        fill_minus_one_btn.clicked.connect(self.set_selected_cells_to_minus_one)
        fill_minus_one_btn.setToolTip("Fill selected cells with -1 (exclude from calibration)")
        
        auto_fill_btn = QPushButton("Auto-Fill Concentrations")
        auto_fill_btn.clicked.connect(self.auto_fill_concentrations)
        auto_fill_btn.setToolTip("Attempt to auto-detect concentrations from sample names")
        
        table_buttons_layout.addWidget(fill_minus_one_btn)
        table_buttons_layout.addWidget(auto_fill_btn)
        table_buttons_layout.addStretch()
        data_table_layout.addLayout(table_buttons_layout)
        
        splitter.addWidget(data_table_group)
        
        count_time_group = QGroupBox("Count vs Time")
        count_time_layout = QVBoxLayout(count_time_group)
        count_time_layout.setContentsMargins(10, 15, 10, 10)
        
        plot_controls = QHBoxLayout()
        self.sample_combo = QComboBox()
        self.sample_combo.currentIndexChanged.connect(self.update_time_plot)
    
        self.plot_isotope_combo = QComboBox()
        self.plot_isotope_combo.currentIndexChanged.connect(self.update_time_plot)
        
        self.normalize_check = QComboBox()
        self.normalize_check.addItems(["Raw Counts", "Normalized (CPS)"])
        self.normalize_check.currentIndexChanged.connect(self.update_time_plot)
        plot_controls.addWidget(self.normalize_check)
        
        plot_controls.addStretch()
        count_time_layout.addLayout(plot_controls)
        
        self.count_vs_time_widget = EnhancedPlotWidget()
        self.count_vs_time_widget.setMinimumHeight(250)
        self.count_vs_time_widget.exclusionRegionsChanged.connect(
            self._on_time_exclusion_changed)
        count_time_layout.addWidget(self.count_vs_time_widget)
        
        splitter.addWidget(count_time_group)
        
        layout.addWidget(splitter)
        
        splitter.setSizes([400, 300])

    def setup_sensitivity_tab(self):
        """
        Set up the Manual Sensitivity tab.
        
        Creates global controls for applying manual slopes, sensitivity table for
        per-element configuration, and export functionality for sensitivity settings.
        """
        layout = QVBoxLayout(self.sensitivity_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        help_label = QLabel(
            "Configure manual sensitivity values for specific elements. "
            "Check the 'Override' checkbox to use manual slope instead of calibration results. "
            "This allows you to selectively override individual elements."
        )
        help_label.setWordWrap(True)
        help_label.setObjectName("helpWarning")
        layout.addWidget(help_label)
        
        global_controls_group = QGroupBox("Global Controls")
        global_controls_layout = QVBoxLayout(global_controls_group)
        global_controls_layout.setContentsMargins(10, 15, 10, 10)
        
        global_slope_controls = QHBoxLayout()
        
        global_slope_controls.addWidget(QLabel("Global Manual Slope:"))
        self.global_manual_slope_input = QDoubleSpinBox()
        self.global_manual_slope_input.setRange(0.0, 1e15)
        self.global_manual_slope_input.setDecimals(2)
        self.global_manual_slope_input.setValue(10.0)
        self.global_manual_slope_input.setSuffix(" cps/ppb")
        global_slope_controls.addWidget(self.global_manual_slope_input)
        
        apply_all_btn = QPushButton("Apply to All Elements")
        apply_all_btn.clicked.connect(self.apply_global_slope_to_all)
        apply_all_btn.setToolTip("Apply global slope value to all elements in the table")
        global_slope_controls.addWidget(apply_all_btn)
        
        apply_checked_btn = QPushButton("Apply to Checked Only")
        apply_checked_btn.clicked.connect(self.apply_global_slope_to_checked)
        apply_checked_btn.setToolTip("Apply global slope value only to elements with Override checked")
        global_slope_controls.addWidget(apply_checked_btn)
        
        global_slope_controls.addStretch()
        global_controls_layout.addLayout(global_slope_controls)
        
        layout.addWidget(global_controls_group)
        
        sensitivity_table_group = QGroupBox("Element Sensitivity Settings")
        sensitivity_table_layout = QVBoxLayout(sensitivity_table_group)
        sensitivity_table_layout.setContentsMargins(10, 15, 10, 10)
        
        self.sensitivity_table = QTableWidget()
        self.sensitivity_table.setColumnCount(4)
        self.sensitivity_table.setHorizontalHeaderLabels([
            "Element", "Override", "Manual Slope (cps/ppb)", "Density (g/cm³)"
        ])
        self.sensitivity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sensitivity_table.setAlternatingRowColors(True)
        self.sensitivity_table.setMinimumHeight(300)
        
        sensitivity_table_layout.addWidget(self.sensitivity_table)
        
        export_controls = QHBoxLayout()
        export_sensitivity_btn = QPushButton("Export Sensitivity Settings")
        export_sensitivity_btn.clicked.connect(self.export_sensitivity_results)
        export_controls.addStretch()
        export_controls.addWidget(export_sensitivity_btn)
        sensitivity_table_layout.addLayout(export_controls)
        
        layout.addWidget(sensitivity_table_group)

    def setup_calibration_tab(self):
        """
        Set up the Calibration Results tab.
        
        Creates calibration plot widget, method selection controls, results table
        with filtering options, and export functionality.
        """
        layout = QVBoxLayout(self.calibration_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        calibration_group = QGroupBox("Calibration Plot")
        calibration_layout = QVBoxLayout(calibration_group)
        calibration_layout.setContentsMargins(10, 15, 10, 10)
        
        # ── Single unified control bar ──────────────────────────────────
        calib_controls = QHBoxLayout()
        calib_controls.setSpacing(6)

        calib_controls.addWidget(QLabel("Isotope:"))

        self.prev_isotope_btn = QPushButton("◀")
        self.prev_isotope_btn.setFixedSize(26, 26)
        self.prev_isotope_btn.setToolTip("Previous isotope")
        self.prev_isotope_btn.clicked.connect(self._go_prev_isotope)
        calib_controls.addWidget(self.prev_isotope_btn)

        self.element_isotope_combo = QComboBox()
        self.element_isotope_combo.setMinimumWidth(90)
        self.element_isotope_combo.setMaximumWidth(120)
        self.element_isotope_combo.currentTextChanged.connect(self.display_selected_calibration)
        calib_controls.addWidget(self.element_isotope_combo)

        self.next_isotope_btn = QPushButton("▶")
        self.next_isotope_btn.setFixedSize(26, 26)
        self.next_isotope_btn.setToolTip("Next isotope")
        self.next_isotope_btn.clicked.connect(self._go_next_isotope)
        calib_controls.addWidget(self.next_isotope_btn)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        calib_controls.addWidget(sep1)

        calib_controls.addWidget(QLabel("Method:"))
        self.calibration_method_combo = QComboBox()
        self.calibration_method_combo.addItems(['Force through zero', 'Simple linear', 'Weighted', 'Manual'])
        self.calibration_method_combo.setMinimumWidth(130)
        self.calibration_method_combo.currentTextChanged.connect(self.update_calibration_display)
        calib_controls.addWidget(self.calibration_method_combo)

        self.manual_slope_label = QLabel("Slope:")
        calib_controls.addWidget(self.manual_slope_label)

        self.manual_slope_input = QDoubleSpinBox()
        self.manual_slope_input.setRange(0.0, 1e15)
        self.manual_slope_input.setDecimals(4)
        self.manual_slope_input.setValue(10.0)
        self.manual_slope_input.setSuffix(" cps/ppb")
        self.manual_slope_input.setGroupSeparatorShown(True)
        self.manual_slope_input.setMinimumWidth(160)
        self.manual_slope_input.setToolTip(
            "Manual calibration slope for the current isotope.\n"
            "Changes are applied live.")
        self.manual_slope_input.editingFinished.connect(self.on_manual_slope_changed)
        calib_controls.addWidget(self.manual_slope_input)

        self.manual_match_btn = QPushButton("Match fit")
        self.manual_match_btn.setMaximumWidth(80)
        self.manual_match_btn.setToolTip("Copy the Simple linear slope into the manual input.")
        self.manual_match_btn.clicked.connect(self.on_manual_match_fit)
        calib_controls.addWidget(self.manual_match_btn)

        self._set_manual_slope_controls_visible(False)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        calib_controls.addWidget(sep2)

        calib_controls.addWidget(QLabel("Apply to All:"))
        self.global_method_combo = QComboBox()
        self.global_method_combo.addItems([
            'Auto (Best R²)',
            'Force through zero',
            'Simple linear',
            'Weighted',
            'Manual'
        ])
        self.global_method_combo.setMinimumWidth(120)
        self.global_method_combo.setToolTip("Set calibration method for all isotopes at once")
        calib_controls.addWidget(self.global_method_combo)

        apply_global_btn = QPushButton("Apply")
        apply_global_btn.setMaximumWidth(70)
        apply_global_btn.clicked.connect(self.apply_global_method)
        apply_global_btn.setToolTip("Apply selected method to all isotopes")
        calib_controls.addWidget(apply_global_btn)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.VLine)
        sep3.setFrameShadow(QFrame.Shadow.Sunken)
        calib_controls.addWidget(sep3)

        self.include_all_btn = QPushButton("Include all")
        self.include_all_btn.setToolTip("Clear all exclusions for the current isotope.")
        self.include_all_btn.clicked.connect(self.reset_current_isotope_exclusions)
        calib_controls.addWidget(self.include_all_btn)

        self.exclusion_status_label = QLabel("")
        self.exclusion_status_label.setStyleSheet("color: #888;")
        calib_controls.addWidget(self.exclusion_status_label)

        calib_controls.addStretch()
        calibration_layout.addLayout(calib_controls)

        self.calibration_widget = CalibrationPlotWidget()
        self.calibration_widget.setMinimumHeight(280)

        self.calibration_widget.point_exclusion_toggled.connect(
            self.on_calibration_point_exclusion_toggled)
        calibration_layout.addWidget(self.calibration_widget)
        
        splitter.addWidget(calibration_group)
        
        results_group = QGroupBox("Calibration Results")
        results_layout = QVBoxLayout(results_group)
        results_layout.setContentsMargins(10, 15, 10, 10)
        
        filter_controls = QHBoxLayout()
        filter_controls.addWidget(QLabel("Filter Results:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(['All Results', 'Show Best Method Only'])
        self.filter_combo.currentIndexChanged.connect(self.filter_results_table)
        filter_controls.addWidget(self.filter_combo)
        
        export_btn = QPushButton("Export Results")
        export_btn.clicked.connect(self.export_results)
        filter_controls.addStretch()
        filter_controls.addWidget(export_btn)
        
        results_layout.addLayout(filter_controls)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(9)
        self.results_table.setHorizontalHeaderLabels([
            "Isotope", "Method", "Slope (cps/conc)", "Intercept (cps)", "BEC", "R-squared", 
            "Density (g/cm³)", "LOD", "LOQ"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setMinimumHeight(200)
        
        self.results_table.setSortingEnabled(True)
        self.results_table.horizontalHeader().setSectionsClickable(True)
        
        results_layout.addWidget(self.results_table)
        
        splitter.addWidget(results_group)
        
        layout.addWidget(splitter)
        
        splitter.setSizes([500, 300])
        
    def _log_tab_switch(self, index):
        """Log which tab the user switches to.
        Args:
            index (Any): Row or item index.
        """
        tab_names = ["Data Management", "Manual Sensitivity", "Calibration Results"]
        name = tab_names[index] if index < len(tab_names) else str(index)
        ual = _ual()
        if ual:
            ual.log_action('CLICK', f'Ionic Calibration tab: {name}',
                           {'tab': name, 'index': index})

    def create_shortcuts(self):
        """
        Create keyboard shortcuts for common actions.
        
        Sets up shortcuts for loading (Ctrl+O), saving (Ctrl+S), session loading (Ctrl+L),
        calculation (F5), element selection (Ctrl+E), and tab navigation (Ctrl+Tab).
        """
        load_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        load_shortcut.activated.connect(self.load_folders)
        
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_session)
        
        load_session_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        load_session_shortcut.activated.connect(self.load_session)
        
        calc_shortcut = QShortcut(QKeySequence("F5"), self)
        calc_shortcut.activated.connect(self.calculate_calibration)
        
        elements_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        elements_shortcut.activated.connect(self.show_periodic_table)
        
        next_tab_shortcut = QShortcut(QKeySequence("Ctrl+Tab"), self)
        next_tab_shortcut.activated.connect(self.next_tab)
        
        prev_tab_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self)
        prev_tab_shortcut.activated.connect(self.prev_tab)

        prev_iso_shortcut = QShortcut(QKeySequence("Ctrl+Left"), self)
        prev_iso_shortcut.activated.connect(self.prev_isotope)

        next_iso_shortcut = QShortcut(QKeySequence("Ctrl+Right"), self)
        next_iso_shortcut.activated.connect(self.next_isotope)

        left_arrow_shortcut = QShortcut(QKeySequence("Left"), self)
        left_arrow_shortcut.activated.connect(self.prev_isotope)

        right_arrow_shortcut = QShortcut(QKeySequence("Right"), self)
        right_arrow_shortcut.activated.connect(self.next_isotope)
    
    def next_tab(self):
        """Switch to the next tab in the tab widget."""
        current = self.tab_widget.currentIndex()
        self.tab_widget.setCurrentIndex((current + 1) % self.tab_widget.count())
        
    def prev_tab(self):
        """Switch to the previous tab in the tab widget."""
        current = self.tab_widget.currentIndex()
        self.tab_widget.setCurrentIndex((current - 1) % self.tab_widget.count())

    def update_sensitivity_table(self):
        """
        Update the sensitivity table with all selected elements.
        
        Populates table rows for each selected isotope with override checkbox,
        manual slope spinbox, and density information from periodic table.
        """
        self.sensitivity_table.setRowCount(0)
        
        if not self.selected_isotopes:
            return
            
        isotope_items = []
        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                element_key = f"{element}-{isotope:.4f}"
                label = self.get_isotope_label(element, isotope)
                isotope_items.append((label, element_key, isotope, element))
        
        isotope_items.sort(key=lambda x: x[2])
        
        for label, element_key, isotope, element in isotope_items:
            row = self.sensitivity_table.rowCount()
            self.sensitivity_table.insertRow(row)
            
            element_item = QTableWidgetItem(label)
            element_item.setFlags(element_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.sensitivity_table.setItem(row, 0, element_item)
            
            override_checkbox = QCheckBox()
            override_enabled = element_key in self.sensitivity_overrides
            override_checkbox.setChecked(override_enabled)
            override_checkbox.stateChanged.connect(lambda state, ek=element_key: self.on_override_changed(ek, state))
            self.sensitivity_table.setCellWidget(row, 1, override_checkbox)
            
            slope_spinbox = QDoubleSpinBox()
            slope_spinbox.setRange(0.0, 1e15)
            slope_spinbox.setDecimals(6)
            
            if element_key in self.sensitivity_overrides:
                slope_spinbox.setValue(self.sensitivity_overrides[element_key]['slope'])
            else:
                slope_spinbox.setValue(10.0)
            
            slope_spinbox.setSuffix(" cps/ppb")
            slope_spinbox.setEnabled(override_enabled)
            slope_spinbox.valueChanged.connect(lambda value, ek=element_key: self.on_slope_changed(ek, value))
            self.sensitivity_table.setCellWidget(row, 2, slope_spinbox)
            
            density_value = "N/A"
            if self.periodic_table:
                element_data = next((e for e in self.periodic_table.get_elements() if e['symbol'] == element), None)
                if element_data:
                    density_value = f"{element_data['density']:.4f}" if isinstance(element_data['density'], (int, float)) else str(element_data['density'])
            
            density_item = QTableWidgetItem(density_value)
            density_item.setFlags(density_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.sensitivity_table.setItem(row, 3, density_item)

    def on_override_changed(self, element_key, state):
        """
        Handle override checkbox state changes.
        
        Args:
            element_key: Element identifier string (format: "Element-mass.xxxx")
            state: Qt.Checked or Qt.Unchecked state
        """
        if state == Qt.Checked:
            if element_key not in self.sensitivity_overrides:
                for row in range(self.sensitivity_table.rowCount()):
                    element_item = self.sensitivity_table.item(row, 0)
                    if element_item:
                        for element, isotopes in self.selected_isotopes.items():
                            for isotope in isotopes:
                                test_key = f"{element}-{isotope:.4f}"
                                if (test_key == element_key and 
                                    self.get_isotope_label(element, isotope) == element_item.text()):
                                    
                                    slope_spinbox = self.sensitivity_table.cellWidget(row, 2)
                                    if slope_spinbox:
                                        slope_value = slope_spinbox.value()
                                        
                                        element_data = next((e for e in self.periodic_table.get_elements() if e['symbol'] == element), None)
                                        density = element_data['density'] if element_data else 'N/A'
                                        
                                        self.sensitivity_overrides[element_key] = {
                                            'slope': slope_value,
                                            'intercept': 0.0,
                                            'r_squared': 1.0,
                                            'lod': 0.0,
                                            'loq': 0.0,
                                            'bec': 0.0,
                                            'density': density
                                        }
                                        break
                        break
            
            for row in range(self.sensitivity_table.rowCount()):
                element_item = self.sensitivity_table.item(row, 0)
                if element_item:
                    for element, isotopes in self.selected_isotopes.items():
                        for isotope in isotopes:
                            test_key = f"{element}-{isotope:.4f}"
                            if (test_key == element_key and 
                                self.get_isotope_label(element, isotope) == element_item.text()):
                                slope_spinbox = self.sensitivity_table.cellWidget(row, 2)
                                if slope_spinbox:
                                    slope_spinbox.setEnabled(True)
                                break
        else:
            if element_key in self.sensitivity_overrides:
                del self.sensitivity_overrides[element_key]
            
            for row in range(self.sensitivity_table.rowCount()):
                element_item = self.sensitivity_table.item(row, 0)
                if element_item:
                    for element, isotopes in self.selected_isotopes.items():
                        for isotope in isotopes:
                            test_key = f"{element}-{isotope:.4f}"
                            if (test_key == element_key and 
                                self.get_isotope_label(element, isotope) == element_item.text()):
                                slope_spinbox = self.sensitivity_table.cellWidget(row, 2)
                                if slope_spinbox:
                                    slope_spinbox.setEnabled(False)
                                break
        
        _state_str = 'enabled' if state == Qt.Checked else 'disabled'
        ual = _ual()
        if ual:
            ual.log_action('PARAMETER_CHANGE',
                           f'Manual override {_state_str}: {element_key}',
                           {'element': element_key, 'override': _state_str})
        self.update_calibration_with_overrides()
        self.data_modified = True

    def on_slope_changed(self, element_key, value):
        """
        Handle manual slope value changes.
        
        Args:
            element_key: Element identifier string
            value: New slope value in cps/ppb
        """
        if element_key in self.sensitivity_overrides:
            self.sensitivity_overrides[element_key]['slope'] = value
            
            self.update_calibration_with_overrides()
            self.data_modified = True

    def apply_global_slope_to_all(self):
        """Apply global slope value to all elements in the sensitivity table."""
        global_slope = self.global_manual_slope_input.value()
        
        for row in range(self.sensitivity_table.rowCount()):
            slope_spinbox = self.sensitivity_table.cellWidget(row, 2)
            if slope_spinbox:
                slope_spinbox.setValue(global_slope)
        
        self.statusBar.showMessage(f"Applied slope {global_slope:.2e} to all elements", 3000)

    def apply_global_slope_to_checked(self):
        """Apply global slope value only to elements with Override checkbox enabled."""
        global_slope = self.global_manual_slope_input.value()
        updated_count = 0
        
        for row in range(self.sensitivity_table.rowCount()):
            override_checkbox = self.sensitivity_table.cellWidget(row, 1)
            if override_checkbox and override_checkbox.isChecked():
                slope_spinbox = self.sensitivity_table.cellWidget(row, 2)
                if slope_spinbox:
                    slope_spinbox.setValue(global_slope)
                    updated_count += 1
        
        self.statusBar.showMessage(f"Applied slope {global_slope:.2e} to {updated_count} checked elements", 3000)

    def update_calibration_with_overrides(self):
        """
        Update calibration results with manual sensitivity overrides.
        
        Adds or updates manual method data in calibration results for elements
        with sensitivity overrides, and removes manual data for elements that
        no longer have overrides.
        """
        if not self.calibration_results:
            return
            
        for element_key, override_data in self.sensitivity_overrides.items():
            if element_key in self.calibration_results:
                self.calibration_results[element_key]['manual'] = override_data.copy()
                
                self.isotope_method_preferences[element_key] = 'Manual'
        
        for element_key in list(self.calibration_results.keys()):
            if (element_key not in self.sensitivity_overrides and 
                'manual' in self.calibration_results[element_key]):
                del self.calibration_results[element_key]['manual']
                
                if self.isotope_method_preferences.get(element_key) == 'Manual':
                    data = self.calibration_results[element_key]
                    r_squared_values = {
                        'zero': data.get('zero', {}).get('r_squared', 0),
                        'simple': data.get('simple', {}).get('r_squared', 0),
                        'weighted': data.get('weighted', {}).get('r_squared', 0)
                    }
                    best_method = max(r_squared_values, key=r_squared_values.get)
                    best_method_display = {
                        'zero': 'Force through zero',
                        'simple': 'Simple linear',
                        'weighted': 'Weighted'
                    }[best_method]
                    self.isotope_method_preferences[element_key] = best_method_display
        
        self.update_results_table()
        if self.element_isotope_combo.currentText():
            self.display_selected_calibration(self.element_isotope_combo.currentText())

    def extract_concentration_from_sample_name(self, sample_name):
        """
        Extract concentration value from sample name using flexible pattern matching.
        
        Args:
            sample_name: Sample name string to parse
            
        Returns:
            Concentration value as string in current unit, or "-1" if not found
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
            (r'(\d+(?:\.\d+)?)\s*μg\s*l[-/]1', 'ppb'),
            (r'(\d+(?:\.\d+)?)\s*ug\s*l[-/]1', 'ppb'),
            (r'(\d+(?:\.\d+)?)\s*ppm', 'ppm'),
            (r'(\d+(?:\.\d+)?)\s*mg/l', 'ppm'), 
            (r'(\d+(?:\.\d+)?)\s*mg\s*l[-/]1', 'ppm'),
            (r'(\d+(?:\.\d+)?)\s*ppt', 'ppt'),
            (r'(\d+(?:\.\d+)?)\s*ng/l', 'ppt'),  
            (r'(\d+(?:\.\d+)?)\s*ng\s*l[-/]1', 'ppt'),
            (r'(\d+(?:\.\d+)?)\s*$', self.unit_combo.currentText()),  
            (r'^(\d+(?:\.\d+)?)(?:\D|$)', self.unit_combo.currentText()),  
        ]
        
        for pattern, unit in concentration_patterns:
            matches = re.findall(pattern, sample_name_lower)
            if matches:
                try:
                    concentration_value = float(matches[0])
                    
                    current_unit = self.unit_combo.currentText()
                    if unit != current_unit:
                        if unit == 'ppm' and current_unit == 'ppb':
                            concentration_value *= 1000
                        elif unit == 'ppb' and current_unit == 'ppm':
                            concentration_value /= 1000
                        elif unit == 'ppt' and current_unit == 'ppb':
                            concentration_value /= 1000
                        elif unit == 'ppb' and current_unit == 'ppt':
                            concentration_value *= 1000
                        elif unit == 'ppm' and current_unit == 'ppt':
                            concentration_value *= 1000000
                        elif unit == 'ppt' and current_unit == 'ppm':
                            concentration_value /= 1000000
                    
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

    def apply_global_method(self):
        """
        Apply the selected global method to all isotopes.
        
        Handles auto-selection based on R² values, manual method application,
        or specific method application to all isotopes.
        """
        if not self.calibration_results:
            QMessageBox.information(self, "No Data", "No calibration results available. Please calculate calibration first.")
            return
        
        global_method = self.global_method_combo.currentText()
        
        if global_method == 'Auto (Best R²)':
            self.apply_auto_method_selection()
        elif global_method == 'Manual':
            self.apply_manual_to_all_isotopes()
        else:
            self.apply_method_to_all_isotopes(global_method)
        
        self.update_results_table()
        if self.element_isotope_combo.currentText():
            self.display_selected_calibration(self.element_isotope_combo.currentText())
        
        self.method_preference_changed.emit(self.isotope_method_preferences)
        
        ual = _ual()
        if ual:
            ual.log_action('ANALYSIS', f'Applied global method: {global_method}',
                           {'method': global_method,
                            'isotope_count': len(self.calibration_results)})
        self.statusBar.showMessage(f"Applied {global_method} to all isotopes", 3000)

    def apply_manual_to_all_isotopes(self):
        """
        Apply manual method to all isotopes by enabling overrides.
        
        Creates sensitivity overrides for all selected isotopes using global manual
        slope value and element densities from periodic table.
        """
        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                element_key = f"{element}-{isotope:.4f}"
                
                if element_key not in self.sensitivity_overrides:
                    element_data = next((e for e in self.periodic_table.get_elements() if e['symbol'] == element), None)
                    density = element_data['density'] if element_data else 'N/A'
                    
                    slope_value = self.global_manual_slope_input.value()
                    
                    self.sensitivity_overrides[element_key] = {
                        'slope': slope_value,
                        'intercept': 0.0,
                        'r_squared': 1.0,
                        'lod': 0.0,
                        'loq': 0.0,
                        'bec': 0.0,
                        'density': density
                    }
                
                self.isotope_method_preferences[element_key] = 'Manual'
        
        self.update_sensitivity_table()
        
        self.update_calibration_with_overrides()

    def apply_auto_method_selection(self):
        """
        Automatically select the best method for each isotope based on highest R².
        
        For isotopes with manual overrides, retains manual method. For others,
        selects the method with the highest R² value.
        """
        self.isotope_method_preferences.clear()
        
        method_map = {
            'zero': 'Force through zero',
            'simple': 'Simple linear', 
            'weighted': 'Weighted'
        }
        
        for isotope_key, data in self.calibration_results.items():
            if isotope_key in self.sensitivity_overrides:
                self.isotope_method_preferences[isotope_key] = 'Manual'
                continue
            
            r_squared_values = {
                'zero': data.get('zero', {}).get('r_squared', 0),
                'simple': data.get('simple', {}).get('r_squared', 0),
                'weighted': data.get('weighted', {}).get('r_squared', 0)
            }
            
            best_method_key = max(r_squared_values, key=r_squared_values.get)
            best_method_display = method_map[best_method_key]
            
            self.isotope_method_preferences[isotope_key] = best_method_display
            
            element, mass = isotope_key.split('-')
            isotope_label = self.get_isotope_label(element, float(mass))
            best_r2 = r_squared_values[best_method_key]
            print(f"Auto-selected {best_method_display} for {isotope_label} (R² = {best_r2:.4f})")

    def apply_method_to_all_isotopes(self, method_name):
        """
        Apply the specified method to all isotopes.
        
        Args:
            method_name: Method name to apply (e.g., 'Force through zero', 'Simple linear')
        """
        for isotope_key in self.calibration_results.keys():
            if isotope_key in self.sensitivity_overrides and method_name != 'Manual':
                continue
                
            self.isotope_method_preferences[isotope_key] = method_name
        
        print(f"Applied {method_name} to applicable isotopes")

    def auto_fill_concentrations(self):
        """
        Automatically fill concentration values based on sample names.
        
        Uses pattern matching to extract concentration values from sample names
        and fills empty or -1 cells in the concentration table.
        """
        self.ignore_item_changed = True
        filled_count = 0
        
        try:
            for row in range(self.table.rowCount()):
                file_item = self.table.item(row, 0)
                if file_item:
                    sample_name = file_item.text()
                    concentration = self.extract_concentration_from_sample_name(sample_name)
                    
                    if concentration != "-1":
                        for col in range(1, self.table.columnCount()):
                            current_item = self.table.item(row, col)
                            if not current_item or current_item.text() in ["-1", ""]:
                                self.table.setItem(row, col, QTableWidgetItem(concentration))
                                filled_count += 1
        finally:
            self.ignore_item_changed = False
            if filled_count > 0:
                self.data_modified = True
                self.save_action.setEnabled(True)
        
        ual = _ual()
        if ual:
            ual.log_action('DATA_OP',
                           f'Auto-fill concentrations: {filled_count} cells filled',
                           {'filled': filled_count})
        if filled_count > 0:
            self.statusBar.showMessage(f"Auto-filled {filled_count} concentration values", 5000)
        else:
            self.statusBar.showMessage("No concentration patterns detected in sample names", 3000)
        
    def filter_results_table(self):
        """
        Filter the results table based on the selected option.
        
        Shows either all calibration results or only the best method for each isotope.
        """
        if self.filter_combo.currentText() == "All Results":
            self.update_results_table()
        else:
            self.update_results_table_best_methods()
            
    def update_results_table_best_methods(self):
        """
        Update the results table showing only the best method for each isotope.
        
        Displays one row per isotope with the preferred calibration method,
        color-coded to indicate whether it was auto-selected or manually chosen.
        """
        self.results_table.setRowCount(0)
        
        if not self.calibration_results:
            return
            
        unit = self.unit_combo.currentText()
        
        best_methods = {}
        auto_selected_isotopes = set()
        
        for isotope_key, data in self.calibration_results.items():
            if isotope_key in self.isotope_method_preferences:
                method_display = self.isotope_method_preferences[isotope_key]
                method_map = {
                    'Force through zero': 'zero',
                    'Simple linear': 'simple',
                    'Weighted': 'weighted',
                    'Manual': 'manual'
                }
                best_methods[isotope_key] = method_map.get(method_display, 'zero')
                
                if method_display != 'Manual':
                    r_squared_values = {
                        'zero': data.get('zero', {}).get('r_squared', 0),
                        'simple': data.get('simple', {}).get('r_squared', 0),
                        'weighted': data.get('weighted', {}).get('r_squared', 0)
                    }
                    auto_best = max(r_squared_values, key=r_squared_values.get)
                    auto_best_display = {
                        'zero': 'Force through zero',
                        'simple': 'Simple linear',
                        'weighted': 'Weighted'
                    }[auto_best]
                    
                    if method_display == auto_best_display:
                        auto_selected_isotopes.add(isotope_key)
                        
            else:
                r_squared_values = {
                    'zero': data.get('zero', {}).get('r_squared', 0),
                    'simple': data.get('simple', {}).get('r_squared', 0),
                    'weighted': data.get('weighted', {}).get('r_squared', 0)
                }
                best_methods[isotope_key] = max(r_squared_values, key=r_squared_values.get)
                auto_selected_isotopes.add(isotope_key)

        row = 0
        for isotope_key, best_method in best_methods.items():
            data = self.calibration_results[isotope_key]
            method_data = data.get(best_method, {})
            
            if not method_data:
                continue
            
            method_display = {
                'zero': 'Force through zero',
                'simple': 'Simple linear',
                'weighted': 'Weighted',
                'manual': 'Manual'
            }.get(best_method, best_method)
            
            self.results_table.insertRow(row)
            element, mass = isotope_key.split('-')
            isotope_label = self.get_isotope_label(element, float(mass))
            
            isotope_item = QTableWidgetItem(isotope_label)
            method_item = QTableWidgetItem(method_display)
            slope_item = QTableWidgetItem(f"{method_data.get('slope', 0):.2e} cps/{unit}")
            intercept_item = QTableWidgetItem(f"{method_data.get('intercept', 0):.2e} cps")
            bec_item = QTableWidgetItem(f"{method_data.get('bec', 0):.2e} {unit}")
            r_squared_item = QTableWidgetItem(f"{method_data.get('r_squared', 0):.4f}")
            density_item = QTableWidgetItem(
                f"{data.get('density', 'N/A'):.4f}" if isinstance(data.get('density'), (int, float)) else str(data.get('density', 'N/A'))
            )
            lod_item = QTableWidgetItem(f"{method_data.get('lod', 0):.2e} {unit}")
            loq_item = QTableWidgetItem(f"{method_data.get('loq', 0):.2e} {unit}")
            
            self.results_table.setItem(row, 0, isotope_item)
            self.results_table.setItem(row, 1, method_item)
            self.results_table.setItem(row, 2, slope_item)
            self.results_table.setItem(row, 3, intercept_item)
            self.results_table.setItem(row, 4, bec_item)
            self.results_table.setItem(row, 5, r_squared_item)
            self.results_table.setItem(row, 6, density_item)
            self.results_table.setItem(row, 7, lod_item)
            self.results_table.setItem(row, 8, loq_item)
            
            status = getattr(self, "_status_colors", None) or _build_ionic_status_colors(theme.palette)

            if best_method == 'manual':
                background_color = status["manual"]
                tooltip_text = f"Manual override (slope = {method_data.get('slope', 0):.2e})"
            elif isotope_key in auto_selected_isotopes:
                background_color = status["auto"]
                tooltip_text = f"Auto-selected based on highest R² ({method_data.get('r_squared', 0):.4f})"
            else:
                background_color = status["selected"]
                tooltip_text = f"Manually selected (R² = {method_data.get('r_squared', 0):.4f})"
            
            method_item.setBackground(QBrush(background_color))
            method_item.setForeground(QBrush(status["text"]))
            method_item.setToolTip(tooltip_text)
            
            base_color = status["base"]
            for col in range(9):
                item = self.results_table.item(row, col)
                if item and col != 1:
                    item.setBackground(QBrush(base_color))
                    item.setForeground(QBrush(status["text"]))
                    
            row += 1
        
        self.show_method_summary()

    def show_method_summary(self):
        """
        Show a summary of method preferences in the status bar.
        
        Displays counts of each method used and breakdown of auto-selected
        versus manually-selected methods.
        """
        if not self.isotope_method_preferences:
            return
            
        method_counts = {}
        auto_count = 0
        manual_count = 0
        
        for isotope_key, method in self.isotope_method_preferences.items():
            method_counts[method] = method_counts.get(method, 0) + 1
            
            if method == 'Manual':
                manual_count += 1
            elif isotope_key in self.calibration_results:
                data = self.calibration_results[isotope_key]
                r_squared_values = {
                    'zero': data.get('zero', {}).get('r_squared', 0),
                    'simple': data.get('simple', {}).get('r_squared', 0),
                    'weighted': data.get('weighted', {}).get('r_squared', 0)
                }
                best_method = max(r_squared_values, key=r_squared_values.get)
                best_method_display = {
                    'zero': 'Force through zero',
                    'simple': 'Simple linear',
                    'weighted': 'Weighted'
                }[best_method]
                
                if method == best_method_display:
                    auto_count += 1
                else:
                    manual_count += 1
        
        method_summary = ", ".join([f"{method}: {count}" for method, count in method_counts.items()])
        selection_summary = f"Auto: {auto_count}, Manual: {manual_count}"
        
        full_summary = f"Methods - {method_summary} | Selection - {selection_summary}"
        self.statusBar.showMessage(full_summary, 8000)
                
    def export_results(self):
        """
        Export calibration results to a CSV file.
        
        Saves all calibration results for all methods and isotopes to a CSV file
        with slope, intercept, R-squared, LOD, LOQ, and other metrics.
        """
        if not self.calibration_results:
            QMessageBox.warning(self, "No Data", "No calibration results to export.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Calibration Results", 
            "", 
            "CSV Files (*.csv)"
        )
        
        if not file_path:
            return
            
        if not file_path.endswith('.csv'):
            file_path += '.csv'
            
        try:
            with open(file_path, 'w') as f:
                unit = self.unit_combo.currentText()
                headers = [
                    "Isotope", "Method", f"Slope (cps/{unit})", "Intercept (cps)", 
                    f"BEC ({unit})", "R-squared", "Density (g/cm³)", 
                    f"LOD ({unit})", f"LOQ ({unit})"
                ]
                f.write(','.join(headers) + '\n')
                
                method_display = {
                    'zero': 'Force through zero',
                    'simple': 'Simple linear',
                    'weighted': 'Weighted',
                    'manual': 'Manual'
                }
                
                for isotope_key, data in self.calibration_results.items():
                    element, mass = isotope_key.split('-')
                    isotope_label = self.get_isotope_label(element, float(mass))
                    
                    for method_key, method_name in method_display.items():
                        if method_key in data:
                            method_data = data[method_key]
                            row = [
                                isotope_label,
                                method_name,
                                f"{method_data.get('slope', 0):.6e}",
                                f"{method_data.get('intercept', 0):.6e}",
                                f"{method_data.get('bec', 0):.6e}",
                                f"{method_data.get('r_squared', 0):.6f}",
                                f"{data.get('density', 'N/A')}" if isinstance(data.get('density'), (int, float)) else str(data.get('density', 'N/A')),
                                f"{method_data.get('lod', 0):.6e}",
                                f"{method_data.get('loq', 0):.6e}"
                            ]
                            f.write(','.join(row) + '\n')
                        
            ual = _ual()
            if ual:
                ual.log_file_operation('EXPORT', file_path,
                                       {'isotopes': list(self.calibration_results.keys()),
                                        'unit': self.unit_combo.currentText()})
            QMessageBox.information(self, "Success", f"Results exported to {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export results: {str(e)}")

    def export_sensitivity_results(self):
        """
        Export sensitivity settings to CSV.
        
        Saves manual sensitivity override settings including override status,
        manual slopes, and density values for all elements.
        """
        if not self.sensitivity_overrides and self.sensitivity_table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "No sensitivity settings to export.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Sensitivity Settings", 
            "", 
            "CSV Files (*.csv)"
        )
        
        if not file_path:
            return
            
        if not file_path.endswith('.csv'):
            file_path += '.csv'
            
        try:
            with open(file_path, 'w') as f:
                unit = self.unit_combo.currentText()
                headers = [
                    "Isotope", "Override Enabled", f"Manual Slope (cps/{unit})", "Density (g/cm³)"
                ]
                f.write(','.join(headers) + '\n')
                
                for row in range(self.sensitivity_table.rowCount()):
                    element_item = self.sensitivity_table.item(row, 0)
                    override_checkbox = self.sensitivity_table.cellWidget(row, 1)
                    slope_spinbox = self.sensitivity_table.cellWidget(row, 2)
                    density_item = self.sensitivity_table.item(row, 3)
                    
                    if element_item:
                        row_data = [
                            element_item.text(),
                            "Yes" if override_checkbox and override_checkbox.isChecked() else "No",
                            f"{slope_spinbox.value():.6e}" if slope_spinbox else "0",
                            density_item.text() if density_item else "N/A"
                        ]
                        f.write(','.join(row_data) + '\n')
                        
            QMessageBox.information(self, "Success", f"Sensitivity settings exported to {file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export sensitivity settings: {str(e)}")
        
    # ------------------------------------------------------------------ #
    # Time-domain exclusion helpers for count_vs_time_widget
    # ------------------------------------------------------------------ #

    def _current_time_plot_context(self):
        """Return (folder, isotope_key) describing what is currently shown
        in count_vs_time_widget.  Returns (None, None) when the context
        cannot be determined."""
        if (self.last_selected_row is not None
                and self.last_selected_col is not None):
            try:
                folder = self.folder_paths[self.last_selected_row]
                header_item = self.table.horizontalHeaderItem(
                    self.last_selected_col)
                isotope_key = (header_item.data(Qt.ItemDataRole.UserRole)
                               if header_item else None)
                if folder and isotope_key:
                    return folder, isotope_key
            except (IndexError, AttributeError):
                pass
        s_idx = self.sample_combo.currentIndex()
        i_idx = self.plot_isotope_combo.currentIndex()
        if s_idx >= 0 and i_idx >= 0 and s_idx < len(self.folder_paths):
            folder = self.folder_paths[s_idx]
            isotope_key = self.plot_isotope_combo.itemData(i_idx)
            if folder and isotope_key:
                return folder, isotope_key
        return None, None

    def _on_time_exclusion_changed(self):
        """Persist the current widget regions into the keyed storage dicts
        whenever regions are added, moved, or removed."""
        folder, isotope_key = self._current_time_plot_context()
        if not folder or not isotope_key:
            return
        regions = self.count_vs_time_widget.get_exclusion_regions()
        elem_regions   = [(lo, hi) for lo, hi, sc in regions
                          if sc == 'element']
        sample_regions = [(lo, hi) for lo, hi, sc in regions
                          if sc == 'sample']

        key = (folder, isotope_key)
        if elem_regions:
            self._time_exclusions_element[key] = elem_regions
        else:
            self._time_exclusions_element.pop(key, None)

        if sample_regions:
            self._time_exclusions_sample[folder] = sample_regions
        else:
            self._time_exclusions_sample.pop(folder, None)

    def _restore_time_exclusions(self, folder, isotope_key):
        """Load the stored regions for (folder, isotope_key) into the
        count_vs_time_widget, replacing whatever was there before.
        Args:
            folder (Any): The folder.
            isotope_key (Any): The isotope key.
        """
        key = (folder, isotope_key)
        elem_regions   = self._time_exclusions_element.get(key, [])
        sample_regions = self._time_exclusions_sample.get(folder, [])
        combined = ([(lo, hi, 'element') for lo, hi in elem_regions] +
                    [(lo, hi, 'sample')  for lo, hi in sample_regions])
        self.count_vs_time_widget.set_exclusion_regions(combined)

    def update_time_plot(self):
        """
        Update the time plot based on selected sample and isotope.
        
        Uses last selected table cell if available, otherwise falls back to
        combo box selections. Supports both raw counts and normalized CPS display.
        """
        if hasattr(self, 'last_selected_row') and self.last_selected_row is not None and self.last_selected_col is not None:
            self.plot_count_vs_time(self.last_selected_row, self.last_selected_col)
            return
            
        sample_idx = self.sample_combo.currentIndex()
        isotope_idx = self.plot_isotope_combo.currentIndex()
        
        if sample_idx < 0 or isotope_idx < 0:
            return
            
        try:
            folder = self.folder_paths[sample_idx]
            data = self.data[folder]
            sample_name = data['run_info'].get("SampleName", Path(folder).name)
            
            isotope_key = self.plot_isotope_combo.itemData(isotope_idx)
            if not isotope_key:
                return
                
            element, mass = isotope_key.split('-')
            mass_float = float(mass)
            
            mass_index = np.argmin(np.abs(data['masses'] - mass_float))
            
            run_info = data['run_info']
            seg = run_info["SegmentInfo"][0]
            acqtime = seg["AcquisitionPeriodNs"] * 1e-9
            accumulations = run_info["NumAccumulations1"] * run_info["NumAccumulations2"]
            dwell_time = acqtime * accumulations
            
            signals = data['signals']
            time_array = np.arange(len(signals)) * dwell_time
            
            counts = signals[:, mass_index]
            
            font = QFont('Arial',50)
            
            isotope_label = self.get_isotope_label(element, mass_float)
            if self.normalize_check.currentText() == "Normalized (CPS)":
                y_data = counts / dwell_time
                y_label = "Count Rate [cps]"
            else:
                y_data = counts
                y_label = "Counts"
            
            self.count_vs_time_widget.clear_plot()
            self.count_vs_time_widget.update_plot(time_array, {isotope_label: y_data})
            self.count_vs_time_widget.setLabel('bottom', "Time [s]", color=theme.palette.plot_fg, font=font)
            self.count_vs_time_widget.setLabel('left', y_label, color=theme.palette.plot_fg, font=font)
            self.count_vs_time_widget.setTitle(f"{isotope_label} - {sample_name}")
            self._restore_time_exclusions(folder, isotope_key)
            
        except Exception as e:
            print(f"Error updating time plot: {str(e)}")
            self.statusBar.showMessage(f"Error updating plot: {str(e)}", 3000)

    def show_periodic_table(self):
        """
        Show the periodic table dialog for element selection.
        
        Creates a new dialog instance with periodic table widget, connects signals,
        and restores previous selections if they exist.
        """
        ual = _ual()
        if ual:
            ual.log_action('DIALOG_OPEN', 'Ionic Calibration — Select Elements',
                           {'current_isotopes': sum(len(v) for v in self.selected_isotopes.values())})
        self._periodic_table_dialog = QDialog(self)
        self._periodic_table_dialog.setWindowTitle("Select Elements")
        self._periodic_table_dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self._periodic_table_dialog)
        
        self.periodic_table = PeriodicTableWidget()
        
        self.periodic_table.element_clicked.connect(self.element_selected)
        self.periodic_table.selection_confirmed.connect(self._handle_selection_confirmed)
        self.periodic_table.isotope_selected.connect(self.on_isotope_selected)
        
        if self.all_masses is not None and len(self.all_masses) > 0:
            self.periodic_table.update_available_masses(self.all_masses)
            
        if self.selected_isotopes:
            for element, isotopes in self.selected_isotopes.items():
                if element in self.periodic_table.buttons:
                    button = self.periodic_table.buttons[element]
                    if button.isotope_display:
                        for isotope in isotopes:
                            identifier = (element, isotope)
                            button.isotope_display.selected_isotopes.add(identifier)
                            if isotope in button.isotope_display.mass_labels:
                                button.isotope_display.mass_labels[isotope].setSelected(True)
                                element_data = next((e for e in self.periodic_table.get_elements() 
                                                if e['symbol'] == element), None)
                                if element_data:
                                    isotope_data = next((iso for iso in element_data['isotopes'] 
                                                    if isinstance(iso, dict) and 
                                                    abs(iso['mass'] - isotope) < 0.001), None)
                                    if isotope_data:
                                        button.set_highlight(isotope_data['abundance'], True)
        
        layout.addWidget(self.periodic_table)
        self._periodic_table_dialog.show()
        
    def _handle_selection_confirmed(self, selected_data):
        """
        Handle selection confirmation and close dialog.
        
        Args:
            selected_data: Dictionary of selected elements and their isotopes
        """
        self.on_selection_confirmed(selected_data)
        if hasattr(self, '_periodic_table_dialog') and self._periodic_table_dialog:
            self._periodic_table_dialog.accept() 
        
    def on_selection_confirmed(self, selected_data):
        """
        Handle confirmed selections from the periodic table.
        
        Args:
            selected_data: Dictionary mapping element symbols to lists of isotope masses
        """
        ual = _ual()
        if ual:
            ual.log_action('SAMPLE_SELECT', 'Ionic Calibration — isotopes confirmed',
                           {'elements': list(selected_data.keys()),
                            'total_isotopes': sum(len(v) for v in selected_data.values())})
        self.selected_isotopes = selected_data
        self.update_table_columns()
        self.update_element_isotope_combo()
        self.update_sensitivity_table()
        self.update_plot_isotope_combo()
        
        self.isotopes_selection_changed.emit(self.selected_isotopes)
        
        if self.data:
            self.plot_count_vs_time()
                
    def on_isotope_selected(self, element, mass, abundance):
        """
        Handle individual isotope selections.
        
        Args:
            element: Element symbol
            mass: Isotope mass value
            abundance: Natural abundance percentage
        """
        if element not in self.selected_isotopes:
            self.selected_isotopes[element] = []
            
        if mass not in self.selected_isotopes[element]:
            self.selected_isotopes[element].append(mass)
        
        self.update_table_columns()
        self.update_element_isotope_combo()
        self.update_sensitivity_table()
        self.update_plot_isotope_combo()
        
        self.isotopes_selection_changed.emit(self.selected_isotopes)
        
        if self.data:
            self.plot_count_vs_time()
                
    def update_plot_isotope_combo(self):
        """
        Update the isotope combo box for the time plot.
        
        Populates combo box with all selected isotopes sorted by mass,
        and triggers plot update if items are available.
        """
        self.plot_isotope_combo.clear()
        
        combo_items = []
        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                label = self.get_isotope_label(element, isotope)
                internal_key = f"{element}-{isotope:.4f}"
                combo_items.append((label, internal_key, isotope))
        
        combo_items.sort(key=lambda x: x[2])
        
        for label, internal_key, _ in combo_items:
            self.plot_isotope_combo.addItem(label, internal_key)
            
        if self.plot_isotope_combo.count() > 0:
            self.update_time_plot()

    def save_session(self):
        """
        Save session using the CSV handler.
        
        Saves all session data including selected isotopes, calibration results,
        sensitivity overrides, table data, and method preferences to a CSV file.
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Session", 
            "", 
            "CSV Files (*.csv)"
        )
        if not file_path:
            return
            
        if not file_path.endswith('.csv'):
            file_path += '.csv'
            
        try:
            session_data = {
                "selected_isotopes": self.selected_isotopes,
                "concentration_unit": self.unit_combo.currentText(),
                "calibration_results": self.calibration_results,
                "sensitivity_overrides": self.sensitivity_overrides,
                "table_data": self.get_table_data(),
                "isotope_method_preferences": self.isotope_method_preferences
            }
            
            progress = QProgressDialog("Saving session...", None, 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(500)
            progress.setValue(10)
            QApplication.processEvents()
            
            from save_export.ionic_session import save_session_to_csv
            save_session_to_csv(file_path, session_data, self)
            
            progress.setValue(100)
            
            ual = _ual()
            if ual:
                ual.log_file_operation('SAVE', file_path,
                                       {'isotopes': list(self.selected_isotopes.keys()),
                                        'results_count': len(self.calibration_results)})
            self.statusBar.showMessage(f"Session saved to {file_path}", 3000)
            self.data_modified = False
            self.save_action.setEnabled(False)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save session: {str(e)}")

    def load_session(self):
        """
        Load session from CSV format.
        
        Restores all session data including isotope selections, calibration results,
        sensitivity overrides, and updates all UI components accordingly.
        """
        if not self.prompt_save_changes():
            return
                
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Load Session", 
            "", 
            "CSV Files (*.csv)"
        )
        if not file_path:
            return
                
        try:
            progress = QProgressDialog("Loading session...", None, 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(500)
            progress.setValue(10)
            QApplication.processEvents()
            
            from save_export.ionic_session import load_session_from_csv, load_summary_stats_from_csv
            session_data = load_session_from_csv(file_path)
            progress.setValue(50)
            QApplication.processEvents()
        
            self.selected_isotopes = session_data["selected_isotopes"]
            self.unit_combo.setCurrentText(session_data["concentration_unit"])
            self.calibration_results = session_data["calibration_results"]
            self.sensitivity_overrides = session_data.get("sensitivity_overrides", {})
            self.isotope_method_preferences = session_data.get("isotope_method_preferences", {})

            self.excluded_points = {}
            for k, rec in (self.calibration_results or {}).items():
                if isinstance(rec, dict):
                    excluded = rec.get('excluded_folders', [])
                    if excluded:
                        self.excluded_points[k] = set(excluded)
        
            self.set_table_data(session_data["table_data"])
            
            summary_stats = load_summary_stats_from_csv(file_path)
            if summary_stats:
                print(f"Loaded summary statistics for {len(summary_stats)} samples")
                self.summary_stats_5sec = summary_stats
            
            self.update_element_isotope_combo()
            self.update_sensitivity_table()  
            self.update_plot_isotope_combo()
            self.update_sample_combo()
            
            if self.calibration_results:
                self.update_results_table()
                if self.element_isotope_combo.count() > 0:
                    self.display_selected_calibration(self.element_isotope_combo.currentText())
                    
                self.calibration_completed.emit("Ionic Calibration", {
                    "results": self.calibration_results,
                    "method_preferences": self.isotope_method_preferences
                })
                
            progress.setValue(100)
            ual = _ual()
            if ual:
                ual.log_file_operation('OPEN', file_path,
                                       {'isotopes': list(self.selected_isotopes.keys()),
                                        'results_count': len(self.calibration_results)})
            self.statusBar.showMessage(f"Session loaded from {file_path}", 3000)
            self.data_modified = False
            self.save_action.setEnabled(False)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load session: {str(e)}")
                
    def _go_prev_isotope(self):
        """Navigate to the previous isotope in the combo box."""
        idx = self.element_isotope_combo.currentIndex()
        if idx > 0:
            self.element_isotope_combo.setCurrentIndex(idx - 1)

    def _go_next_isotope(self):
        """Navigate to the next isotope in the combo box."""
        idx = self.element_isotope_combo.currentIndex()
        if idx < self.element_isotope_combo.count() - 1:
            self.element_isotope_combo.setCurrentIndex(idx + 1)

    def update_element_isotope_combo(self):
        """
        Update element-isotope combo with sorted isotopes.
        
        Populates combo box with all selected isotopes sorted by mass,
        storing internal keys as item data for later retrieval.
        """
        self.element_isotope_combo.clear()
        
        combo_items = []
        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                label = self.get_isotope_label(element, isotope)
                internal_key = f"{element}-{isotope:.4f}"
                combo_items.append((label, internal_key, isotope))
        
        combo_items.sort(key=lambda x: x[2])
        
        for label, internal_key, _ in combo_items:
            self.element_isotope_combo.addItem(label, internal_key)

    def update_ui_from_compressed_data(self):
        """
        Update UI elements after loading compressed data.
        
        Refreshes folder paths, table rows, periodic table, sample combo,
        and table columns based on loaded compressed data.
        """
        self.folder_paths = list(self.data.keys())
        self.update_table_rows()
        self.update_periodic_table()
        self.update_sample_combo()
        
        self.update_table_columns()
        
    def update_sample_combo(self):
        """
        Update the sample combo box with folder names.
        
        Populates combo box with sample names from run.info files,
        falling back to folder names if run.info is not available.
        """
        self.sample_combo.clear()
        
        for folder in self.folder_paths:
            try:
                run_info_path = Path(folder) / "run.info"
                if os.path.exists(run_info_path):
                    with open(run_info_path, "r") as fp:
                        run_info = json.load(fp)
                    sample_name = run_info.get("SampleName", Path(folder).name)
                else:
                    sample_name = Path(folder).name
                    
                self.sample_combo.addItem(sample_name, folder)
                
            except Exception:
                self.sample_combo.addItem(Path(folder).name, folder)

    def table_key_press_event(self, event):
        """
        Handle key press events for copy/paste operations.
        
        Args:
            event: Key press event object
        """
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_C:
                self.copy_cells()
            elif event.key() == Qt.Key.Key_V:
                self.paste_cells()
            else:
                super(QTableWidget, self.table).keyPressEvent(event)
        else:
            super(QTableWidget, self.table).keyPressEvent(event)

    def show_context_menu(self, position):
        """
        Show context menu for cell operations.
        
        Args:
            position: Position where context menu was requested
        """
        menu = QMenu()
        
        copy_action = menu.addAction("Copy")
        copy_action.setShortcut("Ctrl+C")
        
        paste_action = menu.addAction("Paste")
        paste_action.setShortcut("Ctrl+V")
        
        menu.addSeparator()
        
        set_minus_one_action = menu.addAction("Set to -1 (Exclude from Calibration)")
        set_zero_action = menu.addAction("Set to 0 (Blank)")
        
        menu.addSeparator()
        concentrations_menu = menu.addMenu("Set Concentration")
        
        common_concentrations = [0.1, 0.5, 1, 2, 5, 10, 20, 50, 100]
        conc_actions = {}
        
        for conc in common_concentrations:
            action = concentrations_menu.addAction(f"{conc} {self.unit_combo.currentText()}")
            conc_actions[action] = conc
        
        action = menu.exec(self.table.viewport().mapToGlobal(position))
        
        if action == copy_action:
            self.copy_cells()
        elif action == paste_action:
            self.paste_cells()
        elif action == set_minus_one_action:
            self.set_selected_cells_to_minus_one()
        elif action == set_zero_action:
            self.set_selected_cells_to_value(0)
        elif action in conc_actions:
            self.set_selected_cells_to_value(conc_actions[action])

    def set_selected_cells_to_value(self, value):
        """
        Set selected cells to a specific value.
        
        Args:
            value: Value to set in selected cells
        """
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            return
            
        self.ignore_item_changed = True
        try:
            for range_obj in selected_ranges:
                for row in range(range_obj.topRow(), range_obj.bottomRow() + 1):
                    for col in range(range_obj.leftColumn(), range_obj.rightColumn() + 1):
                        if col > 0:
                            self.table.setItem(row, col, QTableWidgetItem(f"{value}"))
        finally:
            self.ignore_item_changed = False
            self.data_modified = True
            self.save_action.setEnabled(True)
            self.statusBar.showMessage(f"Set selected cells to {value}", 2000)

    def set_selected_cells_to_minus_one(self):
        """Set all selected cells to -1."""
        self.set_selected_cells_to_value(-1)

    def copy_cells(self):
        """Copy selected cells to clipboard."""
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            return
            
        copied_data = []
        for range_obj in selected_ranges:
            for row in range(range_obj.topRow(), range_obj.bottomRow() + 1):
                row_data = []
                for col in range(range_obj.leftColumn(), range_obj.rightColumn() + 1):
                    item = self.table.item(row, col)
                    row_data.append(item.text() if item else "")
                copied_data.append('\t'.join(row_data))
        
        clipboard = QApplication.clipboard()
        clipboard.setText('\n'.join(copied_data))
        self.statusBar.showMessage("Copied to clipboard", 2000)

    def paste_cells(self):
        """Paste clipboard data into selected cells."""
        clipboard = QApplication.clipboard()
        data = clipboard.text()
        if not data:
            return
            
        rows = data.split('\n')
        if not rows:
            return
            
        current_row = self.table.currentRow()
        current_col = self.table.currentColumn()
        if current_row < 0 or current_col < 0:
            return
            
        self.ignore_item_changed = True
        try:
            for i, row_data in enumerate(rows):
                if row_data.strip():
                    cells = row_data.split('\t')
                    for j, cell_data in enumerate(cells):
                        row_idx = current_row + i
                        col_idx = current_col + j
                        
                        if (row_idx < self.table.rowCount() and 
                            col_idx < self.table.columnCount()):
                            
                            if col_idx > 0:
                                try:
                                    value = float(cell_data)
                                    self.table.setItem(row_idx, col_idx, 
                                                    QTableWidgetItem(str(value)))
                                except ValueError:
                                    continue
        finally:
            self.ignore_item_changed = False
            self.data_modified = True
            self.save_action.setEnabled(True)
            self.statusBar.showMessage("Paste complete", 2000)
    
    def on_data_changed(self, item):
        """
        Handle data changes in the table.
        
        Args:
            item: Table item that was changed
        """
        if not self.ignore_item_changed:
            self.data_modified = True
            self.save_action.setEnabled(True)
                
    def update_table_rows(self):
        """
        Update table rows with loaded folder data.
        
        Populates first column with sample names and initializes other
        columns with -1 values.
        """
        self.table.setRowCount(len(self.folder_paths))
        for i, folder in enumerate(self.folder_paths):
            try:
                run_info_path = Path(folder) / "run.info"
                with open(run_info_path, "r") as fp:
                    run_info = json.load(fp)
                sample_name = run_info.get("SampleName", Path(folder).name)
            except:
                sample_name = Path(folder).name
                
            item = QTableWidgetItem(sample_name)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, item)
            
            for j in range(1, self.table.columnCount()):
                self.table.setItem(i, j, QTableWidgetItem("-1"))

    def update_table_columns(self):
        """
        Update table columns with sorted isotope labels while preserving existing data.
        
        Saves existing concentration data, rebuilds columns in sorted order by mass,
        and restores data or applies smart auto-fill for new isotopes.
        """
        
        existing_data = {}
        for col in range(1, self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(col)
            if header_item:
                isotope_key = header_item.data(Qt.ItemDataRole.UserRole)
                if isotope_key:
                    existing_data[isotope_key] = {}
                    for row in range(self.table.rowCount()):
                        item = self.table.item(row, col)
                        if item:
                            existing_data[isotope_key][row] = item.text()
                            
        while self.table.columnCount() > 1:
            self.table.removeColumn(1)
        
        all_isotopes = []
        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                label = self.get_isotope_label(element, isotope)
                all_isotopes.append((element, isotope, label))
        
        all_isotopes.sort(key=lambda x: x[1])
        
        for element, isotope, label in all_isotopes:
            col = self.table.columnCount()
            self.table.insertColumn(col)
            unit = self.unit_combo.currentText()
            header = f"{label} [{unit}]"
            self.table.setHorizontalHeaderItem(col, QTableWidgetItem(header))
            header_item = self.table.horizontalHeaderItem(col)
            isotope_key = f"{element}-{isotope:.4f}"
            header_item.setData(Qt.ItemDataRole.UserRole, isotope_key)

            self.table.setItemDelegateForColumn(col, NumericDelegate(self.table))

            for row in range(self.table.rowCount()):
                if isotope_key in existing_data and row in existing_data[isotope_key]:
                    saved_value = existing_data[isotope_key][row]
                    self.table.setItem(row, col, QTableWidgetItem(saved_value))
                else:
                    file_item = self.table.item(row, 0)
                    if file_item:
                        sample_name = file_item.text()
                        concentration = self.extract_concentration_from_sample_name(sample_name)
                        self.table.setItem(row, col, QTableWidgetItem(concentration))
                    else:
                        self.table.setItem(row, col, QTableWidgetItem("-1"))

        self.table.horizontalHeader().setMinimumSectionSize(80)
        self.table.horizontalHeader().setDefaultSectionSize(80)
        
        self.table.setColumnWidth(0, 200)
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False)
                
    def update_periodic_table(self):
        """
        Update periodic table with available masses.
        
        Retrieves masses from parent window if not already set and updates
        periodic table widget with available mass ranges.
        """
        if self.all_masses is None and self.parent_window and hasattr(self.parent_window, 'all_masses'):
            self.all_masses = self.parent_window.all_masses
                
        if hasattr(self.periodic_table, 'update_available_masses'):
            masses_to_update = []
            if self.all_masses is not None:
                if isinstance(self.all_masses, np.ndarray) and self.all_masses.size > 0:
                    masses_to_update = self.all_masses
                elif isinstance(self.all_masses, list) and len(self.all_masses) > 0:
                    masses_to_update = self.all_masses
            self.periodic_table.update_available_masses(masses_to_update)
                
    def parse_header_for_element_isotope_and_unit(self, header):
        """
        Parse header text to extract element, mass, and unit information.
        
        Args:
            header: Header text string (e.g., "65Cu [ppb]")
            
        Returns:
            Tuple of (element symbol, mass, unit) or None if parsing fails
        """
        try:
            label_part = header.split('[')[0].strip()
            unit = header.split('[')[1].split(']')[0].strip()
            
            for element in self.periodic_table.get_elements():
                for isotope in element['isotopes']:
                    if isinstance(isotope, dict) and isotope.get('label') == label_part:
                        return element['symbol'], isotope['mass'], unit
                    
            parts = label_part.split('-')
            if len(parts) == 2:
                return parts[0], float(parts[1]), unit
                
        except Exception:
            pass
        return None

    def plot_count_vs_time(self, selected_row=None, selected_col=None):
        """
        Plot count vs time data with proper isotope labels.
        
        Args:
            selected_row: Row index in table, if None uses combo box selection
            selected_col: Column index in table, if None uses combo box selection
        """
        if not self.data or not self.selected_isotopes:
            return

        self.count_vs_time_widget.clear_plot()

        if selected_row is not None and selected_col is not None:
            try:
                folder = self.folder_paths[selected_row]
                data = self.data[folder]
                sample_name = data['run_info'].get("SampleName", Path(folder).name)

                run_info = data['run_info']
                
                seg = run_info["SegmentInfo"][0]
                acqtime = seg["AcquisitionPeriodNs"] * 1e-9
                accumulations = run_info["NumAccumulations1"] * run_info["NumAccumulations2"]
                dwell_time = acqtime * accumulations

                signals = data['signals']
                time_array = np.arange(len(signals)) * dwell_time
                
                element_mass_info = self.parse_header_for_element_isotope_and_unit(
                    self.table.horizontalHeaderItem(selected_col).text()
                )
                
                if element_mass_info:
                    element, mass, _ = element_mass_info
                    mass_index = np.argmin(np.abs(data['masses'] - float(mass)))
                    isotope_label = self.get_isotope_label(element, float(mass))
                    
                    counts = signals[:, mass_index]
                    
                    if self.normalize_check.currentText() == "Normalized (CPS)":
                        y_data = counts / dwell_time
                        y_label = "Count Rate [cps]"
                    else:
                        y_data = counts
                        y_label = "Counts"
                    
                    self.count_vs_time_widget.update_plot(time_array, {isotope_label: y_data})
                    self.count_vs_time_widget.setLabel('bottom', "Time [s]")
                    self.count_vs_time_widget.setLabel('left', y_label)
                    self.count_vs_time_widget.setTitle(f"{isotope_label} - {sample_name}")
                    isotope_key_ctx = f"{element}-{mass:.4f}"
                    self._restore_time_exclusions(folder, isotope_key_ctx)
                    
                    for i in range(self.sample_combo.count()):
                        if self.sample_combo.itemData(i) == folder:
                            self.sample_combo.blockSignals(True)
                            self.sample_combo.setCurrentIndex(i)
                            self.sample_combo.blockSignals(False)
                            break
                    
                    isotope_key = f"{element}-{mass:.4f}"
                    for i in range(self.plot_isotope_combo.count()):
                        if self.plot_isotope_combo.itemData(i) == isotope_key:
                            self.plot_isotope_combo.blockSignals(True)
                            self.plot_isotope_combo.setCurrentIndex(i)
                            self.plot_isotope_combo.blockSignals(False)
                            break
                else:
                    self.count_vs_time_widget.setTitle("Count vs Time - Invalid column selection")
            except Exception as e:
                print(f"Error plotting count vs time: {str(e)}")
                self.count_vs_time_widget.setTitle("Count vs Time - Error in plotting")
        else:
            self.count_vs_time_widget.setTitle("Count vs Time - No cell selected")

        
    def on_table_cell_clicked(self, row, col):
        """
        Handle table cell click events.
        
        Args:
            row: Row index that was clicked
            col: Column index that was clicked
        """
        if col > 0:
            self.last_selected_row = row
            self.last_selected_col = col
            self.plot_count_vs_time(row, col)
            
    def calculate_calibration(self):
        """
        Calculate calibration with proper isotope matching.
        
        Processes concentration data from table, performs calibration calculations
        for all methods (including manual), and updates results display.
        """
        if not self.selected_isotopes or not self.data:
            return

        ual = _ual()
        if ual:
            ual.log_action('ANALYSIS', 'Ionic calibration calculation started',
                           {'isotope_count': sum(len(v) for v in self.selected_isotopes.values()),
                            'sample_count': len(self.folder_paths),
                            'unit': self.unit_combo.currentText()})

        current_folders = set(self.folder_paths)
        pruned = {}
        for k, excl in self.excluded_points.items():
            kept = {f for f in excl if f in current_folders}
            if kept:
                pruned[k] = kept
        self.excluded_points = pruned

        progress = QProgressDialog("Calculating calibration...", None, 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(500)
        progress.setValue(0)
        QApplication.processEvents()

        concentrations = {}
        current_unit = self.unit_combo.currentText()
        
        column_to_isotope = {}
        for col in range(1, self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(col)
            isotope_key = header_item.data(Qt.ItemDataRole.UserRole)
            if isotope_key:
                column_to_isotope[col] = isotope_key
        
        progress.setValue(10)
        QApplication.processEvents()
        
        for i in range(self.table.rowCount()):
            folder = self.folder_paths[i]
            concentrations[folder] = {}
            
            for col, isotope_key in column_to_isotope.items():
                try:
                    item = self.table.item(i, col)
                    if item is None:
                        continue
                    
                    value = item.text()
                    
                    try:
                        displayed_conc = float(value)
                    except ValueError:
                        continue
                    
                    if displayed_conc != -1:
                        base_conc = self.convert_concentration(displayed_conc, current_unit, self.base_unit)
                        concentrations[folder][isotope_key] = base_conc
                        
                except Exception as e:
                    QMessageBox.warning(self, "Error", 
                        f"Invalid concentration for {folder}, {isotope_key}: {str(e)}")
                    progress.cancel()
                    return
        
        progress.setValue(30)
        QApplication.processEvents()

        # ── Single-point calibration check ────────────────────────────────────
        single_point_labels = []
        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                isotope_key = f"{element}-{isotope:.4f}"
                n_valid = sum(
                    1 for folder in self.folder_paths
                    if isotope_key in concentrations.get(folder, {})
                )
                if n_valid == 1:
                    single_point_labels.append(
                        self.get_isotope_label(element, isotope)
                    )

        if single_point_labels:
            progress.close()
            n = len(single_point_labels)
            noun = "isotope has" if n == 1 else "isotopes have"
            inline_list = ",&nbsp; ".join(single_point_labels)

            dlg = QMessageBox(self)
            dlg.setWindowTitle("Single-Point Calibration Detected")
            dlg.setIcon(QMessageBox.Icon.Information)
            dlg.setText(
                f"<b>{n} {noun} only 1 calibration point:</b><br>"
                f"<span style='font-family:monospace;'>{inline_list}</span>"
            )
            dlg.setInformativeText(
                "With a single standard, only <b>Force Through Zero</b> is "
                "mathematically possible (slope = signal ÷ concentration, "
                "intercept = 0). Simple linear and Weighted fits will mirror "
                "the Force Through Zero result for these isotopes.<br><br>"
                "You can go back and add another calibration standard, "
                "or continue with the single-point Force Through Zero calibration."
            )
            btn_add = dlg.addButton(
                "Add More Points", QMessageBox.ButtonRole.RejectRole
            )
            btn_ftz = dlg.addButton(
                "Continue with Force Through Zero",
                QMessageBox.ButtonRole.AcceptRole,
            )
            dlg.setDefaultButton(btn_add)
            dlg.exec()

            if dlg.clickedButton() is btn_add:
                return

            progress = QProgressDialog("Calculating calibration...", None, 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(30)
            QApplication.processEvents()

        try:
            self.calibration_results = self.perform_calibration(concentrations, progress)
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", 
                                 f"Failed to calculate calibration: {str(e)}")
            progress.cancel()
            return
        
        progress.setValue(90)
        QApplication.processEvents()
        
        self.update_calibration_with_overrides()
        
        current_method = self.calibration_method_combo.currentText()
        for isotope_key in self.calibration_results:
            if isotope_key not in self.isotope_method_preferences:
                if isotope_key in self.sensitivity_overrides:
                    self.isotope_method_preferences[isotope_key] = 'Manual'
                else:
                    self.isotope_method_preferences[isotope_key] = current_method
        
        self.update_results_table()
        
        if self.element_isotope_combo.currentText():
            self.display_selected_calibration(self.element_isotope_combo.currentText())
            
        for isotope_key, data in self.calibration_results.items():
            if isotope_key not in self.isotope_method_preferences:
                if isotope_key in self.sensitivity_overrides:
                    self.isotope_method_preferences[isotope_key] = 'Manual'
                else:
                    r_squared_values = {
                        'zero': data.get('zero', {}).get('r_squared', 0),
                        'simple': data.get('simple', {}).get('r_squared', 0),
                        'weighted': data.get('weighted', {}).get('r_squared', 0)
                    }
                    
                    best_method = max(r_squared_values, key=r_squared_values.get)
                    best_method_display = {
                        'zero': 'Force through zero',
                        'simple': 'Simple linear',
                        'weighted': 'Weighted'
                    }[best_method]
                    
                    self.isotope_method_preferences[isotope_key] = best_method_display
        
        self.data_modified = True
        self.save_action.setEnabled(True)
        
        self.calibration_completed.emit("Ionic Calibration", {
            "results": self.calibration_results,
            "method_preferences": self.isotope_method_preferences
        })

        ual = _ual()
        if ual:
            ual.log_action('ANALYSIS', 'Ionic calibration completed',
                           {'isotopes_computed': len(self.calibration_results),
                            'method': self.calibration_method_combo.currentText()})

        progress.setValue(100)
        self.statusBar.showMessage("Calibration complete", 3000)
        
        self.tab_widget.setCurrentIndex(2)

    def get_table_data(self):
        """
        Get table data with both display and internal formats.
        
        Returns:
            Dictionary containing table_data (list of rows) and header_internal_data
            (mapping of column indices to internal isotope keys)
        """
        table_data = []
        header_internal_data = {}
        
        headers = []
        for col in range(self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(col)
            if header_item:
                headers.append(header_item.text())
                internal_data = header_item.data(Qt.ItemDataRole.UserRole)
                if internal_data:
                    header_internal_data[col] = internal_data
        
        table_data.append(headers)
        
        for row in range(self.table.rowCount()):
            row_data = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                row_data.append(item.text() if item else "")
            table_data.append(row_data)
        
        return {
            'table_data': table_data,
            'header_internal_data': header_internal_data
        }

    def set_table_data(self, data):
        """
        Set table data restoring both formats.
        
        Args:
            data: Dictionary containing table_data and header_internal_data
        """
        if not data:
            return
            
        table_data = data.get('table_data', [])
        header_internal_data = data.get('header_internal_data', {})
        
        if not table_data:
            return
            
        rows = len(table_data)
        cols = len(table_data[0])
        
        self.table.setRowCount(rows - 1)
        self.table.setColumnCount(cols)
        
        for col in range(cols):
            header_text = table_data[0][col]
            header_item = QTableWidgetItem(header_text)
            
            if str(col) in header_internal_data:
                header_item.setData(Qt.ItemDataRole.UserRole, header_internal_data[str(col)])
                
            self.table.setHorizontalHeaderItem(col, header_item)
        
        for row in range(1, rows):
            for col in range(cols):
                item = QTableWidgetItem(str(table_data[row][col]))
                self.table.setItem(row - 1, col, item)
                
        self.table.resizeColumnsToContents()

    def display_selected_calibration(self, selection):
        """
        Handle selection changes in combo box.
        
        Args:
            selection: Selected isotope label text
        """
        if not selection or not self.calibration_results:
            return

        current_index = self.element_isotope_combo.currentIndex()
        if current_index >= 0:
            internal_key = self.element_isotope_combo.itemData(current_index)
            if internal_key and internal_key in self.calibration_results:
                if internal_key in self.isotope_method_preferences:
                    self.calibration_method_combo.blockSignals(True)
                    self.calibration_method_combo.setCurrentText(self.isotope_method_preferences[internal_key])
                    self.calibration_method_combo.blockSignals(False)
                
                element, mass = internal_key.split('-')
                self.display_calibration(element, float(mass))
            
    def update_calibration_display(self):
        """
        Update the calibration display when method is changed and save preference.
        
        Updates display to show selected method and saves the preference for
        the current isotope.
        """
        current_index = self.element_isotope_combo.currentIndex()
        if current_index >= 0:
            internal_key = self.element_isotope_combo.itemData(current_index)
            if internal_key:
                selected_method = self.calibration_method_combo.currentText()
                self.isotope_method_preferences[internal_key] = selected_method

                if (selected_method == 'Manual'
                        and internal_key not in self.sensitivity_overrides
                        and internal_key in self.calibration_results):
                    import numpy as np
                    data = self.calibration_results[internal_key]
                    seed_slope = float(
                        data.get('simple', {}).get('slope', 10.0))
                    if seed_slope <= 0:
                        seed_slope = 10.0

                    element_sym = internal_key.split('-')[0]
                    element_data = next(
                        (e for e in self.periodic_table.get_elements()
                         if e['symbol'] == element_sym),
                        None
                    )
                    density = (element_data['density']
                               if element_data
                               else data.get('density', 'N/A'))

                    x = np.asarray(data.get('x', []), dtype=float)
                    y_std = np.asarray(data.get('y_std', []), dtype=float)
                    y_fit_list = (seed_slope * x).tolist() if len(x) else []

                    if len(x) and len(y_std) == len(x):
                        excluded = self.excluded_points.get(
                            internal_key, set())
                        folders = data.get('folders', [])
                        included = [i for i, f in enumerate(folders)
                                    if f not in excluded]
                        if included:
                            inc_x = x[included]
                            inc_std = y_std[included]
                            sigma_blank = float(
                                inc_std[int(np.argmin(inc_x))])
                        else:
                            sigma_blank = float(
                                y_std[int(np.argmin(x))])
                    else:
                        sigma_blank = 0.0

                    fom = self._compute_figures_of_merit(
                        seed_slope, 0.0, sigma_blank)

                    manual_record = {
                        'slope':     seed_slope,
                        'intercept': 0.0,
                        'r_squared': 1.0,
                        'y_fit':     y_fit_list,
                        'density':   density,
                        **fom,
                    }
                    self.sensitivity_overrides[internal_key] = \
                        manual_record.copy()
                    self.calibration_results[internal_key]['manual'] = \
                        manual_record
                    self.update_sensitivity_table()

                self.method_preference_changed.emit(self.isotope_method_preferences)

                element, mass = internal_key.split('-')
                self.display_calibration(element, float(mass))

    def display_calibration(self, element, isotope):
        """
        Display calibration data with original isotope labels.
        
        Args:
            element: Element symbol
            isotope: Isotope mass value
        """
        if not self.calibration_results:
            return

        current_unit = self.unit_combo.currentText()
        isotope_key = f"{element}-{isotope:.4f}"
        data = self.calibration_results.get(isotope_key)

        if data:
            method_map = {
                'Force through zero': 'zero',
                'Simple linear': 'simple',
                'Weighted': 'weighted',
                'Manual': 'manual'
            }
            selected_method = method_map[self.calibration_method_combo.currentText()]
            
            method_data = data.get(selected_method, {})
            
            if not method_data:
                return

            x_values = [self.convert_concentration(x, self.base_unit, current_unit) for x in data.get('x', [])]
            
            isotope_label = self.get_isotope_label(element, isotope)

            folders_for_isotope = data.get('folders', [])
            excluded_folders = self.excluded_points.get(isotope_key, set())
            excluded_indices = {
                i for i, f in enumerate(folders_for_isotope)
                if f in excluded_folders
            }

            folder_names = [
                Path(f).name for f in folders_for_isotope
            ] if folders_for_isotope else []

            fit_stats = {
                'slope': method_data.get('slope', 0.0),
                'intercept': method_data.get('intercept', 0.0),
                'r_squared': method_data.get('r_squared', 0.0),
            }

            included_mask = [
                f not in excluded_folders for f in folders_for_isotope
            ] if folders_for_isotope else [True] * len(data.get('y', []))
            outlier_indices = self._compute_outlier_indices(
                data.get('y', []),
                method_data.get('y_fit', []),
                included_mask,
            )
            self._outlier_indices_by_isotope[isotope_key] = outlier_indices

            self.calibration_widget.update_plot(
                x_data=x_values,
                y_data=data.get('y', []),
                y_std=data.get('y_std', []),
                method=selected_method,
                y_fit=method_data.get('y_fit', []),
                key=isotope_label,
                excluded_indices=excluded_indices,
                folder_names=folder_names,
                fit_stats=fit_stats,
                outlier_indices=outlier_indices,
                unit_label=current_unit,
            )

            self.calibration_widget.setLabel('bottom', f"Concentration [{current_unit}]")
            self.calibration_widget.setLabel('left', "Signal [cps]")
            title = f"Calibration Results for {isotope_label} ({self.calibration_method_combo.currentText()})"
            self.calibration_widget.setTitle(title)

            self._update_exclusion_status_label(isotope_key,
                                                len(folders_for_isotope))

            self._sync_manual_slope_input(isotope_key, data, current_unit)

            self.update_results_table_with_method(isotope_key, data, current_unit)
                    
    def convert_concentration(self, value, from_unit, to_unit):
        """
        Convert concentration between different units.
        
        Args:
            value: Concentration value to convert
            from_unit: Source unit (ppb, ppm, ppt)
            to_unit: Target unit (ppb, ppm, ppt)
            
        Returns:
            Converted concentration value
        """
        if from_unit == to_unit:
            return value
            
        base_value = value / self.concentration_units[from_unit]
        return base_value * self.concentration_units[to_unit]

    def update_concentration_unit(self, new_unit):
        """
        Update concentration values when unit is changed.
        
        Args:
            new_unit: New concentration unit to use
        """
        if not hasattr(self, 'current_unit'):
            self.current_unit = new_unit
            return

        old_unit = self.current_unit
        self.current_unit = new_unit
        ual = _ual()
        if ual:
            ual.log_action('PARAMETER_CHANGE', f'Concentration unit: {old_unit} → {new_unit}',
                           {'old_unit': old_unit, 'new_unit': new_unit})

        self.ignore_item_changed = True
        try:
            for col in range(1, self.table.columnCount()):
                header = self.table.horizontalHeaderItem(col).text()
                element_isotope = header.split('[')[0].strip()
                new_header = f"{element_isotope} [{new_unit}]"
                self.table.setHorizontalHeaderItem(col, QTableWidgetItem(new_header))

                for row in range(self.table.rowCount()):
                    item = self.table.item(row, col)
                    if item and item.text():
                        try:
                            old_value = float(item.text())
                            new_value = self.convert_concentration(old_value, old_unit, new_unit)
                            self.table.setItem(row, col, QTableWidgetItem(f"{new_value:.4g}"))
                        except ValueError:
                            continue
        finally:
            self.ignore_item_changed = False

        self.calculate_calibration()
        self.update_results_table()
        
    def update_results_table(self):
        """
        Update the results table with calibration results for all methods.
        
        Displays all calibration methods for all isotopes, highlighting the
        preferred method for each isotope.
        """
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(0)
        
        if not self.calibration_results:
            return
            
        unit = self.unit_combo.currentText()
        
        row = 0
        method_display = {
            'zero': 'Force through zero',
            'simple': 'Simple linear',
            'weighted': 'Weighted',
            'manual': 'Manual'
        }
        
        for isotope_key, data in self.calibration_results.items():
            element, mass = isotope_key.split('-')
            isotope_label = self.get_isotope_label(element, float(mass))
            
            for method_key, method_name in method_display.items():
                if method_key in data:
                    method_data = data[method_key]
                    
                    self.results_table.insertRow(row)
                    self.results_table.setItem(row, 0, QTableWidgetItem(isotope_label))
                    self.results_table.setItem(row, 1, QTableWidgetItem(method_name))
                    self.results_table.setItem(row, 2, QTableWidgetItem(f"{method_data.get('slope', 0):.2e} cps/{unit}"))
                    self.results_table.setItem(row, 3, QTableWidgetItem(f"{method_data.get('intercept', 0):.2e} cps"))
                    self.results_table.setItem(row, 4, QTableWidgetItem(f"{method_data.get('bec', 0):.2e} {unit}"))
                    self.results_table.setItem(row, 5, QTableWidgetItem(f"{method_data.get('r_squared', 0):.4f}"))
                    self.results_table.setItem(row, 6, QTableWidgetItem(
                        f"{data.get('density', 'N/A'):.4f}" if isinstance(data.get('density'), (int, float)) else str(data.get('density', 'N/A'))
                    ))
                    self.results_table.setItem(row, 7, QTableWidgetItem(f"{method_data.get('lod', 0):.2e} {unit}"))
                    self.results_table.setItem(row, 8, QTableWidgetItem(f"{method_data.get('loq', 0):.2e} {unit}"))
                    
                    if isotope_key in self.isotope_method_preferences:
                        preferred_method = self.isotope_method_preferences[isotope_key]
                        if method_name == preferred_method:
                            status = getattr(self, "_status_colors", None) or _build_ionic_status_colors(theme.palette)
                            if method_name == 'Manual':
                                color = status["manual"]
                            else:
                                color = status["selected"]
                            
                            for col in range(9):
                                item = self.results_table.item(row, col)
                                if item:
                                    item.setBackground(QBrush(color))
                                    item.setForeground(QBrush(status["text"]))
                    
                    row += 1
        
        self.results_table.setSortingEnabled(True)
            
    def update_results_table_with_method(self, isotope_key, data, unit):
        """
        Update results table with original isotope labels.
        
        Args:
            isotope_key: Element identifier string
            data: Calibration data dictionary
            unit: Concentration unit for display
        """
        method_map = {
            'Force through zero': 'zero',
            'Simple linear': 'simple',
            'Weighted': 'weighted',
            'Manual': 'manual'
        }
        selected_method = method_map[self.calibration_method_combo.currentText()]
        
        method_data = data.get(selected_method, {})

        self.results_table.setRowCount(1)
        
        element, mass = isotope_key.split('-')
        isotope_label = self.get_isotope_label(element, float(mass))
        
        self.results_table.setItem(0, 0, QTableWidgetItem(isotope_label))
        self.results_table.setItem(0, 1, QTableWidgetItem(self.calibration_method_combo.currentText()))
        self.results_table.setItem(0, 2, QTableWidgetItem(f"{method_data.get('slope', 0):.6e} cps/{unit}"))
        self.results_table.setItem(0, 3, QTableWidgetItem(f"{method_data.get('intercept', 0):.6e} cps"))
        self.results_table.setItem(0, 4, QTableWidgetItem(f"{method_data.get('bec', 0):.6e} {unit}"))
        self.results_table.setItem(0, 5, QTableWidgetItem(f"{method_data.get('r_squared', 0):.6f}"))
        self.results_table.setItem(0, 6, QTableWidgetItem(f"{data.get('density', 'N/A'):.4f}" if isinstance(data.get('density'), (int, float)) else str(data.get('density', 'N/A'))))
        self.results_table.setItem(0, 7, QTableWidgetItem(f"{method_data.get('lod', 0):.6e} {unit}"))
        self.results_table.setItem(0, 8, QTableWidgetItem(f"{method_data.get('loq', 0):.6e} {unit}"))

    def get_isotope_label(self, element, mass):
        """
        Get the isotope label directly from the isotope data.
        
        Args:
            element: Element symbol
            mass: Isotope mass value
            
        Returns:
            Isotope label string (e.g., "65Cu")
        """
        element_data = next((e for e in self.periodic_table.get_elements() 
                            if e['symbol'] == element), None)
        if element_data:
            isotope_data = next((iso for iso in element_data['isotopes'] 
                            if isinstance(iso, dict) and 
                            abs(iso['mass'] - float(mass)) < 0.001), None)
            if isotope_data and 'label' in isotope_data:
                return isotope_data['label']
        return f"{element}-{mass:.4f}" 

    def element_selected(self, element):
        """
        Placeholder for element selection signal handler.
        
        Args:
            element: Selected element data
        """
        pass

    def _fit_zero(self, x, y):
        """
        Force-through-zero (FTZ) linear regression.
    
        Finds the slope that minimises Σ(y - slope·x)² with intercept = 0.
    
        Equation
        --------
        slope = Σ(x·y) / Σ(x²)               [ordinary least squares, no intercept]
        R²    = 1 − Σ(y − ŷ)² / Σ(y²)        [denominator uses Σy² not Σ(y−ȳ)²
                                                because the model passes through 0]
    
        Args:
            x (np.ndarray): Concentration values (base unit, e.g. ppb).
            y (np.ndarray): Mean signal values (cps).
    
        Returns:
            dict with keys: slope, intercept (always 0), r_squared, y_fit.
        """
        import numpy as np
    
        slope = np.sum(x * y) / np.sum(x * x)
        y_fit = slope * x
        ss_res = np.sum((y - y_fit) ** 2)
        ss_tot = np.sum(y ** 2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
    
        return {
            "slope": slope,
            "intercept": 0.0,
            "r_squared": r_squared,
            "y_fit": y_fit,
        }
    
    
    def _fit_simple(self, x, y):
        """
        Ordinary least squares (OLS) linear regression.
    
        Finds slope and intercept that minimise Σ(y − slope·x − intercept)².
    
        Equation
        --------
        [slope, intercept] = (XᵀX)⁻¹ Xᵀy   via np.linalg.lstsq
        R²  = 1 − Σ(y − ŷ)² / Σ(y − ȳ)²
    
        Args:
            x (np.ndarray): Concentration values.
            y (np.ndarray): Mean signal values (cps).
    
        Returns:
            dict with keys: slope, intercept, r_squared, y_fit.
        """
        import numpy as np
    
        A = np.vstack([x, np.ones(len(x))]).T
        slope, intercept = np.linalg.lstsq(A, y, rcond=None)[0]
        y_fit = slope * x + intercept
        ss_res = np.sum((y - y_fit) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
    
        return {
            "slope": slope,
            "intercept": intercept,
            "r_squared": r_squared,
            "y_fit": y_fit,
        }
    
    
    def _fit_weighted(self, x, y, y_std):
        """
        Weighted least squares (WLS) linear regression.
    
        Points with lower variance receive higher weight, giving more influence
        to the most precise measurements.
    
        Equation
        --------
        wᵢ      = 1 / σᵢ²
        slope   = (Σw · Σwxy − Σwx · Σwy) / (Σw · Σwx² − (Σwx)²)
        intercept = (Σwx² · Σwy − Σwx · Σwxy) / (Σw · Σwx² − (Σwx)²)
        R²_w    = 1 − Σwᵢ(yᵢ − ŷᵢ)² / Σwᵢ(yᵢ − ȳ)²
    
        Falls back to OLS when the denominator is numerically zero (i.e. all
        points have equal / zero variance).
    
        Args:
            x (np.ndarray): Concentration values.
            y (np.ndarray): Mean signal values (cps).
            y_std (np.ndarray): Standard deviations of the signal.
    
        Returns:
            dict with keys: slope, intercept, r_squared, y_fit.
        """
        import numpy as np
    
        weights = 1.0 / (y_std ** 2)
        w_sum   = np.sum(weights)
        wx_sum  = np.sum(weights * x)
        wy_sum  = np.sum(weights * y)
        wxx_sum = np.sum(weights * x * x)
        wxy_sum = np.sum(weights * x * y)
    
        denominator = w_sum * wxx_sum - wx_sum * wx_sum
    
        if abs(denominator) > 1e-17:
            slope     = (w_sum * wxy_sum - wx_sum * wy_sum) / denominator
            intercept = (wxx_sum * wy_sum - wx_sum * wxy_sum) / denominator
            y_fit     = slope * x + intercept
            ss_res    = np.sum(weights * (y - y_fit) ** 2)
            ss_tot    = np.sum(weights * (y - np.mean(y)) ** 2)
            r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
        else:
            ols = self._fit_simple(x, y)
            slope, intercept, y_fit = ols["slope"], ols["intercept"], ols["y_fit"]
            r_squared = ols["r_squared"]
    
        return {
            "slope": slope,
            "intercept": intercept,
            "r_squared": r_squared,
            "y_fit": y_fit,
        }
    
    
    def _compute_figures_of_merit(self, slope, intercept, sigma_blank):
        """
        Compute analytical figures of merit from regression results.
    
        Equations (IUPAC / Miller & Miller convention)
        -----------------------------------------------
        LOD = 3 · σ_blank / slope      [3-sigma limit of detection]
        LOQ = 10 · σ_blank / slope     [10-sigma limit of quantification]
        BEC = intercept / slope         [blank-equivalent concentration]
                (= LOD for FTZ, where intercept ≡ 0)
    
        All values are in the *base unit* (ppb by default) and are converted
        to the display unit separately before being shown in the UI.
    
        Args:
            slope (float): Calibration slope (cps / base_unit).
            intercept (float): Calibration intercept (cps).
            sigma_blank (float): Standard deviation of signal at lowest
                concentration standard (used as proxy for blank noise).
    
        Returns:
            dict with keys: lod, loq, bec.
                Values are np.nan when slope == 0.
        """
        import numpy as np
    
        if slope == 0:
            return {"lod": np.nan, "loq": np.nan, "bec": np.nan}
    
        lod = (3.0  * sigma_blank) / slope
        loq = (10.0 * sigma_blank) / slope
        bec = intercept / slope
    
        return {"lod": lod, "loq": loq, "bec": bec}
    

    def _run_all_fits_on_subset(self, x, y, y_std, included_mask, density):
        """
        Run the three calibration fits on the subset of points selected by
        ``included_mask`` and return the full result record for one isotope.

        Fits use only the included points, but ``y_fit`` is evaluated at
        every original x so the residuals subplot can show the distance
        between every point (included or not) and the fit line.

        Args:
            x, y, y_std: parallel 1-D numpy arrays (all points).
            included_mask: bool array same shape as x. True = use in fit.
            density: element density for the results record.

        Returns:
            dict or None. ``None`` when fewer than 2 included points remain.
        """
        import numpy as np

        if int(np.sum(included_mask)) < 2:
            return None

        xi = x[included_mask]
        yi = y[included_mask]
        si = y_std[included_mask]

        sigma_blank = float(si[int(np.argmin(xi))])

        fit_zero     = self._fit_zero(xi, yi)
        fit_simple   = self._fit_simple(xi, yi)
        fit_weighted = self._fit_weighted(xi, yi, si)
        
        def eval_line(slope, intercept):
            """
            Args:
                slope (Any): The slope.
                intercept (Any): The intercept.
            Returns:
                object: Result of the operation.
            """
            return (slope * x + intercept).tolist()

        y_fit_zero     = eval_line(fit_zero["slope"],     0.0)
        y_fit_simple   = eval_line(fit_simple["slope"],   fit_simple["intercept"])
        y_fit_weighted = eval_line(fit_weighted["slope"], fit_weighted["intercept"])

        fom_zero     = self._compute_figures_of_merit(
            fit_zero["slope"],     0.0,                    sigma_blank)
        fom_simple   = self._compute_figures_of_merit(
            fit_simple["slope"],   fit_simple["intercept"],   sigma_blank)
        fom_weighted = self._compute_figures_of_merit(
            fit_weighted["slope"], fit_weighted["intercept"], sigma_blank)

        return {
            'zero': {
                'slope':     fit_zero["slope"],
                'intercept': 0.0,
                'r_squared': fit_zero["r_squared"],
                'y_fit':     y_fit_zero,
                **fom_zero,
            },
            'simple': {
                'slope':     fit_simple["slope"],
                'intercept': fit_simple["intercept"],
                'r_squared': fit_simple["r_squared"],
                'y_fit':     y_fit_simple,
                **fom_simple,
            },
            'weighted': {
                'slope':     fit_weighted["slope"],
                'intercept': fit_weighted["intercept"],
                'r_squared': fit_weighted["r_squared"],
                'y_fit':     y_fit_weighted,
                **fom_weighted,
            },
            'x':       x.tolist(),
            'y':       y.tolist(),
            'y_std':   y_std.tolist(),
            'density': density,
        }

    def _compute_outlier_indices(self, y, y_fit, included_mask,
                                 z_threshold=2.5):
        """
        Flag included points whose standardized residual exceeds ``z_threshold``.

        Standardization uses the sample standard deviation of the *included*
        residuals (ddof=1). With too few points the flag is disabled.

        Returns:
            set[int]: indices into the full ``y`` array.
        Args:
            y (Any): Input array or value.
            y_fit (Any): The y fit.
            included_mask (Any): The included mask.
            z_threshold (Any): The z threshold.
        """
        import numpy as np
        y = np.asarray(y, dtype=float)
        y_fit = np.asarray(y_fit, dtype=float)
        if y.shape != y_fit.shape or len(y) == 0:
            return set()

        included_idx = [i for i, m in enumerate(included_mask) if m]
        if len(included_idx) < 4:
            return set()

        residuals = y - y_fit
        s = float(np.std(residuals[included_idx], ddof=1))
        if not np.isfinite(s) or s <= 0:
            return set()

        return {
            i for i in included_idx
            if abs(residuals[i] / s) > z_threshold
        }

    def refit_isotope(self, isotope_key):
        """
        Re-run the three fits for a single isotope using the current
        exclusion set. Called after every exclusion toggle.

        Returns True on success, False if the fit couldn't be performed
        (e.g. fewer than 2 points would remain included).
        Args:
            isotope_key (Any): The isotope key.
        """
        import numpy as np
        data = self.calibration_results.get(isotope_key)
        if not data:
            return False

        x     = np.asarray(data.get('x', []),     dtype=float)
        y     = np.asarray(data.get('y', []),     dtype=float)
        y_std = np.asarray(data.get('y_std', []), dtype=float)
        folders = data.get('folders', [])

        if len(x) == 0 or not folders:
            return False

        excluded_folders = self.excluded_points.get(isotope_key, set())
        included_mask = np.array(
            [f not in excluded_folders for f in folders])

        density = data.get('density', 'N/A')

        new_result = self._run_all_fits_on_subset(
            x, y, y_std, included_mask, density)
        if new_result is None:
            return False

        new_result['folders'] = list(folders)
        new_result['excluded_folders'] = sorted(excluded_folders)
        self.calibration_results[isotope_key] = new_result
        self.data_modified = True
        if hasattr(self, 'save_action'):
            self.save_action.setEnabled(True)
        return True

    # ------------------------------------------------------------------ #
    # Slots wired to the CalibrationPlotWidget signals
    # ------------------------------------------------------------------ #
    def on_calibration_point_exclusion_toggled(self, index):
        """Toggle exclusion of the clicked point for the current isotope,
        refit, and redraw.
        Args:
            index (Any): Row or item index.
        """
        current_index = self.element_isotope_combo.currentIndex()
        if current_index < 0:
            return
        isotope_key = self.element_isotope_combo.itemData(current_index)
        if not isotope_key or isotope_key not in self.calibration_results:
            return

        data = self.calibration_results[isotope_key]
        folders = data.get('folders', [])
        if index < 0 or index >= len(folders):
            return

        folder_path = folders[index]
        excluded = self.excluded_points.setdefault(isotope_key, set())

        if folder_path in excluded:
            excluded.discard(folder_path)
        else:
            remaining = sum(
                1 for f in folders
                if f not in excluded and f != folder_path
            )
            if remaining < 2:
                self.statusBar.showMessage(
                    "Cannot exclude: a fit needs at least 2 included points.",
                    4000)
                return
            excluded.add(folder_path)

        if not self.refit_isotope(isotope_key):
            if folder_path in excluded:
                excluded.discard(folder_path)
            else:
                excluded.add(folder_path)
            self.statusBar.showMessage("Refit failed; exclusion not applied.",
                                       4000)
            return

        element, mass = isotope_key.split('-')
        self.display_calibration(element, float(mass))
        self.update_results_table()

    # ------------------------------------------------------------------ #
    # Toolbar handlers — reset exclusions
    # ------------------------------------------------------------------ #
    def reset_current_isotope_exclusions(self):
        """Clear all exclusions for the currently-displayed isotope and refit."""
        current_index = self.element_isotope_combo.currentIndex()
        if current_index < 0:
            return
        isotope_key = self.element_isotope_combo.itemData(current_index)
        if not isotope_key:
            return
        if not self.excluded_points.get(isotope_key):
            self.statusBar.showMessage("No exclusions to reset.", 2000)
            return

        self.excluded_points[isotope_key] = set()
        if self.refit_isotope(isotope_key):
            element, mass = isotope_key.split('-')
            self.display_calibration(element, float(mass))
            self.update_results_table()
            self.statusBar.showMessage(
                f"Reset exclusions for {self.get_isotope_label(element, float(mass))}",
                3000)

    def _update_exclusion_status_label(self, isotope_key, total_points):
        """Refresh the small status label next to the plot controls.
        Args:
            isotope_key (Any): The isotope key.
            total_points (Any): The total points.
        """
        if not hasattr(self, 'exclusion_status_label'):
            return
        excluded = self.excluded_points.get(isotope_key, set())
        n = len(excluded)
        if n == 0:
            self.exclusion_status_label.setText(
                f"{total_points} points  (click a point to exclude it)"
                if total_points else ""
            )
        else:
            self.exclusion_status_label.setText(
                f"{n}/{total_points} excluded  (click to toggle)"
            )

    def _set_manual_slope_controls_visible(self, visible: bool):
        """Show or hide the inline manual-slope input + Match-fit button.
        Args:
            visible (bool): Whether the item is visible.
        """
        for w in ('manual_slope_label', 'manual_slope_input',
                  'manual_match_btn'):
            widget = getattr(self, w, None)
            if widget is not None:
                widget.setVisible(visible)

    def _sync_manual_slope_input(self, isotope_key, data, current_unit):
        """Populate the inline slope input for the currently-displayed
        isotope. Called from display_calibration at every refresh.

        The input is shown only when the active method is Manual. Its
        value is read from self.sensitivity_overrides when available,
        otherwise seeded from the Simple-linear fit.
        Args:
            isotope_key (Any): The isotope key.
            data (Any): Input data.
            current_unit (Any): The current unit.
        """
        is_manual = (self.calibration_method_combo.currentText() == 'Manual')
        self._set_manual_slope_controls_visible(is_manual)
        if not is_manual:
            return

        if isotope_key in self.sensitivity_overrides:
            slope = float(self.sensitivity_overrides[isotope_key].get(
                'slope', 10.0))
        else:
            simple = data.get('simple', {}) if data else {}
            slope = float(simple.get('slope', 10.0))
            if slope <= 0:
                slope = 10.0

        self.manual_slope_input.setSuffix(f" cps/{current_unit}")

        self.manual_slope_input.blockSignals(True)
        self.manual_slope_input.setValue(slope)
        self.manual_slope_input.blockSignals(False)

    def on_manual_match_fit(self):
        """Copy the Simple-linear slope into the manual input for the
        current isotope, then apply it as the manual value.
        """
        current_index = self.element_isotope_combo.currentIndex()
        if current_index < 0:
            return
        isotope_key = self.element_isotope_combo.itemData(current_index)
        if not isotope_key or isotope_key not in self.calibration_results:
            return
        simple_slope = float(
            self.calibration_results[isotope_key]
            .get('simple', {}).get('slope', 0.0)
        )
        if simple_slope <= 0:
            self.statusBar.showMessage(
                "No Simple-linear slope available to copy.", 3000)
            return
        self.manual_slope_input.blockSignals(True)
        self.manual_slope_input.setValue(simple_slope)
        self.manual_slope_input.blockSignals(False)
        self.on_manual_slope_changed()

    def on_manual_slope_changed(self):
        """Apply the inline manual slope to the current isotope.

        Computes y_fit = slope · x (intercept ≡ 0 for a manual slope),
        re-derives LOD / LOQ / BEC from the stored y_std, stores the
        result in both calibration_results[key]['manual'] and
        sensitivity_overrides[key], and redraws the plot + results table.
        """
        if not hasattr(self, 'calibration_method_combo'):
            return
        if self.calibration_method_combo.currentText() != 'Manual':
            return

        current_index = self.element_isotope_combo.currentIndex()
        if current_index < 0:
            return
        isotope_key = self.element_isotope_combo.itemData(current_index)
        if not isotope_key or isotope_key not in self.calibration_results:
            return

        slope = float(self.manual_slope_input.value())
        if slope <= 0:
            self.statusBar.showMessage(
                "Manual slope must be positive.", 3000)
            return

        import numpy as np
        data = self.calibration_results[isotope_key]
        x = np.asarray(data.get('x', []), dtype=float)
        y_std = np.asarray(data.get('y_std', []), dtype=float)
        folders = data.get('folders', [])

        if len(x) == 0:
            return

        y_fit = (slope * x).tolist()

        excluded = self.excluded_points.get(isotope_key, set())
        included = [i for i, f in enumerate(folders) if f not in excluded]
        if included and len(y_std) == len(x):
            inc_x = x[included]
            inc_std = y_std[included]
            sigma_blank = float(inc_std[int(np.argmin(inc_x))])
        elif len(y_std) > 0:
            sigma_blank = float(np.min(y_std))
        else:
            sigma_blank = 0.0

        fom = self._compute_figures_of_merit(slope, 0.0, sigma_blank)

        element = isotope_key.split('-')[0]
        element_data = next(
            (e for e in self.periodic_table.get_elements()
             if e['symbol'] == element),
            None
        )
        density = (element_data['density']
                   if element_data else data.get('density', 'N/A'))

        manual_record = {
            'slope':     slope,
            'intercept': 0.0,
            'r_squared': 1.0,
            'y_fit':     y_fit,
            'density':   density,
            **fom,
        }

        self.calibration_results[isotope_key]['manual'] = manual_record
        self.sensitivity_overrides[isotope_key] = manual_record.copy()
        self.isotope_method_preferences[isotope_key] = 'Manual'
        self.data_modified = True
        if hasattr(self, 'save_action'):
            self.save_action.setEnabled(True)


        if hasattr(self, 'sensitivity_table'):
            try:
                self.update_sensitivity_table()
            except Exception:
                pass

        element, mass = isotope_key.split('-')
        self.display_calibration(element, float(mass))
        self.update_results_table()

    # ------------------------------------------------------------------ #
    # Isotope navigation (Ctrl+Left / Ctrl+Right)
    # ------------------------------------------------------------------ #
    def next_isotope(self):
        count = self.element_isotope_combo.count()
        if count == 0:
            return

        if self.tab_widget.currentWidget() is not self.calibration_tab:
            return
        idx = (self.element_isotope_combo.currentIndex() + 1) % count
        self.element_isotope_combo.setCurrentIndex(idx)

    def prev_isotope(self):
        count = self.element_isotope_combo.count()
        if count == 0:
            return
        if self.tab_widget.currentWidget() is not self.calibration_tab:
            return
        idx = (self.element_isotope_combo.currentIndex() - 1) % count
        self.element_isotope_combo.setCurrentIndex(idx)


    def perform_calibration(self, concentrations, progress=None):
        """
        Orchestrate calibration calculations for all selected isotopes.
    
        For each isotope, assembles (x, y, y_std) arrays from the loaded
        folders, then delegates regression and figure-of-merit calculations
        to the private helpers:
    
            _fit_zero()                 → Force-through-zero
            _fit_simple()               → OLS linear
            _fit_weighted()             → WLS linear
            _compute_figures_of_merit() → LOD, LOQ, BEC
    
        Args:
            concentrations (dict): {folder: {isotope_key: concentration_ppb}}
            progress (QProgressDialog | None): Optional progress dialog.
    
        Returns:
            dict: {isotope_key: {
                    'zero':     {slope, intercept, r_squared, y_fit, lod, loq, bec},
                    'simple':   {…},
                    'weighted': {…},
                    'x':        list[float],
                    'y':        list[float],
                    'y_std':    list[float],
                    'density':  float | str,
                }}
        """
        import numpy as np
        from PySide6.QtWidgets import QApplication
    
        results = {}
    
        first_folder_data = next(iter(self.data.values()))
        reference_masses  = first_folder_data['masses']
    
        isotope_indices = {}
        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                key = f"{element}-{isotope:.4f}"
                isotope_indices[key] = int(np.argmin(np.abs(reference_masses - isotope)))
    
        total_isotopes  = sum(len(v) for v in self.selected_isotopes.values())
        isotope_count   = 0
    
        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                isotope_key = f"{element}-{isotope:.4f}"
                mass_index  = isotope_indices[isotope_key]
    
                # ── Progress update ───────────────────────────────────────────
                if progress:
                    isotope_count += 1
                    progress.setValue(30 + int(60 * isotope_count / total_isotopes))
                    progress.setLabelText(
                        f"Calculating: {self.get_isotope_label(element, isotope)}"
                    )
                    QApplication.processEvents()
    
                x_list, y_list, y_std_list = [], [], []
                folders_list = []
    
                for folder, folder_data in self.data.items():
                    if isotope_key not in concentrations.get(folder, {}):
                        continue
    
                    conc = concentrations[folder][isotope_key]
                    if conc == -1:
                        continue
    
                    run_info      = folder_data['run_info']
                    acq_ns        = run_info["SegmentInfo"][0]["AcquisitionPeriodNs"]
                    dwell_time    = (acq_ns * 1e-9
                                    * run_info["NumAccumulations1"]
                                    * run_info["NumAccumulations2"])
    
                    local_masses = folder_data['masses']
                    local_idx    = int(np.argmin(np.abs(local_masses - isotope)))
    
                    counts = folder_data['signals'][:, local_idx]
                    cps    = counts / dwell_time

         
                    time_values = np.arange(len(cps)) * dwell_time
                    time_mask   = np.ones(len(cps), dtype=bool)
                    for lo, hi in self._time_exclusions_element.get(
                            (folder, isotope_key), []):
                        time_mask &= ~((time_values >= lo) & (time_values <= hi))
                    for lo, hi in self._time_exclusions_sample.get(folder, []):
                        time_mask &= ~((time_values >= lo) & (time_values <= hi))

              
                    if not time_mask.any():
                        continue

                    cps_for_stats = cps[time_mask]

                    x_list.append(conc)
                    y_list.append(float(np.mean(cps_for_stats)))
                    y_std_list.append(float(np.std(cps_for_stats)))
                    folders_list.append(folder)
    
                if len(x_list) == 0:
                    continue

                # ── Element density from periodic table ───────────────────────
                element_data = next(
                    (e for e in self.periodic_table.get_elements()
                    if e['symbol'] == element),
                    None
                )
                density = element_data['density'] if element_data else 'N/A'

                if len(x_list) == 1:
           
                    x1 = np.array(x_list)
                    y1 = np.array(y_list)
                    s1 = np.array(y_std_list)
                    fit_zero = self._fit_zero(x1, y1)
                    fom = self._compute_figures_of_merit(
                        fit_zero["slope"], 0.0, float(s1[0])
                    )
                    y_fit = (fit_zero["slope"] * x1).tolist()
   
                    shared = {
                        'slope':     fit_zero["slope"],
                        'intercept': 0.0,
                        'r_squared': 1.0,
                        'y_fit':     y_fit,
                        **fom,
                    }
                    results[isotope_key] = {
                        'zero':             shared.copy(),
                        'simple':           shared.copy(),
                        'weighted':         shared.copy(),
                        'x':                x1.tolist(),
                        'y':                y1.tolist(),
                        'y_std':            s1.tolist(),
                        'density':          density,
                        'folders':          list(folders_list),
                        'excluded_folders': [],
                        'single_point':     True,
                    }
                    continue

                x     = np.array(x_list)
                y     = np.array(y_list)
                y_std = np.array(y_std_list)


                excluded_folders = self.excluded_points.get(isotope_key, set())
                included_mask = np.array(
                    [f not in excluded_folders for f in folders_list])

                isotope_result = self._run_all_fits_on_subset(
                    x, y, y_std, included_mask, density)
                if isotope_result is None:
        
                    continue
                isotope_result['folders'] = list(folders_list)
           
                isotope_result['excluded_folders'] = sorted(excluded_folders)
                results[isotope_key] = isotope_result

        return results

    def load_folders(self):
        """
        Load folders or CSV files for calibration with improved dialog structure.
        
        Displays dialog allowing user to choose between NU folders (with run.info),
        data files (CSV, TXT, Excel formats), or TOFWERK .h5 files.
        """
        if not self.prompt_save_changes():
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Data Source")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(400)

        dialog.setStyleSheet(_build_ionic_qss(theme.palette))
        layout = QVBoxLayout(dialog)
        
        instruction = QLabel("Choose your data source type:")
        instruction.setObjectName("dialogInstruction")
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

        folder_desc = QLabel("• Select folders containing NU instrument data with run.info files\n• Supports multiple folders for batch processing\n• ⚠️ Mass ranges must match main analysis")
        folder_desc.setObjectName("helpMuted")
        
        csv_desc = QLabel("• Select Data Files with mass spectrometry data\n• Configure column mappings and time settings\n• ✅ No mass range validation required")
        csv_desc.setObjectName("helpMuted")
        
        tofwerk_desc = QLabel("• Select TOFWERK .h5 files from TofDAQ acquisitions\n• Supports multiple files for batch processing\n• ✅ No mass range validation required")
        tofwerk_desc.setObjectName("helpMuted")
        
        layout.addWidget(folder_desc)
        layout.addWidget(csv_desc)
        layout.addWidget(tofwerk_desc)
        layout.addStretch()

        button_box = QHBoxLayout()
        ok_button = QPushButton("Continue", dialog)
        ok_button.setObjectName("primaryBtn")
        cancel_button = QPushButton("Cancel", dialog)
        cancel_button.setObjectName("secondaryBtn")

        button_box.addStretch()
        button_box.addWidget(ok_button)
        button_box.addWidget(cancel_button)
        layout.addLayout(button_box)

        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)

        if dialog.exec() == QDialog.Accepted:
            if folder_radio.isChecked():
                ual = _ual()
                if ual:
                    ual.log_action('FILE_OP', 'Load Folders — NU folders selected')
                self.select_nu_folders()
            elif csv_radio.isChecked():
                ual = _ual()
                if ual:
                    ual.log_action('FILE_OP', 'Load Folders — CSV/data files selected')
                self.select_data_files()
            else:
                ual = _ual()
                if ual:
                    ual.log_action('FILE_OP', 'Load Folders — TOFWERK .h5 files selected')
                self.select_tofwerk_files()
                
    def select_tofwerk_files(self):
        """
        Handle TOFWERK .h5 file selection for calibration.
        
        Opens file dialog for selecting multiple TOFWERK files and initiates
        TOFWERK import process.
        """
        try:
            h5_files, _ = QFileDialog.getOpenFileNames(
                self,
                "Select TOFWERK .h5 Files for Calibration",
                "",
                "TOFWERK Files (*.h5);;All Files (*)"
            )
            
            if h5_files:
                ual = _ual()
                if ual:
                    ual.log_file_operation(
                        'OPEN', f'{len(h5_files)} TOFWERK .h5 file(s)',
                        {'source': 'TOFWERK', 'files': [str(p) for p in h5_files[:5]]})
                self.handle_tofwerk_import(h5_files)
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error selecting TOFWERK files: {str(e)}")
            
    def handle_tofwerk_import(self, h5_file_paths):
        """
        Handle TOFWERK .h5 file import for calibration.
        
        Args:
            h5_file_paths: List of .h5 file paths to import
            
        Skips mass range validation for TOFWERK files, processes files and
        updates UI accordingly.
        """
        try:
            progress = QProgressDialog("Processing TOFWERK files...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            QApplication.processEvents()
            
            self.data = {}
            self.folder_paths = []
            self.all_masses = set()
            
            total_files = len(h5_file_paths)
            
            for i, h5_path in enumerate(h5_file_paths):
                if progress.wasCanceled():
                    return
                    
                progress.setValue(int((i / total_files) * 90))
                h5_file = Path(h5_path)
                progress.setLabelText(f"Processing {h5_file.name}...")
                QApplication.processEvents()
                
                try:
                    sample_name = h5_file.stem
                    
                    data, info, dwell_time = loading.tofwerk_loading.read_tofwerk_file(h5_path)
                    if 'mass' in info.dtype.names:
                        masses = info['mass']
                    else:
                        masses = np.array([float(label.decode() if isinstance(label, bytes) else label) 
                                        for label in info['label']])
                    
                    if hasattr(data.dtype, 'names') and data.dtype.names:
                        signals = np.column_stack([data[name] for name in data.dtype.names])
                    else:
                        signals = data
                    
                    run_info = {
                        "DataFormat": "TOFWERK",
                        "DwellTime": dwell_time,
                        "SampleName": sample_name,
                        "OriginalFile": str(h5_path),
                        "NumAccumulations1": 1,
                        "NumAccumulations2": 1,
                        "SegmentInfo": [{
                            "AcquisitionPeriodNs": dwell_time * 1e9
                        }]
                    }
                    
                    self.data[h5_path] = {
                        'masses': masses,
                        'signals': signals,
                        'run_info': run_info
                    }
                    self.folder_paths.append(h5_path)
                    self.all_masses.update(masses)
                    
                except Exception as e:
                    QMessageBox.warning(self, "Warning", 
                        f"Error loading TOFWERK file: {h5_file.name}\n{str(e)}")
                    continue
            
            if self.all_masses:
                self.all_masses = sorted(list(self.all_masses))
            
            progress.setValue(95)
            progress.setLabelText("Updating interface...")
            QApplication.processEvents()
            
            self.update_table_rows()
            self.update_sample_combo()
            self.update_periodic_table()
            
            if self.selected_isotopes:
                self.update_table_columns()
                self.update_sensitivity_table()
            
            progress.setValue(100)
            progress.close()
            
            self.statusBar.showMessage(f"Successfully loaded {len(h5_file_paths)} TOFWERK files (mass validation skipped)", 5000)
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(self, "TOFWERK Import Error", f"Failed to process files: {str(e)}")

    def select_nu_folders(self):
        """
        Handle NU folder selection for calibration.
        
        Opens file dialog for selecting multiple folders with run.info files,
        validates and processes selected folders.
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

                ual = _ual()
                if ual:
                    ual.log_file_operation(
                        'OPEN',
                        ', '.join(selected_paths[:3]) + ('…' if len(selected_paths) > 3 else ''),
                        {'source': 'NU folders', 'count': len(selected_paths)})
                self.handle_folder_import(selected_paths)
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error selecting folders: {str(e)}")

    def select_data_files(self):
        """
        Handle data file selection for CSV, TXT, and Excel formats.
        
        Opens file dialog for selecting multiple data files and initiates
        CSV import process.
        """
        try:
            try:
                from loading.import_csv_dialogs import show_csv_structure_dialog
            except ImportError:
                QMessageBox.critical(self, "Import Error", 
                    "Data file import functionality is not available. Please ensure the import_csv_dialogs.py file is present.")
                return
                    
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Select Data Files for Calibration",
                "",
                "Data Files (*.csv *.txt *.xls *.xlsx *.xlsm *.xlsb);;CSV Files (*.csv);;Text Files (*.txt);;Excel Files (*.xls *.xlsx *.xlsm *.xlsb);;All Files (*)"
            )
            
            if file_paths:
                ual = _ual()
                if ual:
                    ual.log_file_operation(
                        'OPEN', f'{len(file_paths)} CSV/data file(s)',
                        {'source': 'CSV', 'files': [str(p) for p in file_paths[:5]]})
                self.handle_csv_import(file_paths)
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error selecting data files: {str(e)}")
                    
    def handle_csv_import(self, selected_paths):
        """
        Handle CSV/Excel file import using import_csv_dialogs.
        
        Args:
            selected_paths: List of file paths to import
            
        Skips mass range validation for CSV files, processes files using
        CSV structure dialog configuration.
        """
        try:
            from loading.import_csv_dialogs import show_csv_structure_dialog
            
            config = show_csv_structure_dialog(selected_paths, self)
            if not config:
                return
                
            progress = QProgressDialog("Processing files...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            QApplication.processEvents()
            
            self.data = {}
            self.folder_paths = []
            self.all_masses = set()
            
            from loading.import_csv_dialogs import DataProcessThread
            
            process_thread = DataProcessThread(config)
            
            process_thread.progress.connect(progress.setValue)
            process_thread.error.connect(lambda msg: QMessageBox.warning(self, "Error", msg))
            
            results = []
            process_thread.finished.connect(lambda data, run_info, time_array, sample_name, datetime: 
                                        results.append((data, run_info, time_array, sample_name, datetime)))
            
            process_thread.run()
            
            for i, (signals, run_info, time_array, sample_name, datetime) in enumerate(results):
                if progress.wasCanceled():
                    return
                    
                masses = list(signals.keys())
                signals_array = np.column_stack([signals[mass] for mass in masses])
                masses_array = np.array(masses)
                
                sample_path = f"{sample_name}"
                self.data[sample_path] = {
                    'masses': masses_array,
                    'signals': signals_array,
                    'run_info': run_info
                }
                self.folder_paths.append(sample_path)
                self.all_masses.update(masses)
            
            self.all_masses = sorted(list(self.all_masses))
            
            progress.setValue(95)
            progress.setLabelText("Updating interface...")
            QApplication.processEvents()
            
            self.update_table_rows()
            self.update_sample_combo()
            self.update_periodic_table()
            
            if self.selected_isotopes:
                self.update_table_columns()
                self.update_sensitivity_table()
            
            progress.setValue(100)
            progress.close()
            
            self.statusBar.showMessage(f"Successfully loaded {len(selected_paths)} CSV files (mass validation skipped)", 5000)
            
        except ImportError:
            QMessageBox.critical(self, "Module Error", 
                            "CSV import module not available. Please ensure import_csv_dialogs.py is in the project.")
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(self, "CSV Import Error", f"Failed to process files: {str(e)}")

    def handle_folder_import(self, selected_paths):
        """
        Handle folder import with mass range validation.
        
        Args:
            selected_paths: List of folder paths to import
            
        Validates folders against parent window mass ranges, loads data from
        valid folders, and updates UI.
        """
        progress = QProgressDialog("Processing selected folders...", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()
        
        self.folder_paths = selected_paths
        
        progress.setLabelText("Validating folders...")
        progress.setValue(10)
        QApplication.processEvents()
        
        reference_masses = None
        mass_tolerance = 0.1
        valid_folders = []
        
        for i, folder in enumerate(self.folder_paths):
            if progress.wasCanceled():
                return
                
            folder_progress = 10 + int((i / len(self.folder_paths)) * 40)
            progress.setValue(folder_progress)
            progress.setLabelText(f"Checking {Path(folder).name}...")
            QApplication.processEvents()
            
            try:
                masses, _, _ = loading.vitesse_loading.read_nu_directory(folder)

                mismatch_msg = None

                if self.parent_window and hasattr(self.parent_window, 'all_masses'):
                    parent_masses = self.parent_window.all_masses
                    if len(masses) != len(parent_masses):
                        mismatch_msg = (
                            f"Mass count mismatch with main analysis:\n"
                            f"  • This folder: {len(masses)} masses\n"
                            f"  • Main analysis: {len(parent_masses)} masses"
                        )
                    else:
                        mass_differences = np.abs(masses - parent_masses)
                        if np.any(mass_differences > mass_tolerance):
                            different_masses = [
                                f"{m1:.4f} vs {m2:.4f}"
                                for m1, m2, diff in zip(masses, parent_masses, mass_differences)
                                if diff > mass_tolerance
                            ]
                            mismatch_msg = (
                                f"Mass value mismatch with main analysis:\n"
                                f"  • Different masses: {', '.join(different_masses)}"
                            )

                if mismatch_msg is None and reference_masses is not None:
                    if len(masses) != len(reference_masses):
                        mismatch_msg = (
                            f"Mass count mismatch between calibration folders:\n"
                            f"  • This folder: {len(masses)} masses\n"
                            f"  • First folder: {len(reference_masses)} masses"
                        )
                    else:
                        mass_differences = np.abs(masses - reference_masses)
                        if np.any(mass_differences > mass_tolerance):
                            mismatch_msg = (
                                f"Mass value mismatch between calibration folders.\n"
                                f"  • Folders do not share identical mass ranges."
                            )

                if mismatch_msg is not None:
                    # ── informational mismatch dialog ──────────────────────
                    progress.close()
                    dlg = QMessageBox(self)
                    dlg.setWindowTitle("Mass Mismatch Detected")
                    dlg.setIcon(QMessageBox.Icon.Information)
                    dlg.setText(
                        f"<b>A mass mismatch was detected for:</b><br>"
                        f"<code>{Path(folder).name}</code>"
                    )
                    dlg.setInformativeText(
                        mismatch_msg.replace("\n", "<br>") +
                        "<br><br>You can ignore this warning and add the folder anyway, "
                        "or skip it."
                    )
                    btn_ignore = dlg.addButton("Ignore & Add Anyway", QMessageBox.ButtonRole.AcceptRole)
                    btn_skip   = dlg.addButton("Skip Folder",         QMessageBox.ButtonRole.RejectRole)
                    dlg.setDefaultButton(btn_skip)
                    dlg.exec()

                    progress = QProgressDialog("Processing selected folders...", "Cancel", 0, 100, self)
                    progress.setWindowModality(Qt.WindowModality.WindowModal)
                    progress.show()

                    if dlg.clickedButton() is btn_ignore:
                        if reference_masses is None:
                            reference_masses = masses
                        valid_folders.append(folder)
                    continue

                # ── no mismatch ────────────────────────────────────────────
                if reference_masses is None:
                    reference_masses = masses
                valid_folders.append(folder)

            except Exception as e:
                progress.close()
                QMessageBox.warning(
                    self,
                    "Folder Validation Error",
                    f"Error validating folder {folder}:\n{str(e)}\n\nThis folder will be skipped."
                )
                progress = QProgressDialog("Processing selected folders...", "Cancel", 0, 100, self)
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.show()
                continue
        
        if not valid_folders:
            progress.close()
            raise ValueError("No valid folders found after mass validation")
        
        progress.setValue(60)
        progress.setLabelText("Loading data...")
        QApplication.processEvents()
        
        self.folder_paths = valid_folders
        
        self.load_data()
        
        progress.setValue(80)
        progress.setLabelText("Updating interface...")
        QApplication.processEvents()
        
        self.update_table_rows()
        self.update_sample_combo()
        if self.plot_isotope_combo.count() > 0:
            self.update_time_plot()
        self.update_periodic_table()
        
        if self.selected_isotopes:
            self.update_table_columns()
            self.update_sensitivity_table()
        
        progress.setValue(100)
        progress.close()
        
    
    def load_data(self):
        """
        Load data from folders or files.
        
        Reads mass spectrometry data from all folder/file paths using appropriate
        loading method (vitesse_loading for NU, tofwerk_loading for TOFWERK),
        updates data dictionary and all_masses set.
        """
        self.data = {}
        self.all_masses = set()
        
        for folder_path in self.folder_paths:
            try:
                path = Path(folder_path)

                if path.is_file() and path.suffix.lower() == '.h5':
                    try:
                        if loading.tofwerk_loading.is_tofwerk_file(path):

                            data, info, dwell_time = loading.tofwerk_loading.read_tofwerk_file(path)
                
                            if 'mass' in info.dtype.names:
                                masses = info['mass']
                            else:
                                masses = np.array([float(label.decode() if isinstance(label, bytes) else label) 
                                                for label in info['label']])
  
                            if hasattr(data.dtype, 'names') and data.dtype.names:
                                signals = np.column_stack([data[name] for name in data.dtype.names])
                            else:
                                signals = data
      
                            run_info = {
                                "DataFormat": "TOFWERK",
                                "DwellTime": dwell_time,
                                "SampleName": path.stem,
                                "OriginalFile": str(path),
                                "NumAccumulations1": 1,
                                "NumAccumulations2": 1,
                                "SegmentInfo": [{
                                    "AcquisitionPeriodNs": dwell_time * 1e9
                                }]
                            }
                            
                            self.data[folder_path] = {
                                'masses': masses,
                                'signals': signals,
                                'run_info': run_info
                            }
                            self.all_masses.update(masses)
                            continue
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Failed to load TOFWERK file {path.name}: {str(e)}")
                        continue
                
                masses, signals, run_info = loading.vitesse_loading.read_nu_directory(folder_path)
                self.data[folder_path] = {'masses': masses, 'signals': signals, 'run_info': run_info}
                self.all_masses.update(masses)
                
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load data from {folder_path}: {str(e)}")
                
        self.all_masses = list(self.all_masses)

    def prompt_save_changes(self):
        """
        Prompt user to save changes if data is modified.
        
        Returns:
            bool: True if user wants to continue, False if user cancels
        """
        if self.data_modified:
            reply = QMessageBox.question(
                self, 
                'Save Changes?',
                "You have unsaved changes. Would you like to save them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self.save_session()
                    return True
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to save changes: {str(e)}")
                    return False
            elif reply == QMessageBox.StandardButton.Cancel:
                return False
        return True
    
    def closeEvent(self, event):
        """
        Handle window close event.
        
        Args:
            event: Close event object
        """
        if self.prompt_save_changes():
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = IonicCalibrationWindow()
    window.showMaximized()
    sys.exit(app.exec())