from PySide6.QtWidgets import (
    QPushButton, QVBoxLayout, QLabel, QTableWidget, QDialog, QCheckBox, 
    QTableWidgetItem, QTabWidget, QHBoxLayout, QLineEdit, QGroupBox,
    QSplitter, QTextEdit, QHeaderView, QFrame, QGridLayout, QProgressBar,
    QToolButton, QSpacerItem, QSizePolicy, QWidget
)
from PySide6.QtGui import QColor, QBrush, QIcon, QFont, QPalette
from PySide6.QtCore import Qt, QTimer

class CalibrationInfoDialog(QDialog):
    def __init__(self, calibration_results, selected_methods, method_preferences=None, parent=None):
        """
        Initialize the calibration information dialog.
        
        Args:
            calibration_results: Dictionary containing all calibration results data
            selected_methods: List of selected transport rate methods
            method_preferences: Dictionary mapping elements to preferred calibration methods
            parent: Parent widget for the dialog
            
        Returns:
            None
        """
        super().__init__(parent)
        self.setWindowTitle("Calibration Information")
        self.setMinimumSize(900, 600)
        self.resize(1000, 700)
        
        self.calibration_results = calibration_results
        self.selected_methods = selected_methods
        self.method_preferences = method_preferences or {}
        self.average_transport_rate = 0
        
        self.setStyleSheet(self.get_modern_stylesheet())
        
        self.init_ui()
        self.populate_data()
        
    def get_modern_stylesheet(self):
        """
        Get the modern stylesheet for the dialog.
        
        Args:
            None
            
        Returns:
            str: CSS stylesheet string for modern UI styling
        """
        return """
        QDialog {
            background-color: #f8f9fa;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        
        QTabWidget::pane {
            border: 1px solid #dee2e6;
            background-color: white;
            border-radius: 8px;
        }
        
        QTabWidget::tab-bar {
            alignment: left;
        }
        
        QTabBar::tab {
            background-color: #e9ecef;
            border: 1px solid #dee2e6;
            padding: 10px 16px;
            margin-right: 2px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            font-weight: 500;
        }
        
        QTabBar::tab:selected {
            background-color: white;
            border-bottom: 1px solid white;
            color: #0d6efd;
            font-weight: 600;
        }
        
        QTabBar::tab:hover:!selected {
            background-color: #f8f9fa;
        }
        
        QTableWidget {
            gridline-color: #e9ecef;
            background-color: white;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            font-size: 12px;
            selection-background-color: #e3f2fd;
        }
        
        QTableWidget::item {
            padding: 8px;
            border-bottom: 1px solid #f1f3f4;
        }
        
        QTableWidget::item:selected {
            background-color: #e3f2fd;
            color: #1565c0;
        }
        
        QHeaderView::section {
            background-color: #495057;
            color: white;
            padding: 10px 6px;
            border: none;
            font-weight: 600;
            font-size: 11px;
        }
        
        QGroupBox {
            font-weight: 600;
            border: 2px solid #dee2e6;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 12px;
            background-color: white;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            padding: 0 10px;
            color: #495057;
        }
        
        QPushButton {
            background-color: #0d6efd;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 12px;
            font-weight: 500;
            font-size: 13px;
        }
        
        QPushButton:hover {
            background-color: #0b5ed7;
        }
        
        QPushButton:pressed {
            background-color: #0a58ca;
        }
        
        QPushButton#exportButton {
            background-color: #198754;
        }
        
        QPushButton#exportButton:hover {
            background-color: #157347;
        }
        
        QLineEdit {
            border: 2px solid #dee2e6;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 13px;
            background-color: white;
        }
        
        QLineEdit:focus {
            border-color: #0d6efd;
            outline: none;
        }
        
        QCheckBox {
            font-size: 13px;
            spacing: 6px;
        }
        
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border-radius: 3px;
        }
        
        QCheckBox::indicator:unchecked {
            border: 2px solid #6c757d;
            background-color: white;
        }
        
        QCheckBox::indicator:checked {
            border: 2px solid #0d6efd;
            background-color: #0d6efd;
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDQuNUw0LjUgOEwxMSAxIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
        }
        """

    def format_isotope_label(self, element_key):
        """
        Convert element key format to isotope label format.
        
        Args:
            element_key: Element key string in format 'Element-mass' (e.g., 'Ag-106.9051')
            
        Returns:
            str: Formatted isotope label (e.g., '107Ag')
        """
        try:
            if '-' in element_key:
                element, mass_str = element_key.split('-')
                mass = float(mass_str)
                rounded_mass = int(round(mass))
                return f"{rounded_mass}{element}"
            return element_key
        except (ValueError, TypeError):
            return element_key

    def get_mass_number_for_sorting(self, formatted_label):
        """
        Extract mass number from formatted isotope label for sorting.
        
        Args:
            formatted_label: Formatted isotope label string (e.g., '107Ag')
            
        Returns:
            int: Mass number for sorting, or 999 if extraction fails
        """
        try:
            import re
            match = re.match(r'^(\d+)', formatted_label)
            if match:
                return int(match.group(1))
            return 999 
        except:
            return 999

    def find_matching_threshold_key(self, formatted_isotope, element_thresholds):
        """
        Find the threshold key that matches the formatted isotope.
        
        Args:
            formatted_isotope: Formatted isotope label string (e.g., '107Ag')
            element_thresholds: Dictionary of element threshold data
            
        Returns:
            str or None: Matching threshold key if found, None otherwise
        """
        try:
            import re
            match = re.match(r'^(\d+)([A-Za-z]+)', formatted_isotope)
            if match:
                mass_num, element = match.groups()
                for key in element_thresholds.keys():
                    if '-' in key:
                        key_element, key_mass = key.split('-')
                        if key_element == element:
                            key_mass_rounded = int(round(float(key_mass)))
                            if key_mass_rounded == int(mass_num):
                                return key
        except:
            pass
        return None

    def find_matching_limit_key(self, formatted_isotope, element_limits):
        """
        Find the limit key that matches the formatted isotope.
        
        Args:
            formatted_isotope: Formatted isotope label string (e.g., '107Ag')
            element_limits: Dictionary of element limit data
            
        Returns:
            str or None: Matching limit key if found, None otherwise
        """
        if formatted_isotope in element_limits:
            return formatted_isotope
            
        try:
            import re
            match = re.match(r'^(\d+)([A-Za-z]+)', formatted_isotope)
            if match:
                mass_num, element = match.groups()
                standardized_key = f"{element}-{float(mass_num):.4f}"
                if standardized_key in element_limits:
                    return standardized_key
                    
                for key in element_limits.keys():
                    if '-' in key:
                        key_element, key_mass = key.split('-')
                        if key_element == element:
                            key_mass_rounded = int(round(float(key_mass)))
                            if key_mass_rounded == int(mass_num):
                                return key
        except:
            pass
        return None

    def init_ui(self):
        """
        Initialize the user interface layout and components.
        
        Args:
            None
            
        Returns:
            None
        """
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)
        
        self.create_header(layout)
        
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        self.create_transport_rate_tab()
        
        self.create_ionic_calibration_tab()
        
        self.create_bottom_buttons(layout)
        
    def create_header(self, layout):
        """
        Create compact header with status summary.
        
        Args:
            layout: Parent layout to add the header to
            
        Returns:
            None
        """
        self.status_widget = self.create_status_summary()
        layout.addWidget(self.status_widget)
        
    def create_status_summary(self):
        """
        Create compact status summary widget in horizontal layout.
        
        Args:
            None
            
        Returns:
            QFrame: Status summary frame widget
        """
        status_frame = QFrame()
        status_frame.setStyleSheet("""
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.setSpacing(12)
        
        transport_count = len([m for m in ["Weight Method", "Particle Method", "Mass Method"] 
                              if m in self.calibration_results and 'transport_rate' in self.calibration_results[m]])
        
        ionic_count = len(self.calibration_results.get("Ionic Calibration", {}))
        
        high_quality_count = 0
        ionic_data = self.calibration_results.get("Ionic Calibration", {})
        for cal_data in ionic_data.values():
            for method_data in ['zero', 'simple', 'weighted', 'manual']:
                if method_data in cal_data and cal_data[method_data].get('r_squared', 0) > 0.99:
                    high_quality_count += 1
                    break
        
        stats = [
            ("Transport Methods", f"{transport_count}/3", "#0d6efd"),
            ("Ionic Calibrations", str(ionic_count), "#6f42c1"),
            ("R²>0.99", str(high_quality_count), "#198754"),
            ("Avg. Transport Rate", f"{self.average_transport_rate:.3f} μL/s", "#833e05")
        ]
        
        for i, (label, value, color) in enumerate(stats):
            stat_widget = QFrame()
            stat_widget.setStyleSheet(f"""
                QFrame {{
                    background-color: {color};
                    border-radius: 4px;
                    padding: 6px 8px;
                }}
                QLabel {{
                    color: white;
                    font-weight: 600;
                }}
            """)
            stat_layout_inner = QVBoxLayout(stat_widget)
            stat_layout_inner.setContentsMargins(4, 3, 4, 3)
            stat_layout_inner.setSpacing(1)
            
            value_label = QLabel(value)
            value_label.setStyleSheet("font-size: 14px; font-weight: 700;")
            label_label = QLabel(label)
            label_label.setStyleSheet("font-size: 14px; font-weight: 700;")
            
            stat_layout_inner.addWidget(value_label)
            stat_layout_inner.addWidget(label_label)
            
            status_layout.addWidget(stat_widget)
            
        return status_frame

    def create_transport_rate_tab(self):
        """
        Create enhanced transport rate calibration tab.
        
        Args:
            None
            
        Returns:
            None
        """
        transport_widget = QWidget()
        layout = QVBoxLayout(transport_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        desc_label = QLabel("""
        <b>Transport Rate Calibration</b><br>
        Configure which transport rate methods to use for mass calculations. 
        The average of selected methods will be used for conversions.
        """)
        desc_label.setStyleSheet("""
            background-color: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 10px;
            border-radius: 4px;
            color: #1565c0;
        """)
        layout.addWidget(desc_label)
        
        self.transport_rate_table = QTableWidget()
        self.setup_transport_rate_table()
        layout.addWidget(self.transport_rate_table)
        
        self.avg_rate_frame = QFrame()
        self.avg_rate_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 2px solid #0d6efd;
                border-radius: 6px;
                padding: 12px;
            }
        """)
        avg_layout = QHBoxLayout(self.avg_rate_frame)
        self.avg_rate_label = QLabel()
        self.avg_rate_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #0d6efd;
        """)
        avg_layout.addWidget(self.avg_rate_label)
        layout.addWidget(self.avg_rate_frame)
        
        self.tab_widget.addTab(transport_widget, "Transport Rate")
        
    def setup_transport_rate_table(self):
        """
        Setup transport rate table with enhanced features.
        
        Args:
            None
            
        Returns:
            None
        """
        self.transport_rate_table.setRowCount(3)
        self.transport_rate_table.setColumnCount(4)
        self.transport_rate_table.setHorizontalHeaderLabels([
            "Method", "Transport Rate (μL/s)", "Status", "Use in Calculation"
        ])
        
        header = self.transport_rate_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        self.transport_rate_table.setAlternatingRowColors(True)
        self.transport_rate_table.setSelectionBehavior(QTableWidget.SelectRows)
        
    def create_ionic_calibration_tab(self):
        """
        Create enhanced ionic calibration tab.
        
        Args:
            None
            
        Returns:
            None
        """
        ionic_widget = QWidget()
        layout = QVBoxLayout(ionic_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        controls_layout = QHBoxLayout()
        
        search_label = QLabel("Search:")
        search_label.setStyleSheet("font-weight: 600;")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter by isotope or element...")
        self.search_box.textChanged.connect(self.filter_ionic_table)
   
        self.quality_filter = QCheckBox("Show only (R² > 0.9)")
        self.quality_filter.stateChanged.connect(self.filter_ionic_table)
        
        controls_layout.addWidget(search_label)
        controls_layout.addWidget(self.search_box, 1)
        controls_layout.addSpacing(16)
        controls_layout.addWidget(self.quality_filter)
        
        layout.addLayout(controls_layout)
        
        self.ionic_calibration_table = QTableWidget()
        self.setup_ionic_table()
        layout.addWidget(self.ionic_calibration_table)
        
        legend_frame = self.create_quality_legend()
        layout.addWidget(legend_frame)
        
        self.tab_widget.addTab(ionic_widget, "Ionic Calibration")
        
    def setup_ionic_table(self):
        """
        Setup ionic calibration table with enhanced features.
        
        Args:
            None
            
        Returns:
            None
        """
        self.ionic_calibration_table.setColumnCount(15)
        headers = [
            "Isotope", "Method", "Slope\n(cps/conc)", "BEC", "LOD", "LOQ", 
            "R²", "Quality", "Density\n(g/cm³)", "Threshold\n(counts)", "LOD_MDL\n(counts)", 
            "MDL\n(fg)", "MQL\n(fg)", "SDL\n(nm)", "SQL\n(nm)", "Status"
        ]
        self.ionic_calibration_table.setHorizontalHeaderLabels(headers)
        
        self.ionic_calibration_table.setAlternatingRowColors(False)
        self.ionic_calibration_table.setSortingEnabled(True)
        self.ionic_calibration_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        tooltips = [
            "Isotope designation", "Calibration method used", 
            "Calibration slope", "Background equivalent concentration",
            "Limit of detection", "Limit of quantification", 
            "Coefficient of determination", "Quality assessment",
            "Particle density", "LOD in counts", 
            "Method detection limit", "Method quantification limit",
            "Size detection limit", "Size quantification limit", "Overall status"
        ]
        
        for i, tooltip in enumerate(tooltips):
            item = self.ionic_calibration_table.horizontalHeaderItem(i)
            if item:
                item.setToolTip(tooltip)
    
    def create_quality_legend(self):
        """
        Create legend for quality indicators.
        
        Args:
            None
            
        Returns:
            QFrame: Legend frame widget
        """
        legend_frame = QFrame()
        legend_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        legend_layout = QHBoxLayout(legend_frame)
        
        legend_label = QLabel("<b>Quality Legend:</b>")
        legend_layout.addWidget(legend_label)
        
        legend_items = [
            ("Manual Input", "#e6f3ff"),
            ("Good (R² > 0.99)", "#d1eddb"),
            ("Acceptable (R² > 0.95)", "#d4edda"),
            ("Maybe (R² > 0.8)", "#fff3cd"),
            ("Poor (R² ≤ 0.8)", "#f8d7da"),
            ("Not Calibrated", "#f1f3f4")
        ]
        
        for text, color in legend_items:
            legend_item = QLabel(text)
            legend_item.setStyleSheet(f"""
                background-color: {color};
                padding: 3px 6px;
                border-radius: 3px;
                font-size: 10px;
                margin-right: 6px;
            """)
            legend_layout.addWidget(legend_item)
            
        legend_layout.addStretch()
        return legend_frame
            
    def create_bottom_buttons(self, layout):
        """
        Create bottom button bar.
        
        Args:
            layout: Parent layout to add buttons to
            
        Returns:
            None
        """
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        export_button = QPushButton("Export Data")
        export_button.setObjectName("exportButton")
        export_button.clicked.connect(self.export_calibration_data)
        export_button.setToolTip("Export calibration data to CSV file")
        
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_data)
        refresh_button.setToolTip("Refresh all calibration data")
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(export_button)
        button_layout.addWidget(refresh_button)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)

    def populate_data(self):
        """
        Populate all tabs with data.
        
        Args:
            None
            
        Returns:
            None
        """
        self.populate_transport_rate_table()
        self.populate_ionic_calibration_table()
        self.update_average_transport_rate()
        
    def populate_transport_rate_table(self):
        """
        Populate transport rate table with enhanced status indicators.
        
        Args:
            None
            
        Returns:
            None
        """
        transport_methods = ["Weight Method", "Particle Method", "Mass Method"]
        
        for row, method in enumerate(transport_methods):
            method_item = QTableWidgetItem(method)
            method_item.setFlags(method_item.flags() & ~Qt.ItemIsEditable)
            self.transport_rate_table.setItem(row, 0, method_item)
            
            if method in self.calibration_results and 'transport_rate' in self.calibration_results[method]:
                rate = self.calibration_results[method]['transport_rate']
                rate_item = QTableWidgetItem(f"{rate:.4f}")
                status_item = QTableWidgetItem("Calibrated")
                status_item.setBackground(QBrush(QColor("#d1eddb")))
            else:
                rate_item = QTableWidgetItem("Not available")
                rate_item.setForeground(QBrush(QColor("#6c757d")))
                status_item = QTableWidgetItem("Not calibrated")
                status_item.setBackground(QBrush(QColor("#f8d7da")))
            
            rate_item.setFlags(rate_item.flags() & ~Qt.ItemIsEditable)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            
            self.transport_rate_table.setItem(row, 1, rate_item)
            self.transport_rate_table.setItem(row, 2, status_item)
            
            checkbox = QCheckBox()
            checkbox.setChecked(method in self.selected_methods)
            checkbox.stateChanged.connect(self.update_average_transport_rate)
            self.transport_rate_table.setCellWidget(row, 3, checkbox)

    def populate_ionic_calibration_table(self):
        """
        Populate ionic calibration table with comprehensive data.
        
        Args:
            None
            
        Returns:
            None
        """
        ionic_data = self.calibration_results.get("Ionic Calibration", {})
        parent = self.parent()
        
        if not ionic_data:
            self.ionic_calibration_table.setRowCount(1)
            no_data_item = QTableWidgetItem("No ionic calibration data available")
            no_data_item.setTextAlignment(Qt.AlignCenter)
            self.ionic_calibration_table.setItem(0, 0, no_data_item)
            self.ionic_calibration_table.setSpan(0, 0, 1, self.ionic_calibration_table.columnCount())
            return
        
        element_thresholds = {}
        element_limits = {}
        current_sample = None
        
        if parent and hasattr(parent, 'element_thresholds') and hasattr(parent, 'current_sample'):
            current_sample = parent.current_sample
            element_thresholds = parent.element_thresholds.get(current_sample, {})
            if hasattr(parent, 'element_limits') and current_sample in parent.element_limits:
                element_limits = parent.element_limits[current_sample]
        
        isotope_mapping = {}
        all_isotopes = []
        
        for key in ionic_data.keys():
            if '-' in key:
                formatted_label = self.format_isotope_label(key)
                isotope_mapping[key] = formatted_label
                all_isotopes.append(formatted_label)
        
        all_isotopes.sort(key=self.get_mass_number_for_sorting)
        
        self.ionic_calibration_table.setRowCount(len(all_isotopes))
        self.ionic_calibration_table.setSortingEnabled(False)
        
        method_map = {
            'Force through zero': 'zero',
            'Simple linear': 'simple', 
            'Weighted': 'weighted',
            'Manual': 'manual'
        }
        
        for row, formatted_isotope in enumerate(all_isotopes):
            ionic_key = next((k for k, v in isotope_mapping.items() if v == formatted_isotope), None)
            
            cal_data = ionic_data.get(ionic_key, {}) if ionic_key else {}
            preferred_method = self.method_preferences.get(ionic_key, "Force through zero")
            method_key = method_map.get(preferred_method, 'zero')
            
            if preferred_method == 'Manual' and 'manual' not in cal_data:
                available_methods = ['zero', 'simple', 'weighted']
                best_r2 = 0
                best_method = 'zero'
                for method in available_methods:
                    if method in cal_data:
                        r2 = cal_data[method].get('r_squared', 0)
                        if r2 > best_r2:
                            best_r2 = r2
                            best_method = method
                method_key = best_method
                preferred_method = {
                    'zero': 'Force through zero',
                    'simple': 'Simple linear', 
                    'weighted': 'Weighted'
                }.get(best_method, 'Force through zero')
            
            method_data = cal_data.get(method_key, {})
            
            r_squared = method_data.get('r_squared', 0)
            
            items = [
                self.create_item(formatted_isotope, editable=False),
                self.create_item(preferred_method, editable=False),
                self.create_scientific_item(method_data.get('slope')),
                self.create_scientific_item(method_data.get('bec')),
                self.create_scientific_item(method_data.get('lod')),
                self.create_scientific_item(method_data.get('loq')),
                self.create_decimal_item(r_squared, 4),
                self.create_quality_item(r_squared),
                self.create_decimal_item(cal_data.get('density'), 4),
            ]
            
            threshold_key = self.find_matching_threshold_key(formatted_isotope, element_thresholds)
            threshold_data = element_thresholds.get(threshold_key, {}) if threshold_key else {}
            items.append(self.create_decimal_item(threshold_data.get('LOD_counts'), 2))
            items.append(self.create_decimal_item(threshold_data.get('LOD_MDL'), 2)) 
                        
            limit_key = self.find_matching_limit_key(formatted_isotope, element_limits)
            limit_data = element_limits.get(limit_key, {}) if limit_key else {}
            items.extend([
                self.create_scientific_item(limit_data.get('MDL')),
                self.create_scientific_item(limit_data.get('MQL')),
                self.create_decimal_item(limit_data.get('SDL'), 1),
                self.create_decimal_item(limit_data.get('SQL'), 1),
            ])
            
            items.append(self.create_status_item(r_squared, method_data, limit_data))
            
            for col, item in enumerate(items):
                self.ionic_calibration_table.setItem(row, col, item)
            
            if r_squared > 0:
                if preferred_method == 'Manual':
                    color = QColor("#e6f3ff")
                elif r_squared >= 0.99:
                    color = QColor("#d1eddb")  
                elif r_squared >= 0.95:
                    color = QColor("#d4edda")  
                elif r_squared >= 0.8:
                    color = QColor("#fff3cd") 
                else:
                    color = QColor("#f8d7da") 
                    
                for col in range(2, len(items)):
                    item = self.ionic_calibration_table.item(row, col)
                    if item:
                        item.setBackground(QBrush(color))
            elif r_squared == 0:
                color = QColor("#f1f3f4")
                for col in range(2, len(items)):
                    item = self.ionic_calibration_table.item(row, col)
                    if item:
                        item.setBackground(QBrush(color))
        
        self.ionic_calibration_table.setSortingEnabled(True)
        self.ionic_calibration_table.resizeColumnsToContents()

    def create_item(self, value, editable=True):
        """
        Create table item with proper formatting.
        
        Args:
            value: Value to display in the item
            editable: Whether the item should be editable
            
        Returns:
            QTableWidgetItem: Formatted table widget item
        """
        if value is None or (isinstance(value, str) and not value):
            item = QTableWidgetItem("—")
            item.setForeground(QBrush(QColor("#6c757d")))
        else:
            item = QTableWidgetItem(str(value))
        
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item
        
    def create_scientific_item(self, value):
        """
        Create item with scientific notation.
        
        Args:
            value: Numeric value to format in scientific notation
            
        Returns:
            QTableWidgetItem: Item formatted in scientific notation
        """
        if value is None or value == 'N/A':
            return self.create_item("—", False)
        try:
            return self.create_item(f"{float(value):.2e}", False)
        except (ValueError, TypeError):
            return self.create_item("—", False)
            
    def create_decimal_item(self, value, decimals=2):
        """
        Create item with decimal formatting.
        
        Args:
            value: Numeric value to format
            decimals: Number of decimal places to display
            
        Returns:
            QTableWidgetItem: Item formatted with specified decimal places
        """
        if value is None or value == 'N/A':
            return self.create_item("—", False)
        try:
            return self.create_item(f"{float(value):.{decimals}f}", False)
        except (ValueError, TypeError):
            return self.create_item("—", False)
            
    def create_quality_item(self, r_squared):
        """
        Create quality assessment item based on R-squared value.
        
        Args:
            r_squared: R-squared coefficient value
            
        Returns:
            QTableWidgetItem: Quality assessment item
        """
        if r_squared >= 0.99:
            quality = "Good"
        elif r_squared >= 0.95:
            quality = "Acceptable"
        elif r_squared >= 0.8:
            quality = "Fair"
        elif r_squared > 0:
            quality = "Poor"
        else:
            quality = "—"
            
        return self.create_item(quality, False)
        
    def create_status_item(self, r_squared, method_data, limit_data):
        """
        Create overall status item.
        
        Args:
            r_squared: R-squared coefficient value
            method_data: Dictionary of method calibration data
            limit_data: Dictionary of limit data
            
        Returns:
            QTableWidgetItem: Overall status item
        """
        if not method_data:
            status = "Not calibrated"
        elif r_squared >= 0.9 and limit_data:
            status = "Complete"
        elif r_squared >= 0.9:
            status = "No limits"
        else:
            status = "Poor quality"
            
        return self.create_item(status, False)

    def filter_ionic_table(self):
        """
        Filter ionic calibration table based on search and quality.
        
        Args:
            None
            
        Returns:
            None
        """
        search_text = self.search_box.text().lower()
        quality_filter = self.quality_filter.isChecked()
        
        for row in range(self.ionic_calibration_table.rowCount()):
            show_row = True
            
            if search_text:
                isotope_item = self.ionic_calibration_table.item(row, 0)
                if isotope_item:
                    isotope_text = isotope_item.text().lower()
                    show_row = search_text in isotope_text

            if show_row and quality_filter:
                r_squared_item = self.ionic_calibration_table.item(row, 6)
                if r_squared_item and r_squared_item.text() != "—":
                    try:
                        r_squared = float(r_squared_item.text())
                        show_row = r_squared > 0.9
                    except ValueError:
                        show_row = False
                else:
                    show_row = False
            
            self.ionic_calibration_table.setRowHidden(row, not show_row)

    def update_average_transport_rate(self):
        """
        Update average transport rate calculation.
        
        Args:
            None
            
        Returns:
            None
        """
        self.selected_methods = []
        total_rate = 0
        count = 0
        
        for row in range(self.transport_rate_table.rowCount()):
            method = self.transport_rate_table.item(row, 0).text()
            checkbox = self.transport_rate_table.cellWidget(row, 3)
            if checkbox and checkbox.isChecked():
                self.selected_methods.append(method)
                if method in self.calibration_results and 'transport_rate' in self.calibration_results[method]:
                    total_rate += self.calibration_results[method]['transport_rate']
                    count += 1
        
        self.average_transport_rate = total_rate / count if count > 0 else 0
        
        if count > 0:
            self.avg_rate_label.setText(
                f"Average Transport Rate: {self.average_transport_rate:.4f} μL/s "
                f"(from {count} selected method{'s' if count > 1 else ''})"
            )
            self.avg_rate_frame.setStyleSheet(self.avg_rate_frame.styleSheet().replace("#dc3545", "#0d6efd"))
        else:
            self.avg_rate_label.setText("No transport rate methods selected")
            self.avg_rate_frame.setStyleSheet(self.avg_rate_frame.styleSheet().replace("#0d6efd", "#dc3545"))
        
        self.update_status_summary()
        
        parent = self.parent()
        if parent:
            parent.average_transport_rate = self.average_transport_rate
            parent.selected_transport_rate_methods = self.selected_methods
            if hasattr(parent, 'current_sample') and parent.current_sample:
                parent.calculate_mass_limits()

    def update_status_summary(self):
        """
        Update the status summary statistics.
        
        Args:
            None
            
        Returns:
            None
        """
        transport_count = len([m for m in ["Weight Method", "Particle Method", "Mass Method"] 
                            if m in self.calibration_results and 'transport_rate' in self.calibration_results[m]])
        
        ionic_count = len(self.calibration_results.get("Ionic Calibration", {}))
        
        high_quality_count = 0
        ionic_data = self.calibration_results.get("Ionic Calibration", {})
        for cal_data in ionic_data.values():
            for method_data in ['zero', 'simple', 'weighted', 'manual']:
                if method_data in cal_data:
                    r_squared = cal_data[method_data].get('r_squared', 0)
                    if method_data == 'manual' or r_squared > 0.99:
                        high_quality_count += 1
                        break
        
        status_layout = self.status_widget.layout()
        for i in range(status_layout.count()):
            stat_widget = status_layout.itemAt(i).widget()
            if stat_widget:
                stat_inner_layout = stat_widget.layout()
                if stat_inner_layout and stat_inner_layout.count() >= 2:
                    value_label = stat_inner_layout.itemAt(0).widget()
                    label_label = stat_inner_layout.itemAt(1).widget()
                    
                    if label_label and value_label:
                        label_text = label_label.text()
                        if label_text == "Transport Methods":
                            value_label.setText(f"{transport_count}/3")
                        elif label_text == "Ionic Calibrations":
                            value_label.setText(str(ionic_count))
                        elif label_text == "R²>0.99":
                            value_label.setText(str(high_quality_count))
                        elif label_text == "Avg. Transport Rate":
                            value_label.setText(f"{self.average_transport_rate:.3f} μL/s")

    def export_calibration_data(self):
        """
        Export calibration data to CSV file.
        
        Args:
            None
            
        Returns:
            None
        """
        try:
            from PySide6.QtWidgets import QFileDialog
            import csv
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Calibration Data", 
                "calibration_data.csv", "CSV Files (*.csv)"
            )
            
            if not file_path:
                return
                
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                writer.writerow(["TRANSPORT RATE CALIBRATION"])
                writer.writerow(["Method", "Rate (μL/s)", "Selected"])
                
                for row in range(self.transport_rate_table.rowCount()):
                    method = self.transport_rate_table.item(row, 0).text()
                    rate = self.transport_rate_table.item(row, 1).text()
                    checkbox = self.transport_rate_table.cellWidget(row, 3)
                    selected = "Yes" if checkbox and checkbox.isChecked() else "No"
                    writer.writerow([method, rate, selected])
                
                writer.writerow([])
                writer.writerow([f"Average Rate: {self.average_transport_rate:.4f} μL/s"])
                writer.writerow([])
                
                writer.writerow(["IONIC CALIBRATION"])
                
                headers = []
                for col in range(self.ionic_calibration_table.columnCount()):
                    header_item = self.ionic_calibration_table.horizontalHeaderItem(col)
                    headers.append(header_item.text() if header_item else f"Column_{col}")
                writer.writerow(headers)
                
                for row in range(self.ionic_calibration_table.rowCount()):
                    if not self.ionic_calibration_table.isRowHidden(row):
                        row_data = []
                        for col in range(self.ionic_calibration_table.columnCount()):
                            item = self.ionic_calibration_table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
            
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Export Complete", 
                                  f"Calibration data exported successfully to:\n{file_path}")
                                  
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Export Error", f"Error exporting data: {str(e)}")

    def refresh_data(self):
        """
        Refresh all calibration data without showing notification.
        
        Args:
            None
            
        Returns:
            None
        """
        self.populate_data()