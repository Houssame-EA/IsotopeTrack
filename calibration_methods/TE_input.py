import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QLineEdit, QComboBox, QMessageBox,
                             QFormLayout, QApplication, QGroupBox, QMainWindow,
                             QScrollArea, QFrame)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator

class InputMethodCalibration(QMainWindow):
    calibration_completed = Signal(str, float)

    def __init__(self, parent=None):
        """
        Initialize the Weight Method Calibration window.
        
        Args:
            parent: Parent widget for this window
        """
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        """
        Initialize and configure the user interface.
        
        Sets up stylesheets, layouts, and connects all signals for the calibration window.
        """
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #f8f9fa;
                color: #212529;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0069d9;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QLineEdit, QComboBox {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
            }
            QLabel {
                color: #495057;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        container = QWidget()
        scroll_layout = QVBoxLayout(container)
        scroll_layout.setSpacing(15)
        scroll.setWidget(container)
        
        self.create_intro_section(scroll_layout)
        self.create_measurement_section(scroll_layout)
        self.create_calculation_section(scroll_layout)
        
        main_layout.addWidget(scroll)
        
        self.setWindowTitle("Weight Method Calibration")
        self.setMinimumSize(800, 600)
        
        self.initial_weight.textChanged.connect(self.update_preview)
        self.final_weight.textChanged.connect(self.update_preview)
        self.waste_weight.textChanged.connect(self.update_preview)
        self.analysis_time.textChanged.connect(self.update_preview)
        self.weight_unit.currentIndexChanged.connect(self.update_preview)
        self.time_unit.currentIndexChanged.connect(self.update_preview)

    def create_intro_section(self, parent_layout):
        """
        Create and add the introduction section to the layout.
        
        Args:
            parent_layout: The parent layout to add the introduction section to
        """
        intro_group = QGroupBox("1. Weight Method Calibration")
        intro_layout = QVBoxLayout(intro_group)
        
        description = QLabel(
            "The weight method determines transport rate by measuring weight changes in the "
            "sample vial and waste collection container during analysis. This provides a direct "
            "physical measurement of the actual sample volume transported to the plasma."
        )
        description.setWordWrap(True)
        intro_layout.addWidget(description)
        
        parent_layout.addWidget(intro_group)
    
    def create_measurement_section(self, parent_layout):
        """
        Create and add the measurement inputs section to the layout.
        
        Args:
            parent_layout: The parent layout to add the measurement section to
        """
        measurement_group = QGroupBox("2. Enter Measurements")
        measurement_layout = QVBoxLayout(measurement_group)
        
        units_layout = QHBoxLayout()
        units_layout.setSpacing(20)
        
        self.weight_unit = QComboBox()
        self.weight_unit.addItems(["mg", "g"])
        
        self.time_unit = QComboBox()
        self.time_unit.addItems(["seconds", "minutes"])
        
        units_layout.addWidget(QLabel("Mass unit:"))
        units_layout.addWidget(self.weight_unit)
        units_layout.addSpacing(40)
        units_layout.addWidget(QLabel("Time unit:"))
        units_layout.addWidget(self.time_unit)
        units_layout.addStretch()
        
        measurement_layout.addLayout(units_layout)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        
        self.initial_weight = QLineEdit()
        self.initial_weight.setPlaceholderText("Initial mass...")
        self.initial_weight.setValidator(QDoubleValidator(0.0, 100000.0, 5))
        
        self.final_weight = QLineEdit()
        self.final_weight.setPlaceholderText("Final mass...")
        self.final_weight.setValidator(QDoubleValidator(0.0, 100000.0, 5))
        
        self.waste_weight = QLineEdit()
        self.waste_weight.setPlaceholderText("Waste mass...")
        self.waste_weight.setValidator(QDoubleValidator(0.0, 100000.0, 5))
        
        self.analysis_time = QLineEdit()
        self.analysis_time.setPlaceholderText("Analysis time...")
        self.analysis_time.setValidator(QDoubleValidator(0.0, 10000.0, 2))
        
        form_layout.addRow("Initial sample mass:", self.initial_weight)
        form_layout.addRow("Final sample mass:", self.final_weight)
        form_layout.addRow("Waste container mass:", self.waste_weight)
        form_layout.addRow("Analysis time:", self.analysis_time)
        
        measurement_layout.addLayout(form_layout)
        
        parent_layout.addWidget(measurement_group)
    
    def create_calculation_section(self, parent_layout):
        """
        Create and add the calculation section to the layout.
        
        Args:
            parent_layout: The parent layout to add the calculation section to
        """
        calculation_group = QGroupBox("3. Calculate Transport Rate")
        calculation_layout = QVBoxLayout(calculation_group)
        
        self.result_preview = QLabel("Enter measurements to see calculation preview")
        self.result_preview.setStyleSheet("""
            background-color: #f0f0f0; 
            padding: 15px; 
            border-radius: 5px;
            font-size: 14px;
            font-weight: bold;
        """)
        self.result_preview.setWordWrap(True)
        self.result_preview.setAlignment(Qt.AlignCenter)
        self.result_preview.setMinimumHeight(60)
        calculation_layout.addWidget(self.result_preview)
        
        calc_button = QPushButton("Calculate Transport Rate")
        calc_button.setMinimumHeight(40)
        calc_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0069d9;
            }
        """)
        calc_button.clicked.connect(self.calculate)
        calculation_layout.addWidget(calc_button)
        
        direct_layout = QHBoxLayout()
        
        direct_info = QLabel("Or enter known rate:")
        
        self.direct_rate = QLineEdit()
        self.direct_rate.setPlaceholderText("Enter known rate...")
        self.direct_rate.setValidator(QDoubleValidator(0.0, 1000.0, 5))
        self.direct_rate.setMaximumWidth(150)
        
        direct_button = QPushButton("Submit Direct")
        direct_button.clicked.connect(self.submit_direct)
        direct_button.setMaximumWidth(120)
        
        direct_layout.addWidget(direct_info)
        direct_layout.addWidget(self.direct_rate)
        direct_layout.addWidget(QLabel("μL/s"))
        direct_layout.addWidget(direct_button)
        direct_layout.addStretch()
        
        calculation_layout.addLayout(direct_layout)
        
        parent_layout.addWidget(calculation_group)
    
    def update_preview(self):
        """
        Update the result preview label with real-time calculation.
        
        Validates user inputs and displays calculated transport rate or appropriate
        error messages in the preview label.
        """
        try:
            if not all([self.initial_weight.text(), self.final_weight.text(), 
                       self.waste_weight.text(), self.analysis_time.text()]):
                self.result_preview.setText("Enter all measurements to see calculation preview")
                self.result_preview.setStyleSheet("""
                    background-color: #f0f0f0; 
                    padding: 15px; 
                    border-radius: 5px;
                    font-size: 14px;
                    color: #6c757d;
                """)
                return
                
            w_initial = float(self.initial_weight.text())
            w_final = float(self.final_weight.text())
            w_waste = float(self.waste_weight.text())
            time = float(self.analysis_time.text())
            
            if time <= 0:
                self.result_preview.setText("⚠️ Analysis time must be greater than zero")
                self.result_preview.setStyleSheet("""
                    background-color: #f8d7da; 
                    padding: 15px; 
                    border-radius: 5px;
                    font-size: 14px;
                    color: #721c24;
                """)
                return
                
            if self.weight_unit.currentText() == "mg":
                w_initial /= 1000
                w_final /= 1000
                w_waste /= 1000
            if self.time_unit.currentText() == "minutes":
                time *= 60

            sample_consumed = w_initial - w_final
            if sample_consumed <= 0:
                self.result_preview.setText("⚠️ Initial mass must be greater than final mass")
                self.result_preview.setStyleSheet("""
                    background-color: #f8d7da; 
                    padding: 15px; 
                    border-radius: 5px;
                    font-size: 14px;
                    color: #721c24;
                """)
                return
                
            volume_to_plasma = sample_consumed - w_waste
            if volume_to_plasma <= 0:
                self.result_preview.setText("⚠️ Sample consumed must be greater than waste mass")
                self.result_preview.setStyleSheet("""
                    background-color: #f8d7da; 
                    padding: 15px; 
                    border-radius: 5px;
                    font-size: 14px;
                    color: #721c24;
                """)
                return
                
            transport_rate = (volume_to_plasma * 1000) / time
            
            self.result_preview.setText(f"Calculated transport rate: {transport_rate:.6f} μL/s")
            self.result_preview.setStyleSheet("""
                background-color: #d4edda; 
                padding: 15px; 
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
                color: #155724;
            """)
            
        except ValueError:
            self.result_preview.setText("Enter valid numbers in all fields")
            self.result_preview.setStyleSheet("""
                background-color: #fff3cd; 
                padding: 15px; 
                border-radius: 5px;
                font-size: 14px;
                color: #856404;
            """)

    def calculate(self):
        """
        Calculate transport rate from user measurements and emit result.
        
        Validates all inputs, performs unit conversions, calculates the transport rate,
        and displays detailed results in a message box. Emits calibration_completed signal
        with the calculated rate.
        """
        try:
            if not all([self.initial_weight.text(), self.final_weight.text(), 
                       self.waste_weight.text(), self.analysis_time.text()]):
                QMessageBox.warning(self, "Input Error", "Please fill in all measurement fields.")
                return
                
            w_initial = float(self.initial_weight.text())
            w_final = float(self.final_weight.text())
            w_waste = float(self.waste_weight.text())
            time = float(self.analysis_time.text())
            
            if time <= 0:
                QMessageBox.warning(self, "Input Error", "Analysis time must be greater than zero.")
                return

            if self.weight_unit.currentText() == "mg":
                w_initial /= 1000
                w_final /= 1000
                w_waste /= 1000
            if self.time_unit.currentText() == "minutes":
                time *= 60

            sample_consumed = w_initial - w_final
            if sample_consumed <= 0:
                QMessageBox.warning(self, "Input Error", "Initial mass must be greater than final mass.")
                return
                
            volume_to_plasma = sample_consumed - w_waste
            if volume_to_plasma <= 0:
                QMessageBox.warning(self, "Input Error", 
                    "Sample consumed must be greater than waste collected. Please check your measurements.")
                return
                
            transport_rate = (volume_to_plasma * 1000) / time
            
            result_message = (
                f"Transport Rate: {transport_rate:.6f} μL/s\n\n"
                f"Calculation Details:\n"
                f"• Sample consumed: {sample_consumed:.5f} g\n"
                f"• Volume to plasma: {volume_to_plasma:.5f} g\n"
                f"• Analysis time: {time:.1f} seconds"
            )
            
            self.calibration_completed.emit("Weight Method", transport_rate)
            
            QMessageBox.information(self, "Calculation Results", result_message)
            
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Please enter valid numbers in all fields.")

    def submit_direct(self):
        """
        Submit a directly entered transport rate value.
        
        Validates the direct rate input and emits the calibration_completed signal
        with the user-provided rate value.
        """
        try:
            rate = float(self.direct_rate.text())
            if rate <= 0:
                QMessageBox.warning(self, "Input Error", "Transport rate must be greater than zero.")
                return
                
            self.calibration_completed.emit("Weight Method", rate)
            QMessageBox.information(
                self, 
                "Success", 
                f"Transport rate of {rate:.6f} μL/s submitted successfully."
            )
            
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Please enter a valid number.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = InputMethodCalibration()
    window.show()
    sys.exit(app.exec())