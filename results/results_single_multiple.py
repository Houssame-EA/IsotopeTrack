from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                              QLabel, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                              QDialogButtonBox, QGroupBox, QColorDialog, QPushButton,
                              QLineEdit, QGraphicsProxyWidget, QFrame, QScrollArea, QWidget, 
                              QListWidgetItem, QListWidget, QMessageBox, QSlider, QTabWidget,
                              QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd
from collections import defaultdict
import math
from widget.colors import default_colors, colorheatmap


class SingleMultipleElementHelper:
    """
    Helper class for single vs multiple element analysis.
    """
    
    @staticmethod
    def analyze_particles(particle_data, percentage_threshold_single=0.5, percentage_threshold_multiple=0.5):
        """
        Analyze particles to determine single vs multiple element combinations.
        
        Args:
            particle_data (list): List of particle data dictionaries
            percentage_threshold_single (float): Threshold percentage for single elements
            percentage_threshold_multiple (float): Threshold percentage for multiple elements
        
        Returns:
            dict: Dictionary with combination statistics or None
        """
        if not particle_data:
            return None
        
        combination_data = defaultdict(list)
        
        for i, particle in enumerate(particle_data):
            elements_dict = particle.get('elements', {})
            elements_with_counts = [elem for elem, count in elements_dict.items() if count > 0]
            
            if elements_with_counts:
                combination_key = ', '.join(sorted(elements_with_counts))
                combination_data[combination_key].append(i)
        
        combinations = {}
        for combination_key, indices in combination_data.items():
            count = len(indices)
            combinations[combination_key] = {
                'count': count,
                'indices': indices,
                'is_single': len(combination_key.split(', ')) == 1
            }
        
        sorted_combinations = sorted(combinations.items(), key=lambda x: x[1]['count'], reverse=True)
        total_particles = len(particle_data)
        
        filtered_single = []
        filtered_multiple = []
        
        for combination, details in sorted_combinations:
            percentage = (details['count'] / total_particles) * 100
            
            if details['is_single']:
                if percentage >= percentage_threshold_single:
                    filtered_single.append((combination, details, percentage))
            else:
                if percentage >= percentage_threshold_multiple:
                    filtered_multiple.append((combination, details, percentage))
        
        return {
            'single_combinations': filtered_single,
            'multiple_combinations': filtered_multiple,
            'total_particles': total_particles,
            'all_combinations': sorted_combinations
        }
    
    @staticmethod
    def calculate_particles_per_ml(particle_count, parent_window, dilution_factor=1.0, sample_info=None):
        """
        Calculate particles/mL using transport rate, time, and dilution factor.
        
        Args:
            particle_count (int): Number of particles
            parent_window: Parent window with transport rate data
            dilution_factor (float): Dilution factor to apply
            sample_info (dict): Sample information including sum status
        
        Returns:
            float: Particles per mL or original particle count
        """
        if not parent_window:
            return particle_count
            
        try:
            transport_rate = getattr(parent_window, 'average_transport_rate', None)
            
            if sample_info and sample_info.get('is_summed', False):
                total_time = 0
                original_samples = sample_info.get('original_samples', [])
                
                for sample_name in original_samples:
                    if hasattr(parent_window, 'sample_time_data'):
                        sample_time_data = parent_window.sample_time_data.get(sample_name)
                        if sample_time_data and len(sample_time_data) > 0:
                            sample_time = sample_time_data[-1] - sample_time_data[0]
                            total_time += sample_time
                    elif hasattr(parent_window, 'time_array'):
                        time_array = parent_window.time_array
                        if time_array and len(time_array) > 0:
                            total_time += time_array[-1] - time_array[0]
            else:
                time_array = getattr(parent_window, 'time_array', None)
                if time_array is not None and len(time_array) > 0:
                    total_time = time_array[-1] - time_array[0]
                else:
                    total_time = 0
            
            if transport_rate and transport_rate > 0 and total_time > 0:
                volume_ml = (transport_rate * total_time) / 1000
                particles_per_ml = particle_count / volume_ml if volume_ml > 0 else 0
                particles_per_ml_corrected = particles_per_ml * dilution_factor
                return particles_per_ml_corrected
            else:
                return particle_count
        except:
            return particle_count
    
    @staticmethod
    def create_pie_chart_data(analysis_results, combination_type='single', custom_colors=None, 
                            use_particles_per_ml=False, parent_window=None, dilution_factor=1.0, sample_info=None):
        """
        Create data for pie charts with custom colors and particles/mL option.
        
        Args:
            analysis_results (dict): Analysis results dictionary
            combination_type (str): Type of combination ('single' or 'multiple')
            custom_colors (dict): Custom color dictionary
            use_particles_per_ml (bool): Whether to use particles/mL units
            parent_window: Parent window with transport rate data
            dilution_factor (float): Dilution factor
            sample_info (dict): Sample information
        
        Returns:
            dict: Pie chart data dictionary or None
        """
        if combination_type == 'single':
            combinations = analysis_results['single_combinations']
        else:
            combinations = analysis_results['multiple_combinations']
        
        if not combinations:
            return None
        
        labels = []
        values = []
        colors = []
        
        if combination_type == 'single':
            color_palette = default_colors
        else:
            color_palette = list(reversed(default_colors))
        
        for i, (combination, details, percentage) in enumerate(combinations):
            particle_count = details['count']
            
            if use_particles_per_ml:
                display_value = SingleMultipleElementHelper.calculate_particles_per_ml(
                    particle_count, parent_window, dilution_factor, sample_info
                )
                unit = "Particles/mL"
            else:
                display_value = particle_count
                unit = "Particles"
            
            clean_combination = SingleMultipleElementHelper.format_element_labels_without_mass(combination)
            
            labels.append(f"{clean_combination}\n({display_value:.0f} {unit})")
            values.append(display_value)
            
            if custom_colors and combination in custom_colors:
                colors.append(custom_colors[combination])
            else:
                colors.append(color_palette[i % len(color_palette)])
        
        return {
            'labels': labels,
            'values': values,
            'colors': colors,
            'combinations': [comb for comb, _, _ in combinations]
        }
    
    @staticmethod
    def format_element_labels_without_mass(combination_string):
        """
        Remove mass numbers from element labels in combination string.
        
        Args:
            combination_string (str): Combination string with mass numbers
        
        Returns:
            str: Cleaned combination string without mass numbers
        """
        import re
        
        elements = [elem.strip() for elem in combination_string.split(',')]
        
        cleaned_elements = []
        for element in elements:
            cleaned = re.sub(r'^\d+', '', element)
            cleaned_elements.append(cleaned)
        
        return ', '.join(cleaned_elements)
    
    @staticmethod
    def create_heatmap_data(analysis_results_dict, use_particles_per_ml=False, parent_window=None, dilution_factor=1.0):
        """
        Create heatmap data for multiple samples with particles/mL option.
        
        Args:
            analysis_results_dict (dict): Dictionary mapping sample names to analysis results
            use_particles_per_ml (bool): Whether to use particles/mL units
            parent_window: Parent window with transport rate data
            dilution_factor (float): Dilution factor
        
        Returns:
            dict: Heatmap data dictionary or None
        """
        if not analysis_results_dict:
            return None
        
        all_single_elements = set()
        all_multiple_combinations = set()
        
        for sample_results in analysis_results_dict.values():
            for combination, details, percentage in sample_results['single_combinations']:
                clean_combination = SingleMultipleElementHelper.format_element_labels_without_mass(combination)
                all_single_elements.add(clean_combination)
            for combination, details, percentage in sample_results['multiple_combinations']:
                clean_combination = SingleMultipleElementHelper.format_element_labels_without_mass(combination)
                all_multiple_combinations.add(clean_combination)
        
        sample_names = list(analysis_results_dict.keys())
        
        single_df_particles = pd.DataFrame(index=sorted(all_single_elements), columns=sample_names)
        single_df_particles = single_df_particles.fillna(0)
        single_df_percentage = pd.DataFrame(index=sorted(all_single_elements), columns=sample_names)
        single_df_percentage = single_df_percentage.fillna(0)
        
        top_multiple = sorted(all_multiple_combinations, 
                            key=lambda x: sum(
                                next((details['count'] for comb, details, _ in sample_results['multiple_combinations'] 
                                     if SingleMultipleElementHelper.format_element_labels_without_mass(comb) == x), 0)
                                for sample_results in analysis_results_dict.values()
                            ), reverse=True)[:30]
        
        multiple_df_particles = pd.DataFrame(index=top_multiple, columns=sample_names)
        multiple_df_particles = multiple_df_particles.fillna(0)
        multiple_df_percentage = pd.DataFrame(index=top_multiple, columns=sample_names)
        multiple_df_percentage = multiple_df_percentage.fillna(0)
        
        for sample_name, sample_results in analysis_results_dict.items():
            sample_info = {'is_summed': False}
            if hasattr(parent_window, 'sample_config') and sample_name in getattr(parent_window, 'sample_config', {}):
                config = parent_window.sample_config[sample_name]
                if config.get('sum_group'):
                    sample_info = {
                        'is_summed': True,
                        'original_samples': [sample_name]
                    }
            
            for combination, details, percentage in sample_results['single_combinations']:
                clean_combination = SingleMultipleElementHelper.format_element_labels_without_mass(combination)
                if clean_combination in single_df_particles.index:
                    if use_particles_per_ml:
                        value = SingleMultipleElementHelper.calculate_particles_per_ml(
                            details['count'], parent_window, dilution_factor, sample_info
                        )
                    else:
                        value = details['count']
                    
                    single_df_particles.loc[clean_combination, sample_name] = value
                    single_df_percentage.loc[clean_combination, sample_name] = percentage
            
            for combination, details, percentage in sample_results['multiple_combinations']:
                clean_combination = SingleMultipleElementHelper.format_element_labels_without_mass(combination)
                if clean_combination in multiple_df_particles.index:
                    if use_particles_per_ml:
                        value = SingleMultipleElementHelper.calculate_particles_per_ml(
                            details['count'], parent_window, dilution_factor, sample_info
                        )
                    else:
                        value = details['count']
                    
                    multiple_df_particles.loc[clean_combination, sample_name] = value
                    multiple_df_percentage.loc[clean_combination, sample_name] = percentage
        
        return {
            'single_particles': single_df_particles,
            'single_percentage': single_df_percentage,
            'multiple_particles': multiple_df_particles,
            'multiple_percentage': multiple_df_percentage
        }
    
    @staticmethod
    def create_statistics_table(analysis_data, is_multiple_sample=False, use_particles_per_ml=False, 
                              parent_window=None, dilution_factor=1.0):
        """
        Create comprehensive statistics table with particles/mL option.
        
        Args:
            analysis_data (dict): Analysis data dictionary
            is_multiple_sample (bool): Whether dealing with multiple samples
            use_particles_per_ml (bool): Whether to use particles/mL units
            parent_window: Parent window with transport rate data
            dilution_factor (float): Dilution factor
        
        Returns:
            pd.DataFrame: Statistics table DataFrame
        """
        if is_multiple_sample:
            table_data = []
            
            for sample_name, sample_results in analysis_data.items():
                total_particles = sample_results['total_particles']
                single_combos = sample_results['single_combinations']
                multiple_combos = sample_results['multiple_combinations']
                
                sample_info = {'is_summed': False}
                if hasattr(parent_window, 'sample_config') and sample_name in getattr(parent_window, 'sample_config', {}):
                    config = parent_window.sample_config[sample_name]
                    if config.get('sum_group'):
                        sample_info = {
                            'is_summed': True,
                            'original_samples': [sample_name]
                        }
                
                single_count = sum(details['count'] for _, details, _ in single_combos)
                multiple_count = sum(details['count'] for _, details, _ in multiple_combos)
                single_percentage = (single_count / total_particles * 100) if total_particles > 0 else 0
                multiple_percentage = (multiple_count / total_particles * 100) if total_particles > 0 else 0
                
                if use_particles_per_ml:
                    total_display = SingleMultipleElementHelper.calculate_particles_per_ml(total_particles, parent_window, dilution_factor, sample_info)
                    single_display = SingleMultipleElementHelper.calculate_particles_per_ml(single_count, parent_window, dilution_factor, sample_info)
                    multiple_display = SingleMultipleElementHelper.calculate_particles_per_ml(multiple_count, parent_window, dilution_factor, sample_info)
                    unit = 'Particles/mL'
                else:
                    total_display = total_particles
                    single_display = single_count
                    multiple_display = multiple_count
                    unit = 'Particles'
                
                table_data.append([
                    sample_name, 'SUMMARY', 'Total Particles', f'{total_display:.1f}', '100.0%', f'All {unit}'
                ])
                table_data.append([
                    sample_name, 'SUMMARY', 'Single Element Total', f'{single_display:.1f}', f'{single_percentage:.1f}%', f'sNPs {unit}'
                ])
                table_data.append([
                    sample_name, 'SUMMARY', 'Multiple Element Total', f'{multiple_display:.1f}', f'{multiple_percentage:.1f}%', f'mNPs {unit}'
                ])
                
                for combination, details, percentage in single_combos:
                    if use_particles_per_ml:
                        display_value = SingleMultipleElementHelper.calculate_particles_per_ml(details['count'], parent_window, dilution_factor, sample_info)
                    else:
                        display_value = details['count']
                    
                    clean_combination = SingleMultipleElementHelper.format_element_labels_without_mass(combination)
                    
                    table_data.append([
                        sample_name, 'SINGLE', clean_combination, f'{display_value:.1f}', f'{percentage:.1f}%', f'sNP {unit}'
                    ])
                
                for combination, details, percentage in multiple_combos:
                    element_count = len(combination.split(', '))
                    if use_particles_per_ml:
                        display_value = SingleMultipleElementHelper.calculate_particles_per_ml(details['count'], parent_window, dilution_factor, sample_info)
                    else:
                        display_value = details['count']
                    
                    clean_combination = SingleMultipleElementHelper.format_element_labels_without_mass(combination)
                    
                    table_data.append([
                        sample_name, 'MULTIPLE', clean_combination, f'{display_value:.1f}', f'{percentage:.1f}%', f'mNP ({element_count} elements) {unit}'
                    ])
            
            columns = ['Sample', 'Type', 'Combination', 'Count', 'Percentage', 'Description']
        else:
            table_data = []
            total_particles = analysis_data['total_particles']
            single_combos = analysis_data['single_combinations']
            multiple_combos = analysis_data['multiple_combinations']
            
            single_count = sum(details['count'] for _, details, _ in single_combos)
            multiple_count = sum(details['count'] for _, details, _ in multiple_combos)
            single_percentage = (single_count / total_particles * 100) if total_particles > 0 else 0
            multiple_percentage = (multiple_count / total_particles * 100) if total_particles > 0 else 0
            
            sample_info = {'is_summed': False}
            
            if use_particles_per_ml:
                total_display = SingleMultipleElementHelper.calculate_particles_per_ml(total_particles, parent_window, dilution_factor, sample_info)
                single_display = SingleMultipleElementHelper.calculate_particles_per_ml(single_count, parent_window, dilution_factor, sample_info)
                multiple_display = SingleMultipleElementHelper.calculate_particles_per_ml(multiple_count, parent_window, dilution_factor, sample_info)
                unit = 'Particles/mL'
            else:
                total_display = total_particles
                single_display = single_count
                multiple_display = multiple_count
                unit = 'Particles'
            
            table_data.append(['SUMMARY', 'Total Particles', f'{total_display:.1f}', '100.0%', f'All {unit}'])
            table_data.append(['SUMMARY', 'Single Element Total', f'{single_display:.1f}', f'{single_percentage:.1f}%', f'sNPs {unit}'])
            table_data.append(['SUMMARY', 'Multiple Element Total', f'{multiple_display:.1f}', f'{multiple_percentage:.1f}%', f'mNPs {unit}'])
            
            for combination, details, percentage in single_combos:
                if use_particles_per_ml:
                    display_value = SingleMultipleElementHelper.calculate_particles_per_ml(details['count'], parent_window, dilution_factor, sample_info)
                else:
                    display_value = details['count']
                
                clean_combination = SingleMultipleElementHelper.format_element_labels_without_mass(combination)
                
                table_data.append(['SINGLE', clean_combination, f'{display_value:.1f}', f'{percentage:.1f}%', f'sNP {unit}'])
            
            for combination, details, percentage in multiple_combos:
                element_count = len(combination.split(', '))
                if use_particles_per_ml:
                    display_value = SingleMultipleElementHelper.calculate_particles_per_ml(details['count'], parent_window, dilution_factor, sample_info)
                else:
                    display_value = details['count']
                
                clean_combination = SingleMultipleElementHelper.format_element_labels_without_mass(combination)
                
                table_data.append(['MULTIPLE', clean_combination, f'{display_value:.1f}', f'{percentage:.1f}%', f'mNP ({element_count} elements) {unit}'])
            
            columns = ['Type', 'Combination', 'Count', 'Percentage', 'Description']
        
        return pd.DataFrame(table_data, columns=columns)


class SingleMultipleElementDisplayDialog(QDialog):
    """
    Dialog for single vs multiple element analysis visualization.
    """
    
    def __init__(self, element_node, parent_window=None):
        """
        Initialize the display dialog.
        
        Args:
            element_node: Element node instance
            parent_window: Parent window widget
        """
        super().__init__(parent_window)
        self.element_node = element_node
        self.parent_window = parent_window
        
        self.setWindowTitle("Single vs Multiple Element Analysis")
        self.setMinimumSize(1800, 1000)
        
        self.setup_ui()
        self.update_display()
        
        self.element_node.configuration_changed.connect(self.update_display)
    
    def is_multiple_sample_data(self):
        """
        Check if dealing with multiple sample data.
        
        Returns:
            bool: True if multiple sample data, False otherwise
        """
        return (hasattr(self.element_node, 'input_data') and 
                self.element_node.input_data and 
                self.element_node.input_data.get('type') == 'multiple_sample_data')
    
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
        Create the configuration panel.
        
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
        
        title = QLabel("Single vs Multiple Element Analysis")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #1F2937;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(title)
        
        viz_group = QGroupBox("Visualization Type")
        viz_layout = QFormLayout(viz_group)
        
        self.visualization_type_combo = QComboBox()
        self.visualization_type_combo.addItems(['Pie Charts', 'Heatmaps'])
        self.visualization_type_combo.setCurrentText(self.element_node.config.get('visualization_type', 'Pie Charts'))
        self.visualization_type_combo.currentTextChanged.connect(self.on_visualization_type_changed)
        viz_layout.addRow("Type:", self.visualization_type_combo)
        
        layout.addWidget(viz_group)
        
        units_group = QGroupBox("Units & Dilution")
        units_layout = QFormLayout(units_group)
        
        self.use_particles_per_ml_checkbox = QCheckBox()
        self.use_particles_per_ml_checkbox.setChecked(self.element_node.config.get('use_particles_per_ml', False))
        self.use_particles_per_ml_checkbox.stateChanged.connect(self.on_units_changed)
        units_layout.addRow("Use Particles/mL:", self.use_particles_per_ml_checkbox)
        
        self.dilution_factor_spin = QDoubleSpinBox()
        self.dilution_factor_spin.setRange(0.001, 100000.0)
        self.dilution_factor_spin.setDecimals(3)
        self.dilution_factor_spin.setValue(self.element_node.config.get('dilution_factor', 1.0))
        self.dilution_factor_spin.valueChanged.connect(self.on_config_changed)
        units_layout.addRow("Dilution Factor:", self.dilution_factor_spin)
        
        layout.addWidget(units_group)
        
        if self.is_multiple_sample_data():
            multiple_group = QGroupBox("Multiple Sample Display")
            multiple_layout = QFormLayout(multiple_group)
            
            self.display_mode_combo = QComboBox()
            self.display_mode_combo.addItems([
                'Individual Subplots', 
                'Side by Side Subplots',
                'Combined View'
            ])
            self.display_mode_combo.setCurrentText(self.element_node.config.get('display_mode', 'Individual Subplots'))
            self.display_mode_combo.currentTextChanged.connect(self.on_config_changed)
            multiple_layout.addRow("Display Mode:", self.display_mode_combo)
            
            layout.addWidget(multiple_group)
        
        threshold_group = QGroupBox("Threshold Settings")
        threshold_layout = QFormLayout(threshold_group)
        
        self.single_threshold_spin = QDoubleSpinBox()
        self.single_threshold_spin.setRange(0.00, 10.00)
        self.single_threshold_spin.setDecimals(2)
        self.single_threshold_spin.setSuffix('%')
        self.single_threshold_spin.setValue(self.element_node.config.get('single_threshold', 0.5))
        self.single_threshold_spin.valueChanged.connect(self.on_config_changed)
        threshold_layout.addRow("Single Elements Threshold:", self.single_threshold_spin)
        
        self.multiple_threshold_spin = QDoubleSpinBox()
        self.multiple_threshold_spin.setRange(0.00, 10.00)
        self.multiple_threshold_spin.setDecimals(2)
        self.multiple_threshold_spin.setSuffix('%')
        self.multiple_threshold_spin.setValue(self.element_node.config.get('multiple_threshold', 0.5))
        self.multiple_threshold_spin.valueChanged.connect(self.on_config_changed)
        threshold_layout.addRow("Multiple Elements Threshold:", self.multiple_threshold_spin)
        
        layout.addWidget(threshold_group)
        
        self.pie_settings_group = QGroupBox("Pie Chart Settings")
        pie_layout = QFormLayout(self.pie_settings_group)
        
        self.show_percentages_checkbox = QCheckBox()
        self.show_percentages_checkbox.setChecked(self.element_node.config.get('show_percentages', True))
        self.show_percentages_checkbox.stateChanged.connect(self.on_config_changed)
        pie_layout.addRow("Show Percentages:", self.show_percentages_checkbox)
        
        self.explode_slices_checkbox = QCheckBox()
        self.explode_slices_checkbox.setChecked(self.element_node.config.get('explode_slices', False))
        self.explode_slices_checkbox.stateChanged.connect(self.on_config_changed)
        pie_layout.addRow("Explode Slices:", self.explode_slices_checkbox)
        
        self.label_color_button = QPushButton()
        self.label_color = QColor(self.element_node.config.get('label_color', '#000000'))
        self.label_color_button.setStyleSheet(f"background-color: {self.label_color.name()}; min-height: 30px;")
        self.label_color_button.clicked.connect(self.choose_label_color)
        pie_layout.addRow("Label Color:", self.label_color_button)
        
        layout.addWidget(self.pie_settings_group)
        
        self.pie_color_group = QGroupBox("Pie Chart Colors")
        self.pie_color_layout = QVBoxLayout(self.pie_color_group)
        self.update_pie_color_controls()
        layout.addWidget(self.pie_color_group)
        
        self.heatmap_settings_group = QGroupBox("Heatmap Settings")
        heatmap_layout = QFormLayout(self.heatmap_settings_group)
        
        self.use_log_scale_checkbox = QCheckBox()
        self.use_log_scale_checkbox.setChecked(self.element_node.config.get('use_log_scale', True))
        self.use_log_scale_checkbox.stateChanged.connect(self.on_config_changed)
        heatmap_layout.addRow("Use Log Scale:", self.use_log_scale_checkbox)
        
        self.show_values_checkbox = QCheckBox()
        self.show_values_checkbox.setChecked(self.element_node.config.get('show_values', True))
        self.show_values_checkbox.stateChanged.connect(self.on_config_changed)
        heatmap_layout.addRow("Show Percentages on Cells:", self.show_values_checkbox)
        
        self.colormap_combo = QComboBox()
        colormaps = colorheatmap
        self.colormap_combo.addItems(colormaps)
        self.colormap_combo.setCurrentText(self.element_node.config.get('colormap', 'YlGn'))
        self.colormap_combo.currentTextChanged.connect(self.on_config_changed)
        heatmap_layout.addRow("Colormap:", self.colormap_combo)
        
        layout.addWidget(self.heatmap_settings_group)
        
        font_group = QGroupBox("Font Settings")
        font_layout = QFormLayout(font_group)
        
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(self.get_font_families())
        self.font_family_combo.setCurrentText(self.element_node.config.get('font_family', 'Times New Roman'))
        self.font_family_combo.currentTextChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Family:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(self.element_node.config.get('font_size', 12))
        self.font_size_spin.valueChanged.connect(self.on_config_changed)
        font_layout.addRow("Font Size:", self.font_size_spin)
        
        font_style_layout = QHBoxLayout()
        self.font_bold_checkbox = QCheckBox("Bold")
        self.font_bold_checkbox.setChecked(self.element_node.config.get('font_bold', False))
        self.font_bold_checkbox.stateChanged.connect(self.on_config_changed)
        self.font_italic_checkbox = QCheckBox("Italic")
        self.font_italic_checkbox.setChecked(self.element_node.config.get('font_italic', False))
        self.font_italic_checkbox.stateChanged.connect(self.on_config_changed)
        font_style_layout.addWidget(self.font_bold_checkbox)
        font_style_layout.addWidget(self.font_italic_checkbox)
        font_style_layout.addStretch()
        font_layout.addRow("Font Style:", font_style_layout)
        
        self.font_color_button = QPushButton()
        self.font_color = QColor(self.element_node.config.get('font_color', '#000000'))
        self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 30px;")
        self.font_color_button.clicked.connect(self.choose_font_color)
        font_layout.addRow("Font Color:", self.font_color_button)
        
        layout.addWidget(font_group)
        
        if self.is_multiple_sample_data():
            self.sample_colors_group = QGroupBox("Sample Colors & Names")
            self.sample_colors_layout = QVBoxLayout(self.sample_colors_group)
            self.update_sample_color_controls()
            layout.addWidget(self.sample_colors_group)
        
        self.stats_group = QGroupBox("Data Statistics")
        stats_layout = QVBoxLayout(self.stats_group)
        
        self.stats_label = QLabel("Connect data to see statistics")
        self.stats_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(self.stats_group)
        
        self.update_visualization_type_controls()
        
        button_layout = QHBoxLayout()
        
        download_button = QPushButton("Download Figure")
        download_button.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
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
        
        download_table_button = QPushButton("Download Statistics Table")
        download_table_button.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
        """)
        download_table_button.clicked.connect(self.download_statistics_table)
        button_layout.addWidget(download_table_button)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        return scroll
    
    def on_units_changed(self):
        """
        Handle units change - show/hide dilution factor.
        
        Returns:
            None
        """
        use_particles_per_ml = self.use_particles_per_ml_checkbox.isChecked()
        self.dilution_factor_spin.setEnabled(use_particles_per_ml)
        self.on_config_changed()
    
    def update_pie_color_controls(self):
        """
        Update pie chart color controls.
        
        Returns:
            None
        """
        for i in reversed(range(self.pie_color_layout.count())):
            self.pie_color_layout.itemAt(i).widget().deleteLater()
        
        analysis_data = self.element_node.extract_analysis_data()
        if not analysis_data:
            return
        
        all_combinations = set()
        if self.is_multiple_sample_data():
            for sample_results in analysis_data.values():
                for combination, _, _ in sample_results['single_combinations']:
                    all_combinations.add(('single', combination))
                for combination, _, _ in sample_results['multiple_combinations']:
                    all_combinations.add(('multiple', combination))
        else:
            for combination, _, _ in analysis_data['single_combinations']:
                all_combinations.add(('single', combination))
            for combination, _, _ in analysis_data['multiple_combinations']:
                all_combinations.add(('multiple', combination))
        
        if not all_combinations:
            return
        
        single_colors = self.element_node.config.get('single_pie_colors', {})
        multiple_colors = self.element_node.config.get('multiple_pie_colors', {})
        
        single_combos = [combo for combo_type, combo in all_combinations if combo_type == 'single']
        multiple_combos = [combo for combo_type, combo in all_combinations if combo_type == 'multiple']
        
        if single_combos:
            single_label = QLabel("Single Element Colors:")
            single_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            self.pie_color_layout.addWidget(single_label)
            
            for combo in sorted(single_combos):
                self.create_pie_color_control(combo, 'single', single_colors)
        
        if multiple_combos:
            multiple_label = QLabel("Multiple Element Colors:")
            multiple_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            self.pie_color_layout.addWidget(multiple_label)
            
            for combo in sorted(multiple_combos):
                self.create_pie_color_control(combo, 'multiple', multiple_colors)
    
    def create_pie_color_control(self, combination, combo_type, color_dict):
        """
        Create a color control for a specific combination.
        
        Args:
            combination (str): Combination string
            combo_type (str): Type of combination ('single' or 'multiple')
            color_dict (dict): Color dictionary
        
        Returns:
            None
        """
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 2, 0, 2)
        
        clean_combination = SingleMultipleElementHelper.format_element_labels_without_mass(combination)
        display_text = clean_combination[:20] + "..." if len(clean_combination) > 20 else clean_combination
        
        label = QLabel(display_text)
        label.setFixedWidth(150)
        layout.addWidget(label)
        
        color_button = QPushButton()
        color_button.setFixedSize(30, 20)
        
        if combo_type == 'single':
            color_palette = default_colors
        else:
            color_palette = list(reversed(default_colors))
        
        if combination in color_dict:
            color = color_dict[combination]
        else:
            color = color_palette[len(color_dict) % len(color_palette)]
            color_dict[combination] = color
        
        color_button.setStyleSheet(f"background-color: {color}; border: 1px solid black;")
        color_button.clicked.connect(
            lambda checked, c=combination, t=combo_type, btn=color_button: self.select_pie_color(c, t, btn)
        )
        layout.addWidget(color_button)
        layout.addStretch()
        
        self.pie_color_layout.addWidget(container)
    
    def select_pie_color(self, combination, combo_type, button):
        """
        Select color for pie chart element.
        
        Args:
            combination (str): Combination string
            combo_type (str): Type of combination
            button (QPushButton): Color button widget
        
        Returns:
            None
        """
        current_colors = self.element_node.config.get(f'{combo_type}_pie_colors', {})
        current_color = current_colors.get(combination, '#3B82F6')
        
        clean_combination = SingleMultipleElementHelper.format_element_labels_without_mass(combination)
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {clean_combination}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if f'{combo_type}_pie_colors' not in self.element_node.config:
                self.element_node.config[f'{combo_type}_pie_colors'] = {}
            self.element_node.config[f'{combo_type}_pie_colors'][combination] = color_hex
            
            self.on_config_changed()
    
    def on_visualization_type_changed(self):
        """
        Handle visualization type change.
        
        Returns:
            None
        """
        self.update_visualization_type_controls()
        self.on_config_changed()
    
    def update_visualization_type_controls(self):
        """
        Show/hide controls based on visualization type.
        
        Returns:
            None
        """
        viz_type = self.visualization_type_combo.currentText()
        
        if viz_type == 'Pie Charts':
            self.pie_settings_group.setVisible(True)
            self.pie_color_group.setVisible(True)
            self.heatmap_settings_group.setVisible(False)
            self.stats_group.setVisible(True)
        elif viz_type == 'Heatmaps':
            self.pie_settings_group.setVisible(False)
            self.pie_color_group.setVisible(False)
            self.heatmap_settings_group.setVisible(True)
            self.stats_group.setVisible(True)
    
    def choose_font_color(self):
        """
        Open color dialog for font color.
        
        Returns:
            None
        """
        color = QColorDialog.getColor(self.font_color, self, "Select Font Color")
        if color.isValid():
            self.font_color = color
            self.font_color_button.setStyleSheet(f"background-color: {color.name()}; min-height: 30px;")
            self.on_config_changed()
    
    def choose_label_color(self):
        """
        Open color dialog for label color.
        
        Returns:
            None
        """
        color = QColorDialog.getColor(self.label_color, self, "Select Label Color")
        if color.isValid():
            self.label_color = color
            self.label_color_button.setStyleSheet(f"background-color: {color.name()}; min-height: 30px;")
            self.on_config_changed()
    
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
        
        color_palette = default_colors
        
        sample_colors = self.element_node.config.get('sample_colors', {})
        sample_name_mappings = self.element_node.config.get('sample_name_mappings', {})
        
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
                color = color_palette[i % len(color_palette)]
                sample_colors[original_sample_name] = color
            
            color_button.setStyleSheet(f"background-color: {color}; border: 1px solid black;")
            color_button.clicked.connect(
                lambda checked, sample=original_sample_name, btn=color_button: self.select_sample_color(sample, btn)
            )
            sample_layout.addWidget(color_button)
            
            sample_layout.addStretch()
            
            container = QWidget()
            container.setLayout(sample_layout)
            self.sample_colors_layout.addWidget(container)
        
        self.element_node.config['sample_colors'] = sample_colors
        self.element_node.config['sample_name_mappings'] = sample_name_mappings
    
    def on_sample_name_changed(self, original_name, new_name):
        """
        Handle sample name change.
        
        Args:
            original_name (str): Original sample name
            new_name (str): New display name
        
        Returns:
            None
        """
        if 'sample_name_mappings' not in self.element_node.config:
            self.element_node.config['sample_name_mappings'] = {}
        
        self.element_node.config['sample_name_mappings'][original_name] = new_name
        self.on_config_changed()
    
    def get_available_sample_names(self):
        """
        Get available sample names from input data.
        
        Returns:
            list: List of sample names
        """
        if self.is_multiple_sample_data():
            return self.element_node.input_data.get('sample_names', [])
        return []
    
    def get_display_name(self, original_name):
        """
        Get display name for a sample.
        
        Args:
            original_name (str): Original sample name
        
        Returns:
            str: Display name for the sample
        """
        mappings = self.element_node.config.get('sample_name_mappings', {})
        return mappings.get(original_name, original_name)
    
    def select_sample_color(self, sample_name, button):
        """
        Open color dialog for sample.
        
        Args:
            sample_name (str): Name of the sample
            button (QPushButton): Button widget to update
        
        Returns:
            None
        """
        current_color = self.element_node.config.get('sample_colors', {}).get(sample_name, '#3B82F6')
        display_name = self.get_display_name(sample_name)
        color = QColorDialog.getColor(QColor(current_color), self, f"Select Color for {display_name}")
        
        if color.isValid():
            color_hex = color.name()
            button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
            
            if 'sample_colors' not in self.element_node.config:
                self.element_node.config['sample_colors'] = {}
            self.element_node.config['sample_colors'][sample_name] = color_hex
            
            self.on_config_changed()
    
    def create_plot_panel(self):
        """
        Create the plot panel.
        
        Returns:
            QFrame: Frame widget containing plot tabs
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
        
        self.plot_tabs = QTabWidget()
        
        self.figure = Figure(figsize=(16, 10), dpi=100, tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.plot_tabs.addTab(self.canvas, "Visualization")
        
        self.stats_table = QTableWidget()
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.plot_tabs.addTab(self.stats_table, "Statistics Table")
        
        layout.addWidget(self.plot_tabs)
        
        return panel
    
    def on_config_changed(self):
        """
        Handle configuration changes.
        
        Returns:
            None
        """
        config_updates = {
            'visualization_type': self.visualization_type_combo.currentText(),
            'use_particles_per_ml': self.use_particles_per_ml_checkbox.isChecked(),
            'dilution_factor': self.dilution_factor_spin.value(),
            'single_threshold': self.single_threshold_spin.value(),
            'multiple_threshold': self.multiple_threshold_spin.value(),
            'show_percentages': self.show_percentages_checkbox.isChecked(),
            'explode_slices': self.explode_slices_checkbox.isChecked(),
            'label_color': self.label_color.name(),
            'use_log_scale': self.use_log_scale_checkbox.isChecked(),
            'show_values': self.show_values_checkbox.isChecked(),
            'colormap': self.colormap_combo.currentText(),
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
        
        self.element_node.config.update(config_updates)
        
        self.update_pie_color_controls()
        
        self.update_display()
    
    def download_figure(self):
        """
        Download the current figure.
        
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        custom_title = self.element_node.config.get('custom_title', 'single_multiple_element_analysis')
        safe_filename = "".join(c for c in custom_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_filename = safe_filename.replace(' ', '_').lower()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Single/Multiple Element Analysis",
            f"{safe_filename}.png",
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;JPEG Files (*.jpg);;All Files (*)"
        )
        
        if file_path:
            try:
                self.figure.savefig(file_path, dpi=300, bbox_inches='tight', 
                                  facecolor='white', edgecolor='none')
                QMessageBox.information(self, "Success", 
                                      f"Figure saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", 
                                   f"Failed to save:\n{str(e)}")
    
    def download_statistics_table(self):
        """
        Download the statistics table as CSV.
        
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        analysis_data = self.element_node.extract_analysis_data()
        if not analysis_data:
            QMessageBox.warning(self, "Warning", "No data available to download")
            return
        
        use_particles_per_ml = self.element_node.config.get('use_particles_per_ml', False)
        dilution_factor = self.element_node.config.get('dilution_factor', 1.0)
        
        stats_df = SingleMultipleElementHelper.create_statistics_table(
            analysis_data, self.is_multiple_sample_data(), use_particles_per_ml, 
            self.parent_window, dilution_factor
        )
        
        custom_title = self.element_node.config.get('custom_title', 'single_multiple_element_analysis')
        safe_filename = "".join(c for c in custom_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_filename = safe_filename.replace(' ', '_').lower()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Statistics Table",
            f"{safe_filename}_statistics.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            try:
                stats_df.to_csv(file_path, index=False)
                QMessageBox.information(self, "Success", 
                                      f"Statistics table saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", 
                                   f"Failed to save:\n{str(e)}")
    
    def create_font_properties(self, config):
        """
        Create matplotlib font properties from config.
        
        Args:
            config (dict): Configuration dictionary
        
        Returns:
            fm.FontProperties: Matplotlib font properties object
        """
        font_family = config.get('font_family', 'Times New Roman')
        font_size = config.get('font_size', 12)
        is_bold = config.get('font_bold', False)
        is_italic = config.get('font_italic', False)
        
        font_props = fm.FontProperties(
            family=font_family,
            size=font_size,
            weight='bold' if is_bold else 'normal',
            style='italic' if is_italic else 'normal'
        )
        
        return font_props
    
    def apply_font_to_figure(self, fig, config):
        """
        Apply font settings to entire figure including pie chart labels.
        
        Args:
            fig: Matplotlib figure object
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        font_props = self.create_font_properties(config)
        font_color = config.get('font_color', '#000000')
        
        for ax in fig.get_axes():
            title = ax.get_title()
            if title:
                ax.set_title(title, fontproperties=font_props, color=font_color)
            
            ax.set_xlabel(ax.get_xlabel(), fontproperties=font_props, color=font_color)
            ax.set_ylabel(ax.get_ylabel(), fontproperties=font_props, color=font_color)
            
            for tick in ax.get_xticklabels():
                tick.set_fontproperties(font_props)
                tick.set_color(font_color)
            for tick in ax.get_yticklabels():
                tick.set_fontproperties(font_props)
                tick.set_color(font_color)
            
            legend = ax.get_legend()
            if legend:
                for text in legend.get_texts():
                    text.set_fontproperties(font_props)
                    text.set_color(font_color)
    
    def update_display(self):
        """
        Update the display.
        
        Returns:
            None
        """
        try:
            self.figure.clear()
            
            analysis_data = self.element_node.extract_analysis_data()
            
            if not analysis_data:
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5, 'No particle data available\nConnect to Sample Selector', 
                       ha='center', va='center', transform=ax.transAxes,
                       fontsize=12, color='gray')
                ax.set_xticks([])
                ax.set_yticks([])
            else:
                config = self.element_node.config
                viz_type = config.get('visualization_type', 'Pie Charts')
                
                self.update_statistics(analysis_data)
                
                self.update_statistics_table(analysis_data)
                
                if viz_type == 'Pie Charts':
                    self.create_pie_chart_plots(analysis_data, config)
                elif viz_type == 'Heatmaps':
                    self.create_heatmap_plots(analysis_data, config)
                
                self.apply_font_to_figure(self.figure, config)
            
            self.figure.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            print(f"Error updating single/multiple element display: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def update_statistics_table(self, analysis_data):
        """
        Update the statistics table tab.
        
        Args:
            analysis_data (dict): Analysis data dictionary
        
        Returns:
            None
        """
        try:
            use_particles_per_ml = self.element_node.config.get('use_particles_per_ml', False)
            dilution_factor = self.element_node.config.get('dilution_factor', 1.0)
            
            stats_df = SingleMultipleElementHelper.create_statistics_table(
                analysis_data, self.is_multiple_sample_data(), use_particles_per_ml,
                self.parent_window, dilution_factor
            )
            
            self.stats_table.setRowCount(len(stats_df))
            self.stats_table.setColumnCount(len(stats_df.columns))
            self.stats_table.setHorizontalHeaderLabels(stats_df.columns.tolist())
            
            for i, row in stats_df.iterrows():
                for j, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    if j == 0 and str(value) == 'SUMMARY':
                        item.setBackground(QColor('#E6F3FF'))
                    self.stats_table.setItem(i, j, item)
            
            self.stats_table.resizeColumnsToContents()
            
        except Exception as e:
            print(f"Error updating statistics table: {str(e)}")
    
    def update_statistics(self, analysis_data):
        """
        Update statistics display.
        
        Args:
            analysis_data (dict): Analysis data dictionary
        
        Returns:
            None
        """
        use_particles_per_ml = self.element_node.config.get('use_particles_per_ml', False)
        dilution_factor = self.element_node.config.get('dilution_factor', 1.0)
        unit = "Particles/mL" if use_particles_per_ml else "Particles"
        
        if self.is_multiple_sample_data():
            total_particles = 0
            total_single = 0
            total_multiple = 0
            
            for sample_results in analysis_data.values():
                total_particles += sample_results['total_particles']
                total_single += sum(details['count'] for _, details, _ in sample_results['single_combinations'])
                total_multiple += sum(details['count'] for _, details, _ in sample_results['multiple_combinations'])
            
            if use_particles_per_ml:
                total_display = SingleMultipleElementHelper.calculate_particles_per_ml(total_particles, self.parent_window, dilution_factor)
                single_display = SingleMultipleElementHelper.calculate_particles_per_ml(total_single, self.parent_window, dilution_factor)
                multiple_display = SingleMultipleElementHelper.calculate_particles_per_ml(total_multiple, self.parent_window, dilution_factor)
            else:
                total_display = total_particles
                single_display = total_single
                multiple_display = total_multiple
            
            stats_text = f"Total: {total_display:.1f} {unit}\n"
            stats_text += f"Single elements: {single_display:.1f} {unit}\n"
            stats_text += f"Multiple elements: {multiple_display:.1f} {unit}"
        else:
            total_particles = analysis_data['total_particles']
            single_count = sum(details['count'] for _, details, _ in analysis_data['single_combinations'])
            multiple_count = sum(details['count'] for _, details, _ in analysis_data['multiple_combinations'])
            
            if use_particles_per_ml:
                total_display = SingleMultipleElementHelper.calculate_particles_per_ml(total_particles, self.parent_window, dilution_factor)
                single_display = SingleMultipleElementHelper.calculate_particles_per_ml(single_count, self.parent_window, dilution_factor)
                multiple_display = SingleMultipleElementHelper.calculate_particles_per_ml(multiple_count, self.parent_window, dilution_factor)
            else:
                total_display = total_particles
                single_display = single_count
                multiple_display = multiple_count
            
            stats_text = f"Total: {total_display:.1f} {unit}\n"
            stats_text += f"Single elements: {single_display:.1f} {unit}\n"
            stats_text += f"Multiple elements: {multiple_display:.1f} {unit}"
        
        self.stats_label.setText(stats_text)
    
    def create_pie_chart_plots(self, analysis_data, config):
        """
        Create pie chart plots.
        
        Args:
            analysis_data (dict): Analysis data dictionary
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        if self.is_multiple_sample_data():
            self.create_multiple_sample_pie_charts(analysis_data, config)
        else:
            self.create_single_sample_pie_charts(analysis_data, config)
    
    def create_single_sample_pie_charts(self, analysis_data, config):
        """
        Create pie charts for single sample with enhanced font application.
        
        Args:
            analysis_data (dict): Analysis data dictionary
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        fig = self.figure
        
        single_colors = config.get('single_pie_colors', {})
        multiple_colors = config.get('multiple_pie_colors', {})
        label_color = config.get('label_color', '#000000')
        use_particles_per_ml = config.get('use_particles_per_ml', False)
        dilution_factor = config.get('dilution_factor', 1.0)
        
        font_props = self.create_font_properties(config)
        
        ax1 = fig.add_subplot(1, 2, 1)
        single_pie_data = SingleMultipleElementHelper.create_pie_chart_data(
            analysis_data, 'single', single_colors, use_particles_per_ml, self.parent_window, dilution_factor
        )
        
        if single_pie_data:
            wedges, texts, autotexts = ax1.pie(
                single_pie_data['values'], 
                labels=single_pie_data['labels'],
                colors=single_pie_data['colors'],
                autopct='%1.1f%%' if config.get('show_percentages', True) else None,
                explode=[0.1] * len(single_pie_data['values']) if config.get('explode_slices', False) else None
            )
            
            for text in texts:
                text.set_fontproperties(font_props)
                text.set_color(label_color)
            
            if autotexts:
                for autotext in autotexts:
                    autotext.set_fontproperties(font_props)
                    autotext.set_color('black')
                    autotext.set_weight('bold')
        
        ax1.set_title('Single Element Particles', fontproperties=font_props, color=config.get('font_color', '#000000'))
        
        ax2 = fig.add_subplot(1, 2, 2)
        multiple_pie_data = SingleMultipleElementHelper.create_pie_chart_data(
            analysis_data, 'multiple', multiple_colors, use_particles_per_ml, self.parent_window, dilution_factor
        )
        
        if multiple_pie_data:
            wedges, texts, autotexts = ax2.pie(
                multiple_pie_data['values'], 
                labels=multiple_pie_data['labels'],
                colors=multiple_pie_data['colors'],
                autopct='%1.1f%%' if config.get('show_percentages', True) else None,
                explode=[0.1] * len(multiple_pie_data['values']) if config.get('explode_slices', False) else None
            )
            
            for text in texts:
                text.set_fontproperties(font_props)
                text.set_color(label_color)
            
            if autotexts:
                for autotext in autotexts:
                    autotext.set_fontproperties(font_props)
                    autotext.set_color('black')
                    autotext.set_weight('bold')
        
        ax2.set_title('Multiple Element Particles', fontproperties=font_props, color=config.get('font_color', '#000000'))
    
    def create_multiple_sample_pie_charts(self, analysis_data, config):
        """
        Create pie charts for multiple samples with enhanced font application.
        
        Args:
            analysis_data (dict): Analysis data dictionary
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        sample_names = list(analysis_data.keys())
        n_samples = len(sample_names)
        
        display_mode = config.get('display_mode', 'Individual Subplots')
        single_colors = config.get('single_pie_colors', {})
        multiple_colors = config.get('multiple_pie_colors', {})
        label_color = config.get('label_color', '#000000')
        use_particles_per_ml = config.get('use_particles_per_ml', False)
        dilution_factor = config.get('dilution_factor', 1.0)
        
        font_props = self.create_font_properties(config)
        
        if display_mode == 'Individual Subplots':
            rows = n_samples
            cols = 2
            
            for i, sample_name in enumerate(sample_names):
                sample_results = analysis_data[sample_name]
                display_name = self.get_display_name(sample_name)
                
                sample_info = {'is_summed': False}
                if hasattr(self.parent_window, 'sample_config') and sample_name in getattr(self.parent_window, 'sample_config', {}):
                    config_data = self.parent_window.sample_config[sample_name]
                    if config_data.get('sum_group'):
                        sample_info = {
                            'is_summed': True,
                            'original_samples': [sample_name]
                        }
                
                ax1 = self.figure.add_subplot(rows, cols, i*2 + 1)
                single_pie_data = SingleMultipleElementHelper.create_pie_chart_data(
                    sample_results, 'single', single_colors, use_particles_per_ml, self.parent_window, dilution_factor, sample_info
                )
                
                if single_pie_data:
                    wedges, texts, autotexts = ax1.pie(
                        single_pie_data['values'], 
                        labels=single_pie_data['labels'],
                        colors=single_pie_data['colors'],
                        autopct='%1.1f%%' if config.get('show_percentages', True) else None
                    )
                    
                    for text in texts:
                        text.set_fontproperties(font_props)
                        text.set_color(label_color)
                    
                    if autotexts:
                        for autotext in autotexts:
                            autotext.set_fontproperties(font_props)
                            autotext.set_color('black')
                            autotext.set_weight('bold')
                
                ax1.set_title(f'{display_name} - Single Elements', fontproperties=font_props)
                
                ax2 = self.figure.add_subplot(rows, cols, i*2 + 2)
                multiple_pie_data = SingleMultipleElementHelper.create_pie_chart_data(
                    sample_results, 'multiple', multiple_colors, use_particles_per_ml, self.parent_window, dilution_factor, sample_info
                )
                
                if multiple_pie_data:
                    wedges, texts, autotexts = ax2.pie(
                        multiple_pie_data['values'], 
                        labels=multiple_pie_data['labels'],
                        colors=multiple_pie_data['colors'],
                        autopct='%1.1f%%' if config.get('show_percentages', True) else None
                    )
                    
                    for text in texts:
                        text.set_fontproperties(font_props)
                        text.set_color(label_color)
                    
                    if autotexts:
                        for autotext in autotexts:
                            autotext.set_fontproperties(font_props)
                            autotext.set_color('black')
                            autotext.set_weight('bold')
                
                ax2.set_title(f'{display_name} - Multiple Elements', fontproperties=font_props)
    
    def create_heatmap_plots(self, analysis_data, config):
        """
        Create heatmap plots.
        
        Args:
            analysis_data (dict): Analysis data dictionary
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        if self.is_multiple_sample_data():
            self.create_multiple_sample_heatmaps(analysis_data, config)
        else:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, 'Heatmaps are designed for multiple samples\nSelect multiple samples to see heatmap visualization', 
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=12, color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
    
    def create_multiple_sample_heatmaps(self, analysis_data, config):
        """
        Create heatmaps for multiple samples with particles/mL support.
        
        Args:
            analysis_data (dict): Analysis data dictionary
            config (dict): Configuration dictionary
        
        Returns:
            None
        """
        use_particles_per_ml = config.get('use_particles_per_ml', False)
        dilution_factor = config.get('dilution_factor', 1.0)
        
        heatmap_data = SingleMultipleElementHelper.create_heatmap_data(
            analysis_data, use_particles_per_ml, self.parent_window, dilution_factor
        )
        
        if not heatmap_data:
            return
        
        single_df_particles = heatmap_data['single_particles']
        single_df_percentage = heatmap_data['single_percentage']
        multiple_df_particles = heatmap_data['multiple_particles']
        multiple_df_percentage = heatmap_data['multiple_percentage']
        
        fig = self.figure
        
        colormap_name = config.get('colormap', 'YlGn')
        colormap = plt.cm.get_cmap(colormap_name)
        
        ax1 = fig.add_subplot(1, 2, 1)
        
        if not single_df_particles.empty:
            plot_data = single_df_particles.copy()
            if config.get('use_log_scale', True):
                plot_data = plot_data.replace(0, np.nan)
                plot_data = np.log10(plot_data + 1)
            
            im1 = ax1.imshow(plot_data.values, cmap=colormap_name, aspect='auto')
            
            ax1.set_xticks(range(len(single_df_particles.columns)))
            ax1.set_xticklabels([self.get_display_name(name) for name in single_df_particles.columns], 
                            rotation=0, ha='right')
            ax1.set_yticks(range(len(single_df_particles.index)))
            ax1.set_yticklabels(single_df_particles.index)
            
            if config.get('show_values', True):
                data_min = np.nanmin(plot_data.values)
                data_max = np.nanmax(plot_data.values)
                norm = plt.Normalize(vmin=data_min, vmax=data_max)
                
                for i in range(len(single_df_percentage.index)):
                    for j in range(len(single_df_percentage.columns)):
                        percentage = single_df_percentage.iloc[i, j]
                        if not np.isnan(percentage) and percentage > 0:
                            data_value = plot_data.iloc[i, j]
                            if not np.isnan(data_value):
                                color_rgba = colormap(norm(data_value))
                       
                                luminance = 0.299 * color_rgba[0] + 0.587 * color_rgba[1] + 0.114 * color_rgba[2]
           
                                text_color = 'white' if luminance < 0.5 else 'black'
                            
                            ax1.text(j, i, f'{percentage:.2f}%', ha='center', va='center', 
                                color=text_color, fontweight='bold')
            
            cbar1 = fig.colorbar(im1, ax=ax1, shrink=0.8)
            unit = 'Particles/mL' if use_particles_per_ml else 'Particles'
            cbar_label = f'{unit}' if not config.get('use_log_scale', True) else f'Log({unit} + 1)'
            cbar1.set_label(cbar_label)
        
        ax1.set_title('Single Element Distribution')
        
        ax2 = fig.add_subplot(1, 2, 2)
        
        if not multiple_df_particles.empty:
            plot_data = multiple_df_particles.copy()
            if config.get('use_log_scale', True):
                plot_data = plot_data.replace(0, np.nan)
                plot_data = np.log10(plot_data + 1)
            
            im2 = ax2.imshow(plot_data.values, cmap=colormap_name, aspect='auto')
            
            ax2.set_xticks(range(len(multiple_df_particles.columns)))
            ax2.set_xticklabels([self.get_display_name(name) for name in multiple_df_particles.columns], 
                            rotation=0, ha='right')
            ax2.set_yticks(range(len(multiple_df_particles.index)))
            ax2.set_yticklabels(multiple_df_particles.index)
            
            if config.get('show_values', True):
                data_min = np.nanmin(plot_data.values)
                data_max = np.nanmax(plot_data.values)
                norm = plt.Normalize(vmin=data_min, vmax=data_max)
                
                for i in range(len(multiple_df_percentage.index)):
                    for j in range(len(multiple_df_percentage.columns)):
                        percentage = multiple_df_percentage.iloc[i, j]
                        if not np.isnan(percentage) and percentage > 0:
                            data_value = plot_data.iloc[i, j]
                            if not np.isnan(data_value):
                                color_rgba = colormap(norm(data_value))

                                luminance = 0.299 * color_rgba[0] + 0.587 * color_rgba[1] + 0.114 * color_rgba[2]
 
                                text_color = 'white' if luminance < 0.5 else 'black'
                            
                            ax2.text(j, i, f'{percentage:.2f}%', ha='center', va='center', 
                                color=text_color, fontweight='bold')
            
            cbar2 = fig.colorbar(im2, ax=ax2, shrink=0.8)
            unit = 'Particles/mL' if use_particles_per_ml else 'Particles'
            cbar_label = f'{unit}' if not config.get('use_log_scale', True) else f'Log({unit} + 1)'
            cbar2.set_label(cbar_label)
        
        ax2.set_title('Multiple Element Distribution')


class SingleMultipleElementPlotNode(QObject):
    """
    Node for single vs multiple element analysis.
    """
    
    position_changed = Signal(object)
    configuration_changed = Signal()
    
    def __init__(self, parent_window=None):
        """
        Initialize single/multiple element plot node.
        
        Args:
            parent_window: Parent window widget
        """
        super().__init__()
        self.title = "Single/Multiple"
        self.node_type = "single_multiple_element_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.config = {
            'custom_title': 'Single vs Multiple Element Analysis',
            'visualization_type': 'Pie Charts',
            'display_mode': 'Individual Subplots',
            'use_particles_per_ml': False,
            'dilution_factor': 1.0,
            'single_threshold': 0.5,
            'multiple_threshold': 0.5,
            'show_percentages': True,
            'explode_slices': False,
            'label_color': '#000000',
            'single_pie_colors': {},
            'multiple_pie_colors': {},
            'use_log_scale': True,
            'show_values': True,
            'colormap': 'YlGn',
            'sample_colors': {},
            'sample_name_mappings': {},
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
        dialog = SingleMultipleElementDisplayDialog(self, parent_window)
        dialog.exec()
        return True
    
    def process_data(self, input_data):
        """
        Process input data.
        
        Args:
            input_data (dict): Input data dictionary
        
        Returns:
            None
        """
        if not input_data:
            print("No input data received for single/multiple element analysis")
            return
        
        print(f"Single/Multiple element analysis received data: {input_data.get('type', 'unknown')}")
        self.input_data = input_data
        self.configuration_changed.emit()
    
    def extract_analysis_data(self):
        """
        Extract analysis data from input.
        
        Returns:
            dict or None: Analysis data dictionary
        """
        if not self.input_data:
            return None
        
        input_type = self.input_data.get('type')
        single_threshold = self.config.get('single_threshold', 0.5)
        multiple_threshold = self.config.get('multiple_threshold', 0.5)
        
        if input_type == 'sample_data':
            particles = self.input_data.get('particle_data', [])
            return SingleMultipleElementHelper.analyze_particles(
                particles, single_threshold, multiple_threshold
            )
        elif input_type == 'multiple_sample_data':
            return self._extract_multiple_sample_analysis()
        
        return None
    
    def _extract_multiple_sample_analysis(self):
        """
        Extract analysis for multiple samples.
        
        Returns:
            dict: Dictionary of analysis results by sample name
        """
        particles = self.input_data.get('particle_data', [])
        sample_names = self.input_data.get('sample_names', [])
        
        if not particles:
            return None
        
        sample_particles = {name: [] for name in sample_names}
        
        for particle in particles:
            source_sample = particle.get('source_sample')
            if source_sample and source_sample in sample_particles:
                sample_particles[source_sample].append(particle)
        
        analysis_results = {}
        single_threshold = self.config.get('single_threshold', 0.5)
        multiple_threshold = self.config.get('multiple_threshold', 0.5)
        
        for sample_name, sample_particle_list in sample_particles.items():
            if sample_particle_list:
                analysis_results[sample_name] = SingleMultipleElementHelper.analyze_particles(
                    sample_particle_list, single_threshold, multiple_threshold
                )
        
        return analysis_results