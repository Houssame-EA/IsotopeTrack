import sys
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
                               QPushButton, QLabel, QLineEdit, QComboBox, QTableWidget, 
                               QTableWidgetItem, QGroupBox, QSpinBox, QDoubleSpinBox,
                               QTextEdit, QTabWidget, QWidget, QCheckBox, QMessageBox,
                               QListWidget, QListWidgetItem, QSplitter, QHeaderView)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import numpy as np
import re

try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False

class SignalCalculatorDialog(QDialog):
    """
    NOTE: This feature is planned for future implementation and is not yet integrated into the application.
    
    Dialog for creating calculated/derived signals from existing isotope signals with isobaric corrections.
    """
    
    calculated_signals_changed = Signal(dict)
    
    def __init__(self, selected_isotopes, current_sample, data, time_array, parent=None):
        """
        Initialize the signal calculator dialog.
        
        Args:
            selected_isotopes: Dictionary of selected isotopes by element
            current_sample: Current sample name
            data: Dictionary of signal data arrays
            time_array: Array of time values
            parent: Parent widget for the dialog
            
        Returns:
            None
        """
        super().__init__(parent)
        self.selected_isotopes = selected_isotopes
        self.current_sample = current_sample
        self.data = data
        self.time_array = time_array
        self.parent_window = parent
        
        self.calculated_signals = {}
        
        self.setWindowTitle("Signal Calculator & Isobaric Corrections")
        self.setMinimumSize(900, 700)
        self.setup_ui()
        self.populate_available_signals()
        
    def setup_ui(self):
        """
        Set up the user interface with tabs and controls.
        
        Args:
            None
            
        Returns:
            None
        """
        layout = QVBoxLayout(self)
        
        tabs = QTabWidget()
        
        calc_tab = self.create_calculator_tab()
        tabs.addTab(calc_tab, "Signal Calculator")
        
        isobaric_tab = self.create_isobaric_tab()
        tabs.addTab(isobaric_tab, "Isobaric Corrections")
        
        preset_tab = self.create_preset_tab()
        tabs.addTab(preset_tab, "Common Corrections")
        
        layout.addWidget(tabs)
        
        button_layout = QHBoxLayout()
        
        self.preview_button = QPushButton("Preview Result")
        self.add_signal_button = QPushButton("Add Calculated Signal")
        self.save_button = QPushButton("Save All")
        self.cancel_button = QPushButton("Cancel")
        
        self.preview_button.clicked.connect(self.preview_calculation)
        self.add_signal_button.clicked.connect(self.add_calculated_signal)
        self.save_button.clicked.connect(self.save_signals)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.preview_button)
        button_layout.addWidget(self.add_signal_button)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
    def create_calculator_tab(self):
        """
        Create the general signal calculator tab.
        
        Args:
            None
            
        Returns:
            QWidget: Calculator tab widget
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        signal_group = QGroupBox("Define Calculated Signal")
        signal_layout = QGridLayout(signal_group)
        
        signal_layout.addWidget(QLabel("Signal Name:"), 0, 0)
        self.signal_name_edit = QLineEdit()
        self.signal_name_edit.setPlaceholderText("e.g., 'Corrected_107Ag' or 'Sum_Fe_isotopes'")
        signal_layout.addWidget(self.signal_name_edit, 0, 1, 1, 2)
        
        signal_layout.addWidget(QLabel("Equation:"), 1, 0)
        self.equation_edit = QLineEdit()
        self.equation_edit.setPlaceholderText("e.g., A + B - 0.5*C or A - B*1.23")
        signal_layout.addWidget(self.equation_edit, 1, 1, 1, 2)
        
        signal_layout.addWidget(QLabel("Available Signals:"), 2, 0)
        self.available_signals_list = QListWidget()
        self.available_signals_list.itemDoubleClicked.connect(self.add_signal_to_equation)
        signal_layout.addWidget(self.available_signals_list, 3, 0, 3, 1)
        
        button_widget = QWidget()
        button_layout = QGridLayout(button_widget)
        
        ops = ['+', '-', '*', '/', '(', ')', 'Clear']
        positions = [(i//3, i%3) for i in range(len(ops))]
        
        for pos, op in zip(positions, ops):
            btn = QPushButton(op)
            if op == 'Clear':
                btn.clicked.connect(lambda: self.equation_edit.clear())
            else:
                btn.clicked.connect(lambda checked, o=op: self.add_operator(o))
            button_layout.addWidget(btn, *pos)
        
        signal_layout.addWidget(button_widget, 3, 1, 3, 1)
        
        constants_widget = QWidget()
        constants_layout = QVBoxLayout(constants_widget)
        constants_layout.addWidget(QLabel("Add Constant:"))
        
        constant_input_layout = QHBoxLayout()
        self.constant_edit = QDoubleSpinBox()
        self.constant_edit.setRange(-999999, 999999)
        self.constant_edit.setDecimals(6)
        add_constant_btn = QPushButton("Add")
        add_constant_btn.clicked.connect(self.add_constant)
        
        constant_input_layout.addWidget(self.constant_edit)
        constant_input_layout.addWidget(add_constant_btn)
        constants_layout.addLayout(constant_input_layout)
        
        signal_layout.addWidget(constants_widget, 3, 2, 3, 1)
        
        layout.addWidget(signal_group)
        
        help_group = QGroupBox("Instructions")
        help_layout = QVBoxLayout(help_group)
        help_text = QTextEdit()
        help_text.setMaximumHeight(100)
        help_text.setHtml("""
        <b>Signal Calculator Instructions:</b><br>
        • Double-click signals from the list to add them to the equation<br>
        • Use mathematical operators: +, -, *, /, (, )<br>
        • Add constants using the constant input box<br>
        • Signal variables will be replaced with actual signal names (A, B, C, etc.)<br>
        • Example: A + B - 0.1234*C (where A, B, C are your selected signals)
        """)
        help_text.setReadOnly(True)
        help_layout.addWidget(help_text)
        layout.addWidget(help_group)
        
        return widget
        
    def create_isobaric_tab(self):
        """
        Create the isobaric correction tab with preset templates.
        
        Args:
            None
            
        Returns:
            QWidget: Isobaric correction tab widget
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        template_group = QGroupBox("Isobaric Correction Templates")
        template_layout = QVBoxLayout(template_group)
        
        interferences = [
            ("58Fe on 58Ni", "Ni58_corrected = A - B"),
            ("87Rb on 87Sr", "Sr87_corrected = A - B"), 
            ("204Hg on 204Pb", "Pb204_corrected = A - B"),
            ("115In on 115Sn", "Sn115_corrected = A - B"),
            ("138Ba on 138Ce", "Ce138_corrected = A - B"),
        ]
        
        self.interference_combo = QComboBox()
        for desc, eq in interferences:
            self.interference_combo.addItem(desc, eq)
        
        template_layout.addWidget(QLabel("Select Common Interference:"))
        template_layout.addWidget(self.interference_combo)
        
        apply_template_btn = QPushButton("Apply Template")
        apply_template_btn.clicked.connect(self.apply_isobaric_template)
        template_layout.addWidget(apply_template_btn)
        
        layout.addWidget(template_group)
        
        custom_group = QGroupBox("Custom Isobaric Correction")
        custom_layout = QGridLayout(custom_group)
        
        custom_layout.addWidget(QLabel("Target Signal:"), 0, 0)
        self.target_signal_combo = QComboBox()
        custom_layout.addWidget(self.target_signal_combo, 0, 1)
        
        custom_layout.addWidget(QLabel("Interfering Signal:"), 1, 0)
        self.interfering_signal_combo = QComboBox()
        custom_layout.addWidget(self.interfering_signal_combo, 1, 1)
        
        custom_layout.addWidget(QLabel("Correction Factor:"), 2, 0)
        self.correction_factor_spin = QDoubleSpinBox()
        self.correction_factor_spin.setRange(-10, 10)
        self.correction_factor_spin.setDecimals(6)
        self.correction_factor_spin.setValue(1.0)
        custom_layout.addWidget(self.correction_factor_spin, 2, 1)
        
        build_correction_btn = QPushButton("Build Correction Equation")
        build_correction_btn.clicked.connect(self.build_isobaric_correction)
        custom_layout.addWidget(build_correction_btn, 3, 0, 1, 2)
        
        layout.addWidget(custom_group)
        
        ratio_group = QGroupBox("Isotope Ratio Based Correction")
        ratio_layout = QGridLayout(ratio_group)
        
        ratio_layout.addWidget(QLabel("Primary Isotope:"), 0, 0)
        self.primary_isotope_combo = QComboBox()
        ratio_layout.addWidget(self.primary_isotope_combo, 0, 1)
        
        ratio_layout.addWidget(QLabel("Reference Isotope:"), 1, 0)
        self.reference_isotope_combo = QComboBox()
        ratio_layout.addWidget(self.reference_isotope_combo, 1, 1)
        
        ratio_layout.addWidget(QLabel("Natural Ratio:"), 2, 0)
        self.natural_ratio_spin = QDoubleSpinBox()
        self.natural_ratio_spin.setRange(0.001, 1000)
        self.natural_ratio_spin.setDecimals(6)
        ratio_layout.addWidget(self.natural_ratio_spin, 2, 1)
        
        build_ratio_btn = QPushButton("Build Ratio Correction")
        build_ratio_btn.clicked.connect(self.build_ratio_correction)
        ratio_layout.addWidget(build_ratio_btn, 3, 0, 1, 2)
        
        layout.addWidget(ratio_group)
        
        return widget
        
    def create_preset_tab(self):
        """
        Create tab with preset correction equations.
        
        Args:
            None
            
        Returns:
            QWidget: Preset corrections tab widget
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        presets_group = QGroupBox("Common Mass Spectrometry Corrections")
        presets_layout = QVBoxLayout(presets_group)
        
        self.presets_table = QTableWidget()
        self.presets_table.setColumnCount(3)
        self.presets_table.setHorizontalHeaderLabels(["Correction Type", "Description", "Equation Template"])
        
        presets = [
            ("ArC+ on 52Cr", "Argon-carbon interference on Chromium-52", "Cr52_corrected = A - B*factor"),
            ("ArO+ on 56Fe", "Argon-oxygen interference on Iron-56", "Fe56_corrected = A - B*factor"),
            ("ArAr+ on 80Se", "Argon dimer interference on Selenium-80", "Se80_corrected = A - B*factor"),
            ("Double charge", "Doubly charged ion correction", "Target_corrected = A - B*0.5"),
            ("Oxide formation", "Metal oxide interference", "Target_corrected = A - B*factor"),
            ("Sum isotopes", "Sum all isotopes of an element", "Element_total = A + B + C"),
        ]
        
        self.presets_table.setRowCount(len(presets))
        for i, (corr_type, desc, eq) in enumerate(presets):
            self.presets_table.setItem(i, 0, QTableWidgetItem(corr_type))
            self.presets_table.setItem(i, 1, QTableWidgetItem(desc))
            self.presets_table.setItem(i, 2, QTableWidgetItem(eq))
        
        self.presets_table.resizeColumnsToContents()
        presets_layout.addWidget(self.presets_table)
        
        apply_preset_btn = QPushButton("Apply Selected Preset")
        apply_preset_btn.clicked.connect(self.apply_preset)
        presets_layout.addWidget(apply_preset_btn)
        
        layout.addWidget(presets_group)
        
        return widget
        
    def populate_available_signals(self):
        """
        Populate the available signals list with isotopes and calculated signals.
        
        Args:
            None
            
        Returns:
            None
        """
        self.available_signals_list.clear()
        
        signal_vars = {}
        var_counter = 0
        
        for element, isotopes in self.selected_isotopes.items():
            for isotope in isotopes:
                if element == 'Calculated':
                    element_key = isotope
                else:
                    try:
                        isotope_float = float(isotope)
                        element_key = f"{element}-{isotope_float:.4f}"
                    except (ValueError, TypeError):
                        element_key = f"{element}-{isotope}"
                
                display_label = self.parent_window.get_formatted_label(element_key)
                
                var_name = chr(65 + var_counter)
                var_counter += 1
                
                signal_vars[var_name] = element_key
                
                item = QListWidgetItem(f"{var_name}: {display_label}")
                item.setData(Qt.UserRole, var_name)
                self.available_signals_list.addItem(item)
        
        self.signal_variables = signal_vars
        
        signal_names = [f"{var}: {self.parent_window.get_formatted_label(key)}" 
                    for var, key in signal_vars.items()]
        
        self.target_signal_combo.clear()
        self.target_signal_combo.addItems(signal_names)
        
        self.interfering_signal_combo.clear()
        self.interfering_signal_combo.addItems(signal_names)
        
        self.primary_isotope_combo.clear()
        self.primary_isotope_combo.addItems(signal_names)
        
        self.reference_isotope_combo.clear()
        self.reference_isotope_combo.addItems(signal_names)
            
    def add_signal_to_equation(self, item):
        """
        Add selected signal variable to equation.
        
        Args:
            item: QListWidgetItem containing signal variable information
            
        Returns:
            None
        """
        var_name = item.data(Qt.UserRole)
        current_text = self.equation_edit.text()
        self.equation_edit.setText(current_text + var_name)
        
    def add_operator(self, operator):
        """
        Add mathematical operator to equation.
        
        Args:
            operator: Mathematical operator string to add
            
        Returns:
            None
        """
        current_text = self.equation_edit.text()
        self.equation_edit.setText(current_text + operator)
        
    def add_constant(self):
        """
        Add constant value to equation.
        
        Args:
            None
            
        Returns:
            None
        """
        constant = self.constant_edit.value()
        current_text = self.equation_edit.text()
        self.equation_edit.setText(current_text + str(constant))
        
    def apply_isobaric_template(self):
        """
        Apply selected isobaric interference template.
        
        Args:
            None
            
        Returns:
            None
        """
        template_equation = self.interference_combo.currentData()
        if template_equation:
            parts = template_equation.split(" = ")
            if len(parts) == 2:
                signal_name = parts[0]
                equation = parts[1]
                
                self.signal_name_edit.setText(signal_name)
                self.equation_edit.setText(equation)
                
    def build_isobaric_correction(self):
        """
        Build isobaric correction equation from selections.
        
        Args:
            None
            
        Returns:
            None
        """
        target_text = self.target_signal_combo.currentText()
        interfering_text = self.interfering_signal_combo.currentText()
        factor = self.correction_factor_spin.value()
        
        if target_text and interfering_text:
            target_var = target_text.split(':')[0]
            interfering_var = interfering_text.split(':')[0]
            
            target_element = target_text.split(': ')[1] if ': ' in target_text else target_var
            signal_name = f"{target_element}_corrected"
            
            if factor == 1.0:
                equation = f"{target_var} - {interfering_var}"
            else:
                equation = f"{target_var} - {factor}*{interfering_var}"
                
            self.signal_name_edit.setText(signal_name)
            self.equation_edit.setText(equation)
            
    def build_ratio_correction(self):
        """
        Build isotope ratio based correction.
        
        Args:
            None
            
        Returns:
            None
        """
        primary_text = self.primary_isotope_combo.currentText()
        reference_text = self.reference_isotope_combo.currentText()
        ratio = self.natural_ratio_spin.value()
        
        if primary_text and reference_text:
            primary_var = primary_text.split(':')[0]
            reference_var = reference_text.split(':')[0]
            
            primary_element = primary_text.split(': ')[1] if ': ' in primary_text else primary_var
            signal_name = f"{primary_element}_ratio_corrected"
            equation = f"{primary_var} - {ratio}*{reference_var}"
            
            self.signal_name_edit.setText(signal_name)
            self.equation_edit.setText(equation)
            
    def apply_preset(self):
        """
        Apply selected preset equation.
        
        Args:
            None
            
        Returns:
            None
        """
        current_row = self.presets_table.currentRow()
        if current_row >= 0:
            equation_item = self.presets_table.item(current_row, 2)
            if equation_item:
                template = equation_item.text()
                parts = template.split(" = ")
                
                if len(parts) == 2:
                    signal_name = parts[0]
                    equation = parts[1]
                    
                    self.signal_name_edit.setText(signal_name)
                    self.equation_edit.setText(equation)
                    
    def preview_calculation(self):
        """
        Preview the calculated signal result.
        
        Args:
            None
            
        Returns:
            None
        """
        signal_name = self.signal_name_edit.text().strip()
        equation = self.equation_edit.text().strip()
        
        if not signal_name or not equation:
            QMessageBox.warning(self, "Input Error", "Please provide both signal name and equation.")
            return
            
        try:
            result_signal = self.calculate_signal(equation)
            
            preview_dialog = SignalPreviewDialog(signal_name, result_signal, self.time_array, self)
            preview_dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Error calculating signal: {str(e)}")
            
    def calculate_signal(self, equation):
        """
        Calculate the signal from the equation.
        
        Args:
            equation: Mathematical equation string to evaluate
            
        Returns:
            ndarray: Calculated signal data array
        """
        safe_dict = {}
        
        for var, element_key in self.signal_variables.items():
            if element_key in self.data:
                safe_dict[var] = self.data[element_key]
            else:
                try:
                    if '-' in element_key:
                        element, isotope_mass_str = element_key.split('-', 1)
                        target_mass = float(isotope_mass_str)
                        
                        closest_mass = min(self.data.keys(), 
                                        key=lambda x: abs(float(x) - target_mass) if isinstance(x, (int, float)) else float('inf'))
                        safe_dict[var] = self.data[closest_mass]
                    else:
                        matching_keys = [k for k in self.data.keys() if str(k) == element_key]
                        if matching_keys:
                            safe_dict[var] = self.data[matching_keys[0]]
                        else:
                            raise ValueError(f"Cannot find data for {element_key}")
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Cannot process signal variable {var} ({element_key}): {str(e)}")
            
        safe_dict.update({
            'np': np,
            'sqrt': np.sqrt,
            'abs': np.abs,
            'log': np.log,
            'exp': np.exp,
            'sin': np.sin,
            'cos': np.cos,
            'tan': np.tan,
        })
        
        try:
            result = eval(equation, {"__builtins__": {}}, safe_dict)
            return np.array(result)
        except Exception as e:
            raise ValueError(f"Invalid equation: {str(e)}")
                
    def add_calculated_signal(self):
        """
        Add the calculated signal to the list.
        
        Args:
            None
            
        Returns:
            None
        """
        signal_name = self.signal_name_edit.text().strip()
        equation = self.equation_edit.text().strip()
        
        if not signal_name or not equation:
            QMessageBox.warning(self, "Input Error", "Please provide both signal name and equation.")
            return
            
        try:
            result_signal = self.calculate_signal(equation)
            
            self.calculated_signals[signal_name] = {
                'equation': equation,
                'variables': self.signal_variables.copy(),
                'signal_data': result_signal
            }
            
            QMessageBox.information(self, "Success", f"Calculated signal '{signal_name}' added successfully.")
            
            self.signal_name_edit.clear()
            self.equation_edit.clear()
            
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Error adding signal: {str(e)}")
            
    def save_signals(self):
        """
        Save all calculated signals and close dialog.
        
        Args:
            None
            
        Returns:
            None
        """
        if self.calculated_signals:
            self.calculated_signals_changed.emit(self.calculated_signals)
            self.accept()
        else:
            QMessageBox.information(self, "No Signals", "No calculated signals to save.")


class SignalPreviewDialog(QDialog):
    
    def __init__(self, signal_name, signal_data, time_array, parent=None):
        """
        Initialize the signal preview dialog.
        
        Args:
            signal_name: Name of the calculated signal
            signal_data: Array of signal values
            time_array: Array of time values
            parent: Parent widget for the dialog
            
        Returns:
            None
        """
        super().__init__(parent)
        self.signal_name = signal_name
        self.signal_data = signal_data
        self.time_array = time_array
        
        self.setWindowTitle(f"Preview: {signal_name}")
        self.setMinimumSize(800, 600)
        self.setup_ui()
        
    def setup_ui(self):
        """
        Set up the user interface for signal preview.
        
        Args:
            None
            
        Returns:
            None
        """
        layout = QVBoxLayout(self)
        
        name_label = QLabel(f"Signal: {self.signal_name}")
        name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2196F3;")
        layout.addWidget(name_label)
        
        stats_group = QGroupBox("Signal Statistics")
        stats_layout = QGridLayout(stats_group)
        
        stats_layout.addWidget(QLabel("Mean:"), 0, 0)
        stats_layout.addWidget(QLabel(f"{np.mean(self.signal_data):.4f}"), 0, 1)
        
        stats_layout.addWidget(QLabel("Std Dev:"), 0, 2)
        stats_layout.addWidget(QLabel(f"{np.std(self.signal_data):.4f}"), 0, 3)
        
        stats_layout.addWidget(QLabel("Min:"), 1, 0)
        stats_layout.addWidget(QLabel(f"{np.min(self.signal_data):.4f}"), 1, 1)
        
        stats_layout.addWidget(QLabel("Max:"), 1, 2)
        stats_layout.addWidget(QLabel(f"{np.max(self.signal_data):.4f}"), 1, 3)
        
        stats_layout.addWidget(QLabel("Points:"), 2, 0)
        stats_layout.addWidget(QLabel(f"{len(self.signal_data)}"), 2, 1)
        
        stats_layout.addWidget(QLabel("Time Range:"), 2, 2)
        stats_layout.addWidget(QLabel(f"{self.time_array[0]:.2f} - {self.time_array[-1]:.2f} s"), 2, 3)
        
        layout.addWidget(stats_group)
        
        if PYQTGRAPH_AVAILABLE:
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setLabel('left', 'Signal Intensity')
            self.plot_widget.setLabel('bottom', 'Time (s)')
            self.plot_widget.setTitle(f"Preview: {self.signal_name}")
            
            self.plot_widget.plot(self.time_array, self.signal_data, 
                                pen=pg.mkPen(color='blue', width=2),
                                name=self.signal_name)
            
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
            self.plot_widget.setBackground('w')
            
            layout.addWidget(self.plot_widget)
        else:
            plot_label = QLabel("Signal plot preview\n(Install pyqtgraph for interactive plotting)")
            plot_label.setAlignment(Qt.AlignCenter)
            plot_label.setMinimumHeight(300)
            plot_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
            layout.addWidget(plot_label)
        
        button_layout = QHBoxLayout()
        
        save_data_btn = QPushButton("Export Signal Data")
        save_data_btn.clicked.connect(self.export_signal_data)
        button_layout.addWidget(save_data_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
    def export_signal_data(self):
        """
        Export signal data to CSV file.
        
        Args:
            None
            
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog
        import csv
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Signal Data", 
            f"{self.signal_name}.csv",
            "CSV Files (*.csv)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Time (s)', f'{self.signal_name}'])
                    for t, s in zip(self.time_array, self.signal_data):
                        writer.writerow([t, s])
                        
                QMessageBox.information(self, "Export Complete", f"Signal data exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export data:\n{str(e)}")