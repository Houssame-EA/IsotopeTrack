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
from scipy.stats import norm

class CustomColorBar:
    """
    Custom color bar for scatter plots since PyQtGraph's ColorBarItem is for ImageItems.
    
    This class creates a visual color bar with gradient segments and value labels
    to represent the mapping between data values and colors in scatter plots.
    """
    
    def __init__(self, plot_item, colormap, vmin, vmax, config, element_name=""):
        """
        Initialize the custom color bar.
        
        Args:
            plot_item: PyQtGraph PlotItem to add color bar to
            colormap: PyQtGraph ColorMap object for color mapping
            vmin (float): Minimum value for color scale
            vmax (float): Maximum value for color scale
            config (dict): Configuration dictionary with font settings
            element_name (str): Name of element being visualized (optional)
        
        Returns:
            None
        """
        self.plot_item = plot_item
        self.colormap = colormap
        self.vmin = vmin
        self.vmax = vmax
        self.config = config
        self.element_name = element_name
        self.color_bar_items = []
        
    def create_color_bar(self):
        """
        Create a custom color bar using plot items.
        
        Generates a series of colored rectangles with value labels to show
        the color-to-value mapping on the plot.
        
        Args:
            None
        
        Returns:
            list: List of plot items added to create the color bar
        """
        try:
            font_family = self.config.get('font_family', 'Times New Roman')
            font_size = self.config.get('font_size', 18)
            font_color = self.config.get('font_color', '#000000')
            data_type_display = self.config.get('data_type_display', 'Counts (Raw)')
            
            n_segments = 20
            values = np.linspace(0, 1, n_segments)
            
            view_box = self.plot_item.getViewBox()
            view_range = view_box.viewRange()
            x_range = view_range[0]
            y_range = view_range[1]
            
            bar_x_start = x_range[1] + 0.05 * (x_range[1] - x_range[0])
            bar_width = 0.03 * (x_range[1] - x_range[0])
            bar_height = 0.7 * (y_range[1] - y_range[0])
            bar_y_start = y_range[0] + 0.15 * (y_range[1] - y_range[0])
            
            segment_height = bar_height / n_segments
            
            for i, val in enumerate(values):
                color_rgba = self.colormap.map(val, mode='byte')
                color = QColor(color_rgba[0], color_rgba[1], color_rgba[2], 255)
                
                y_pos = bar_y_start + i * segment_height
                
                rect_x = [bar_x_start, bar_x_start + bar_width, bar_x_start + bar_width, bar_x_start, bar_x_start]
                rect_y = [y_pos, y_pos, y_pos + segment_height, y_pos + segment_height, y_pos]
                
                rect_item = pg.PlotDataItem(x=rect_x, y=rect_y, 
                                          fillLevel=y_pos, 
                                          fillBrush=pg.mkBrush(color),
                                          pen=pg.mkPen(color))
                self.plot_item.addItem(rect_item)
                self.color_bar_items.append(rect_item)
            
            n_labels = 5
            for i in range(n_labels):
                frac = i / (n_labels - 1)
                value = self.vmin + frac * (self.vmax - self.vmin)
                y_pos = bar_y_start + frac * bar_height
                
                label_text = f"{value:.2f}"
                text_item = pg.TextItem(label_text, color=font_color, anchor=(0, 0.5))
                text_item.setPos(bar_x_start + bar_width + 0.01 * (x_range[1] - x_range[0]), y_pos)
                self.plot_item.addItem(text_item)
                self.color_bar_items.append(text_item)
            
            if self.element_name:
                title_text = f"{self.element_name} ({data_type_display})"
                title_item = pg.TextItem(title_text, color=font_color, anchor=(0.5, 0))
                title_x = bar_x_start + bar_width / 2
                title_y = bar_y_start + bar_height + 0.05 * (y_range[1] - y_range[0])
                title_item.setPos(title_x, title_y)
                self.plot_item.addItem(title_item)
                self.color_bar_items.append(title_item)
            
            return self.color_bar_items
            
        except Exception as e:
            print(f"Error creating custom color bar: {e}")
            return []

    def remove_color_bar(self):
        """
        Remove the color bar items from the plot.
        
        Args:
            None
        
        Returns:
            None
        """
        for item in self.color_bar_items:
            try:
                self.plot_item.removeItem(item)
            except:
                pass
        self.color_bar_items.clear()

class CorrelationPlotDisplayDialog(QDialog):
    """
    Dialog for element correlation visualization with custom equations and multiple samples support.
    
    Provides interactive configuration for creating correlation plots between elements
    with support for simple element-to-element correlations or custom mathematical
    expressions. Includes multiple sample visualization modes and color mapping options.
    """
    
    def __init__(self, correlation_node, parent_window=None):
        """
        Initialize the correlation plot display dialog.
        
        Args:
            correlation_node: Correlation node instance containing configuration and data
            parent_window: Parent window widget (optional)
        
        Returns:
            None
        """
        super().__init__(parent_window)
        self.correlation_node = correlation_node
        self.parent_window = parent_window
        
        self.setWindowTitle("Element Correlation Analysis - Custom Equations")
        self.setMinimumSize(1400, 800)
        
        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        self.active_color_bars = []
        
        self.setup_ui()
        self.update_display()
        
        self.correlation_node.configuration_changed.connect(self.update_display)
        
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
        return (hasattr(self.correlation_node, 'input_data') and 
                self.correlation_node.input_data and 
                self.correlation_node.input_data.get('type') == 'multiple_sample_data')
        
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
        Create the correlation configuration panel with all settings.
        
        Creates a scrollable panel containing configuration options for:
        - Analysis mode (simple or custom equations)
        - Element selection or equation inputs
        - Data type selection
        - Plot options (filters, log scales, trend lines)
        - Font settings
        - Marker settings
        - Sample colors for multiple samples
        
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
        
        title = QLabel("Correlation Plot Settings")
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
            self.display_mode_combo.setCurrentText(self.correlation_node.config.get('display_mode', 'Overlaid (Different Colors)'))
            self.display_mode_combo.currentTextChanged.connect(self.on_config_changed)
            multiple_layout.addRow("Display Mode:", self.display_mode_combo)
            
            layout.addWidget(multiple_group)
        
        mode_group = QGroupBox("Analysis Mode")
        mode_layout = QVBoxLayout(mode_group)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(['Simple Element Correlation', 'Custom Mathematical Expressions'])
        self.mode_combo.setCurrentText(self.correlation_node.config.get('mode', 'Simple Element Correlation'))
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        
        layout.addWidget(mode_group)
        
        self.simple_panel = self.create_simple_mode_panel()
        layout.addWidget(self.simple_panel)
        
        self.custom_panel = self.create_custom_mode_panel()
        layout.addWidget(self.custom_panel)
        
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
        self.data_type_combo.setCurrentText(self.correlation_node.config.get('data_type_display', 'Counts (Raw)'))
        self.data_type_combo.currentTextChanged.connect(self.on_config_changed)
        data_layout.addWidget(self.data_type_combo)
        
        layout.addWidget(data_group)
        
        plot_group = QGroupBox("Plot Options")
        plot_layout = QFormLayout(plot_group)
        
        self.filter_zeros_checkbox = QCheckBox()
        self.filter_zeros_checkbox.setChecked(self.correlation_node.config.get('filter_zeros', True))
        self.filter_zeros_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Filter Zero Values:", self.filter_zeros_checkbox)
        
        self.filter_saturated_checkbox = QCheckBox()
        self.filter_saturated_checkbox.setChecked(self.correlation_node.config.get('filter_saturated', True))
        self.filter_saturated_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Filter Saturated Particles:", self.filter_saturated_checkbox)
        
        self.saturation_threshold_spin = QSpinBox()
        self.saturation_threshold_spin.setRange(1, 1000000)
        self.saturation_threshold_spin.setValue(self.correlation_node.config.get('saturation_threshold', 10000))
        self.saturation_threshold_spin.setSuffix(" ")
        self.saturation_threshold_spin.valueChanged.connect(self.on_config_changed)
        plot_layout.addRow("Saturation Threshold:", self.saturation_threshold_spin)
        
        self.show_correlation_checkbox = QCheckBox()
        self.show_correlation_checkbox.setChecked(self.correlation_node.config.get('show_correlation', True))
        self.show_correlation_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Show Correlation Coefficient:", self.show_correlation_checkbox)
        
        self.show_trendline_checkbox = QCheckBox()
        self.show_trendline_checkbox.setChecked(self.correlation_node.config.get('show_trendline', True))
        self.show_trendline_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Show Trend Line:", self.show_trendline_checkbox)
        
        self.log_x_checkbox = QCheckBox()
        self.log_x_checkbox.setChecked(self.correlation_node.config.get('log_x', False))
        self.log_x_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Log X-axis:", self.log_x_checkbox)
        
        self.log_y_checkbox = QCheckBox()
        self.log_y_checkbox.setChecked(self.correlation_node.config.get('log_y', False))
        self.log_y_checkbox.stateChanged.connect(self.on_config_changed)
        plot_layout.addRow("Log Y-axis:", self.log_y_checkbox)
        
        layout.addWidget(plot_group)
        
        font_group = QGroupBox("Font Settings")
        font_layout = QFormLayout(font_group)
        
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(self.get_font_families())
        self.font_family_combo.setCurrentText(self.correlation_node.config.get('font_family', 'Times New Roman'))
        self.font_family_combo.currentTextChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Family:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(self.correlation_node.config.get('font_size', 18))
        self.font_size_spin.valueChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Size:", self.font_size_spin)
        
        font_style_layout = QHBoxLayout()
        self.font_bold_checkbox = QCheckBox("Bold")
        self.font_bold_checkbox.setChecked(self.correlation_node.config.get('font_bold', False))
        self.font_bold_checkbox.stateChanged.connect(self.on_config_changed)
        self.font_italic_checkbox = QCheckBox("Italic")
        self.font_italic_checkbox.setChecked(self.correlation_node.config.get('font_italic', False))
        self.font_italic_checkbox.stateChanged.connect(self.on_config_changed)
        font_style_layout.addWidget(self.font_bold_checkbox)
        font_style_layout.addWidget(self.font_italic_checkbox)
        font_style_layout.addStretch()
        font_layout.addRow("Font Style:", font_style_layout)
        
        self.font_color_button = QPushButton()
        self.font_color = QColor(self.correlation_node.config.get('font_color', '#000000'))
        self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 30px;")
        self.font_color_button.clicked.connect(lambda: self.choose_color('font'))
        font_layout.addRow("Font Color:", self.font_color_button)
        
        layout.addWidget(font_group)
        
        marker_group = QGroupBox("Marker Settings")
        marker_layout = QFormLayout(marker_group)
        
        self.marker_size_spin = QSpinBox()
        self.marker_size_spin.setRange(1, 20)
        self.marker_size_spin.setValue(self.correlation_node.config.get('marker_size', 6))
        self.marker_size_spin.valueChanged.connect(self.on_config_changed)
        marker_layout.addRow("Marker Size:", self.marker_size_spin)
        
        self.marker_alpha_spin = QDoubleSpinBox()
        self.marker_alpha_spin.setRange(0.1, 1.0)
        self.marker_alpha_spin.setSingleStep(0.1)
        self.marker_alpha_spin.setDecimals(1)
        self.marker_alpha_spin.setValue(self.correlation_node.config.get('marker_alpha', 0.7))
        self.marker_alpha_spin.valueChanged.connect(self.on_config_changed)
        marker_layout.addRow("Marker Transparency:", self.marker_alpha_spin)
        
        if not self.is_multiple_sample_data():
            color_layout = QHBoxLayout()
            self.single_sample_color_button = QPushButton()
            self.single_sample_color_button.setFixedSize(60, 25)
            current_color = self.correlation_node.config.get('single_sample_color', '#3B82F6')
            self.single_sample_color_button.setStyleSheet(f"background-color: {current_color}; border: 1px solid black;")
            self.single_sample_color_button.clicked.connect(self.select_single_sample_color)
            color_layout.addWidget(self.single_sample_color_button)
            color_layout.addStretch()
            marker_layout.addRow("Marker Color:", color_layout)
        
        layout.addWidget(marker_group)
        
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
        
        self.on_mode_changed()
        
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
            font_family = self.correlation_node.config.get('font_family', 'Times New Roman')
            font_size = self.correlation_node.config.get('font_size', 18)
            is_bold = self.correlation_node.config.get('font_bold', False)
            is_italic = self.correlation_node.config.get('font_italic', False)
            font_color = self.correlation_node.config.get('font_color', '#000000')
            
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
    
    def select_single_sample_color(self):
        """
        Open color dialog for single sample marker color selection.
        
        Args:
            None
        
        Returns:
            None
        """
        current_color = self.correlation_node.config.get('single_sample_color', '#3B82F6')
        color = QColorDialog.getColor(QColor(current_color), self, "Select Marker Color")
        
        if color.isValid():
            color_hex = color.name()
            self.single_sample_color_button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            self.correlation_node.config['single_sample_color'] = color_hex
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
        if not config.get('filter_saturated', True):
            return element_data
        
        threshold = config.get('saturation_threshold', 10000)
        
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
        
        sample_colors = self.correlation_node.config.get('sample_colors', {})
        
        sample_name_mappings = self.correlation_node.config.get('sample_name_mappings', {})
        
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
        
        self.correlation_node.config['sample_colors'] = sample_colors
        self.correlation_node.config['sample_name_mappings'] = sample_name_mappings

    def on_sample_name_changed(self, original_name, new_name):
        """
        Handle sample name change event.
        
        Args:
            original_name (str): Original sample name
            new_name (str): New custom display name
        
        Returns:
            None
        """
        if 'sample_name_mappings' not in self.correlation_node.config:
            self.correlation_node.config['sample_name_mappings'] = {}
        
        self.correlation_node.config['sample_name_mappings'][original_name] = new_name
        
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
        
        if 'sample_name_mappings' in self.correlation_node.config:
            self.correlation_node.config['sample_name_mappings'].pop(original_name, None)
        
        self.on_config_changed()

    def get_display_name(self, original_name):
        """
        Get display name for a sample (either custom or original).
        
        Args:
            original_name (str): Original sample name
        
        Returns:
            str: Display name (custom if set, otherwise original)
        """
        mappings = self.correlation_node.config.get('sample_name_mappings', {})
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
            return self.correlation_node.input_data.get('sample_names', [])
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
        current_color = self.correlation_node.config.get('sample_colors', {}).get(sample_name, '#3B82F6')
        display_name = self.get_display_name(sample_name)
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {display_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'sample_colors' not in self.correlation_node.config:
                self.correlation_node.config['sample_colors'] = {}
            self.correlation_node.config['sample_colors'][sample_name] = color_hex
            
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
            "Save Correlation Plot",
            "correlation_plot.png",
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
                                    f"Correlation plot saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", 
                                f"Failed to save:\n{str(e)}")
        
    def create_simple_mode_panel(self):
        """
        Create simple element selection panel for direct correlations.
        
        Provides dropdowns for selecting X-axis element, Y-axis element,
        and optional color mapping element.
        
        Args:
            None
        
        Returns:
            QGroupBox: Simple mode configuration panel
        """
        panel = QGroupBox("Simple Element Selection")
        layout = QFormLayout(panel)
        
        available_elements = self.get_available_elements()
        
        self.x_element_combo = QComboBox()
        self.x_element_combo.addItems(available_elements)
        self.x_element_combo.setCurrentText(self.correlation_node.config.get('x_element', available_elements[0] if available_elements else ''))
        self.x_element_combo.currentTextChanged.connect(self.on_config_changed)
        layout.addRow("X-axis Element:", self.x_element_combo)
        
        self.y_element_combo = QComboBox()
        self.y_element_combo.addItems(available_elements)
        current_y_element = self.correlation_node.config.get('y_element', available_elements[1] if len(available_elements) > 1 else '')
        if current_y_element in available_elements:
            self.y_element_combo.setCurrentText(current_y_element)
        self.y_element_combo.currentTextChanged.connect(self.on_config_changed)
        layout.addRow("Y-axis Element:", self.y_element_combo)
        
        self.color_element_combo = QComboBox()
        color_elements = ["None"] + available_elements
        self.color_element_combo.addItems(color_elements)
        self.color_element_combo.setCurrentText(self.correlation_node.config.get('color_element', 'None'))
        self.color_element_combo.currentTextChanged.connect(self.on_config_changed)
        layout.addRow("Color by Element:", self.color_element_combo)
        
        return panel
    
    def create_custom_mode_panel(self):
        """
        Create custom equation panel with mathematical expression inputs.
        
        Provides text fields for entering custom mathematical expressions
        for X and Y axes, with validation and quick template buttons.
        
        Args:
            None
        
        Returns:
            QGroupBox: Custom mode configuration panel
        """
        panel = QGroupBox("Custom Mathematical Expressions")
        layout = QVBoxLayout(panel)
        
        help_text = QLabel("""
        <b>Create custom equations using your elements:</b><br/>
        <b>Available Elements:</b> Use exact element names<br/>
        <b>Operations:</b> +, -, *, /, ** (power)<br/>
        <b>Functions:</b> log(), ln(), sqrt(), abs()<br/>
        <b>Examples:</b><br/>
        • Element1/Element2<br/>
        • (Element1 + Element2) * 2<br/>
        • log(Element1)<br/>
        • Element1**2 + Element2<br/>
        • sqrt(Element1/Element2)
        """)
        help_text.setStyleSheet("""
            QLabel {
                background-color: #FEF3C7;
                border: 1px solid #F59E0B;
                border-radius: 4px;
                padding: 8px;
                font-size: 10px;
            }
        """)
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        
        available_elements = self.get_available_elements()
        if available_elements:
            elements_text = QLabel(f"<b>Your Elements:</b> {', '.join(available_elements)}")
            elements_text.setStyleSheet("""
                QLabel {
                    background-color: #DBEAFE;
                    border: 1px solid #3B82F6;
                    border-radius: 4px;
                    padding: 6px;
                    font-size: 10px;
                }
            """)
            elements_text.setWordWrap(True)
            layout.addWidget(elements_text)
        
        x_layout = QFormLayout()
        self.x_equation_edit = QLineEdit()
        self.x_equation_edit.setText(self.correlation_node.config.get('x_equation', ''))
        self.x_equation_edit.setPlaceholderText("e.g., Element1/Element2")
        self.x_equation_edit.textChanged.connect(self.on_equation_changed)
        x_layout.addRow("X-axis Equation:", self.x_equation_edit)
        
        self.x_label_edit = QLineEdit()
        self.x_label_edit.setText(self.correlation_node.config.get('x_label', 'X-axis'))
        self.x_label_edit.setPlaceholderText("e.g., Element1/Element2 Ratio")
        self.x_label_edit.textChanged.connect(self.on_config_changed)
        x_layout.addRow("X-axis Label:", self.x_label_edit)
        
        layout.addLayout(x_layout)
        
        y_layout = QFormLayout()
        self.y_equation_edit = QLineEdit()
        self.y_equation_edit.setText(self.correlation_node.config.get('y_equation', ''))
        self.y_equation_edit.setPlaceholderText("e.g., Element3 + Element4")
        self.y_equation_edit.textChanged.connect(self.on_equation_changed)
        y_layout.addRow("Y-axis Equation:", self.y_equation_edit)
        
        self.y_label_edit = QLineEdit()
        self.y_label_edit.setText(self.correlation_node.config.get('y_label', 'Y-axis'))
        self.y_label_edit.setPlaceholderText("e.g., Combined Element Content")
        self.y_label_edit.textChanged.connect(self.on_config_changed)
        y_layout.addRow("Y-axis Label:", self.y_label_edit)
        
        layout.addLayout(y_layout)
        
        self.validation_label = QLabel()
        self.validation_label.setStyleSheet("""
            QLabel {
                padding: 5px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.validation_label)
        
        quick_layout = QHBoxLayout()
        quick_layout.addWidget(QLabel("Quick Templates:"))
        
        ratio_btn = QPushButton("A/B")
        ratio_btn.clicked.connect(lambda: self.insert_template("Element1/Element2"))
        quick_layout.addWidget(ratio_btn)
        
        sum_btn = QPushButton("A+B")
        sum_btn.clicked.connect(lambda: self.insert_template("Element1 + Element2"))
        quick_layout.addWidget(sum_btn)
        
        log_btn = QPushButton("Log(A)")
        log_btn.clicked.connect(lambda: self.insert_template("log(Element1)"))
        quick_layout.addWidget(log_btn)
        
        quick_layout.addStretch()
        layout.addLayout(quick_layout)
        
        self.validate_equations()
        
        return panel
    
    def insert_template(self, template):
        """
        Insert equation template into appropriate field.
        
        Args:
            template (str): Template equation string to insert
        
        Returns:
            None
        """
        if self.x_equation_edit.hasFocus() or not self.y_equation_edit.text():
            self.x_equation_edit.setText(template)
        else:
            self.y_equation_edit.setText(template)
    
    def on_mode_changed(self):
        """
        Handle mode change between simple and custom modes.
        
        Shows/hides appropriate panels and validates equations if switching
        to custom mode.
        
        Args:
            None
        
        Returns:
            None
        """
        mode = self.mode_combo.currentText()
        
        if mode == 'Simple Element Correlation':
            self.simple_panel.setVisible(True)
            self.simple_panel.show()
            self.custom_panel.setVisible(False)
            self.custom_panel.hide()
        else:
            self.simple_panel.setVisible(False)
            self.simple_panel.hide()
            self.custom_panel.setVisible(True)
            self.custom_panel.show()
            self.validate_equations()
        
        self.correlation_node.config['mode'] = mode
        self.on_config_changed()
    
    def on_equation_changed(self):
        """
        Handle equation changes with validation.
        
        Args:
            None
        
        Returns:
            None
        """
        self.validate_equations()
        self.on_config_changed()
    
    def validate_equations(self):
        """
        Validate the mathematical equations with error handling.
        
        Tests equations with dummy data and displays validation status
        with colored feedback messages.
        
        Args:
            None
        
        Returns:
            bool: True if equations are valid, False otherwise
        """
        try:
            x_eq = self.x_equation_edit.text().strip()
            y_eq = self.y_equation_edit.text().strip()
            
            if not x_eq and not y_eq:
                self.validation_label.setText("💡 Enter equations above")
                self.validation_label.setStyleSheet("""
                    QLabel {
                        background-color: #FEF3C7;
                        color: #92400E;
                        padding: 5px;
                        border-radius: 4px;
                        font-size: 10px;
                        font-weight: bold;
                    }
                """)
                return False
            
            available_elements = self.get_available_elements()
            if not available_elements:
                self.validation_label.setText("❌ No elements available")
                self.validation_label.setStyleSheet("""
                    QLabel {
                        background-color: #FEE2E2;
                        color: #DC2626;
                        padding: 5px;
                        border-radius: 4px;
                        font-size: 10px;
                        font-weight: bold;
                    }
                """)
                return False
            
            dummy_data = {elem: 1.0 for elem in available_elements}
            
            valid = True
            error_msg = ""
            
            if x_eq:
                try:
                    result = self.evaluate_equation(x_eq, dummy_data)
                    if math.isnan(result) or math.isinf(result):
                        raise ValueError("Result is NaN or infinite")
                except Exception as e:
                    valid = False
                    error_msg = f"X equation error: {str(e)}"
            
            if y_eq and valid:
                try:
                    result = self.evaluate_equation(y_eq, dummy_data)
                    if math.isnan(result) or math.isinf(result):
                        raise ValueError("Result is NaN or infinite")
                except Exception as e:
                    valid = False
                    error_msg = f"Y equation error: {str(e)}"
            
            if valid:
                self.validation_label.setText("✅ Equations are valid")
                self.validation_label.setStyleSheet("""
                    QLabel {
                        background-color: #D1FAE5;
                        color: #059669;
                        padding: 5px;
                        border-radius: 4px;
                        font-size: 10px;
                        font-weight: bold;
                    }
                """)
                return True
            else:
                self.validation_label.setText(f"❌ {error_msg}")
                self.validation_label.setStyleSheet("""
                    QLabel {
                        background-color: #FEE2E2;
                        color: #DC2626;
                        padding: 5px;
                        border-radius: 4px;
                        font-size: 10px;
                        font-weight: bold;
                    }
                """)
                return False
                
        except Exception as e:
            self.validation_label.setText(f"❌ Validation error: {str(e)}")
            self.validation_label.setStyleSheet("""
                QLabel {
                    background-color: #FEE2E2;
                    color: #DC2626;
                    padding: 5px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                }
            """)
            return False
    
    def evaluate_equation(self, equation, element_data):
        """
        Safely evaluate mathematical equation with element values.
        
        Replaces element names with values and evaluates in a restricted
        environment for security.
        
        Args:
            equation (str): Mathematical equation string
            element_data (dict): Dictionary mapping element names to values
        
        Returns:
            float: Result of equation evaluation
        
        Raises:
            ValueError: If equation is invalid or produces NaN/inf
        """
        import re
        import math
        import numpy as np
        
        expr = equation
        for element_name, value in element_data.items():
            pattern = r'\b' + re.escape(element_name) + r'\b'
            expr = re.sub(pattern, str(value), expr)
        
        expr = expr.replace('log(', 'math.log10(')
        expr = expr.replace('ln(', 'math.log(')
        expr = expr.replace('sqrt(', 'math.sqrt(')
        expr = expr.replace('abs(', 'abs(')
        
        safe_dict = {
            "__builtins__": {},
            "math": math,
            "abs": abs,
            "min": min,
            "max": max,
            "pow": pow
        }
        
        try:
            result = eval(expr, safe_dict)
            if math.isnan(result) or math.isinf(result):
                raise ValueError("Result is NaN or infinite")
            return result
        except ZeroDivisionError:
            return float('nan')
        except Exception as e:
            raise ValueError(f"Invalid expression: {str(e)}")
    
    def get_available_elements(self):
        """
        Get available elements from the correlation node's data.
        
        Attempts to extract elements from plot data first, then falls back
        to input data if necessary.
        
        Args:
            None
        
        Returns:
            list: List of available element label strings
        """
        if hasattr(self.correlation_node, 'extract_plot_data'):
            try:
                plot_data = self.correlation_node.extract_plot_data()
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
        
        if not self.correlation_node.input_data:
            return []
        
        data_type = self.correlation_node.input_data.get('type')
        
        if data_type in ['sample_data', 'multiple_sample_data']:
            selected_isotopes = self.correlation_node.input_data.get('selected_isotopes', [])
            if selected_isotopes:
                return [isotope['label'] for isotope in selected_isotopes]
        
        return []
    
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
        mode = self.mode_combo.currentText()
        
        config_updates = {
            'mode': mode,
            'data_type_display': self.data_type_combo.currentText(),
            'filter_zeros': self.filter_zeros_checkbox.isChecked(),
            'filter_saturated': self.filter_saturated_checkbox.isChecked(),
            'saturation_threshold': self.saturation_threshold_spin.value(),
            'show_correlation': self.show_correlation_checkbox.isChecked(),
            'show_trendline': self.show_trendline_checkbox.isChecked(),
            'log_x': self.log_x_checkbox.isChecked(),
            'log_y': self.log_y_checkbox.isChecked(),
            'marker_size': self.marker_size_spin.value(),
            'marker_alpha': self.marker_alpha_spin.value(),
            'font_family': self.font_family_combo.currentText(),
            'font_size': self.font_size_spin.value(),
            'font_bold': self.font_bold_checkbox.isChecked(),
            'font_italic': self.font_italic_checkbox.isChecked(),
            'font_color': self.font_color.name()
        }
        
        if mode == 'Simple Element Correlation':
            config_updates.update({
                'x_element': self.x_element_combo.currentText(),
                'y_element': self.y_element_combo.currentText(),
                'color_element': self.color_element_combo.currentText(),
            })
        else:
            config_updates.update({
                'x_equation': self.x_equation_edit.text(),
                'y_equation': self.y_equation_edit.text(),
                'x_label': self.x_label_edit.text(),
                'y_label': self.y_label_edit.text(),
            })
        
        if not self.is_multiple_sample_data():
            config_updates['single_sample_color'] = self.correlation_node.config.get('single_sample_color', '#3B82F6')
        
        if self.is_multiple_sample_data():
            config_updates.update({
                'display_mode': self.display_mode_combo.currentText()
            })
        
        self.correlation_node.config.update(config_updates)
        
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
   
    def cleanup_color_bars(self):
        """
        Clean up existing color bars before creating new plots.
        
        Args:
            None
        
        Returns:
            None
        """
        for color_bar in self.active_color_bars:
            try:
                color_bar.remove_color_bar()
            except:
                pass
        self.active_color_bars.clear()

    def update_display(self):
        """
        Update the correlation display with support for multiple samples.
        
        Clears existing plot and recreates based on current configuration
        and data. Handles both single and multiple sample modes.
        
        Args:
            None
        
        Returns:
            None
        """
        try:
            self.cleanup_color_bars()
            
            self.plot_widget.clear()
            
            plot_data = self.correlation_node.extract_plot_data()
            
            if not plot_data:
                plot_item = self.plot_widget.addPlot()
                text_item = pg.TextItem("No particle data available\nConnect to Sample Selector\nand Isotope Filter nodes\nThen run particle detection", 
                                      anchor=(0.5, 0.5), color='gray')
                plot_item.addItem(text_item)
                text_item.setPos(0.5, 0.5)
                plot_item.hideAxis('left')
                plot_item.hideAxis('bottom')
            else:
                config = self.correlation_node.config
                
                if self.is_multiple_sample_data():
                    self.create_multiple_sample_correlation(plot_data, config)
                else:
                    plot_item = self.plot_widget.addPlot()
                    self.create_correlation_plot(plot_item, plot_data, config)
                    self.apply_plot_settings(plot_item)
            
        except Exception as e:
            print(f"Error updating correlation display: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def create_multiple_sample_correlation(self, plot_data, config):
        """
        Create correlation plot for multiple samples with different display modes.
        
        Args:
            plot_data (dict): Dictionary of sample data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        display_mode = config.get('display_mode', 'Overlaid (Different Colors)')
        sample_names = list(plot_data.keys())
        
        if display_mode == 'Individual Subplots':
            self.create_subplot_correlations(plot_data, config)
        elif display_mode == 'Side by Side Subplots':
            self.create_side_by_side_correlations(plot_data, config)
        else:
            plot_item = self.plot_widget.addPlot()
            self.create_combined_correlation(plot_item, plot_data, config)
            self.apply_plot_settings(plot_item)
    
    def create_subplot_correlations(self, plot_data, config):
        """
        Create individual subplots for each sample with color bars.
        
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
                self.create_sample_specific_correlation(plot_item, sample_data, config, sample_color)
                
                title_text = f"{self.get_display_name(sample_name)}"
                plot_item.setTitle(title_text)
                
                mode = config.get('mode', 'Simple Element Correlation')
                data_type_display = config.get('data_type_display', 'Counts (Raw)')
                log_x = config.get('log_x', False)
                log_y = config.get('log_y', False)
                
                if mode == 'Simple Element Correlation':
                    x_element = config.get('x_element', '')
                    y_element = config.get('y_element', '')
                    x_label = f"log₁₀({x_element}) ({data_type_display})" if log_x else f"{x_element} ({data_type_display})"
                    y_label = f"log₁₀({y_element}) ({data_type_display})" if log_y else f"{y_element} ({data_type_display})"
                else:
                    x_base_label = config.get('x_label', config.get('x_equation', 'X-axis'))
                    y_base_label = config.get('y_label', config.get('y_equation', 'Y-axis'))
                    x_label = f"log₁₀({x_base_label}) ({data_type_display})" if log_x else f"{x_base_label} ({data_type_display})"
                    y_label = f"log₁₀({y_base_label}) ({data_type_display})" if log_y else f"{y_base_label} ({data_type_display})"
                
                self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
                
                self.apply_plot_settings(plot_item)

    def create_side_by_side_correlations(self, plot_data, config):
        """
        Create side-by-side correlation plots with color bars.
        
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
                self.create_sample_specific_correlation(plot_item, sample_data, config, sample_color)
                
                title_text = f"{self.get_display_name(sample_name)}"
                plot_item.setTitle(title_text)
                
                mode = config.get('mode', 'Simple Element Correlation')
                data_type_display = config.get('data_type_display', 'Counts (Raw)')
                log_x = config.get('log_x', False)
                log_y = config.get('log_y', False)
                
                if mode == 'Simple Element Correlation':
                    x_element = config.get('x_element', '')
                    y_element = config.get('y_element', '')
                    x_label = f"log₁₀({x_element}) ({data_type_display})" if log_x else f"{x_element} ({data_type_display})"
                    y_label = f"log₁₀({y_element}) ({data_type_display})" if log_y else f"{y_element} ({data_type_display})"
                else:
                    x_base_label = config.get('x_label', config.get('x_equation', 'X-axis'))
                    y_base_label = config.get('y_label', config.get('y_equation', 'Y-axis'))
                    x_label = f"log₁₀({x_base_label}) ({data_type_display})" if log_x else f"{x_base_label} ({data_type_display})"
                    y_label = f"log₁₀({y_base_label}) ({data_type_display})" if log_y else f"{y_base_label} ({data_type_display})"
                
                if i == 0:
                    self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
                else:
                    self.set_axis_labels_with_font(plot_item, x_label, "", config)
                
                self.apply_plot_settings(plot_item)

                
    def create_combined_correlation(self, plot_item, plot_data, config):
        """
        Create combined correlation plot (overlaid) with color bars.
        
        Overlays all samples on a single plot with distinct colors and adds
        legend for identification.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            plot_data (dict): Dictionary of sample data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_colors = config.get('sample_colors', {})
        default_colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
        
        mode = config.get('mode', 'Simple Element Correlation')
        data_type_display = config.get('data_type_display', 'Counts (Raw)')
        log_x = config.get('log_x', False)
        log_y = config.get('log_y', False)
        
        legend_items = []
        
        for i, (sample_name, sample_data) in enumerate(plot_data.items()):
            if sample_data and 'element_data' in sample_data:
                element_data = sample_data['element_data']
                
                filtered_element_data = self.apply_global_saturation_filter(element_data, config)
                
                if filtered_element_data.empty:
                    continue
                
                sample_color = sample_colors.get(sample_name, default_colors[i % len(default_colors)])
                
                try:
                    x_values, y_values, color_values = self.extract_xy_values_with_color(filtered_element_data, config)
                    
                    if len(x_values) > 0 and len(y_values) > 0:
                        if config.get('filter_zeros', True):
                            valid_mask = (x_values > 0) & (y_values > 0)
                            x_values = x_values[valid_mask]
                            y_values = y_values[valid_mask]
                            if color_values is not None:
                                color_values = color_values[valid_mask]
                        
                        if len(x_values) > 0:
                            if log_x:
                                valid_x_mask = x_values > 0
                                x_values = x_values[valid_x_mask]
                                y_values = y_values[valid_x_mask]
                                if color_values is not None:
                                    color_values = color_values[valid_x_mask]
                                
                                if len(x_values) == 0:
                                    continue
                                
                                x_values = np.log10(x_values)
                            
                            if log_y:
                                valid_y_mask = y_values > 0
                                x_values = x_values[valid_y_mask]
                                y_values = y_values[valid_y_mask]
                                if color_values is not None:
                                    color_values = color_values[valid_y_mask]
                                
                                if len(y_values) == 0:
                                    continue
                                
                                y_values = np.log10(y_values)
                            
                            if (mode == 'Simple Element Correlation' and 
                                color_values is not None and 
                                config.get('color_element', 'None') != 'None'):
                                
                                scatter = self.create_color_mapped_scatter(plot_item, x_values, y_values, 
                                                                        color_values, config, sample_color,
                                                                        element_name=config.get('color_element'))
                            else:
                                scatter = self.create_single_color_scatter(plot_item, x_values, y_values, 
                                                                        config, sample_color)
                            
                            legend_items.append((scatter, self.get_display_name(sample_name)))
                            
                            if config.get('show_trendline', True) and len(x_values) > 1:
                                self.add_trend_line(plot_item, x_values, y_values, sample_color)
                
                except Exception as e:
                    print(f"Error plotting sample {sample_name}: {str(e)}")
                    continue
        
        if mode == 'Simple Element Correlation':
            x_element = config.get('x_element', 'X-axis')
            y_element = config.get('y_element', 'Y-axis')
            x_label = f"log₁₀({x_element}) ({data_type_display})" if log_x else f"{x_element} ({data_type_display})"
            y_label = f"log₁₀({y_element}) ({data_type_display})" if log_y else f"{y_element} ({data_type_display})"
        else:
            x_base_label = config.get('x_label', config.get('x_equation', 'X-axis'))
            y_base_label = config.get('y_label', config.get('y_equation', 'Y-axis'))
            x_label = f"log₁₀({x_base_label}) ({data_type_display})" if log_x else f"{x_base_label} ({data_type_display})"
            y_label = f"log₁₀({y_base_label}) ({data_type_display})" if log_y else f"{y_base_label} ({data_type_display})"
        
        self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
        
        if legend_items:
            legend = plot_item.addLegend()
            for item, name in legend_items:
                legend.addItem(item, name)
        
    def extract_xy_values_with_color(self, filtered_element_data, config):
        """
        Extract X, Y, and color values based on mode.
        
        Handles both simple element correlation and custom equation modes.
        
        Args:
            filtered_element_data (DataFrame): Filtered particle element data
            config (dict): Configuration dictionary
        
        Returns:
            tuple: (x_values, y_values, color_values) as numpy arrays
        """
        mode = config.get('mode', 'Simple Element Correlation')
        
        if mode == 'Simple Element Correlation':
            x_element = config.get('x_element', '')
            y_element = config.get('y_element', '')
            color_element = config.get('color_element', 'None')
            
            if (x_element and y_element and 
                x_element in filtered_element_data.columns and 
                y_element in filtered_element_data.columns):
                
                x_values = filtered_element_data[x_element].values
                y_values = filtered_element_data[y_element].values
                
                color_values = None
                if (color_element != 'None' and 
                    color_element in filtered_element_data.columns):
                    color_values = filtered_element_data[color_element].values
                
                return x_values, y_values, color_values
        
        else:
            x_equation = config.get('x_equation', '').strip()
            y_equation = config.get('y_equation', '').strip()
            
            if x_equation and y_equation:
                x_vals = []
                y_vals = []
                
                for _, row in filtered_element_data.iterrows():
                    element_dict = row.to_dict()
                    
                    try:
                        x_val = self.evaluate_equation(x_equation, element_dict)
                        y_val = self.evaluate_equation(y_equation, element_dict)
                        
                        if not (math.isnan(x_val) or math.isnan(y_val) or 
                            math.isinf(x_val) or math.isinf(y_val)):
                            x_vals.append(x_val)
                            y_vals.append(y_val)
                    except:
                        continue
                
                if x_vals and y_vals:
                    return np.array(x_vals), np.array(y_vals), None
        
        return np.array([]), np.array([]), None

    def extract_xy_values(self, filtered_element_data, config):
        """
        Extract X and Y values based on mode (backward compatibility).
        
        Args:
            filtered_element_data (DataFrame): Filtered particle element data
            config (dict): Configuration dictionary
        
        Returns:
            tuple: (x_values, y_values) as numpy arrays
        """
        x_values, y_values, _ = self.extract_xy_values_with_color(filtered_element_data, config)
        return x_values, y_values

    def create_correlation_plot(self, plot_item, plot_data, config):
        """
        Create the correlation plot (single sample) with color mapping support and color bars.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            plot_data (dict): Plot data dictionary with element data
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        element_data = plot_data['element_data']
        data_type_display = config.get('data_type_display', 'Counts (Raw)')
        
        filtered_element_data = self.apply_global_saturation_filter(element_data, config)
        
        if filtered_element_data.empty:
            text_item = pg.TextItem('No data after filtering', 
                                anchor=(0.5, 0.5), color='gray')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)
            return
        
        mode = config.get('mode', 'Simple Element Correlation')
        
        try:
            x_values, y_values, color_values = self.extract_xy_values_with_color(filtered_element_data, config)
            
            if len(x_values) == 0 or len(y_values) == 0:
                text_item = pg.TextItem('No valid data from configuration\nCheck your settings', 
                                    anchor=(0.5, 0.5), color='red')
                plot_item.addItem(text_item)
                text_item.setPos(0.5, 0.5)
                return
            
            original_filtered_data = filtered_element_data.copy()
            
            if config.get('filter_zeros', True):
                valid_mask = (x_values > 0) & (y_values > 0)
                x_values = x_values[valid_mask]
                y_values = y_values[valid_mask]
                
                if color_values is not None:
                    color_values = color_values[valid_mask]
                if mode == 'Simple Element Correlation':
                    filtered_element_data = original_filtered_data.iloc[valid_mask]
            
            if len(x_values) == 0:
                text_item = pg.TextItem('No data after zero filtering', 
                                    anchor=(0.5, 0.5), color='red')
                plot_item.addItem(text_item)
                text_item.setPos(0.5, 0.5)
                return
            
            log_x = config.get('log_x', False)
            log_y = config.get('log_y', False)
            
            if log_x:
                valid_x_mask = x_values > 0
                x_values = x_values[valid_x_mask]
                y_values = y_values[valid_x_mask]
                
                if color_values is not None:
                    color_values = color_values[valid_x_mask]
                if mode == 'Simple Element Correlation':
                    filtered_element_data = filtered_element_data.iloc[valid_x_mask]
                
                if len(x_values) == 0:
                    text_item = pg.TextItem('No positive X data for log transformation', 
                                        anchor=(0.5, 0.5), color='red')
                    plot_item.addItem(text_item)
                    text_item.setPos(0.5, 0.5)
                    return
                
                x_values = np.log10(x_values)
            
            if log_y:
                valid_y_mask = y_values > 0
                x_values = x_values[valid_y_mask]
                y_values = y_values[valid_y_mask]
                
                if color_values is not None:
                    color_values = color_values[valid_y_mask]
                if mode == 'Simple Element Correlation':
                    filtered_element_data = filtered_element_data.iloc[valid_y_mask]
                
                if len(y_values) == 0:
                    text_item = pg.TextItem('No positive Y data for log transformation', 
                                        anchor=(0.5, 0.5), color='red')
                    plot_item.addItem(text_item)
                    text_item.setPos(0.5, 0.5)
                    return
                
                y_values = np.log10(y_values)
            
            sample_color = config.get('single_sample_color', '#3B82F6')
            
            scatter = None
            if (mode == 'Simple Element Correlation' and 
                color_values is not None and 
                config.get('color_element', 'None') != 'None'):
                scatter = self.create_color_mapped_scatter(plot_item, x_values, y_values, 
                                                        color_values, config, sample_color,
                                                        element_name=config.get('color_element'))
            else:
                scatter = self.create_single_color_scatter(plot_item, x_values, y_values, 
                                                        config, sample_color)
            
            if config.get('show_trendline', True) and len(x_values) > 1:
                self.add_trend_line(plot_item, x_values, y_values, sample_color)
            
            if config.get('show_correlation', True) and len(x_values) > 1:
                self.add_correlation_text(plot_item, x_values, y_values, config)
            
            if mode == 'Simple Element Correlation':
                x_element = config.get('x_element', '')
                y_element = config.get('y_element', '')
                x_label = f"log₁₀({x_element}) ({data_type_display})" if log_x else f"{x_element} ({data_type_display})"
                y_label = f"log₁₀({y_element}) ({data_type_display})" if log_y else f"{y_element} ({data_type_display})"
            else:
                x_base_label = config.get('x_label', config.get('x_equation', 'X-axis'))
                y_base_label = config.get('y_label', config.get('y_equation', 'Y-axis'))
                x_label = f"log₁₀({x_base_label}) ({data_type_display})" if log_x else f"{x_base_label} ({data_type_display})"
                y_label = f"log₁₀({y_base_label}) ({data_type_display})" if log_y else f"{y_base_label} ({data_type_display})"
            
            self.set_axis_labels_with_font(plot_item, x_label, y_label, config)
            
        except Exception as e:
            text_item = pg.TextItem(f'Error creating plot:\n{str(e)}', 
                                anchor=(0.5, 0.5), color='red')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)

    def create_sample_specific_correlation(self, plot_item, sample_data, config, sample_color):
        """
        Create correlation plot for a specific sample with color mapping support and color bars.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            sample_data (dict): Sample element data dictionary
            config (dict): Configuration dictionary
            sample_color (str): Hex color string for sample
        
        Returns:
            None
        """
        element_data = sample_data.get('element_data')
        if element_data is None:
            return
        
        data_type_display = config.get('data_type_display', 'Counts (Raw)')
        
        filtered_element_data = self.apply_global_saturation_filter(element_data, config)
        
        if filtered_element_data.empty:
            text_item = pg.TextItem('No data after filtering', 
                                anchor=(0.5, 0.5), color='gray')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)
            return
        
        mode = config.get('mode', 'Simple Element Correlation')
        
        try:
            x_values, y_values, color_values = self.extract_xy_values_with_color(filtered_element_data, config)
            
            if len(x_values) > 0 and len(y_values) > 0:
                original_filtered_data = filtered_element_data.copy()
                
                if config.get('filter_zeros', True):
                    valid_mask = (x_values > 0) & (y_values > 0)
                    x_values = x_values[valid_mask]
                    y_values = y_values[valid_mask]
                    
                    if color_values is not None:
                        color_values = color_values[valid_mask]
                    if mode == 'Simple Element Correlation':
                        filtered_element_data = original_filtered_data.iloc[valid_mask]
                
                if len(x_values) > 0:
                    log_x = config.get('log_x', False)
                    log_y = config.get('log_y', False)
                    
                    if log_x:
                        valid_x_mask = x_values > 0
                        x_values = x_values[valid_x_mask]
                        y_values = y_values[valid_x_mask]
                        
                        if color_values is not None:
                            color_values = color_values[valid_x_mask]
                        if mode == 'Simple Element Correlation':
                            filtered_element_data = filtered_element_data.iloc[valid_x_mask]
                        
                        if len(x_values) == 0:
                            return
                        
                        x_values = np.log10(x_values)
                    
                    if log_y:
                        valid_y_mask = y_values > 0
                        x_values = x_values[valid_y_mask]
                        y_values = y_values[valid_y_mask]
                        
                        if color_values is not None:
                            color_values = color_values[valid_y_mask]
                        if mode == 'Simple Element Correlation':
                            filtered_element_data = filtered_element_data.iloc[valid_y_mask]
                        
                        if len(y_values) == 0:
                            return
                        
                        y_values = np.log10(y_values)
                    
                    scatter = None
                    if (mode == 'Simple Element Correlation' and 
                        color_values is not None and 
                        config.get('color_element', 'None') != 'None'):
                        scatter = self.create_color_mapped_scatter(plot_item, x_values, y_values, 
                                                                color_values, config, sample_color,
                                                                element_name=config.get('color_element'))
                    else:
                        scatter = self.create_single_color_scatter(plot_item, x_values, y_values, 
                                                                config, sample_color)
                    
                    if config.get('show_trendline', True) and len(x_values) > 1:
                        self.add_trend_line(plot_item, x_values, y_values, sample_color)
                    
                    if config.get('show_correlation', True) and len(x_values) > 1:
                        self.add_correlation_text(plot_item, x_values, y_values, config)
            
        except Exception as e:
            text_item = pg.TextItem(f'Error creating plot:\n{str(e)}', 
                                anchor=(0.5, 0.5), color='red')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)

    def create_node_correlation(self, plot_item, plot_data):
        """
        Create simple correlation plot for node display (single sample).
        
        Creates a simplified scatter plot with limited points for performance
        in node thumbnail view.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            plot_data (dict): Plot data dictionary with element data
        
        Returns:
            None
        """
        if not plot_data:
            return
        
        element_data = plot_data['element_data']
        
        filtered_element_data = self.apply_global_saturation_filter_node(element_data, self.config)
        
        if filtered_element_data.empty:
            return
        
        mode = self.config.get('mode', 'Simple Element Correlation')
        sample_color = self.config.get('single_sample_color', '#3B82F6')
        log_x = self.config.get('log_x', False)
        log_y = self.config.get('log_y', False)
        
        try:
            if mode == 'Simple Element Correlation':
                x_element = self.config.get('x_element', '')
                y_element = self.config.get('y_element', '')
                
                if (x_element and y_element and 
                    x_element in filtered_element_data.columns and 
                    y_element in filtered_element_data.columns):
                    
                    x_values = filtered_element_data[x_element].values
                    y_values = filtered_element_data[y_element].values
                    
                    if log_x or log_y:
                        valid_mask = (x_values > 0) & (y_values > 0)
                        x_values = x_values[valid_mask]
                        y_values = y_values[valid_mask]
                    
                    if len(x_values) > 0:
                        if log_x:
                            x_values = np.log10(x_values)
                        
                        if log_y:
                            y_values = np.log10(y_values)
                        
                        n_points = min(100, len(x_values))
                        if n_points > 0:
                            indices = np.linspace(0, len(x_values)-1, n_points, dtype=int)
                            
                            color_obj = QColor(sample_color)
                            color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), 180)
                            
                            scatter = pg.ScatterPlotItem(x=x_values[indices], y=y_values[indices], 
                                                    size=4, pen=None, brush=pg.mkBrush(*color_rgba))
                            plot_item.addItem(scatter)
            else:
                x_equation = self.config.get('x_equation', '').strip()
                y_equation = self.config.get('y_equation', '').strip()
                
                if x_equation and y_equation:
                    x_vals, y_vals = [], []
                    for _, row in filtered_element_data.head(min(50, len(filtered_element_data))).iterrows():
                        try:
                            element_dict = row.to_dict()
                            x_val = self.evaluate_equation(x_equation, element_dict)
                            y_val = self.evaluate_equation(y_equation, element_dict)
                            if not (math.isnan(x_val) or math.isnan(y_val)):
                                x_vals.append(x_val)
                                y_vals.append(y_val)
                        except:
                            continue
                    
                    if x_vals and y_vals:
                        x_vals = np.array(x_vals)
                        y_vals = np.array(y_vals)
                        
                        if log_x or log_y:
                            valid_mask = (x_vals > 0) & (y_vals > 0)
                            x_vals = x_vals[valid_mask]
                            y_vals = y_vals[valid_mask]
                        
                        if len(x_vals) > 0:
                            if log_x:
                                x_vals = np.log10(x_vals)
                            
                            if log_y:
                                y_vals = np.log10(y_vals)
                            
                            color_obj = QColor(sample_color)
                            color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), 180)
                            
                            scatter = pg.ScatterPlotItem(x=x_vals, y=y_vals, 
                                                    size=4, pen=None, brush=pg.mkBrush(*color_rgba))
                            plot_item.addItem(scatter)
            
        except Exception as e:
            print(f"Error creating node correlation: {str(e)}")
        
        plot_item.hideAxis('left')
        plot_item.hideAxis('bottom')
        plot_item.setLabel('left', '')
        plot_item.setLabel('bottom', '')
        plot_item.setTitle('')
            
    def add_trend_line(self, plot_item, x_values, y_values, color):
        """
        Add linear regression trend line to plot.
        
        Args:
            plot_item: PyQtGraph PlotItem
            x_values (ndarray): X data values
            y_values (ndarray): Y data values
            color (str): Color for trend line
        
        Returns:
            None
        """
        try:
            if len(x_values) > 1 and len(y_values) > 1:
                z = np.polyfit(x_values, y_values, 1)
                p = np.poly1d(z)
                x_trend = np.linspace(x_values.min(), x_values.max(), 100)
                y_trend = p(x_trend)
                
                trend_line = pg.PlotDataItem(x=x_trend, y=y_trend, 
                                           pen=pg.mkPen(color=color, style=pg.QtCore.Qt.DashLine, width=2))
                plot_item.addItem(trend_line)
        except Exception as e:
            print(f"Error adding trend line: {e}")
    
    def add_correlation_text(self, plot_item, x_values, y_values, config):
        """
        Add correlation coefficient text to plot.
        
        Args:
            plot_item: PyQtGraph PlotItem
            x_values (ndarray): X data values
            y_values (ndarray): Y data values
            config (dict): Configuration dictionary with font settings
        
        Returns:
            None
        """
        try:
            if len(x_values) > 1 and len(y_values) > 1:
                correlation = np.corrcoef(x_values, y_values)[0, 1]
                
                font_family = config.get('font_family', 'Times New Roman')
                font_size = config.get('font_size', 18)
                font_color = config.get('font_color', '#000000')
                
                text_item = pg.TextItem(f'r = {correlation:.3f}', 
                                      anchor=(0, 1), color=font_color)
                
                plot_item.addItem(text_item)
                
                view_box = plot_item.getViewBox()
                x_range = view_box.state['viewRange'][0]
                y_range = view_box.state['viewRange'][1]
                
                text_x = x_range[0] + 0.05 * (x_range[1] - x_range[0])
                text_y = y_range[0] + 0.95 * (y_range[1] - y_range[0])
                
                text_item.setPos(text_x, text_y)
        except Exception as e:
            print(f"Error adding correlation text: {e}")
            
    def create_color_mapped_scatter(self, plot_item, x_values, y_values, color_values, config, base_color='#3B82F6', element_name=""):
        """
        Create scatter plot with color mapping and custom color bar.
        
        Maps color values to a viridis-like colormap and creates individual
        colored markers for each point.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            x_values (ndarray): X coordinates for scatter points
            y_values (ndarray): Y coordinates for scatter points
            color_values (ndarray): Values to map to colors
            config (dict): Configuration dictionary
            base_color (str): Fallback color for NaN values
            element_name (str): Name of element for color bar label
        
        Returns:
            ScatterPlotItem: Created scatter plot item
        """
        try:
            if len(color_values) == 0 or np.all(np.isnan(color_values)):
                return self.create_single_color_scatter(plot_item, x_values, y_values, config, base_color)
            
            valid_color_mask = ~np.isnan(color_values)
            if not np.any(valid_color_mask):
                return self.create_single_color_scatter(plot_item, x_values, y_values, config, base_color)
            
            valid_color_values = color_values[valid_color_mask]
            color_min = np.min(valid_color_values)
            color_max = np.max(valid_color_values)
            
            if color_max == color_min:
                return self.create_single_color_scatter(plot_item, x_values, y_values, config, base_color)
            
            normalized_colors = (color_values - color_min) / (color_max - color_min)
            
            pos = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
            colors = np.array([
                [68, 1, 84, 255],
                [59, 82, 139, 255],
                [33, 145, 140, 255],
                [94, 201, 98, 255],
                [253, 231, 37, 255]
            ], dtype=np.ubyte)
            
            colormap = pg.ColorMap(pos, colors)
            
            marker_size = config.get('marker_size', 6)**2
            marker_alpha = int(config.get('marker_alpha', 0.7) * 255)
            
            spots = []
            for i in range(len(x_values)):
                if np.isnan(color_values[i]):
                    color_obj = QColor(base_color)
                    brush_color = (color_obj.red(), color_obj.green(), color_obj.blue(), marker_alpha)
                else:
                    color_rgba = colormap.map(normalized_colors[i], mode='byte')
                    brush_color = (color_rgba[0], color_rgba[1], color_rgba[2], marker_alpha)
                
                spots.append({
                    'pos': (x_values[i], y_values[i]),
                    'size': marker_size,
                    'pen': pg.mkPen(color='black', width=0.5),
                    'brush': pg.mkBrush(*brush_color)
                })
            
            scatter = pg.ScatterPlotItem()
            scatter.addPoints(spots)
            plot_item.addItem(scatter)
            
            if element_name:
                color_bar = CustomColorBar(plot_item, colormap, color_min, color_max, config, element_name)
                color_bar_items = color_bar.create_color_bar()
                if color_bar_items:
                    self.active_color_bars.append(color_bar)
            
            return scatter
            
        except Exception as e:
            print(f"Error creating color mapped scatter: {e}")
            return self.create_single_color_scatter(plot_item, x_values, y_values, config, base_color)
        
    
    def create_single_color_scatter(self, plot_item, x_values, y_values, config, color='#3B82F6'):
        """
        Create scatter plot with single color for all points.
        
        Args:
            plot_item: PyQtGraph PlotItem for drawing
            x_values (ndarray): X coordinates for scatter points
            y_values (ndarray): Y coordinates for scatter points
            config (dict): Configuration dictionary
            color (str): Hex color string for all markers
        
        Returns:
            ScatterPlotItem: Created scatter plot item
        """
        marker_size = config.get('marker_size', 6)**2
        marker_alpha = int(config.get('marker_alpha', 0.7) * 255)
        
        color_obj = QColor(color)
        color_rgba = (color_obj.red(), color_obj.green(), color_obj.blue(), marker_alpha)
        
        scatter = pg.ScatterPlotItem(x=x_values, y=y_values, 
                                size=marker_size, 
                                pen=pg.mkPen(color='black', width=0.5),
                                brush=pg.mkBrush(*color_rgba))
        plot_item.addItem(scatter)
        return scatter


class CorrelationPlotNode(QObject):
    """
    Enhanced Correlation plot node with multiple sample support.
    
    This node manages correlation plotting configuration and data processing
    for both single and multiple sample workflows. It connects to the visual
    node system and provides data extraction and processing capabilities.
    """
    
    position_changed = Signal(object)
    configuration_changed = Signal()
    
    def __init__(self, parent_window=None):
        """
        Initialize correlation plot node.
        
        Args:
            parent_window: Parent window widget (optional)
        
        Returns:
            None
        """
        super().__init__()
        self.title = "Element Correlation"
        self.node_type = "correlation_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.config = {
            'mode': 'Simple Element Correlation',
            'x_element': '',
            'y_element': '',
            'color_element': 'None',
            'x_equation': '',
            'y_equation': '',
            'x_label': 'X-axis',
            'y_label': 'Y-axis',
            'data_type_display': 'Counts (Raw)',
            'filter_zeros': True,
            'filter_saturated': True,
            'saturation_threshold': 10000,
            'show_correlation': True,
            'show_trendline': True,
            'log_x': False,
            'log_y': False,
            'marker_size': 6,
            'marker_alpha': 0.7,
            'single_sample_color': '#3B82F6',
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
        
        Args:
            parent_window: Parent window widget
        
        Returns:
            bool: True if configuration was successful
        """
        dialog = CorrelationPlotDisplayDialog(self, parent_window)
        dialog.exec()
        return True
        
    def process_data(self, input_data):
        """
        Process input data and update correlation plot.
        
        Receives data from connected nodes, auto-configures elements if needed,
        and triggers visual updates.
        
        Args:
            input_data (dict): Input data dictionary from upstream nodes
        
        Returns:
            None
        """
        if not input_data:
            print("No input data received for correlation plot")
            return
            
        print(f"Correlation plot received data: {input_data.get('type', 'unknown')}")
        self.input_data = input_data
        
        if not self.config.get('x_element') or not self.config.get('y_element'):
            self.auto_configure_elements()
        
        self.configuration_changed.emit()
        
    def auto_configure_elements(self):
        """
        Auto-configure elements when data is first received.
        
        Automatically selects first two available elements for X and Y axes.
        
        Args:
            None
        
        Returns:
            None
        """
        if not self.input_data:
            return
            
        available_elements = self.get_available_elements()
        
        if len(available_elements) >= 2:
            self.config['x_element'] = available_elements[0]
            self.config['y_element'] = available_elements[1]
            
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
        if not config.get('filter_saturated', True):
            return element_data
        
        threshold = config.get('saturation_threshold', 10000)
        
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
            data_key (str): Key for data type in particle dictionary
        
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
            data_key (str): Key for data type in particle dictionary
        
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
            
        
    def evaluate_equation(self, equation, element_data):
        """
        Safely evaluate mathematical equation with element values.
        
        Replaces element names with values and evaluates in a restricted
        environment for security. Same implementation as in dialog.
        
        Args:
            equation (str): Mathematical equation string
            element_data (dict): Dictionary mapping element names to values
        
        Returns:
            float: Result of equation evaluation
        
        Raises:
            ValueError: If equation is invalid or produces NaN/inf
        """
        import re
        import math
        
        expr = equation
        for element_name, value in element_data.items():
            pattern = r'\b' + re.escape(element_name) + r'\b'
            expr = re.sub(pattern, str(value), expr)
        
        expr = expr.replace('log(', 'math.log10(')
        expr = expr.replace('ln(', 'math.log(')
        expr = expr.replace('sqrt(', 'math.sqrt(')
        expr = expr.replace('abs(', 'abs(')
        
        safe_dict = {
            "__builtins__": {},
            "math": math,
            "abs": abs,
            "min": min,
            "max": max,
            "pow": pow
        }
        
        try:
            result = eval(expr, safe_dict)
            if math.isnan(result) or math.isinf(result):
                raise ValueError("Result is NaN or infinite")
            return result
        except ZeroDivisionError:
            return float('nan')
        except Exception as e:
            raise ValueError(f"Invalid expression: {str(e)}")