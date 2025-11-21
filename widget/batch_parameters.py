from PySide6.QtWidgets import (QPushButton, QVBoxLayout, QLineEdit, QScrollArea, 
                              QWidget, QLabel, QHBoxLayout, QComboBox, QDialogButtonBox,
                              QDialog, QListWidget, QCheckBox, QDoubleSpinBox, QListWidgetItem,
                              QGroupBox, QGridLayout, QSpinBox)


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
        self.resize(600, 600)
        self.elements = elements or {}
        self.current_parameters = current_parameters or {}
        self.selected_elements = set()
        self.all_samples = all_samples or []
        self.selected_samples = set()
        
        self.setup_ui()
        
    def setup_ui(self):
        """
        Set up the user interface for the dialog.
        
        Args:
            None
            
        Returns:
            None
        """
        main_layout = QVBoxLayout(self)
        
        sample_group = QGroupBox("Select Samples")
        sample_layout = QVBoxLayout(sample_group)
        
        sample_buttons_layout = QHBoxLayout()
        select_all_samples_btn = QPushButton("Select All Samples")
        select_all_samples_btn.clicked.connect(self.select_all_samples)
        deselect_all_samples_btn = QPushButton("Deselect All Samples")
        deselect_all_samples_btn.clicked.connect(self.deselect_all_samples)
        sample_buttons_layout.addWidget(select_all_samples_btn)
        sample_buttons_layout.addWidget(deselect_all_samples_btn)
        sample_layout.addLayout(sample_buttons_layout)
        
        self.sample_list = QListWidget()
        self.sample_list.setSelectionMode(QListWidget.MultiSelection)
        for sample_name in self.all_samples:
            item = QListWidgetItem(sample_name)
            self.sample_list.addItem(item)
        sample_layout.addWidget(self.sample_list)
        
        main_layout.addWidget(sample_group)
        
        group_box = QGroupBox("Select Elements")
        group_layout = QVBoxLayout(group_box)
        
        search_layout = QHBoxLayout()
        search_label = QLabel("Filter:")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Type to filter elements...")
        self.search_box.textChanged.connect(self.filter_elements)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_box)
        group_layout.addLayout(search_layout)
        
        buttons_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.deselect_all)
        buttons_layout.addWidget(select_all_btn)
        buttons_layout.addWidget(deselect_all_btn)
        group_layout.addLayout(buttons_layout)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.elements_layout = QVBoxLayout(scroll_content)
        
        self.element_checkboxes = {}
        for element_key, display_label in self.elements.items():
            checkbox = QCheckBox(display_label)
            checkbox.element_key = element_key
            checkbox.stateChanged.connect(self.update_selected_elements)
            self.element_checkboxes[element_key] = checkbox
            self.elements_layout.addWidget(checkbox)
            
        scroll_area.setWidget(scroll_content)
        group_layout.addWidget(scroll_area)
        main_layout.addWidget(group_box)
        
        params_group = QGroupBox("Parameter Settings")
        params_layout = QGridLayout(params_group)
        
        self.include_checkbox = QCheckBox("Include in Analysis")
        self.include_checkbox.setChecked(True)
        params_layout.addWidget(QLabel("Include:"), 0, 0)
        params_layout.addWidget(self.include_checkbox, 0, 1)
        
        params_layout.addWidget(QLabel("Detection Method:"), 1, 0)
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Currie", "Formula_C", "Manual", "Compound Poisson LogNormal"])
        self.method_combo.currentTextChanged.connect(self.toggle_manual_threshold)
        params_layout.addWidget(self.method_combo, 1, 1)
        
        params_layout.addWidget(QLabel("Manual Threshold:"), 2, 0)
        self.manual_threshold = QDoubleSpinBox()
        self.manual_threshold.setRange(0.0, 999999.0)
        self.manual_threshold.setDecimals(2)
        self.manual_threshold.setValue(100.0)
        self.manual_threshold.setSingleStep(10.0)
        self.manual_threshold.setEnabled(False)
        self.manual_threshold.setToolTip("Manual threshold value (only used when Detection Method is 'Manual')")
        params_layout.addWidget(self.manual_threshold, 2, 1)
        
        self.apply_smoothing = QCheckBox("Apply Smoothing")
        self.apply_smoothing.setChecked(False)
        params_layout.addWidget(QLabel("Smoothing:"), 3, 0)
        params_layout.addWidget(self.apply_smoothing, 3, 1)
        
        params_layout.addWidget(QLabel("Window Length:"), 4, 0)
        self.window_length = QDoubleSpinBox()
        self.window_length.setRange(3, 9)
        self.window_length.setValue(3)
        self.window_length.setSingleStep(2)
        params_layout.addWidget(self.window_length, 4, 1)
        
        params_layout.addWidget(QLabel("Smoothing Iterations:"), 5, 0)
        self.iterations = QDoubleSpinBox()
        self.iterations.setRange(1, 10)
        self.iterations.setValue(1)
        self.iterations.setSingleStep(1)
        params_layout.addWidget(self.iterations, 5, 1)
        
        params_layout.addWidget(QLabel("Minimum Points:"), 6, 0)
        self.min_points = QDoubleSpinBox()
        self.min_points.setRange(1, 5)
        self.min_points.setValue(1)
        self.min_points.setSingleStep(1)
        params_layout.addWidget(self.min_points, 6, 1)
        
        params_layout.addWidget(QLabel("Alpha (Error Rate):"), 7, 0)
        self.confidence_level = QDoubleSpinBox()
        self.confidence_level.setRange(0.00000001, 0.1)
        self.confidence_level.setDecimals(8)
        self.confidence_level.setValue(0.000001)
        self.confidence_level.setSingleStep(0.000001)
        params_layout.addWidget(self.confidence_level, 7, 1)
        
        self.iterative_checkbox = QCheckBox("iterative")
        self.iterative_checkbox.setChecked(True) 
        params_layout.addWidget(QLabel("iterative"), 8, 0)
        params_layout.addWidget(self.iterative_checkbox, 8, 1)
        
        params_layout.addWidget(QLabel("Custom Window Size:"), 9, 0)
        
        window_size_container = QWidget()
        window_size_layout = QHBoxLayout(window_size_container)
        window_size_layout.setContentsMargins(0, 0, 0, 0)
        window_size_layout.setSpacing(10)
        
        self.use_window_size = QCheckBox("Enable")
        self.use_window_size.setChecked(False)
        self.use_window_size.setToolTip("Enable custom window size for background calculation")
        self.use_window_size.stateChanged.connect(self.toggle_window_size)
        window_size_layout.addWidget(self.use_window_size)
        
        self.window_size = QSpinBox()
        self.window_size.setRange(500, 100000)
        self.window_size.setValue(5000)
        self.window_size.setSingleStep(100)
        self.window_size.setEnabled(False)
        self.window_size.setToolTip("Custom window size for background calculation")
        window_size_layout.addWidget(self.window_size)
        
        params_layout.addWidget(window_size_container, 9, 1)
        
        self.initialize_controls_from_parameters()
        
        main_layout.addWidget(params_group)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.apply_smoothing.stateChanged.connect(self.toggle_smoothing_controls)
            
    def toggle_manual_threshold(self, method):
        """
        Enable or disable manual threshold input based on selected detection method.
        
        Args:
            method: The selected detection method string
            
        Returns:
            None
        """
        is_manual = method == "Manual"
        self.manual_threshold.setEnabled(is_manual)
    
        if is_manual:
            self.manual_threshold.setStyleSheet("QDoubleSpinBox { background-color: #E8F5E8; }")
        else:
            self.manual_threshold.setStyleSheet("")
        
    def toggle_smoothing_controls(self, state):
        """
        Enable or disable smoothing parameter controls based on checkbox state.
        
        Args:
            state: The checkbox state value
            
        Returns:
            None
        """
        self.window_length.setEnabled(state)
        self.iterations.setEnabled(state)
        
    def filter_elements(self):
        """
        Filter element checkboxes based on search text input.
        
        Args:
            None
            
        Returns:
            None
        """
        search_text = self.search_box.text().lower()
        for element_key, checkbox in self.element_checkboxes.items():
            display_label = checkbox.text().lower()
            checkbox.setVisible(search_text in display_label)
            
    def toggle_window_size(self, state):
        """
        Enable or disable window size input based on checkbox state.
        
        Args:
            state: The checkbox state value
            
        Returns:
            None
        """
        is_enabled = state == 2  
        self.window_size.setEnabled(is_enabled)
        
        if is_enabled:
            self.window_size.setStyleSheet("QSpinBox { background-color: #E8F5E8; }")
        else:
            self.window_size.setStyleSheet("")
                
    def initialize_controls_from_parameters(self):
        """
        Initialize UI controls with current parameter values from existing settings.
        
        Args:
            None
            
        Returns:
            None
        """
        if not self.current_parameters:
            return
        
        if self.current_parameters:
            first_key = next(iter(self.current_parameters))
            params = self.current_parameters[first_key]
            
            self.include_checkbox.setChecked(params.get('include', True))
            method = params.get('method', "Adaptive_Formula_C")
            self.method_combo.setCurrentText(method)
            self.manual_threshold.setValue(params.get('manual_threshold', 100.0))
            self.apply_smoothing.setChecked(params.get('apply_smoothing', False))
            self.window_length.setValue(params.get('smooth_window', 3))
            self.iterations.setValue(params.get('iterations', 1))
            self.min_points.setValue(params.get('min_continuous', 1))
            self.confidence_level.setValue(params.get('alpha', 0.000001))
            self.iterative_checkbox.setChecked(params.get('iterative', True))
            
            self.use_window_size.setChecked(params.get('use_window_size', False))
            self.window_size.setValue(params.get('window_size', 5000))
            
            self.toggle_smoothing_controls(self.apply_smoothing.isChecked())
            self.toggle_manual_threshold(method)
            self.toggle_window_size(self.use_window_size.checkState()) 
                    
    def select_all(self):
        """
        Select all visible element checkboxes.
        
        Args:
            None
            
        Returns:
            None
        """
        for checkbox in self.element_checkboxes.values():
            if checkbox.isVisible():
                checkbox.setChecked(True)
                
    def deselect_all(self):
        """
        Deselect all element checkboxes.
        
        Args:
            None
            
        Returns:
            None
        """
        for checkbox in self.element_checkboxes.values():
            checkbox.setChecked(False)
            
    def update_selected_elements(self):
        """
        Update the set of selected elements based on checkbox states.
        
        Args:
            None
            
        Returns:
            None
        """
        self.selected_elements = {
            checkbox.element_key for checkbox in self.element_checkboxes.values()
            if checkbox.isChecked()
        }
        
    def get_parameters(self):
        """
        Get the parameter values to apply to selected elements.
        
        Args:
            None
            
        Returns:
            dict: Dictionary containing all parameter settings
        """
        return {
            'include': self.include_checkbox.isChecked(),
            'method': self.method_combo.currentText(),
            'manual_threshold': self.manual_threshold.value(),
            'apply_smoothing': self.apply_smoothing.isChecked(),
            'smooth_window': int(self.window_length.value()),
            'iterations': int(self.iterations.value()),
            'min_continuous': int(self.min_points.value()),
            'alpha': self.confidence_level.value(),
            "iterative": self.iterative_checkbox.isChecked(),
            'use_window_size': self.use_window_size.isChecked(), 
            'window_size': self.window_size.value(),              
        }

    def select_all_samples(self):
        """
        Select all samples in the sample list.
        
        Args:
            None
            
        Returns:
            None
        """
        for i in range(self.sample_list.count()):
            item = self.sample_list.item(i)
            item.setSelected(True)
    
    def deselect_all_samples(self):
        """
        Deselect all samples in the sample list.
        
        Args:
            None
            
        Returns:
            None
        """
        for i in range(self.sample_list.count()):
            item = self.sample_list.item(i)
            item.setSelected(False)
            
    def get_selected_samples(self):
        """
        Get the names of all selected samples.
        
        Args:
            None
            
        Returns:
            list: List of selected sample names as strings
        """
        selected_samples = []
        for i in range(self.sample_list.count()):
            item = self.sample_list.item(i)
            if item.isSelected():
                selected_samples.append(item.text())
        return selected_samples