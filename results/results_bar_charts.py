from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                              QLabel, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                              QDialogButtonBox, QGroupBox, QColorDialog, QPushButton,
                              QLineEdit, QGraphicsProxyWidget, QFrame, QScrollArea, QWidget, QListWidgetItem, QListWidget, QMessageBox)
from PySide6.QtCore import Qt, Signal, QObject
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


class HistogramDisplayDialog(QDialog):

    def __init__(self, histogram_node, parent_window=None):
        """
        Initialize the histogram display dialog.
        
        Args:
            histogram_node: Histogram node instance containing configuration and data
            parent_window: Parent window widget (optional)
        
        Returns:
            None
        """
        super().__init__(parent_window)
        self.histogram_node = histogram_node
        self.parent_window = parent_window
        
        self.setWindowTitle("Particle Data Histogram Analysis")
        self.setMinimumSize(1400, 800)
        
        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        self.setup_ui()
        self.update_display()
        
        self.histogram_node.configuration_changed.connect(self.update_display)
        
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
        return (hasattr(self.histogram_node, 'input_data') and 
                self.histogram_node.input_data and 
                self.histogram_node.input_data.get('type') == 'multiple_sample_data')
        
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
        Create the histogram configuration panel with all settings.
        
        Creates a scrollable panel containing configuration options for:
        - Display mode (for multiple samples)
        - Data type selection
        - Single element enhancements (density curves, median lines)
        - Plot options (bins, transparency, log scales, statistics)
        - Font settings
        - Axis limits
        - Element and sample colors
        
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
        
        title = QLabel("Histogram Settings")
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
            self.display_mode_combo.setCurrentText(self.histogram_node.config.get('display_mode', 'Overlaid (Different Colors)'))
            self.display_mode_combo.currentTextChanged.connect(self.on_config_changed)
            multiple_layout.addRow("Display Mode:", self.display_mode_combo)
            
            self.normalize_samples_checkbox = QCheckBox()
            self.normalize_samples_checkbox.setChecked(self.histogram_node.config.get('normalize_samples', False))
            self.normalize_samples_checkbox.stateChanged.connect(self.on_config_changed)
            multiple_layout.addRow("Normalize by Sample Size:", self.normalize_samples_checkbox)
            
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
        self.data_type_combo.setCurrentText(self.histogram_node.config.get('data_type_display', 'Counts (Raw)'))
        self.data_type_combo.currentTextChanged.connect(self.on_data_type_changed)
        data_layout.addWidget(self.data_type_combo)
        
        layout.addWidget(data_group)
        
        single_element_group = QGroupBox("Single Element Enhancement")
        single_element_layout = QFormLayout(single_element_group)
        
        self.show_curve_checkbox = QCheckBox()
        self.show_curve_checkbox.setChecked(self.histogram_node.config.get('show_curve', True))
        self.show_curve_checkbox.stateChanged.connect(self.on_config_changed)
        single_element_layout.addRow("Show Density Curve:", self.show_curve_checkbox)
        
        self.curve_type_combo = QComboBox()
        self.curve_type_combo.addItems(['Kernel Density', 'Log-Normal Fit', 'Normal Fit', 'Gamma Fit'])
        self.curve_type_combo.setCurrentText(self.histogram_node.config.get('curve_type', 'Kernel Density'))
        self.curve_type_combo.currentTextChanged.connect(self.on_config_changed)
        single_element_layout.addRow("Curve Type:", self.curve_type_combo)
        
        self.show_median_checkbox = QCheckBox()
        self.show_median_checkbox.setChecked(self.histogram_node.config.get('show_median', True))
        self.show_median_checkbox.stateChanged.connect(self.on_config_changed)
        single_element_layout.addRow("Show Median Line:", self.show_median_checkbox)
        
        curve_color_layout = QHBoxLayout()
        self.curve_color_button = QPushButton()
        self.curve_color_button.setFixedSize(60, 25)
        curve_color = self.histogram_node.config.get('curve_color', '#2C3E50')
        self.curve_color_button.setStyleSheet(f"background-color: {curve_color}; border: 1px solid black;")
        self.curve_color_button.clicked.connect(self.select_curve_color)
        curve_color_layout.addWidget(self.curve_color_button)
        curve_color_layout.addStretch()
        single_element_layout.addRow("Curve Color:", curve_color_layout)
        
        layout.addWidget(single_element_group)
        
        plot_group = QGroupBox("Plot Options")
        plot_layout = QFormLayout(plot_group)
        
        self.bins_spin = QSpinBox()
        self.bins_spin.setRange(5, 100)
        self.bins_spin.setValue(self.histogram_node.config.get('bins', 20))
        self.bins_spin.valueChanged.connect(self.on_config_changed)
        plot_layout.addRow("Number of Bins:", self.bins_spin)
        
        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setRange(0.1, 1.0)
        self.alpha_spin.setSingleStep(0.1)
        self.alpha_spin.setDecimals(1)
        self.alpha_spin.setValue(self.histogram_node.config.get('alpha', 0.7))
        self.alpha_spin.valueChanged.connect(self.on_config_changed)
        plot_layout.addRow("Transparency:", self.alpha_spin)
        
        self.log_x_checkbox = QCheckBox()
        self.log_x_checkbox.setChecked(self.histogram_node.config.get('log_x', False))
        self.log_x_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Log X-axis:", self.log_x_checkbox)
        
        self.log_y_checkbox = QCheckBox()
        self.log_y_checkbox.setChecked(self.histogram_node.config.get('log_y', False))
        self.log_y_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Log Y-axis:", self.log_y_checkbox)
        
        self.show_stats_checkbox = QCheckBox()
        self.show_stats_checkbox.setChecked(self.histogram_node.config.get('show_stats', True))
        self.show_stats_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Show Statistics:", self.show_stats_checkbox)
        
        layout.addWidget(plot_group)
        
        font_group = QGroupBox("Font Settings")
        font_layout = QFormLayout(font_group)
        
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(self.get_font_families())
        self.font_family_combo.setCurrentText(self.histogram_node.config.get('font_family', 'Times New Roman'))
        self.font_family_combo.currentTextChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Family:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(self.histogram_node.config.get('font_size', 18))
        self.font_size_spin.valueChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Size:", self.font_size_spin)
        
        font_style_layout = QHBoxLayout()
        self.font_bold_checkbox = QCheckBox("Bold")
        self.font_bold_checkbox.setChecked(self.histogram_node.config.get('font_bold', False))
        self.font_bold_checkbox.stateChanged.connect(self.on_config_changed)
        self.font_italic_checkbox = QCheckBox("Italic")
        self.font_italic_checkbox.setChecked(self.histogram_node.config.get('font_italic', False))
        self.font_italic_checkbox.stateChanged.connect(self.on_config_changed)
        font_style_layout.addWidget(self.font_bold_checkbox)
        font_style_layout.addWidget(self.font_italic_checkbox)
        font_style_layout.addStretch()
        font_layout.addRow("Font Style:", font_style_layout)
        
        self.font_color_button = QPushButton()
        self.font_color = QColor(self.histogram_node.config.get('font_color', '#000000'))
        self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 30px;")
        self.font_color_button.clicked.connect(lambda: self.choose_color('font'))
        font_layout.addRow("Font Color:", self.font_color_button)
        
        layout.addWidget(font_group)
        
        limits_group = QGroupBox("Axis Limits")
        limits_layout = QFormLayout(limits_group)
        
        x_layout = QHBoxLayout()
        self.x_min_spin = QDoubleSpinBox()
        self.x_min_spin.setRange(-999999, 999999)
        self.x_min_spin.setValue(self.histogram_node.config.get('x_min', 0))
        self.x_min_spin.valueChanged.connect(self.on_config_changed)
        
        self.x_max_spin = QDoubleSpinBox()
        self.x_max_spin.setRange(-999999, 999999)
        self.x_max_spin.setValue(self.histogram_node.config.get('x_max', 1000))
        self.x_max_spin.valueChanged.connect(self.on_config_changed)
        
        self.auto_x_checkbox = QCheckBox("Auto")
        self.auto_x_checkbox.setChecked(self.histogram_node.config.get('auto_x', True))
        self.auto_x_checkbox.stateChanged.connect(self.on_config_changed)
        self.auto_x_checkbox.stateChanged.connect(self.toggle_x_limits)
        
        x_layout.addWidget(self.x_min_spin)
        x_layout.addWidget(QLabel("to"))
        x_layout.addWidget(self.x_max_spin)
        x_layout.addWidget(self.auto_x_checkbox)
        limits_layout.addRow("X Range:", x_layout)
        
        y_layout = QHBoxLayout()
        self.y_min_spin = QDoubleSpinBox()
        self.y_min_spin.setRange(0, 999999)
        self.y_min_spin.setValue(self.histogram_node.config.get('y_min', 0))
        self.y_min_spin.valueChanged.connect(self.on_config_changed)
        
        self.y_max_spin = QDoubleSpinBox()
        self.y_max_spin.setRange(0, 999999)
        self.y_max_spin.setValue(self.histogram_node.config.get('y_max', 100))
        self.y_max_spin.valueChanged.connect(self.on_config_changed)
        
        self.auto_y_checkbox = QCheckBox("Auto")
        self.auto_y_checkbox.setChecked(self.histogram_node.config.get('auto_y', True))
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
            font_family = self.histogram_node.config.get('font_family', 'Times New Roman')
            font_size = self.histogram_node.config.get('font_size', 18)
            is_bold = self.histogram_node.config.get('font_bold', False)
            is_italic = self.histogram_node.config.get('font_italic', False)
            font_color = self.histogram_node.config.get('font_color', '#000000')
            
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
                            
                except Exception as e:
                    print(f"Warning: Could not update legend font settings: {e}")
            
            x_axis.update()
            y_axis.update()
            if legend is not None:
                legend.update()
            
        except Exception as e:
            print(f"Error applying plot settings: {e}")
    
    def select_curve_color(self):
        """
        Open color dialog for density curve color selection.
        
        Args:
            None
        
        Returns:
            None
        """
        current_color = self.histogram_node.config.get('curve_color', '#2C3E50')
        color = QColorDialog.getColor(QColor(current_color), self, "Select Curve Color")
        
        if color.isValid():
            color_hex = color.name()
            self.curve_color_button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            self.histogram_node.config['curve_color'] = color_hex
            self.on_config_changed()
    
    def on_data_type_changed(self):
        """
        Handle data type selection change event.
        
        Args:
            None
        
        Returns:
            None
        """
        self.on_config_changed()
    
    def update_sample_color_controls(self):
        """
        Update color controls for multiple samples with editable names.
        
        Creates color picker buttons and name edit fields for each sample
        with reset functionality.
        
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
        
        sample_colors = self.histogram_node.config.get('sample_colors', {})
        
        sample_name_mappings = self.histogram_node.config.get('sample_name_mappings', {})
        
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
        
        self.histogram_node.config['sample_colors'] = sample_colors
        self.histogram_node.config['sample_name_mappings'] = sample_name_mappings

    def on_sample_name_changed(self, original_name, new_name):
        """
        Handle sample name change event.
        
        Args:
            original_name (str): Original sample name
            new_name (str): New custom display name
        
        Returns:
            None
        """
        if 'sample_name_mappings' not in self.histogram_node.config:
            self.histogram_node.config['sample_name_mappings'] = {}
        
        self.histogram_node.config['sample_name_mappings'][original_name] = new_name
        
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
        
        if 'sample_name_mappings' in self.histogram_node.config:
            self.histogram_node.config['sample_name_mappings'].pop(original_name, None)
        
        self.on_config_changed()

    def get_display_name(self, original_name):
        """
        Get display name for a sample (either custom or original).
        
        Args:
            original_name (str): Original sample name
        
        Returns:
            str: Display name (custom if set, otherwise original)
        """
        mappings = self.histogram_node.config.get('sample_name_mappings', {})
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
            return self.histogram_node.input_data.get('sample_names', [])
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
        current_color = self.histogram_node.config.get('sample_colors', {}).get(sample_name, '#3B82F6')
        display_name = self.get_display_name(sample_name)
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {display_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'sample_colors' not in self.histogram_node.config:
                self.histogram_node.config['sample_colors'] = {}
            self.histogram_node.config['sample_colors'][sample_name] = color_hex
            
            self.on_config_changed()
    
    def download_figure(self):
        """
        Download the current figure using PyQtGraph exporters.
        
        Exports the histogram plot to PNG or SVG format based on user selection.
        
        Args:
            None
        
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Histogram Plot",
            "histogram_plot.png",
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
                                    f"Histogram saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", 
                                f"Failed to save:\n{str(e)}")

    def update_color_controls(self):
        """
        Update color controls based on available elements.
        
        Creates color picker buttons for each element with default color assignments.
        
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
        
        default_colors = ['#663399', '#2E86AB', '#A23B72', '#F18F01', '#C73E1D', 
                         '#7209B7', '#F72585', '#4361EE', '#277DA1', '#F8961E']
        
        element_colors = self.histogram_node.config.get('element_colors', {})
        
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
        
        self.histogram_node.config['element_colors'] = element_colors
    
    def get_available_elements(self):
        """
        Get available elements from the histogram node's data, sorted by mass number.
        
        Attempts to extract elements from plot data first, then falls back to
        input data. Elements are sorted by their mass number for consistent ordering.
        
        Args:
            None
        
        Returns:
            list: List of element label strings sorted by mass number
        """
        if hasattr(self.histogram_node, 'extract_plot_data'):
            plot_data = self.histogram_node.extract_plot_data()
            if plot_data:
                if self.is_multiple_sample_data():
                    all_elements = set()
                    for sample_data in plot_data.values():
                        if isinstance(sample_data, dict):
                            all_elements.update(sample_data.keys())
                    return sort_elements_by_mass(list(all_elements))
                else:
                    return sort_elements_by_mass(list(plot_data.keys()))
        
        if not self.histogram_node.input_data:
            return []
        
        data_type = self.histogram_node.input_data.get('type')
        
        if data_type in ['sample_data', 'multiple_sample_data']:
            selected_isotopes = self.histogram_node.input_data.get('selected_isotopes', [])
            if selected_isotopes:
                element_labels = [isotope['label'] for isotope in selected_isotopes]
                return sort_elements_by_mass(element_labels)
        
        return []
    
    def sort_plot_data_by_mass(self, plot_data):
        """
        Sort plot data dictionary by mass number of element keys.
        
        Args:
            plot_data (dict): Dictionary with element names as keys
        
        Returns:
            dict: Dictionary sorted by element mass numbers
        """
        return sort_element_dict_by_mass(plot_data)
                
    def select_element_color(self, element_name, button):
        """
        Open color dialog for element color selection.
        
        Args:
            element_name (str): Name of the element to set color for
            button (QPushButton): Button widget to update with new color
        
        Returns:
            None
        """
        current_color = self.histogram_node.config.get('element_colors', {}).get(element_name, '#663399')
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {element_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'element_colors' not in self.histogram_node.config:
                self.histogram_node.config['element_colors'] = {}
            self.histogram_node.config['element_colors'][element_name] = color_hex
            
            self.on_config_changed()
    
    def toggle_x_limits(self):
        """
        Enable/disable X-axis limit controls based on auto setting.
        
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
        Enable/disable Y-axis limit controls based on auto setting.
        
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
        histogram update.
        
        Args:
            None
        
        Returns:
            None
        """
        config_updates = {
            'data_type_display': self.data_type_combo.currentText(),
            'show_curve': self.show_curve_checkbox.isChecked(),
            'curve_type': self.curve_type_combo.currentText(),
            'show_median': self.show_median_checkbox.isChecked(),
            'bins': self.bins_spin.value(),
            'alpha': self.alpha_spin.value(),
            'log_x': self.log_x_checkbox.isChecked(),
            'log_y': self.log_y_checkbox.isChecked(),
            'show_stats': self.show_stats_checkbox.isChecked(),
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
        
        self.histogram_node.config.update(config_updates)
        
        self.update_display()

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
   
    def update_display(self):
        """
        Update the histogram display with support for multiple samples.
        
        Clears existing plot and recreates based on current configuration
        and data. Handles both single and multiple sample modes.
        
        Args:
            None
        
        Returns:
            None
        """
        try:
            self.plot_widget.clear()
            
            plot_data = self.histogram_node.extract_plot_data()
            
            if not plot_data:
                plot_item = self.plot_widget.addPlot()
                text_item = pg.TextItem("No particle data available\nConnect to Sample Selector\nand run particle detection", 
                                      anchor=(0.5, 0.5), color='gray')
                plot_item.addItem(text_item)
                text_item.setPos(0.5, 0.5)
                plot_item.hideAxis('left')
                plot_item.hideAxis('bottom')
            else:
                config = self.histogram_node.config
                
                if self.is_multiple_sample_data():
                    self.create_multiple_sample_histogram(plot_data, config)
                else:
                    plot_item = self.plot_widget.addPlot()
                    self.create_histogram_plot(plot_item, plot_data, config)
                    self.apply_plot_settings(plot_item)
            
        except Exception as e:
            print(f"Error updating histogram display: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def create_multiple_sample_histogram(self, plot_data, config):
        """
        Create histogram plot for multiple samples with different display modes.
        
        Args:
            plot_data (dict): Dictionary of sample data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        display_mode = config.get('display_mode', 'Overlaid (Different Colors)')
        sample_names = list(plot_data.keys())
        
        if display_mode == 'Individual Subplots':
            self.create_subplot_histograms(plot_data, config)
        elif display_mode == 'Side by Side Subplots':
            self.create_side_by_side_histograms(plot_data, config)
        else:
            plot_item = self.plot_widget.addPlot()
            self.create_combined_histogram(plot_item, plot_data, config)
            self.apply_plot_settings(plot_item)
    
    def create_subplot_histograms(self, plot_data, config):
        """
        Create individual subplots for each sample.
        
        Arranges histograms in a grid layout with each sample in its own subplot.
        
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
                self.create_sample_specific_histogram(plot_item, sample_data, config, sample_color)
                
                title_text = f"{self.get_display_name(sample_name)}"
                plot_item.setTitle(title_text)
                
                data_type_display = config.get('data_type_display', 'Counts (Raw)')
                log_x = config.get('log_x', False)
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
                
                x_base_label = label_mapping.get(data_type_display, 'Values per Particle')
                y_base_label = 'Number of Particles'
                
                x_label = f"log₁₀({x_base_label})" if log_x else x_base_label
                y_label = f"log₁₀({y_base_label})" if log_y else y_base_label
                
                self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
                
                self.apply_plot_settings(plot_item)

    def create_side_by_side_histograms(self, plot_data, config):
        """
        Create side-by-side histogram plots.
        
        Arranges histograms in a single row for easy comparison across samples.
        
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
                self.create_sample_specific_histogram(plot_item, sample_data, config, sample_color)
                
                title_text = f"{self.get_display_name(sample_name)}"
                plot_item.setTitle(title_text)
                
                data_type_display = config.get('data_type_display', 'Counts (Raw)')
                log_x = config.get('log_x', False)
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
                
                x_base_label = label_mapping.get(data_type_display, 'Values per Particle')
                y_base_label = 'Number of Particles'
                
                x_label = f"log₁₀({x_base_label})" if log_x else x_base_label
                y_label = f"log₁₀({y_base_label})" if log_y else y_base_label
                
                if i == 0:
                    self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
                else:
                    self.set_axis_labels_with_font(plot_item, x_label, "", config)
                
                self.apply_plot_settings(plot_item)
                
    def create_combined_histogram(self, plot_item, plot_data, config):
        """
        Create combined histogram plot (overlaid).
        
        Overlays histograms from all samples on a single plot with distinct
        colors and adds legend for identification.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            plot_data (dict): Dictionary of sample data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_colors = config.get('sample_colors', {})
        default_colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
        
        data_type_display = config.get('data_type_display', 'Counts (Raw)')
        log_x = config.get('log_x', False)
        log_y = config.get('log_y', False)
        
        legend_items = []
        
        for i, (sample_name, sample_data) in enumerate(plot_data.items()):
            if sample_data:
                sample_color = sample_colors.get(sample_name, default_colors[i % len(default_colors)])
                
                combined_values = []
                for element_values in sample_data.values():
                    if config.get('data_type_display', 'Counts (Raw)') != 'Counts (Raw)':
                        filtered_values = [v for v in element_values if v > 0 and not np.isnan(v)]
                        combined_values.extend(filtered_values)
                    else:
                        combined_values.extend(element_values)
                
                if combined_values:
                    if log_x:
                        valid_mask = np.array(combined_values) > 0
                        if np.any(valid_mask):
                            combined_values = np.log10(np.array(combined_values)[valid_mask])
                        else:
                            continue
                    
                    bins = config.get('bins', 20)
                    y, bin_edges = np.histogram(combined_values, bins=bins)
                    
                    if log_y:
                        y = np.log10(y + 1)
                    
                    color_obj = QColor(sample_color)
                    alpha = int(config.get('alpha', 0.7) * 255)
                    color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), alpha)
                    
                    step_plot = pg.PlotDataItem(x=bin_edges, y=y,
                                               stepMode=True,
                                               fillLevel=0,
                                               brush=pg.mkBrush(*color_rgba),
                                               pen=pg.mkPen(color=sample_color, width=1))
                    plot_item.addItem(step_plot)
                    
                    legend_items.append((step_plot, self.get_display_name(sample_name)))
        
        label_mapping = {
            'Counts (Raw)': 'Intensity (counts)',
            'Element Mass (fg)': 'Element Mass (fg)',
            'Particle Mass (fg)': 'Particle Mass (fg)', 
            'Element Moles (fmol)': 'Element Moles (fmol)',
            'Particle Moles (fmol)': 'Particle Moles (fmol)',
            'Element Diameter (nm)': 'Element Diameter (nm)',
            'Particle Diameter (nm)': 'Particle Diameter (nm)'
        }
        
        x_base_label = label_mapping.get(data_type_display, 'Values per Particle')
        y_base_label = 'Number of Particles'
        
        x_label = f"log₁₀({x_base_label})" if log_x else x_base_label
        y_label = f"log₁₀({y_base_label})" if log_y else y_base_label
        
        self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
        
        if legend_items:
            legend = plot_item.addLegend()
            for item, name in legend_items:
                legend.addItem(item, name)

    def create_sample_specific_histogram(self, plot_item, sample_data, config, sample_color):
        """
        Create histogram plot for a specific sample.
        
        Handles both single element (with enhancements) and multiple element cases.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            sample_data (dict): Sample element data dictionary
            config (dict): Configuration dictionary
            sample_color (str): Hex color string for sample
        
        Returns:
            None
        """
        element_colors = config.get('element_colors', {})
        data_type_display = config.get('data_type_display', 'Counts (Raw)')
        log_x = config.get('log_x', False)
        log_y = config.get('log_y', False)
        
        sorted_sample_data = self.sort_plot_data_by_mass(sample_data)
        is_single_element = len(sorted_sample_data) == 1
        
        if is_single_element:
            element_name = list(sorted_sample_data.keys())[0]
            values = sorted_sample_data[element_name]
            
            if values and len(values) > 0:
                if data_type_display != 'Counts (Raw)':
                    values = [v for v in values if v > 0 and not np.isnan(v)]
                    if not values:
                        return
                
                if log_x:
                    valid_mask = np.array(values) > 0
                    if np.any(valid_mask):
                        values = np.log10(np.array(values)[valid_mask])
                    else:
                        return
                
                bins = config.get('bins', 20)
                y, bin_edges = np.histogram(values, bins=bins)
                
                if log_y:
                    y = np.log10(y + 1)
                
                element_color = element_colors.get(element_name, sample_color)
                
                color_obj = QColor(element_color)
                alpha = int(config.get('alpha', 0.7) * 255)
                color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), alpha)
                
                step_plot = pg.PlotDataItem(x=bin_edges, y=y,
                                           stepMode=True,
                                           fillLevel=0,
                                           brush=pg.mkBrush(*color_rgba),
                                           pen=pg.mkPen(color=element_color, width=1))
                plot_item.addItem(step_plot)
                
                if config.get('show_curve', True) and len(values) > 5:
                    self.add_density_curve_to_plot(plot_item, values, config, bin_edges, len(values))
                
                if config.get('show_median', True):
                    self.add_median_line_to_plot(plot_item, values, config)
        else:
            legend_items = []
            
            for i, (element_name, values) in enumerate(sorted_sample_data.items()):
                if values and len(values) > 0:
                    if data_type_display != 'Counts (Raw)':
                        values = [v for v in values if v > 0 and not np.isnan(v)]
                        if not values:
                            continue
                    
                    if log_x:
                        valid_mask = np.array(values) > 0
                        if np.any(valid_mask):
                            values = np.log10(np.array(values)[valid_mask])
                        else:
                            continue
                    
                    bins = config.get('bins', 20)
                    y, bin_edges = np.histogram(values, bins=bins)
                    
                    if log_y:
                        y = np.log10(y + 1)
                    
                    element_color = element_colors.get(element_name, sample_color)
                    
                    color_obj = QColor(element_color)
                    alpha = int(config.get('alpha', 0.7) * 255)
                    color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), alpha)
                    
                    step_plot = pg.PlotDataItem(x=bin_edges, y=y,
                                               stepMode=True,
                                               fillLevel=0,
                                               brush=pg.mkBrush(*color_rgba),
                                               pen=pg.mkPen(color=element_color, width=1))
                    plot_item.addItem(step_plot)
                    
                    legend_items.append((step_plot, element_name))
            
            if len(legend_items) > 1:
                legend = plot_item.addLegend()
                for item, name in legend_items:
                    legend.addItem(item, name)

    def create_histogram_plot(self, plot_item, plot_data, config):
        """
        Create the histogram plot (single sample).
        
        Handles both single element (with enhancements like density curves and
        median lines) and multiple element cases (with legend).
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            plot_data (dict): Plot data dictionary with element data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        element_colors = config.get('element_colors', {})
        data_type_display = config.get('data_type_display', 'Counts (Raw)')
        log_x = config.get('log_x', False)
        log_y = config.get('log_y', False)
        
        sorted_plot_data = self.sort_plot_data_by_mass(plot_data)

        is_single_element = len(sorted_plot_data) == 1
        
        if is_single_element:
            element_name = list(sorted_plot_data.keys())[0]
            values = sorted_plot_data[element_name]
            
            if values and len(values) > 0:
                if data_type_display != 'Counts (Raw)':
                    values = [v for v in values if v > 0 and not np.isnan(v)]
                    if not values:
                        return
                
                if log_x:
                    valid_mask = np.array(values) > 0
                    if np.any(valid_mask):
                        values = np.log10(np.array(values)[valid_mask])
                    else:
                        return
                
                bins = config.get('bins', 20)
                y, bin_edges = np.histogram(values, bins=bins)
                
                if log_y:
                    y = np.log10(y + 1)
                
                element_color = element_colors.get(element_name, '#663399')
                
                color_obj = QColor(element_color)
                alpha = int(config.get('alpha', 0.7) * 255)
                color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), alpha)
                
                step_plot = pg.PlotDataItem(x=bin_edges, y=y,
                                           stepMode=True,
                                           fillLevel=0,
                                           brush=pg.mkBrush(*color_rgba),
                                           pen=pg.mkPen(color=element_color, width=1))
                plot_item.addItem(step_plot)
                
                if config.get('show_curve', True) and len(values) > 5:
                    self.add_density_curve_to_plot(plot_item, values, config, bin_edges, len(values))
                
                if config.get('show_median', True):
                    self.add_median_line_to_plot(plot_item, values, config)
        else:
            legend_items = []
            
            for i, (element_name, values) in enumerate(sorted_plot_data.items()): 
                if values and len(values) > 0:
                    if data_type_display != 'Counts (Raw)':
                        values = [v for v in values if v > 0 and not np.isnan(v)]
                        if not values:
                            continue
                    
                    if log_x:
                        valid_mask = np.array(values) > 0
                        if np.any(valid_mask):
                            values = np.log10(np.array(values)[valid_mask])
                        else:
                            continue
                    
                    bins = config.get('bins', 20)
                    y, bin_edges = np.histogram(values, bins=bins)
                    
                    if log_y:
                        y = np.log10(y + 1)
                    
                    element_color = element_colors.get(element_name, '#663399')
                    
                    color_obj = QColor(element_color)
                    alpha = int(config.get('alpha', 0.7) * 255)
                    color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), alpha)
                    
                    step_plot = pg.PlotDataItem(x=bin_edges, y=y,
                                               stepMode=True,
                                               fillLevel=0,
                                               brush=pg.mkBrush(*color_rgba),
                                               pen=pg.mkPen(color=element_color, width=1))
                    plot_item.addItem(step_plot)
                    
                    legend_items.append((step_plot, element_name))
            
            if len(legend_items) > 1:
                legend = plot_item.addLegend()
                for item, name in legend_items:
                    legend.addItem(item, name)
        
        label_mapping = {
            'Counts (Raw)': 'Intensity (counts)',
            'Element Mass (fg)': 'Element Mass (fg)',
            'Particle Mass (fg)': 'Particle Mass (fg)', 
            'Element Moles (fmol)': 'Element Moles (fmol)',
            'Particle Moles (fmol)': 'Particle Moles (fmol)',
            'Element Diameter (nm)': 'Element Diameter (nm)',
            'Particle Diameter (nm)': 'Particle Diameter (nm)'
        }
        
        x_base_label = label_mapping.get(data_type_display, 'Values per Particle')
        y_base_label = 'Number of Particles'
        
        x_label = f"log₁₀({x_base_label})" if log_x else x_base_label
        y_label = f"log₁₀({y_base_label})" if log_y else y_base_label
        
        self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
        
        if not config.get('auto_x', True):
            plot_item.setXRange(config['x_min'], config['x_max'])
        if not config.get('auto_y', True):
            plot_item.setYRange(config['y_min'], config['y_max'])
        
        if config.get('show_stats', True):
            self.add_statistics_text(plot_item, plot_data, config)

    def add_density_curve_to_plot(self, plot_item, values, config, bin_edges, total_count):
        """
        Add density curve overlay scaled to match count histogram.
        
        Supports multiple curve types: kernel density, log-normal, normal, and gamma fits.
        The density curve is automatically scaled to match histogram counts.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            values (list): Data values for curve fitting
            config (dict): Configuration dictionary
            bin_edges (ndarray): Bin edges from histogram
            total_count (int): Total number of data points
        
        Returns:
            None
        """
        curve_type = config.get('curve_type', 'Kernel Density')
        curve_color = config.get('curve_color', '#2C3E50')
        
        try:
            if len(bin_edges) > 1:
                bin_width = bin_edges[1] - bin_edges[0]
            else:
                bin_width = 1.0
            
            x_min, x_max = min(values), max(values)
            x_range = x_max - x_min
            x_curve = np.linspace(x_min - 0.1*x_range, x_max + 0.1*x_range, 200)
            
            if curve_type == 'Kernel Density':
                kde = gaussian_kde(values)
                y_curve = kde(x_curve)
                
            elif curve_type == 'Log-Normal Fit':
                if all(v > 0 for v in values):
                    shape, loc, scale = stats.lognorm.fit(values, floc=0)
                    y_curve = stats.lognorm.pdf(x_curve, shape, loc, scale)
                else:
                    kde = gaussian_kde(values)
                    y_curve = kde(x_curve)
                    
            elif curve_type == 'Normal Fit':
                mu, sigma = stats.norm.fit(values)
                y_curve = stats.norm.pdf(x_curve, mu, sigma)
                
            elif curve_type == 'Gamma Fit':
                if all(v > 0 for v in values):
                    a, loc, scale = stats.gamma.fit(values, floc=0)
                    y_curve = stats.gamma.pdf(x_curve, a, loc, scale)
                else:
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
        Add median vertical line with label.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            values (list): Data values to calculate median from
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        median_value = np.median(values)
        
        median_line = pg.InfiniteLine(pos=median_value, angle=90, 
                                     pen=pg.mkPen(color='black', style=pg.QtCore.Qt.DashLine, width=2))
        plot_item.addItem(median_line)
        
        median_text = pg.TextItem(f'median: {median_value:.2f}', 
                                 anchor=(0, 1), color='black')
        plot_item.addItem(median_text)
        
        view_box = plot_item.getViewBox()
        try:
            x_range = view_box.state['viewRange'][0]
            y_range = view_box.state['viewRange'][1]
            
            text_y = y_range[0] + 0.9 * (y_range[1] - y_range[0])
            median_text.setPos(median_value, text_y)
        except:
            median_text.setPos(median_value, 1)
    
    def add_statistics_text(self, plot_item, plot_data, config):
        """
        Add statistics text box to the plot.
        
        Displays particle counts, mean, and median values for each element
        in a formatted text box.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            plot_data (dict): Plot data dictionary
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        if not plot_data:
            return
        
        sorted_plot_data = self.sort_plot_data_by_mass(plot_data)
        
        data_type = config.get('data_type_display', 'Counts (Raw)')
        
        stats_text = f"Statistics ({data_type}):\n"
        total_particles = 0
        
        for element_label, values in sorted_plot_data.items():
            if values and len(values) > 0:
                if data_type != 'Counts (Raw)':
                    valid_values = [v for v in values if v > 0 and not np.isnan(v)]
                else:
                    valid_values = values
                
                if valid_values:
                    particle_count = len(valid_values)
                    mean_value = np.mean(valid_values)
                    median_value = np.median(valid_values)
                    total_particles += particle_count
                    
                    if 'Mass' in data_type:
                        stats_text += f"{element_label}: {particle_count} particles\n"
                        stats_text += f"  Mean: {mean_value:.2f} fg, Median: {median_value:.2f} fg\n"
                    elif 'Moles' in data_type:
                        stats_text += f"{element_label}: {particle_count} particles\n"
                        stats_text += f"  Mean: {mean_value:.4f} fmol, Median: {median_value:.4f} fmol\n"
                    elif 'Diameter' in data_type:
                        stats_text += f"{element_label}: {particle_count} particles\n"
                        stats_text += f"  Mean: {mean_value:.1f} nm, Median: {median_value:.1f} nm\n"
                    else:
                        stats_text += f"{element_label}: {particle_count} particles\n"
                        stats_text += f"  Mean: {mean_value:.1f}, Median: {median_value:.1f}\n"
        
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


class HistogramPlotNode(QObject):
    
    position_changed = Signal(object)
    configuration_changed = Signal()
    
    def __init__(self, parent_window=None):
        """
        Initialize histogram plot node.
        
        Args:
            parent_window: Parent window widget (optional)
        
        Returns:
            None
        """
        super().__init__()
        self.title = "Histogram"
        self.node_type = "histogram_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.config = {
            'data_type_display': 'Counts (Raw)',
            'show_curve': True,
            'curve_type': 'Kernel Density',
            'show_median': True,
            'curve_color': '#2C3E50',
            'bins': 20,
            'alpha': 0.7,
            'log_x': False,
            'log_y': False,
            'show_stats': True,
            'x_min': 0,
            'x_max': 1000,
            'auto_x': True,
            'y_min': 0,
            'y_max': 100,
            'auto_y': True,
            'element_colors': {},
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
        dialog = HistogramDisplayDialog(self, parent_window)
        dialog.exec()
        return True
        
    def process_data(self, input_data):
        """
        Process input data and update histogram.
        
        Receives data from connected nodes and triggers visual updates.
        
        Args:
            input_data (dict): Input data dictionary from upstream nodes
        
        Returns:
            None
        """
        if not input_data:
            print("No input data received for histogram")
            return
            
        print(f"Histogram received data: {input_data.get('type', 'unknown')}")
        self.input_data = input_data
        
        self.configuration_changed.emit()
        
    def extract_plot_data(self):
        """
        Extract plottable data from input.
        
        Creates element-to-values dictionaries for the selected data type,
        supporting both single and multiple sample modes.
        
        Args:
            None
        
        Returns:
            dict or None: Dictionary with element data, or None if no data
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
    
    def sort_plot_data_by_mass(self, plot_data):
        """
        Sort plot data dictionary by mass number of element keys.
        
        Args:
            plot_data (dict): Dictionary with element names as keys
        
        Returns:
            dict: Dictionary sorted by element mass numbers
        """
        return sort_element_dict_by_mass(plot_data)
    
    def _extract_single_sample_data(self, data_key):
        """
        Extract data for single sample.
        
        Collects values for each element from filtered particle data.
        
        Args:
            data_key (str): Key for data type in particle dictionary
        
        Returns:
            dict or None: Dictionary mapping element names to value lists,
                         or None if extraction fails
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
        
        return element_data

    def _extract_multiple_sample_data(self, data_key):
        """
        Extract data for multiple samples.
        
        Collects values for each element from filtered particle data,
        organized by sample.
        
        Args:
            data_key (str): Key for data type in particle dictionary
        
        Returns:
            dict or None: Dictionary mapping sample names to element data dictionaries,
                         or None if extraction fails
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
        
        sample_data = {k: v for k, v in sample_data.items() if v}
        return sample_data
    
class ElementBarChartDisplayDialog(QDialog):

    def __init__(self, bar_chart_node, parent_window=None):
        """
        Initialize the element bar chart display dialog.
        
        Args:
            bar_chart_node: Bar chart node instance containing configuration and data
            parent_window: Parent window widget (optional)
        
        Returns:
            None
        """
        super().__init__(parent_window)
        self.bar_chart_node = bar_chart_node
        self.parent_window = parent_window
        
        self.setWindowTitle("Element Particle Count Bar Chart Analysis")
        self.setMinimumSize(1400, 800)
        
        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        self.setup_ui()
        self.update_display()
        
        self.bar_chart_node.configuration_changed.connect(self.update_display)
        
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
        return (hasattr(self.bar_chart_node, 'input_data') and 
                self.bar_chart_node.input_data and 
                self.bar_chart_node.input_data.get('type') == 'multiple_sample_data')
        
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
        Create the bar chart configuration panel with all settings.
        
        Creates a scrollable panel containing configuration options for:
        - Display mode (for multiple samples)
        - Plot options (value labels, sorting, log scales)
        - Font settings
        - Element and sample colors
        
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
        
        title = QLabel("Bar Chart Settings")
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
                'Grouped Bars (Side by Side)', 
                'Stacked Bars', 
                'Individual Subplots',
                'Side by Side Subplots'
            ])
            self.display_mode_combo.setCurrentText(self.bar_chart_node.config.get('display_mode', 'Grouped Bars (Side by Side)'))
            self.display_mode_combo.currentTextChanged.connect(self.on_config_changed)
            multiple_layout.addRow("Display Mode:", self.display_mode_combo)
            
            self.normalize_samples_checkbox = QCheckBox()
            self.normalize_samples_checkbox.setChecked(self.bar_chart_node.config.get('normalize_samples', False))
            self.normalize_samples_checkbox.stateChanged.connect(self.on_config_changed)
            multiple_layout.addRow("Normalize by Sample Size:", self.normalize_samples_checkbox)
            
            layout.addWidget(multiple_group)
        
        plot_group = QGroupBox("Plot Options")
        plot_layout = QFormLayout(plot_group)
        
        self.show_values_checkbox = QCheckBox()
        self.show_values_checkbox.setChecked(self.bar_chart_node.config.get('show_values', True))
        self.show_values_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Show Values on Bars:", self.show_values_checkbox)
        
        self.sort_bars_combo = QComboBox()
        self.sort_bars_combo.addItems(['No Sorting', 'Ascending', 'Descending', 'Alphabetical'])
        self.sort_bars_combo.setCurrentText(self.bar_chart_node.config.get('sort_bars', 'No Sorting'))
        self.sort_bars_combo.currentTextChanged.connect(self.on_config_changed)
        plot_layout.addRow("Sort Bars:", self.sort_bars_combo)
        
        self.log_x_checkbox = QCheckBox()
        self.log_x_checkbox.setChecked(self.bar_chart_node.config.get('log_x', False))
        self.log_x_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Log X-axis:", self.log_x_checkbox)
        
        self.log_y_checkbox = QCheckBox()
        self.log_y_checkbox.setChecked(self.bar_chart_node.config.get('log_y', False))
        self.log_y_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Log Y-axis:", self.log_y_checkbox)
        
        layout.addWidget(plot_group)
        
        font_group = QGroupBox("Font Settings")
        font_layout = QFormLayout(font_group)
        
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(self.get_font_families())
        self.font_family_combo.setCurrentText(self.bar_chart_node.config.get('font_family', 'Times New Roman'))
        self.font_family_combo.currentTextChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Family:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(self.bar_chart_node.config.get('font_size', 18))
        self.font_size_spin.valueChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Size:", self.font_size_spin)
        
        font_style_layout = QHBoxLayout()
        self.font_bold_checkbox = QCheckBox("Bold")
        self.font_bold_checkbox.setChecked(self.bar_chart_node.config.get('font_bold', False))
        self.font_bold_checkbox.stateChanged.connect(self.on_config_changed)
        self.font_italic_checkbox = QCheckBox("Italic")
        self.font_italic_checkbox.setChecked(self.bar_chart_node.config.get('font_italic', False))
        self.font_italic_checkbox.stateChanged.connect(self.on_config_changed)
        font_style_layout.addWidget(self.font_bold_checkbox)
        font_style_layout.addWidget(self.font_italic_checkbox)
        font_style_layout.addStretch()
        font_layout.addRow("Font Style:", font_style_layout)
        
        self.font_color_button = QPushButton()
        self.font_color = QColor(self.bar_chart_node.config.get('font_color', '#000000'))
        self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 30px;")
        self.font_color_button.clicked.connect(lambda: self.choose_color('font'))
        font_layout.addRow("Font Color:", self.font_color_button)
        
        layout.addWidget(font_group)
        
        self.colors_group = QGroupBox("Element Colors")
        self.colors_layout = QVBoxLayout(self.colors_group)
        self.update_color_controls()
        layout.addWidget(self.colors_group)
        
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
            font_family = self.bar_chart_node.config.get('font_family', 'Times New Roman')
            font_size = self.bar_chart_node.config.get('font_size', 18)
            is_bold = self.bar_chart_node.config.get('font_bold', False)
            is_italic = self.bar_chart_node.config.get('font_italic', False)
            font_color = self.bar_chart_node.config.get('font_color', '#000000')
            
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
    
    def update_sample_color_controls(self):
        """
        Update color controls for multiple samples with editable names.
        
        Creates color picker buttons and name edit fields for each sample
        with reset functionality.
        
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
        
        sample_colors = self.bar_chart_node.config.get('sample_colors', {})
        
        sample_name_mappings = self.bar_chart_node.config.get('sample_name_mappings', {})
        
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
        
        self.bar_chart_node.config['sample_colors'] = sample_colors
        self.bar_chart_node.config['sample_name_mappings'] = sample_name_mappings

    def on_sample_name_changed(self, original_name, new_name):
        """
        Handle sample name change event.
        
        Args:
            original_name (str): Original sample name
            new_name (str): New custom display name
        
        Returns:
            None
        """
        if 'sample_name_mappings' not in self.bar_chart_node.config:
            self.bar_chart_node.config['sample_name_mappings'] = {}
        
        self.bar_chart_node.config['sample_name_mappings'][original_name] = new_name
        
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
        
        if 'sample_name_mappings' in self.bar_chart_node.config:
            self.bar_chart_node.config['sample_name_mappings'].pop(original_name, None)
        
        self.on_config_changed()

    def get_display_name(self, original_name):
        """
        Get display name for a sample (either custom or original).
        
        Args:
            original_name (str): Original sample name
        
        Returns:
            str: Display name (custom if set, otherwise original)
        """
        mappings = self.bar_chart_node.config.get('sample_name_mappings', {})
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
            return self.bar_chart_node.input_data.get('sample_names', [])
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
        current_color = self.bar_chart_node.config.get('sample_colors', {}).get(sample_name, '#3B82F6')
        display_name = self.get_display_name(sample_name)
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {display_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'sample_colors' not in self.bar_chart_node.config:
                self.bar_chart_node.config['sample_colors'] = {}
            self.bar_chart_node.config['sample_colors'][sample_name] = color_hex
            
            self.on_config_changed()
    
    def update_color_controls(self):
        """
        Update color controls based on available elements.
        
        Creates color picker buttons for each element with default color assignments.
        
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
        
        default_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                         '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        
        element_colors = self.bar_chart_node.config.get('element_colors', {})
        
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
        
        self.bar_chart_node.config['element_colors'] = element_colors
    
    def get_available_elements(self):
        """
        Get available elements from the bar chart node's data, sorted by mass number.
        
        Attempts to extract elements from plot data first, then falls back to
        input data. Elements are sorted by their mass number for consistent ordering.
        
        Args:
            None
        
        Returns:
            list: List of element label strings sorted by mass number
        """
        if hasattr(self.bar_chart_node, 'extract_plot_data'):
            plot_data = self.bar_chart_node.extract_plot_data()
            if plot_data:
                if self.is_multiple_sample_data():
                    all_elements = set()
                    for sample_data in plot_data.values():
                        if isinstance(sample_data, dict):
                            all_elements.update(sample_data.keys())
                    return sort_elements_by_mass(list(all_elements))
                else:
                    return sort_elements_by_mass(list(plot_data.keys()))
        
        if not self.bar_chart_node.input_data:
            return []
        
        data_type = self.bar_chart_node.input_data.get('type')
        
        if data_type in ['sample_data', 'multiple_sample_data']:
            selected_isotopes = self.bar_chart_node.input_data.get('selected_isotopes', [])
            if selected_isotopes:
                element_labels = [isotope['label'] for isotope in selected_isotopes]
                return sort_elements_by_mass(element_labels)
        
        return []
    
    def download_figure(self):
        """
        Download the current figure using PyQtGraph exporters.
        
        Exports the bar chart plot to PNG or SVG format based on user selection.
        
        Args:
            None
        
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Element Bar Chart",
            "element_bar_chart.png",
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
                                    f"Bar chart saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", 
                                f"Failed to save:\n{str(e)}")
        
    def select_element_color(self, element_name, button):
        """
        Open color dialog for element color selection.
        
        Args:
            element_name (str): Name of the element to set color for
            button (QPushButton): Button widget to update with new color
        
        Returns:
            None
        """
        current_color = self.bar_chart_node.config.get('element_colors', {}).get(element_name, '#1f77b4')
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {element_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'element_colors' not in self.bar_chart_node.config:
                self.bar_chart_node.config['element_colors'] = {}
            self.bar_chart_node.config['element_colors'][element_name] = color_hex
            
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
        
        Collects all configuration values from UI controls and triggers
        bar chart update.
        
        Args:
            None
        
        Returns:
            None
        """
        config_updates = {
            'show_values': self.show_values_checkbox.isChecked(),
            'sort_bars': self.sort_bars_combo.currentText(),
            'log_x': self.log_x_checkbox.isChecked(),
            'log_y': self.log_y_checkbox.isChecked(),
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
        
        self.bar_chart_node.config.update(config_updates)
        
        self.update_display()

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
  
    def update_display(self):
        """
        Update the bar chart display with support for multiple samples.
        
        Clears existing plot and recreates based on current configuration
        and data. Handles both single and multiple sample modes.
        
        Args:
            None
        
        Returns:
            None
        """
        try:
            self.plot_widget.clear()
            
            plot_data = self.bar_chart_node.extract_plot_data()
            
            if not plot_data:
                plot_item = self.plot_widget.addPlot()
                text_item = pg.TextItem("No particle data available\nConnect to Sample Selector\nand run particle detection", 
                                      anchor=(0.5, 0.5), color='gray')
                plot_item.addItem(text_item)
                text_item.setPos(0.5, 0.5)
                plot_item.hideAxis('left')
                plot_item.hideAxis('bottom')
            else:
                config = self.bar_chart_node.config
                
                if self.is_multiple_sample_data():
                    self.create_multiple_sample_bar_chart(plot_data, config)
                else:
                    plot_item = self.plot_widget.addPlot()
                    self.create_bar_chart_plot(plot_item, plot_data, config)
                    self.apply_plot_settings(plot_item)
            
        except Exception as e:
            print(f"Error updating bar chart display: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def create_multiple_sample_bar_chart(self, plot_data, config):
        """
        Create bar chart for multiple samples with different display modes.
        
        Args:
            plot_data (dict): Dictionary of sample data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        display_mode = config.get('display_mode', 'Grouped Bars (Side by Side)')
        sample_names = list(plot_data.keys())
        
        if display_mode == 'Individual Subplots':
            self.create_subplot_bar_charts(plot_data, config)
        elif display_mode == 'Side by Side Subplots':
            self.create_side_by_side_bar_charts(plot_data, config)
        else:
            plot_item = self.plot_widget.addPlot()
            self.create_combined_bar_chart(plot_item, plot_data, config)
            self.apply_plot_settings(plot_item)
    
    def create_subplot_bar_charts(self, plot_data, config):
        """
        Create individual subplots for each sample.
        
        Arranges bar charts in a grid layout with each sample in its own subplot.
        
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
                
                self.create_sample_specific_bar_chart(plot_item, sample_data, config, sample_color)
                
                title_text = f"{self.get_display_name(sample_name)}"
                plot_item.setTitle(title_text)
                
                log_x = config.get('log_x', False)
                log_y = config.get('log_y', False)
                
                x_label = "log₁₀(Isotope Elements)" if log_x else "Isotope Elements"
                y_label = "log₁₀(Number of Particles)" if log_y else "Number of Particles"
                
                self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
                
                self.apply_plot_settings(plot_item)

    def create_side_by_side_bar_charts(self, plot_data, config):
        """
        Create side-by-side bar charts.
        
        Arranges bar charts in a single row for easy comparison across samples.
        
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
                
                self.create_sample_specific_bar_chart(plot_item, sample_data, config, sample_color)
                
                title_text = f"{self.get_display_name(sample_name)}"
                plot_item.setTitle(title_text)
                
                log_x = config.get('log_x', False)
                log_y = config.get('log_y', False)
                
                x_label = "log₁₀(Isotope Elements)" if log_x else "Isotope Elements"
                y_label = "log₁₀(Number of Particles)" if log_y else "Number of Particles"
                
                if i == 0:
                    self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
                else:
                    self.set_axis_labels_with_font(plot_item, x_label, "", config)
                
                self.apply_plot_settings(plot_item)
                
    def sort_elements_for_display(self, elements, counts, sort_option):
        """
        Sort elements based on user preference, with mass number as default order.
        
        Args:
            elements (list): List of element names
            counts (list): List of particle counts for each element
            sort_option (str): Sorting option ('No Sorting', 'Ascending', 'Descending', 'Alphabetical')
        
        Returns:
            tuple: (sorted_elements, sorted_counts) as lists
        """
        mass_sorted_elements = sort_elements_by_mass(elements)
        
        if sort_option == 'No Sorting':
            element_count_dict = dict(zip(elements, counts))
            sorted_counts = [element_count_dict[elem] for elem in mass_sorted_elements]
            return mass_sorted_elements, sorted_counts
        
        elif sort_option == 'Ascending':
            sorted_data = sorted(zip(elements, counts), key=lambda x: x[1])
            return zip(*sorted_data)
        
        elif sort_option == 'Descending':
            sorted_data = sorted(zip(elements, counts), key=lambda x: x[1], reverse=True)
            return zip(*sorted_data)
        
        elif sort_option == 'Alphabetical':
            sorted_data = sorted(zip(elements, counts), key=lambda x: x[0])
            return zip(*sorted_data)
        
        else:
            element_count_dict = dict(zip(elements, counts))
            sorted_counts = [element_count_dict[elem] for elem in mass_sorted_elements]
            return mass_sorted_elements, sorted_counts
        
    def create_combined_bar_chart(self, plot_item, plot_data, config):
        """
        Create combined bar chart (grouped or stacked).
        
        Displays data from all samples on a single plot either as grouped
        bars side-by-side or stacked bars depending on display mode.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            plot_data (dict): Dictionary of sample data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        display_mode = config.get('display_mode', 'Grouped Bars (Side by Side)')
        sample_colors = config.get('sample_colors', {})
        default_colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
        log_x = config.get('log_x', False)
        log_y = config.get('log_y', False)
        
        all_elements = set()
        for sample_data in plot_data.values():
            all_elements.update(sample_data.keys())
        all_elements = sort_elements_by_mass(list(all_elements))
        
        sort_option = config.get('sort_bars', 'No Sorting')
        if sort_option != 'No Sorting':
            element_totals = []
            for element in all_elements:
                total = sum(plot_data[sample].get(element, 0) for sample in plot_data.keys())
                element_totals.append((element, total))
            
            if sort_option == 'Ascending':
                element_totals.sort(key=lambda x: x[1])
            elif sort_option == 'Descending':
                element_totals.sort(key=lambda x: x[1], reverse=True)
            elif sort_option == 'Alphabetical':
                element_totals.sort(key=lambda x: x[0])
            
            all_elements = [element for element, _ in element_totals]
        
        x_positions = np.arange(len(all_elements))
        
        legend_items = []
        
        if display_mode == 'Stacked Bars':
            bottom_values = np.zeros(len(all_elements))
            
            for i, sample_name in enumerate(plot_data.keys()):
                sample_color = sample_colors.get(sample_name, default_colors[i % len(default_colors)])
                heights = [plot_data[sample_name].get(element, 0) for element in all_elements]
                
                if log_y:
                    heights = [np.log10(h + 1) for h in heights]
                    bottom_values_display = [np.log10(b + 1) for b in bottom_values]
                else:
                    bottom_values_display = bottom_values
                
                color_obj = QColor(sample_color)
                color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), 200)
                
                bar_item = pg.BarGraphItem(x=x_positions, height=heights, width=0.8, 
                                        brush=pg.mkBrush(*color_rgba),
                                        pen=pg.mkPen(color='black', width=1))
                plot_item.addItem(bar_item)
                
                legend_items.append((bar_item, self.get_display_name(sample_name)))
                
                bottom_values += np.array([plot_data[sample_name].get(element, 0) for element in all_elements])
        
        else:
            n_samples = len(plot_data)
            bar_width = 0.8 / n_samples
            
            for i, sample_name in enumerate(plot_data.keys()):
                sample_color = sample_colors.get(sample_name, default_colors[i % len(default_colors)])
                heights = [plot_data[sample_name].get(element, 0) for element in all_elements]
                
                if log_y:
                    heights = [np.log10(h + 1) for h in heights]
                
                x_offset = x_positions + (i - n_samples/2 + 0.5) * bar_width
                
                color_obj = QColor(sample_color)
                color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), 200)
                
                bar_item = pg.BarGraphItem(x=x_offset, height=heights, width=bar_width, 
                                        brush=pg.mkBrush(*color_rgba),
                                        pen=pg.mkPen(color='black', width=1))
                plot_item.addItem(bar_item)
                
                legend_items.append((bar_item, self.get_display_name(sample_name)))
                
                if config.get('show_values', True):
                    for j, (x_pos, height) in enumerate(zip(x_offset, heights)):
                        if height > 0:
                            original_value = plot_data[sample_name].get(all_elements[j], 0)
                            value_text = pg.TextItem(str(int(original_value)), 
                                                anchor=(0.5, 1), color='black')
                            plot_item.addItem(value_text)
                            value_text.setPos(x_pos, height + max(heights) * 0.02)
        
        x_axis = plot_item.getAxis('bottom')
        x_axis.setTicks([[(i, elem) for i, elem in enumerate(all_elements)]])
        
        x_label = "log₁₀(Isotope Elements)" if log_x else "Isotope Elements"
        y_label = "log₁₀(Number of Particles)" if log_y else "Number of Particles"
        
        self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
        
        if legend_items:
            legend = plot_item.addLegend()
            for item, name in legend_items:
                legend.addItem(item, name)

    
    def create_sample_specific_bar_chart(self, plot_item, sample_data, config, sample_color):
        """
        Create bar chart for a specific sample.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            sample_data (dict): Sample element data dictionary
            config (dict): Configuration dictionary
            sample_color (str): Hex color string for sample
        
        Returns:
            None
        """
        log_x = config.get('log_x', False)
        log_y = config.get('log_y', False)
        
        elements = sort_elements_by_mass(list(sample_data.keys()))
        counts = [sample_data[elem] for elem in elements]
        
        sort_option = config.get('sort_bars', 'No Sorting')
        elements, counts = self.sort_elements_for_display(elements, counts, sort_option)
        
        elements = list(elements)
        counts = list(counts)
        
        if log_y:
            counts = [np.log10(c + 1) for c in counts]
        
        x_positions = np.arange(len(elements))
        
        color_obj = QColor(sample_color)
        color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), 200)
        
        bar_item = pg.BarGraphItem(x=x_positions, height=counts, width=0.8, 
                                brush=pg.mkBrush(*color_rgba),
                                pen=pg.mkPen(color='black', width=1))
        plot_item.addItem(bar_item)
        
        if config.get('show_values', True):
            original_counts = [sample_data[elem] for elem in elements]
            
            for i, (x_pos, height) in enumerate(zip(x_positions, counts)):
                if height > 0:
                    value_text = pg.TextItem(str(int(original_counts[i])), 
                                        anchor=(0.5, 1), color='black')
                    plot_item.addItem(value_text)
                    value_text.setPos(x_pos, height + max(counts) * 0.02)
        
        x_axis = plot_item.getAxis('bottom')
        x_axis.setTicks([[(i, elem) for i, elem in enumerate(elements)]])
        
        
    def create_bar_chart_plot(self, plot_item, plot_data, config):
        """
        Create the bar chart plot (single sample).
        
        Creates bars for each element with individual colors and optional value labels.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            plot_data (dict): Plot data dictionary with element counts
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        element_colors = config.get('element_colors', {})
        default_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        log_x = config.get('log_x', False)
        log_y = config.get('log_y', False)
        
        elements = sort_elements_by_mass(list(plot_data.keys()))
        counts = [plot_data[elem] for elem in elements]
        
        sort_option = config.get('sort_bars', 'No Sorting')
        elements, counts = self.sort_elements_for_display(elements, counts, sort_option)
        
        elements = list(elements)
        counts = list(counts)
        
        if log_y:
            counts = [np.log10(c + 1) for c in counts]
        
        colors = []
        for i, element in enumerate(elements):
            if element in element_colors:
                colors.append(element_colors[element])
            else:
                colors.append(default_colors[i % len(default_colors)])
        
        x_positions = np.arange(len(elements))
        
        legend_items = []
        
        for i, (x_pos, element, count, color) in enumerate(zip(x_positions, elements, counts, colors)):
            color_obj = QColor(color)
            color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), 200)
            
            bar_item = pg.BarGraphItem(x=[x_pos], height=[count], width=0.8, 
                                    brush=pg.mkBrush(*color_rgba),
                                    pen=pg.mkPen(color='black', width=1))
            plot_item.addItem(bar_item)
            
            if len(elements) > 1:
                legend_items.append((bar_item, element))
        
        if config.get('show_values', True):
            original_counts = [plot_data[elem] for elem in elements]
            
            for i, (x_pos, height) in enumerate(zip(x_positions, counts)):
                if height > 0:
                    value_text = pg.TextItem(str(int(original_counts[i])), 
                                        anchor=(0.5, 1), color='black')
                    plot_item.addItem(value_text)
                    value_text.setPos(x_pos, height + max(counts) * 0.02)
        
        x_axis = plot_item.getAxis('bottom')
        x_axis.setTicks([[(i, elem) for i, elem in enumerate(elements)]])
        
        x_label = "log₁₀(Isotope Elements)" if log_x else "Isotope Elements"
        y_label = "log₁₀(Number of Particles)" if log_y else "Number of Particles"
        
        self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
        
        if len(legend_items) > 1:
            legend = plot_item.addLegend()
            for item, name in legend_items:
                legend.addItem(item, name)


class ElementBarChartPlotNode(QObject):

    position_changed = Signal(object)
    configuration_changed = Signal()
    
    def __init__(self, parent_window=None):
        """
        Initialize element bar chart plot node.
        
        Args:
            parent_window: Parent window widget (optional)
        
        Returns:
            None
        """
        super().__init__()
        self.title = "Element Bar Chart"
        self.node_type = "element_bar_chart_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.config = {
            'show_values': True,
            'sort_bars': 'No Sorting',
            'log_x': False,
            'log_y': False,
            'element_colors': {},
            'display_mode': 'Grouped Bars (Side by Side)',
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
        dialog = ElementBarChartDisplayDialog(self, parent_window)
        dialog.exec()
        return True
        
    def process_data(self, input_data):
        """
        Process input data and update bar chart.
        
        Receives data from connected nodes and triggers visual updates.
        
        Args:
            input_data (dict): Input data dictionary from upstream nodes
        
        Returns:
            None
        """
        if not input_data:
            print("No input data received for element bar chart")
            return
            
        print(f"Element bar chart received data: {input_data.get('type', 'unknown')}")
        self.input_data = input_data
        
        self.configuration_changed.emit()
 
    
    def extract_plot_data(self):
        """
        Extract plottable data from input - enhanced for multiple samples.
        
        Counts the number of particles containing each element for both
        single and multiple sample modes.
        
        Args:
            None
        
        Returns:
            dict or None: Dictionary with element particle counts, or None if no data
        """
        if not self.input_data:
            return None
            
        data_type = self.input_data.get('type')
        
        if data_type == 'sample_data':
            particles = self.input_data.get('particle_data')
            
            if not particles:
                return None
            
            element_particle_counts = {}
            for particle in particles:
                for element_name, count in particle.get('elements', {}).items():
                    if count > 0:
                        if element_name not in element_particle_counts:
                            element_particle_counts[element_name] = 0
                        element_particle_counts[element_name] += 1
            
            return element_particle_counts
            
        elif data_type == 'multiple_sample_data':
            particles = self.input_data.get('particle_data', [])
            sample_names = self.input_data.get('sample_names', [])
            
            if not particles:
                print("No particle data available for multiple samples")
                return None
            
            sample_data = {}
            
            for sample_name in sample_names:
                sample_data[sample_name] = {}
            
            for particle in particles:
                source_sample = particle.get('source_sample')
                if source_sample and source_sample in sample_data:
                    for element_name, count in particle.get('elements', {}).items():
                        if count > 0:
                            if element_name not in sample_data[source_sample]:
                                sample_data[source_sample][element_name] = 0
                            sample_data[source_sample][element_name] += 1
            
            sample_data = {k: v for k, v in sample_data.items() if v}
            
            return sample_data
                            
        return None