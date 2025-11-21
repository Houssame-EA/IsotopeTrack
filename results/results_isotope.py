from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                              QLabel, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                              QDialogButtonBox, QGroupBox, QColorDialog, QPushButton,
                              QLineEdit, QGraphicsProxyWidget, QFrame, QScrollArea, QWidget, QListWidgetItem, QListWidget, QMessageBox,
                              QSlider)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QPixmap, QPainter, QBrush, QPen, QFont
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter, SVGExporter
import numpy as np
import math
import numpy as np
from scipy.stats import norm
import math

class IsotopicRatioDisplayDialog(QDialog):
    
    def __init__(self, isotopic_ratio_node, parent_window=None):
        """
        Initialize the isotopic ratio display dialog.
        
        Args:
            isotopic_ratio_node: Isotopic ratio node instance containing configuration and data
            parent_window: Parent window widget (optional)
        
        Returns:
            None
        """
        super().__init__(parent_window)
        self.isotopic_ratio_node = isotopic_ratio_node
        self.parent_window = parent_window
        
        self.setWindowTitle("Isotopic Ratio Analysis")
        self.setMinimumSize(1400, 800)
        
        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        self.setup_ui()
        self.update_display()
        
        self.isotopic_ratio_node.configuration_changed.connect(self.update_display)
        
    def setup_ui(self):
        """
        Set up the user interface layout.
        
        Creates a horizontal layout with configuration panel on the left
        and plot panel on the right.
        
        Args:
            None
        
        Returns:
            None
        """
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        config_panel = self.create_config_panel()
        config_panel.setFixedWidth(400)
        layout.addWidget(config_panel)
        
        plot_panel = self.create_plot_panel()
        layout.addWidget(plot_panel, stretch=1)
        
    def is_multiple_sample_data(self):
        """
        Check if dealing with multiple sample data.
        
        Args:
            None
        
        Returns:
            bool: True if input data is multiple sample type, False otherwise
        """
        return (hasattr(self.isotopic_ratio_node, 'input_data') and 
                self.isotopic_ratio_node.input_data and 
                self.isotopic_ratio_node.input_data.get('type') == 'multiple_sample_data')
        
    def get_font_families(self):
        """
        Get list of available font families for display.
        
        Args:
            None
        
        Returns:
            list: List of font family name strings
        """
        return [
            "Times New Roman", "Arial", "Helvetica", "Calibri", "Verdana",
            "Tahoma", "Georgia", "Trebuchet MS", "Comic Sans MS", "Impact",
            "Lucida Console", "Courier New", "Palatino", "Garamond", "Book Antiqua"
        ]
        
    def create_config_panel(self):
        """
        Create the isotopic ratio configuration panel with all settings.
        
        Creates a scrollable panel containing all configuration options including:
        - Multiple sample display modes
        - Data type selection
        - Element selection
        - Natural abundance and standards
        - Reference line display options
        - Font settings
        - Filtering options
        - Axis settings
        - Confidence intervals
        - Display options
        - Sample color controls
        
        Args:
            None
        
        Returns:
            QScrollArea: Scrollable configuration panel widget
        """
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
        """)
        
        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)
        
        title = QLabel("Isotopic Ratio Settings")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #1F2937;
                margin-bottom: 8px;
            }
        """)
        layout.addWidget(title)
        
        if self.is_multiple_sample_data():
            multiple_group = QGroupBox("Multiple Sample Display")
            multiple_layout = QFormLayout(multiple_group)
            
            self.display_mode_combo = QComboBox()
            self.display_mode_combo.addItems([
                'Overlaid (Different Colors)', 
                'Side by Side Subplots', 
                'Individual Subplots',
                'Combined with Legend'
            ])
            self.display_mode_combo.setCurrentText(self.isotopic_ratio_node.config.get('display_mode', 'Overlaid (Different Colors)'))
            self.display_mode_combo.currentTextChanged.connect(self.on_config_changed)
            multiple_layout.addRow("Display Mode:", self.display_mode_combo)
            
            layout.addWidget(multiple_group)
        
        data_group = QGroupBox("Data Type")
        data_layout = QVBoxLayout(data_group)
        
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems([
            'Counts (Raw)',
            'Element Mass (fg)', 
            'Particle Mass (fg)',
            'Element Moles (fmol)',
            'Particle Moles (fmol)'
        ])
        self.data_type_combo.setCurrentText(self.isotopic_ratio_node.config.get('data_type_display', 'Counts (Raw)'))
        self.data_type_combo.currentTextChanged.connect(self.on_data_type_changed)
        data_layout.addWidget(self.data_type_combo)
        
        layout.addWidget(data_group)
        
        element_group = QGroupBox("Element Selection")
        element_layout = QFormLayout(element_group)
        
        available_elements = self.get_available_elements()
        
        self.element1_combo = QComboBox()
        self.element1_combo.addItems(available_elements)
        self.element1_combo.setCurrentText(self.isotopic_ratio_node.config.get('element1', available_elements[0] if available_elements else ''))
        self.element1_combo.currentTextChanged.connect(self.on_element_changed)
        element_layout.addRow("Element 1 (Numerator):", self.element1_combo)
        
        self.element2_combo = QComboBox()
        self.element2_combo.addItems(available_elements)
        current_element2 = self.isotopic_ratio_node.config.get('element2', available_elements[1] if len(available_elements) > 1 else '')
        if current_element2 in available_elements:
            self.element2_combo.setCurrentText(current_element2)
        self.element2_combo.currentTextChanged.connect(self.on_element_changed)
        element_layout.addRow("Element 2 (Denominator):", self.element2_combo)
        
        self.x_axis_element_combo = QComboBox()
        self.x_axis_element_combo.addItems(available_elements)
        current_x_axis = self.isotopic_ratio_node.config.get('x_axis_element', available_elements[0] if available_elements else '')
        if current_x_axis in available_elements:
            self.x_axis_element_combo.setCurrentText(current_x_axis)
        self.x_axis_element_combo.currentTextChanged.connect(self.on_config_changed)
        element_layout.addRow("X-axis Element:", self.x_axis_element_combo)
        
        layout.addWidget(element_group)
        
        abundance_group = QGroupBox("Reference Values (Auto-Calculated)")
        abundance_layout = QFormLayout(abundance_group)
        
        self.natural_ratio_spin = QDoubleSpinBox()
        self.natural_ratio_spin.setRange(0.0, 10000.0)
        self.natural_ratio_spin.setDecimals(6)
        self.natural_ratio_spin.setValue(self.isotopic_ratio_node.config.get('natural_ratio', 1.0))
        self.natural_ratio_spin.setReadOnly(True)
        self.natural_ratio_spin.setStyleSheet("QDoubleSpinBox { background-color: #F3F4F6; }")
        abundance_layout.addRow("Natural Abundance Ratio:", self.natural_ratio_spin)
        
        self.standard_ratio_spin = QDoubleSpinBox()
        self.standard_ratio_spin.setRange(0.0, 10000.0)
        self.standard_ratio_spin.setDecimals(6)
        self.standard_ratio_spin.setValue(self.isotopic_ratio_node.config.get('standard_ratio', 1.0))
        self.standard_ratio_spin.setReadOnly(True)
        self.standard_ratio_spin.setStyleSheet("QDoubleSpinBox { background-color: #F3F4F6; }")
        abundance_layout.addRow("Standard Ratio:", self.standard_ratio_spin)
        
        self.adjust_to_natural_checkbox = QCheckBox()
        self.adjust_to_natural_checkbox.setChecked(self.isotopic_ratio_node.config.get('adjust_to_natural', False))
        self.adjust_to_natural_checkbox.stateChanged.connect(self.on_config_changed)
        abundance_layout.addRow("Adjust to Natural Abundance:", self.adjust_to_natural_checkbox)
        
        layout.addWidget(abundance_group)
        
        reference_group = QGroupBox("Reference Lines Display")
        reference_layout = QFormLayout(reference_group)
        
        self.show_natural_line_checkbox = QCheckBox()
        self.show_natural_line_checkbox.setChecked(self.isotopic_ratio_node.config.get('show_natural_line', True))
        self.show_natural_line_checkbox.stateChanged.connect(self.on_config_changed)
        reference_layout.addRow("Show Natural Abundance Line:", self.show_natural_line_checkbox)
        
        self.show_standard_line_checkbox = QCheckBox()
        self.show_standard_line_checkbox.setChecked(self.isotopic_ratio_node.config.get('show_standard_line', True))
        self.show_standard_line_checkbox.stateChanged.connect(self.on_config_changed)
        reference_layout.addRow("Show Standard Ratio Line:", self.show_standard_line_checkbox)
        
        self.show_mean_line_checkbox = QCheckBox()
        self.show_mean_line_checkbox.setChecked(self.isotopic_ratio_node.config.get('show_mean_line', True))
        self.show_mean_line_checkbox.stateChanged.connect(self.on_config_changed)
        reference_layout.addRow("Show Mean Ratio Line:", self.show_mean_line_checkbox)
        
        layout.addWidget(reference_group)
        
        font_group = QGroupBox("Font Settings")
        font_layout = QFormLayout(font_group)
        
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(self.get_font_families())
        self.font_family_combo.setCurrentText(self.isotopic_ratio_node.config.get('font_family', 'Times New Roman'))
        self.font_family_combo.currentTextChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Family:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(self.isotopic_ratio_node.config.get('font_size', 18))
        self.font_size_spin.valueChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Size:", self.font_size_spin)
        
        font_style_layout = QHBoxLayout()
        self.font_bold_checkbox = QCheckBox("Bold")
        self.font_bold_checkbox.setChecked(self.isotopic_ratio_node.config.get('font_bold', False))
        self.font_bold_checkbox.stateChanged.connect(self.on_config_changed)
        self.font_italic_checkbox = QCheckBox("Italic")
        self.font_italic_checkbox.setChecked(self.isotopic_ratio_node.config.get('font_italic', False))
        self.font_italic_checkbox.stateChanged.connect(self.on_config_changed)
        font_style_layout.addWidget(self.font_bold_checkbox)
        font_style_layout.addWidget(self.font_italic_checkbox)
        font_style_layout.addStretch()
        font_layout.addRow("Font Style:", font_style_layout)
        
        self.font_color_button = QPushButton()
        self.font_color = QColor(self.isotopic_ratio_node.config.get('font_color', '#000000'))
        self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 30px;")
        self.font_color_button.clicked.connect(lambda: self.choose_color('font'))
        font_layout.addRow("Font Color:", self.font_color_button)
        
        layout.addWidget(font_group)
        
        filter_group = QGroupBox("Filtering Options")
        filter_layout = QFormLayout(filter_group)
        
        self.filter_zeros_checkbox = QCheckBox()
        self.filter_zeros_checkbox.setChecked(self.isotopic_ratio_node.config.get('filter_zeros', True))
        self.filter_zeros_checkbox.stateChanged.connect(self.on_config_changed)
        filter_layout.addRow("Filter Zero Values:", self.filter_zeros_checkbox)
        
        self.filter_saturated_checkbox = QCheckBox()
        self.filter_saturated_checkbox.setChecked(self.isotopic_ratio_node.config.get('filter_saturated', False))
        self.filter_saturated_checkbox.stateChanged.connect(self.on_config_changed)
        filter_layout.addRow("Filter Saturated Particles:", self.filter_saturated_checkbox)
        
        self.saturation_threshold_spin = QDoubleSpinBox()
        self.saturation_threshold_spin.setRange(0.1, 1000000.0)
        self.saturation_threshold_spin.setDecimals(2)
        self.update_saturation_threshold()
        self.saturation_threshold_spin.valueChanged.connect(self.on_config_changed)
        filter_layout.addRow("Saturation Threshold:", self.saturation_threshold_spin)
        
        layout.addWidget(filter_group)
        
        axis_group = QGroupBox("Axis Settings")
        axis_layout = QFormLayout(axis_group)
        
        self.x_max_spin = QDoubleSpinBox()
        self.x_max_spin.setRange(1.0, 1000000.0)
        self.x_max_spin.setValue(self.isotopic_ratio_node.config.get('x_max', 99999990.0))
        self.x_max_spin.valueChanged.connect(self.on_config_changed)
        axis_layout.addRow("X-axis Maximum:", self.x_max_spin)
        
        self.log_x_checkbox = QCheckBox()
        self.log_x_checkbox.setChecked(self.isotopic_ratio_node.config.get('log_x', False))
        self.log_x_checkbox.stateChanged.connect(self.on_config_changed)
        axis_layout.addRow("Logarithmic X-axis:", self.log_x_checkbox)
        
        self.log_y_checkbox = QCheckBox()
        self.log_y_checkbox.setChecked(self.isotopic_ratio_node.config.get('log_y', False))
        self.log_y_checkbox.stateChanged.connect(self.on_config_changed)
        axis_layout.addRow("Logarithmic Y-axis:", self.log_y_checkbox)
        
        layout.addWidget(axis_group)
        
        ci_group = QGroupBox("Confidence Intervals")
        ci_layout = QFormLayout(ci_group)
        
        self.show_ci_checkbox = QCheckBox()
        self.show_ci_checkbox.setChecked(self.isotopic_ratio_node.config.get('show_confidence_intervals', True))
        self.show_ci_checkbox.stateChanged.connect(self.on_config_changed)
        ci_layout.addRow("Show Poisson 95% CI:", self.show_ci_checkbox)
        
        layout.addWidget(ci_group)
        
        display_group = QGroupBox("Display Options")
        display_layout = QFormLayout(display_group)
        
        self.marker_size_spin = QSpinBox()
        self.marker_size_spin.setRange(1, 20)
        self.marker_size_spin.setValue(self.isotopic_ratio_node.config.get('marker_size', 14))
        self.marker_size_spin.valueChanged.connect(self.on_config_changed)
        display_layout.addRow("Marker Size:", self.marker_size_spin)
        
        self.marker_alpha_spin = QDoubleSpinBox()
        self.marker_alpha_spin.setRange(0.1, 1.0)
        self.marker_alpha_spin.setSingleStep(0.1)
        self.marker_alpha_spin.setDecimals(1)
        self.marker_alpha_spin.setValue(self.isotopic_ratio_node.config.get('marker_alpha', 0.7))
        self.marker_alpha_spin.valueChanged.connect(self.on_config_changed)
        display_layout.addRow("Marker Transparency:", self.marker_alpha_spin)
        
        if not self.is_multiple_sample_data():
            color_layout = QHBoxLayout()
            self.single_sample_color_button = QPushButton()
            self.single_sample_color_button.setFixedSize(60, 25)
            current_color = self.isotopic_ratio_node.config.get('single_sample_color', '#E74C3C')
            self.single_sample_color_button.setStyleSheet(f"background-color: {current_color}; border: 1px solid black;")
            self.single_sample_color_button.clicked.connect(self.select_single_sample_color)
            color_layout.addWidget(self.single_sample_color_button)
            color_layout.addStretch()
            display_layout.addRow("Marker Color:", color_layout)
        
        layout.addWidget(display_group)
        
        if self.is_multiple_sample_data():
            self.sample_colors_group = QGroupBox("Sample Colors")
            self.sample_colors_layout = QVBoxLayout(self.sample_colors_group)
            self.update_sample_color_controls()
            layout.addWidget(self.sample_colors_group)
        
        button_layout = QHBoxLayout()

        download_button = QPushButton("Download Figure")
        download_button.setStyleSheet("""
            QPushButton {
                background-color: #80D8C3;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
        """)
        download_button.clicked.connect(self.download_figure)
        button_layout.addWidget(download_button)

        layout.addLayout(button_layout)
        layout.addStretch()
        
        return scroll
            
    def choose_color(self, color_type):
        """
        Open color dialog for font color selection.
        
        Args:
            color_type (str): Type of color to choose ('font')
        
        Returns:
            None
        """
        if color_type == 'font':
            color = QColorDialog.getColor(self.font_color, self, "Select Font Color")
            if color.isValid():
                self.font_color = color
                self.font_color_button.setStyleSheet(f"background-color: {color.name()}; min-height: 30px;")
                self.on_config_changed()

    def apply_plot_settings(self, plot_item):
        """
        Apply font settings to a plot item including axes and legend.
        
        Args:
            plot_item: PyQtGraph PlotItem to apply settings to
        
        Returns:
            None
        """
        try:
            font_family = self.isotopic_ratio_node.config.get('font_family', 'Times New Roman')
            font_size = self.isotopic_ratio_node.config.get('font_size', 18)
            is_bold = self.isotopic_ratio_node.config.get('font_bold', False)
            is_italic = self.isotopic_ratio_node.config.get('font_italic', False)
            font_color = self.isotopic_ratio_node.config.get('font_color', '#000000')
            
            font = QFont(font_family, font_size)
            font.setBold(is_bold)
            font.setItalic(is_italic)
            
            x_axis = plot_item.getAxis('bottom')
            y_axis = plot_item.getAxis('left')
            
            x_axis.setStyle(tickFont=font, tickTextOffset=10, tickLength=10)
            y_axis.setStyle(tickFont=font, tickTextOffset=10, tickLength=10)
            
            x_axis.setTextPen(QColor(font_color))
            y_axis.setTextPen(QColor(font_color))
            x_axis.setPen(QPen(QColor(font_color), 1))
            y_axis.setPen(QPen(QColor(font_color), 1))
            
            legend = getattr(plot_item, 'legend', None)
            if legend is not None:
                try:
                    legend_size_css = f'{font_size}pt'
                    legend.setLabelTextSize(legend_size_css)
                    legend.setLabelTextColor(QColor(font_color))
                    
                    for sample, label in legend.items:
                        if hasattr(label, 'setText'):
                            label_style = {
                                'color': font_color,
                                'size': legend_size_css,
                                'bold': is_bold,
                                'italic': is_italic
                            }
                            label.setText(label.text, **label_style)
                            
                except Exception as e:
                    print(f"Warning: Could not update legend font settings: {e}")
            
            x_axis.update()
            y_axis.update()
            if legend is not None:
                legend.update()
            
        except Exception as e:
            print(f"Error applying plot settings: {e}")
                    
    def update_saturation_threshold(self):
        """
        Update saturation threshold based on selected data type.
        
        Sets appropriate default thresholds based on whether data is in
        mass, moles, or counts units.
        
        Args:
            None
        
        Returns:
            None
        """
        data_type = self.data_type_combo.currentText()
        
        if 'Mass' in data_type:
            default_threshold = 500.0
            self.saturation_threshold_spin.setSuffix(" fg")
        elif 'Moles' in data_type:
            default_threshold = 5.0
            self.saturation_threshold_spin.setSuffix(" fmol")
        else:
            default_threshold = 9999999.0
            self.saturation_threshold_spin.setSuffix(" counts")
        
        current_threshold = self.saturation_threshold_spin.value()
        if current_threshold == 10000.0 or abs(current_threshold - 10000.0) < 1.0:
            self.saturation_threshold_spin.setValue(default_threshold)
            self.isotopic_ratio_node.config['saturation_threshold'] = default_threshold
    
    def select_single_sample_color(self):
        """
        Open color dialog for single sample marker color selection.
        
        Args:
            None
        
        Returns:
            None
        """
        current_color = self.isotopic_ratio_node.config.get('single_sample_color', '#E74C3C')
        color = QColorDialog.getColor(QColor(current_color), self, "Select Marker Color")
        
        if color.isValid():
            color_hex = color.name()
            self.single_sample_color_button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            self.isotopic_ratio_node.config['single_sample_color'] = color_hex
            self.on_config_changed()
    
    def on_data_type_changed(self):
        """
        Handle data type selection change.
        
        Updates saturation threshold and triggers configuration change.
        
        Args:
            None
        
        Returns:
            None
        """
        self.update_saturation_threshold()
        self.on_config_changed()
    
    def on_element_changed(self):
        """
        Handle element selection change and auto-calculate ratios.
        
        Automatically calculates natural abundance and standard ratios
        when elements are changed.
        
        Args:
            None
        
        Returns:
            None
        """
        self.calculate_natural_abundance()
        self.calculate_standard_ratio()
        self.on_config_changed()
    
    def apply_global_saturation_filter(self, element_data, config):
        """
        Apply global saturation filter to all elements in particles.
        
        Filters out particles where any element exceeds the saturation threshold.
        
        Args:
            element_data (DataFrame): Particle-by-element data matrix
            config (dict): Configuration dictionary with filter settings
        
        Returns:
            DataFrame: Filtered element data
        """
        if not config.get('filter_saturated', False):
            return element_data
        
        threshold = config.get('saturation_threshold', 99999999)
        
        import pandas as pd
        mask = pd.Series([True] * len(element_data))
        
        for col in element_data.columns:
            mask = mask & (element_data[col] < threshold)
        
        filtered_data = element_data[mask]
        print(f"Global saturation filter: {len(element_data)} -> {len(filtered_data)} particles (threshold: {threshold})")
        return filtered_data
    
    def update_sample_color_controls(self):
        """
        Update color controls for multiple samples with editable names.
        
        Creates color picker buttons and name edit fields for each sample.
        
        Args:
            None
        
        Returns:
            None
        """
        for i in reversed(range(self.sample_colors_layout.count())):
            self.sample_colors_layout.itemAt(i).widget().deleteLater()
        
        sample_names = self.get_available_sample_names()
        
        if not sample_names:
            no_data_label = QLabel("No samples available")
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet("color: gray; font-style: italic;")
            self.sample_colors_layout.addWidget(no_data_label)
            return
        
        default_sample_colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', 
                                '#06B6D4', '#F97316', '#84CC16', '#EC4899', '#6366F1']
        
        sample_colors = self.isotopic_ratio_node.config.get('sample_colors', {})
        
        sample_name_mappings = self.isotopic_ratio_node.config.get('sample_name_mappings', {})
        
        self.sample_name_edits = {}
        
        for i, original_sample_name in enumerate(sample_names):
            sample_layout = QHBoxLayout()
            
            name_edit = QLineEdit()
            name_edit.setFixedWidth(180)
            
            display_name = sample_name_mappings.get(original_sample_name, original_sample_name)
            name_edit.setText(display_name)
            
            name_edit.setStyleSheet("""
                QLineEdit {
                    padding: 2px 5px;
                    border: 1px solid #E2E8F0;
                    border-radius: 4px;
                    font-size: 11px;
                }
                QLineEdit:focus {
                    border: 1px solid #3B82F6;
                }
            """)
            
            name_edit.textChanged.connect(
                lambda text, orig=original_sample_name: self.on_sample_name_changed(orig, text)
            )
            
            sample_layout.addWidget(name_edit)
            self.sample_name_edits[original_sample_name] = name_edit
            
            color_button = QPushButton()
            color_button.setFixedSize(25, 18)
            
            if original_sample_name in sample_colors:
                color = sample_colors[original_sample_name]
            else:
                color = default_sample_colors[i % len(default_sample_colors)]
                sample_colors[original_sample_name] = color
            
            color_button.setStyleSheet(f"background-color: {color}; border: 1px solid black;")
            color_button.clicked.connect(
                lambda checked, sample=original_sample_name, btn=color_button: self.select_sample_color(sample, btn)
            )
            
            sample_layout.addWidget(color_button)
            
            reset_button = QPushButton("↺")
            reset_button.setFixedSize(20, 18)
            reset_button.setToolTip(f"Reset to original name: {original_sample_name}")
            reset_button.setStyleSheet("""
                QPushButton {
                    font-size: 12px;
                    padding: 0;
                    border: 1px solid #E2E8F0;
                    border-radius: 3px;
                    background-color: #F3F4F6;
                }
                QPushButton:hover {
                    background-color: #E5E7EB;
                }
            """)
            reset_button.clicked.connect(
                lambda checked, orig=original_sample_name: self.reset_sample_name(orig)
            )
            
            sample_layout.addWidget(reset_button)
            sample_layout.addStretch()
            
            container = QWidget()
            container.setLayout(sample_layout)
            self.sample_colors_layout.addWidget(container)
        
        self.isotopic_ratio_node.config['sample_colors'] = sample_colors
        self.isotopic_ratio_node.config['sample_name_mappings'] = sample_name_mappings

    def on_sample_name_changed(self, original_name, new_name):
        """
        Handle sample name change event.
        
        Args:
            original_name (str): Original sample name
            new_name (str): New custom display name
        
        Returns:
            None
        """
        if 'sample_name_mappings' not in self.isotopic_ratio_node.config:
            self.isotopic_ratio_node.config['sample_name_mappings'] = {}
        
        self.isotopic_ratio_node.config['sample_name_mappings'][original_name] = new_name
        
        self.on_config_changed()

    def reset_sample_name(self, original_name):
        """
        Reset sample name to original value.
        
        Args:
            original_name (str): Original sample name to restore
        
        Returns:
            None
        """
        if original_name in self.sample_name_edits:
            self.sample_name_edits[original_name].setText(original_name)
        
        if 'sample_name_mappings' in self.isotopic_ratio_node.config:
            self.isotopic_ratio_node.config['sample_name_mappings'].pop(original_name, None)
        
        self.on_config_changed()

    def get_display_name(self, original_name):
        """
        Get display name for a sample (either custom or original).
        
        Args:
            original_name (str): Original sample name
        
        Returns:
            str: Display name (custom if set, otherwise original)
        """
        mappings = self.isotopic_ratio_node.config.get('sample_name_mappings', {})
        return mappings.get(original_name, original_name)
        
    def get_available_sample_names(self):
        """
        Get available sample names from input data.
        
        Args:
            None
        
        Returns:
            list: List of sample name strings
        """
        if self.is_multiple_sample_data():
            return self.isotopic_ratio_node.input_data.get('sample_names', [])
        return []
    
    def select_sample_color(self, sample_name, button):
        """
        Open color dialog for sample color selection.
        
        Args:
            sample_name (str): Name of the sample to set color for
            button (QPushButton): Button widget to update with new color
        
        Returns:
            None
        """
        current_color = self.isotopic_ratio_node.config.get('sample_colors', {}).get(sample_name, '#3B82F6')
        display_name = self.get_display_name(sample_name)
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {display_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'sample_colors' not in self.isotopic_ratio_node.config:
                self.isotopic_ratio_node.config['sample_colors'] = {}
            self.isotopic_ratio_node.config['sample_colors'][sample_name] = color_hex
            
            self.on_config_changed()
    
    def download_figure(self):
        """
        Download the current figure using PyQtGraph exporters.
        
        Detects plot items in the scene and exports to PNG or SVG format.
        
        Args:
            None
        
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Isotopic Ratio Plot",
            "isotopic_ratio_plot.png",
            "PNG Files (*.png);;SVG Files (*.svg);;All Files (*)"
        )
        
        if file_path:
            try:
                plot_items = []
                scene = self.plot_widget.scene()
                for item in scene.items():
                    if hasattr(item, 'plotItem') and item.plotItem is not None:
                        plot_items.append(item.plotItem)
                    elif isinstance(item, pg.PlotItem):
                        plot_items.append(item)
                
                if plot_items:
                    plot_item = plot_items[0]
                    
                    if file_path.lower().endswith('.svg'):
                        exporter = SVGExporter(plot_item)
                    else:
                        exporter = ImageExporter(plot_item)
                        exporter.parameters()['width'] = 1920  
                    
                    exporter.export(file_path)
                else:
                    pixmap = self.plot_widget.grab()
                    pixmap.save(file_path)
                
                QMessageBox.information(self, "✅ Success", 
                                    f"Isotopic ratio plot saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", 
                                f"Failed to save:\n{str(e)}")
                
    def get_available_elements(self):
        """
        Get available elements from the isotopic ratio node's data.
        
        Attempts to extract elements from plot data first, then falls back
        to input data if necessary.
        
        Args:
            None
        
        Returns:
            list: List of available element label strings
        """
        if hasattr(self.isotopic_ratio_node, 'extract_plot_data'):
            try:
                plot_data = self.isotopic_ratio_node.extract_plot_data()
                if plot_data:
                    if self.is_multiple_sample_data():
                        all_elements = set()
                        for sample_data in plot_data.values():
                            if isinstance(sample_data, dict) and 'element_data' in sample_data:
                                all_elements.update(sample_data['element_data'].columns)
                        return sorted(list(all_elements))
                    else:
                        if 'element_data' in plot_data:
                            return list(plot_data['element_data'].columns)
            except:
                pass
        
        if not self.isotopic_ratio_node.input_data:
            return []
        
        data_type = self.isotopic_ratio_node.input_data.get('type')
        
        if data_type in ['sample_data', 'multiple_sample_data']:
            selected_isotopes = self.isotopic_ratio_node.input_data.get('selected_isotopes', [])
            if selected_isotopes:
                return [isotope['label'] for isotope in selected_isotopes]
        
        return []
        
    def calculate_natural_abundance(self):
        """
        Auto-calculate natural abundance ratio using local periodic table data.
        
        Silently calculates the ratio between selected elements based on
        their natural isotopic abundances.
        
        Args:
            None
        
        Returns:
            None
        """
        try:
            element1_name = self.element1_combo.currentText()
            element2_name = self.element2_combo.currentText()
            
            if not element1_name or not element2_name:
                return
            
            from results.results_periodic import CompactPeriodicTableWidget
            periodic_table = CompactPeriodicTableWidget()
            elements_data = periodic_table.get_elements()
            
            abundance1 = None
            abundance2 = None
            
            for element in elements_data:
                for isotope in element['isotopes']:
                    if isinstance(isotope, dict):
                        isotope_label = isotope.get('label', '')
                        if isotope_label == element1_name:
                            abundance1 = isotope.get('abundance', 0)
                        elif isotope_label == element2_name:
                            abundance2 = isotope.get('abundance', 0)
            
            if abundance1 is not None and abundance2 is not None and abundance1 > 0 and abundance2 > 0:
                natural_ratio = abundance1 / abundance2
                self.natural_ratio_spin.setValue(natural_ratio)
                self.isotopic_ratio_node.config['natural_ratio'] = natural_ratio
                print(f"Auto-calculated natural abundance ratio: {natural_ratio:.6f}")
            else:
                self.natural_ratio_spin.setValue(1.0)
                self.isotopic_ratio_node.config['natural_ratio'] = 1.0
                
        except Exception as e:
            print(f"Error calculating natural abundance: {str(e)}")
            self.natural_ratio_spin.setValue(1.0)
            self.isotopic_ratio_node.config['natural_ratio'] = 1.0
    
    def calculate_standard_ratio(self):
        """
        Auto-calculate standard ratio from calibration data (cps/ppb).
        
        Silently retrieves calibration slopes from parent window and
        calculates the ratio between selected elements.
        
        Args:
            None
        
        Returns:
            None
        """
        try:
            if not self.parent_window:
                return
            
            element1_name = self.element1_combo.currentText()
            element2_name = self.element2_combo.currentText()
            
            if not element1_name or not element2_name:
                return
            
            if not hasattr(self.parent_window, 'calibration_results'):
                return
            
            ionic_data = self.parent_window.calibration_results.get("Ionic Calibration", {})
            
            if not ionic_data:
                return
            
            element1_key = self.find_element_key_from_display_label(element1_name)
            element2_key = self.find_element_key_from_display_label(element2_name)
            
            if not element1_key or not element2_key:
                return
            
            element1_cal = ionic_data.get(element1_key, {})
            element2_cal = ionic_data.get(element2_key, {})
            
            if not element1_cal or not element2_cal:
                return
            
            element1_slope = self.get_preferred_slope(element1_cal, element1_key)
            element2_slope = self.get_preferred_slope(element2_cal, element2_key)
            
            if element1_slope is None or element2_slope is None:
                return
            
            if element1_slope <= 0 or element2_slope <= 0:
                return
            
            standard_ratio = element1_slope / element2_slope
            
            self.standard_ratio_spin.setValue(standard_ratio)
            self.isotopic_ratio_node.config['standard_ratio'] = standard_ratio
            print(f"Auto-calculated standard ratio: {standard_ratio:.6f} ({element1_slope:.2f}/{element2_slope:.2f}")
            
        except Exception as e:
            print(f"Error calculating standard ratio: {str(e)}")
            self.standard_ratio_spin.setValue(1.0)
            self.isotopic_ratio_node.config['standard_ratio'] = 1.0
    
    def find_element_key_from_display_label(self, display_label):
        """
        Find element key from display label.
        
        Args:
            display_label (str): Formatted display label for element
        
        Returns:
            str or None: Element key if found, None otherwise
        """
        if not self.parent_window or not hasattr(self.parent_window, 'selected_isotopes'):
            return None
            
        for element, isotopes in self.parent_window.selected_isotopes.items():
            for isotope in isotopes:
                element_key = f"{element}-{isotope:.4f}"
                if hasattr(self.parent_window, 'get_formatted_label'):
                    if self.parent_window.get_formatted_label(element_key) == display_label:
                        return element_key
        return None
    
    def get_preferred_slope(self, cal_data, element_key):
        """
        Get preferred calibration slope for an element.
        
        Args:
            cal_data (dict): Calibration data dictionary
            element_key (str): Element key string
        
        Returns:
            float or None: Calibration slope if found, None otherwise
        """
        if not self.parent_window:
            return None
        
        preferred_method = getattr(self.parent_window, 'isotope_method_preferences', {}).get(element_key, 'Force through zero')
        method_map = {
            'Force through zero': 'zero',
            'Simple linear': 'simple',
            'Weighted': 'weighted',
            'Manual': 'manual',
            
        }
        method_key = method_map.get(preferred_method, 'zero')
        
        method_data = cal_data.get(method_key)
        if method_data and 'slope' in method_data:
            return method_data['slope']
        
        for fallback_method in ['weighted', 'simple', 'zero', 'manual']:
            method_data = cal_data.get(fallback_method)
            if method_data and 'slope' in method_data:
                return method_data['slope']
        
        return None
    
    def create_plot_panel(self):
        """
        Create the expandable plot panel with PyQtGraph.
        
        Args:
            None
        
        Returns:
            QFrame: Frame widget containing the plot
        """
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_widget.setBackground('w')
        layout.addWidget(self.plot_widget)
        
        return panel
    
    def on_config_changed(self):
        """
        Handle configuration changes and update display.
        
        Collects all configuration values from UI controls and triggers
        plot update.
        
        Args:
            None
        
        Returns:
            None
        """
        config_updates = {
            'element1': self.element1_combo.currentText(),
            'element2': self.element2_combo.currentText(),
            'x_axis_element': self.x_axis_element_combo.currentText(),
            'data_type_display': self.data_type_combo.currentText(),
            'natural_ratio': self.natural_ratio_spin.value(),
            'standard_ratio': self.standard_ratio_spin.value(),
            'adjust_to_natural': self.adjust_to_natural_checkbox.isChecked(),
            'show_natural_line': self.show_natural_line_checkbox.isChecked(),
            'show_standard_line': self.show_standard_line_checkbox.isChecked(),
            'show_mean_line': self.show_mean_line_checkbox.isChecked(),
            'filter_zeros': self.filter_zeros_checkbox.isChecked(),
            'filter_saturated': self.filter_saturated_checkbox.isChecked(),
            'saturation_threshold': self.saturation_threshold_spin.value(),
            'x_max': self.x_max_spin.value(),
            'log_x': self.log_x_checkbox.isChecked(),
            'log_y': self.log_y_checkbox.isChecked(),
            'show_confidence_intervals': self.show_ci_checkbox.isChecked(),
            'marker_size': self.marker_size_spin.value(),
            'marker_alpha': self.marker_alpha_spin.value(),
            'font_family': self.font_family_combo.currentText(),
            'font_size': self.font_size_spin.value(),
            'font_bold': self.font_bold_checkbox.isChecked(),
            'font_italic': self.font_italic_checkbox.isChecked(),
            'font_color': self.font_color.name()
        }
        
        if not self.is_multiple_sample_data():
            config_updates['single_sample_color'] = self.isotopic_ratio_node.config.get('single_sample_color', '#E74C3C')
        
        if self.is_multiple_sample_data():
            config_updates.update({
                'display_mode': self.display_mode_combo.currentText()
            })
        
        self.isotopic_ratio_node.config.update(config_updates)
        
        self.update_display()

    def update_display(self):
        """
        Update the isotopic ratio display with support for multiple samples.
        
        Clears existing plot and recreates based on current configuration
        and data. Handles both single and multiple sample modes.
        
        Args:
            None
        
        Returns:
            None
        """
        try:
            self.plot_widget.clear()
            
            plot_data = self.isotopic_ratio_node.extract_plot_data()
            
            if not plot_data:
                plot_item = self.plot_widget.addPlot()
                text_item = pg.TextItem("No particle data available\nConnect to Sample Selector\nand Isotope Filter nodes\nThen run particle detection", 
                                      anchor=(0.5, 0.5), color='gray')
                plot_item.addItem(text_item)
                text_item.setPos(0.5, 0.5)
                plot_item.hideAxis('left')
                plot_item.hideAxis('bottom')
            else:
                config = self.isotopic_ratio_node.config
                
                if self.is_multiple_sample_data():
                    self.create_multiple_sample_isotopic_ratio(plot_data, config)
                else:
                    plot_item = self.plot_widget.addPlot()
                    self.create_isotopic_ratio_plot(plot_item, plot_data, config)
                    self.apply_plot_settings(plot_item)
            
        except Exception as e:
            print(f"Error updating isotopic ratio display: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def create_multiple_sample_isotopic_ratio(self, plot_data, config):
        """
        Create isotopic ratio plot for multiple samples with different display modes.
        
        Args:
            plot_data (dict): Dictionary of sample data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        display_mode = config.get('display_mode', 'Overlaid (Different Colors)')
        sample_names = list(plot_data.keys())
        
        if display_mode == 'Individual Subplots':
            self.create_subplot_isotopic_ratios(plot_data, config)
        elif display_mode == 'Side by Side Subplots':
            self.create_side_by_side_isotopic_ratios(plot_data, config)
        else:
            plot_item = self.plot_widget.addPlot()
            self.create_combined_isotopic_ratio(plot_item, plot_data, config)
            self.apply_plot_settings(plot_item)
    
    def create_legend_proxy_item(self, color, line_style='solid', width=2):
        """
        Create a proxy item for legend that represents a line.
        
        Args:
            color (str): Color hex string or name
            line_style (str): Line style ('solid' or 'dash')
            width (int): Line width in pixels
        
        Returns:
            PlotDataItem: Proxy plot item for legend display
        """
        x_data = np.array([0, 1])
        y_data = np.array([0, 0])
        
        pen_style = pg.QtCore.Qt.SolidLine if line_style == 'solid' else pg.QtCore.Qt.DashLine
        pen = pg.mkPen(color=color, style=pen_style, width=width)
        
        proxy_item = pg.PlotDataItem(x=x_data, y=y_data, pen=pen)
        return proxy_item
    
    def create_combined_isotopic_ratio(self, plot_item, plot_data, config):
        """
        Create combined isotopic ratio plot with individual sample confidence intervals.
        
        Overlays all samples on a single plot with distinct colors and matching
        confidence intervals. Applies logarithmic transformations if enabled.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            plot_data (dict): Dictionary of sample data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_colors = config.get('sample_colors', {})
        default_colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
        
        element1 = config.get('element1', '')
        element2 = config.get('element2', '')
        x_axis_element = config.get('x_axis_element', element1)
        data_type_display = config.get('data_type_display', 'Counts (Raw)')
        
        log_x = config.get('log_x', False)
        log_y = config.get('log_y', False)
        
        x_label = f"log₁₀({x_axis_element}) ({data_type_display})" if log_x else f"{x_axis_element} ({data_type_display})"
        y_label = f"log₁₀(Ratio {element1}/{element2})" if log_y else f"Ratio {element1}/{element2}"
        if config.get('adjust_to_natural', False):
            y_label += " (Adjusted to Natural Abundance)"

        self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
            
        if not element1 or not element2:
            text_item = pg.TextItem('Please select elements in configuration', 
                                anchor=(0.5, 0.5), color='red')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)
            return
        
        legend_items = []
        
        for i, (sample_name, sample_data) in enumerate(plot_data.items()):
            if sample_data and 'element_data' in sample_data:
                element_data = sample_data['element_data']
                
                filtered_element_data = self.apply_global_saturation_filter(element_data, config)
                
                if filtered_element_data.empty:
                    continue
                
                if element1 not in filtered_element_data.columns or element2 not in filtered_element_data.columns:
                    continue
                
                sample_color = sample_colors.get(sample_name, default_colors[i % len(default_colors)])
                
                if config.get('filter_zeros', True):
                    valid_mask = (filtered_element_data[element1] > 0) & (filtered_element_data[element2] > 0)
                    filtered_element_data = filtered_element_data[valid_mask]
                
                if len(filtered_element_data) == 0:
                    continue
                
                ratios = filtered_element_data[element1] / filtered_element_data[element2]
                
                natural_ratio = config.get('natural_ratio', 1.0)
                standard_ratio = config.get('standard_ratio', 1.0)
                adjust_to_natural = config.get('adjust_to_natural', False)
                
                adjustment_factor = 1.0
                if adjust_to_natural and natural_ratio > 0 and standard_ratio > 0:
                    adjustment_factor = natural_ratio / standard_ratio
                    ratios = ratios * adjustment_factor
                
                x_data = filtered_element_data[x_axis_element] if x_axis_element in filtered_element_data.columns else filtered_element_data[element1]
                
                if log_x:
                    valid_x_mask = x_data > 0
                    x_data = x_data[valid_x_mask]
                    ratios = ratios[valid_x_mask]
                    filtered_element_data = filtered_element_data[valid_x_mask]
                    
                    if len(x_data) == 0:
                        continue
                    
                    x_data = np.log10(x_data)
                
                if log_y:
                    valid_y_mask = ratios > 0
                    x_data = x_data[valid_y_mask]
                    ratios = ratios[valid_y_mask]
                    filtered_element_data = filtered_element_data[valid_y_mask]
                    
                    if len(ratios) == 0:
                        continue
                    
                    ratios = np.log10(ratios)
                
                if config.get('show_confidence_intervals', True):
                    counts_data = filtered_element_data
                    self.add_sample_confidence_intervals(plot_item, x_data, counts_data, element1, element2, 
                                                    adjustment_factor, config, sample_color, sample_name)
                
                marker_size = config.get('marker_size', 14)
                marker_alpha = int(config.get('marker_alpha', 0.7) * 255)
                
                color_obj = QColor(sample_color)
                color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), marker_alpha)
                
                scatter = pg.ScatterPlotItem(x=x_data.values, y=ratios.values, 
                                        size=marker_size, 
                                        pen=pg.mkPen(color='black', width=0.5),
                                        brush=pg.mkBrush(*color_rgba))
                plot_item.addItem(scatter)
                
                legend_items.append((scatter, self.get_display_name(sample_name)))
        
        natural_ratio = config.get('natural_ratio', 1.0)
        standard_ratio = config.get('standard_ratio', 1.0)
        adjust_to_natural = config.get('adjust_to_natural', False)
        
        if config.get('show_natural_line', True) and natural_ratio > 0:
            display_natural = np.log10(natural_ratio) if log_y else natural_ratio
            natural_line = pg.InfiniteLine(pos=display_natural, angle=0, 
                                        pen=pg.mkPen(color='blue', style=pg.QtCore.Qt.DashLine, width=2))
            plot_item.addItem(natural_line)
            natural_proxy = self.create_legend_proxy_item('blue', 'dash', 2)
            legend_items.append((natural_proxy, f"Natural: {natural_ratio:.4f}"))
        
        if config.get('show_standard_line', True) and standard_ratio > 0:
            adjusted_standard = standard_ratio * (natural_ratio / standard_ratio if adjust_to_natural else 1.0)
            display_standard = np.log10(adjusted_standard) if log_y else adjusted_standard
            standard_line = pg.InfiniteLine(pos=display_standard, angle=0, 
                                        pen=pg.mkPen(color='green', style=pg.QtCore.Qt.DashLine, width=2))
            plot_item.addItem(standard_line)
            standard_proxy = self.create_legend_proxy_item('green', 'dash', 2)
            legend_items.append((standard_proxy, f"Standard: {adjusted_standard:.4f}"))
        
        if config.get('show_mean_line', True):
            all_ratios = []
            for sample_name, sample_data in plot_data.items():
                if sample_data and 'element_data' in sample_data:
                    element_data = sample_data['element_data']
                    filtered_element_data = self.apply_global_saturation_filter(element_data, config)
                    
                    if filtered_element_data.empty:
                        continue
                    
                    if element1 not in filtered_element_data.columns or element2 not in filtered_element_data.columns:
                        continue
                    
                    if config.get('filter_zeros', True):
                        valid_mask = (filtered_element_data[element1] > 0) & (filtered_element_data[element2] > 0)
                        filtered_element_data = filtered_element_data[valid_mask]
                    
                    if len(filtered_element_data) == 0:
                        continue
                    
                    ratios = filtered_element_data[element1] / filtered_element_data[element2]
                    
                    if adjust_to_natural and natural_ratio > 0 and standard_ratio > 0:
                        adjustment_factor = natural_ratio / standard_ratio
                        ratios = ratios * adjustment_factor
                    
                    all_ratios.extend(ratios.values)
            
            if all_ratios:
                mean_ratio = np.mean(all_ratios)
                display_mean = np.log10(mean_ratio) if (log_y and mean_ratio > 0) else mean_ratio
                mean_line = pg.InfiniteLine(pos=display_mean, angle=0, 
                                        pen=pg.mkPen(color='red', width=2))
                plot_item.addItem(mean_line)
                mean_proxy = self.create_legend_proxy_item('red', 'solid', 2)
                legend_items.append((mean_proxy, f"Mean: {mean_ratio:.4f}"))
        
        if legend_items:
            legend = plot_item.addLegend()
            for item, name in legend_items:
                legend.addItem(item, name)


    def create_sample_specific_isotopic_ratio(self, plot_item, sample_data, config, sample_color, sample_name="Sample"):
        """
        Create isotopic ratio plot for a specific sample with matching colored confidence intervals.
        
        Applies logarithmic transformations if enabled and adds reference lines.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            sample_data (dict): Sample element data dictionary
            config (dict): Configuration dictionary
            sample_color (str): Hex color string for sample
            sample_name (str): Name of sample for legend
        
        Returns:
            None
        """
        element1 = config.get('element1', '')
        element2 = config.get('element2', '')
        x_axis_element = config.get('x_axis_element', element1)
        data_type_display = config.get('data_type_display', 'Counts (Raw)')
        
        if not element1 or not element2:
            return
        
        element_data = sample_data.get('element_data')
        if element_data is None:
            return
        
        filtered_element_data = self.apply_global_saturation_filter(element_data, config)
        
        if filtered_element_data.empty:
            text_item = pg.TextItem('No data after filtering', 
                                anchor=(0.5, 0.5), color='gray')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)
            return
        
        if element1 not in filtered_element_data.columns or element2 not in filtered_element_data.columns:
            return
        
        if config.get('filter_zeros', True):
            valid_mask = (filtered_element_data[element1] > 0) & (filtered_element_data[element2] > 0)
            filtered_element_data = filtered_element_data[valid_mask]
        
        if len(filtered_element_data) == 0:
            return
        
        ratios = filtered_element_data[element1] / filtered_element_data[element2]
        
        natural_ratio = config.get('natural_ratio', 1.0)
        standard_ratio = config.get('standard_ratio', 1.0)
        adjust_to_natural = config.get('adjust_to_natural', False)
        
        adjustment_factor = 1.0
        if adjust_to_natural and natural_ratio > 0 and standard_ratio > 0:
            adjustment_factor = natural_ratio / standard_ratio
            ratios = ratios * adjustment_factor
        
        x_data = filtered_element_data[x_axis_element] if x_axis_element in filtered_element_data.columns else filtered_element_data[element1]
        
        log_x = config.get('log_x', False)
        log_y = config.get('log_y', False)
        
        if log_x:
            valid_x_mask = x_data > 0
            x_data = x_data[valid_x_mask]
            ratios = ratios[valid_x_mask]
            filtered_element_data = filtered_element_data[valid_x_mask]
            
            if len(x_data) == 0:
                return
            
            x_data = np.log10(x_data)
        
        if log_y:
            valid_y_mask = ratios > 0
            x_data = x_data[valid_y_mask]
            ratios = ratios[valid_y_mask]
            filtered_element_data = filtered_element_data[valid_y_mask]
            
            if len(ratios) == 0:
                return
            
            ratios = np.log10(ratios)
        
        if config.get('show_confidence_intervals', True):
            self.add_sample_confidence_intervals(plot_item, x_data, filtered_element_data, element1, element2, 
                                            adjustment_factor, config, sample_color, sample_name)
        
        marker_size = config.get('marker_size', 14)
        marker_alpha = int(config.get('marker_alpha', 0.7) * 255)
        
        color_obj = QColor(sample_color)
        color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), marker_alpha)
        
        scatter = pg.ScatterPlotItem(x=x_data.values, y=ratios.values, 
                                size=marker_size, 
                                pen=pg.mkPen(color='black', width=0.5),
                                brush=pg.mkBrush(*color_rgba))
        plot_item.addItem(scatter)
        
        legend_items = [(scatter, self.get_display_name(sample_name))]
        
        if config.get('show_natural_line', True) and natural_ratio > 0:
            display_natural = np.log10(natural_ratio) if log_y else natural_ratio
            natural_line = pg.InfiniteLine(pos=display_natural, angle=0, 
                                        pen=pg.mkPen(color='blue', style=pg.QtCore.Qt.DashLine, width=1))
            plot_item.addItem(natural_line)
            natural_proxy = self.create_legend_proxy_item('blue', 'dash', 1)
            legend_items.append((natural_proxy, f"Natural: {natural_ratio:.4f}"))
        
        if config.get('show_standard_line', True) and standard_ratio > 0:
            adjusted_standard = standard_ratio * adjustment_factor if adjust_to_natural else standard_ratio
            display_standard = np.log10(adjusted_standard) if log_y else adjusted_standard
            standard_line = pg.InfiniteLine(pos=display_standard, angle=0, 
                                        pen=pg.mkPen(color='green', style=pg.QtCore.Qt.DashLine, width=1))
            plot_item.addItem(standard_line)
            standard_proxy = self.create_legend_proxy_item('green', 'dash', 1)
            legend_items.append((standard_proxy, f"Standard: {adjusted_standard:.4f}"))
        
        if config.get('show_mean_line', True):
            if log_y:
                original_ratios = filtered_element_data[element1] / filtered_element_data[element2]
                original_ratios = original_ratios * adjustment_factor
                mean_ratio = original_ratios.mean()
                display_mean = np.log10(mean_ratio) if mean_ratio > 0 else 0
            else:
                mean_ratio = ratios.mean()
                display_mean = mean_ratio
            
            mean_line = pg.InfiniteLine(pos=display_mean, angle=0, 
                                    pen=pg.mkPen(color='red', width=1))
            plot_item.addItem(mean_line)
            mean_proxy = self.create_legend_proxy_item('red', 'solid', 1)
            legend_items.append((mean_proxy, f"Mean: {mean_ratio:.4f}"))
        
        if legend_items:
            legend = plot_item.addLegend()
            for item, name in legend_items:
                legend.addItem(item, name)

                    
    def create_subplot_isotopic_ratios(self, plot_data, config):
        """
        Create individual subplots for each sample with individual confidence intervals.
        
        Applies logarithmic transformations if enabled.
        
        Args:
            plot_data (dict): Dictionary of sample data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_names = list(plot_data.keys())
        n_samples = len(sample_names)
        
        cols = min(3, n_samples)
        rows = math.ceil(n_samples / cols)
        
        sample_colors = config.get('sample_colors', {})
        default_colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
        
        for i, sample_name in enumerate(sample_names):
            row = i // cols
            col = i % cols
            plot_item = self.plot_widget.addPlot(row=row, col=col)
            
            sample_data = plot_data[sample_name]
            if sample_data:
                sample_color = sample_colors.get(sample_name, default_colors[i % len(default_colors)])
                self.create_sample_specific_isotopic_ratio(plot_item, sample_data, config, sample_color, sample_name)
                plot_item.setTitle(f"{self.get_display_name(sample_name)}")

                element1 = config.get('element1', '')
                element2 = config.get('element2', '')
                x_axis_element = config.get('x_axis_element', element1)
                data_type_display = config.get('data_type_display', 'Counts (Raw)')
                
                log_x = config.get('log_x', False)
                log_y = config.get('log_y', False)
                
                x_label = f"log₁₀({x_axis_element}) ({data_type_display})" if log_x else f"{x_axis_element} ({data_type_display})"
                y_label = f"log₁₀(Ratio {element1}/{element2})" if log_y else f"Ratio {element1}/{element2}"
                
                self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
                
                self.apply_plot_settings(plot_item)


    def create_side_by_side_isotopic_ratios(self, plot_data, config):
        """
        Create side-by-side isotopic ratio plots with individual confidence intervals.
        
        Applies logarithmic transformations if enabled.
        
        Args:
            plot_data (dict): Dictionary of sample data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_names = list(plot_data.keys())
        n_samples = len(sample_names)
        
        sample_colors = config.get('sample_colors', {})
        default_colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
        
        for i, sample_name in enumerate(sample_names):
            plot_item = self.plot_widget.addPlot(row=0, col=i)
            
            sample_data = plot_data[sample_name]
            if sample_data:
                sample_color = sample_colors.get(sample_name, default_colors[i % len(default_colors)])
                self.create_sample_specific_isotopic_ratio(plot_item, sample_data, config, sample_color, sample_name)
                plot_item.setTitle(f"{self.get_display_name(sample_name)}")
                
                element1 = config.get('element1', '')
                element2 = config.get('element2', '')
                x_axis_element = config.get('x_axis_element', element1)
                data_type_display = config.get('data_type_display', 'Counts (Raw)')
                
                log_x = config.get('log_x', False)
                log_y = config.get('log_y', False)
                
                x_label = f"log₁₀({x_axis_element}) ({data_type_display})" if log_x else f"{x_axis_element} ({data_type_display})"
                y_label = f"log₁₀(Ratio {element1}/{element2})" if log_y else f"Ratio {element1}/{element2}"
                
                if i == 0:
                    self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
                else:
                    self.set_axis_labels_with_font(plot_item, x_label, "", config)
                
                self.apply_plot_settings(plot_item)
                    
    def set_axis_labels_with_font(self, plot_item, x_label, y_label, config):
        """
        Set axis labels with proper font formatting.
        
        Args:
            plot_item: PyQtGraph PlotItem
            x_label (str): X-axis label text
            y_label (str): Y-axis label text
            config (dict): Configuration dictionary with font settings
        
        Returns:
            None
        """
        font_family = config.get('font_family', 'Times New Roman')
        font_size = config.get('font_size', 18)
        is_bold = config.get('font_bold', False)
        is_italic = config.get('font_italic', False)
        font_color = config.get('font_color', '#000000')
        
        font_weight = "bold" if is_bold else "normal"
        font_style = "italic" if is_italic else "normal"
        font_string = f'{font_style} {font_weight} {font_size}pt {font_family}'
        
        plot_item.setLabel('bottom', x_label, color=font_color, font=font_string)
        plot_item.setLabel('left', y_label, color=font_color, font=font_string)

    def create_isotopic_ratio_plot(self, plot_item, plot_data, config):
        """
        Create the isotopic ratio plot with Poisson confidence intervals for single sample.
        
        Applies logarithmic transformations if enabled and adds reference lines and legend.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            plot_data (dict): Plot data dictionary with element data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        element1 = config.get('element1', '')
        element2 = config.get('element2', '')
        x_axis_element = config.get('x_axis_element', element1)
        data_type_display = config.get('data_type_display', 'Counts (Raw)')
        
        if not element1 or not element2:
            text_item = pg.TextItem('Please select elements in configuration', 
                                anchor=(0.5, 0.5), color='red')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)
            return
        
        element_data = plot_data.get('element_data')
        if element_data is None:
            text_item = pg.TextItem('Missing element data', 
                                anchor=(0.5, 0.5), color='red')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)
            return
        
        filtered_element_data = self.apply_global_saturation_filter(element_data, config)
        
        if filtered_element_data.empty:
            text_item = pg.TextItem('No data after filtering', 
                                anchor=(0.5, 0.5), color='gray')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)
            return
        
        if element1 not in filtered_element_data.columns or element2 not in filtered_element_data.columns:
            text_item = pg.TextItem(f'Elements {element1} or {element2} not found in data', 
                                anchor=(0.5, 0.5), color='red')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)
            return
        
        if config.get('filter_zeros', True):
            valid_mask = (filtered_element_data[element1] > 0) & (filtered_element_data[element2] > 0)
            filtered_element_data = filtered_element_data[valid_mask]
        
        if len(filtered_element_data) == 0:
            text_item = pg.TextItem(f'No valid data for {element1}/{element2}', 
                                anchor=(0.5, 0.5), color='red')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)
            return
        
        ratios = filtered_element_data[element1] / filtered_element_data[element2]
        
        natural_ratio = config.get('natural_ratio', 1.0)
        standard_ratio = config.get('standard_ratio', 1.0)
        adjust_to_natural = config.get('adjust_to_natural', False)
        
        adjustment_factor = 1.0
        if adjust_to_natural and natural_ratio > 0 and standard_ratio > 0:
            adjustment_factor = natural_ratio / standard_ratio
            ratios = ratios * adjustment_factor
        
        if x_axis_element in filtered_element_data.columns:
            x_data = filtered_element_data[x_axis_element]
            x_label = f"{x_axis_element} ({data_type_display})"
        else:
            x_data = filtered_element_data[element1]
            x_label = f"{element1} ({data_type_display})"
        
        log_x = config.get('log_x', False)
        log_y = config.get('log_y', False)
        
        if log_x:
            valid_x_mask = x_data > 0
            x_data = x_data[valid_x_mask]
            ratios = ratios[valid_x_mask]
            filtered_element_data = filtered_element_data[valid_x_mask]
            
            if len(x_data) == 0:
                text_item = pg.TextItem('No positive X data for log transformation', 
                                    anchor=(0.5, 0.5), color='red')
                plot_item.addItem(text_item)
                text_item.setPos(0.5, 0.5)
                return
            
            x_data = np.log10(x_data)
            x_label = f"log₁₀({x_axis_element}) ({data_type_display})"
        
        if log_y:
            valid_y_mask = ratios > 0
            x_data = x_data[valid_y_mask]
            ratios = ratios[valid_y_mask]
            filtered_element_data = filtered_element_data[valid_y_mask]
            
            if len(ratios) == 0:
                text_item = pg.TextItem('No positive ratio data for log transformation', 
                                    anchor=(0.5, 0.5), color='red')
                plot_item.addItem(text_item)
                text_item.setPos(0.5, 0.5)
                return
            
            ratios = np.log10(ratios)
            y_label = f"log₁₀(Ratio {element1}/{element2})"
            if adjust_to_natural:
                y_label += " (Adjusted to Natural Abundance)"
        else:
            y_label = f"Ratio {element1}/{element2}"
            if adjust_to_natural:
                y_label += " (Adjusted to Natural Abundance)"
        
        sample_color = config.get('single_sample_color', '#E74C3C')
        
        if config.get('show_confidence_intervals', True):
            self.add_sample_confidence_intervals(plot_item, x_data, filtered_element_data, element1, element2, 
                                            adjustment_factor, config, sample_color, "Single Sample")
        
        marker_size = config.get('marker_size', 14)
        marker_alpha = int(config.get('marker_alpha', 0.7) * 255)
        
        color_obj = QColor(sample_color)
        color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), marker_alpha)
        
        scatter = pg.ScatterPlotItem(x=x_data.values, y=ratios.values, 
                                size=marker_size, 
                                pen=pg.mkPen(color='black', width=0.5),
                                brush=pg.mkBrush(*color_rgba))
        plot_item.addItem(scatter)
        
        legend_items = [(scatter, f"Ratio {element1}/{element2}")]
        
        if config.get('show_natural_line', True) and natural_ratio > 0:
            display_natural = np.log10(natural_ratio) if log_y else natural_ratio
            natural_line = pg.InfiniteLine(pos=display_natural, angle=0, 
                                        pen=pg.mkPen(color='blue', style=pg.QtCore.Qt.DashLine, width=2))
            plot_item.addItem(natural_line)
            natural_proxy = self.create_legend_proxy_item('blue', 'dash', 2)
            legend_items.append((natural_proxy, f"Natural: {natural_ratio:.4f}"))
        
        if config.get('show_standard_line', True) and standard_ratio > 0:
            adjusted_standard = standard_ratio * adjustment_factor if adjust_to_natural else standard_ratio
            display_standard = np.log10(adjusted_standard) if log_y else adjusted_standard
            standard_line = pg.InfiniteLine(pos=display_standard, angle=0, 
                                        pen=pg.mkPen(color='green', style=pg.QtCore.Qt.DashLine, width=2))
            plot_item.addItem(standard_line)
            standard_proxy = self.create_legend_proxy_item('green', 'dash', 2)
            legend_items.append((standard_proxy, f"Standard: {adjusted_standard:.4f}"))
        
        if config.get('show_mean_line', True):
            if log_y:
                original_ratios = filtered_element_data[element1] / filtered_element_data[element2]
                original_ratios = original_ratios * adjustment_factor
                mean_ratio = original_ratios.mean()
                display_mean = np.log10(mean_ratio) if mean_ratio > 0 else 0
            else:
                mean_ratio = ratios.mean()
                display_mean = mean_ratio
            
            mean_line = pg.InfiniteLine(pos=display_mean, angle=0, 
                                    pen=pg.mkPen(color='red', width=2))
            plot_item.addItem(mean_line)
            mean_proxy = self.create_legend_proxy_item('red', 'solid', 2)
            legend_items.append((mean_proxy, f"Mean: {mean_ratio:.4f}"))
        
        font_family = config.get('font_family', 'Times New Roman')
        font_size = config.get('font_size', 18)
        is_bold = config.get('font_bold', False)
        is_italic = config.get('font_italic', False)
        font_color = config.get('font_color', '#000000')
        
        font_weight = "bold" if is_bold else "normal"
        font_style = "italic" if is_italic else "normal"
        font_string = f'{font_style} {font_weight} {font_size}pt {font_family}'
        
        plot_item.setLabel('bottom', x_label, color=font_color, font=font_string)
        plot_item.setLabel('left', y_label, color=font_color, font=font_string)
        
        if legend_items:
            legend = plot_item.addLegend()
            for item, name in legend_items:
                legend.addItem(item, name)

                    

                
    def add_sample_confidence_intervals(self, plot_item, x_data, element_data, element1, element2, 
                              adjustment_factor, config, sample_color, sample_name):
        """
        Add Poisson confidence intervals as boundary lines only with matching color.
        
        Supports logarithmic transformation of both X and Y data.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            x_data (Series): X-axis data (already transformed if log_x)
            element_data (DataFrame): Particle element data for count estimation
            element1 (str): Numerator element name
            element2 (str): Denominator element name
            adjustment_factor (float): Ratio adjustment factor
            config (dict): Configuration dictionary
            sample_color (str): Hex color string for CI lines
            sample_name (str): Sample name for logging
        
        Returns:
            None
        """
        try:
            data_type_display = config.get('data_type_display', 'Counts (Raw)')
            log_x = config.get('log_x', False)
            log_y = config.get('log_y', False)
            
            if log_x:
                x_min = x_data.min()
                x_max = x_data.max()
                x_range = np.linspace(x_min, x_max, 100)
            else:
                x_min = max(x_data.min() * 0.1, 0.001)
                x_max = min(config.get('x_max', 99999999.0), x_data.max() * 1.2)
                x_range = np.linspace(x_min, x_max, 100)
            
            upper_ci = []
            lower_ci = []
            
            ratios = element_data[element1] / element_data[element2]
            theoretical_ratio = ratios.mean()
            
            theoretical_ratio *= adjustment_factor
            
            for x_val in x_range:
                if log_x:
                    linear_x_val = 10**x_val
                else:
                    linear_x_val = x_val
                
                if linear_x_val > 0:
                    if 'Mass' in data_type_display:
                        estimated_count = max(linear_x_val * 100.0, 0.1)
                    elif 'Moles' in data_type_display:
                        estimated_count = max(linear_x_val * 10000.0, 0.1)
                    else:
                        estimated_count = max(linear_x_val / 10.0, 0.1)
                    
                    if estimated_count < 1.0:
                        relative_error = 1.96 / max(np.sqrt(estimated_count), 0.1)
                        relative_error = min(relative_error, 2.0)
                    else:
                        relative_error = 1.96 / np.sqrt(estimated_count)
                    
                    upper = theoretical_ratio * (1 + relative_error)
                    lower = theoretical_ratio * (1 - relative_error)
                    
                    lower = max(0.001, lower)
                    
                    if log_y:
                        upper = np.log10(upper) if upper > 0 else -3
                        lower = np.log10(lower) if lower > 0 else -3
                    
                    upper_ci.append(upper)
                    lower_ci.append(lower)
                else:
                    if log_y:
                        upper_ci.append(np.log10(theoretical_ratio * 2) if theoretical_ratio > 0 else 0)
                        lower_ci.append(np.log10(theoretical_ratio * 0.5) if theoretical_ratio > 0 else -3)
                    else:
                        upper_ci.append(theoretical_ratio * 2)
                        lower_ci.append(theoretical_ratio * 0.5)
            
            x_range = np.array(x_range)
            upper_ci = np.array(upper_ci)
            lower_ci = np.array(lower_ci)
            
            color_obj = QColor(sample_color)
            pen_color = (color_obj.red(), color_obj.green(), color_obj.blue(), 200)
            
            upper_line = pg.PlotDataItem(x=x_range, y=upper_ci, 
                                    pen=pg.mkPen(color=pen_color, width=1.5))
            lower_line = pg.PlotDataItem(x=x_range, y=lower_ci, 
                                    pen=pg.mkPen(color=pen_color, width=1.5))
            
            plot_item.addItem(upper_line)
            plot_item.addItem(lower_line)
            
            print(f"Added confidence interval lines for {sample_name} with color {sample_color} (data type: {data_type_display}, log_x: {log_x}, log_y: {log_y})")
            
        except Exception as e:
            print(f"Error adding confidence intervals for {sample_name}: {str(e)}")
            import traceback
            traceback.print_exc()


class IsotopicRatioPlotNode(QObject):
    
    position_changed = Signal(object)
    configuration_changed = Signal()
    
    def __init__(self, parent_window=None):
        """
        Initialize isotopic ratio plot node.
        
        Args:
            parent_window: Parent window widget for accessing calibration data
        
        Returns:
            None
        """
        super().__init__()
        self.title = "Isotopic"
        self.node_type = "isotopic_ratio_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.config = {
        'element1': '',
        'element2': '',
        'x_axis_element': '',
        'data_type_display': 'Counts (Raw)',
        'natural_ratio': 1.0,
        'standard_ratio': 1.0,
        'adjust_to_natural': False,
        'show_natural_line': True,
        'show_standard_line': True,
        'show_mean_line': True,
        'filter_zeros': True,
        'filter_saturated': False,
        'saturation_threshold': 9999999.0,
        'x_max': 999999999.0,
        'log_x': False,
        'log_y': False,
        'show_confidence_intervals': True,
        'marker_size': 14,
        'marker_alpha': 0.7,
        'single_sample_color': '#E74C3C',
        'display_mode': 'Overlaid (Different Colors)',
        'sample_colors': {},
        'sample_name_mappings': {},
        'font_family': 'Times New Roman',
        'font_size': 18,
        'font_bold': False,
        'font_italic': False,
        'font_color': '#000000'
    }
            
        self.input_data = None
        self.plot_widget = None
            
    def set_position(self, pos):
        """
        Set position of the node in the workflow canvas.
        
        Args:
            pos (QPointF): Position coordinates
        
        Returns:
            None
        """
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)
        
    def configure(self, parent_window):
        """
        Show configuration dialog for user interaction.
        
        Show configuration dialog for user interaction.
        
        Args:
            parent_window: Parent window widget
        
        Returns:
            bool: True if configuration was successful
        """
        dialog = IsotopicRatioDisplayDialog(self, parent_window)
        dialog.exec()
        return True
        
    def process_data(self, input_data):
        """
        Process input data and update isotopic ratio plot.
        
        Receives data from connected nodes, auto-configures elements if needed,
        and triggers visual updates.
        
        Args:
            input_data (dict): Input data dictionary from upstream nodes
        
        Returns:
            None
        """
        if not input_data:
            print("No input data received for isotopic ratio")
            return
            
        print(f"Isotopic ratio received data: {input_data.get('type', 'unknown')}")
        self.input_data = input_data
        
        if not self.config.get('element1') or not self.config.get('element2'):
            self.auto_configure_elements()
        
        self.configuration_changed.emit()
        
    def auto_configure_elements(self):
        """
        Auto-configure elements when data is first received.
        
        Automatically selects first two available elements for ratio calculation.
        
        Args:
            None
        
        Returns:
            None
        """
        if not self.input_data:
            return
            
        available_elements = self.get_available_elements()
        
        if len(available_elements) >= 2:
            self.config['element1'] = available_elements[0]
            self.config['element2'] = available_elements[1]
            self.config['x_axis_element'] = available_elements[0]
            
    def get_available_elements(self):
        """
        Get available elements from input data.
        
        Extracts element labels from selected isotopes in the input data.
        
        Args:
            None
        
        Returns:
            list: List of available element label strings
        """
        if not self.input_data:
            return []
        
        data_type = self.input_data.get('type')
        
        if data_type in ['sample_data', 'multiple_sample_data']:
            selected_isotopes = self.input_data.get('selected_isotopes', [])
            if selected_isotopes:
                return [isotope['label'] for isotope in selected_isotopes]
        
        return []
        
    def apply_global_saturation_filter_node(self, element_data, config):
        """
        Apply global saturation filter for node display.
        
        Filters out particles where any element exceeds the saturation threshold.
        
        Args:
            element_data (DataFrame): Particle-by-element data matrix
            config (dict): Configuration dictionary with filter settings
        
        Returns:
            DataFrame: Filtered element data
        """
        if not config.get('filter_saturated', False):
            return element_data
        
        threshold = config.get('saturation_threshold', 9999999)
        
        import pandas as pd
        mask = pd.Series([True] * len(element_data))
        
        for col in element_data.columns:
            mask = mask & (element_data[col] < threshold)
        
        return element_data[mask]
        
    def extract_plot_data(self):
        """
        Extract plottable data from input matching histogram logic.
        
        Creates particle-by-element matrices for the selected data type,
        supporting both single and multiple sample modes.
        
        Args:
            None
        
        Returns:
            dict or None: Dictionary with element_data DataFrames, or None if no data
        """
        if not self.input_data:
            return None
            
        data_type_display = self.config.get('data_type_display', 'Counts (Raw)')
        input_type = self.input_data.get('type')
        
        data_key_mapping = {
            'Counts (Raw)': 'elements',
            'Element Mass (fg)': 'element_mass_fg',
            'Particle Mass (fg)': 'particle_mass_fg',
            'Element Moles (fmol)': 'element_moles_fmol',
            'Particle Moles (fmol)': 'particle_moles_fmol'
        }
        
        data_key = data_key_mapping.get(data_type_display, 'elements')
        
        if input_type == 'sample_data':
            return self._extract_single_sample_data(data_key)
            
        elif input_type == 'multiple_sample_data':
            return self._extract_multiple_sample_data(data_key)
            
        return None
    
    def _extract_single_sample_data(self, data_key):
        """
        Extract data for single sample creating particle-by-element matrix.
        
        Creates a DataFrame where rows are particles and columns are elements,
        with appropriate filtering based on data type.
        
        Args:
            data_key (str): Key for data type in particle dictionary ('elements', 'element_mass_fg', etc.)
        
        Returns:
            dict or None: Dictionary with 'element_data' DataFrame, or None if extraction fails
        """
        particles = self.input_data.get('particle_data')
        
        if not particles:
            print(f"No filtered particle data available from sample selector")
            return None
        
        try:
            all_elements = set()
            for particle in particles:
                particle_data_dict = particle.get(data_key, {})
                all_elements.update(particle_data_dict.keys())
            
            if not all_elements:
                print(f"No elements found in particle data for data_key: {data_key}")
                return None
            
            all_elements = sorted(list(all_elements))
            print(f"Found elements: {all_elements}")
            
            particle_element_matrix = []
            
            for particle in particles:
                particle_data_dict = particle.get(data_key, {})
                particle_row = []
                
                for element_name in all_elements:
                    value = particle_data_dict.get(element_name, 0)
                    
                    if data_key == 'elements':
                        if value > 0:
                            particle_row.append(value)
                        else:
                            particle_row.append(0)
                    else:
                        if value > 0 and not np.isnan(value):
                            particle_row.append(value)
                        else:
                            particle_row.append(0)
                
                particle_element_matrix.append(particle_row)
            
            if not particle_element_matrix:
                print(f"No valid particle data found")
                return None
            
            import pandas as pd
            element_df = pd.DataFrame(particle_element_matrix, columns=all_elements)
            
            print(f"Created DataFrame with shape: {element_df.shape}")
            
            return {
                'element_data': element_df
            }
            
        except Exception as e:
            print(f"Error in _extract_single_sample_data: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_multiple_sample_data(self, data_key):
        """
        Extract data for multiple samples creating particle-by-element matrix for each sample.
        
        Creates a separate DataFrame for each sample where rows are particles and
        columns are elements, with appropriate filtering based on data type.
        
        Args:
            data_key (str): Key for data type in particle dictionary ('elements', 'element_mass_fg', etc.)
        
        Returns:
            dict or None: Dictionary mapping sample names to data dictionaries with 'element_data' DataFrames,
                         or None if extraction fails
        """
        particles = self.input_data.get('particle_data', [])
        sample_names = self.input_data.get('sample_names', [])
        
        if not particles:
            print("No filtered particle data available from sample selector")
            return None
        
        try:
            all_elements = set()
            for particle in particles:
                particle_data_dict = particle.get(data_key, {})
                all_elements.update(particle_data_dict.keys())
            
            if not all_elements:
                print(f"No elements found in particle data for data_key: {data_key}")
                return None
            
            all_elements = sorted(list(all_elements))
            print(f"Found elements: {all_elements}")
            
            sample_particles = {}
            for sample_name in sample_names:
                sample_particles[sample_name] = []
            
            for particle in particles:
                source_sample = particle.get('source_sample')
                if source_sample and source_sample in sample_particles:
                    sample_particles[source_sample].append(particle)
            
            sample_data = {}
            
            for sample_name, sample_particle_list in sample_particles.items():
                if not sample_particle_list:
                    continue
                
                particle_element_matrix = []
                
                for particle in sample_particle_list:
                    particle_data_dict = particle.get(data_key, {})
                    particle_row = []
                    
                    for element_name in all_elements:
                        value = particle_data_dict.get(element_name, 0)
                        
                        if data_key == 'elements':
                            if value > 0:
                                particle_row.append(value)
                            else:
                                particle_row.append(0)
                        else:
                            if value > 0 and not np.isnan(value):
                                particle_row.append(value)
                            else:
                                particle_row.append(0)
                    
                    particle_element_matrix.append(particle_row)
                
                if particle_element_matrix:
                    import pandas as pd
                    element_df = pd.DataFrame(particle_element_matrix, columns=all_elements)
                    sample_data[sample_name] = {
                        'element_data': element_df
                    }
                    print(f"Created DataFrame for {sample_name} with shape: {element_df.shape}")
            
            return sample_data
            
        except Exception as e:
            print(f"Error in _extract_multiple_sample_data: {str(e)}")
            import traceback
            traceback.print_exc()
            return None