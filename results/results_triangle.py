from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                              QLabel, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                              QDialogButtonBox, QGroupBox, QColorDialog, QPushButton,
                              QLineEdit, QGraphicsProxyWidget, QFrame, QScrollArea, QWidget, 
                              QListWidgetItem, QListWidget, QMessageBox, QSlider)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import math
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import mpltern
from widget.colors import default_colors, colorheatmap

class TernaryPlotHelper:
    """
    Helper class for ternary plotting using mpltern.
    """
    
    @staticmethod
    def create_ternary_axes(ax, element_labels=None, show_grid=True, font_props=None):
        """
        Create ternary plot axes and labels using mpltern with font settings.
        
        Args:
            ax: Matplotlib axes object with ternary projection
            element_labels (list): List of three element labels
            show_grid (bool): Whether to show grid lines
            font_props: Matplotlib font properties object
        
        Returns:
            ax: Configured ternary axes object
        """
        if element_labels is None:
            element_labels = ['Element A', 'Element B', 'Element C']
        
        if font_props:
            ax.set_tlabel(element_labels[2], fontproperties=font_props)
            ax.set_llabel(element_labels[0], fontproperties=font_props)
            ax.set_rlabel(element_labels[1], fontproperties=font_props)
        else:
            ax.set_tlabel(element_labels[2])
            ax.set_llabel(element_labels[0])
            ax.set_rlabel(element_labels[1])
        
        if show_grid:
            ax.grid(True, alpha=0.3)
            ticks = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
            ax.taxis.set_ticks(ticks)
            ax.laxis.set_ticks(ticks)
            ax.raxis.set_ticks(ticks)
            
            tick_labels = [f'{int(t*100)}%' for t in ticks]
            ax.taxis.set_ticklabels(tick_labels)
            ax.laxis.set_ticklabels(tick_labels)
            ax.raxis.set_ticklabels(tick_labels)
            
            if font_props:
                for tick_label in ax.taxis.get_ticklabels():
                    tick_label.set_fontproperties(font_props)
                for tick_label in ax.laxis.get_ticklabels():
                    tick_label.set_fontproperties(font_props)
                for tick_label in ax.raxis.get_ticklabels():
                    tick_label.set_fontproperties(font_props)
        else:
            ax.grid(False)
        
        ax.set_title('')
        
        return ax


class TriangleDisplayDialog(QDialog):
    """
    Enhanced Dialog for triangle/ternary plot visualization with multiple sample support and font settings.
    """
    
    def __init__(self, triangle_node, parent_window=None):
        """
        Initialize the triangle display dialog.
        
        Args:
            triangle_node: Triangle plot node instance
            parent_window: Parent window widget
        """
        super().__init__(parent_window)
        self.triangle_node = triangle_node
        self.parent_window = parent_window
    
        self.setWindowTitle("Ternary Composition Analysis")
        self.setMinimumSize(1600, 900)
        
        self.setup_ui()
        self.update_display()
        
        self.triangle_node.configuration_changed.connect(self.update_display)
    
    def is_multiple_sample_data(self):
        """
        Check if we're dealing with multiple sample data.
        
        Returns:
            bool: True if multiple sample data, False otherwise
        """
        return (hasattr(self.triangle_node, 'input_data') and 
                self.triangle_node.input_data and 
                self.triangle_node.input_data.get('type') == 'multiple_sample_data')
    
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
        config_panel.setFixedWidth(500)
        layout.addWidget(config_panel)
        
        plot_panel = self.create_plot_panel()
        layout.addWidget(plot_panel, stretch=1)
        
    def create_config_panel(self):
        """
        Create the triangle plot configuration panel.
        
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        title = QLabel("Trenary Plot Settings")
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
                'Combined Plot',
                'Overlaid Samples'
            ])
            self.display_mode_combo.setCurrentText(self.triangle_node.config.get('display_mode', 'Individual Subplots'))
            self.display_mode_combo.currentTextChanged.connect(self.on_config_changed)
            multiple_layout.addRow("Display Mode:", self.display_mode_combo)
            
            layout.addWidget(multiple_group)
        
        element_group = QGroupBox("Element Selection")
        element_layout = QFormLayout(element_group)
        
        available_elements = self.get_available_elements()
        
        self.element_a_combo = QComboBox()
        self.element_a_combo.addItems(['-- Select Element A --'] + available_elements)
        self.element_a_combo.setCurrentText(self.triangle_node.config.get('element_a', '-- Select Element A --'))
        self.element_a_combo.currentTextChanged.connect(self.on_config_changed)
        element_layout.addRow("Element A (Bottom Left):", self.element_a_combo)
        
        self.element_b_combo = QComboBox()
        self.element_b_combo.addItems(['-- Select Element B --'] + available_elements)
        self.element_b_combo.setCurrentText(self.triangle_node.config.get('element_b', '-- Select Element B --'))
        self.element_b_combo.currentTextChanged.connect(self.on_config_changed)
        element_layout.addRow("Element B (Bottom Right):", self.element_b_combo)
        
        self.element_c_combo = QComboBox()
        self.element_c_combo.addItems(['-- Select Element C --'] + available_elements)
        self.element_c_combo.setCurrentText(self.triangle_node.config.get('element_c', '-- Select Element C --'))
        self.element_c_combo.currentTextChanged.connect(self.on_config_changed)
        element_layout.addRow("Element C (Top):", self.element_c_combo)
        
        layout.addWidget(element_group)
        
        data_group = QGroupBox("Data Type")
        data_layout = QVBoxLayout(data_group)
        
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems([
            'Counts (%)',
            'Element Mass (%)', 
            'Particle Mass (%)',
            'Element Moles (%)',
            'Particle Moles (%)'
        ])
        self.data_type_combo.setCurrentText(self.triangle_node.config.get('data_type_display', 'Counts (%)'))
        self.data_type_combo.currentTextChanged.connect(self.on_data_type_changed)
        data_layout.addWidget(self.data_type_combo)
        
        layout.addWidget(data_group)

        font_group = QGroupBox("Font Settings")
        font_layout = QFormLayout(font_group)
        
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(self.get_font_families())
        self.font_family_combo.setCurrentText(self.triangle_node.config.get('font_family', 'Times New Roman'))
        self.font_family_combo.currentTextChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Family:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(self.triangle_node.config.get('font_size', 18))
        self.font_size_spin.valueChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Size:", self.font_size_spin)
        
        font_style_layout = QHBoxLayout()
        self.font_bold_checkbox = QCheckBox("Bold")
        self.font_bold_checkbox.setChecked(self.triangle_node.config.get('font_bold', False))
        self.font_bold_checkbox.stateChanged.connect(self.on_config_changed)
        self.font_italic_checkbox = QCheckBox("Italic")
        self.font_italic_checkbox.setChecked(self.triangle_node.config.get('font_italic', False))
        self.font_italic_checkbox.stateChanged.connect(self.on_config_changed)
        font_style_layout.addWidget(self.font_bold_checkbox)
        font_style_layout.addWidget(self.font_italic_checkbox)
        font_style_layout.addStretch()
        font_layout.addRow("Font Style:", font_style_layout)
        
        self.font_color_button = QPushButton()
        self.font_color = QColor(self.triangle_node.config.get('font_color', '#000000'))
        self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 30px;")
        self.font_color_button.clicked.connect(lambda: self.choose_color('font'))
        font_layout.addRow("Font Color:", self.font_color_button)
        
        layout.addWidget(font_group)
 
        style_group = QGroupBox("Plot Style")
        style_layout = QFormLayout(style_group)
        
        self.plot_type_combo = QComboBox()
        self.plot_type_combo.addItems(['Scatter Plot', 'Density Plot (Hexbin)'])
        self.plot_type_combo.setCurrentText(self.triangle_node.config.get('plot_type', 'Scatter Plot'))
        self.plot_type_combo.currentTextChanged.connect(self.on_plot_type_changed)
        style_layout.addRow("Plot Type:", self.plot_type_combo)
        
        average_group = QGroupBox("Average Point Display")
        average_layout = QFormLayout(average_group)

        self.show_average_checkbox = QCheckBox()
        self.show_average_checkbox.setChecked(self.triangle_node.config.get('show_average_point', True))
        self.show_average_checkbox.stateChanged.connect(self.on_config_changed)
        average_layout.addRow("Show Average Point:", self.show_average_checkbox)

        self.average_color_button = QPushButton()
        self.average_color = QColor(self.triangle_node.config.get('average_point_color', '#FF0000'))
        self.average_color_button.setStyleSheet(f"background-color: {self.average_color.name()}; min-height: 30px;")
        self.average_color_button.clicked.connect(lambda: self.choose_color('average'))
        average_layout.addRow("Average Point Color:", self.average_color_button)

        self.average_size_spin = QSpinBox()
        self.average_size_spin.setRange(20, 200)
        self.average_size_spin.setValue(self.triangle_node.config.get('average_point_size', 100))
        self.average_size_spin.valueChanged.connect(self.on_config_changed)
        average_layout.addRow("Average Point Size:", self.average_size_spin)

        self.show_average_text_checkbox = QCheckBox()
        self.show_average_text_checkbox.setChecked(self.triangle_node.config.get('show_average_text', True))
        self.show_average_text_checkbox.stateChanged.connect(self.on_config_changed)
        average_layout.addRow("Show Average Text:", self.show_average_text_checkbox)

        self.average_all_elements_checkbox = QCheckBox()
        self.average_all_elements_checkbox.setChecked(self.triangle_node.config.get('average_only_with_all_elements', True))
        self.average_all_elements_checkbox.stateChanged.connect(self.on_config_changed)
        average_layout.addRow("Average Only With All 3 Elements:", self.average_all_elements_checkbox)

        layout.addWidget(average_group)
                        
        self.scatter_controls_widget = QWidget()
        scatter_controls_layout = QFormLayout(self.scatter_controls_widget)
        scatter_controls_layout.setContentsMargins(0, 0, 0, 0)
        
        self.marker_size_spin = QSpinBox()
        self.marker_size_spin.setRange(1, 100)
        self.marker_size_spin.setValue(self.triangle_node.config.get('marker_size', 20))
        self.marker_size_spin.valueChanged.connect(self.on_config_changed)
        scatter_controls_layout.addRow("Marker Size:", self.marker_size_spin)
        
        self.marker_alpha_slider = QSlider(Qt.Horizontal)
        self.marker_alpha_slider.setRange(1, 100)
        self.marker_alpha_slider.setValue(int(self.triangle_node.config.get('marker_alpha', 0.7) * 100))
        self.marker_alpha_slider.valueChanged.connect(self.on_config_changed)
        scatter_controls_layout.addRow("Transparency:", self.marker_alpha_slider)
        
        style_layout.addRow(self.scatter_controls_widget)
        
        self.hexbin_controls_widget = QWidget()
        hexbin_controls_layout = QFormLayout(self.hexbin_controls_widget)
        hexbin_controls_layout.setContentsMargins(0, 0, 0, 0)
        
        self.hexbin_gridsize_spin = QSpinBox()
        self.hexbin_gridsize_spin.setRange(10, 100)
        self.hexbin_gridsize_spin.setValue(self.triangle_node.config.get('hexbin_gridsize', 30))
        self.hexbin_gridsize_spin.valueChanged.connect(self.on_config_changed)
        hexbin_controls_layout.addRow("Hexbin Grid Size:", self.hexbin_gridsize_spin)
        
        self.hexbin_alpha_slider = QSlider(Qt.Horizontal)
        self.hexbin_alpha_slider.setRange(1, 100)
        self.hexbin_alpha_slider.setValue(int(self.triangle_node.config.get('hexbin_alpha', 0.8) * 100))
        self.hexbin_alpha_slider.valueChanged.connect(self.on_config_changed)
        hexbin_controls_layout.addRow("Hexbin Transparency:", self.hexbin_alpha_slider)
        
        style_layout.addRow(self.hexbin_controls_widget)
        
        self.show_grid_checkbox = QCheckBox()
        self.show_grid_checkbox.setChecked(self.triangle_node.config.get('show_grid', True))
        self.show_grid_checkbox.stateChanged.connect(self.on_config_changed)
        style_layout.addRow("Show Grid:", self.show_grid_checkbox)
        
        self.colormap_combo = QComboBox()
        colormaps = colorheatmap
        self.colormap_combo.addItems(colormaps)
        self.colormap_combo.setCurrentText(self.triangle_node.config.get('colormap', 'YlGn'))
        self.colormap_combo.currentTextChanged.connect(self.on_config_changed)
        style_layout.addRow("Color Map:", self.colormap_combo)
        
        self.show_colorbar_checkbox = QCheckBox()
        self.show_colorbar_checkbox.setChecked(self.triangle_node.config.get('show_colorbar', True))
        self.show_colorbar_checkbox.stateChanged.connect(self.on_config_changed)
        style_layout.addRow("Show Color Bar:", self.show_colorbar_checkbox)
        
        self.colorbar_label_edit = QLineEdit()
        self.colorbar_label_edit.setText(self.triangle_node.config.get('colorbar_label', 'Density'))
        self.colorbar_label_edit.textChanged.connect(self.on_config_changed)
        style_layout.addRow("Color Bar Label:", self.colorbar_label_edit)
        
        layout.addWidget(style_group)
        
        self.update_plot_type_controls()
        
        if self.is_multiple_sample_data():
            self.sample_colors_group = QGroupBox("Sample Colors & Names")
            self.sample_colors_layout = QVBoxLayout(self.sample_colors_group)
            self.update_sample_color_controls()
            layout.addWidget(self.sample_colors_group)
        
        filter_group = QGroupBox("Filter Settings")
        filter_layout = QFormLayout(filter_group)
        
        self.min_total_spin = QDoubleSpinBox()
        self.min_total_spin.setRange(0.0, 1000.0)
        self.min_total_spin.setDecimals(2)
        self.min_total_spin.setValue(self.triangle_node.config.get('min_total', 0.0))
        self.min_total_spin.valueChanged.connect(self.on_config_changed)
        filter_layout.addRow("Min Total (sum of 3 elements):", self.min_total_spin)
        
        self.max_particles_spin = QSpinBox()
        self.max_particles_spin.setRange(1, 10000000)
        self.max_particles_spin.setValue(self.triangle_node.config.get('max_particles', 10000000))
        self.max_particles_spin.valueChanged.connect(self.on_config_changed)
        filter_layout.addRow("Max Particles to Plot:", self.max_particles_spin)
        
        layout.addWidget(filter_group)
        
        stats_group = QGroupBox("Data Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_label = QLabel("Connect data to see statistics")
        self.stats_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_group)
        
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
    
    def on_plot_type_changed(self):
        """
        Handle plot type change.
        
        Returns:
            None
        """
        self.update_plot_type_controls()
        self.on_config_changed()
    
    def update_plot_type_controls(self):
        """
        Show/hide controls based on plot type.
        
        Returns:
            None
        """
        plot_type = self.plot_type_combo.currentText()
        
        if plot_type == 'Scatter Plot':
            self.scatter_controls_widget.setVisible(True)
            self.hexbin_controls_widget.setVisible(False)
        else:
            self.scatter_controls_widget.setVisible(False)
            self.hexbin_controls_widget.setVisible(True)
    
    def choose_color(self, color_type):
        """
        Open color dialog for font color or average point color.
        
        Args:
            color_type (str): Type of color to choose ('font' or 'average')
        
        Returns:
            None
        """
        if color_type == 'font':
            color = QColorDialog.getColor(self.font_color, self, "Select Font Color")
            if color.isValid():
                self.font_color = color
                self.font_color_button.setStyleSheet(f"background-color: {color.name()}; min-height: 30px;")
                self.on_config_changed()
        elif color_type == 'average':
            color = QColorDialog.getColor(self.average_color, self, "Select Average Point Color")
            if color.isValid():
                self.average_color = color
                self.average_color_button.setStyleSheet(f"background-color: {color.name()}; min-height: 30px;")
                self.on_config_changed()

    def create_font_properties(self, config):
        """
        Create matplotlib font properties from config.
        
        Args:
            config (dict): Configuration dictionary with font settings
        
        Returns:
            fm.FontProperties: Matplotlib font properties object
        """
        font_family = config.get('font_family', 'Times New Roman')
        font_size = config.get('font_size', 18)
        is_bold = config.get('font_bold', False)
        is_italic = config.get('font_italic', False)
        
        font_props = fm.FontProperties(
            family=font_family,
            size=font_size,
            weight='bold' if is_bold else 'normal',
            style='italic' if is_italic else 'normal'
        )
        
        return font_props

    def apply_font_to_axes(self, ax, config):
        """
        Apply font settings to matplotlib axes including legend.
        
        Args:
            ax: Matplotlib axes object
            config (dict): Configuration dictionary with font settings
        
        Returns:
            None
        """
        try:
            font_props = self.create_font_properties(config)
            font_color = config.get('font_color', '#000000')
            
            for axis_name in ['taxis', 'laxis', 'raxis']:
                if hasattr(ax, axis_name):
                    axis = getattr(ax, axis_name)
                    for tick_label in axis.get_ticklabels():
                        tick_label.set_fontproperties(font_props)
                        tick_label.set_color(font_color)
            
            legend = ax.get_legend()
            if legend is not None:
                for text in legend.get_texts():
                    text.set_fontproperties(font_props)
                    text.set_color(font_color)
                
                legend.get_frame().set_facecolor('white')
                legend.get_frame().set_alpha(0.9)
                legend.get_frame().set_edgecolor('gray')
                legend.get_frame().set_linewidth(1)
            
            title = ax.get_title()
            if title:
                ax.set_title(title, fontproperties=font_props, color=font_color)
                
        except Exception as e:
            print(f"Error applying font to axes: {e}")

    def apply_font_to_colorbar(self, cbar, config):
        """
        Apply font settings to colorbar.
        
        Args:
            cbar: Matplotlib colorbar object
            config (dict): Configuration dictionary with font settings
        
        Returns:
            None
        """
        try:
            font_props = self.create_font_properties(config)
            font_color = config.get('font_color', '#000000')
            
            cbar.set_label(cbar.get_label(), fontproperties=font_props, color=font_color)
            
            for tick_label in cbar.ax.get_yticklabels():
                tick_label.set_fontproperties(font_props)
                tick_label.set_color(font_color)
                
        except Exception as e:
            print(f"Error applying font to colorbar: {e}")
    
    def get_available_elements(self):
        """
        Get available elements from input data.
        
        Returns:
            list: Sorted list of available element names
        """
        if not self.triangle_node.input_data:
            return []
        
        elements = set()
        particles = self.triangle_node.input_data.get('particle_data', [])
        
        for particle in particles:
            elements.update(particle.get('elements', {}).keys())
        
        return sorted(list(elements))
    
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
        
        sample_colors = self.triangle_node.config.get('sample_colors', {})
        
        sample_name_mappings = self.triangle_node.config.get('sample_name_mappings', {})
        
        self.sample_name_edits = {}
        
        for i, original_sample_name in enumerate(sample_names):
            sample_layout = QHBoxLayout()
            
            name_edit = QLineEdit()
            name_edit.setFixedWidth(200)
            
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
            color_button.setFixedSize(30, 20)
            
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
            reset_button.setFixedSize(20, 20)
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
        
        self.triangle_node.config['sample_colors'] = sample_colors
        self.triangle_node.config['sample_name_mappings'] = sample_name_mappings

    def on_sample_name_changed(self, original_name, new_name):
        """
        Handle sample name change.
        
        Args:
            original_name (str): Original sample name
            new_name (str): New display name
        
        Returns:
            None
        """
        if 'sample_name_mappings' not in self.triangle_node.config:
            self.triangle_node.config['sample_name_mappings'] = {}
        
        self.triangle_node.config['sample_name_mappings'][original_name] = new_name
        
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
        
        if 'sample_name_mappings' in self.triangle_node.config:
            self.triangle_node.config['sample_name_mappings'].pop(original_name, None)
        
        self.on_config_changed()

    def get_display_name(self, original_name):
        """
        Get display name for a sample (either custom or original).
        
        Args:
            original_name (str): Original sample name
        
        Returns:
            str: Display name for the sample
        """
        mappings = self.triangle_node.config.get('sample_name_mappings', {})
        return mappings.get(original_name, original_name)
        
    def get_available_sample_names(self):
        """
        Get available sample names from input data.
        
        Returns:
            list: List of sample names
        """
        if self.is_multiple_sample_data():
            return self.triangle_node.input_data.get('sample_names', [])
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
        current_color = self.triangle_node.config.get('sample_colors', {}).get(sample_name, '#3B82F6')
        display_name = self.get_display_name(sample_name)
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {display_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'sample_colors' not in self.triangle_node.config:
                self.triangle_node.config['sample_colors'] = {}
            self.triangle_node.config['sample_colors'][sample_name] = color_hex
            
            self.on_config_changed()
    
    def download_figure(self):
        """
        Download the current figure.
        
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        custom_title = self.triangle_node.config.get('custom_title', 'triangle_plot')
        safe_filename = "".join(c for c in custom_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_filename = safe_filename.replace(' ', '_').lower()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Trernary Plot",
            f"{safe_filename}.png",
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;JPEG Files (*.jpg);;All Files (*)"
        )
        
        if file_path:
            try:
                self.figure.savefig(file_path, dpi=300, bbox_inches='tight', 
                                facecolor='white', edgecolor='none')
                QMessageBox.information(self, "✅ Success", 
                                    f"Trernary plot saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", 
                                f"Failed to save:\n{str(e)}")
    
    def create_plot_panel(self):
        """
        Create the expandable plot panel.
        
        Returns:
            QFrame: Frame widget containing the plot canvas
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
        
        self.figure = Figure(figsize=(16, 10), dpi=160, tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        return panel

    def on_config_changed(self):
        """
        Handle configuration changes.
        
        Returns:
            None
        """
        config_updates = {
            'element_a': self.element_a_combo.currentText(),
            'element_b': self.element_b_combo.currentText(),
            'element_c': self.element_c_combo.currentText(),
            'data_type_display': self.data_type_combo.currentText(),
            'plot_type': self.plot_type_combo.currentText(),
            'marker_size': self.marker_size_spin.value(),
            'marker_alpha': self.marker_alpha_slider.value() / 100.0,
            'hexbin_gridsize': self.hexbin_gridsize_spin.value(),
            'hexbin_alpha': self.hexbin_alpha_slider.value() / 100.0,
            'show_grid': self.show_grid_checkbox.isChecked(),
            'colormap': self.colormap_combo.currentText(),
            'show_colorbar': self.show_colorbar_checkbox.isChecked(),
            'colorbar_label': self.colorbar_label_edit.text(),
            'min_total': self.min_total_spin.value(),
            'max_particles': self.max_particles_spin.value(),
            'font_family': self.font_family_combo.currentText(),
            'font_size': self.font_size_spin.value(),
            'font_bold': self.font_bold_checkbox.isChecked(),
            'font_italic': self.font_italic_checkbox.isChecked(),
            'font_color': self.font_color.name(),
            'show_average_point': self.show_average_checkbox.isChecked(),
            'average_point_color': self.average_color.name(),
            'average_point_size': self.average_size_spin.value(),
            'show_average_text': self.show_average_text_checkbox.isChecked(),
            'average_only_with_all_elements': self.average_all_elements_checkbox.isChecked()  

        }
        
        if self.is_multiple_sample_data():
            config_updates.update({
                'display_mode': self.display_mode_combo.currentText()
            })
        
        self.triangle_node.config.update(config_updates)
        
        self.update_display()
        
    def calculate_and_plot_average(self, ax, sample_data, config, sample_name=""):
        """
        Calculate and plot average point with statistics, optionally filtering for particles with all elements.
        
        Args:
            ax: Matplotlib axes object
            sample_data (list): List of sample data points
            config (dict): Configuration dictionary
            sample_name (str): Name of the sample
        
        Returns:
            None
        """
        if not sample_data or not config.get('show_average_point', True):
            return
        
        filtered_data = sample_data
        if config.get('average_only_with_all_elements', True):
            filtered_data = self.filter_particles_with_all_elements(sample_data, config)
            
            if not filtered_data:
                return
        
        a_vals = [point['a'] for point in filtered_data]
        b_vals = [point['b'] for point in filtered_data]
        c_vals = [point['c'] for point in filtered_data]
        
        if not a_vals:
            return
        
        mean_a = np.mean(a_vals)
        mean_b = np.mean(b_vals)
        mean_c = np.mean(c_vals)
        
        std_a = np.std(a_vals)
        std_b = np.std(b_vals)
        std_c = np.std(c_vals)
        
        mean_a_pct = mean_a * 100
        mean_b_pct = mean_b * 100
        mean_c_pct = mean_c * 100
        std_a_pct = std_a * 100
        std_b_pct = std_b * 100
        std_c_pct = std_c * 100
        
        element_a = config.get('element_a', 'Element A')
        element_b = config.get('element_b', 'Element B')
        element_c = config.get('element_c', 'Element C')
        
        average_color = config.get('average_point_color', '#FF0000')
        average_size = config.get('average_point_size', 100)
        
        filter_suffix = ""
        if config.get('average_only_with_all_elements', True):
            total_particles = len(sample_data)
            filtered_particles = len(filtered_data)
            if filtered_particles < total_particles:
                filter_suffix = f" ({filtered_particles}/{total_particles} particles)"
        
        ax.scatter([mean_b], [mean_c], [mean_a],
                s=average_size,
                marker='*',
                color=average_color,
                edgecolors='black',
                linewidth=2,
                zorder=10,
                label=f'Average{" (" + sample_name + ")" if sample_name else ""}{filter_suffix}')
        
        if config.get('show_average_text', True):
            text_font = fm.FontProperties(
                family='Times New Roman',
                size=12,
                weight='bold',
                style='normal'
            )
            
            text_x = mean_b + 0.2
            text_y = mean_c + 0.01
            text_z = 1 - text_x - text_y
            
            stats_text = f"{element_a}: {mean_a_pct:.1f}±{std_a_pct:.1f}%\n"
            stats_text += f"{element_b}: {mean_b_pct:.1f}±{std_b_pct:.1f}%\n"
            stats_text += f"{element_c}: {mean_c_pct:.1f}±{std_c_pct:.1f}%"
            
            ax.text(text_x, text_y, text_z, stats_text,
                fontproperties=text_font,
                color='black',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='gray'),
                ha='left',
                va='bottom',
                zorder=11)
                
    def filter_particles_with_all_elements(self, sample_data, config):
        """
        Filter particles to only include those with all three selected elements detected.
        
        Args:
            sample_data (list): List of sample data points
            config (dict): Configuration dictionary
        
        Returns:
            list: Filtered list of particles with all three elements
        """
        if not sample_data:
            return []
        
        data_type_display = config.get('data_type_display', 'Counts (%)')
        filtered_particles = []
        
        for point in sample_data:
            
            a_val = point.get('a', 0)
            b_val = point.get('b', 0)
            c_val = point.get('c', 0)
            
            if a_val > 0 and b_val > 0 and c_val > 0:
                filtered_particles.append(point)
        
        return filtered_particles
    
    def get_particles_with_all_elements_from_raw_data(self, config):
        """
        Get count of particles that have all three elements from raw data.
        
        Args:
            config (dict): Configuration dictionary
        
        Returns:
            tuple: (particles_with_all_elements, total_particles)
        """
        if not self.input_data:
            return 0, 0
        
        element_a = config.get('element_a', '-- Select Element A --')
        element_b = config.get('element_b', '-- Select Element B --')
        element_c = config.get('element_c', '-- Select Element C --')
        
        if (element_a.startswith('--') or element_b.startswith('--') or element_c.startswith('--')):
            return 0, 0
        
        data_type_display = config.get('data_type_display', 'Counts (%)')
        data_key_mapping = {
            'Counts (%)': 'elements',
            'Element Mass (%)': 'element_mass_fg',
            'Particle Mass (%)': 'particle_mass_fg',
            'Element Moles (%)': 'element_moles_fmol',
            'Particle Moles (%)': 'particle_moles_fmol'
        }
        data_key = data_key_mapping.get(data_type_display, 'elements')
        
        particles = self.input_data.get('particle_data', [])
        total_particles = 0
        particles_with_all_elements = 0
        
        for particle in particles:
            total_particles += 1
            particle_data_dict = particle.get(data_key, {})
            
            val_a = particle_data_dict.get(element_a, 0)
            val_b = particle_data_dict.get(element_b, 0)
            val_c = particle_data_dict.get(element_c, 0)
            
            if data_key == 'elements':
                if val_a > 0 and val_b > 0 and val_c > 0:
                    particles_with_all_elements += 1
            else:
                if (not np.isnan(val_a) and not np.isnan(val_b) and not np.isnan(val_c) and
                    val_a > 0 and val_b > 0 and val_c > 0):
                    particles_with_all_elements += 1
        
        return particles_with_all_elements, total_particles

    def update_display(self):
        """
        Update the triangle plot display.
        
        Returns:
            None
        """
        try:
            
            self.figure.clear()
            
            plot_data = self.triangle_node.extract_plot_data()
            
            if not plot_data:
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5, 'No particle data available\nConnect to Sample Selector\nSelect 3 elements for triangle plot', 
                        ha='center', va='center', transform=ax.transAxes,
                        fontsize=12, color='gray')
                ax.set_xticks([])
                ax.set_yticks([])
            else:
                config = self.triangle_node.config
                
                self.update_statistics(plot_data)
                
                if self.is_multiple_sample_data():
                    self.create_multiple_sample_triangle_plots(plot_data, config)
                else:
                    self.create_triangle_plot(plot_data, config)
            
            self.figure.tight_layout()
            
            self.canvas.draw()
            
        except Exception as e:
            print(f"Error updating triangle display: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def create_multiple_sample_triangle_plots(self, plot_data, config):
        """
        Create triangle plots for multiple samples.
        
        Args:
            plot_data (dict): Dictionary of sample data by sample name
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        display_mode = config.get('display_mode', 'Individual Subplots')
        sample_names = list(plot_data.keys())
        
        if display_mode == 'Individual Subplots':
            self.create_subplot_triangle_plots(plot_data, config)
        elif display_mode == 'Side by Side Subplots':
            self.create_side_by_side_triangle_plots(plot_data, config)
        elif display_mode == 'Combined Plot':
            self.create_combined_triangle_plot(plot_data, config)
        else:
            self.create_overlaid_triangle_plots(plot_data, config)
    
    def create_subplot_triangle_plots(self, plot_data, config):
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
        
        cols = min(2, n_samples)
        rows = math.ceil(n_samples / cols)
        
        for i, sample_name in enumerate(sample_names):
            ax = self.figure.add_subplot(rows, cols, i + 1, projection='ternary')
            
            sample_data = plot_data[sample_name]
            if sample_data:
                display_name = self.get_display_name(sample_name)
                self.create_sample_triangle_plot(ax, sample_data, config, display_name)
                self.apply_font_to_axes(ax, config)
    
    def create_side_by_side_triangle_plots(self, plot_data, config):
        """
        Create side-by-side triangle plots.
        
        Args:
            plot_data (dict): Dictionary of sample data by sample name
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_names = list(plot_data.keys())
        n_samples = len(sample_names)
        
        for i, sample_name in enumerate(sample_names):
            ax = self.figure.add_subplot(1, n_samples, i + 1, projection='ternary')
            
            sample_data = plot_data[sample_name]
            if sample_data:
                display_name = self.get_display_name(sample_name)
                self.create_sample_triangle_plot(ax, sample_data, config, display_name)
                self.apply_font_to_axes(ax, config)
    
    def create_combined_triangle_plot(self, plot_data, config):
        """
        Create a single triangle plot combining all samples.
        
        Args:
            plot_data (dict): Dictionary of sample data by sample name
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        ax = self.figure.add_subplot(111, projection='ternary')
        
        combined_data = []
        for sample_name, sample_data in plot_data.items():
            combined_data.extend(sample_data)
        
        if combined_data:
            self.create_sample_triangle_plot(ax, combined_data, config, f"Combined ({len(plot_data)} samples)")
            self.apply_font_to_axes(ax, config)
    
    def create_overlaid_triangle_plots(self, plot_data, config):
        """
        Create overlaid triangle plots with different colors per sample.
        
        Args:
            plot_data (dict): Dictionary of sample data by sample name
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        ax = self.figure.add_subplot(111, projection='ternary')
        
        element_a = config.get('element_a', 'Element A')
        element_b = config.get('element_b', 'Element B')
        element_c = config.get('element_c', 'Element C')
        element_labels = [element_a, element_b, element_c]
        
        font_props = self.create_font_properties(config)
        
        TernaryPlotHelper.create_ternary_axes(ax, element_labels, config.get('show_grid', True), font_props)
        
        sample_colors = config.get('sample_colors', {})
        default_colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
        
        for i, (sample_name, sample_data) in enumerate(plot_data.items()):
            if sample_data:
                color = sample_colors.get(sample_name, default_colors[i % len(default_colors)])
                
                display_name = self.get_display_name(sample_name)
                self.calculate_and_plot_average(ax, sample_data, config, display_name)

                b_vals = [point['b'] for point in sample_data]
                c_vals = [point['c'] for point in sample_data]
                a_vals = [point['a'] for point in sample_data]
                
                ax.scatter(b_vals, c_vals, a_vals,
                          s=config.get('marker_size', 20),
                          alpha=config.get('marker_alpha', 0.7),
                          color=color,
                          label=display_name,
                          edgecolors='white',
                          linewidth=0.5)
        
        legend = ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        
        self.apply_font_to_axes(ax, config)
    
    def create_sample_triangle_plot(self, ax, sample_data, config, sample_name):
        """
        Create triangle plot for a single sample using mpltern with hexbin support.
        
        Args:
            ax: Matplotlib axes object with ternary projection
            sample_data (list): List of sample data points
            config (dict): Configuration dictionary
            sample_name (str): Name of the sample
        
        Returns:
            None
        """
        if not sample_data:
            return
        
        element_a = config.get('element_a', 'Element A')
        element_b = config.get('element_b', 'Element B') 
        element_c = config.get('element_c', 'Element C')
        element_labels = [element_a, element_b, element_c]
        
        font_props = self.create_font_properties(config)
        
        TernaryPlotHelper.create_ternary_axes(ax, element_labels, config.get('show_grid', True), font_props)
        
        b_vals = [point['b'] for point in sample_data]
        c_vals = [point['c'] for point in sample_data]
        a_vals = [point['a'] for point in sample_data]
        
        if not b_vals:
            return
        
        plot_type = config.get('plot_type', 'Scatter Plot')
        show_colorbar = config.get('show_colorbar', True)
        
        if plot_type == 'Scatter Plot':
            scatter = ax.scatter(b_vals, c_vals, a_vals,
                            s=config.get('marker_size', 20),
                            alpha=config.get('marker_alpha', 0.7),
                            c=range(len(b_vals)),
                            cmap=config.get('colormap', 'YlGn'),
                            edgecolors='white',
                            linewidth=0.5)
            
            if show_colorbar:
                cbar = self.figure.colorbar(scatter, ax=ax, shrink=0.8, aspect=20)
                colorbar_label = config.get('colorbar_label', 'Point Index')
                cbar.set_label(colorbar_label)
                self.apply_font_to_colorbar(cbar, config)
                
        else:
            hexbin = ax.hexbin(b_vals, c_vals, a_vals,
                            gridsize=config.get('hexbin_gridsize', 30),
                            cmap=config.get('colormap', 'YlGn'),
                            alpha=config.get('hexbin_alpha', 0.8),
                            mincnt=1)
            
            if show_colorbar:
                cbar = self.figure.colorbar(hexbin, ax=ax, shrink=0.8, aspect=20)
                colorbar_label = config.get('colorbar_label', 'Density')
                cbar.set_label(colorbar_label)
                self.apply_font_to_colorbar(cbar, config)
        
        self.calculate_and_plot_average(ax, sample_data, config, sample_name)
        
    def update_statistics(self, plot_data):
        """
        Update the statistics display.
        
        Args:
            plot_data: Plot data (dict for multiple samples, list for single sample)
        
        Returns:
            None
        """
        if self.is_multiple_sample_data():
            total_particles = 0
            total_with_all_elements = 0
            
            for sample_data in plot_data.values():
                total_particles += len(sample_data)
                if self.triangle_node.config.get('average_only_with_all_elements', True):
                    filtered_data = self.filter_particles_with_all_elements(sample_data, self.triangle_node.config)
                    total_with_all_elements += len(filtered_data)
            
            sample_count = len(plot_data)
            stats_text = f"{sample_count} samples\n"
            stats_text += f"{total_particles} particles plotted"
            
            if self.triangle_node.config.get('average_only_with_all_elements', True) and total_with_all_elements < total_particles:
                stats_text += f"\n{total_with_all_elements} particles with all 3 elements"
                
        else:
            total_particles = len(plot_data)
            stats_text = f"{total_particles} particles plotted"
            
            if self.triangle_node.config.get('average_only_with_all_elements', True):
                filtered_data = self.filter_particles_with_all_elements(plot_data, self.triangle_node.config)
                particles_with_all = len(filtered_data)
                if particles_with_all < total_particles:
                    stats_text += f"\n{particles_with_all} particles with all 3 elements"
        
        self.stats_label.setText(stats_text)
        
    def create_triangle_plot(self, plot_data, config):
        """
        Create the triangle visualization for single sample.
        
        Args:
            plot_data (list): List of data points
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        ax = self.figure.add_subplot(111, projection='ternary')
        self.create_sample_triangle_plot(ax, plot_data, config, "Trenary Plot")
        self.apply_font_to_axes(ax, config)


class TrianglePlotNode(QObject):
    """
    Enhanced Triangle plot node with multiple sample support and custom sample names.
    """
    
    position_changed = Signal(object)
    configuration_changed = Signal()
    
    def __init__(self, parent_window=None):
        """
        Initialize triangle plot node.
        
        Args:
            parent_window: Parent window widget
        """
        super().__init__()
        self.title = "Trenary Plot"
        self.node_type = "triangle_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.config = {
            'custom_title': 'Trernary Plot',
            'element_a': '-- Select Element A --',
            'element_b': '-- Select Element B --',
            'element_c': '-- Select Element C --',
            'data_type_display': 'Counts (%)',
            'plot_type': 'Scatter Plot',
            'marker_size': 20,
            'marker_alpha': 0.7,
            'hexbin_gridsize': 30,
            'hexbin_alpha': 0.8,
            'show_grid': True,
            'colormap': 'YlGn',
            'show_colorbar': True,
            'colorbar_label': 'Density',
            'min_total': 0.0,
            'max_particles': 100000000,
            'display_mode': 'Individual Subplots',
            'sample_colors': {},
            'sample_name_mappings': {},  
            'show_average_point': True,
            'average_point_color': '#FF0000', 
            'average_only_with_all_elements': True,
            'average_point_size': 100,
            'show_average_text': True,
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
        dialog = TriangleDisplayDialog(self, parent_window)
        dialog.exec()
        return True
        
    def process_data(self, input_data):
        """
        Process input data and update triangle plot.
        
        Args:
            input_data (dict): Input data dictionary
        
        Returns:
            None
        """
        if not input_data:
            print("No input data received for triangle plot")
            return
            
        print(f"Triangle plot received data: {input_data.get('type', 'unknown')}")
        self.input_data = input_data
        
        self.configuration_changed.emit()
        

    def extract_plot_data(self):
        """
        Extract triangle plot data from input with percentage calculation.
        
        Returns:
            dict or list or None: Extracted plot data
        """
        if not self.input_data:
            return None
            
        element_a = self.config.get('element_a', '-- Select Element A --')
        element_b = self.config.get('element_b', '-- Select Element B --')
        element_c = self.config.get('element_c', '-- Select Element C --')
        
        if (element_a.startswith('--') or element_b.startswith('--') or element_c.startswith('--')):
            return None
        
        data_type_display = self.config.get('data_type_display', 'Counts (%)')
        input_type = self.input_data.get('type')
        
        data_key_mapping = {
            'Counts (%)': 'elements',
            'Element Mass (%)': 'element_mass_fg',
            'Particle Mass (%)': 'particle_mass_fg',
            'Element Moles (%)': 'element_moles_fmol',
            'Particle Moles (%)': 'particle_moles_fmol'
        }
        
        data_key = data_key_mapping.get(data_type_display, 'elements')
        
        if input_type == 'sample_data':
            return self._extract_single_sample_triangle(data_key, element_a, element_b, element_c)
        elif input_type == 'multiple_sample_data':
            return self._extract_multiple_sample_triangle(data_key, element_a, element_b, element_c)
            
        return None
    
    def _extract_single_sample_triangle(self, data_key, element_a, element_b, element_c):
        """
        Extract triangle data for single sample with percentage calculation.
        
        Args:
            data_key (str): Key for data type in particle dictionary
            element_a (str): First element name
            element_b (str): Second element name
            element_c (str): Third element name
        
        Returns:
            list or None: List of triangle data points
        """
        particles = self.input_data.get('particle_data')
        
        if not particles:
            return None
        
        try:
            triangle_data = []
            min_total = self.config.get('min_total', 0.0)
            max_particles = self.config.get('max_particles', 10000000)
            
            particle_count = 0
            for particle in particles:
                if particle_count >= max_particles:
                    break
                    
                particle_data_dict = particle.get(data_key, {})
                
                val_a = particle_data_dict.get(element_a, 0)
                val_b = particle_data_dict.get(element_b, 0)
                val_c = particle_data_dict.get(element_c, 0)
                
                if data_key == 'elements':
                    if val_a <= 0 or val_b <= 0 or val_c <= 0:
                        continue
                else:
                    if (np.isnan(val_a) or np.isnan(val_b) or np.isnan(val_c) or
                        val_a < 0 or val_b < 0 or val_c < 0):
                        continue
                
                total = val_a + val_b + val_c
                if total < min_total:
                    continue
                
                if total > 0:
                    triangle_data.append({
                        'a': val_a / total,
                        'b': val_b / total,
                        'c': val_c / total,
                        'total': total,
                        'a_percent': (val_a / total) * 100,
                        'b_percent': (val_b / total) * 100,
                        'c_percent': (val_c / total) * 100
                    })
                    particle_count += 1
            
            return triangle_data
            
        except Exception as e:
            print(f"Error in _extract_single_sample_triangle: {str(e)}")
            return None

    def _extract_multiple_sample_triangle(self, data_key, element_a, element_b, element_c):
        """
        Extract triangle data for multiple samples with percentage calculation.
        
        Args:
            data_key (str): Key for data type in particle dictionary
            element_a (str): First element name
            element_b (str): Second element name
            element_c (str): Third element name
        
        Returns:
            dict or None: Dictionary of triangle data by sample name
        """
        particles = self.input_data.get('particle_data', [])
        sample_names = self.input_data.get('sample_names', [])
        
        if not particles:
            return None
        
        try:
            sample_triangle_data = {}
            min_total = self.config.get('min_total', 0.0)
            max_particles = self.config.get('max_particles', 10000000)
            
            for sample_name in sample_names:
                sample_triangle_data[sample_name] = []
            
            sample_particle_counts = {name: 0 for name in sample_names}
            
            for particle in particles:
                source_sample = particle.get('source_sample')
                if source_sample and source_sample in sample_triangle_data:
                    
                    if sample_particle_counts[source_sample] >= max_particles:
                        continue
                        
                    particle_data_dict = particle.get(data_key, {})
                    
                    val_a = particle_data_dict.get(element_a, 0)
                    val_b = particle_data_dict.get(element_b, 0)
                    val_c = particle_data_dict.get(element_c, 0)
                    
                    if data_key == 'elements':
                        if val_a <= 0 or val_b <= 0 or val_c <= 0:
                            continue
                    else:
                        if (np.isnan(val_a) or np.isnan(val_b) or np.isnan(val_c) or
                            val_a < 0 or val_b < 0 or val_c < 0):
                            continue
                    
                    total = val_a + val_b + val_c
                    if total < min_total:
                        continue
                    
                    if total > 0:
                        sample_triangle_data[source_sample].append({
                            'a': val_a / total,
                            'b': val_b / total,
                            'c': val_c / total,
                            'total': total,
                            'a_percent': (val_a / total) * 100,
                            'b_percent': (val_b / total) * 100,
                            'c_percent': (val_c / total) * 100
                        })
                        sample_particle_counts[source_sample] += 1
            
            sample_triangle_data = {k: v for k, v in sample_triangle_data.items() if v}
            
            return sample_triangle_data
            
        except Exception as e:
            print(f"Error in _extract_multiple_sample_triangle: {str(e)}")
            return None