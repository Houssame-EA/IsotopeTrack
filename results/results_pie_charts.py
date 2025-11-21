from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                              QLabel, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                              QDialogButtonBox, QGroupBox, QColorDialog, QPushButton,
                              QLineEdit, QGraphicsProxyWidget, QFrame, QScrollArea, QWidget, QListWidgetItem, QListWidget, QMessageBox)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QPen, QFont
import numpy as np
import math
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter, SVGExporter
import numpy as np
import math


class PieChartDisplayDialog(QDialog):
    """
    Enhanced Dialog for pie chart visualization with PyQtGraph and multiple sample support.
    
    Provides interactive interface for visualizing element distribution as pie charts
    with support for single and multiple sample analysis, customizable fonts, colors,
    and display options.
    """
    
    def __init__(self, pie_chart_node, parent_window=None):
        """
        Initialize the pie chart display dialog.
        
        Args:
            pie_chart_node: Pie chart node instance containing configuration and data
            parent_window: Parent window widget (optional)
        
        Returns:
            None
        """
        super().__init__(parent_window)
        self.pie_chart_node = pie_chart_node
        self.parent_window = parent_window
        
        self.setWindowTitle("Element Distribution Pie Charts - Multi-Sample Analysis")
        self.setMinimumSize(1400, 800)
        
        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        self.setup_ui()
        self.update_display()
        
        self.pie_chart_node.configuration_changed.connect(self.update_display)
    
    def is_multiple_sample_data(self):
        """
        Check if dealing with multiple sample data.
        
        Args:
            None
        
        Returns:
            bool: True if input data is multiple sample type, False otherwise
        """
        return (hasattr(self.pie_chart_node, 'input_data') and 
                self.pie_chart_node.input_data and 
                self.pie_chart_node.input_data.get('type') == 'multiple_sample_data')
        
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
        
    def setup_ui(self):
        """
        Set up the user interface layout.
        
        Creates horizontal layout with configuration panel on left and plot panel on right.
        
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
        
    def create_config_panel(self):
        """
        Create the pie chart configuration panel with all settings.
        
        Creates scrollable panel containing all configuration options including
        multiple sample display modes, data type selection, chart type, font settings,
        label display options, threshold settings, and color controls.
        
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
        
        title = QLabel("Pie Chart Settings")
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
                'Individual Subplots', 
                'Side by Side Subplots',
                'Combined Distribution',
                'Overlaid Comparison'
            ])
            self.display_mode_combo.setCurrentText(self.pie_chart_node.config.get('display_mode', 'Individual Subplots'))
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
        self.data_type_combo.setCurrentText(self.pie_chart_node.config.get('data_type_display', 'Counts (Raw)'))
        self.data_type_combo.currentTextChanged.connect(self.on_data_type_changed)
        data_layout.addWidget(self.data_type_combo)
        
        layout.addWidget(data_group)
        
        chart_group = QGroupBox("Chart Type")
        chart_layout = QVBoxLayout(chart_group)
        
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems([
            'Element Distribution',
            'Particle Count Distribution'
        ])
        self.chart_type_combo.setCurrentText(self.pie_chart_node.config.get('chart_type', 'Element Distribution'))
        self.chart_type_combo.currentTextChanged.connect(self.on_config_changed)
        chart_layout.addWidget(self.chart_type_combo)
        
        self.data_info_label = QLabel()
        self.data_info_label.setStyleSheet("""
            QLabel {
                color: #059669;
                font-size: 10px;
                padding: 8px;
                background-color: rgba(236, 253, 245, 150);
                border-radius: 4px;
                border: 1px solid #10B981;
            }
        """)
        self.data_info_label.setWordWrap(True)
        self.update_data_info_label()
        chart_layout.addWidget(self.data_info_label)
        
        layout.addWidget(chart_group)
        
        font_group = QGroupBox("Font Settings")
        font_layout = QFormLayout(font_group)
        
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(self.get_font_families())
        self.font_family_combo.setCurrentText(self.pie_chart_node.config.get('font_family', 'Times New Roman'))
        self.font_family_combo.currentTextChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Family:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(self.pie_chart_node.config.get('font_size', 18))
        self.font_size_spin.valueChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Size:", self.font_size_spin)
        
        font_style_layout = QHBoxLayout()
        self.font_bold_checkbox = QCheckBox("Bold")
        self.font_bold_checkbox.setChecked(self.pie_chart_node.config.get('font_bold', False))
        self.font_bold_checkbox.stateChanged.connect(self.on_config_changed)
        self.font_italic_checkbox = QCheckBox("Italic")
        self.font_italic_checkbox.setChecked(self.pie_chart_node.config.get('font_italic', False))
        self.font_italic_checkbox.stateChanged.connect(self.on_config_changed)
        font_style_layout.addWidget(self.font_bold_checkbox)
        font_style_layout.addWidget(self.font_italic_checkbox)
        font_style_layout.addStretch()
        font_layout.addRow("Font Style:", font_style_layout)
        
        self.font_color_button = QPushButton()
        self.font_color = QColor(self.pie_chart_node.config.get('font_color', '#000000'))
        self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 30px;")
        self.font_color_button.clicked.connect(lambda: self.choose_color('font'))
        font_layout.addRow("Font Color:", self.font_color_button)
        
        layout.addWidget(font_group)
        
        label_group = QGroupBox("Label Display Options")
        label_layout = QFormLayout(label_group)
        
        self.show_counts_checkbox = QCheckBox()
        self.show_counts_checkbox.setChecked(self.pie_chart_node.config.get('show_counts', True))
        self.show_counts_checkbox.stateChanged.connect(self.on_config_changed)
        label_layout.addRow("Show Particle Counts:", self.show_counts_checkbox)
        
        self.show_percentages_checkbox = QCheckBox()
        self.show_percentages_checkbox.setChecked(self.pie_chart_node.config.get('show_percentages', True))
        self.show_percentages_checkbox.stateChanged.connect(self.on_config_changed)
        label_layout.addRow("Show Percentages:", self.show_percentages_checkbox)
        
        self.smart_labels_checkbox = QCheckBox()
        self.smart_labels_checkbox.setChecked(self.pie_chart_node.config.get('smart_labels', True))
        self.smart_labels_checkbox.stateChanged.connect(self.on_config_changed)
        label_layout.addRow("Smart Label Positioning:", self.smart_labels_checkbox)
        
        self.show_lines_checkbox = QCheckBox()
        self.show_lines_checkbox.setChecked(self.pie_chart_node.config.get('show_connection_lines', True))
        self.show_lines_checkbox.stateChanged.connect(self.on_config_changed)
        label_layout.addRow("Show Connection Lines:", self.show_lines_checkbox)
        
        layout.addWidget(label_group)
        
        threshold_group = QGroupBox("Threshold Settings")
        threshold_layout = QFormLayout(threshold_group)
        
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 50.0)
        self.threshold_spin.setSingleStep(0.1)
        self.threshold_spin.setDecimals(1)
        self.threshold_spin.setSuffix(" %")
        self.threshold_spin.setValue(self.pie_chart_node.config.get('threshold', 1.0))
        self.threshold_spin.valueChanged.connect(self.on_config_changed)
        threshold_layout.addRow("Threshold for 'Others':", self.threshold_spin)
        
        self.filter_zeros_checkbox = QCheckBox()
        self.filter_zeros_checkbox.setChecked(self.pie_chart_node.config.get('filter_zeros', True))
        self.filter_zeros_checkbox.stateChanged.connect(self.on_config_changed)
        threshold_layout.addRow("Filter Zero Values:", self.filter_zeros_checkbox)
        
        layout.addWidget(threshold_group)
        
        if self.is_multiple_sample_data():
            self.sample_colors_group = QGroupBox("Sample Colors")
            self.sample_colors_layout = QVBoxLayout(self.sample_colors_group)
            self.update_sample_color_controls()
            layout.addWidget(self.sample_colors_group)
        
        self.colors_group = QGroupBox("Element Colors")
        self.colors_layout = QVBoxLayout(self.colors_group)
        self.update_color_controls()
        layout.addWidget(self.colors_group)
        
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
        Apply font settings to PyQtGraph plot item including title and axes.
        
        Args:
            plot_item: PyQtGraph PlotItem to apply settings to
        
        Returns:
            None
        """
        try:
            font_family = self.pie_chart_node.config.get('font_family', 'Times New Roman')
            font_size = self.pie_chart_node.config.get('font_size', 18)
            is_bold = self.pie_chart_node.config.get('font_bold', False)
            is_italic = self.pie_chart_node.config.get('font_italic', False)
            font_color = self.pie_chart_node.config.get('font_color', '#000000')
            
            font = QFont(font_family, font_size)
            font.setBold(is_bold)
            font.setItalic(is_italic)
            
            if hasattr(plot_item, 'titleLabel') and plot_item.titleLabel is not None:
                plot_item.titleLabel.item.setFont(font)
                plot_item.titleLabel.item.setDefaultTextColor(QColor(font_color))
            
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
        self.update_data_info_label()
        self.on_config_changed()
    
    def update_sample_color_controls(self):
        """
        Update color controls for multiple samples with editable names.
        
        Creates color picker buttons and name edit fields for each sample with
        reset functionality for custom names.
        
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
        
        sample_colors = self.pie_chart_node.config.get('sample_colors', {})
        
        sample_name_mappings = self.pie_chart_node.config.get('sample_name_mappings', {})
        
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
        
        self.pie_chart_node.config['sample_colors'] = sample_colors
        self.pie_chart_node.config['sample_name_mappings'] = sample_name_mappings

    def on_sample_name_changed(self, original_name, new_name):
        """
        Handle sample name change event.
        
        Args:
            original_name (str): Original sample name
            new_name (str): New custom display name
        
        Returns:
            None
        """
        if 'sample_name_mappings' not in self.pie_chart_node.config:
            self.pie_chart_node.config['sample_name_mappings'] = {}
        
        self.pie_chart_node.config['sample_name_mappings'][original_name] = new_name
        
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
        
        if 'sample_name_mappings' in self.pie_chart_node.config:
            self.pie_chart_node.config['sample_name_mappings'].pop(original_name, None)
        
        self.on_config_changed()

    def get_display_name(self, original_name):
        """
        Get display name for a sample (either custom or original).
        
        Args:
            original_name (str): Original sample name
        
        Returns:
            str: Display name (custom if set, otherwise original)
        """
        mappings = self.pie_chart_node.config.get('sample_name_mappings', {})
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
            return self.pie_chart_node.input_data.get('sample_names', [])
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
        current_color = self.pie_chart_node.config.get('sample_colors', {}).get(sample_name, '#3B82F6')
        display_name = self.get_display_name(sample_name)
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {display_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'sample_colors' not in self.pie_chart_node.config:
                self.pie_chart_node.config['sample_colors'] = {}
            self.pie_chart_node.config['sample_colors'][sample_name] = color_hex
            
            self.on_config_changed()
    
    def update_data_info_label(self):
        """
        Update the data availability info label.
        
        Args:
            None
        
        Returns:
            None
        """
        if not self.pie_chart_node.input_data:
            info_text = "⚠️ No data source connected\nConnect a Sample Selector node"
        elif self.is_multiple_sample_data():
            sample_count = len(self.get_available_sample_names())
            data_type = self.data_type_combo.currentText()
            info_text = f"ℹ️ Source: {sample_count} samples\nData Type: {data_type}"
        else:
            data_type = self.data_type_combo.currentText()
            info_text = f"ℹ️ Single sample analysis\nData Type: {data_type}"
        
        self.data_info_label.setText(info_text)
    
    def download_figure(self):
        """
        Download the current figure using PyQtGraph exporters.
        
        Supports PNG and SVG export formats with automatic detection of plot items.
        
        Args:
            None
        
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Pie Chart Plot",
            "pie_chart_plot.png",
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
                                    f"Pie chart saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", 
                                f"Failed to save:\n{str(e)}")
    
    def update_color_controls(self):
        """
        Update color controls based on available elements.
        
        Creates color picker buttons for each element with default color assignment.
        
        Args:
            None
        
        Returns:
            None
        """
        for i in reversed(range(self.colors_layout.count())):
            self.colors_layout.itemAt(i).widget().deleteLater()
        
        available_elements = self.get_available_elements()
        
        if not available_elements:
            no_data_label = QLabel("No elements available\nConnect data source")
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet("color: gray; font-style: italic;")
            self.colors_layout.addWidget(no_data_label)
            return
        
        default_colors = [
            '#FF6347', '#FFD700', '#FFA500', '#20B2AA', '#00BFFF',
            '#F0E68C', '#E0FFFF', '#AFEEEE', '#DDA0DD', '#FFE4E1',
            '#FAEBD7', '#D3D3D3', '#90EE90', '#FFB6C1', '#FFA07A'
        ]
        
        element_colors = self.pie_chart_node.config.get('element_colors', {})
        
        for i, element_name in enumerate(available_elements):
            element_layout = QHBoxLayout()
            
            label = QLabel(element_name)
            label.setFixedWidth(100)
            element_layout.addWidget(label)
            
            color_button = QPushButton()
            color_button.setFixedSize(30, 20)
            
            if element_name in element_colors:
                color = element_colors[element_name]
            else:
                color = default_colors[i % len(default_colors)]
                element_colors[element_name] = color
            
            color_button.setStyleSheet(f"background-color: {color}; border: 1px solid black;")
            color_button.clicked.connect(lambda checked, elem=element_name, btn=color_button: self.select_element_color(elem, btn))
            
            element_layout.addWidget(color_button)
            element_layout.addStretch()
            
            container = QWidget()
            container.setLayout(element_layout)
            self.colors_layout.addWidget(container)
        
        self.pie_chart_node.config['element_colors'] = element_colors
    
    def get_available_elements(self):
        """
        Get available elements from the pie chart node's data.
        
        Attempts to extract elements from plot data first, then falls back to input data.
        
        Args:
            None
        
        Returns:
            list: List of available element label strings
        """
        if hasattr(self.pie_chart_node, 'extract_plot_data'):
            try:
                plot_data = self.pie_chart_node.extract_plot_data()
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
        
        if not self.pie_chart_node.input_data:
            return []
        
        data_type = self.pie_chart_node.input_data.get('type')
        
        if data_type in ['sample_data', 'multiple_sample_data']:
            selected_isotopes = self.pie_chart_node.input_data.get('selected_isotopes', [])
            if selected_isotopes:
                return [isotope['label'] for isotope in selected_isotopes]
        
        return []
        
    def select_element_color(self, element_name, button):
        """
        Open color dialog for element color selection.
        
        Args:
            element_name (str): Name of the element to set color for
            button (QPushButton): Button widget to update with new color
        
        Returns:
            None
        """
        current_color = self.pie_chart_node.config.get('element_colors', {}).get(element_name, '#FF6347')
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {element_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'element_colors' not in self.pie_chart_node.config:
                self.pie_chart_node.config['element_colors'] = {}
            self.pie_chart_node.config['element_colors'][element_name] = color_hex
            
            self.on_config_changed()
    
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
        
        Collects all configuration values from UI controls and triggers plot update.
        
        Args:
            None
        
        Returns:
            None
        """
        config_updates = {
            'chart_type': self.chart_type_combo.currentText(),
            'data_type_display': self.data_type_combo.currentText(),
            'threshold': self.threshold_spin.value(),
            'filter_zeros': self.filter_zeros_checkbox.isChecked(),
            'font_family': self.font_family_combo.currentText(),
            'font_size': self.font_size_spin.value(),
            'font_bold': self.font_bold_checkbox.isChecked(),
            'font_italic': self.font_italic_checkbox.isChecked(),
            'font_color': self.font_color.name(),
            'show_counts': self.show_counts_checkbox.isChecked(),
            'show_percentages': self.show_percentages_checkbox.isChecked(),
            'smart_labels': self.smart_labels_checkbox.isChecked(),
            'show_connection_lines': self.show_lines_checkbox.isChecked()
        }
        
        if self.is_multiple_sample_data():
            config_updates.update({
                'display_mode': self.display_mode_combo.currentText()
            })
        
        self.pie_chart_node.config.update(config_updates)
        
        self.update_display()
    
    def update_display(self):
        """
        Update the pie chart display with PyQtGraph support.
        
        Clears existing plot and recreates based on current configuration and data.
        Handles both single and multiple sample modes.
        
        Args:
            None
        
        Returns:
            None
        """
        try:
            self.update_data_info_label()
            
            self.plot_widget.clear()
            
            plot_data = self.pie_chart_node.extract_plot_data()
            
            if not plot_data:
                plot_item = self.plot_widget.addPlot()
                text_item = pg.TextItem("No particle data available\nConnect to Sample Selector\nand run particle detection", 
                                      anchor=(0.5, 0.5), color='gray')
                plot_item.addItem(text_item)
                text_item.setPos(0.5, 0.5)
                plot_item.hideAxis('left')
                plot_item.hideAxis('bottom')
            else:
                config = self.pie_chart_node.config
                
                if self.is_multiple_sample_data():
                    self.create_multiple_sample_pie_charts(plot_data, config)
                else:
                    plot_item = self.plot_widget.addPlot()
                    chart_type = config.get('chart_type', 'Element Distribution')
                    data_type_display = config.get('data_type_display', 'Counts (Raw)')
                    
                    if chart_type == 'Particle Count Distribution':
                        data = self.calculate_particle_count_distribution_single(plot_data, config)
                        title = f'Particle Count Distribution ({data_type_display})'
                    else:
                        data = self.calculate_element_distribution_single(plot_data, config)
                        title = f'Element Distribution ({data_type_display})'
                    
                    if data:
                        self.create_pyqtgraph_pie_chart(plot_item, data, config, title)
                    
                    self.apply_plot_settings(plot_item)
            
        except Exception as e:
            print(f"Error updating pie chart display: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def create_multiple_sample_pie_charts(self, plot_data, config):
        """
        Create pie charts for multiple samples with different display modes.
        
        Args:
            plot_data (dict): Dictionary of sample data with particle count information
            config (dict): Configuration dictionary with display settings
        
        Returns:
            None
        """
        display_mode = config.get('display_mode', 'Individual Subplots')
        sample_names = list(plot_data.keys())
        
        if display_mode == 'Individual Subplots':
            self.create_subplot_pie_charts_fixed(plot_data, config)
        elif display_mode == 'Side by Side Subplots':
            self.create_side_by_side_pie_charts_fixed(plot_data, config)
        elif display_mode == 'Combined Distribution':
            self.create_combined_distribution_pie_chart_fixed(plot_data, config)
        else:
            self.create_overlaid_comparison_pie_charts_fixed(plot_data, config)

    def create_subplot_pie_charts_fixed(self, plot_data, config):
        """
        Create individual subplots for each sample with particle count labels.
        
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
        
        for i, sample_name in enumerate(sample_names):
            row = i // cols
            col = i % cols
            plot_item = self.plot_widget.addPlot(row=row, col=col)
            
            sample_data = plot_data[sample_name]
            if sample_data and 'element_data' in sample_data:
                chart_type = config.get('chart_type', 'Element Distribution')
                
                if chart_type == 'Particle Count Distribution':
                    data = self.calculate_particle_count_distribution_single(sample_data, config)
                else:
                    data = self.calculate_element_distribution_single(sample_data, config)
                
                if data:
                    display_name = self.get_display_name(sample_name)
                    self.create_pyqtgraph_pie_chart_with_fixed_labels(plot_item, data, sample_data, config, display_name)
                
                self.apply_plot_settings(plot_item)
                
    def create_pyqtgraph_pie_chart_with_fixed_labels(self, plot_item, data, sample_data, config, title):
        """
        Create custom pie chart using PyQtGraph with particle count labels.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            data (dict): Element data dictionary with values
            sample_data (dict): Sample data dictionary with element_data DataFrame
            config (dict): Configuration dictionary with display settings
            title (str): Chart title string
        
        Returns:
            None
        """
        if not data:
            return
        
        total = sum(data.values())
        percentages = {k: (v/total)*100 for k, v in data.items()}
        
        threshold = config.get('threshold', 1.0)
        main_elements = {k: v for k, v in percentages.items() if v >= threshold}
        others = {k: v for k, v in percentages.items() if v < threshold}
        
        if others:
            main_elements['Others'] = sum(others.values())
        
        sorted_elements = sorted(main_elements.items(), key=lambda x: x[1], reverse=True)
        
        labels = [item[0] for item in sorted_elements]
        sizes = [item[1] for item in sorted_elements]
        
        particle_counts = {}
        element_data = sample_data.get('element_data')
        
        if element_data is not None:
            for label in labels:
                if label == 'Others':
                    particle_count = 0
                    for element_name in others.keys():
                        if element_name in element_data.columns:
                            particle_count += (element_data[element_name] > 0).sum()
                    particle_counts[label] = particle_count
                else:
                    if label in element_data.columns:
                        particle_counts[label] = (element_data[label] > 0).sum()
                    else:
                        particle_counts[label] = 0
        else:
            for label in labels:
                if label == 'Others':
                    particle_counts[label] = sum(data[k] for k in others.keys())
                else:
                    particle_counts[label] = data[label]
        
        element_colors = config.get('element_colors', {})
        default_colors = ['#FF6347', '#FFD700', '#FFA500', '#20B2AA', '#00BFFF', 
                        '#F0E68C', '#E0FFFF', '#AFEEEE', '#DDA0DD', '#FFE4E1']
        
        colors = []
        for i, label in enumerate(labels):
            if label in element_colors:
                colors.append(element_colors[label])
            elif label == 'Others':
                colors.append('#808080')
            else:
                colors.append(default_colors[i % len(default_colors)])
        
        self.draw_pie_chart_with_pyqtgraph_fixed(plot_item, labels, sizes, particle_counts, colors, config)
        
        plot_item.setTitle(title)
        
        plot_item.hideAxis('left')
        plot_item.hideAxis('bottom')
        
        plot_item.setAspectLocked(True)
        
        plot_item.setRange(xRange=[-1.5, 1.5], yRange=[-1.5, 1.5])

    
    def create_side_by_side_pie_charts(self, plot_data, config):
        """
        Create side-by-side pie charts for multiple samples.
        
        Args:
            plot_data (dict): Dictionary of sample data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_names = list(plot_data.keys())
        n_samples = len(sample_names)
        
        for i, sample_name in enumerate(sample_names):
            plot_item = self.plot_widget.addPlot(row=0, col=i)
            
            sample_data = plot_data[sample_name]
            if sample_data and 'element_data' in sample_data:
                chart_type = config.get('chart_type', 'Element Distribution')
                
                if chart_type == 'Particle Count Distribution':
                    data = self.calculate_particle_count_distribution_single(sample_data, config)
                else:
                    data = self.calculate_element_distribution_single(sample_data, config)
                
                if data:
                    display_name = self.get_display_name(sample_name)
                    self.create_pyqtgraph_pie_chart(plot_item, data, config, display_name)
                
                self.apply_plot_settings(plot_item)
    
    def create_combined_distribution_pie_chart(self, plot_data, config):
        """
        Create a single pie chart combining all samples.
        
        Args:
            plot_data (dict): Dictionary of sample data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        plot_item = self.plot_widget.addPlot()
        
        combined_data = {}
        chart_type = config.get('chart_type', 'Element Distribution')
        
        for sample_name, sample_data in plot_data.items():
            if sample_data and 'element_data' in sample_data:
                if chart_type == 'Particle Count Distribution':
                    data = self.calculate_particle_count_distribution_single(sample_data, config)
                else:
                    data = self.calculate_element_distribution_single(sample_data, config)
                
                for element, value in data.items():
                    combined_data[element] = combined_data.get(element, 0) + value
        
        if combined_data:
            title = f"Combined ({len(plot_data)} samples)"
            self.create_pyqtgraph_pie_chart(plot_item, combined_data, config, title)
        
        self.apply_plot_settings(plot_item)
    
    def create_overlaid_comparison_pie_charts(self, plot_data, config):
        """
        Create overlaid comparison charts for first two samples.
        
        Args:
            plot_data (dict): Dictionary of sample data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_names = list(plot_data.keys())
        n_samples = len(sample_names)
        
        plot_item1 = self.plot_widget.addPlot(row=0, col=0)
        plot_item2 = self.plot_widget.addPlot(row=0, col=1)
        
        if n_samples >= 2:
            for i, (plot_item, sample_name) in enumerate(zip([plot_item1, plot_item2], sample_names[:2])):
                sample_data = plot_data[sample_name]
                if sample_data and 'element_data' in sample_data:
                    chart_type = config.get('chart_type', 'Element Distribution')
                    
                    if chart_type == 'Particle Count Distribution':
                        data = self.calculate_particle_count_distribution_single(sample_data, config)
                    else:
                        data = self.calculate_element_distribution_single(sample_data, config)
                    
                    if data:
                        display_name = self.get_display_name(sample_name)
                        self.create_pyqtgraph_pie_chart(plot_item, data, config, display_name)
                    
                    self.apply_plot_settings(plot_item)
    
    def calculate_particle_count_distribution_single(self, sample_data, config):
        """
        Calculate actual particle count (number of particles with each element > 0).
        
        Args:
            sample_data (dict): Sample data dictionary with element_data DataFrame
            config (dict): Configuration dictionary with filter settings
        
        Returns:
            dict: Dictionary mapping element names to particle counts
        """
        element_data = sample_data.get('element_data')
        if element_data is None:
            return {}
        
        if config.get('filter_zeros', True):
            filtered_data = element_data[element_data > 0]
        else:
            filtered_data = element_data
        
        count_totals = {}
        for element_label in element_data.columns:
            particle_count = (element_data[element_label] > 0).sum()
            if particle_count > 0:
                count_totals[element_label] = particle_count
        
        return count_totals
    
    def calculate_element_distribution_single(self, sample_data, config):
        """
        Calculate element distribution based on chart type.
        
        Args:
            sample_data (dict): Sample data dictionary with element_data DataFrame
            config (dict): Configuration dictionary with chart type and filter settings
        
        Returns:
            dict: Dictionary mapping element names to summed values or particle counts
        """
        element_data = sample_data.get('element_data')
        if element_data is None:
            return {}
        
        if config.get('filter_zeros', True):
            filtered_data = element_data[element_data > 0]
        else:
            filtered_data = element_data
        
        chart_type = config.get('chart_type', 'Element Distribution')
        
        if chart_type == 'Particle Count Distribution':
            element_totals = {}
            for element_label in element_data.columns:
                particle_count = (element_data[element_label] > 0).sum()
                if particle_count > 0:
                    element_totals[element_label] = particle_count
        else:
            element_totals = {}
            for element_label in filtered_data.columns:
                element_total = filtered_data[element_label].sum()
                if element_total > 0:
                    element_totals[element_label] = element_total
        
        return element_totals
    
    def create_pyqtgraph_pie_chart(self, plot_item, data, config, title):
        """
        Create custom pie chart using PyQtGraph with particle counts.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            data (dict): Element data dictionary with values
            config (dict): Configuration dictionary with display settings
            title (str): Chart title string
        
        Returns:
            None
        """
        if not data:
            return
        
        total = sum(data.values())
        percentages = {k: (v/total)*100 for k, v in data.items()}
        
        threshold = config.get('threshold', 1.0)
        main_elements = {k: v for k, v in percentages.items() if v >= threshold}
        others = {k: v for k, v in percentages.items() if v < threshold}
        
        if others:
            main_elements['Others'] = sum(others.values())
        
        sorted_elements = sorted(main_elements.items(), key=lambda x: x[1], reverse=True)
        
        labels = [item[0] for item in sorted_elements]
        sizes = [item[1] for item in sorted_elements]
        
        original_counts = {}
        
        plot_data = self.pie_chart_node.extract_plot_data()
        if plot_data and 'element_data' in plot_data:
            element_data = plot_data['element_data']
            
            for label in labels:
                if label == 'Others':
                    particle_count = 0
                    for element_name in others.keys():
                        if element_name in element_data.columns:
                            particle_count += (element_data[element_name] > 0).sum()
                    original_counts[label] = particle_count
                else:
                    if label in element_data.columns:
                        original_counts[label] = (element_data[label] > 0).sum()
                    else:
                        original_counts[label] = 0
        else:
            for label in labels:
                if label == 'Others':
                    original_counts[label] = sum(data[k] for k in others.keys())
                else:
                    original_counts[label] = data[label]
        
        element_colors = config.get('element_colors', {})
        default_colors = ['#FF6347', '#FFD700', '#FFA500', '#20B2AA', '#00BFFF', 
                        '#F0E68C', '#E0FFFF', '#AFEEEE', '#DDA0DD', '#FFE4E1']
        
        colors = []
        for i, label in enumerate(labels):
            if label in element_colors:
                colors.append(element_colors[label])
            elif label == 'Others':
                colors.append('#808080')
            else:
                colors.append(default_colors[i % len(default_colors)])
        
        self.draw_pie_chart_with_pyqtgraph_fixed(plot_item, labels, sizes, original_counts, colors, config)
        
        plot_item.setTitle(title)
        
        plot_item.hideAxis('left')
        plot_item.hideAxis('bottom')
        
        plot_item.setAspectLocked(True)
        
        plot_item.setRange(xRange=[-1.5, 1.5], yRange=[-1.5, 1.5])
        
    def draw_pie_chart_with_pyqtgraph_fixed(self, plot_item, labels, sizes, original_counts, colors, config):
        """
        Draw pie chart using PyQtGraph with polygons and particle count labels.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            labels (list): List of element label strings
            sizes (list): List of percentage values for each element
            original_counts (dict): Dictionary mapping labels to particle counts
            colors (list): List of color hex strings for each element
            config (dict): Configuration dictionary with label display settings
        
        Returns:
            None
        """
        if not sizes:
            return
        
        angles = [(size / 100.0) * 360 for size in sizes]
        
        start_angle = 90
        
        font_family = config.get('font_family', 'Times New Roman')
        font_size = max(8, config.get('font_size', 18) - 6)
        is_bold = config.get('font_bold', False)
        is_italic = config.get('font_italic', False)
        font_color = config.get('font_color', '#000000')
        
        text_font = QFont(font_family, font_size)
        text_font.setBold(is_bold)
        text_font.setItalic(is_italic)
        
        show_counts = config.get('show_counts', True)
        show_percentages = config.get('show_percentages', True)
        smart_labels = config.get('smart_labels', True)
        show_lines = config.get('show_connection_lines', True)
        
        for i, (label, angle, size, color) in enumerate(zip(labels, angles, sizes, colors)):
            end_angle = start_angle + angle
            
            start_rad = math.radians(start_angle)
            end_rad = math.radians(end_angle)
            
            radius = 1.0
            segments = max(16, int(angle / 3))
            
            wedge_x = [0]
            wedge_y = [0]
            
            for j in range(segments + 1):
                t = j / segments
                current_angle = start_rad + t * (end_rad - start_rad)
                x = radius * math.cos(current_angle)
                y = radius * math.sin(current_angle)
                wedge_x.append(x)
                wedge_y.append(y)
            
            wedge_x.append(0)
            wedge_y.append(0)
            
            wedge_item = pg.PlotDataItem(wedge_x, wedge_y, 
                                        pen=pg.mkPen('white', width=2),
                                        brush=pg.mkBrush(color),
                                        fillLevel=0)
            plot_item.addItem(wedge_item)
            
            particle_count = original_counts[label]
            
            mid_angle_rad = math.radians(start_angle + angle / 2)
            
            if smart_labels and size > 10:
                label_radius = 0.6
                label_x = label_radius * math.cos(mid_angle_rad)
                label_y = label_radius * math.sin(mid_angle_rad)
                
                if show_counts and show_percentages:
                    display_text = f'{label}\n({particle_count:,} particles) {size:.1f}%'
                elif show_counts:
                    display_text = f'{label}\n({particle_count:,} particles)'
                elif show_percentages:
                    display_text = f'{label}\n{size:.1f}%'
                else:
                    display_text = label
                
                text_item = pg.TextItem(display_text, anchor=(0.5, 0.5), color=font_color)
                
                if hasattr(text_item, 'textItem'):
                    text_item.textItem.setFont(text_font)
                elif hasattr(text_item, 'item'):
                    text_item.item.setFont(text_font)
                
                text_item.setPos(label_x, label_y)
                plot_item.addItem(text_item)
                
            else:
                inside_radius = 1.05
                outside_radius = 1.3
                
                inside_x = inside_radius * math.cos(mid_angle_rad)
                inside_y = inside_radius * math.sin(mid_angle_rad)
                outside_x = outside_radius * math.cos(mid_angle_rad)
                outside_y = outside_radius * math.sin(mid_angle_rad)
                
                if show_lines:
                    line_data = pg.PlotDataItem([inside_x, outside_x], [inside_y, outside_y], 
                                            pen=pg.mkPen('gray', width=1))
                    plot_item.addItem(line_data)
                
                if show_counts and show_percentages:
                    display_text = f'{label}\n({particle_count:,} particles) {size:.1f}%'
                elif show_counts:
                    display_text = f'{label}\n({particle_count:,} particles)'
                elif show_percentages:
                    display_text = f'{label}\n{size:.1f}%'
                else:
                    display_text = label
                
                if outside_x > 0:
                    anchor = (0, 0.5)
                else:
                    anchor = (1, 0.5)
                
                text_item = pg.TextItem(display_text, anchor=anchor, color=font_color)
                
                if hasattr(text_item, 'textItem'):
                    text_item.textItem.setFont(text_font)
                elif hasattr(text_item, 'item'):
                    text_item.item.setFont(text_font)
                
                text_item.setPos(outside_x, outside_y)
                plot_item.addItem(text_item)
            
            start_angle = end_angle


class PieChartPlotNode(QObject):
    """
    Enhanced Pie chart plot node with PyQtGraph and multiple sample support.
    
    Manages pie chart plotting configuration and data processing for both single
    and multiple sample workflows. Connects to visual node system and provides
    data extraction capabilities.
    """
    
    position_changed = Signal(object)
    configuration_changed = Signal()
    
    def __init__(self, parent_window=None):
        """
        Initialize pie chart plot node.
        
        Args:
            parent_window: Parent window widget for accessing application context
        
        Returns:
            None
        """
        super().__init__()
        self.title = "Element Distribution"
        self.node_type = "pie_chart_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.config = {
            'chart_type': 'Element Distribution',
            'data_type_display': 'Counts (Raw)',
            'threshold': 1.0,
            'filter_zeros': True,
            'element_colors': {},
            'display_mode': 'Individual Subplots',
            'sample_colors': {},
            'sample_name_mappings': {},
            'font_family': 'Times New Roman',
            'font_size': 18,
            'font_bold': False,
            'font_italic': False,
            'font_color': '#000000',
            'show_counts': True,
            'show_percentages': True,
            'smart_labels': True,
            'show_connection_lines': True
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
        
        Args:
            parent_window: Parent window widget
        
        Returns:
            bool: True if configuration was successful
        """
        dialog = PieChartDisplayDialog(self, parent_window)
        dialog.exec()
        return True
        
    def process_data(self, input_data):
        """
        Process input data and update pie chart.
        
        Receives data from connected nodes and triggers visual updates.
        
        Args:
            input_data (dict): Input data dictionary from upstream nodes
        
        Returns:
            None
        """
        if not input_data:
            print("No input data received for pie chart")
            return
            
        print(f"Pie chart received data: {input_data.get('type', 'unknown')}")
        self.input_data = input_data
        
        
        self.configuration_changed.emit()
        
    
    def extract_plot_data(self):
        """
        Extract plottable data from input creating particle-by-element matrices.
        
        Creates DataFrames where rows are particles and columns are elements,
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
        
        Args:
            data_key (str): Key for data type in particle dictionary
        
        Returns:
            dict or None: Dictionary with element_data DataFrame, or None if extraction fails
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
            
            return {
                'element_data': element_df
            }
            
        except Exception as e:
            print(f"Error in _extract_single_sample_data: {str(e)}")
            return None

    def _extract_multiple_sample_data(self, data_key):
        """
        Extract data for multiple samples creating particle-by-element matrix for each sample.
        
        Args:
            data_key (str): Key for data type in particle dictionary
        
        Returns:
            dict or None: Dictionary mapping sample names to data dictionaries, or None if extraction fails
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
            
            return sample_data
            
        except Exception as e:
            print(f"Error in _extract_multiple_sample_data: {str(e)}")
            return None
    

class ElementCompositionDisplayDialog(QDialog):
    """
    Enhanced Dialog for element composition visualization with PyQtGraph and multiple sample support.
    
    Provides interactive interface for visualizing element combinations as pie charts with
    support for single and multiple sample analysis, threshold filtering, and customizable display.
    """
    
    def __init__(self, composition_node, parent_window=None):
        """
        Initialize the element composition display dialog.
        
        Args:
            composition_node: Element composition node instance containing configuration and data
            parent_window: Parent window widget (optional)
        
        Returns:
            None
        """
        super().__init__(parent_window)
        self.composition_node = composition_node
        self.parent_window = parent_window
        
        self.setWindowTitle("Element Combination Analysis - Multi-Sample Support")
        self.setMinimumSize(1600, 900)
        
        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        self.setup_ui()
        self.update_display()
        
        self.composition_node.configuration_changed.connect(self.update_display)
    
    def is_multiple_sample_data(self):
        """
        Check if dealing with multiple sample data.
        
        Args:
            None
        
        Returns:
            bool: True if input data is multiple sample type, False otherwise
        """
        return (hasattr(self.composition_node, 'input_data') and 
                self.composition_node.input_data and 
                self.composition_node.input_data.get('type') == 'multiple_sample_data')
    
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
        
    def setup_ui(self):
        """
        Set up the user interface layout.
        
        Creates horizontal layout with configuration panel on left and plot panel on right.
        
        Args:
            None
        
        Returns:
            None
        """
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        config_panel = self.create_config_panel()
        config_panel.setFixedWidth(580)
        layout.addWidget(config_panel)
        
        plot_panel = self.create_plot_panel()
        layout.addWidget(plot_panel, stretch=1)
        
    def create_config_panel(self):
        """
        Create the composition configuration panel with all settings.
        
        Creates scrollable panel containing all configuration options including
        multiple sample display modes, data type selection, analysis type, element
        selection, font settings, threshold settings, display options, and color controls.
        
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
        layout.setSpacing(10)
        
        title = QLabel("Element Composition Settings")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #1F2937;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(title)
        
        if self.is_multiple_sample_data():
            multiple_group = QGroupBox("Multiple Sample Display")
            multiple_layout = QFormLayout(multiple_group)
            
            self.display_mode_combo = QComboBox()
            self.display_mode_combo.addItems([
                'Individual Subplots', 
                'Side by Side Subplots',
                'Combined Analysis',
                'Comparative View'
            ])
            self.display_mode_combo.setCurrentText(self.composition_node.config.get('display_mode', 'Individual Subplots'))
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
        self.data_type_combo.setCurrentText(self.composition_node.config.get('data_type_display', 'Counts (Raw)'))
        self.data_type_combo.currentTextChanged.connect(self.on_data_type_changed)
        data_layout.addWidget(self.data_type_combo)
        
        self.calibration_info_label = QLabel()
        self.update_calibration_info_label()
        data_layout.addWidget(self.calibration_info_label)
        
        layout.addWidget(data_group)
        
        analysis_group = QGroupBox("Analysis Type")
        analysis_layout = QVBoxLayout(analysis_group)
        
        self.analysis_type_combo = QComboBox()
        self.analysis_type_combo.addItems([
            'Single vs Multiple Elements',
            'Specific Element Combinations',
            'Element Distribution by Data Type'
        ])
        self.analysis_type_combo.setCurrentText(self.composition_node.config.get('analysis_type', 'Single vs Multiple Elements'))
        self.analysis_type_combo.currentTextChanged.connect(self.on_config_changed)
        analysis_layout.addWidget(self.analysis_type_combo)
        
        layout.addWidget(analysis_group)
        
        element_group = QGroupBox("Element Selection")
        element_layout = QVBoxLayout(element_group)
        
        available_elements = self.get_available_elements()
        
        self.elements_to_analyze = QListWidget()
        self.elements_to_analyze.setSelectionMode(QListWidget.MultiSelection)
        self.elements_to_analyze.setMaximumHeight(120)
        
        for element in available_elements:
            item = QListWidgetItem(element)
            self.elements_to_analyze.addItem(item)
            item.setSelected(True)
        
        self.elements_to_analyze.itemSelectionChanged.connect(self.on_config_changed)
        element_layout.addWidget(QLabel("Elements to Analyze:"))
        element_layout.addWidget(self.elements_to_analyze)
        
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_elements)
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_all_elements)
        
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(clear_btn)
        element_layout.addLayout(button_layout)
        
        layout.addWidget(element_group)
        
        font_group = QGroupBox("Font Settings")
        font_layout = QFormLayout(font_group)
        
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(self.get_font_families())
        self.font_family_combo.setCurrentText(self.composition_node.config.get('font_family', 'Times New Roman'))
        self.font_family_combo.currentTextChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Family:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(self.composition_node.config.get('font_size', 18))
        self.font_size_spin.valueChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Size:", self.font_size_spin)
        
        font_style_layout = QHBoxLayout()
        self.font_bold_checkbox = QCheckBox("Bold")
        self.font_bold_checkbox.setChecked(self.composition_node.config.get('font_bold', False))
        self.font_bold_checkbox.stateChanged.connect(self.on_config_changed)
        self.font_italic_checkbox = QCheckBox("Italic")
        self.font_italic_checkbox.setChecked(self.composition_node.config.get('font_italic', False))
        self.font_italic_checkbox.stateChanged.connect(self.on_config_changed)
        font_style_layout.addWidget(self.font_bold_checkbox)
        font_style_layout.addWidget(self.font_italic_checkbox)
        font_style_layout.addStretch()
        font_layout.addRow("Font Style:", font_style_layout)
        
        self.font_color_button = QPushButton()
        self.font_color = QColor(self.composition_node.config.get('font_color', '#000000'))
        self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 30px;")
        self.font_color_button.clicked.connect(lambda: self.choose_color('font'))
        font_layout.addRow("Font Color:", self.font_color_button)
        
        layout.addWidget(font_group)
        
        threshold_group = QGroupBox("Threshold Settings")
        threshold_layout = QFormLayout(threshold_group)
        
        self.particle_threshold_spin = QSpinBox()
        self.particle_threshold_spin.setRange(1, 10000)
        self.particle_threshold_spin.setValue(self.composition_node.config.get('particle_threshold', 10))
        self.particle_threshold_spin.valueChanged.connect(self.on_config_changed)
        threshold_layout.addRow("Min Particle Count:", self.particle_threshold_spin)
        
        self.percentage_threshold_spin = QDoubleSpinBox()
        self.percentage_threshold_spin.setRange(0.0, 50.0)
        self.percentage_threshold_spin.setSingleStep(0.1)
        self.percentage_threshold_spin.setDecimals(1)
        self.percentage_threshold_spin.setSuffix(" %")
        self.percentage_threshold_spin.setValue(self.composition_node.config.get('percentage_threshold', 1.0))
        self.percentage_threshold_spin.valueChanged.connect(self.on_config_changed)
        threshold_layout.addRow("Min Percentage:", self.percentage_threshold_spin)
        
        self.filter_zeros_checkbox = QCheckBox()
        self.filter_zeros_checkbox.setChecked(self.composition_node.config.get('filter_zeros', True))
        self.filter_zeros_checkbox.stateChanged.connect(self.on_config_changed)
        threshold_layout.addRow("Filter Zero Values:", self.filter_zeros_checkbox)
        
        layout.addWidget(threshold_group)
        
        display_group = QGroupBox("Display Options")
        display_layout = QFormLayout(display_group)
        
        self.show_data_values_checkbox = QCheckBox()
        self.show_data_values_checkbox.setChecked(self.composition_node.config.get('show_data_values', True))
        self.show_data_values_checkbox.stateChanged.connect(self.on_config_changed)
        display_layout.addRow("Show Data Values:", self.show_data_values_checkbox)
        
        self.show_counts_checkbox = QCheckBox()
        self.show_counts_checkbox.setChecked(self.composition_node.config.get('show_counts', True))
        self.show_counts_checkbox.stateChanged.connect(self.on_config_changed)
        display_layout.addRow("Show Particle Counts:", self.show_counts_checkbox)
        
        self.show_percentages_checkbox = QCheckBox()
        self.show_percentages_checkbox.setChecked(self.composition_node.config.get('show_percentages', True))
        self.show_percentages_checkbox.stateChanged.connect(self.on_config_changed)
        display_layout.addRow("Show Percentages:", self.show_percentages_checkbox)
        
        self.show_element_percentages_checkbox = QCheckBox()
        self.show_element_percentages_checkbox.setChecked(self.composition_node.config.get('show_element_percentages', False))
        self.show_element_percentages_checkbox.stateChanged.connect(self.on_config_changed)
        display_layout.addRow("Show Element % in Combinations:", self.show_element_percentages_checkbox)
        
        self.smart_labels_checkbox = QCheckBox()
        self.smart_labels_checkbox.setChecked(self.composition_node.config.get('smart_labels', True))
        self.smart_labels_checkbox.stateChanged.connect(self.on_config_changed)
        display_layout.addRow("Smart Label Positioning:", self.smart_labels_checkbox)
        
        self.show_lines_checkbox = QCheckBox()
        self.show_lines_checkbox.setChecked(self.composition_node.config.get('show_connection_lines', True))
        self.show_lines_checkbox.stateChanged.connect(self.on_config_changed)
        display_layout.addRow("Show Connection Lines:", self.show_lines_checkbox)
        
        layout.addWidget(display_group)
        
        if self.is_multiple_sample_data():
            self.sample_colors_group = QGroupBox("Sample Colors")
            self.sample_colors_layout = QVBoxLayout(self.sample_colors_group)
            self.update_sample_color_controls()
            layout.addWidget(self.sample_colors_group)
        
        self.colors_group = QGroupBox("Element Combination Colors")
        self.colors_layout = QVBoxLayout(self.colors_group)
        self.update_color_controls()
        layout.addWidget(self.colors_group)
        
        button_layout = QHBoxLayout()

        download_button = QPushButton("Download Figure")
        download_button.setStyleSheet("""
            QPushButton {
                background-color: #80D8C3;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
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
        Apply font settings to PyQtGraph plot item including title and axes.
        
        Args:
            plot_item: PyQtGraph PlotItem to apply settings to
        
        Returns:
            None
        """
        try:
            font_family = self.composition_node.config.get('font_family', 'Times New Roman')
            font_size = self.composition_node.config.get('font_size', 18)
            is_bold = self.composition_node.config.get('font_bold', False)
            is_italic = self.composition_node.config.get('font_italic', False)
            font_color = self.composition_node.config.get('font_color', '#000000')
            
            font = QFont(font_family, font_size)
            font.setBold(is_bold)
            font.setItalic(is_italic)
            
            if hasattr(plot_item, 'titleLabel') and plot_item.titleLabel is not None:
                plot_item.titleLabel.item.setFont(font)
                plot_item.titleLabel.item.setDefaultTextColor(QColor(font_color))
            
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
        self.update_calibration_info_label()
        self.on_config_changed()
    
    def update_sample_color_controls(self):
        """
        Update color controls for multiple samples.
        
        Creates color picker buttons for each sample with default color assignment.
        
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
        
        sample_colors = self.composition_node.config.get('sample_colors', {})
        
        for i, sample_name in enumerate(sample_names):
            sample_layout = QHBoxLayout()
            
            label = QLabel(sample_name[:20] + "..." if len(sample_name) > 20 else sample_name)
            label.setFixedWidth(150)
            sample_layout.addWidget(label)
            
            color_button = QPushButton()
            color_button.setFixedSize(30, 20)
            
            if sample_name in sample_colors:
                color = sample_colors[sample_name]
            else:
                color = default_sample_colors[i % len(default_sample_colors)]
                sample_colors[sample_name] = color
            
            color_button.setStyleSheet(f"background-color: {color}; border: 1px solid black;")
            color_button.clicked.connect(lambda checked, sample=sample_name, btn=color_button: self.select_sample_color(sample, btn))
            
            sample_layout.addWidget(color_button)
            sample_layout.addStretch()
            
            container = QWidget()
            container.setLayout(sample_layout)
            self.sample_colors_layout.addWidget(container)
        
        self.composition_node.config['sample_colors'] = sample_colors
    
    def get_available_sample_names(self):
        """
        Get available sample names from input data.
        
        Args:
            None
        
        Returns:
            list: List of sample name strings
        """
        if self.is_multiple_sample_data():
            return self.composition_node.input_data.get('sample_names', [])
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
        current_color = self.composition_node.config.get('sample_colors', {}).get(sample_name, '#3B82F6')
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {sample_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'sample_colors' not in self.composition_node.config:
                self.composition_node.config['sample_colors'] = {}
            self.composition_node.config['sample_colors'][sample_name] = color_hex
            
            self.on_config_changed()
    
    def update_calibration_info_label(self):
        """
        Update the calibration and data type info label.
        
        Args:
            None
        
        Returns:
            None
        """
        data_type = self.data_type_combo.currentText()
        
        if not self.composition_node.input_data:
            info_text = "⚠️ No data source connected\nConnect a Sample Selector node"
        elif self.is_multiple_sample_data():
            sample_count = len(self.get_available_sample_names())
            info_text = f"ℹ️ Source: {sample_count} samples\nData Type: {data_type}"
        else:
            info_text = f"ℹ️ Single sample analysis\nData Type: {data_type}"
        
        if data_type == 'Counts (Raw)':
            info_text += "\nPercentages: Based on particle counts"
        else:
            info_text += f"\nPercentages: Based on {data_type.lower()}"
        
        style = """
            QLabel {
                color: #059669;
                font-size: 10px;
                padding: 8px;
                background-color: rgba(236, 253, 245, 150);
                border-radius: 4px;
                border: 1px solid #10B981;
            }
        """
        
        self.calibration_info_label.setText(info_text)
        self.calibration_info_label.setStyleSheet(style)
        self.calibration_info_label.setWordWrap(True)
    
    def download_figure(self):
        """
        Download the current figure using PyQtGraph exporters.
        
        Supports PNG and SVG export formats with automatic detection of plot items.
        
        Args:
            None
        
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Element Composition Plot",
            "element_composition_plot.png",
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
                                    f"Element composition plot saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", 
                                f"Failed to save:\n{str(e)}")
    
    def get_available_elements(self):
        """
        Get available elements from the composition node's data.
        
        Attempts to extract elements from plot data first, then falls back to input data.
        
        Args:
            None
        
        Returns:
            list: List of available element label strings
        """
        if hasattr(self.composition_node, 'extract_plot_data'):
            try:
                plot_data = self.composition_node.extract_plot_data()
                if plot_data:
                    if self.is_multiple_sample_data():
                        all_elements = set()
                        for sample_data in plot_data.values():
                            if isinstance(sample_data, dict):
                                for combination_info in sample_data.values():
                                    if isinstance(combination_info, dict) and 'elements' in combination_info:
                                        all_elements.update(combination_info['elements'].keys())
                        return sorted(list(all_elements))
                    else:
                        all_elements = set()
                        for combination_info in plot_data.values():
                            if isinstance(combination_info, dict) and 'elements' in combination_info:
                                all_elements.update(combination_info['elements'].keys())
                        return sorted(list(all_elements))
            except:
                pass
        
        if not self.composition_node.input_data:
            return []
        
        data_type = self.composition_node.input_data.get('type')
        
        if data_type in ['sample_data', 'multiple_sample_data']:
            selected_isotopes = self.composition_node.input_data.get('selected_isotopes', [])
            if selected_isotopes:
                return [isotope['label'] for isotope in selected_isotopes]
        
        return []
        
    def select_all_elements(self):
        """
        Select all elements in the element list.
        
        Args:
            None
        
        Returns:
            None
        """
        for i in range(self.elements_to_analyze.count()):
            item = self.elements_to_analyze.item(i)
            item.setSelected(True)
        self.on_config_changed()
    
    def clear_all_elements(self):
        """
        Clear all element selections in the element list.
        
        Args:
            None
        
        Returns:
            None
        """
        for i in range(self.elements_to_analyze.count()):
            item = self.elements_to_analyze.item(i)
            item.setSelected(False)
        self.on_config_changed()
    
    def update_color_controls(self):
        """
        Update color controls for actual element combinations from data.
        
        Creates color picker buttons for each combination with particle count display,
        limited to top 15 combinations to avoid UI clutter.
        
        Args:
            None
        
        Returns:
            None
        """
        for i in reversed(range(self.colors_layout.count())):
            self.colors_layout.itemAt(i).widget().deleteLater()
        
        actual_combinations = self.get_actual_combinations()
        
        if not actual_combinations:
            no_data_label = QLabel("No combinations available\nConnect data source and select elements")
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet("color: gray; font-style: italic;")
            self.colors_layout.addWidget(no_data_label)
            return
        
        default_colors = [
            '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
            '#FF6B35', '#FFD700', '#20B2AA', '#FF69B4', '#32CD32',
            '#FF4500', '#9370DB', '#00CED1', '#FF1493', '#00FF7F'
        ]
        
        combination_colors = self.composition_node.config.get('combination_colors', {})
        
        display_combinations = list(actual_combinations.keys())[:15]
        
        for i, combination in enumerate(display_combinations):
            combo_layout = QHBoxLayout()
            
            display_combo = combination if len(combination) <= 30 else combination[:27] + "..."
            label = QLabel(display_combo)
            label.setFixedWidth(200)
            label.setToolTip(combination)
            combo_layout.addWidget(label)
            
            color_button = QPushButton()
            color_button.setFixedSize(30, 20)
            
            if combination in combination_colors:
                color = combination_colors[combination]
            else:
                color = default_colors[i % len(default_colors)]
                combination_colors[combination] = color
            
            color_button.setStyleSheet(f"background-color: {color}; border: 1px solid black;")
            color_button.clicked.connect(lambda checked, combo=combination, btn=color_button: self.select_combination_color(combo, btn))
            
            combo_layout.addWidget(color_button)
            
            combo_info = actual_combinations[combination]
            if isinstance(combo_info, dict):
                count = combo_info.get('particle_count', 0)
            else:
                count = combo_info
            count_label = QLabel(f"({count})")
            count_label.setStyleSheet("color: #6B7280; font-size: 10px;")
            combo_layout.addWidget(count_label)
            
            combo_layout.addStretch()
            
            container = QWidget()
            container.setLayout(combo_layout)
            self.colors_layout.addWidget(container)
        
        if len(actual_combinations) > 15:
            others_layout = QHBoxLayout()
            others_label = QLabel("Others (remaining combinations)")
            others_label.setFixedWidth(200)
            others_layout.addWidget(others_label)
            
            others_button = QPushButton()
            others_button.setFixedSize(30, 20)
            
            others_color = combination_colors.get('Others', '#808080')
            others_button.setStyleSheet(f"background-color: {others_color}; border: 1px solid black;")
            others_button.clicked.connect(lambda checked, btn=others_button: self.select_combination_color('Others', btn))
            
            others_layout.addWidget(others_button)
            others_layout.addStretch()
            
            others_container = QWidget()
            others_container.setLayout(others_layout)
            self.colors_layout.addWidget(others_container)
        
        self.composition_node.config['combination_colors'] = combination_colors
    
    def get_actual_combinations(self):
        """
        Get actual element combinations from current data with particle counts.
        
        Args:
            None
        
        Returns:
            dict: Dictionary mapping combination names to particle count info
        """
        plot_data = self.composition_node.extract_plot_data()
        if plot_data:
            if self.is_multiple_sample_data():
                all_combinations = {}
                for sample_data in plot_data.values():
                    if isinstance(sample_data, dict):
                        for combo, combo_info in sample_data.items():
                            if isinstance(combo_info, dict):
                                if combo not in all_combinations:
                                    all_combinations[combo] = {
                                        'particle_count': 0,
                                        'data_value': 0,
                                        'elements': combo_info.get('elements', {})
                                    }
                                all_combinations[combo]['particle_count'] += combo_info.get('particle_count', 0)
                                all_combinations[combo]['data_value'] += combo_info.get('data_value', 0)
                            else:
                                all_combinations[combo] = all_combinations.get(combo, 0) + combo_info
                return dict(sorted(all_combinations.items(), key=lambda x: x[1]['particle_count'] if isinstance(x[1], dict) else x[1], reverse=True))
            else:
                return dict(sorted(plot_data.items(), key=lambda x: x[1]['particle_count'] if isinstance(x[1], dict) else x[1], reverse=True))
        return {}
    
    def select_combination_color(self, combo_type, button):
        """
        Open color dialog for combination type color selection.
        
        Args:
            combo_type (str): Name of the combination type to set color for
            button (QPushButton): Button widget to update with new color
        
        Returns:
            None
        """
        current_color = self.composition_node.config.get('combination_colors', {}).get(combo_type, '#3B82F6')
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {combo_type}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'combination_colors' not in self.composition_node.config:
                self.composition_node.config['combination_colors'] = {}
            self.composition_node.config['combination_colors'][combo_type] = color_hex
            
            self.on_config_changed()
    
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
        
        Collects all configuration values from UI controls and triggers plot update.
        
        Args:
            None
        
        Returns:
            None
        """
        selected_elements = []
        for i in range(self.elements_to_analyze.count()):
            item = self.elements_to_analyze.item(i)
            if item.isSelected():
                selected_elements.append(item.text())
        
        config_updates = {
            'analysis_type': self.analysis_type_combo.currentText(),
            'data_type_display': self.data_type_combo.currentText(),
            'selected_elements': selected_elements,
            'particle_threshold': self.particle_threshold_spin.value(),
            'percentage_threshold': self.percentage_threshold_spin.value(),
            'filter_zeros': self.filter_zeros_checkbox.isChecked(),
            'show_data_values': self.show_data_values_checkbox.isChecked(),
            'show_counts': self.show_counts_checkbox.isChecked(),
            'show_percentages': self.show_percentages_checkbox.isChecked(),
            'show_element_percentages': self.show_element_percentages_checkbox.isChecked(),
            'font_family': self.font_family_combo.currentText(),
            'font_size': self.font_size_spin.value(),
            'font_bold': self.font_bold_checkbox.isChecked(),
            'font_italic': self.font_italic_checkbox.isChecked(),
            'font_color': self.font_color.name(),
            'smart_labels': self.smart_labels_checkbox.isChecked(),
            'show_connection_lines': self.show_lines_checkbox.isChecked()
        }
        
        if self.is_multiple_sample_data():
            config_updates.update({
                'display_mode': self.display_mode_combo.currentText()
            })
        
        self.composition_node.config.update(config_updates)
        
        self.update_color_controls()
        
        self.update_display()
    
    def update_display(self):
        """
        Update the composition display with PyQtGraph support.
        
        Clears existing plot and recreates based on current configuration and data.
        Handles both single and multiple sample modes.
        
        Args:
            None
        
        Returns:
            None
        """
        try:
            self.update_calibration_info_label()
            
            self.plot_widget.clear()
            
            plot_data = self.composition_node.extract_plot_data()
            
            if not plot_data:
                plot_item = self.plot_widget.addPlot()
                text_item = pg.TextItem("No particle data available\nConnect to Sample Selector\nSelect elements to analyze", 
                                      anchor=(0.5, 0.5), color='gray')
                plot_item.addItem(text_item)
                text_item.setPos(0.5, 0.5)
                plot_item.hideAxis('left')
                plot_item.hideAxis('bottom')
            else:
                config = self.composition_node.config
                
                if self.is_multiple_sample_data():
                    self.create_multiple_sample_composition_pyqtgraph(plot_data, config)
                else:
                    plot_item = self.plot_widget.addPlot()
                    analysis_type = config.get('analysis_type', 'Single vs Multiple Elements')
                    data_type_display = config.get('data_type_display', 'Counts (Raw)')
                    
                    if analysis_type == 'Single vs Multiple Elements':
                        data = self.calculate_single_vs_multiple_analysis(plot_data, config)
                        title = f'Single vs Multiple Elements ({data_type_display})'
                    elif analysis_type == 'Specific Element Combinations':
                        data = self.calculate_specific_combinations_analysis(plot_data, config)
                        title = f'Element Combinations ({data_type_display})'
                    else:
                        data = plot_data
                        title = f'Element Distribution ({data_type_display})'
                    
                    if data:
                        self.create_pyqtgraph_composition_pie_chart(plot_item, data, config, title)
                    
                    self.apply_plot_settings(plot_item)
            
        except Exception as e:
            print(f"Error updating composition display: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def create_multiple_sample_composition_pyqtgraph(self, plot_data, config):
        """
        Create composition analysis for multiple samples with different display modes.
        
        Args:
            plot_data (dict): Dictionary of sample combination data
            config (dict): Configuration dictionary with display settings
        
        Returns:
            None
        """
        display_mode = config.get('display_mode', 'Individual Subplots')
        sample_names = list(plot_data.keys())
        
        if display_mode == 'Individual Subplots':
            self.create_subplot_compositions_pyqtgraph(plot_data, config)
        elif display_mode == 'Side by Side Subplots':
            self.create_side_by_side_compositions_pyqtgraph(plot_data, config)
        elif display_mode == 'Combined Analysis':
            self.create_combined_composition_analysis_pyqtgraph(plot_data, config)
        else:
            self.create_comparative_composition_view_pyqtgraph(plot_data, config)
    
    def create_subplot_compositions_pyqtgraph(self, plot_data, config):
        """
        Create individual subplots for each sample composition.
        
        Args:
            plot_data (dict): Dictionary of sample combination data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_names = list(plot_data.keys())
        n_samples = len(sample_names)
        
        cols = min(3, n_samples)
        rows = math.ceil(n_samples / cols)
        
        for i, sample_name in enumerate(sample_names):
            row = i // cols
            col = i % cols
            plot_item = self.plot_widget.addPlot(row=row, col=col)
            
            sample_data = plot_data[sample_name]
            if sample_data:
                analysis_type = config.get('analysis_type', 'Single vs Multiple Elements')
                
                if analysis_type == 'Single vs Multiple Elements':
                    data = self.calculate_single_vs_multiple_analysis(sample_data, config)
                elif analysis_type == 'Specific Element Combinations':
                    data = self.calculate_specific_combinations_analysis(sample_data, config)
                else:
                    data = sample_data
                
                if data:
                    self.create_pyqtgraph_composition_pie_chart(plot_item, data, config, sample_name)
                
                self.apply_plot_settings(plot_item)
    
    def create_side_by_side_compositions_pyqtgraph(self, plot_data, config):
        """
        Create side-by-side composition plots for multiple samples.
        
        Args:
            plot_data (dict): Dictionary of sample combination data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_names = list(plot_data.keys())
        n_samples = len(sample_names)
        
        for i, sample_name in enumerate(sample_names):
            plot_item = self.plot_widget.addPlot(row=0, col=i)
            
            sample_data = plot_data[sample_name]
            if sample_data:
                analysis_type = config.get('analysis_type', 'Single vs Multiple Elements')
                
                if analysis_type == 'Single vs Multiple Elements':
                    data = self.calculate_single_vs_multiple_analysis(sample_data, config)
                elif analysis_type == 'Specific Element Combinations':
                    data = self.calculate_specific_combinations_analysis(sample_data, config)
                else:
                    data = sample_data
                
                if data:
                    self.create_pyqtgraph_composition_pie_chart(plot_item, data, config, sample_name)
                
                self.apply_plot_settings(plot_item)
    
    def create_combined_composition_analysis_pyqtgraph(self, plot_data, config):
        """
        Create a single composition analysis combining all samples.
        
        Args:
            plot_data (dict): Dictionary of sample combination data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        plot_item = self.plot_widget.addPlot()
        
        combined_data = {}
        for sample_name, sample_data in plot_data.items():
            if sample_data:
                for combination, combo_info in sample_data.items():
                    if isinstance(combo_info, dict):
                        if combination not in combined_data:
                            combined_data[combination] = {
                                'particle_count': 0,
                                'data_value': 0,
                                'elements': combo_info.get('elements', {})
                            }
                        combined_data[combination]['particle_count'] += combo_info.get('particle_count', 0)
                        combined_data[combination]['data_value'] += combo_info.get('data_value', 0)
                    else:
                        combined_data[combination] = combined_data.get(combination, 0) + combo_info
        
        if combined_data:
            analysis_type = config.get('analysis_type', 'Single vs Multiple Elements')
            
            if analysis_type == 'Single vs Multiple Elements':
                data = self.calculate_single_vs_multiple_analysis(combined_data, config)
            elif analysis_type == 'Specific Element Combinations':
                data = self.calculate_specific_combinations_analysis(combined_data, config)
            else:
                data = combined_data
            
            if data:
                title = f"Combined Analysis ({len(plot_data)} samples)"
                self.create_pyqtgraph_composition_pie_chart(plot_item, data, config, title)
        
        self.apply_plot_settings(plot_item)
    
    def create_comparative_composition_view_pyqtgraph(self, plot_data, config):
        """
        Create comparative view showing differences between first two samples.
        
        Args:
            plot_data (dict): Dictionary of sample combination data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_names = list(plot_data.keys())
        
        if len(sample_names) >= 2:
            plot_item1 = self.plot_widget.addPlot(row=0, col=0)
            plot_item2 = self.plot_widget.addPlot(row=0, col=1)
            
            for plot_item, sample_name in zip([plot_item1, plot_item2], sample_names[:2]):
                sample_data = plot_data[sample_name]
                if sample_data:
                    analysis_type = config.get('analysis_type', 'Single vs Multiple Elements')
                    
                    if analysis_type == 'Single vs Multiple Elements':
                        data = self.calculate_single_vs_multiple_analysis(sample_data, config)
                    elif analysis_type == 'Specific Element Combinations':
                        data = self.calculate_specific_combinations_analysis(sample_data, config)
                    else:
                        data = sample_data
                    
                    if data:
                        self.create_pyqtgraph_composition_pie_chart(plot_item, data, config, sample_name)
                    
                    self.apply_plot_settings(plot_item)
    
    def calculate_single_vs_multiple_analysis(self, plot_data, config):
        """
        Calculate single vs multiple element analysis by grouping combinations.
        
        Args:
            plot_data (dict): Combination data dictionary
            config (dict): Configuration dictionary
        
        Returns:
            dict: Dictionary with single and multiple element summary data
        """
        single_particle_count = 0
        single_data_value = 0
        multiple_particle_count = 0
        multiple_data_value = 0
        
        for combination, combo_info in plot_data.items():
            if isinstance(combo_info, dict):
                particle_count = combo_info.get('particle_count', 0)
                data_value = combo_info.get('data_value', 0)
            else:
                particle_count = combo_info
                data_value = combo_info
            
            if len(combination.split(', ')) == 1:
                single_particle_count += particle_count
                single_data_value += data_value
            else:
                multiple_particle_count += particle_count
                multiple_data_value += data_value
        
        data = {}
        if single_particle_count > 0:
            data['Single Elements'] = {
                'particle_count': single_particle_count,
                'data_value': single_data_value,
                'elements': {}
            }
        if multiple_particle_count > 0:
            data['Multiple Elements'] = {
                'particle_count': multiple_particle_count,
                'data_value': multiple_data_value,
                'elements': {}
            }
        
        return data
    
    def calculate_specific_combinations_analysis(self, plot_data, config):
        """
        Calculate specific combinations analysis with particle threshold filtering.
        
        Args:
            plot_data (dict): Combination data dictionary
            config (dict): Configuration dictionary with threshold settings
        
        Returns:
            dict: Dictionary with filtered combination data above threshold
        """
        particle_threshold = config.get('particle_threshold', 10)
        filtered_data = {}
        
        for combination, combo_info in plot_data.items():
            if isinstance(combo_info, dict):
                particle_count = combo_info.get('particle_count', 0)
                if particle_count >= particle_threshold:
                    filtered_data[combination] = combo_info
            else:
                if combo_info >= particle_threshold:
                    filtered_data[combination] = combo_info
        
        return filtered_data
    
    def create_pyqtgraph_composition_pie_chart(self, plot_item, data, config, title):
        """
        Create custom pie chart for element composition using PyQtGraph.
        
        Calculates percentages based on selected data type (counts or mass/moles),
        applies threshold filtering, and creates wedges with detailed labels.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            data (dict): Combination data dictionary with particle counts and values
            config (dict): Configuration dictionary with display settings
            title (str): Chart title string
        
        Returns:
            None
        """
        if not data:
            return
        
        data_type_display = config.get('data_type_display', 'Counts (Raw)')
        
        if data_type_display == 'Counts (Raw)':
            total_for_percentage = 0
            for combo_info in data.values():
                if isinstance(combo_info, dict):
                    total_for_percentage += combo_info.get('particle_count', 0)
                else:
                    total_for_percentage += combo_info
        else:
            total_for_percentage = 0
            for combo_info in data.values():
                if isinstance(combo_info, dict):
                    total_for_percentage += combo_info.get('data_value', 0)
                else:
                    total_for_percentage += combo_info
        
        if total_for_percentage == 0:
            return
            
        percentages = {}
        for combination, combo_info in data.items():
            if isinstance(combo_info, dict):
                if data_type_display == 'Counts (Raw)':
                    value_for_percentage = combo_info.get('particle_count', 0)
                else:
                    value_for_percentage = combo_info.get('data_value', 0)
            else:
                value_for_percentage = combo_info
            percentages[combination] = (value_for_percentage / total_for_percentage) * 100
        
        threshold = config.get('percentage_threshold', 1.0)
        main_combinations = {k: v for k, v in percentages.items() if v >= threshold}
        others = {k: v for k, v in percentages.items() if v < threshold}
        
        if others:
            main_combinations['Others'] = sum(others.values())
        
        sorted_combinations = sorted(main_combinations.items(), key=lambda x: x[1], reverse=True)
        
        labels = [item[0] for item in sorted_combinations]
        sizes = [item[1] for item in sorted_combinations]
        
        display_data = {}
        for label in labels:
            if label == 'Others':
                particle_count = 0
                data_value = 0
                elements_dict = {}
                
                for combo_name in others.keys():
                    combo_info = data[combo_name]
                    if isinstance(combo_info, dict):
                        particle_count += combo_info.get('particle_count', 0)
                        data_value += combo_info.get('data_value', 0)
                        for elem, val in combo_info.get('elements', {}).items():
                            elements_dict[elem] = elements_dict.get(elem, 0) + val
                    else:
                        particle_count += combo_info
                        data_value += combo_info
                
                display_data[label] = {
                    'particle_count': particle_count,
                    'data_value': data_value,
                    'elements': elements_dict
                }
            else:
                combo_info = data[label]
                if isinstance(combo_info, dict):
                    display_data[label] = combo_info
                else:
                    display_data[label] = {
                        'particle_count': combo_info,
                        'data_value': combo_info,
                        'elements': {}
                    }
        
        combination_colors = config.get('combination_colors', {})
        default_colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', 
                         '#FF6B35', '#FFD700', '#20B2AA', '#FF69B4', '#32CD32']
        
        colors = []
        for i, label in enumerate(labels):
            if label in combination_colors:
                colors.append(combination_colors[label])
            elif label == 'Others':
                colors.append('#808080')
            else:
                colors.append(default_colors[i % len(default_colors)])
        
        self.draw_composition_pie_chart_with_pyqtgraph(plot_item, labels, sizes, display_data, colors, config)
        
        plot_item.setTitle(title)
        
        plot_item.hideAxis('left')
        plot_item.hideAxis('bottom')
        
        plot_item.setAspectLocked(True)
        
        plot_item.setRange(xRange=[-1.5, 1.5], yRange=[-1.5, 1.5])
    
    def draw_composition_pie_chart_with_pyqtgraph(self, plot_item, labels, sizes, display_data, colors, config):
        """
        Draw pie chart for element composition using PyQtGraph with detailed labels.
        
        Creates wedges with smart label positioning and optional display of data values,
        particle counts, percentages, and element percentages within combinations.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            labels (list): List of combination label strings
            sizes (list): List of percentage values for each combination
            display_data (dict): Dictionary mapping labels to detailed data info
            colors (list): List of color hex strings for each combination
            config (dict): Configuration dictionary with label display settings
        
        Returns:
            None
        """
        if not sizes:
            return
        
        angles = [(size / 100.0) * 360 for size in sizes]
        
        start_angle = 90
        
        font_family = config.get('font_family', 'Times New Roman')
        font_size = max(8, config.get('font_size', 18) - 6)
        is_bold = config.get('font_bold', False)
        is_italic = config.get('font_italic', False)
        font_color = config.get('font_color', '#000000')
        
        text_font = QFont(font_family, font_size)
        text_font.setBold(is_bold)
        text_font.setItalic(is_italic)
        
        show_data_values = config.get('show_data_values', True)
        show_counts = config.get('show_counts', True)
        show_percentages = config.get('show_percentages', True)
        show_element_percentages = config.get('show_element_percentages', False)
        smart_labels = config.get('smart_labels', True)
        show_lines = config.get('show_connection_lines', True)
        data_type_display = config.get('data_type_display', 'Counts (Raw)')
        
        for i, (label, angle, size, color) in enumerate(zip(labels, angles, sizes, colors)):
            end_angle = start_angle + angle
            
            start_rad = math.radians(start_angle)
            end_rad = math.radians(end_angle)
            
            radius = 1.0
            segments = max(16, int(angle / 3))
            
            wedge_x = [0]
            wedge_y = [0]
            
            for j in range(segments + 1):
                t = j / segments
                current_angle = start_rad + t * (end_rad - start_rad)
                x = radius * math.cos(current_angle)
                y = radius * math.sin(current_angle)
                wedge_x.append(x)
                wedge_y.append(y)
            
            wedge_x.append(0)
            wedge_y.append(0)
            
            wedge_item = pg.PlotDataItem(wedge_x, wedge_y, 
                                        pen=pg.mkPen('white', width=2),
                                        brush=pg.mkBrush(color),
                                        fillLevel=0)
            plot_item.addItem(wedge_item)
            
            combo_info = display_data[label]
            particle_count = combo_info.get('particle_count', 0)
            data_value = combo_info.get('data_value', 0)
            elements_dict = combo_info.get('elements', {})
            
            mid_angle_rad = math.radians(start_angle + angle / 2)
            
            display_text_parts = [label]
            
            if show_counts:
                display_text_parts.append(f"({particle_count:,} particles)")
            
            if show_data_values and data_type_display != 'Counts (Raw)':
                if 'Mass' in data_type_display:
                    display_text_parts.append(f"[{data_value:.2f} fg]")
                elif 'Moles' in data_type_display:
                    display_text_parts.append(f"[{data_value:.2f} fmol]")
                else:
                    display_text_parts.append(f"[{data_value:.2f}]")
            
            if show_percentages:
                display_text_parts.append(f"{size:.1f}%")
            
            if show_element_percentages and elements_dict and len(elements_dict) > 1:
                element_total = sum(elements_dict.values())
                if element_total > 0:
                    element_percentages = []
                    for elem, val in elements_dict.items():
                        elem_percent = (val / element_total) * 100
                        element_percentages.append(f"{elem}: {elem_percent:.1f}%")
                    if element_percentages:
                        display_text_parts.append(f"({', '.join(element_percentages)})")
            
            display_text = '\n'.join(display_text_parts)
            
            if smart_labels and size > 10:
                label_radius = 0.6
                label_x = label_radius * math.cos(mid_angle_rad)
                label_y = label_radius * math.sin(mid_angle_rad)
                
                text_item = pg.TextItem(display_text, anchor=(0.5, 0.5), color=font_color)
                
                if hasattr(text_item, 'textItem'):
                    text_item.textItem.setFont(text_font)
                elif hasattr(text_item, 'item'):
                    text_item.item.setFont(text_font)
                
                text_item.setPos(label_x, label_y)
                plot_item.addItem(text_item)
                
            else:
                inside_radius = 1.05
                outside_radius = 1.3
                
                inside_x = inside_radius * math.cos(mid_angle_rad)
                inside_y = inside_radius * math.sin(mid_angle_rad)
                outside_x = outside_radius * math.cos(mid_angle_rad)
                outside_y = outside_radius * math.sin(mid_angle_rad)
                
                if show_lines:
                    line_data = pg.PlotDataItem([inside_x, outside_x], [inside_y, outside_y], 
                                               pen=pg.mkPen('gray', width=1))
                    plot_item.addItem(line_data)
                
                if outside_x > 0:
                    anchor = (0, 0.5)
                else:
                    anchor = (1, 0.5)
                
                text_item = pg.TextItem(display_text, anchor=anchor, color=font_color)
                
                if hasattr(text_item, 'textItem'):
                    text_item.textItem.setFont(text_font)
                elif hasattr(text_item, 'item'):
                    text_item.item.setFont(text_font)
                
                text_item.setPos(outside_x, outside_y)
                plot_item.addItem(text_item)
            
            start_angle = end_angle


class ElementCompositionPlotNode(QObject):
    """
    Enhanced Element composition plot node with PyQtGraph and multiple sample support.
    
    Manages element combination analysis configuration and data processing for both
    single and multiple sample workflows. Tracks element combinations and their
    occurrence patterns across particles.
    """
    
    position_changed = Signal(object)
    configuration_changed = Signal()
    
    def __init__(self, parent_window=None):
        """
        Initialize element composition plot node.
        
        Args:
            parent_window: Parent window widget for accessing application context
        
        Returns:
            None
        """
        super().__init__()
        self.title = "Element Composition"
        self.node_type = "element_composition_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.config = {
            'analysis_type': 'Single vs Multiple Elements',
            'data_type_display': 'Counts (Raw)',
            'selected_elements': [],
            'particle_threshold': 10,
            'percentage_threshold': 1.0,
            'filter_zeros': True,
            'show_data_values': True,
            'show_counts': True,
            'show_percentages': True,
            'show_element_percentages': False,
            'combination_colors': {},
            'display_mode': 'Individual Subplots',
            'sample_colors': {},
            'font_family': 'Times New Roman',
            'font_size': 18,
            'font_bold': False,
            'font_italic': False,
            'font_color': '#000000',
            'smart_labels': True,
            'show_connection_lines': True
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
        
        Args:
            parent_window: Parent window widget
        
        Returns:
            bool: True if configuration was successful
        """
        dialog = ElementCompositionDisplayDialog(self, parent_window)
        dialog.exec()
        return True
        
    def process_data(self, input_data):
        """
        Process input data and update composition analysis.
        
        Receives data from connected nodes and triggers visual updates.
        
        Args:
            input_data (dict): Input data dictionary from upstream nodes
        
        Returns:
            None
        """
        if not input_data:
            print("No input data received for element composition")
            return
            
        print(f"Element composition received data: {input_data.get('type', 'unknown')}")
        self.input_data = input_data
        
        self.configuration_changed.emit()
    
    def extract_plot_data(self):
        """
        Extract plottable data from input with element combination tracking.
        
        Analyzes particles to identify which elements occur together, tracking
        both particle counts and total data values for each combination.
        
        Args:
            None
        
        Returns:
            dict or None: Dictionary with combination data, or None if no data
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
            return self._extract_single_sample_data_enhanced(data_key)
            
        elif input_type == 'multiple_sample_data':
            return self._extract_multiple_sample_data_enhanced(data_key)
            
        return None
    
    def _extract_single_sample_data_enhanced(self, data_key):
        """
        Extract data for single sample with element combination tracking.
        
        Analyzes each particle to identify element combinations and tracks
        particle counts and total values for each unique combination.
        
        Args:
            data_key (str): Key for data type in particle dictionary
        
        Returns:
            dict or None: Dictionary with combination data, or None if extraction fails
        """
        particles = self.input_data.get('particle_data')
        
        if not particles:
            print(f"No filtered particle data available from sample selector")
            return None
        
        try:
            combination_data = {}
            filter_zeros = self.config.get('filter_zeros', True)
            
            for particle in particles:
                particle_data_dict = particle.get(data_key, {})
                elements_in_particle = {}
                
                for element_name, value in particle_data_dict.items():
                    if data_key == 'elements':
                        if value > 0:
                            elements_in_particle[element_name] = value
                    else:
                        if value > 0 and not np.isnan(value):
                            elements_in_particle[element_name] = value
                
                if elements_in_particle:
                    combination = ', '.join(sorted(elements_in_particle.keys()))
                    total_data_value = sum(elements_in_particle.values())
                    
                    if combination not in combination_data:
                        combination_data[combination] = {
                            'particle_count': 0,
                            'data_value': 0,
                            'elements': {}
                        }
                    
                    combination_data[combination]['particle_count'] += 1
                    combination_data[combination]['data_value'] += total_data_value
                    
                    for element_name, value in elements_in_particle.items():
                        if element_name not in combination_data[combination]['elements']:
                            combination_data[combination]['elements'][element_name] = 0
                        combination_data[combination]['elements'][element_name] += value
            
            return combination_data
            
        except Exception as e:
            print(f"Error in _extract_single_sample_data_enhanced: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_multiple_sample_data_enhanced(self, data_key):
        """
        Extract data for multiple samples with element combination tracking.
        
        Analyzes particles from each sample separately to identify element
        combinations and tracks particle counts and values per sample.
        
        Args:
            data_key (str): Key for data type in particle dictionary
        
        Returns:
            dict or None: Dictionary mapping samples to combination data, or None if extraction fails
        """
        particles = self.input_data.get('particle_data', [])
        sample_names = self.input_data.get('sample_names', [])
        
        if not particles:
            print("No filtered particle data available from sample selector")
            return None
        
        try:
            sample_data = {}
            filter_zeros = self.config.get('filter_zeros', True)
            
            for sample_name in sample_names:
                sample_data[sample_name] = {}
            
            for particle in particles:
                source_sample = particle.get('source_sample')
                if source_sample and source_sample in sample_data:
                    particle_data_dict = particle.get(data_key, {})
                    elements_in_particle = {}
                    
                    for element_name, value in particle_data_dict.items():
                        if data_key == 'elements':
                            if value > 0:
                                elements_in_particle[element_name] = value
                        else:
                            if value > 0 and not np.isnan(value):
                                elements_in_particle[element_name] = value
                    
                    if elements_in_particle:
                        combination = ', '.join(sorted(elements_in_particle.keys()))
                        total_data_value = sum(elements_in_particle.values())
                        
                        if combination not in sample_data[source_sample]:
                            sample_data[source_sample][combination] = {
                                'particle_count': 0,
                                'data_value': 0,
                                'elements': {}
                            }
                        
                        sample_data[source_sample][combination]['particle_count'] += 1
                        sample_data[source_sample][combination]['data_value'] += total_data_value
                        
                        for element_name, value in elements_in_particle.items():
                            if element_name not in sample_data[source_sample][combination]['elements']:
                                sample_data[source_sample][combination]['elements'][element_name] = 0
                            sample_data[source_sample][combination]['elements'][element_name] += value
            
            sample_data = {k: v for k, v in sample_data.items() if v}
            
            return sample_data
            
        except Exception as e:
            print(f"Error in _extract_multiple_sample_data_enhanced: {str(e)}")
            import traceback
            traceback.print_exc()
            return None