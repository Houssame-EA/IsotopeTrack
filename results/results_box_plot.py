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
from results.utils_sort import (
    extract_mass_and_element,
    sort_elements_by_mass,
    format_element_label,
    format_combination_label,
    sort_element_dict_by_mass
)


class BoxPlotDisplayDialog(QDialog):
    """
    Dialog for box plot visualization with multiple shape options and samples support.
    """
    
    def __init__(self, box_plot_node, parent_window=None):
        """
        Initialize the box plot display dialog.
        
        Args:
            box_plot_node: Box plot node instance
            parent_window: Parent window widget
        """
        super().__init__(parent_window)
        self.box_plot_node = box_plot_node
        self.parent_window = parent_window
        
        self.setWindowTitle("Particle Data Distribution Plot Analysis")
        self.setMinimumSize(1400, 800)
        
        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        self.setup_ui()
        self.update_display()
        
        self.box_plot_node.configuration_changed.connect(self.update_display)
        
    def setup_ui(self):
        """
        Set up the user interface.
        
        Returns:
            None
        """
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        config_panel = self.create_config_panel()
        config_panel.setFixedWidth(420)
        layout.addWidget(config_panel)
        
        plot_panel = self.create_plot_panel()
        layout.addWidget(plot_panel, stretch=1)
        
    def is_multiple_sample_data(self):
        """
        Check if we're dealing with multiple sample data.
        
        Returns:
            bool: True if multiple sample data, False otherwise
        """
        return (hasattr(self.box_plot_node, 'input_data') and 
                self.box_plot_node.input_data and 
                self.box_plot_node.input_data.get('type') == 'multiple_sample_data')
        
    def get_font_families(self):
        """
        Get list of available font families.
        
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
        Create the box plot configuration panel with shape options.
        
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
        
        title = QLabel("Distribution Plot Settings")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #1F2937;
                margin-bottom: 8px;
            }
        """)
        layout.addWidget(title)
        
        shape_group = QGroupBox("Plot Shape")
        shape_layout = QFormLayout(shape_group)
        
        self.plot_shape_combo = QComboBox()
        self.plot_shape_combo.addItems([
            'Box Plot (Traditional)',
            'Violin Plot',
            'Box + Violin (Overlay)', 
            'Strip Plot (Dots)',
            'Half Violin + Half Box',
            'Notched Box Plot',
            'Bar Plot with Error Bars'
        ])
        self.plot_shape_combo.setCurrentText(self.box_plot_node.config.get('plot_shape', 'Box Plot (Traditional)'))
        self.plot_shape_combo.currentTextChanged.connect(self.on_config_changed)
        shape_layout.addRow("Shape:", self.plot_shape_combo)
        
        self.violin_bandwidth_spin = QDoubleSpinBox()
        self.violin_bandwidth_spin.setRange(0.01, 2.0)
        self.violin_bandwidth_spin.setSingleStep(0.1)
        self.violin_bandwidth_spin.setDecimals(2)
        self.violin_bandwidth_spin.setValue(self.box_plot_node.config.get('violin_bandwidth', 0.2))
        self.violin_bandwidth_spin.valueChanged.connect(self.on_config_changed)
        shape_layout.addRow("Violin Bandwidth:", self.violin_bandwidth_spin)
        
        self.strip_jitter_spin = QDoubleSpinBox()
        self.strip_jitter_spin.setRange(0.0, 0.5)
        self.strip_jitter_spin.setSingleStep(0.05)
        self.strip_jitter_spin.setDecimals(2)
        self.strip_jitter_spin.setValue(self.box_plot_node.config.get('strip_jitter', 0.2))
        self.strip_jitter_spin.valueChanged.connect(self.on_config_changed)
        shape_layout.addRow("Strip/Swarm Jitter:", self.strip_jitter_spin)
        
        layout.addWidget(shape_group)
        
        if self.is_multiple_sample_data():
            multiple_group = QGroupBox("Multiple Sample Display")
            multiple_layout = QFormLayout(multiple_group)
            
            self.display_mode_combo = QComboBox()
            self.display_mode_combo.addItems([
                'Side by Side', 
                'Individual Subplots',
                'Grouped by Element'
            ])
            self.display_mode_combo.setCurrentText(self.box_plot_node.config.get('display_mode', 'Side by Side'))
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
            'Particle Moles (fmol)',
            'Element Diameter (nm)',
            'Particle Diameter (nm)'
        ])
        self.data_type_combo.setCurrentText(self.box_plot_node.config.get('data_type_display', 'Counts (Raw)'))
        self.data_type_combo.currentTextChanged.connect(self.on_data_type_changed)
        data_layout.addWidget(self.data_type_combo)
        
        layout.addWidget(data_group)
        
        plot_group = QGroupBox("Plot Options")
        plot_layout = QFormLayout(plot_group)
        
        self.show_outliers_checkbox = QCheckBox()
        self.show_outliers_checkbox.setChecked(self.box_plot_node.config.get('show_outliers', True))
        self.show_outliers_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Show Outliers:", self.show_outliers_checkbox)
        
        self.show_mean_checkbox = QCheckBox()
        self.show_mean_checkbox.setChecked(self.box_plot_node.config.get('show_mean', True))
        self.show_mean_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Show Mean Points:", self.show_mean_checkbox)
        
        self.show_median_checkbox = QCheckBox()
        self.show_median_checkbox.setChecked(self.box_plot_node.config.get('show_median', True))
        self.show_median_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Show Median Line:", self.show_median_checkbox)
        
        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setRange(0.1, 1.0)
        self.alpha_spin.setSingleStep(0.1)
        self.alpha_spin.setDecimals(1)
        self.alpha_spin.setValue(self.box_plot_node.config.get('alpha', 0.7))
        self.alpha_spin.valueChanged.connect(self.on_config_changed)
        plot_layout.addRow("Fill Transparency:", self.alpha_spin)
        
        self.log_y_checkbox = QCheckBox()
        self.log_y_checkbox.setChecked(self.box_plot_node.config.get('log_y', False))
        self.log_y_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Log Y-axis:", self.log_y_checkbox)
        
        self.show_stats_checkbox = QCheckBox()
        self.show_stats_checkbox.setChecked(self.box_plot_node.config.get('show_stats', True))
        self.show_stats_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Show Statistics:", self.show_stats_checkbox)
        
        self.plot_width_spin = QDoubleSpinBox()
        self.plot_width_spin.setRange(0.1, 2.0)
        self.plot_width_spin.setSingleStep(0.1)
        self.plot_width_spin.setDecimals(1)
        self.plot_width_spin.setValue(self.box_plot_node.config.get('plot_width', 0.8))
        self.plot_width_spin.valueChanged.connect(self.on_config_changed)
        plot_layout.addRow("Plot Width:", self.plot_width_spin)
        
        layout.addWidget(plot_group)
        
        font_group = QGroupBox("Font Settings")
        font_layout = QFormLayout(font_group)
        
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(self.get_font_families())
        self.font_family_combo.setCurrentText(self.box_plot_node.config.get('font_family', 'Times New Roman'))
        self.font_family_combo.currentTextChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Family:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(self.box_plot_node.config.get('font_size', 18))
        self.font_size_spin.valueChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Size:", self.font_size_spin)
        
        font_style_layout = QHBoxLayout()
        self.font_bold_checkbox = QCheckBox("Bold")
        self.font_bold_checkbox.setChecked(self.box_plot_node.config.get('font_bold', False))
        self.font_bold_checkbox.stateChanged.connect(self.on_config_changed)
        self.font_italic_checkbox = QCheckBox("Italic")
        self.font_italic_checkbox.setChecked(self.box_plot_node.config.get('font_italic', False))
        self.font_italic_checkbox.stateChanged.connect(self.on_config_changed)
        font_style_layout.addWidget(self.font_bold_checkbox)
        font_style_layout.addWidget(self.font_italic_checkbox)
        font_style_layout.addStretch()
        font_layout.addRow("Font Style:", font_style_layout)
        
        self.font_color_button = QPushButton()
        self.font_color = QColor(self.box_plot_node.config.get('font_color', '#000000'))
        self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 30px;")
        self.font_color_button.clicked.connect(lambda: self.choose_color('font'))
        font_layout.addRow("Font Color:", self.font_color_button)
        
        layout.addWidget(font_group)
        
        limits_group = QGroupBox("Y-Axis Limits")
        limits_layout = QFormLayout(limits_group)
        
        y_layout = QHBoxLayout()
        self.y_min_spin = QDoubleSpinBox()
        self.y_min_spin.setRange(-999999, 999999)
        self.y_min_spin.setValue(self.box_plot_node.config.get('y_min', 0))
        self.y_min_spin.valueChanged.connect(self.on_config_changed)
        
        self.y_max_spin = QDoubleSpinBox()
        self.y_max_spin.setRange(-999999, 999999)
        self.y_max_spin.setValue(self.box_plot_node.config.get('y_max', 100))
        self.y_max_spin.valueChanged.connect(self.on_config_changed)
        
        self.auto_y_checkbox = QCheckBox("Auto")
        self.auto_y_checkbox.setChecked(self.box_plot_node.config.get('auto_y', True))
        self.auto_y_checkbox.stateChanged.connect(self.on_config_changed)
        self.auto_y_checkbox.stateChanged.connect(self.toggle_y_limits)
        
        y_layout.addWidget(self.y_min_spin)
        y_layout.addWidget(QLabel("to"))
        y_layout.addWidget(self.y_max_spin)
        y_layout.addWidget(self.auto_y_checkbox)
        limits_layout.addRow("Y Range:", y_layout)
        
        layout.addWidget(limits_group)
        
        self.colors_group = QGroupBox("Element Colors")
        self.colors_layout = QVBoxLayout(self.colors_group)
        self.update_color_controls()
        layout.addWidget(self.colors_group)
        
        if self.is_multiple_sample_data():
            self.sample_colors_group = QGroupBox("Sample Colors")
            self.sample_colors_layout = QVBoxLayout(self.sample_colors_group)
            self.update_sample_color_controls()
            layout.addWidget(self.sample_colors_group)
        
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
    
    def choose_color(self, color_type):
        """
        Open color dialog for font color.
        
        Args:
            color_type (str): Type of color to choose
        
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
            font_family = self.box_plot_node.config.get('font_family', 'Times New Roman')
            font_size = self.box_plot_node.config.get('font_size', 18)
            is_bold = self.box_plot_node.config.get('font_bold', False)
            is_italic = self.box_plot_node.config.get('font_italic', False)
            font_color = self.box_plot_node.config.get('font_color', '#000000')
            
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
        
        Returns:
            None
        """
        self.on_config_changed()
    
    def update_sample_color_controls(self):
        """
        Update color controls for multiple samples with editable names.
        
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
        
        sample_colors = self.box_plot_node.config.get('sample_colors', {})
        
        sample_name_mappings = self.box_plot_node.config.get('sample_name_mappings', {})
        
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
        
        self.box_plot_node.config['sample_colors'] = sample_colors
        self.box_plot_node.config['sample_name_mappings'] = sample_name_mappings

    def on_sample_name_changed(self, original_name, new_name):
        """
        Handle sample name change.
        
        Args:
            original_name (str): Original sample name
            new_name (str): New display name
        
        Returns:
            None
        """
        if 'sample_name_mappings' not in self.box_plot_node.config:
            self.box_plot_node.config['sample_name_mappings'] = {}
        
        self.box_plot_node.config['sample_name_mappings'][original_name] = new_name
        self.on_config_changed()

    def reset_sample_name(self, original_name):
        """
        Reset sample name to original.
        
        Args:
            original_name (str): Original sample name to reset to
        
        Returns:
            None
        """
        if original_name in self.sample_name_edits:
            self.sample_name_edits[original_name].setText(original_name)
        
        if 'sample_name_mappings' in self.box_plot_node.config:
            self.box_plot_node.config['sample_name_mappings'].pop(original_name, None)
        
        self.on_config_changed()

    def get_display_name(self, original_name):
        """
        Get display name for a sample.
        
        Args:
            original_name (str): Original sample name
        
        Returns:
            str: Display name for the sample
        """
        mappings = self.box_plot_node.config.get('sample_name_mappings', {})
        return mappings.get(original_name, original_name)
        
    def get_available_sample_names(self):
        """
        Get available sample names from input data.
        
        Returns:
            list: List of sample names
        """
        if self.is_multiple_sample_data():
            return self.box_plot_node.input_data.get('sample_names', [])
        return []
    
    def select_sample_color(self, sample_name, button):
        """
        Open color dialog for sample.
        
        Args:
            sample_name (str): Name of the sample
            button (QPushButton): Button widget to update with color
        
        Returns:
            None
        """
        current_color = self.box_plot_node.config.get('sample_colors', {}).get(sample_name, '#3B82F6')
        display_name = self.get_display_name(sample_name)
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {display_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'sample_colors' not in self.box_plot_node.config:
                self.box_plot_node.config['sample_colors'] = {}
            self.box_plot_node.config['sample_colors'][sample_name] = color_hex
            
            self.on_config_changed()
    
    def download_figure(self):
        """
        Download the current figure.
        
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Distribution Plot",
            "distribution_plot.png",
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
                                    f"Distribution plot saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", 
                                f"Failed to save:\n{str(e)}")

    def update_color_controls(self):
        """
        Update color controls based on available elements.
        
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
        
        default_colors = ['#663399', '#2E86AB', '#A23B72', '#F18F01', '#C73E1D', 
                         '#7209B7', '#F72585', '#4361EE', '#277DA1', '#F8961E']
        
        element_colors = self.box_plot_node.config.get('element_colors', {})
        
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
        
        self.box_plot_node.config['element_colors'] = element_colors
    
    def get_available_elements(self):
        """
        Get available elements from the box plot node's data, sorted by mass number.
        
        Returns:
            list: Sorted list of available element names
        """
        if hasattr(self.box_plot_node, 'extract_plot_data'):
            plot_data = self.box_plot_node.extract_plot_data()
            if plot_data:
                if self.is_multiple_sample_data():
                    all_elements = set()
                    for sample_data in plot_data.values():
                        if isinstance(sample_data, dict):
                            all_elements.update(sample_data.keys())
                    return sort_elements_by_mass(list(all_elements))
                else:
                    return sort_elements_by_mass(list(plot_data.keys()))
        
        if not self.box_plot_node.input_data:
            return []
        
        data_type = self.box_plot_node.input_data.get('type')
        
        if data_type in ['sample_data', 'multiple_sample_data']:
            selected_isotopes = self.box_plot_node.input_data.get('selected_isotopes', [])
            if selected_isotopes:
                element_labels = [isotope['label'] for isotope in selected_isotopes]
                return sort_elements_by_mass(element_labels)
        
        return []
        
    def select_element_color(self, element_name, button):
        """
        Open color dialog for element.
        
        Args:
            element_name (str): Name of the element
            button (QPushButton): Button widget to update with color
        
        Returns:
            None
        """
        current_color = self.box_plot_node.config.get('element_colors', {}).get(element_name, '#663399')
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {element_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'element_colors' not in self.box_plot_node.config:
                self.box_plot_node.config['element_colors'] = {}
            self.box_plot_node.config['element_colors'][element_name] = color_hex
            
            self.on_config_changed()
    
    def toggle_y_limits(self):
        """
        Enable/disable Y-axis limit controls.
        
        Returns:
            None
        """
        auto_enabled = self.auto_y_checkbox.isChecked()
        self.y_min_spin.setEnabled(not auto_enabled)
        self.y_max_spin.setEnabled(not auto_enabled)
        
    def create_plot_panel(self):
        """
        Create the plot panel with PyQtGraph.
        
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
        Handle configuration changes.
        
        Returns:
            None
        """
        config_updates = {
            'data_type_display': self.data_type_combo.currentText(),
            'plot_shape': self.plot_shape_combo.currentText(),
            'violin_bandwidth': self.violin_bandwidth_spin.value(),
            'strip_jitter': self.strip_jitter_spin.value(),
            'show_outliers': self.show_outliers_checkbox.isChecked(),
            'show_mean': self.show_mean_checkbox.isChecked(),
            'show_median': self.show_median_checkbox.isChecked(),
            'alpha': self.alpha_spin.value(),
            'log_y': self.log_y_checkbox.isChecked(),
            'show_stats': self.show_stats_checkbox.isChecked(),
            'plot_width': self.plot_width_spin.value(),
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
            })
        
        self.box_plot_node.config.update(config_updates)
        
        self.update_display()

    def set_axis_labels_with_font(self, plot_item, x_label, y_label, config):
        """
        Set axis labels with proper font formatting.
        
        Args:
            plot_item: PyQtGraph plot item
            x_label (str): X-axis label
            y_label (str): Y-axis label
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
   
    def update_display(self):
        """
        Update the plot display based on selected shape.
        
        Returns:
            None
        """
        try:
            self.plot_widget.clear()
            
            plot_data = self.box_plot_node.extract_plot_data()
            
            if not plot_data:
                plot_item = self.plot_widget.addPlot()
                text_item = pg.TextItem("No particle data available\nConnect to Sample Selector\nand run particle detection", 
                                      anchor=(0.5, 0.5), color='gray')
                plot_item.addItem(text_item)
                text_item.setPos(0.5, 0.5)
                plot_item.hideAxis('left')
                plot_item.hideAxis('bottom')
            else:
                config = self.box_plot_node.config
                
                if self.is_multiple_sample_data():
                    self.create_multiple_sample_plot(plot_data, config)
                else:
                    plot_item = self.plot_widget.addPlot()
                    self.create_distribution_plot(plot_item, plot_data, config)
                    self.apply_plot_settings(plot_item)
            
        except Exception as e:
            print(f"Error updating plot display: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def create_multiple_sample_plot(self, plot_data, config):
        """
        Create plot for multiple samples.
        
        Args:
            plot_data (dict): Dictionary of sample data by sample name
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        display_mode = config.get('display_mode', 'Side by Side')
        
        if display_mode == 'Individual Subplots':
            self.create_subplot_plots(plot_data, config)
        elif display_mode == 'Grouped by Element':
            self.create_grouped_plots(plot_data, config)
        else:
            plot_item = self.plot_widget.addPlot()
            self.create_combined_plot(plot_item, plot_data, config)
            self.apply_plot_settings(plot_item)
    
    def create_subplot_plots(self, plot_data, config):
        """
        Create individual subplots for each sample.
        
        Args:
            plot_data (dict): Dictionary of sample data by sample name
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
                sorted_sample_data = sort_element_dict_by_mass(sample_data)
                
                self.create_distribution_plot(plot_item, sorted_sample_data, config)
                
                title_text = f"{self.get_display_name(sample_name)}"
                plot_item.setTitle(title_text)
                
                data_type_display = config.get('data_type_display', 'Counts (Raw)')
                log_y = config.get('log_y', False)
                
                label_mapping = {
                    'Counts (Raw)': 'Intensity (counts)',
                    'Element Mass (fg)': 'Element Mass (fg)',
                    'Particle Mass (fg)': 'Particle Mass (fg)', 
                    'Element Moles (fmol)': 'Element Moles (fmol)',
                    'Particle Moles (fmol)': 'Particle Moles (fmol)',
                    'Element Diameter (nm)': 'Element Diameter (nm)',
                    'Particle Diameter (nm)': 'Particle Diameter (nm)'
                }
                
                y_base_label = label_mapping.get(data_type_display, 'Values')
                y_label = f"log₁₀({y_base_label})" if log_y else y_base_label
                
                self.set_axis_labels_with_font(plot_item, "Elements", y_label, config)
                self.apply_plot_settings(plot_item)

    def create_grouped_plots(self, plot_data, config):
        """
        Create plots grouped by element.
        
        Args:
            plot_data (dict): Dictionary of sample data by sample name
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        all_elements = set()
        for sample_data in plot_data.values():
            all_elements.update(sample_data.keys())
        all_elements = sort_elements_by_mass(list(all_elements))
        
        n_elements = len(all_elements)
        cols = min(3, n_elements)
        rows = math.ceil(n_elements / cols)
        
        for i, element_name in enumerate(all_elements):
            row = i // cols
            col = i % cols
            plot_item = self.plot_widget.addPlot(row=row, col=col)
            
            element_data = {}
            for sample_name, sample_data in plot_data.items():
                if element_name in sample_data:
                    element_data[sample_name] = {element_name: sample_data[element_name]}
            
            if element_data:
                self.create_combined_plot(plot_item, element_data, config, single_element=element_name)
                plot_item.setTitle(element_name)
                
                data_type_display = config.get('data_type_display', 'Counts (Raw)')
                log_y = config.get('log_y', False)
                
                label_mapping = {
                    'Counts (Raw)': 'Intensity (counts)',
                    'Element Mass (fg)': 'Element Mass (fg)',
                    'Particle Mass (fg)': 'Particle Mass (fg)', 
                    'Element Moles (fmol)': 'Element Moles (fmol)',
                    'Particle Moles (fmol)': 'Particle Moles (fmol)',
                    'Element Diameter (nm)': 'Element Diameter (nm)',
                    'Particle Diameter (nm)': 'Particle Diameter (nm)'
                }
                
                y_base_label = label_mapping.get(data_type_display, 'Values')
                y_label = f"log₁₀({y_base_label})" if log_y else y_base_label
                
                self.set_axis_labels_with_font(plot_item, "Samples", y_label, config)
                self.apply_plot_settings(plot_item)
        
    def create_combined_plot(self, plot_item, plot_data, config, single_element=None):
        """
        Create combined plot with multiple shapes.
        
        Args:
            plot_item: PyQtGraph plot item
            plot_data (dict): Dictionary of sample data
            config (dict): Configuration dictionary
            single_element (str): Optional single element name
        
        Returns:
            None
        """
        sample_colors = config.get('sample_colors', {})
        element_colors = config.get('element_colors', {})
        default_colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
        
        x_pos = 0
        x_positions = []
        x_labels = []
        
        for sample_idx, (sample_name, sample_data) in enumerate(plot_data.items()):
            if sample_data:
                sorted_sample_data = sort_element_dict_by_mass(sample_data)
                
                for element_idx, (element_name, values) in enumerate(sorted_sample_data.items()):
                    if values and len(values) > 0:
                        data_type_display = config.get('data_type_display', 'Counts (Raw)')
                        if data_type_display != 'Counts (Raw)':
                            filtered_values = [v for v in values if v > 0 and not np.isnan(v)]
                        else:
                            filtered_values = values
                        
                        if filtered_values:
                            if config.get('log_y', False):
                                filtered_values = np.log10(np.array(filtered_values))
                            
                            self.create_single_plot(plot_item, x_pos, filtered_values, 
                                                sample_name, element_name, config)
                            
                            if single_element:
                                display_label = self.get_display_name(sample_name)
                            else:
                                display_label = f"{element_name}\n({self.get_display_name(sample_name)})"
                            
                            x_positions.append(x_pos)
                            x_labels.append(display_label)
                            x_pos += 1
        
        if x_positions and x_labels:
            x_axis = plot_item.getAxis('bottom')
            x_axis.setTicks([list(zip(x_positions, x_labels))])
        
        if not config.get('auto_y', True):
            plot_item.setYRange(config['y_min'], config['y_max'])
        
    def create_single_plot(self, plot_item, x_pos, values, sample_name, element_name, config):
        """
        Create a single plot based on the selected shape.
        
        Args:
            plot_item: PyQtGraph plot item
            x_pos (float): X-axis position
            values (list): Data values
            sample_name (str): Name of the sample
            element_name (str): Name of the element
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        if len(values) < 2:
            return
        
        plot_shape = config.get('plot_shape', 'Box Plot (Traditional)')
        
        sample_colors = config.get('sample_colors', {})
        element_colors = config.get('element_colors', {})
        default_colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
        
        if self.is_multiple_sample_data():
            color = sample_colors.get(sample_name, default_colors[0])
        else:
            color = element_colors.get(element_name, default_colors[0])
        
        color_obj = QColor(color)
        alpha = int(config.get('alpha', 0.7) * 255)
        plot_width = config.get('plot_width', 0.8)
        
        if plot_shape == 'Box Plot (Traditional)':
            self.create_box_plot_single(plot_item, x_pos, values, color, alpha, plot_width, config)
        elif plot_shape == 'Violin Plot':
            self.create_violin_plot_single(plot_item, x_pos, values, color, alpha, plot_width, config)
        elif plot_shape == 'Box + Violin (Overlay)':
            self.create_box_violin_overlay(plot_item, x_pos, values, color, alpha, plot_width, config)
        elif plot_shape == 'Strip Plot (Dots)':
            self.create_strip_plot_single(plot_item, x_pos, values, color, alpha, plot_width, config)
        elif plot_shape == 'Half Violin + Half Box':
            self.create_half_violin_box(plot_item, x_pos, values, color, alpha, plot_width, config)
        elif plot_shape == 'Notched Box Plot':
            self.create_notched_box_plot(plot_item, x_pos, values, color, alpha, plot_width, config)
        elif plot_shape == 'Bar Plot with Error Bars':
            self.create_bar_plot_with_errors(plot_item, x_pos, values, color, alpha, plot_width, config)

    def create_box_plot_single(self, plot_item, x_pos, values, color, alpha, plot_width, config):
        """
        Create traditional box plot.
        
        Args:
            plot_item: PyQtGraph plot item
            x_pos (float): X-axis position
            values (list): Data values
            color (str): Color hex code
            alpha (int): Alpha transparency value
            plot_width (float): Width of the plot
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        q1 = np.percentile(values, 25)
        median = np.percentile(values, 50)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1
        
        lower_whisker = q1 - 1.5 * iqr
        upper_whisker = q3 + 1.5 * iqr
        outliers = [v for v in values if v < lower_whisker or v > upper_whisker]
        
        color_obj = QColor(color)
        
        box_item = pg.QtWidgets.QGraphicsRectItem(
            x_pos - plot_width/2, q1, plot_width, q3 - q1
        )
        box_item.setBrush(pg.mkBrush(color_obj.red(), color_obj.green(), color_obj.blue(), alpha))
        box_item.setPen(pg.mkPen(color, width=2))
        plot_item.addItem(box_item)
        
        if config.get('show_median', True):
            median_line = pg.PlotDataItem([x_pos - plot_width/2, x_pos + plot_width/2], [median, median],
                                         pen=pg.mkPen('black', width=3))
            plot_item.addItem(median_line)
        
        whisker_pen = pg.mkPen('black', width=2)
        lower_whisker_actual = max(lower_whisker, min(values))
        upper_whisker_actual = min(upper_whisker, max(values))
        
        whisker_line = pg.PlotDataItem([x_pos, x_pos], [q1, lower_whisker_actual], pen=whisker_pen)
        plot_item.addItem(whisker_line)
        whisker_line = pg.PlotDataItem([x_pos, x_pos], [q3, upper_whisker_actual], pen=whisker_pen)
        plot_item.addItem(whisker_line)
        
        cap_width = plot_width * 0.3
        lower_cap = pg.PlotDataItem([x_pos - cap_width/2, x_pos + cap_width/2], 
                                   [lower_whisker_actual, lower_whisker_actual], pen=whisker_pen)
        plot_item.addItem(lower_cap)
        upper_cap = pg.PlotDataItem([x_pos - cap_width/2, x_pos + cap_width/2], 
                                   [upper_whisker_actual, upper_whisker_actual], pen=whisker_pen)
        plot_item.addItem(upper_cap)
        
        if config.get('show_outliers', True) and outliers:
            outlier_x = [x_pos] * len(outliers)
            outlier_plot = pg.ScatterPlotItem(x=outlier_x, y=outliers, 
                                            pen=pg.mkPen('black'), brush=pg.mkBrush('red'),
                                            size=6, symbol='o')
            plot_item.addItem(outlier_plot)
        
        if config.get('show_mean', True):
            mean_value = np.mean(values)
            mean_plot = pg.ScatterPlotItem(x=[x_pos], y=[mean_value], 
                                         pen=pg.mkPen('white', width=2), brush=pg.mkBrush('blue'),
                                         size=8, symbol='s')
            plot_item.addItem(mean_plot)

    def create_violin_plot_single(self, plot_item, x_pos, values, color, alpha, plot_width, config):
        """
        Create violin plot using KDE.
        
        Args:
            plot_item: PyQtGraph plot item
            x_pos (float): X-axis position
            values (list): Data values
            color (str): Color hex code
            alpha (int): Alpha transparency value
            plot_width (float): Width of the plot
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        try:
            bandwidth = config.get('violin_bandwidth', 0.2)
            kde = gaussian_kde(values, bw_method=bandwidth)
            
            y_min, y_max = min(values), max(values)
            y_range = y_max - y_min
            y_violin = np.linspace(y_min - 0.1*y_range, y_max + 0.1*y_range, 100)
            density = kde(y_violin)
            
            max_density = np.max(density)
            if max_density > 0:
                normalized_density = (density / max_density) * (plot_width / 2)
            else:
                normalized_density = np.zeros_like(density)
            
            x_left = x_pos - normalized_density
            x_right = x_pos + normalized_density
            
            color_obj = QColor(color)
            
            left_curve = pg.PlotDataItem(x=x_left, y=y_violin, 
                                        pen=pg.mkPen(color, width=2),
                                        fillLevel=x_pos,
                                        brush=pg.mkBrush(color_obj.red(), color_obj.green(), color_obj.blue(), alpha//2))
            plot_item.addItem(left_curve)
            
            right_curve = pg.PlotDataItem(x=x_right, y=y_violin, 
                                         pen=pg.mkPen(color, width=2),
                                         fillLevel=x_pos,
                                         brush=pg.mkBrush(color_obj.red(), color_obj.green(), color_obj.blue(), alpha//2))
            plot_item.addItem(right_curve)
            
            q1 = np.percentile(values, 25)
            median = np.percentile(values, 50)
            q3 = np.percentile(values, 75)
            
            if config.get('show_median', True):
                median_line = pg.PlotDataItem([x_pos - plot_width/4, x_pos + plot_width/4], [median, median],
                                             pen=pg.mkPen('white', width=4))
                plot_item.addItem(median_line)
            
            q1_line = pg.PlotDataItem([x_pos - plot_width/6, x_pos + plot_width/6], [q1, q1],
                                     pen=pg.mkPen('white', width=2))
            plot_item.addItem(q1_line)
            q3_line = pg.PlotDataItem([x_pos - plot_width/6, x_pos + plot_width/6], [q3, q3],
                                     pen=pg.mkPen('white', width=2))
            plot_item.addItem(q3_line)
            
            if config.get('show_mean', True):
                mean_value = np.mean(values)
                mean_plot = pg.ScatterPlotItem(x=[x_pos], y=[mean_value], 
                                             pen=pg.mkPen('white', width=2), brush=pg.mkBrush('red'),
                                             size=8, symbol='d')
                plot_item.addItem(mean_plot)
                
        except Exception as e:
            print(f"Error creating violin plot: {e}")
            self.create_box_plot_single(plot_item, x_pos, values, color, alpha, plot_width, config)

    def create_box_violin_overlay(self, plot_item, x_pos, values, color, alpha, plot_width, config):
        """
        Create overlay of box plot and violin plot.
        
        Args:
            plot_item: PyQtGraph plot item
            x_pos (float): X-axis position
            values (list): Data values
            color (str): Color hex code
            alpha (int): Alpha transparency value
            plot_width (float): Width of the plot
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        self.create_violin_plot_single(plot_item, x_pos, values, color, alpha//2, plot_width, config)
        
        box_config = config.copy()
        box_config['show_median'] = True
        box_config['show_mean'] = False
        self.create_box_plot_single(plot_item, x_pos, values, color, alpha, plot_width*0.3, box_config)

    def create_strip_plot_single(self, plot_item, x_pos, values, color, alpha, plot_width, config):
        """
        Create strip plot (jittered dots).
        
        Args:
            plot_item: PyQtGraph plot item
            x_pos (float): X-axis position
            values (list): Data values
            color (str): Color hex code
            alpha (int): Alpha transparency value
            plot_width (float): Width of the plot
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        jitter = config.get('strip_jitter', 0.2)
        
        np.random.seed(42)
        x_jitter = np.random.uniform(-jitter, jitter, len(values))
        x_positions = [x_pos + j for j in x_jitter]
        
        color_obj = QColor(color)
        
        strip_plot = pg.ScatterPlotItem(x=x_positions, y=values, 
                                       pen=pg.mkPen(color), 
                                       brush=pg.mkBrush(color_obj.red(), color_obj.green(), color_obj.blue(), alpha),
                                       size=6, symbol='o')
        plot_item.addItem(strip_plot)
        
        if config.get('show_mean', True):
            mean_value = np.mean(values)
            mean_line = pg.PlotDataItem([x_pos - plot_width/2, x_pos + plot_width/2], [mean_value, mean_value],
                                       pen=pg.mkPen('red', width=3))
            plot_item.addItem(mean_line)
        
        if config.get('show_median', True):
            median_value = np.median(values)
            median_line = pg.PlotDataItem([x_pos - plot_width/2, x_pos + plot_width/2], [median_value, median_value],
                                         pen=pg.mkPen('blue', width=2))
            plot_item.addItem(median_line)

    def create_half_violin_box(self, plot_item, x_pos, values, color, alpha, plot_width, config):
        """
        Create half violin + half box plot.
        
        Args:
            plot_item: PyQtGraph plot item
            x_pos (float): X-axis position
            values (list): Data values
            color (str): Color hex code
            alpha (int): Alpha transparency value
            plot_width (float): Width of the plot
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        try:
            bandwidth = config.get('violin_bandwidth', 0.2)
            kde = gaussian_kde(values, bw_method=bandwidth)
            
            y_min, y_max = min(values), max(values)
            y_range = y_max - y_min
            y_violin = np.linspace(y_min - 0.1*y_range, y_max + 0.1*y_range, 100)
            density = kde(y_violin)
            
            max_density = np.max(density)
            if max_density > 0:
                normalized_density = (density / max_density) * (plot_width / 2)
            else:
                normalized_density = np.zeros_like(density)
            
            x_left = x_pos - normalized_density
            color_obj = QColor(color)
            
            left_curve = pg.PlotDataItem(x=x_left, y=y_violin, 
                                        pen=pg.mkPen(color, width=2),
                                        fillLevel=x_pos,
                                        brush=pg.mkBrush(color_obj.red(), color_obj.green(), color_obj.blue(), alpha//2))
            plot_item.addItem(left_curve)
        except:
            pass
        
        q1 = np.percentile(values, 25)
        median = np.percentile(values, 50)
        q3 = np.percentile(values, 75)
        
        box_item = pg.QtWidgets.QGraphicsRectItem(
            x_pos, q1, plot_width/2, q3 - q1
        )
        box_item.setBrush(pg.mkBrush(color_obj.red(), color_obj.green(), color_obj.blue(), alpha))
        box_item.setPen(pg.mkPen(color, width=2))
        plot_item.addItem(box_item)
        
        if config.get('show_median', True):
            median_line = pg.PlotDataItem([x_pos, x_pos + plot_width/2], [median, median],
                                         pen=pg.mkPen('black', width=3))
            plot_item.addItem(median_line)

    def create_notched_box_plot(self, plot_item, x_pos, values, color, alpha, plot_width, config):
        """
        Create notched box plot.
        
        Args:
            plot_item: PyQtGraph plot item
            x_pos (float): X-axis position
            values (list): Data values
            color (str): Color hex code
            alpha (int): Alpha transparency value
            plot_width (float): Width of the plot
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        q1 = np.percentile(values, 25)
        median = np.percentile(values, 50)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1
        n = len(values)
        
        notch_extent = 1.57 * iqr / np.sqrt(n) if n > 0 else 0
        notch_lower = median - notch_extent
        notch_upper = median + notch_extent
        
        color_obj = QColor(color)
        
        notch_width = plot_width * 0.3
        
        box_points = [
            (x_pos - plot_width/2, q1),
            (x_pos + plot_width/2, q1),
            (x_pos + plot_width/2, notch_lower),
            (x_pos + notch_width/2, median),
            (x_pos + plot_width/2, notch_upper),
            (x_pos + plot_width/2, q3),
            (x_pos - plot_width/2, q3),
            (x_pos - plot_width/2, notch_upper),
            (x_pos - notch_width/2, median),
            (x_pos - plot_width/2, notch_lower),
        ]
        
        x_coords = [p[0] for p in box_points]
        y_coords = [p[1] for p in box_points]
        
        box_curve = pg.PlotDataItem(x=x_coords + [x_coords[0]], y=y_coords + [y_coords[0]], 
                                   pen=pg.mkPen(color, width=2),
                                   fillLevel=None,
                                   brush=pg.mkBrush(color_obj.red(), color_obj.green(), color_obj.blue(), alpha))
        plot_item.addItem(box_curve)
        
        if config.get('show_median', True):
            median_line = pg.PlotDataItem([x_pos - notch_width/2, x_pos + notch_width/2], [median, median],
                                         pen=pg.mkPen('black', width=3))
            plot_item.addItem(median_line)
        
        lower_whisker = max(q1 - 1.5 * iqr, min(values))
        upper_whisker = min(q3 + 1.5 * iqr, max(values))
        
        whisker_pen = pg.mkPen('black', width=2)
        whisker_line = pg.PlotDataItem([x_pos, x_pos], [q1, lower_whisker], pen=whisker_pen)
        plot_item.addItem(whisker_line)
        whisker_line = pg.PlotDataItem([x_pos, x_pos], [q3, upper_whisker], pen=whisker_pen)
        plot_item.addItem(whisker_line)

    def create_bar_plot_with_errors(self, plot_item, x_pos, values, color, alpha, plot_width, config):
        """
        Create bar plot with error bars.
        
        Args:
            plot_item: PyQtGraph plot item
            x_pos (float): X-axis position
            values (list): Data values
            color (str): Color hex code
            alpha (int): Alpha transparency value
            plot_width (float): Width of the plot
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        mean_value = np.mean(values)
        std_value = np.std(values)
        sem_value = std_value / np.sqrt(len(values))
        
        color_obj = QColor(color)
        
        bar_item = pg.QtWidgets.QGraphicsRectItem(
            x_pos - plot_width/2, 0, plot_width, mean_value
        )
        bar_item.setBrush(pg.mkBrush(color_obj.red(), color_obj.green(), color_obj.blue(), alpha))
        bar_item.setPen(pg.mkPen(color, width=2))
        plot_item.addItem(bar_item)
        
        error_pen = pg.mkPen('black', width=2)
        error_cap_width = plot_width * 0.3
        
        upper_error = mean_value + sem_value
        error_line = pg.PlotDataItem([x_pos, x_pos], [mean_value, upper_error], pen=error_pen)
        plot_item.addItem(error_line)
        error_cap = pg.PlotDataItem([x_pos - error_cap_width/2, x_pos + error_cap_width/2], 
                                   [upper_error, upper_error], pen=error_pen)
        plot_item.addItem(error_cap)
        
        lower_error = max(0, mean_value - sem_value)
        error_line = pg.PlotDataItem([x_pos, x_pos], [mean_value, lower_error], pen=error_pen)
        plot_item.addItem(error_line)
        error_cap = pg.PlotDataItem([x_pos - error_cap_width/2, x_pos + error_cap_width/2], 
                                   [lower_error, lower_error], pen=error_pen)
        plot_item.addItem(error_cap)

    def create_distribution_plot(self, plot_item, plot_data, config):
        """
        Create distribution plot for single sample with multiple elements.
        
        Args:
            plot_item: PyQtGraph plot item
            plot_data (dict): Dictionary of element data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        element_colors = config.get('element_colors', {})
        default_colors = ['#663399', '#2E86AB', '#A23B72', '#F18F01', '#C73E1D']
        
        sorted_plot_data = sort_element_dict_by_mass(plot_data)
        
        x_pos = 0
        x_positions = []
        x_labels = []
        
        for element_idx, (element_name, values) in enumerate(sorted_plot_data.items()):
            if values and len(values) > 0:
                data_type_display = config.get('data_type_display', 'Counts (Raw)')
                if data_type_display != 'Counts (Raw)':
                    filtered_values = [v for v in values if v > 0 and not np.isnan(v)]
                else:
                    filtered_values = values
                
                if filtered_values:
                    if config.get('log_y', False):
                        filtered_values = np.log10(np.array(filtered_values))
                    
                    self.create_single_plot(plot_item, x_pos, filtered_values, 
                                        None, element_name, config)
                    
                    x_positions.append(x_pos)
                    x_labels.append(element_name)
                    x_pos += 1
        
        if x_positions and x_labels:
            x_axis = plot_item.getAxis('bottom')
            x_axis.setTicks([list(zip(x_positions, x_labels))])
        
        data_type_display = config.get('data_type_display', 'Counts (Raw)')
        log_y = config.get('log_y', False)
        
        label_mapping = {
            'Counts (Raw)': 'Intensity (counts)',
            'Element Mass (fg)': 'Element Mass (fg)',
            'Particle Mass (fg)': 'Particle Mass (fg)', 
            'Element Moles (fmol)': 'Element Moles (fmol)',
            'Particle Moles (fmol)': 'Particle Moles (fmol)',
            'Element Diameter (nm)': 'Element Diameter (nm)',
            'Particle Diameter (nm)': 'Particle Diameter (nm)'
        }
        
        y_base_label = label_mapping.get(data_type_display, 'Values')
        y_label = f"log₁₀({y_base_label})" if log_y else y_base_label
        
        self.set_axis_labels_with_font(plot_item, "Elements", y_label, config)
        
        if not config.get('auto_y', True):
            plot_item.setYRange(config['y_min'], config['y_max'])
        
        if config.get('show_stats', True):
            self.add_statistics_text(plot_item, sorted_plot_data, config)
            
        
    def add_statistics_text(self, plot_item, plot_data, config):
        """
        Add statistics text box to the plot.
        
        Args:
            plot_item: PyQtGraph plot item
            plot_data (dict): Dictionary of element data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        if not plot_data:
            return
        
        data_type = config.get('data_type_display', 'Counts (Raw)')
        plot_shape = config.get('plot_shape', 'Box Plot (Traditional)')
        
        stats_text = f"Statistics ({data_type}):\nPlot: {plot_shape}\n"
        
        for element_label, values in plot_data.items():
            if values and len(values) > 0:
                if data_type != 'Counts (Raw)':
                    valid_values = [v for v in values if v > 0 and not np.isnan(v)]
                else:
                    valid_values = values
                
                if valid_values:
                    particle_count = len(valid_values)
                    mean_value = np.mean(valid_values)
                    median_value = np.median(valid_values)
                    q1 = np.percentile(valid_values, 25)
                    q3 = np.percentile(valid_values, 75)
                    std_value = np.std(valid_values)
                    
                    if 'Mass' in data_type:
                        stats_text += f"{element_label}: {particle_count} particles\n"
                        stats_text += f"  Mean: {mean_value:.2f}±{std_value:.2f} fg\n"
                        stats_text += f"  Median: {median_value:.2f} fg (Q1: {q1:.2f}, Q3: {q3:.2f})\n"
                    elif 'Moles' in data_type:
                        stats_text += f"{element_label}: {particle_count} particles\n"
                        stats_text += f"  Mean: {mean_value:.4f}±{std_value:.4f} fmol\n"
                        stats_text += f"  Median: {median_value:.4f} fmol (Q1: {q1:.4f}, Q3: {q3:.4f})\n"
                    elif 'Diameter' in data_type:
                        stats_text += f"{element_label}: {particle_count} particles\n"
                        stats_text += f"  Mean: {mean_value:.1f}±{std_value:.1f} nm\n"
                        stats_text += f"  Median: {median_value:.1f} nm (Q1: {q1:.1f}, Q3: {q3:.1f})\n"
                    else:
                        stats_text += f"{element_label}: {particle_count} particles\n"
                        stats_text += f"  Mean: {mean_value:.1f}±{std_value:.1f}\n"
                        stats_text += f"  Median: {median_value:.1f} (Q1: {q1:.1f}, Q3: {q3:.1f})\n"
        
        stats_text_item = pg.TextItem(stats_text, anchor=(0, 1), 
                                     border=pg.mkPen(color='black', width=1),
                                     fill=pg.mkBrush(color=(255, 255, 255, 200)))
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


class BoxPlotNode(QObject):
    """
    Enhanced box plot node with multiple shape support.
    """
    
    position_changed = Signal(object)
    configuration_changed = Signal()
    
    def __init__(self, parent_window=None):
        """
        Initialize box plot node.
        
        Args:
            parent_window: Parent window widget
        """
        super().__init__()
        self.title = "Distribution Plot"
        self.node_type = "box_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.config = {
            'data_type_display': 'Counts (Raw)',
            'plot_shape': 'Box Plot (Traditional)',
            'violin_bandwidth': 0.2,
            'strip_jitter': 0.2,
            'show_outliers': True,
            'show_mean': True,
            'show_median': True,
            'alpha': 0.7,
            'log_y': False,
            'show_stats': True,
            'plot_width': 0.8,
            'y_min': 0,
            'y_max': 100,
            'auto_y': True,
            'element_colors': {},
            'display_mode': 'Side by Side',
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
        Set position of the node.
        
        Args:
            pos: Position coordinates
        
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
            bool: True if configuration was successful
        """
        dialog = BoxPlotDisplayDialog(self, parent_window)
        dialog.exec()
        return True
        
    def process_data(self, input_data):
        """
        Process input data and update plot.
        
        Args:
            input_data (dict): Input data dictionary
        
        Returns:
            None
        """
        if not input_data:
            print("No input data received for distribution plot")
            return
            
        print(f"Distribution plot received data: {input_data.get('type', 'unknown')}")
        self.input_data = input_data
        
        self.configuration_changed.emit()
        
    def extract_plot_data(self):
        """
        Extract plottable data from input.
        
        Returns:
            dict or None: Extracted plot data
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
            'Particle Moles (fmol)': 'particle_moles_fmol',
            'Element Diameter (nm)': 'element_diameter_nm',
            'Particle Diameter (nm)': 'particle_diameter_nm'
        }
        
        data_key = data_key_mapping.get(data_type_display, 'elements')
        
        if input_type == 'sample_data':
            return self._extract_single_sample_data(data_key)
        elif input_type == 'multiple_sample_data':
            return self._extract_multiple_sample_data(data_key)
            
        return None
    
    def _extract_single_sample_data(self, data_key):
        """
        Extract data for single sample.
        
        Args:
            data_key (str): Key for data type in particle dictionary
        
        Returns:
            dict or None: Dictionary of element data
        """
        particles = self.input_data.get('particle_data')
        
        if not particles:
            print(f"No filtered particle data available from sample selector")
            return None
        
        element_data = {}
        for particle in particles:
            particle_data_dict = particle.get(data_key, {})
            
            for element_name, value in particle_data_dict.items():
                if data_key == 'elements':
                    if value > 0:
                        if element_name not in element_data:
                            element_data[element_name] = []
                        element_data[element_name].append(value)
                else:
                    if value > 0 and not np.isnan(value):
                        if element_name not in element_data:
                            element_data[element_name] = []
                        element_data[element_name].append(value)
        
        return sort_element_dict_by_mass(element_data)

    def _extract_multiple_sample_data(self, data_key):
        """
        Extract data for multiple samples.
        
        Args:
            data_key (str): Key for data type in particle dictionary
        
        Returns:
            dict or None: Dictionary of sample data
        """
        particles = self.input_data.get('particle_data', [])
        
        if not particles:
            print("No filtered particle data available from sample selector")
            return None
        
        sample_names = self.input_data.get('sample_names', [])
        
        sample_data = {}
        for sample_name in sample_names:
            sample_data[sample_name] = {}
        
        for particle in particles:
            source_sample = particle.get('source_sample')
            if source_sample and source_sample in sample_data:
                particle_data_dict = particle.get(data_key, {})
                
                for element_name, value in particle_data_dict.items():
                    if data_key == 'elements':
                        if value > 0:
                            if element_name not in sample_data[source_sample]:
                                sample_data[source_sample][element_name] = []
                            sample_data[source_sample][element_name].append(value)
                    else:
                        if value > 0 and not np.isnan(value):
                            if element_name not in sample_data[source_sample]:
                                sample_data[source_sample][element_name] = []
                            sample_data[source_sample][element_name].append(value)
        
        sorted_sample_data = {}
        for sample_name, data in sample_data.items():
            if data:
                sorted_sample_data[sample_name] = sort_element_dict_by_mass(data)
        
        return sorted_sample_data