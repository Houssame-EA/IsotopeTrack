from PySide6.QtWidgets import (
    QPushButton, QVBoxLayout, QLabel, QTableWidget, QDialog, QCheckBox,
    QTableWidgetItem, QTabWidget, QHBoxLayout, QLineEdit, QGroupBox,
    QHeaderView, QFrame, QWidget
)
from PySide6.QtGui import QColor, QBrush
from PySide6.QtCore import Qt
from theme import theme


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
        self.resize(1000, 680)

        self.calibration_results = calibration_results
        self.selected_methods = selected_methods
        self.method_preferences = method_preferences or {}
        self.average_transport_rate = 0

        self.init_ui()
        self.populate_data()

        theme.themeChanged.connect(self.apply_theme)
        self.apply_theme()

    def apply_theme(self):
        """Apply the currently active theme palette to this dialog."""
        self.setStyleSheet(self.get_modern_stylesheet())
        self._repaint_rows_for_theme()
        self._refresh_summary_line()
        self._refresh_avg_rate_style()

    def closeEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        try:
            theme.themeChanged.disconnect(self.apply_theme)
        except (TypeError, RuntimeError):
            pass
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    # Styling
    # ------------------------------------------------------------------ #

    def get_modern_stylesheet(self):
        """Stylesheet parameterized on the active theme palette.

        Returns:
            str: CSS stylesheet string
        """
        p = theme.palette
        return f"""
        QDialog {{
            background-color: {p.bg_primary};
            color: {p.text_primary};
            font-family: 'Segoe UI', Arial, sans-serif;
        }}

        QLabel {{
            color: {p.text_primary};
            background-color: transparent;
        }}

        QTabWidget::pane {{
            border: 1px solid {p.border};
            background-color: {p.bg_secondary};
            border-radius: 8px;
        }}

        QTabWidget::tab-bar {{
            alignment: left;
        }}

        QTabBar::tab {{
            background-color: {p.bg_tertiary};
            color: {p.text_secondary};
            border: 1px solid {p.border};
            padding: 10px 16px;
            margin-right: 2px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            font-weight: 500;
        }}

        QTabBar::tab:selected {{
            background-color: {p.bg_secondary};
            border-bottom: 1px solid {p.bg_secondary};
            color: {p.accent};
            font-weight: 600;
        }}

        QTabBar::tab:hover:!selected {{
            background-color: {p.bg_hover};
        }}

        QTableWidget {{
            gridline-color: {p.border};
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 6px;
            font-size: 12px;
            selection-background-color: {p.accent};
            selection-color: {p.text_inverse};
            alternate-background-color: {p.bg_tertiary};
        }}

        QTableWidget::item {{
            padding: 8px;
            border-bottom: 1px solid {p.border_subtle};
            color: {p.text_primary};
        }}

        QTableWidget::item:selected {{
            background-color: {p.accent};
            color: {p.text_inverse};
        }}

        QHeaderView::section {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            padding: 10px 6px;
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
            font-weight: 600;
            font-size: 11px;
        }}

        /* The QHeaderView widget itself — distinct from ::section.
           Without this, the empty area below the last row number stays
           white (macOS default) in dark mode. */
        QHeaderView {{
            background-color: {p.bg_tertiary};
            border: none;
        }}

        /* Top-left square where row and column headers meet. */
        QTableCornerButton::section {{
            background-color: {p.bg_tertiary};
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
        }}

        QGroupBox {{
            font-weight: 600;
            color: {p.text_primary};
            border: 2px solid {p.border};
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 12px;
            background-color: {p.bg_secondary};
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            padding: 0 10px;
            color: {p.text_primary};
        }}

        QPushButton {{
            background-color: {p.accent};
            color: {p.text_inverse};
            border: none;
            border-radius: 6px;
            padding: 8px 12px;
            font-weight: 500;
            font-size: 13px;
        }}

        QPushButton:hover {{
            background-color: {p.accent_hover};
        }}

        QPushButton:pressed {{
            background-color: {p.accent_pressed};
        }}

        QPushButton#exportButton {{
            background-color: {p.success};
        }}

        QPushButton#exportButton:hover {{
            background-color: {p.accent_hover};
        }}

        QLineEdit {{
            color: {p.text_primary};
            background-color: {p.bg_tertiary};
            border: 2px solid {p.border};
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 13px;
        }}

        QLineEdit:focus {{
            border-color: {p.accent};
            outline: none;
        }}

        QTextEdit {{
            color: {p.text_primary};
            background-color: {p.bg_secondary};
            border: 1px solid {p.border};
            border-radius: 6px;
        }}

        QCheckBox {{
            color: {p.text_primary};
            font-size: 13px;
            spacing: 6px;
        }}

        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 3px;
        }}

        QCheckBox::indicator:unchecked {{
            border: 2px solid {p.border};
            background-color: {p.bg_tertiary};
        }}

        QCheckBox::indicator:checked {{
            border: 2px solid {p.accent};
            background-color: {p.accent};
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDQuNUw0LjUgOEwxMSAxIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
        }}
        """

    # ------------------------------------------------------------------ #
    # Theme-aware color helpers
    # ------------------------------------------------------------------ #

    def _quality_row_color(self, r_squared, method_name):
        """Pick a row tint color for the ionic table based on R² + method.

        Maps the six legacy quality buckets to the 4-tier palette + accent_soft.
        Light mode keeps pastel-like colors; dark mode gets desaturated
        tints automatically because they come from the palette.
        Args:
            r_squared (Any): The r squared.
            method_name (Any): The method name.
        Returns:
            object: Result of the operation.
        """
        p = theme.palette
        if r_squared <= 0:
            return QColor(p.bg_tertiary)
        if method_name == 'Manual':
            return QColor(p.accent_soft)
        if r_squared >= 0.95:
            return QColor(p.tier_low)
        if r_squared >= 0.8:
            return QColor(p.tier_medium)
        return QColor(p.tier_critical)

    def _tier_text_color(self):
        """Text color to use on top of tier-colored row backgrounds.
        Returns:
            object: Result of the operation.
        """
        return QColor(theme.palette.tier_text)

    def _muted_color(self):
        """Color for 'Not available' / em-dash placeholder text.
        Returns:
            object: Result of the operation.
        """
        return QColor(theme.palette.text_muted)

    # ------------------------------------------------------------------ #
    # isotope key helpers (unchanged logic)
    # ------------------------------------------------------------------ #

    def format_isotope_label(self, element_key):
        """
        Args:
            element_key (Any): The element key.
        Returns:
            object: Result of the operation.
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
        Args:
            formatted_label (Any): The formatted label.
        Returns:
            int: Result of the operation.
        """
        try:
            import re
            match = re.match(r'^(\d+)', formatted_label)
            if match:
                return int(match.group(1))
            return 999
        except Exception:
            return 999

    def find_matching_threshold_key(self, formatted_isotope, element_thresholds):
        """
        Args:
            formatted_isotope (Any): The formatted isotope.
            element_thresholds (Any): The element thresholds.
        Returns:
            None
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
        except Exception:
            pass
        return None

    def find_matching_limit_key(self, formatted_isotope, element_limits):
        """
        Args:
            formatted_isotope (Any): The formatted isotope.
            element_limits (Any): The element limits.
        Returns:
            None
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
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------ #
    # UI layout
    # ------------------------------------------------------------------ #

    def init_ui(self):
        """Initialize the user interface layout and components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-size: 13px; font-weight: 500;")
        layout.addWidget(self.summary_label)

        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget, 1)

        self.create_transport_rate_tab()
        self.create_ionic_calibration_tab()

        self.create_bottom_buttons(layout)

    def create_transport_rate_tab(self):
        """Create transport rate calibration tab."""
        transport_widget = QWidget()
        layout = QVBoxLayout(transport_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.transport_desc_label = QLabel(
            "Select which transport rate methods to use for mass calculations. "
            "The average of selected methods is used for conversions."
        )
        self.transport_desc_label.setWordWrap(True)
        self.transport_desc_label.setStyleSheet(
            f"color: {theme.palette.text_secondary}; font-size: 12px; padding: 2px 0;"
        )
        layout.addWidget(self.transport_desc_label)

        self.transport_rate_table = QTableWidget()
        self.setup_transport_rate_table()
        layout.addWidget(self.transport_rate_table, 1)

        self.avg_rate_label = QLabel()
        self.avg_rate_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {theme.palette.accent}; "
            f"padding: 6px 2px;"
        )
        layout.addWidget(self.avg_rate_label)

        self.tab_widget.addTab(transport_widget, "Transport Rate")

    def setup_transport_rate_table(self):
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
        """Create ionic calibration tab."""
        ionic_widget = QWidget()
        layout = QVBoxLayout(ionic_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        controls_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setStyleSheet("font-weight: 600;")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter by isotope or element…")
        self.search_box.setClearButtonEnabled(True)
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
        layout.addWidget(self.ionic_calibration_table, 1)


        self.tab_widget.addTab(ionic_widget, "Ionic Calibration")

    def setup_ionic_table(self):
        self.ionic_calibration_table.setColumnCount(16)
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

    def create_bottom_buttons(self, layout):
        """
        Args:
            layout (Any): Target layout.
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

    # ------------------------------------------------------------------ #
    # Data population
    # ------------------------------------------------------------------ #

    def populate_data(self):
        self.populate_transport_rate_table()
        self.populate_ionic_calibration_table()
        self.update_average_transport_rate()
        self._refresh_summary_line()

    def populate_transport_rate_table(self):
        transport_methods = ["Weight Method", "Particle Method", "Mass Method"]
        p = theme.palette

        for row, method in enumerate(transport_methods):
            method_item = QTableWidgetItem(method)
            method_item.setFlags(method_item.flags() & ~Qt.ItemIsEditable)
            self.transport_rate_table.setItem(row, 0, method_item)

            is_calibrated = (
                method in self.calibration_results
                and 'transport_rate' in self.calibration_results[method]
            )

            if is_calibrated:
                rate = self.calibration_results[method]['transport_rate']
                rate_item = QTableWidgetItem(f"{rate:.4f}")
                status_item = QTableWidgetItem("Calibrated")
                status_item.setBackground(QBrush(QColor(p.tier_low)))
                status_item.setForeground(QBrush(self._tier_text_color()))
            else:
                rate_item = QTableWidgetItem("Not available")
                rate_item.setForeground(QBrush(self._muted_color()))
                status_item = QTableWidgetItem("Not calibrated")
                status_item.setBackground(QBrush(QColor(p.tier_critical)))
                status_item.setForeground(QBrush(self._tier_text_color()))

            rate_item.setFlags(rate_item.flags() & ~Qt.ItemIsEditable)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)

            self.transport_rate_table.setItem(row, 1, rate_item)
            self.transport_rate_table.setItem(row, 2, status_item)

            checkbox = QCheckBox()
            checkbox.setChecked(method in self.selected_methods)
            checkbox.stateChanged.connect(self.update_average_transport_rate)
            self.transport_rate_table.setCellWidget(row, 3, checkbox)

    def populate_ionic_calibration_table(self):
        ionic_data = self.calibration_results.get("Ionic Calibration", {})
        parent = self.parent()

        if not ionic_data:
            self.ionic_calibration_table.setRowCount(1)
            no_data_item = QTableWidgetItem("No ionic calibration data available")
            no_data_item.setTextAlignment(Qt.AlignCenter)
            self.ionic_calibration_table.setItem(0, 0, no_data_item)
            self.ionic_calibration_table.setSpan(
                0, 0, 1, self.ionic_calibration_table.columnCount()
            )
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

        self._row_tint_meta = []

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

            self._row_tint_meta.append((row, r_squared, preferred_method, len(items)))

        self._apply_ionic_row_tints()
        self.ionic_calibration_table.setSortingEnabled(True)
        self.ionic_calibration_table.resizeColumnsToContents()

    def _apply_ionic_row_tints(self):
        """Apply theme-aware row tints to the ionic calibration table."""
        if not hasattr(self, '_row_tint_meta'):
            return
        text_color = self._tier_text_color()
        for row, r_squared, preferred_method, n_items in self._row_tint_meta:
            color = self._quality_row_color(r_squared, preferred_method)
            for col in range(2, n_items):
                item = self.ionic_calibration_table.item(row, col)
                if item:
                    item.setBackground(QBrush(color))
                    if r_squared > 0:
                        item.setForeground(QBrush(text_color))

    def _repaint_rows_for_theme(self):
        """Re-apply row tints after a theme change."""
        self._apply_ionic_row_tints()
        if hasattr(self, 'transport_rate_table'):
            p = theme.palette
            text_color = self._tier_text_color()
            for row in range(self.transport_rate_table.rowCount()):
                status_item = self.transport_rate_table.item(row, 2)
                if not status_item:
                    continue
                if status_item.text() == "Calibrated":
                    status_item.setBackground(QBrush(QColor(p.tier_low)))
                    status_item.setForeground(QBrush(text_color))
                elif status_item.text() == "Not calibrated":
                    status_item.setBackground(QBrush(QColor(p.tier_critical)))
                    status_item.setForeground(QBrush(text_color))
                rate_item = self.transport_rate_table.item(row, 1)
                if rate_item and rate_item.text() == "Not available":
                    rate_item.setForeground(QBrush(self._muted_color()))
        if hasattr(self, 'transport_desc_label'):
            self.transport_desc_label.setStyleSheet(
                f"color: {theme.palette.text_secondary}; font-size: 12px; padding: 2px 0;"
            )

    # ------------------------------------------------------------------ #
    # Item factories
    # ------------------------------------------------------------------ #

    def create_item(self, value, editable=True):
        """
        Args:
            value (Any): Value to set or process.
            editable (Any): The editable.
        Returns:
            object: Result of the operation.
        """
        if value is None or (isinstance(value, str) and not value):
            item = QTableWidgetItem("—")
            item.setForeground(QBrush(self._muted_color()))
        else:
            item = QTableWidgetItem(str(value))
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def create_scientific_item(self, value):
        """
        Args:
            value (Any): Value to set or process.
        Returns:
            object: Result of the operation.
        """
        if value is None or value == 'N/A':
            return self.create_item("—", False)
        try:
            return self.create_item(f"{float(value):.2e}", False)
        except (ValueError, TypeError):
            return self.create_item("—", False)

    def create_decimal_item(self, value, decimals=2):
        """
        Args:
            value (Any): Value to set or process.
            decimals (Any): The decimals.
        Returns:
            object: Result of the operation.
        """
        if value is None or value == 'N/A':
            return self.create_item("—", False)
        try:
            return self.create_item(f"{float(value):.{decimals}f}", False)
        except (ValueError, TypeError):
            return self.create_item("—", False)

    def create_quality_item(self, r_squared):
        """
        Args:
            r_squared (Any): The r squared.
        Returns:
            object: Result of the operation.
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
        Args:
            r_squared (Any): The r squared.
            method_data (Any): The method data.
            limit_data (Any): The limit data.
        Returns:
            object: Result of the operation.
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

    # ------------------------------------------------------------------ #
    # Filtering & updates
    # ------------------------------------------------------------------ #

    def filter_ionic_table(self):
        search_text = self.search_box.text().lower()
        quality_filter = self.quality_filter.isChecked()

        for row in range(self.ionic_calibration_table.rowCount()):
            show_row = True

            if search_text:
                isotope_item = self.ionic_calibration_table.item(row, 0)
                if isotope_item:
                    show_row = search_text in isotope_item.text().lower()

            if show_row and quality_filter:
                r_squared_item = self.ionic_calibration_table.item(row, 6)
                if r_squared_item and r_squared_item.text() != "—":
                    try:
                        show_row = float(r_squared_item.text()) > 0.9
                    except ValueError:
                        show_row = False
                else:
                    show_row = False

            self.ionic_calibration_table.setRowHidden(row, not show_row)

    def update_average_transport_rate(self):
        self.selected_methods = []
        total_rate = 0
        count = 0

        for row in range(self.transport_rate_table.rowCount()):
            method = self.transport_rate_table.item(row, 0).text()
            checkbox = self.transport_rate_table.cellWidget(row, 3)
            if checkbox and checkbox.isChecked():
                self.selected_methods.append(method)
                if (
                    method in self.calibration_results
                    and 'transport_rate' in self.calibration_results[method]
                ):
                    total_rate += self.calibration_results[method]['transport_rate']
                    count += 1

        self.average_transport_rate = total_rate / count if count > 0 else 0
        self._refresh_avg_rate_style()
        self._refresh_summary_line()

        parent = self.parent()
        if parent:
            parent.average_transport_rate = self.average_transport_rate
            parent.selected_transport_rate_methods = self.selected_methods
            if hasattr(parent, 'current_sample') and parent.current_sample:
                parent.calculate_mass_limits()

    def _refresh_avg_rate_style(self):
        """Update the inline avg-rate text + its color, from the current palette."""
        if not hasattr(self, 'avg_rate_label'):
            return
        p = theme.palette
        count = len(self.selected_methods)
        if count > 0:
            self.avg_rate_label.setText(
                f"Average transport rate: {self.average_transport_rate:.4f} μL/s "
                f"(from {count} selected method{'s' if count > 1 else ''})"
            )
            color = p.accent
        else:
            self.avg_rate_label.setText("No transport rate methods selected")
            color = p.danger
        self.avg_rate_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {color}; padding: 6px 2px;"
        )

    def _refresh_summary_line(self):
        """Compact text summary shown at the top of the dialog."""
        if not hasattr(self, 'summary_label'):
            return

        transport_count = len([
            m for m in ["Weight Method", "Particle Method", "Mass Method"]
            if m in self.calibration_results
            and 'transport_rate' in self.calibration_results[m]
        ])
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

        p = theme.palette
        parts = [
            f"<span style='color:{p.text_secondary};'>Transport:</span> "
            f"<b style='color:{p.text_primary};'>{transport_count}/3 calibrated</b>",
            f"<span style='color:{p.text_secondary};'>Ionic:</span> "
            f"<b style='color:{p.text_primary};'>{ionic_count} isotope"
            f"{'s' if ionic_count != 1 else ''}</b>",
            f"<span style='color:{p.text_secondary};'>R² &gt; 0.99:</span> "
            f"<b style='color:{p.text_primary};'>{high_quality_count}</b>",
            f"<span style='color:{p.text_secondary};'>Avg rate:</span> "
            f"<b style='color:{p.accent};'>{self.average_transport_rate:.3f} μL/s</b>",
        ]
        self.summary_label.setText("  ·  ".join(parts))

    # ------------------------------------------------------------------ #
    # Export / refresh
    # ------------------------------------------------------------------ #

    def export_calibration_data(self):
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
            QMessageBox.information(
                self, "Export Complete",
                f"Calibration data exported successfully to:\n{file_path}"
            )
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Export Error", f"Error exporting data: {str(e)}")

    def refresh_data(self):
        """Refresh all calibration data without showing notification."""
        self.populate_data()