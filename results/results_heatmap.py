from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                              QLabel, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                              QDialogButtonBox, QGroupBox, QColorDialog, QPushButton,
                              QLineEdit, QGraphicsProxyWidget, QFrame, QScrollArea, QWidget, QListWidgetItem, QListWidget, QMessageBox)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import math
import re
from results.utils_sort import (
    extract_mass_and_element,
    sort_elements_by_mass,
    format_element_label,
    format_combination_label,
    sort_element_dict_by_mass
)

from widget.colors import colorheatmap


class HeatmapDisplayDialog(QDialog):
    """
    Enhanced dialog for heatmap visualization with multiple sample support and font settings.
    """
    
    def __init__(self, heatmap_node, parent_window=None):
        """
        Initialize the heatmap display dialog.
        
        Args:
            heatmap_node: Heatmap node instance
            parent_window: Parent window widget
        """
        super().__init__(parent_window)
        self.heatmap_node = heatmap_node
        self.parent_window = parent_window
        
        self.setWindowTitle("Element Combination Heatmap - Multi-Sample Analysis")
        self.setMinimumSize(1600, 900)
        
        self.setup_ui()
        self.update_display()
        
        self.heatmap_node.configuration_changed.connect(self.update_display)
    
    def is_multiple_sample_data(self):
        """
        Check if dealing with multiple sample data.
        
        Returns:
            bool: True if multiple sample data, False otherwise
        """
        return (hasattr(self.heatmap_node, 'input_data') and 
                self.heatmap_node.input_data and 
                self.heatmap_node.input_data.get('type') == 'multiple_sample_data')
    
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
        Create the heatmap configuration panel with multiple sample support and font settings.
        
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
        
        title = QLabel("Heatmap Settings")
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
                'Combined Heatmap',
                'Comparative View'
            ])
            self.display_mode_combo.setCurrentText(self.heatmap_node.config.get('display_mode', 'Individual Subplots'))
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
            'Element Mass %',
            'Particle Mass %',
            'Element Mole %',
            'Particle Mole %'
        ])
        self.data_type_combo.setCurrentText(self.heatmap_node.config.get('data_type_display', 'Counts (Raw)'))
        self.data_type_combo.currentTextChanged.connect(self.on_data_type_changed)
        data_layout.addWidget(self.data_type_combo)
        
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
        data_layout.addWidget(self.data_info_label)
        
        layout.addWidget(data_group)
        
        font_group = QGroupBox("Font Settings")
        font_layout = QFormLayout(font_group)
        
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(self.get_font_families())
        self.font_family_combo.setCurrentText(self.heatmap_node.config.get('font_family', 'Times New Roman'))
        self.font_family_combo.currentTextChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Family:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(self.heatmap_node.config.get('font_size', 12))
        self.font_size_spin.valueChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Size:", self.font_size_spin)
        
        font_style_layout = QHBoxLayout()
        self.font_bold_checkbox = QCheckBox("Bold")
        self.font_bold_checkbox.setChecked(self.heatmap_node.config.get('font_bold', False))
        self.font_bold_checkbox.stateChanged.connect(self.on_config_changed)
        self.font_italic_checkbox = QCheckBox("Italic")
        self.font_italic_checkbox.setChecked(self.heatmap_node.config.get('font_italic', False))
        self.font_italic_checkbox.stateChanged.connect(self.on_config_changed)
        font_style_layout.addWidget(self.font_bold_checkbox)
        font_style_layout.addWidget(self.font_italic_checkbox)
        font_style_layout.addStretch()
        font_layout.addRow("Font Style:", font_style_layout)
        
        self.font_color_button = QPushButton()
        self.font_color = QColor(self.heatmap_node.config.get('font_color', '#000000'))
        self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 30px;")
        self.font_color_button.clicked.connect(lambda: self.choose_color('font'))
        font_layout.addRow("Font Color:", self.font_color_button)
        
        layout.addWidget(font_group)
        
        search_group = QGroupBox("Element Search & Filter")
        search_layout = QVBoxLayout(search_group)
        
        search_input_layout = QHBoxLayout()
        search_label = QLabel("Search Elements:")
        search_input_layout.addWidget(search_label)
        
        self.search_element_edit = QLineEdit()
        self.search_element_edit.setPlaceholderText("e.g., Fe, Ti or Ti Fe (order doesn't matter)")
        self.search_element_edit.textChanged.connect(self.on_search_changed)
        search_input_layout.addWidget(self.search_element_edit)
        
        clear_search_btn = QPushButton("Clear")
        clear_search_btn.setMaximumWidth(60)
        clear_search_btn.clicked.connect(self.clear_search)
        search_input_layout.addWidget(clear_search_btn)
        
        search_layout.addLayout(search_input_layout)
        
        self.highlight_matches_checkbox = QCheckBox()
        self.highlight_matches_checkbox.setChecked(self.heatmap_node.config.get('highlight_matches', True))
        self.highlight_matches_checkbox.stateChanged.connect(self.on_config_changed)
        search_layout.addWidget(QLabel("Highlight matching combinations:"))
        search_layout.addWidget(self.highlight_matches_checkbox)
        
        self.filter_combinations_checkbox = QCheckBox()
        self.filter_combinations_checkbox.setChecked(self.heatmap_node.config.get('filter_combinations', False))
        self.filter_combinations_checkbox.stateChanged.connect(self.on_config_changed)
        search_layout.addWidget(QLabel("Show only matching combinations:"))
        search_layout.addWidget(self.filter_combinations_checkbox)
        
        self.search_results_label = QLabel("")
        self.search_results_label.setStyleSheet("color: #6B7280; font-size: 10px;")
        search_layout.addWidget(self.search_results_label)
        
        layout.addWidget(search_group)
        
        range_group = QGroupBox("Combination Range")
        range_layout = QFormLayout(range_group)
        
        self.start_spin = QSpinBox()
        self.start_spin.setRange(1, 1000)
        self.start_spin.setValue(self.heatmap_node.config.get('start_range', 1))
        self.start_spin.valueChanged.connect(self.on_config_changed)
        range_layout.addRow("Start from combination:", self.start_spin)
        
        self.end_spin = QSpinBox()
        self.end_spin.setRange(2, 1000)
        self.end_spin.setValue(self.heatmap_node.config.get('end_range', 10))
        self.end_spin.valueChanged.connect(self.on_config_changed)
        range_layout.addRow("End at combination:", self.end_spin)
        
        layout.addWidget(range_group)
        
        filter_group = QGroupBox("Filter Settings")
        filter_layout = QFormLayout(filter_group)
        
        self.filter_zeros_checkbox = QCheckBox()
        self.filter_zeros_checkbox.setChecked(self.heatmap_node.config.get('filter_zeros', True))
        self.filter_zeros_checkbox.stateChanged.connect(self.on_config_changed)
        filter_layout.addRow("Filter Zero Values:", self.filter_zeros_checkbox)
        
        self.min_particles_spin = QSpinBox()
        self.min_particles_spin.setRange(1, 1000)
        self.min_particles_spin.setValue(self.heatmap_node.config.get('min_particles', 1))
        self.min_particles_spin.valueChanged.connect(self.on_config_changed)
        filter_layout.addRow("Min Particles per Combination:", self.min_particles_spin)
        
        layout.addWidget(filter_group)
        
        label_group = QGroupBox("Label Format")
        label_layout = QFormLayout(label_group)
        
        self.show_mass_numbers_checkbox = QCheckBox()
        self.show_mass_numbers_checkbox.setChecked(self.heatmap_node.config.get('show_mass_numbers', True))
        self.show_mass_numbers_checkbox.stateChanged.connect(self.on_config_changed)
        label_layout.addRow("Show Mass Numbers (55Fe vs Fe):", self.show_mass_numbers_checkbox)
        
        layout.addWidget(label_group)
        
        colorscale_group = QGroupBox("Color Scale")
        colorscale_layout = QVBoxLayout(colorscale_group)
        
        self.colorscale_combo = QComboBox()
        colorscales = colorheatmap
        self.colorscale_combo.addItems(colorscales)
        self.colorscale_combo.setCurrentText(self.heatmap_node.config.get('colorscale', 'YlGnBu'))
        self.colorscale_combo.currentTextChanged.connect(self.on_config_changed)
        colorscale_layout.addWidget(self.colorscale_combo)
        
        layout.addWidget(colorscale_group)
        
        display_group = QGroupBox("Display Options")
        display_layout = QFormLayout(display_group)
        
        self.show_numbers_checkbox = QCheckBox()
        self.show_numbers_checkbox.setChecked(self.heatmap_node.config.get('show_numbers', True))
        self.show_numbers_checkbox.stateChanged.connect(self.on_config_changed)
        display_layout.addRow("Show Numbers:", self.show_numbers_checkbox)
        
        self.show_colorbar_checkbox = QCheckBox()
        self.show_colorbar_checkbox.setChecked(self.heatmap_node.config.get('show_colorbar', True))
        self.show_colorbar_checkbox.stateChanged.connect(self.on_config_changed)
        display_layout.addRow("Show Colorbar:", self.show_colorbar_checkbox)
        
        layout.addWidget(display_group)
        
        if self.is_multiple_sample_data():
            self.sample_colors_group = QGroupBox("Sample Colors")
            self.sample_colors_layout = QVBoxLayout(self.sample_colors_group)
            self.update_sample_color_controls()
            layout.addWidget(self.sample_colors_group)
        
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

    def apply_font_settings(self, ax):
        """
        Apply font settings to a matplotlib axis including colorbars.
        
        Args:
            ax: Matplotlib axis object
        
        Returns:
            None
        """
        try:
            font_family = self.heatmap_node.config.get('font_family', 'Times New Roman')
            font_size = self.heatmap_node.config.get('font_size', 12)
            is_bold = self.heatmap_node.config.get('font_bold', False)
            is_italic = self.heatmap_node.config.get('font_italic', False)
            font_color = self.heatmap_node.config.get('font_color', '#000000')
            
            font_weight = 'bold' if is_bold else 'normal'
            font_style = 'italic' if is_italic else 'normal'
            
            ax.tick_params(axis='both', which='major', labelsize=font_size, colors=font_color)
            
            for label in ax.get_xticklabels():
                label.set_fontfamily(font_family)
                label.set_fontweight(font_weight)
                label.set_fontstyle(font_style)
                label.set_color(font_color)
                
            for label in ax.get_yticklabels():
                label.set_fontfamily(font_family)
                label.set_fontweight(font_weight)
                label.set_fontstyle(font_style)
                label.set_color(font_color)
            
            if ax.get_title():
                ax.set_title(ax.get_title(), 
                        fontfamily=font_family, 
                        fontsize=font_size + 2,
                        fontweight=font_weight,
                        fontstyle=font_style,
                        color=font_color)
            
            for child in ax.figure.get_children():
                if hasattr(child, 'colorbar') and child.colorbar is not None:
                    cbar = child.colorbar
                    cbar.ax.tick_params(labelsize=font_size, colors=font_color)
                    for label in cbar.ax.get_yticklabels():
                        label.set_fontfamily(font_family)
                        label.set_fontweight(font_weight)
                        label.set_fontstyle(font_style)
                        label.set_color(font_color)
                    
                    if cbar.ax.get_ylabel():
                        cbar.set_label(cbar.ax.get_ylabel(),
                                    fontfamily=font_family,
                                    fontsize=font_size,
                                    fontweight=font_weight,
                                    fontstyle=font_style,
                                    color=font_color)
            
            if hasattr(ax, 'collections'):
                for collection in ax.collections:
                    if hasattr(collection, 'colorbar') and collection.colorbar is not None:
                        cbar = collection.colorbar
                        cbar.ax.tick_params(labelsize=font_size, colors=font_color)
                        for label in cbar.ax.get_yticklabels():
                            label.set_fontfamily(font_family)
                            label.set_fontweight(font_weight)
                            label.set_fontstyle(font_style)
                            label.set_color(font_color)
                        
                        if cbar.ax.get_ylabel():
                            cbar.set_label(cbar.ax.get_ylabel(),
                                        fontfamily=font_family,
                                        fontsize=font_size,
                                        fontweight=font_weight,
                                        fontstyle=font_style,
                                        color=font_color)

        except Exception as e:
            print(f"Error applying font settings: {e}")

    
    def on_data_type_changed(self):
        """
        Handle data type selection change.
        
        Returns:
            None
        """
        self.update_data_info_label()
        self.on_config_changed()
    
    def on_search_changed(self):
        """
        Handle search text change.
        
        Returns:
            None
        """
        search_text = self.search_element_edit.text().strip()
        self.heatmap_node.config['search_element'] = search_text
        self.update_search_results()
        self.on_config_changed()
    
    def clear_search(self):
        """
        Clear the search field.
        
        Returns:
            None
        """
        self.search_element_edit.clear()
        self.heatmap_node.config['search_element'] = ''
        self.update_search_results()
        self.on_config_changed()
    
    def check_combination_matches_search(self, combination, search_elements):
        """
        Check if a combination matches the search elements (order independent).
        
        Args:
            combination (str): Combination string
            search_elements (list): List of search element strings
        
        Returns:
            bool: True if combination matches search, False otherwise
        """
        if not search_elements:
            return False
        
        combo_elements = [elem.strip() for elem in combination.split(',')]
        
        for search_elem in search_elements:
            found = False
            for combo_elem in combo_elements:
                combo_no_mass = format_element_label(combo_elem, False)
                search_no_mass = format_element_label(search_elem, False)
                
                if (search_elem.lower() in combo_elem.lower() or 
                    search_no_mass.lower() in combo_no_mass.lower()):
                    found = True
                    break
            if not found:
                return False
        
        return True
    
    def update_search_results(self):
        """
        Update search results information.
        
        Returns:
            None
        """
        search_text = self.search_element_edit.text().strip()
        if not search_text:
            self.search_results_label.setText("")
            return
        
        search_elements = []
        for elem in search_text.replace(',', ' ').split():
            if elem.strip():
                search_elements.append(elem.strip())
        
        if not search_elements:
            self.search_results_label.setText("")
            return
        
        combinations_data = self.heatmap_node.extract_combinations_data()
        if not combinations_data:
            self.search_results_label.setText("No data available")
            return
        
        matching_combinations = []
        
        if self.is_multiple_sample_data():
            for sample_name, sample_data in combinations_data.items():
                for combination, data in sample_data.items():
                    if self.check_combination_matches_search(combination, search_elements):
                        matching_combinations.append(f"{sample_name}: {combination}")
        else:
            for combination, data in combinations_data.items():
                if self.check_combination_matches_search(combination, search_elements):
                    matching_combinations.append(combination)
        
        if matching_combinations:
            search_display = ", ".join(search_elements)
            self.search_results_label.setText(f"Found {len(matching_combinations)} combinations with '{search_display}'")
        else:
            search_display = ", ".join(search_elements)
            self.search_results_label.setText(f"No combinations containing '{search_display}' found")
    
    def update_sample_color_controls(self):
        """
        Update color controls for multiple samples.
        
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
        
        sample_colors = self.heatmap_node.config.get('sample_colors', {})
        
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
        
        self.heatmap_node.config['sample_colors'] = sample_colors
        
    def get_available_sample_names(self):
        """
        Get available sample names from input data.
        
        Returns:
            list: List of sample names
        """
        if self.is_multiple_sample_data():
            return self.heatmap_node.input_data.get('sample_names', [])
        return []
    
    def select_sample_color(self, sample_name, button):
        """
        Open color dialog for sample.
        
        Args:
            sample_name (str): Name of the sample
            button (QPushButton): Button widget to update
        
        Returns:
            None
        """
        current_color = self.heatmap_node.config.get('sample_colors', {}).get(sample_name, '#3B82F6')
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {sample_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'sample_colors' not in self.heatmap_node.config:
                self.heatmap_node.config['sample_colors'] = {}
            self.heatmap_node.config['sample_colors'][sample_name] = color_hex
            
            self.on_config_changed()
    
    def update_data_info_label(self):
        """
        Update the data availability info label.
        
        Returns:
            None
        """
        if not self.heatmap_node.input_data:
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
        Download the current figure.
        
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Heatmap Plot",
            "heatmap_plot.png",
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;JPEG Files (*.jpg);;All Files (*)"
        )
        
        if file_path:
            try:
                self.figure.savefig(file_path, dpi=300, bbox_inches='tight', 
                                facecolor='white', edgecolor='none')
                QMessageBox.information(self, "✅ Success", 
                                    f"Heatmap saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", 
                                f"Failed to save:\n{str(e)}")
    
    def create_plot_panel(self):
        """
        Create the expandable plot panel.
        
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
        if hasattr(self, 'end_spin') and hasattr(self, 'start_spin'):
            if self.end_spin.value() <= self.start_spin.value():
                self.end_spin.setValue(self.start_spin.value() + 1)
        
        config_updates = {
            'data_type_display': self.data_type_combo.currentText(),
            'search_element': self.search_element_edit.text().strip(),
            'highlight_matches': self.highlight_matches_checkbox.isChecked(),
            'filter_combinations': self.filter_combinations_checkbox.isChecked(),
            'start_range': self.start_spin.value(),
            'end_range': self.end_spin.value(),
            'filter_zeros': self.filter_zeros_checkbox.isChecked(),
            'min_particles': self.min_particles_spin.value(),
            'show_mass_numbers': self.show_mass_numbers_checkbox.isChecked(),
            'colorscale': self.colorscale_combo.currentText(),
            'show_numbers': self.show_numbers_checkbox.isChecked(),
            'show_colorbar': self.show_colorbar_checkbox.isChecked(),
            'font_family': self.font_family_combo.currentText(),
            'font_size': self.font_size_spin.value(),
            'font_bold': self.font_bold_checkbox.isChecked(),
            'font_italic': self.font_italic_checkbox.isChecked(),
            'font_color': self.font_color.name()
        }
        
        if self.is_multiple_sample_data():
            config_updates.update({
                'display_mode': self.display_mode_combo.currentText()
            })
        
        self.heatmap_node.config.update(config_updates)
        self.update_display()

    def update_display(self):
        """
        Update the heatmap display with multiple sample support.
        
        Returns:
            None
        """
        try:
            self.update_data_info_label()
            
            self.figure.clear()
            
            combinations_data = self.heatmap_node.extract_combinations_data()
            
            if not combinations_data:
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5, 'No particle data available\nConnect to Sample Selector\nRun particle detection first', 
                        ha='center', va='center', transform=ax.transAxes,
                        fontsize=12, color='gray')
                ax.set_xticks([])
                ax.set_yticks([])
                self.apply_font_settings(ax)
            else:
                config = self.heatmap_node.config
                
                self.update_statistics(combinations_data)
                self.update_search_results()
                
                if self.is_multiple_sample_data():
                    self.create_multiple_sample_heatmaps(combinations_data, config)
                else:
                    self.create_heatmap(combinations_data, config)
            
            self.figure.tight_layout()
            
            self.canvas.draw()
            
        except Exception as e:
            print(f"Error updating heatmap display: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def create_multiple_sample_heatmaps(self, combinations_data, config):
        """
        Create heatmaps for multiple samples with different display modes.
        
        Args:
            combinations_data (dict): Dictionary of combination data by sample
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        display_mode = config.get('display_mode', 'Individual Subplots')
        sample_names = list(combinations_data.keys())
        
        if display_mode == 'Individual Subplots':
            self.create_subplot_heatmaps(combinations_data, config)
        elif display_mode == 'Side by Side Subplots':
            self.create_side_by_side_heatmaps(combinations_data, config)
        elif display_mode == 'Combined Heatmap':
            self.create_combined_heatmap(combinations_data, config)
        else:
            self.create_comparative_heatmaps(combinations_data, config)
    
    def create_subplot_heatmaps(self, combinations_data, config):
        """
        Create individual subplots for each sample.
        
        Args:
            combinations_data (dict): Dictionary of combination data by sample
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_names = list(combinations_data.keys())
        n_samples = len(sample_names)
        
        cols = min(2, n_samples)
        rows = math.ceil(n_samples / cols)
        
        for i, sample_name in enumerate(sample_names):
            ax = self.figure.add_subplot(rows, cols, i + 1)
            
            sample_data = combinations_data[sample_name]
            if sample_data:
                self.create_sample_specific_heatmap(ax, sample_data, config, sample_name)
                self.apply_font_settings(ax)
    
    def create_side_by_side_heatmaps(self, combinations_data, config):
        """
        Create side-by-side heatmaps.
        
        Args:
            combinations_data (dict): Dictionary of combination data by sample
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_names = list(combinations_data.keys())
        n_samples = len(sample_names)
        
        for i, sample_name in enumerate(sample_names):
            ax = self.figure.add_subplot(1, n_samples, i + 1)
            
            sample_data = combinations_data[sample_name]
            if sample_data:
                self.create_sample_specific_heatmap(ax, sample_data, config, sample_name)
                self.apply_font_settings(ax)
    
    def create_combined_heatmap(self, combinations_data, config):
        """
        Create a single heatmap combining all samples.
        
        Args:
            combinations_data (dict): Dictionary of combination data by sample
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        ax = self.figure.add_subplot(111)
        
        combined_data = {}
        for sample_name, sample_data in combinations_data.items():
            for combination, data in sample_data.items():
                if combination not in combined_data:
                    combined_data[combination] = {
                        'count': 0,
                        'total_values': {},
                        'particle_count': 0
                    }
                
                combined_data[combination]['count'] += data['count']
                combined_data[combination]['particle_count'] += data['particle_count']
                
                for element, values in data['total_values'].items():
                    if element not in combined_data[combination]['total_values']:
                        combined_data[combination]['total_values'][element] = []
                    combined_data[combination]['total_values'][element].extend(values)
        
        if combined_data:
            self.create_sample_specific_heatmap(ax, combined_data, config, f"Combined ({len(combinations_data)} samples)")
            self.apply_font_settings(ax)
    
    def create_comparative_heatmaps(self, combinations_data, config):
        """
        Create comparative view showing differences between samples.
        
        Args:
            combinations_data (dict): Dictionary of combination data by sample
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_names = list(combinations_data.keys())
        
        if len(sample_names) >= 2:
            ax1 = self.figure.add_subplot(121)
            ax2 = self.figure.add_subplot(122)
            
            for ax, sample_name in zip([ax1, ax2], sample_names[:2]):
                sample_data = combinations_data[sample_name]
                if sample_data:
                    self.create_sample_specific_heatmap(ax, sample_data, config, sample_name)
                    self.apply_font_settings(ax)
    
    def create_sample_specific_heatmap(self, ax, sample_data, config, sample_name):
        """
        Create heatmap with Y-axis ordered by particle count, X-axis and labels ordered by mass.
        
        Args:
            ax: Matplotlib axis object
            sample_data (dict): Sample combination data
            config (dict): Configuration dictionary
            sample_name (str): Name of the sample
        
        Returns:
            None
        """
        if not sample_data:
            return
        
        data_type_display = config.get('data_type_display', 'Counts (Raw)')
        search_text = config.get('search_element', '').strip()
        highlight_matches = config.get('highlight_matches', True)
        filter_combinations = config.get('filter_combinations', False)
        start_range = config.get('start_range', 1)
        end_range = config.get('end_range', 10)
        min_particles = config.get('min_particles', 1)
        show_mass_numbers = config.get('show_mass_numbers', True)
        colorscale = config.get('colorscale', 'YlGnBu')
        show_numbers = config.get('show_numbers', True)
        show_colorbar = config.get('show_colorbar', True)
        
        search_elements = []
        if search_text:
            for elem in search_text.replace(',', ' ').split():
                if elem.strip():
                    search_elements.append(elem.strip())
        
        sorted_combinations = sorted(sample_data.items(), 
                                key=lambda x: x[1]['particle_count'], reverse=True)
        
        if search_elements and filter_combinations:
            sorted_combinations = [(combo, data) for combo, data in sorted_combinations 
                                if self.check_combination_matches_search(combo, search_elements)]
        
        sorted_combinations = [(combo, data) for combo, data in sorted_combinations 
                            if data['particle_count'] >= min_particles]
        
        end_range = min(end_range, len(sorted_combinations))
        start_range = max(1, min(start_range, end_range))
        
        if end_range <= start_range:
            end_range = start_range + 1
        
        selected_combinations = sorted_combinations[start_range-1:end_range]
        
        if not selected_combinations:
            ax.text(0.5, 0.5, 'No combinations match\ncurrent filters', 
                    ha='center', va='center', transform=ax.transAxes,
                    fontsize=12, color='gray')
            return
        
        all_elements = set()
        for _, data in selected_combinations:
            all_elements.update(data['total_values'].keys())
        all_elements = sort_elements_by_mass(list(all_elements))
        
        combination_labels = []
        data_matrix = []
        highlight_rows = []
        
        for combination, data in selected_combinations:
            count = data['particle_count']
            
            formatted_combo = format_combination_label(combination, show_mass_numbers)
            combination_labels.append(f"{formatted_combo} ({count})")
            
            is_highlighted = False
            if search_elements and self.check_combination_matches_search(combination, search_elements):
                is_highlighted = True
            highlight_rows.append(is_highlighted)
            
            row = []
            
            if data_type_display in ['Element Mass %', 'Particle Mass %', 'Element Mole %', 'Particle Mole %']:
                if data_type_display in ['Element Mass %', 'Particle Mass %']:
                    total_for_percentage = 0
                    for element in data['total_values']:
                        values = data['total_values'][element]
                        if values:
                            total_for_percentage += np.sum(values)
                elif data_type_display in ['Element Mole %', 'Particle Mole %']:
                    total_for_percentage = 0
                    for element in data['total_values']:
                        values = data['total_values'][element]
                        if values:
                            total_for_percentage += np.sum(values)
            
            for element in all_elements:
                if element in data['total_values']:
                    values = data['total_values'][element]
                    
                    if values:
                        if data_type_display == 'Counts (Raw)':
                            value = np.mean(values)
                        elif data_type_display == 'Element Mass (fg)':
                            value = np.mean(values)
                        elif data_type_display == 'Particle Mass (fg)':
                            value = np.mean(values)
                        elif data_type_display == 'Element Moles (fmol)':
                            value = np.mean(values)
                        elif data_type_display == 'Particle Moles (fmol)':
                            value = np.mean(values)
                        elif data_type_display == 'Element Mass %':
                            element_total = np.sum(values)
                            if total_for_percentage > 0:
                                value = (element_total / total_for_percentage) * 100
                            else:
                                value = 0
                        elif data_type_display == 'Particle Mass %':
                            element_total = np.sum(values)
                            if total_for_percentage > 0:
                                value = (element_total / total_for_percentage) * 100
                            else:
                                value = 0
                        elif data_type_display == 'Element Mole %':
                            element_total = np.sum(values)
                            if total_for_percentage > 0:
                                value = (element_total / total_for_percentage) * 100
                            else:
                                value = 0
                        elif data_type_display == 'Particle Mole %':
                            element_total = np.sum(values)
                            if total_for_percentage > 0:
                                value = (element_total / total_for_percentage) * 100
                            else:
                                value = 0
                        else:
                            value = np.mean(values)
                    else:
                        value = 0
                else:
                    value = 0
                
                row.append(value)
            data_matrix.append(row)
        
        data_matrix = np.array(data_matrix)
        
        data_matrix = np.nan_to_num(data_matrix, nan=0.0)
        
        im = ax.imshow(data_matrix, cmap=colorscale, aspect='auto', interpolation='nearest')
        
        formatted_x_labels = [format_element_label(elem, show_mass_numbers) for elem in all_elements]
        ax.set_xticks(range(len(formatted_x_labels)))
        ax.set_xticklabels(formatted_x_labels, rotation=0, ha='right', fontsize=10, fontweight='bold')
        
        ax.set_yticks(range(len(combination_labels)))
        ax.set_yticklabels(combination_labels, fontsize=10, fontweight='bold')
        
        if search_elements and highlight_matches:
            for i, is_highlighted in enumerate(highlight_rows):
                if is_highlighted:
                    ax.axhline(y=i+0.35, color='black', linewidth=2, alpha=0.9, 
                            xmin=-0.15, xmax=0, clip_on=False)
                    ax.get_yticklabels()[i].set_weight('bold')
        
        if self.is_multiple_sample_data():
            title = sample_name
            if search_elements:
                matching_count = sum(highlight_rows)
                search_display = ", ".join(search_elements)
                title += f" (Search: '{search_display}' - {matching_count} matches)"
            ax.set_title(title, fontsize=12, fontweight='bold', pad=20)
        
        colorbar_ref = None
        if show_colorbar:
            colorbar_ref = self.figure.colorbar(im, ax=ax, shrink=0.8)
            
            font_family = config.get('font_family', 'Times New Roman')
            font_size = config.get('font_size', 12)
            is_bold = config.get('font_bold', False)
            is_italic = config.get('font_italic', False)
            font_color = config.get('font_color', '#000000')
            
            font_weight = 'bold' if is_bold else 'normal'
            font_style = 'italic' if is_italic else 'normal'
            
            colorbar_ref.set_label(data_type_display,
                                fontfamily=font_family,
                                fontsize=font_size,
                                fontweight=font_weight,
                                fontstyle=font_style,
                                color=font_color)
            
            colorbar_ref.ax.tick_params(labelsize=font_size, colors=font_color)
            for label in colorbar_ref.ax.get_yticklabels():
                label.set_fontfamily(font_family)
                label.set_fontweight(font_weight)
                label.set_fontstyle(font_style)
                label.set_color(font_color)
        
        if show_numbers and data_matrix.size < 1000: 
            for i in range(len(combination_labels)):
                for j in range(len(all_elements)):
                    value = data_matrix[i, j]
                    if value > 0:
                        text_color = 'white' if value > np.max(data_matrix) * 0.5 else 'black'
                        
                        if data_type_display in ['Element Mass %', 'Particle Mass %', 'Element Mole %', 'Particle Mole %']:
                            text = f'{value:.1f}%'
                        elif value >= 1000:
                            text = f'{value:.0f}'
                        elif value >= 1:
                            text = f'{value:.1f}'
                        else:
                            text = f'{value:.2f}'
                        
                        font_family = config.get('font_family', 'Times New Roman')
                        cell_font_size = config.get('font_size', 12)
                        font_weight = 'bold' if config.get('font_bold', False) else 'normal'
                        
                        ax.text(j, i, text, ha='center', va='center', 
                            color=text_color, 
                            fontsize=cell_font_size, 
                            fontfamily=font_family,
                            weight=font_weight)
            
    def update_statistics(self, combinations_data):
        """
        Update the statistics display.
        
        Args:
            combinations_data (dict): Dictionary of combination data
        
        Returns:
            None
        """
        if self.is_multiple_sample_data():
            total_combinations = 0
            total_particles = 0
            all_elements = set()
            
            for sample_data in combinations_data.values():
                total_combinations += len(sample_data)
                for data in sample_data.values():
                    total_particles += data['particle_count']
                    all_elements.update(data['total_values'].keys())
            
            sample_count = len(combinations_data)
            stats_text = f"{sample_count} samples\n"
            stats_text += f"{total_combinations} total combinations\n"
            stats_text += f"{total_particles} total particles\n"
            stats_text += f"{len(all_elements)} elements detected"
        else:
            total_combinations = len(combinations_data)
            total_particles = sum(data['particle_count'] for data in combinations_data.values())
            
            all_elements = set()
            for data in combinations_data.values():
                all_elements.update(data['total_values'].keys())
            
            stats_text = f"{total_combinations} combinations\n"
            stats_text += f"{total_particles} total particles\n"
            stats_text += f"{len(all_elements)} elements detected"
        
        self.stats_label.setText(stats_text)
    
    def create_heatmap(self, combinations_data, config):
        """
        Create the heatmap visualization (single sample).
        
        Args:
            combinations_data (dict): Combination data dictionary
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        ax = self.figure.add_subplot(111)
        self.create_sample_specific_heatmap(ax, combinations_data, config, "Element Combinations")
        self.apply_font_settings(ax)


class HeatmapPlotNode(QObject):
    """
    Enhanced heatmap plot node with multiple sample support and font settings.
    """
    
    position_changed = Signal(object)
    configuration_changed = Signal()
    
    def __init__(self, parent_window=None):
        """
        Initialize heatmap plot node.
        
        Args:
            parent_window: Parent window widget
        """
        super().__init__()
        self.title = "Element Heatmap"
        self.node_type = "heatmap_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.config = {
            'data_type_display': 'Counts (Raw)',
            'search_element': '',
            'highlight_matches': True,
            'filter_combinations': False,
            'start_range': 1,
            'end_range': 10,
            'filter_zeros': True,
            'min_particles': 1,
            'show_mass_numbers': True,
            'colorscale': 'YlGnBu',
            'show_numbers': True,
            'show_colorbar': True,
            'display_mode': 'Individual Subplots',
            'sample_colors': {},
            'font_family': 'Times New Roman',
            'font_size': 12,
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
        dialog = HeatmapDisplayDialog(self, parent_window)
        dialog.exec()
        return True
        
    def process_data(self, input_data):
        """
        Process input data and update heatmap.
        
        Args:
            input_data (dict): Input data dictionary
        
        Returns:
            None
        """
        if not input_data:
            print("No input data received for heatmap")
            return
            
        print(f"Heatmap received data: {input_data.get('type', 'unknown')}")
        self.input_data = input_data

        self.configuration_changed.emit()
        
    def extract_combinations_data(self):
        """
        Extract element combinations data from input.
        
        Returns:
            dict or None: Extracted combinations data
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
            'Element Mass %': 'element_mass_fg',
            'Particle Mass %': 'particle_mass_fg',
            'Element Mole %': 'element_moles_fmol',
            'Particle Mole %': 'particle_moles_fmol'
        }
        
        data_key = data_key_mapping.get(data_type_display, 'elements')
        
        if input_type == 'sample_data':
            return self._extract_single_sample_combinations(data_key)
        elif input_type == 'multiple_sample_data':
            return self._extract_multiple_sample_combinations(data_key)
            
        return None
    
    def _extract_single_sample_combinations(self, data_key):
        """
        Extract combinations data for single sample.
        
        Args:
            data_key (str): Key for data type in particle dictionary
        
        Returns:
            dict or None: Dictionary of combination data
        """
        particles = self.input_data.get('particle_data')
        
        if not particles:
            print(f"No filtered particle data available from sample selector")
            return None
        
        try:
            combinations = {}
            filter_zeros = self.config.get('filter_zeros', True)
            
            for particle in particles:
                particle_data_dict = particle.get(data_key, {})
                elements_in_particle = []
                element_values = {}
                
                for element_name, value in particle_data_dict.items():
                    if data_key == 'elements':
                        if value > 0:
                            elements_in_particle.append(element_name)
                            element_values[element_name] = value
                    else:
                        if value > 0 and not np.isnan(value):
                            elements_in_particle.append(element_name)
                            element_values[element_name] = value
                
                if elements_in_particle:
                    sorted_elements = sort_elements_by_mass(elements_in_particle)
                    combination_key = ', '.join(sorted_elements)
                    
                    if combination_key not in combinations:
                        combinations[combination_key] = {
                            'count': 0,
                            'particle_count': 0,
                            'total_values': {}
                        }
                    
                    combinations[combination_key]['count'] += 1
                    combinations[combination_key]['particle_count'] += 1
                    
                    for element, value in element_values.items():
                        if element not in combinations[combination_key]['total_values']:
                            combinations[combination_key]['total_values'][element] = []
                        
                        combinations[combination_key]['total_values'][element].append(value)
            
            return combinations
            
        except Exception as e:
            print(f"Error in _extract_single_sample_combinations: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_multiple_sample_combinations(self, data_key):
        """
        Extract combinations data for multiple samples.
        
        Args:
            data_key (str): Key for data type in particle dictionary
        
        Returns:
            dict or None: Dictionary of sample combination data
        """
        particles = self.input_data.get('particle_data', [])
        sample_names = self.input_data.get('sample_names', [])
        
        if not particles:
            print("No filtered particle data available from sample selector")
            return None
        
        try:
            sample_combinations = {}
            filter_zeros = self.config.get('filter_zeros', True)
            
            for sample_name in sample_names:
                sample_combinations[sample_name] = {}
            
            for particle in particles:
                source_sample = particle.get('source_sample')
                if source_sample and source_sample in sample_combinations:
                    
                    particle_data_dict = particle.get(data_key, {})
                    elements_in_particle = []
                    element_values = {}
                    
                    for element_name, value in particle_data_dict.items():
                        if data_key == 'elements':
                            if value > 0:
                                elements_in_particle.append(element_name)
                                element_values[element_name] = value
                        else:
                            if value > 0 and not np.isnan(value):
                                elements_in_particle.append(element_name)
                                element_values[element_name] = value
                    
                    if elements_in_particle:
                        sorted_elements = sort_elements_by_mass(elements_in_particle)
                        combination_key = ', '.join(sorted_elements)
                        
                        if combination_key not in sample_combinations[source_sample]:
                            sample_combinations[source_sample][combination_key] = {
                                'count': 0,
                                'particle_count': 0,
                                'total_values': {}
                            }
                        
                        sample_combinations[source_sample][combination_key]['count'] += 1
                        sample_combinations[source_sample][combination_key]['particle_count'] += 1
                        
                        for element, value in element_values.items():
                            if element not in sample_combinations[source_sample][combination_key]['total_values']:
                                sample_combinations[source_sample][combination_key]['total_values'][element] = []
                            
                            sample_combinations[source_sample][combination_key]['total_values'][element].append(value)
            
            sample_combinations = {k: v for k, v in sample_combinations.items() if v}
            
            return sample_combinations
            
        except Exception as e:
            print(f"Error in _extract_multiple_sample_combinations: {str(e)}")
            import traceback
            traceback.print_exc()
            return None