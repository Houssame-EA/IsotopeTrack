from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QPushButton, QVBoxLayout, QLineEdit, QScrollArea,
                              QWidget, QLabel, QHBoxLayout, QComboBox, QDialogButtonBox,
                              QDialog, QListWidget, QCheckBox, QDoubleSpinBox, QListWidgetItem,
                              QGroupBox, QGridLayout, QSpinBox, QToolButton)
from theme import theme, dialog_qss


class CollapsibleSection(QWidget):
    """A lightweight collapsible container with a toggle header.

    Used to hide 'Advanced' parameters that most users don't need to touch,
    keeping the default dialog view short and focused.
    """
    def __init__(self, title: str, parent=None):
        """
        Args:
            title (str): Window or dialog title.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self._toggle = QToolButton(text=title, checkable=True, checked=False)
        self._toggle.setStyleSheet("QToolButton { border: none; font-weight: 600; }")
        self._toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(Qt.RightArrow)
        self._toggle.clicked.connect(self._on_toggled)

        self._content = QWidget()
        self._content.setVisible(False)
        self._content_layout = QGridLayout(self._content)
        self._content_layout.setContentsMargins(12, 6, 0, 0)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)
        outer.addWidget(self._toggle)
        outer.addWidget(self._content)

    def _on_toggled(self, checked: bool):
        """
        Args:
            checked (bool): Whether the item is checked.
        """
        self._toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self._content.setVisible(checked)

    def content_layout(self) -> QGridLayout:
        """
        Returns:
            QGridLayout: Result of the operation.
        """
        return self._content_layout


class BatchElementParametersDialog(QDialog):
    def __init__(self, parent=None, elements=None, current_parameters=None, all_samples=None):
        """
        Initialize the batch element parameters dialog.

        Args:
            parent: Parent widget for the dialog
            elements: Dictionary mapping element keys to display labels
            current_parameters: Dictionary of current parameter settings
            all_samples: List of all available sample names

        Returns:
            None
        """
        super().__init__(parent)
        self.setWindowTitle("Batch Edit Element Parameters")
        self.resize(720, 620)
        self.elements = elements or {}
        self.current_parameters = current_parameters or {}
        self.selected_elements = set()
        self.all_samples = all_samples or []
        self.selected_samples = set()

        self.setup_ui()

        theme.themeChanged.connect(self.apply_theme)
        self.apply_theme()

    def apply_theme(self):
        """Apply the currently active theme palette to this dialog."""
        self.setStyleSheet(dialog_qss(theme.palette))
        if hasattr(self, 'manual_threshold'):
            self.toggle_manual_threshold(self.method_combo.currentText())
        if hasattr(self, 'window_size'):
            self.toggle_window_size(self.use_window_size.checkState())

    def closeEvent(self, event):
        """Disconnect theme signal so we don't leak slots on closed dialogs.
        Args:
            event (Any): Qt event object.
        """
        try:
            theme.themeChanged.disconnect(self.apply_theme)
        except (TypeError, RuntimeError):
            pass
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #

    def setup_ui(self):
        """Build the dialog layout.

        Structure (top → bottom):
          - Selection row: Samples list | Elements list  (side by side)
          - Parameter Settings group (essentials always visible)
          - Advanced (collapsible) group
          - OK / Cancel
        """
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        selection_row = QHBoxLayout()
        selection_row.setSpacing(10)
        selection_row.addWidget(self._build_samples_group(), 1)
        selection_row.addWidget(self._build_elements_group(), 1)
        main_layout.addLayout(selection_row, 1)

        main_layout.addWidget(self._build_params_group())

        main_layout.addWidget(self._build_advanced_section())

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.initialize_controls_from_parameters()

    def _build_samples_group(self) -> QGroupBox:
        """
        Returns:
            QGroupBox: Result of the operation.
        """
        self.samples_group = QGroupBox("Samples")
        layout = QVBoxLayout(self.samples_group)
        layout.setSpacing(6)

        btn_row = QHBoxLayout()
        select_all = QPushButton("Select all")
        select_all.clicked.connect(self.select_all_samples)
        deselect_all = QPushButton("Clear")
        deselect_all.clicked.connect(self.deselect_all_samples)
        btn_row.addWidget(select_all)
        btn_row.addWidget(deselect_all)
        layout.addLayout(btn_row)

        self.sample_list = QListWidget()
        self.sample_list.setSelectionMode(QListWidget.MultiSelection)
        for sample_name in self.all_samples:
            self.sample_list.addItem(QListWidgetItem(sample_name))
        self.sample_list.itemSelectionChanged.connect(self._update_sample_count)
        layout.addWidget(self.sample_list, 1)

        self._update_sample_count()
        return self.samples_group

    def _build_elements_group(self) -> QGroupBox:
        """
        Returns:
            QGroupBox: Result of the operation.
        """
        self.elements_group = QGroupBox("Elements")
        layout = QVBoxLayout(self.elements_group)
        layout.setSpacing(6)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter elements…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self.filter_elements)
        layout.addWidget(self.search_box)

        btn_row = QHBoxLayout()
        select_all = QPushButton("Select all")
        select_all.clicked.connect(self.select_all)
        deselect_all = QPushButton("Clear")
        deselect_all.clicked.connect(self.deselect_all)
        btn_row.addWidget(select_all)
        btn_row.addWidget(deselect_all)
        layout.addLayout(btn_row)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.elements_layout = QVBoxLayout(scroll_content)
        self.elements_layout.setSpacing(2)
        self.elements_layout.setContentsMargins(4, 4, 4, 4)

        self.element_checkboxes = {}
        for element_key, display_label in self.elements.items():
            checkbox = QCheckBox(display_label)
            checkbox.element_key = element_key
            checkbox.stateChanged.connect(self._on_element_toggled)
            self.element_checkboxes[element_key] = checkbox
            self.elements_layout.addWidget(checkbox)
        self.elements_layout.addStretch(1)

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area, 1)

        self._update_element_count()
        return self.elements_group

    def _build_params_group(self) -> QGroupBox:
        """
        Returns:
            QGroupBox: Result of the operation.
        """
        params_group = QGroupBox("Parameter Settings")
        grid = QGridLayout(params_group)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)

        row = 0

        self.include_checkbox = QCheckBox("Include selected elements in analysis")
        self.include_checkbox.setChecked(True)
        grid.addWidget(self.include_checkbox, row, 0, 1, 2)
        row += 1

        grid.addWidget(QLabel("Detection Method:"), row, 0)
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Manual",
            "Compound Poisson LogNormal",
        ])
        self.method_combo.currentTextChanged.connect(self.toggle_manual_threshold)
        grid.addWidget(self.method_combo, row, 1)
        row += 1

        self.manual_threshold_label = QLabel("Manual Threshold:")
        self.manual_threshold = QDoubleSpinBox()
        self.manual_threshold.setRange(0.0, 999999.0)
        self.manual_threshold.setDecimals(2)
        self.manual_threshold.setValue(100.0)
        self.manual_threshold.setSingleStep(10.0)
        self.manual_threshold.setToolTip("Threshold in counts (only used with the Manual method).")
        grid.addWidget(self.manual_threshold_label, row, 0)
        grid.addWidget(self.manual_threshold, row, 1)
        row += 1

        self.iterative_checkbox = QCheckBox("Iterative thresholding")
        self.iterative_checkbox.setChecked(True)
        self.iterative_checkbox.setToolTip(
            "Re-estimate the threshold after removing detected particles, then repeat."
        )
        grid.addWidget(self.iterative_checkbox, row, 0, 1, 2)
        row += 1

        return params_group

    def _build_advanced_section(self) -> CollapsibleSection:
        """
        Returns:
            CollapsibleSection: Result of the operation.
        """
        section = CollapsibleSection("Advanced")
        grid = section.content_layout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)

        row = 0

        grid.addWidget(QLabel("Minimum Points:"), row, 0)
        self.min_points = QSpinBox()
        self.min_points.setRange(1, 5)
        self.min_points.setValue(1)
        self.min_points.setToolTip(
            "Minimum number of consecutive points above threshold to count as a particle."
        )
        grid.addWidget(self.min_points, row, 1)
        row += 1

        grid.addWidget(QLabel("Alpha (Error Rate):"), row, 0)
        self.confidence_level = QDoubleSpinBox()
        self.confidence_level.setRange(0.00000001, 0.1)
        self.confidence_level.setDecimals(8)
        self.confidence_level.setValue(0.000001)
        self.confidence_level.setSingleStep(0.000001)
        self.confidence_level.setToolTip("False-positive rate for the detection threshold.")
        grid.addWidget(self.confidence_level, row, 1)
        row += 1

        grid.addWidget(QLabel("Custom Window Size:"), row, 0)
        window_container = QWidget()
        window_layout = QHBoxLayout(window_container)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(8)
        self.use_window_size = QCheckBox("Enable")
        self.use_window_size.setToolTip("Enable a custom rolling window for background calculation.")
        self.use_window_size.stateChanged.connect(self.toggle_window_size)
        self.window_size = QSpinBox()
        self.window_size.setRange(500, 100000)
        self.window_size.setValue(5000)
        self.window_size.setSingleStep(100)
        self.window_size.setToolTip("Custom window size for background calculation.")
        self.window_size.setVisible(False)
        window_layout.addWidget(self.use_window_size)
        window_layout.addWidget(self.window_size, 1)
        grid.addWidget(window_container, row, 1)
        row += 1

        grid.addWidget(QLabel("Integration Method:"), row, 0)
        self.integration_method = QComboBox()
        self.integration_method.addItems(["Background", "Threshold", "Midpoint"])
        grid.addWidget(self.integration_method, row, 1)
        row += 1

        grid.addWidget(QLabel("Split Method:"), row, 0)
        self.split_method = QComboBox()
        self.split_method.addItems(["No Splitting", "1D Watershed"])
        self.split_method.setCurrentText("1D Watershed")
        self.split_method.currentTextChanged.connect(self._toggle_valley_ratio)
        grid.addWidget(self.split_method, row, 1)
        row += 1

        self.valley_ratio_label = QLabel("Valley Ratio:")
        self.valley_ratio_label.setToolTip(
            "Valley-to-peak height ratio threshold for 1D Watershed.\n"
            "Lower = only split very deep valleys.\n"
            "Higher = split shallower valleys.\n"
            "Default: 0.50"
        )
        self.valley_ratio = QDoubleSpinBox()
        self.valley_ratio.setRange(0.01, 0.99)
        self.valley_ratio.setDecimals(2)
        self.valley_ratio.setSingleStep(0.05)
        self.valley_ratio.setValue(0.50)
        self.valley_ratio.setToolTip(self.valley_ratio_label.toolTip())
        grid.addWidget(self.valley_ratio_label, row, 0)
        grid.addWidget(self.valley_ratio, row, 1)
        row += 1

        return section

    # ------------------------------------------------------------------ #
    # Behavior
    # ------------------------------------------------------------------ #

    def toggle_manual_threshold(self, method):
        """Show/hide the manual threshold input based on the detection method.
        Args:
            method (Any): The method.
        """
        is_manual = method == "Manual"
        if hasattr(self, 'manual_threshold_label'):
            self.manual_threshold_label.setVisible(is_manual)
        if hasattr(self, 'manual_threshold'):
            self.manual_threshold.setVisible(is_manual)
            if is_manual:
                _p = theme.palette
                self.manual_threshold.setStyleSheet(
                    f"QDoubleSpinBox {{ background-color: {_p.accent_soft}; "
                    f"color: {_p.text_primary}; }}"
                )
            else:
                self.manual_threshold.setStyleSheet("")

    def toggle_window_size(self, state):
        """Show/hide the window size input based on the Enable checkbox.

        Accepts either a Qt.CheckState enum (from checkState()) or an int
        (from the stateChanged signal), since both call sites feed this.
        Args:
            state (Any): State value.
        """
        if isinstance(state, Qt.CheckState):
            is_enabled = state == Qt.CheckState.Checked
        else:
            is_enabled = int(state) == Qt.CheckState.Checked.value
        self.window_size.setVisible(is_enabled)
        if is_enabled:
            _p = theme.palette
            self.window_size.setStyleSheet(
                f"QSpinBox {{ background-color: {_p.accent_soft}; "
                f"color: {_p.text_primary}; }}"
            )
        else:
            self.window_size.setStyleSheet("")

    def _toggle_valley_ratio(self, method: str):
        """Show/hide the valley ratio input depending on the split method.
        Args:
            method (str): The method.
        """
        is_watershed = method == "1D Watershed"
        self.valley_ratio_label.setVisible(is_watershed)
        self.valley_ratio.setVisible(is_watershed)

    def filter_elements(self):
        """Filter element checkboxes based on search text input."""
        search_text = self.search_box.text().lower()
        for checkbox in self.element_checkboxes.values():
            checkbox.setVisible(search_text in checkbox.text().lower())

    # ----- selection helpers ------------------------------------------- #

    def select_all(self):
        for checkbox in self.element_checkboxes.values():
            if checkbox.isVisible():
                checkbox.setChecked(True)

    def deselect_all(self):
        for checkbox in self.element_checkboxes.values():
            checkbox.setChecked(False)

    def select_all_samples(self):
        for i in range(self.sample_list.count()):
            self.sample_list.item(i).setSelected(True)

    def deselect_all_samples(self):
        for i in range(self.sample_list.count()):
            self.sample_list.item(i).setSelected(False)

    def _on_element_toggled(self):
        self.selected_elements = {
            cb.element_key for cb in self.element_checkboxes.values() if cb.isChecked()
        }
        self._update_element_count()

    def update_selected_elements(self):
        """Back-compat alias in case external code referenced this name."""
        self._on_element_toggled()

    def _update_element_count(self):
        total = len(self.element_checkboxes)
        selected = sum(1 for cb in self.element_checkboxes.values() if cb.isChecked())
        self.elements_group.setTitle(f"Elements  ({selected}/{total})")

    def _update_sample_count(self):
        total = self.sample_list.count()
        selected = len(self.sample_list.selectedItems())
        self.samples_group.setTitle(f"Samples  ({selected}/{total})")

    # ------------------------------------------------------------------ #
    # Parameter I/O
    # ------------------------------------------------------------------ #

    def initialize_controls_from_parameters(self):
        """Initialize UI controls with current parameter values from existing settings."""
        if not self.current_parameters:
            self.toggle_manual_threshold(self.method_combo.currentText())
            self.toggle_window_size(self.use_window_size.checkState())
            self._toggle_valley_ratio(self.split_method.currentText())
            return

        first_key = next(iter(self.current_parameters))
        params = self.current_parameters[first_key]

        self.include_checkbox.setChecked(params.get('include', True))
        method = params.get('Method', "Compound Poisson LogNormal")
        self.method_combo.setCurrentText(method)
        self.manual_threshold.setValue(params.get('manual_threshold', 1000.0))
        self.min_points.setValue(params.get('min_continuous', 1))
        self.confidence_level.setValue(params.get('alpha', 0.000001))
        self.iterative_checkbox.setChecked(params.get('iterative', True))

        self.use_window_size.setChecked(params.get('use_window_size', False))
        self.window_size.setValue(params.get('window_size', 5000))
        self.integration_method.setCurrentText(params.get('integration_method', 'Background'))
        split = params.get('split_method', '1D Watershed')
        self.split_method.setCurrentText(split)
        self.valley_ratio.setValue(params.get('valley_ratio', 0.50))
        self._toggle_valley_ratio(split)

        self.toggle_manual_threshold(method)
        self.toggle_window_size(self.use_window_size.checkState())

    def get_parameters(self):
        """Return the parameter values to apply to selected elements.
        Returns:
            dict: Result of the operation.
        """
        return {
            'include': self.include_checkbox.isChecked(),
            'method': self.method_combo.currentText(),
            'manual_threshold': self.manual_threshold.value(),
            'min_continuous': int(self.min_points.value()),
            'alpha': self.confidence_level.value(),
            'iterative': self.iterative_checkbox.isChecked(),
            'use_window_size': self.use_window_size.isChecked(),
            'window_size': self.window_size.value(),
            'integration_method': self.integration_method.currentText(),
            'split_method': self.split_method.currentText(),
            'valley_ratio': self.valley_ratio.value(),
        }

    def get_selected_samples(self):
        """Return names of all selected samples.
        Returns:
            list: Result of the operation.
        """
        return [
            self.sample_list.item(i).text()
            for i in range(self.sample_list.count())
            if self.sample_list.item(i).isSelected()
        ]