from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                              QLabel, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                              QDialogButtonBox, QGroupBox, QColorDialog, QPushButton,
                              QLineEdit, QGraphicsProxyWidget, QFrame, QScrollArea, QWidget, QListWidgetItem, QListWidget, QMessageBox)
from PySide6.QtCore import Qt, Signal, QObject, QRectF
from PySide6.QtGui import QColor, QPixmap, QPainter, QBrush, QPen, QFont
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter, SVGExporter
import numpy as np
import math
from scipy import stats
from scipy.stats import gaussian_kde


class MolarRatioDisplayDialog(QDialog):
    
    def __init__(self, molar_ratio_node, parent_window=None):
        """
        Initialize molar ratio display dialog.
        
        Args:
            molar_ratio_node: Node containing molar ratio configuration and data
            parent_window: Parent window widget
        """
        super().__init__(parent_window)
        self.molar_ratio_node = molar_ratio_node
        self.parent_window = parent_window
        
        self.setWindowTitle("Particle Data Molar Ratio Analysis")
        self.setMinimumSize(1400, 800)
        
        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        self.setup_ui()
        self.update_display()
        
        self.molar_ratio_node.configuration_changed.connect(self.update_display)
        
    def setup_ui(self):
        """
        Set up the user interface layout.
        
        Args:
            None
            
        Returns:
            None
        """
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        config_panel = self.create_config_panel()
        config_panel.setFixedWidth(450)
        layout.addWidget(config_panel)
        
        plot_panel = self.create_plot_panel()
        layout.addWidget(plot_panel, stretch=1)
        
        if not hasattr(self, 'plot_widget') or self.plot_widget is None:
            self.plot_widget = pg.GraphicsLayoutWidget()
            self.plot_widget.setBackground('w')
            
    def is_multiple_sample_data(self):
        """
        Check if input data contains multiple samples.
        
        Args:
            None
            
        Returns:
            bool: True if multiple sample data, False otherwise
        """
        return (hasattr(self.molar_ratio_node, 'input_data') and 
                self.molar_ratio_node.input_data and 
                self.molar_ratio_node.input_data.get('type') == 'multiple_sample_data')
        
    def get_font_families(self):
        """
        Get list of available font families.
        
        Args:
            None
            
        Returns:
            list: List of font family names
        """
        return [
            "Times New Roman", "Arial", "Helvetica", "Calibri", "Verdana",
            "Tahoma", "Georgia", "Trebuchet MS", "Comic Sans MS", "Impact",
            "Lucida Console", "Courier New", "Palatino", "Garamond", "Book Antiqua"
        ]
        
    def create_config_panel(self):
        """
        Create the configuration panel with all settings.
        
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
        
        title = QLabel("Molar Ratio Analysis Settings")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #1F2937;
                margin-bottom: 8px;
            }
        """)
        layout.addWidget(title)
        
        element_group = QGroupBox("Element Selection for Ratio")
        element_layout = QFormLayout(element_group)
        
        self.numerator_combo = QComboBox()
        self.numerator_combo.setMinimumWidth(150)
        self.numerator_combo.currentTextChanged.connect(self.on_element_changed)
        element_layout.addRow("Numerator Element:", self.numerator_combo)
        
        self.denominator_combo = QComboBox()
        self.denominator_combo.setMinimumWidth(150)
        self.denominator_combo.currentTextChanged.connect(self.on_element_changed)
        element_layout.addRow("Denominator Element:", self.denominator_combo)
        
        self.ratio_display_label = QLabel("Ratio: Select elements")
        self.ratio_display_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: bold;
                color: #3B82F6;
                padding: 8px;
                background-color: rgba(59, 130, 246, 0.1);
                border-radius: 4px;
                border: 1px solid #3B82F6;
            }
        """)
        element_layout.addRow("Current Ratio:", self.ratio_display_label)
        
        layout.addWidget(element_group)
        
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
            self.display_mode_combo.setCurrentText(self.molar_ratio_node.config.get('display_mode', 'Overlaid (Different Colors)'))
            self.display_mode_combo.currentTextChanged.connect(self.on_config_changed)
            multiple_layout.addRow("Display Mode:", self.display_mode_combo)
            
            self.normalize_samples_checkbox = QCheckBox()
            self.normalize_samples_checkbox.setChecked(self.molar_ratio_node.config.get('normalize_samples', False))
            self.normalize_samples_checkbox.stateChanged.connect(self.on_config_changed)
            multiple_layout.addRow("Normalize by Sample Size:", self.normalize_samples_checkbox)
            
            layout.addWidget(multiple_group)
        
        data_group = QGroupBox("Molar Data Type")
        data_layout = QVBoxLayout(data_group)
        
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems([
            'Element Moles (fmol)',
            'Particle Moles (fmol)'
        ])
        self.data_type_combo.setCurrentText(self.molar_ratio_node.config.get('data_type_display', 'Element Moles (fmol)'))
        self.data_type_combo.currentTextChanged.connect(self.on_data_type_changed)
        data_layout.addWidget(self.data_type_combo)
        
        layout.addWidget(data_group)
        
        calc_group = QGroupBox("Ratio Calculation")
        calc_layout = QFormLayout(calc_group)
        
        self.min_threshold_spin = QDoubleSpinBox()
        self.min_threshold_spin.setRange(0.0, 1000.0)
        self.min_threshold_spin.setSingleStep(0.1)
        self.min_threshold_spin.setDecimals(3)
        self.min_threshold_spin.setValue(self.molar_ratio_node.config.get('min_threshold', 0.001))
        self.min_threshold_spin.valueChanged.connect(self.on_config_changed)
        calc_layout.addRow("Min Value Threshold (fmol):", self.min_threshold_spin)
        
        self.zero_handling_combo = QComboBox()
        self.zero_handling_combo.addItems([
            'Skip particles with zero values',
            'Replace zeros with threshold',
            'Use log10 safe calculation'
        ])
        self.zero_handling_combo.setCurrentText(self.molar_ratio_node.config.get('zero_handling', 'Skip particles with zero values'))
        self.zero_handling_combo.currentTextChanged.connect(self.on_config_changed)
        calc_layout.addRow("Zero Value Handling:", self.zero_handling_combo)
        
        self.outlier_filter_checkbox = QCheckBox()
        self.outlier_filter_checkbox.setChecked(self.molar_ratio_node.config.get('filter_outliers', True))
        self.outlier_filter_checkbox.stateChanged.connect(self.on_config_changed)
        calc_layout.addRow("Filter Extreme Outliers:", self.outlier_filter_checkbox)
        
        self.outlier_percentile_spin = QDoubleSpinBox()
        self.outlier_percentile_spin.setRange(90.0, 99.9)
        self.outlier_percentile_spin.setSingleStep(0.5)
        self.outlier_percentile_spin.setDecimals(1)
        self.outlier_percentile_spin.setValue(self.molar_ratio_node.config.get('outlier_percentile', 99.0))
        self.outlier_percentile_spin.valueChanged.connect(self.on_config_changed)
        calc_layout.addRow("Keep Below Percentile:", self.outlier_percentile_spin)
        
        layout.addWidget(calc_group)
        
        plot_group = QGroupBox("Plot Options")
        plot_layout = QFormLayout(plot_group)
        
        self.bins_spin = QSpinBox()
        self.bins_spin.setRange(10, 200)
        self.bins_spin.setValue(self.molar_ratio_node.config.get('bins', 50))
        self.bins_spin.valueChanged.connect(self.on_config_changed)
        plot_layout.addRow("Number of Bins:", self.bins_spin)
        
        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setRange(0.1, 1.0)
        self.alpha_spin.setSingleStep(0.1)
        self.alpha_spin.setDecimals(1)
        self.alpha_spin.setValue(self.molar_ratio_node.config.get('alpha', 0.7))
        self.alpha_spin.valueChanged.connect(self.on_config_changed)
        plot_layout.addRow("Transparency:", self.alpha_spin)
        
        self.bin_borders_checkbox = QCheckBox()
        self.bin_borders_checkbox.setChecked(self.molar_ratio_node.config.get('bin_borders', True))
        self.bin_borders_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Show Bin Borders:", self.bin_borders_checkbox)
        
        self.log_x_checkbox = QCheckBox()
        self.log_x_checkbox.setChecked(self.molar_ratio_node.config.get('log_x', True))
        self.log_x_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Log X-axis (Ratio):", self.log_x_checkbox)
        
        self.log_y_checkbox = QCheckBox()
        self.log_y_checkbox.setChecked(self.molar_ratio_node.config.get('log_y', False))
        self.log_y_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Log Y-axis (Count):", self.log_y_checkbox)
        
        self.show_stats_checkbox = QCheckBox()
        self.show_stats_checkbox.setChecked(self.molar_ratio_node.config.get('show_stats', True))
        self.show_stats_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Show Statistics:", self.show_stats_checkbox)
        
        self.show_curve_checkbox = QCheckBox()
        self.show_curve_checkbox.setChecked(self.molar_ratio_node.config.get('show_curve', True))
        self.show_curve_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Show Density Curve:", self.show_curve_checkbox)
        
        self.show_median_checkbox = QCheckBox()
        self.show_median_checkbox.setChecked(self.molar_ratio_node.config.get('show_median', True))
        self.show_median_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Show Median Line:", self.show_median_checkbox)
        
        self.show_mean_checkbox = QCheckBox()
        self.show_mean_checkbox.setChecked(self.molar_ratio_node.config.get('show_mean', True))
        self.show_mean_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Show Mean Line ± SD:", self.show_mean_checkbox)
        
        layout.addWidget(plot_group)
        
        font_group = QGroupBox("Font Settings")
        font_layout = QFormLayout(font_group)
        
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(self.get_font_families())
        self.font_family_combo.setCurrentText(self.molar_ratio_node.config.get('font_family', 'Times New Roman'))
        self.font_family_combo.currentTextChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Family:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(self.molar_ratio_node.config.get('font_size', 18))
        self.font_size_spin.valueChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Size:", self.font_size_spin)
        
        font_style_layout = QHBoxLayout()
        self.font_bold_checkbox = QCheckBox("Bold")
        self.font_bold_checkbox.setChecked(self.molar_ratio_node.config.get('font_bold', False))
        self.font_bold_checkbox.stateChanged.connect(self.on_config_changed)
        self.font_italic_checkbox = QCheckBox("Italic")
        self.font_italic_checkbox.setChecked(self.molar_ratio_node.config.get('font_italic', False))
        self.font_italic_checkbox.stateChanged.connect(self.on_config_changed)
        font_style_layout.addWidget(self.font_bold_checkbox)
        font_style_layout.addWidget(self.font_italic_checkbox)
        font_style_layout.addStretch()
        font_layout.addRow("Font Style:", font_style_layout)
        
        self.font_color_button = QPushButton()
        self.font_color = QColor(self.molar_ratio_node.config.get('font_color', '#000000'))
        self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 30px;")
        self.font_color_button.clicked.connect(lambda: self.choose_color('font'))
        font_layout.addRow("Font Color:", self.font_color_button)
        
        layout.addWidget(font_group)
        
        limits_group = QGroupBox("Axis Limits")
        limits_layout = QFormLayout(limits_group)
        
        x_layout = QHBoxLayout()
        self.x_min_spin = QDoubleSpinBox()
        self.x_min_spin.setRange(0.0001, 999999)
        self.x_min_spin.setDecimals(4)
        self.x_min_spin.setValue(self.molar_ratio_node.config.get('x_min', 0.01))
        self.x_min_spin.valueChanged.connect(self.on_config_changed)
        
        self.x_max_spin = QDoubleSpinBox()
        self.x_max_spin.setRange(0.0001, 999999)
        self.x_max_spin.setDecimals(4)
        self.x_max_spin.setValue(self.molar_ratio_node.config.get('x_max', 100.0))
        self.x_max_spin.valueChanged.connect(self.on_config_changed)
        
        self.auto_x_checkbox = QCheckBox("Auto")
        self.auto_x_checkbox.setChecked(self.molar_ratio_node.config.get('auto_x', True))
        self.auto_x_checkbox.stateChanged.connect(self.on_config_changed)
        self.auto_x_checkbox.stateChanged.connect(self.toggle_x_limits)
        
        x_layout.addWidget(self.x_min_spin)
        x_layout.addWidget(QLabel("to"))
        x_layout.addWidget(self.x_max_spin)
        x_layout.addWidget(self.auto_x_checkbox)
        limits_layout.addRow("X Range (Ratio):", x_layout)
        
        y_layout = QHBoxLayout()
        self.y_min_spin = QDoubleSpinBox()
        self.y_min_spin.setRange(0, 999999)
        self.y_min_spin.setValue(self.molar_ratio_node.config.get('y_min', 0))
        self.y_min_spin.valueChanged.connect(self.on_config_changed)
        
        self.y_max_spin = QDoubleSpinBox()
        self.y_max_spin.setRange(0, 999999)
        self.y_max_spin.setValue(self.molar_ratio_node.config.get('y_max', 100))
        self.y_max_spin.valueChanged.connect(self.on_config_changed)
        
        self.auto_y_checkbox = QCheckBox("Auto")
        self.auto_y_checkbox.setChecked(self.molar_ratio_node.config.get('auto_y', True))
        self.auto_y_checkbox.stateChanged.connect(self.on_config_changed)
        self.auto_y_checkbox.stateChanged.connect(self.toggle_y_limits)
        
        y_layout.addWidget(self.y_min_spin)
        y_layout.addWidget(QLabel("to"))
        y_layout.addWidget(self.y_max_spin)
        y_layout.addWidget(self.auto_y_checkbox)
        limits_layout.addRow("Y Range (Count):", y_layout)
        
        layout.addWidget(limits_group)
        
        if self.is_multiple_sample_data():
            self.sample_colors_group = QGroupBox("Sample Colors")
            self.sample_colors_layout = QVBoxLayout(self.sample_colors_group)
            self.update_sample_color_controls()
            layout.addWidget(self.sample_colors_group)
        
        self.update_element_options()
        
        self.toggle_x_limits()
        self.toggle_y_limits()
        
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
    
    def update_element_options(self):
        """
        Update available elements in combo boxes.
        
        Args:
            None
            
        Returns:
            None
        """
        available_elements = self.get_available_elements()
        
        current_num = self.numerator_combo.currentText()
        current_den = self.denominator_combo.currentText()
        
        self.numerator_combo.clear()
        self.denominator_combo.clear()
        
        if available_elements and len(available_elements) >= 2:
            self.numerator_combo.addItems(available_elements)
            self.denominator_combo.addItems(available_elements)
            
            if current_num in available_elements:
                self.numerator_combo.setCurrentText(current_num)
            else:
                self.numerator_combo.setCurrentText(available_elements[0])
                self.molar_ratio_node.config['numerator_element'] = available_elements[0]
                
            if current_den in available_elements:
                self.denominator_combo.setCurrentText(current_den)
            elif len(available_elements) > 1:
                self.denominator_combo.setCurrentText(available_elements[1])
                self.molar_ratio_node.config['denominator_element'] = available_elements[1]
            else:
                self.denominator_combo.setCurrentText(available_elements[0])
                self.molar_ratio_node.config['denominator_element'] = available_elements[0]
        else:
            self.numerator_combo.addItem("No elements available")
            self.denominator_combo.addItem("No elements available")
        
        self.update_ratio_display()
        
    def update_ratio_display(self):
        """
        Update the ratio display label.
        
        Args:
            None
            
        Returns:
            None
        """
        num_element = self.numerator_combo.currentText()
        den_element = self.denominator_combo.currentText()
        
        if num_element and den_element and num_element != "No elements available":
            ratio_text = f"Ratio: {num_element} / {den_element}"
        else:
            ratio_text = "Ratio: Select elements"
        
        self.ratio_display_label.setText(ratio_text)
    
    def on_element_changed(self):
        """
        Handle element selection change.
        
        Args:
            None
            
        Returns:
            None
        """
        self.update_ratio_display()
        self.on_config_changed()
    
    def choose_color(self, color_type):
        """
        Open color dialog for font color.
        
        Args:
            color_type (str): Type of color to change
            
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
        Apply font settings to a plot item.
        
        Args:
            plot_item: PyQtGraph plot item
            
        Returns:
            None
        """
        try:
            font_family = self.molar_ratio_node.config.get('font_family', 'Times New Roman')
            font_size = self.molar_ratio_node.config.get('font_size', 18)
            is_bold = self.molar_ratio_node.config.get('font_bold', False)
            is_italic = self.molar_ratio_node.config.get('font_italic', False)
            font_color = self.molar_ratio_node.config.get('font_color', '#000000')
            
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
            
            x_axis.update()
            y_axis.update()
            
        except Exception as e:
            print(f"Error applying plot settings: {e}")
    
    def on_data_type_changed(self):
        """
        Handle data type selection change.
        
        Args:
            None
            
        Returns:
            None
        """
        self.on_config_changed()
    
    def update_sample_color_controls(self):
        """
        Update color controls for multiple samples with editable names.
        
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
        
        sample_colors = self.molar_ratio_node.config.get('sample_colors', {})
        
        sample_name_mappings = self.molar_ratio_node.config.get('sample_name_mappings', {})
        
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
        
        self.molar_ratio_node.config['sample_colors'] = sample_colors
        self.molar_ratio_node.config['sample_name_mappings'] = sample_name_mappings

    def on_sample_name_changed(self, original_name, new_name):
        """
        Handle sample name change.
        
        Args:
            original_name (str): Original sample name
            new_name (str): New display name
            
        Returns:
            None
        """
        if 'sample_name_mappings' not in self.molar_ratio_node.config:
            self.molar_ratio_node.config['sample_name_mappings'] = {}
        
        self.molar_ratio_node.config['sample_name_mappings'][original_name] = new_name
        self.on_config_changed()

    def reset_sample_name(self, original_name):
        """
        Reset sample name to original.
        
        Args:
            original_name (str): Original sample name
            
        Returns:
            None
        """
        if original_name in self.sample_name_edits:
            self.sample_name_edits[original_name].setText(original_name)
        
        if 'sample_name_mappings' in self.molar_ratio_node.config:
            self.molar_ratio_node.config['sample_name_mappings'].pop(original_name, None)
        
        self.on_config_changed()

    def get_display_name(self, original_name):
        """
        Get display name for a sample.
        
        Args:
            original_name (str): Original sample name
            
        Returns:
            str: Display name for the sample
        """
        mappings = self.molar_ratio_node.config.get('sample_name_mappings', {})
        return mappings.get(original_name, original_name)
        
    def get_available_sample_names(self):
        """
        Get available sample names from input data.
        
        Args:
            None
            
        Returns:
            list: List of sample names
        """
        if self.is_multiple_sample_data():
            return self.molar_ratio_node.input_data.get('sample_names', [])
        return []
    
    def select_sample_color(self, sample_name, button):
        """
        Open color dialog for sample.
        
        Args:
            sample_name (str): Name of the sample
            button: Button widget to update
            
        Returns:
            None
        """
        current_color = self.molar_ratio_node.config.get('sample_colors', {}).get(sample_name, '#3B82F6')
        display_name = self.get_display_name(sample_name)
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {display_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'sample_colors' not in self.molar_ratio_node.config:
                self.molar_ratio_node.config['sample_colors'] = {}
            self.molar_ratio_node.config['sample_colors'][sample_name] = color_hex
            
            self.on_config_changed()
    
    def download_figure(self):
        """
        Download the current figure.
        
        Args:
            None
            
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Molar Ratio Plot",
            "molar_ratio_plot.png",
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
                                    f"Molar ratio plot saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", 
                                f"Failed to save:\n{str(e)}")

    def get_available_elements(self):
        """
        Get available elements from the molar ratio node data.
        
        Args:
            None
            
        Returns:
            list: List of available element labels
        """
        if hasattr(self.molar_ratio_node, 'extract_available_elements'):
            plot_data = self.molar_ratio_node.extract_available_elements()
            if plot_data:
                return plot_data
        
        if not self.molar_ratio_node.input_data:
            return []
        
        data_type = self.molar_ratio_node.input_data.get('type')
        
        if data_type in ['sample_data', 'multiple_sample_data']:
            selected_isotopes = self.molar_ratio_node.input_data.get('selected_isotopes', [])
            if selected_isotopes:
                return [isotope['label'] for isotope in selected_isotopes]
        
        return []
    
    def toggle_x_limits(self):
        """
        Enable or disable X-axis limit controls.
        
        Args:
            None
            
        Returns:
            None
        """
        auto_enabled = self.auto_x_checkbox.isChecked()
        self.x_min_spin.setEnabled(not auto_enabled)
        self.x_max_spin.setEnabled(not auto_enabled)
    
    def toggle_y_limits(self):
        """
        Enable or disable Y-axis limit controls.
        
        Args:
            None
            
        Returns:
            None
        """
        auto_enabled = self.auto_y_checkbox.isChecked()
        self.y_min_spin.setEnabled(not auto_enabled)
        self.y_max_spin.setEnabled(not auto_enabled)
        
    def create_plot_panel(self):
        """
        Create the plot panel with PyQtGraph.
        
        Args:
            None
            
        Returns:
            QFrame: Frame containing the plot widget
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
        Handle configuration changes.
        
        Args:
            None
            
        Returns:
            None
        """
        config_updates = {
            'data_type_display': self.data_type_combo.currentText(),
            'numerator_element': self.numerator_combo.currentText(),
            'denominator_element': self.denominator_combo.currentText(),
            'min_threshold': self.min_threshold_spin.value(),
            'zero_handling': self.zero_handling_combo.currentText(),
            'filter_outliers': self.outlier_filter_checkbox.isChecked(),
            'outlier_percentile': self.outlier_percentile_spin.value(),
            'bins': self.bins_spin.value(),
            'alpha': self.alpha_spin.value(),
            'bin_borders': self.bin_borders_checkbox.isChecked(),
            'log_x': self.log_x_checkbox.isChecked(),
            'log_y': self.log_y_checkbox.isChecked(),
            'show_stats': self.show_stats_checkbox.isChecked(),
            'show_curve': self.show_curve_checkbox.isChecked(),
            'show_median': self.show_median_checkbox.isChecked(),
            'show_mean': self.show_mean_checkbox.isChecked(),
            'x_min': self.x_min_spin.value(),
            'x_max': self.x_max_spin.value(),
            'auto_x': self.auto_x_checkbox.isChecked(),
            'y_min': self.y_min_spin.value(),
            'y_max': self.y_max_spin.value(),
            'auto_y': self.auto_y_checkbox.isChecked(),
            'font_family': self.font_family_combo.currentText(),
            'font_size': self.font_size_spin.value(),
            'font_bold': self.font_bold_checkbox.isChecked(),
            'font_italic': self.font_italic_checkbox.isChecked(),
            'font_color': self.font_color.name()
        }
        
        if self.is_multiple_sample_data():
            config_updates.update({
                'display_mode': self.display_mode_combo.currentText(),
                'normalize_samples': self.normalize_samples_checkbox.isChecked()
            })
        
        self.molar_ratio_node.config.update(config_updates)
        
        self.update_display()

    def create_font_for_text(self, config):
        """
        Create QFont object from config for text elements.
        
        Args:
            config (dict): Configuration dictionary
            
        Returns:
            QFont: Configured font object
        """
        font_family = config.get('font_family', 'Times New Roman')
        font_size = max(8, int(config.get('font_size', 18) * 0.8))
        is_bold = config.get('font_bold', False)
        is_italic = config.get('font_italic', False)
        
        font = QFont(font_family, font_size)
        font.setBold(is_bold)
        font.setItalic(is_italic)
        return font

    def set_axis_labels_with_font(self, plot_item, x_label, y_label, config):
        """
        Set axis labels with proper font formatting.
        
        Args:
            plot_item: PyQtGraph plot item
            x_label (str): X-axis label text
            y_label (str): Y-axis label text
            config (dict): Configuration dictionary
            
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
   
    def update_display(self):
        """
        Update the molar ratio plot display.
        
        Args:
            None
            
        Returns:
            None
        """
        try:
            if not hasattr(self, 'plot_widget') or self.plot_widget is None:
                print("Error: plot_widget not initialized")
                return
                
            self.plot_widget.clear()
            
            plot_data = self.molar_ratio_node.extract_plot_data()
            
            is_empty_data = False
            if plot_data is None:
                is_empty_data = True
            elif isinstance(plot_data, dict):
                is_empty_data = all(len(sample_data) == 0 if hasattr(sample_data, '__len__') else sample_data is None 
                                for sample_data in plot_data.values())
            elif hasattr(plot_data, '__len__'):
                is_empty_data = len(plot_data) == 0
            else:
                is_empty_data = True
                
            if is_empty_data:
                plot_item = self.plot_widget.addPlot()
                text_item = pg.TextItem("No molar ratio data available\nConnect to Sample Selector\nand select two elements", 
                                    anchor=(0.5, 0.5), color='gray')
                plot_item.addItem(text_item)
                text_item.setPos(0.5, 0.5)
                plot_item.hideAxis('left')
                plot_item.hideAxis('bottom')
            else:
                config = self.molar_ratio_node.config
                
                if self.is_multiple_sample_data():
                    self.create_multiple_sample_molar_ratio(plot_data, config)
                else:
                    plot_item = self.plot_widget.addPlot()
                    self.create_molar_ratio_plot(plot_item, plot_data, config)
                    self.apply_plot_settings(plot_item)
            
        except Exception as e:
            print(f"Error updating molar ratio display: {str(e)}")
            import traceback
            traceback.print_exc()
        
    def create_multiple_sample_molar_ratio(self, plot_data, config):
        """
        Create molar ratio plot for multiple samples.
        
        Args:
            plot_data (dict): Dictionary of sample names to ratio arrays
            config (dict): Configuration dictionary
            
        Returns:
            None
        """
        display_mode = config.get('display_mode', 'Overlaid (Different Colors)')
        sample_names = list(plot_data.keys())
        
        if display_mode == 'Individual Subplots':
            self.create_subplot_molar_ratios(plot_data, config)
        elif display_mode == 'Side by Side Subplots':
            self.create_side_by_side_molar_ratios(plot_data, config)
        else:
            plot_item = self.plot_widget.addPlot()
            self.create_combined_molar_ratio(plot_item, plot_data, config)
            self.apply_plot_settings(plot_item)
    
    def create_subplot_molar_ratios(self, plot_data, config):
        """
        Create individual subplots for each sample.
        
        Args:
            plot_data (dict): Dictionary of sample names to ratio arrays
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
            
            sample_ratios = plot_data[sample_name]
            if sample_ratios is not None and hasattr(sample_ratios, '__len__') and len(sample_ratios) > 0:
                sample_color = sample_colors.get(sample_name, default_colors[i % len(default_colors)])
                self.create_sample_molar_ratio(plot_item, sample_ratios, config, sample_color)
            
                title_text = f"{self.get_display_name(sample_name)}"
                plot_item.setTitle(title_text)
                
                numerator = config.get('numerator_element', 'Element1')
                denominator = config.get('denominator_element', 'Element2')
                log_x = config.get('log_x', True)
                log_y = config.get('log_y', False)
                
                x_label = f"log₁₀({numerator}/{denominator})" if log_x else f"{numerator}/{denominator}"
                y_label = f"log₁₀(Number of Particles)" if log_y else "Number of Particles"
                
                self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
                self.apply_plot_settings(plot_item)

    def create_side_by_side_molar_ratios(self, plot_data, config):
        """
        Create side-by-side molar ratio plots.
        
        Args:
            plot_data (dict): Dictionary of sample names to ratio arrays
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
            
            sample_ratios = plot_data[sample_name]
            if sample_ratios is not None and len(sample_ratios) > 0:
                sample_color = sample_colors.get(sample_name, default_colors[i % len(default_colors)])
                self.create_sample_molar_ratio(plot_item, sample_ratios, config, sample_color)
                
                title_text = f"{self.get_display_name(sample_name)}"
                plot_item.setTitle(title_text)
                
                numerator = config.get('numerator_element', 'Element1')
                denominator = config.get('denominator_element', 'Element2')
                log_x = config.get('log_x', True)
                log_y = config.get('log_y', False)
                
                x_label = f"log₁₀({numerator}/{denominator})" if log_x else f"{numerator}/{denominator}"
                y_label = f"log₁₀(Number of Particles)" if log_y else "Number of Particles"
                
                if i == 0:
                    self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
                else:
                    self.set_axis_labels_with_font(plot_item, x_label, "", config)
                
                self.apply_plot_settings(plot_item)
                
    def create_combined_molar_ratio(self, plot_item, plot_data, config):
        """
        Create combined molar ratio plot (overlaid).
        
        Args:
            plot_item: PyQtGraph plot item
            plot_data (dict): Dictionary of sample names to ratio arrays
            config (dict): Configuration dictionary
            
        Returns:
            None
        """
        sample_colors = config.get('sample_colors', {})
        default_colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
        
        legend_items = []
        
        for i, (sample_name, sample_ratios) in enumerate(plot_data.items()):
            if sample_ratios is not None and len(sample_ratios) > 0:
                sample_color = sample_colors.get(sample_name, default_colors[i % len(default_colors)])
                
                bins = config.get('bins', 50)
                log_x = config.get('log_x', True)
                log_y = config.get('log_y', False)
                
                plot_ratios = sample_ratios.copy()
                if log_x:
                    plot_ratios = np.log10(plot_ratios)
                
                y, bin_edges = np.histogram(plot_ratios, bins=bins)
                
                if log_y:
                    y = np.log10(y + 1)
                
                color_obj = QColor(sample_color)
                alpha = int(config.get('alpha', 0.7) * 255)
                color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), alpha)
                
                bin_borders = config.get('bin_borders', True)
                pen_width = 1 if bin_borders else 0
                pen_color = 'k' if bin_borders else sample_color
                
                bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
                bin_width = bin_edges[1] - bin_edges[0]
                bar_item = pg.BarGraphItem(x=bin_centers, height=y, width=bin_width,
                                        brush=pg.mkBrush(*color_rgba),
                                        pen=pg.mkPen(color=pen_color, width=pen_width))
                plot_item.addItem(bar_item)
                
                legend_items.append((bar_item, self.get_display_name(sample_name)))

        
        numerator = config.get('numerator_element', 'Element1')
        denominator = config.get('denominator_element', 'Element2')
        log_x = config.get('log_x', True)
        log_y = config.get('log_y', False)
        
        x_label = f"log₁₀({numerator}/{denominator})" if log_x else f"{numerator}/{denominator}"
        y_label = f"log₁₀(Number of Particles)" if log_y else "Number of Particles"
        
        self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
        
        if legend_items:
            legend = plot_item.addLegend()
            for item, name in legend_items:
                legend.addItem(item, name)

    def create_sample_molar_ratio(self, plot_item, ratios, config, sample_color):
        """
        Create molar ratio plot for a specific sample.
        
        Args:
            plot_item: PyQtGraph plot item
            ratios (np.ndarray): Array of ratio values
            config (dict): Configuration dictionary
            sample_color (str): Hex color code for sample
            
        Returns:
            None
        """
        if ratios is None or len(ratios) == 0:
            return
        
        bins = config.get('bins', 50)
        log_x = config.get('log_x', True)
        log_y = config.get('log_y', False)
        
        plot_ratios = ratios.copy()
        if log_x:
            plot_ratios = np.log10(plot_ratios)
        
        y, bin_edges = np.histogram(plot_ratios, bins=bins)
        
        if log_y:
            y = np.log10(y + 1)
        
        color_obj = QColor(sample_color)
        alpha = int(config.get('alpha', 0.7) * 255)
        color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), alpha)
        
        bin_borders = config.get('bin_borders', True)
        pen_width = 1 if bin_borders else 0
        pen_color = 'k' if bin_borders else sample_color
        
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        bin_width = bin_edges[1] - bin_edges[0]
        bar_item = pg.BarGraphItem(x=bin_centers, height=y, width=bin_width,
                                brush=pg.mkBrush(*color_rgba),
                                pen=pg.mkPen(color=pen_color, width=pen_width))
        plot_item.addItem(bar_item)
        
        if config.get('show_curve', True) and len(ratios) > 5:
            self.add_density_curve_to_plot(plot_item, plot_ratios, config, bin_edges, len(ratios))
        
        if config.get('show_median', True):
            self.add_median_line_to_plot(plot_item, plot_ratios, config)
        
        if config.get('show_mean', True):
            self.add_mean_line_to_plot(plot_item, plot_ratios, ratios, config)
        
        if not config.get('auto_x', True):
            x_min = config['x_min']
            x_max = config['x_max']
            if log_x:
                x_min = np.log10(x_min)
                x_max = np.log10(x_max)
            plot_item.setXRange(x_min, x_max)
        
        if not config.get('auto_y', True):
            y_min = config['y_min']
            y_max = config['y_max']
            if log_y:
                y_min = np.log10(y_min + 1)
                y_max = np.log10(y_max + 1)
            plot_item.setYRange(y_min, y_max)

    def create_molar_ratio_plot(self, plot_item, plot_data, config):
        """
        Create the molar ratio plot (single sample).
        
        Args:
            plot_item: PyQtGraph plot item
            plot_data (np.ndarray): Array of ratio values
            config (dict): Configuration dictionary
            
        Returns:
            None
        """
        if plot_data is None or len(plot_data) == 0:
            return
        
        bins = config.get('bins', 50)
        log_x = config.get('log_x', True)
        log_y = config.get('log_y', False)
        
        plot_ratios = plot_data.copy()
        if log_x:
            plot_ratios = np.log10(plot_ratios)
        
        y, bin_edges = np.histogram(plot_ratios, bins=bins)
        
        if log_y:
            y = np.log10(y + 1)
        
        color = '#663399'
        color_obj = QColor(color)
        alpha = int(config.get('alpha', 0.7) * 255)
        color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), alpha)
        
        bin_borders = config.get('bin_borders', True)
        pen_width = 1 if bin_borders else 0
        pen_color = 'k' if bin_borders else color
        
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        bin_width = bin_edges[1] - bin_edges[0]
        bar_item = pg.BarGraphItem(x=bin_centers, height=y, width=bin_width,
                                brush=pg.mkBrush(*color_rgba),
                                pen=pg.mkPen(color=pen_color, width=pen_width))
        plot_item.addItem(bar_item)
        
        if config.get('show_curve', True) and len(plot_data) > 5:
            self.add_density_curve_to_plot(plot_item, plot_ratios, config, bin_edges, len(plot_data))
        
        if config.get('show_median', True):
            self.add_median_line_to_plot(plot_item, plot_ratios, config)
        
        if config.get('show_mean', True):
            self.add_mean_line_to_plot(plot_item, plot_ratios, plot_data, config)
        
        numerator = config.get('numerator_element', 'Element1')
        denominator = config.get('denominator_element', 'Element2')
        
        x_label = f"log₁₀({numerator}/{denominator})" if log_x else f"{numerator}/{denominator}"
        y_label = f"log₁₀(Number of Particles)" if log_y else "Number of Particles"
        
        self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
        
        if not config.get('auto_x', True):
            x_min = config['x_min']
            x_max = config['x_max']
            if log_x:
                x_min = np.log10(x_min)
                x_max = np.log10(x_max)
            plot_item.setXRange(x_min, x_max)
        
        if not config.get('auto_y', True):
            y_min = config['y_min']
            y_max = config['y_max']
            if log_y:
                y_min = np.log10(y_min + 1)
                y_max = np.log10(y_max + 1)
            plot_item.setYRange(y_min, y_max)
        
        if config.get('show_stats', True):
            self.add_statistics_text(plot_item, plot_data, config)

    def add_density_curve_to_plot(self, plot_item, values, config, bin_edges, total_count):
        """
        Add density curve overlay scaled to match count histogram.
        
        Args:
            plot_item: PyQtGraph plot item
            values (np.ndarray): Array of values
            config (dict): Configuration dictionary
            bin_edges (np.ndarray): Histogram bin edges
            total_count (int): Total number of data points
            
        Returns:
            None
        """
        curve_color = '#2C3E50'
        
        try:
            if len(bin_edges) > 1:
                bin_width = bin_edges[1] - bin_edges[0]
            else:
                bin_width = 1.0
            
            x_min, x_max = min(values), max(values)
            x_range = x_max - x_min
            x_curve = np.linspace(x_min - 0.1*x_range, x_max + 0.1*x_range, 200)
            
            kde = gaussian_kde(values)
            y_curve = kde(x_curve)
            
            y_curve_scaled = y_curve * total_count * bin_width
            
            if config.get('log_y', False):
                y_curve_scaled = np.log10(y_curve_scaled + 1)
            
            curve_plot = pg.PlotDataItem(x=x_curve, y=y_curve_scaled, 
                                        pen=pg.mkPen(color=curve_color, width=2.5))
            plot_item.addItem(curve_plot)
            
        except Exception as e:
            print(f"Error creating density curve: {str(e)}")

    def add_median_line_to_plot(self, plot_item, values, config):
        """
        Add median vertical line with font-styled text.
        
        Args:
            plot_item: PyQtGraph plot item
            values (np.ndarray): Array of values
            config (dict): Configuration dictionary
            
        Returns:
            None
        """
        median_value = np.median(values)
        
        font_color = config.get('font_color', '#000000')
        
        median_line = pg.InfiniteLine(pos=median_value, angle=90, 
                                     pen=pg.mkPen(color=font_color, style=pg.QtCore.Qt.DashLine, width=2))
        plot_item.addItem(median_line)
        
        log_x = config.get('log_x', True)
        if log_x:
            original_median = 10**median_value
            median_text_str = f'median: {original_median:.3f}'
        else:
            median_text_str = f'median: {median_value:.3f}'
        
        median_text = pg.TextItem(median_text_str, anchor=(0, 1), color=font_color)
        
        try:
            font = self.create_font_for_text(config)
            median_text.setFont(font)
        except Exception as e:
            print(f"Error setting median text font: {e}")
        
        plot_item.addItem(median_text)
        
        view_box = plot_item.getViewBox()
        try:
            x_range = view_box.state['viewRange'][0]
            y_range = view_box.state['viewRange'][1]
            
            text_y = y_range[0] + 0.9 * (y_range[1] - y_range[0])
            median_text.setPos(median_value, text_y)
        except:
            median_text.setPos(median_value, 1)
            
    def add_mean_line_to_plot(self, plot_item, transformed_values, original_values, config):
        """
        Add mean vertical line with standard deviation bands and font-styled text.
        
        Args:
            plot_item: PyQtGraph plot item
            transformed_values (np.ndarray): Log-transformed values if applicable
            original_values (np.ndarray): Original ratio values
            config (dict): Configuration dictionary
            
        Returns:
            None
        """
        original_mean = np.mean(original_values)
        original_std = np.std(original_values)
        
        font_color = config.get('font_color', '#000000')
        log_x = config.get('log_x', True)
        
        if log_x:
            mean_value_display = np.log10(original_mean)
            mean_plus_std = original_mean + original_std
            mean_minus_std = max(original_mean - original_std, 0.001)
            mean_plus_std_display = np.log10(mean_plus_std)
            mean_minus_std_display = np.log10(mean_minus_std)
        else:
            mean_value_display = original_mean
            mean_plus_std_display = original_mean + original_std
            mean_minus_std_display = original_mean - original_std
        
        mean_line = pg.InfiniteLine(pos=mean_value_display, angle=90, 
                                pen=pg.mkPen(color=font_color, style=pg.QtCore.Qt.SolidLine, width=2))
        plot_item.addItem(mean_line)
        
        std_color = QColor(font_color)
        std_color.setAlpha(100)
        
        std_plus_line = pg.InfiniteLine(pos=mean_plus_std_display, angle=90,
                                    pen=pg.mkPen(color=std_color, style=pg.QtCore.Qt.DotLine, width=1))
        std_minus_line = pg.InfiniteLine(pos=mean_minus_std_display, angle=90,
                                        pen=pg.mkPen(color=std_color, style=pg.QtCore.Qt.DotLine, width=1))
        
        plot_item.addItem(std_plus_line)
        plot_item.addItem(std_minus_line)
        
        mean_text_str = f'mean ± SD: {original_mean:.1f} ± {original_std:.1f}'
        
        mean_text = pg.TextItem(mean_text_str, anchor=(0, 0), color=font_color)
        
        try:
            font = self.create_font_for_text(config)
            mean_text.setFont(font)
        except Exception as e:
            print(f"Error setting mean text font: {e}")
        
        plot_item.addItem(mean_text)
        
        view_box = plot_item.getViewBox()
        try:
            x_range = view_box.state['viewRange'][0]
            y_range = view_box.state['viewRange'][1]
            
            text_y = y_range[0] + 0.1 * (y_range[1] - y_range[0])
            mean_text.setPos(mean_value_display, text_y)
        except:
            mean_text.setPos(mean_value_display, 0.1)

    def add_statistics_text(self, plot_item, plot_data, config):
        """
        Add statistics text box to the plot with font formatting.
        
        Args:
            plot_item: PyQtGraph plot item
            plot_data (np.ndarray): Array of ratio values
            config (dict): Configuration dictionary
            
        Returns:
            None
        """
        if plot_data is None or len(plot_data) == 0:
            return
        
        numerator = config.get('numerator_element', 'Element1')
        denominator = config.get('denominator_element', 'Element2')
        log_x = config.get('log_x', True)
        font_color = config.get('font_color', '#000000')
        
        particle_count = len(plot_data)
        
        if log_x:
            original_ratios = 10**plot_data
            mean_value = np.mean(original_ratios)
            median_value = np.median(original_ratios)
            std_value = np.std(original_ratios)
            q1 = np.percentile(original_ratios, 25)
            q3 = np.percentile(original_ratios, 75)
        else:
            mean_value = np.mean(plot_data)
            median_value = np.median(plot_data)
            std_value = np.std(plot_data)
            q1 = np.percentile(plot_data, 25)
            q3 = np.percentile(plot_data, 75)
        
        stats_text = f"Molar Ratio Statistics:\n"
        stats_text += f"Ratio: {numerator}/{denominator}\n"
        stats_text += f"Particles: {particle_count}\n"
        stats_text += f"Mean: {mean_value:.3f} ± {std_value:.3f}\n"
        stats_text += f"Median: {median_value:.3f}\n"
        stats_text += f"Q1: {q1:.3f}, Q3: {q3:.3f}\n"
        
        stats_text_item = pg.TextItem(stats_text, anchor=(0, 1), 
                                    border=pg.mkPen(color=font_color, width=1),
                                    fill=pg.mkBrush(color=(255, 255, 255, 200)),
                                    color=font_color)
        
        try:
            font = self.create_font_for_text(config)
            stats_text_item.setFont(font)
        except Exception as e:
            print(f"Error setting statistics text font: {e}")
        
        plot_item.addItem(stats_text_item)
        
        view_box = plot_item.getViewBox()
        try:
            x_range = view_box.state['viewRange'][0]
            y_range = view_box.state['viewRange'][1]
            
            text_x = x_range[0] + 0.02 * (x_range[1] - x_range[0])
            text_y = y_range[0] + 0.98 * (y_range[1] - y_range[0])
            
            stats_text_item.setPos(text_x, text_y)
        except:
            stats_text_item.setPos(0.02, 0.98)
            
            
class MolarRatioPlotNode(QObject):
    
    position_changed = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        """
        Initialize molar ratio plot node.
        
        Args:
            parent_window: Parent window widget
            
        Returns:
            None
        """
        super().__init__()
        self.title = "Molar Ratio"
        self.node_type = "molar_ratio_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.config = {
            'data_type_display': 'Element Moles (fmol)',
            'numerator_element': '',
            'denominator_element': '',
            'min_threshold': 0.001,
            'zero_handling': 'Skip particles with zero values',
            'filter_outliers': True,
            'outlier_percentile': 99.0,
            'bins': 50,
            'alpha': 0.7,
            'bin_borders': True,
            'log_x': True,
            'log_y': False,
            'show_stats': True,
            'show_curve': True,
            'show_median': True,
            'show_mean': True,
            'x_min': 0.01,
            'x_max': 100.0,
            'auto_x': True,
            'y_min': 0,
            'y_max': 100,
            'auto_y': True,
            'display_mode': 'Overlaid (Different Colors)',
            'normalize_samples': False,
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
        Set node position.
        
        Args:
            pos: Position coordinate
            
        Returns:
            None
        """
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)
        
    def configure(self, parent_window):
        """
        Show configuration dialog.
        
        Args:
            parent_window: Parent window widget
            
        Returns:
            bool: True if configuration successful
        """
        dialog = MolarRatioDisplayDialog(self, parent_window)
        dialog.exec()
        return True
        
    def process_data(self, input_data):
        """
        Process input data and update molar ratio plot.
        
        Args:
            input_data (dict): Input data dictionary
            
        Returns:
            None
        """
        if not input_data:
            print("No input data received for molar ratio plot")
            return
            
        print(f"Molar ratio plot received data: {input_data.get('type', 'unknown')}")
        self.input_data = input_data
        
        self.configuration_changed.emit()
        
    def extract_available_elements(self):
        """
        Extract available elements for selection.
        
        Args:
            None
            
        Returns:
            list: List of available element labels
        """
        if not self.input_data:
            return []
        
        selected_isotopes = self.input_data.get('selected_isotopes', [])
        if selected_isotopes:
            return [isotope['label'] for isotope in selected_isotopes]
        
        return []
        
    def extract_plot_data(self):
        """
        Extract molar ratio data from input.
        
        Args:
            None
            
        Returns:
            np.ndarray or dict: Array of ratios or dictionary of sample ratios
        """
        if not self.input_data:
            return None
        
        numerator_element = self.config.get('numerator_element', '')
        denominator_element = self.config.get('denominator_element', '')
        
        if not numerator_element or not denominator_element:
            return None
        
        if numerator_element == denominator_element:
            print("Warning: Numerator and denominator elements are the same")
            return None
        
        data_type_display = self.config.get('data_type_display', 'Element Moles (fmol)')
        input_type = self.input_data.get('type')
        
        data_key_mapping = {
            'Element Moles (fmol)': 'element_moles_fmol',
            'Particle Moles (fmol)': 'particle_moles_fmol'
        }
        
        data_key = data_key_mapping.get(data_type_display, 'element_moles_fmol')
        
        if input_type == 'sample_data':
            return self._extract_single_sample_ratios(data_key, numerator_element, denominator_element)
        elif input_type == 'multiple_sample_data':
            return self._extract_multiple_sample_ratios(data_key, numerator_element, denominator_element)
            
        return None

    def _extract_single_sample_ratios(self, data_key, numerator_element, denominator_element):
        """
        Extract molar ratios for single sample.
        
        Args:
            data_key (str): Key for data type in particle dictionary
            numerator_element (str): Element for numerator
            denominator_element (str): Element for denominator
            
        Returns:
            np.ndarray: Array of calculated ratios
        """
        particles = self.input_data.get('particle_data')
        
        if not particles:
            print(f"No filtered particle data available from sample selector")
            return None
        
        ratios = []
        min_threshold = self.config.get('min_threshold', 0.001)
        zero_handling = self.config.get('zero_handling', 'Skip particles with zero values')
        
        for particle in particles:
            particle_data_dict = particle.get(data_key, {})
            
            numerator_value = particle_data_dict.get(numerator_element, 0)
            denominator_value = particle_data_dict.get(denominator_element, 0)
            
            if zero_handling == 'Skip particles with zero values':
                if numerator_value <= 0 or denominator_value <= 0 or np.isnan(numerator_value) or np.isnan(denominator_value):
                    continue
            elif zero_handling == 'Replace zeros with threshold':
                if numerator_value <= 0 or np.isnan(numerator_value):
                    numerator_value = min_threshold
                if denominator_value <= 0 or np.isnan(denominator_value):
                    denominator_value = min_threshold
            elif zero_handling == 'Use log10 safe calculation':
                if numerator_value <= 0 or np.isnan(numerator_value):
                    numerator_value = min_threshold
                if denominator_value <= 0 or np.isnan(denominator_value):
                    denominator_value = min_threshold
            
            if denominator_value > 0:
                ratio = numerator_value / denominator_value
                if ratio > 0 and not np.isnan(ratio) and not np.isinf(ratio):
                    ratios.append(ratio)
        
        if not ratios:
            return None
        
        if self.config.get('filter_outliers', True):
            percentile = self.config.get('outlier_percentile', 99.0)
            upper_limit = np.percentile(ratios, percentile)
            lower_limit = np.percentile(ratios, 100 - percentile)
            ratios = [r for r in ratios if lower_limit <= r <= upper_limit]
        
        return np.array(ratios)

    def _extract_multiple_sample_ratios(self, data_key, numerator_element, denominator_element):
        """
        Extract molar ratios for multiple samples.
        
        Args:
            data_key (str): Key for data type in particle dictionary
            numerator_element (str): Element for numerator
            denominator_element (str): Element for denominator
            
        Returns:
            dict: Dictionary mapping sample names to ratio arrays
        """
        particles = self.input_data.get('particle_data', [])
        
        if not particles:
            print("No filtered particle data available from sample selector")
            return None
        
        sample_names = self.input_data.get('sample_names', [])
        
        sample_ratios = {}
        for sample_name in sample_names:
            sample_ratios[sample_name] = []
        
        min_threshold = self.config.get('min_threshold', 0.001)
        zero_handling = self.config.get('zero_handling', 'Skip particles with zero values')
        
        for particle in particles:
            source_sample = particle.get('source_sample')
            if source_sample and source_sample in sample_ratios:
                particle_data_dict = particle.get(data_key, {})
                
                numerator_value = particle_data_dict.get(numerator_element, 0)
                denominator_value = particle_data_dict.get(denominator_element, 0)
                
                if zero_handling == 'Skip particles with zero values':
                    if numerator_value <= 0 or denominator_value <= 0 or np.isnan(numerator_value) or np.isnan(denominator_value):
                        continue
                elif zero_handling == 'Replace zeros with threshold':
                    if numerator_value <= 0 or np.isnan(numerator_value):
                        numerator_value = min_threshold
                    if denominator_value <= 0 or np.isnan(denominator_value):
                        denominator_value = min_threshold
                elif zero_handling == 'Use log10 safe calculation':
                    if numerator_value <= 0 or np.isnan(numerator_value):
                        numerator_value = min_threshold
                    if denominator_value <= 0 or np.isnan(denominator_value):
                        denominator_value = min_threshold
                
                if denominator_value > 0:
                    ratio = numerator_value / denominator_value
                    if ratio > 0 and not np.isnan(ratio) and not np.isinf(ratio):
                        sample_ratios[source_sample].append(ratio)
        
        if self.config.get('filter_outliers', True):
            percentile = self.config.get('outlier_percentile', 99.0)
            
            for sample_name, ratios in sample_ratios.items():
                if ratios:
                    upper_limit = np.percentile(ratios, percentile)
                    lower_limit = np.percentile(ratios, 100 - percentile)
                    filtered_ratios = [r for r in ratios if lower_limit <= r <= upper_limit]
                    sample_ratios[sample_name] = np.array(filtered_ratios) if filtered_ratios else np.array([])
                else:
                    sample_ratios[sample_name] = np.array([])
        else:
            for sample_name, ratios in sample_ratios.items():
                sample_ratios[sample_name] = np.array(ratios) if ratios else np.array([])
        
        sample_ratios = {k: v for k, v in sample_ratios.items() if len(v) > 0}
        return sample_ratios if sample_ratios else None