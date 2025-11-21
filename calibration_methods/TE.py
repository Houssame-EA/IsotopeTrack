import sys
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QComboBox, QLabel, QMessageBox, 
                               QWidget, QToolButton, QScrollArea, QFrame)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, Signal

from calibration_methods.TE_input import InputMethodCalibration
from calibration_methods.TE_number import NumberMethodWidget
from calibration_methods.TE_mass import MassMethodWidget
import qtawesome as qta

class ModernWidget(QWidget):
    def __init__(self, parent=None):
        """
        Initialize a modern styled widget.
        
        Args:
            parent: Parent widget for this widget
        """
        super().__init__(parent)

class TransportRateCalibrationWindow(QDialog):
    calibration_completed = Signal(str, float)

    def __init__(self, selected_methods, parent=None):
        """
        Initialize the Transport Rate Calibration Window.
        
        Args:
            selected_methods: List of calibration method names to display
            parent: Parent widget for this dialog
        """
        super().__init__(parent)
        self.setWindowTitle("Transport Rate Calibration")
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        
        self.closeEvent = self.handle_close
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QToolButton {
                border: none;
                padding: 5px;
            }
            QToolButton:hover {
                background-color: #f0f0f0;
                border-radius: 3px;
            }
        """)
        self.selected_methods = selected_methods
        self.initUI()
        self.showMaximized()
        
    def handle_close(self, event):
        """
        Handle the window close event by hiding instead of closing.
        
        Args:
            event: The close event object
        """
        event.ignore()
        self.hide()

    def initUI(self):
        """
        Initialize and configure the user interface.
        
        Sets up the main layout, header section with return button, method selection
        dropdown, content area for calibration widgets, and connects all signals.
        """
        main_widget = ModernWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        header_layout = QHBoxLayout()
        
        title = QLabel("Transport Rate Calibration")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 10px;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        return_button = QPushButton("Back to Main")
        return_button.setIcon(qta.icon('fa6s.house', color="#B81414"))
        return_button.setFixedSize(150, 45)
        return_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #FF6B6B, stop:0.5 #FF8E53, stop:1 #FF6B9D);
                color: white;
                border: 3px solid #FF4081;
                padding: 8px 16px;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
                border-radius: 22px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #FF5252, stop:0.5 #FF7043, stop:1 #FF4081);
                border: 3px solid #E91E63;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #E53935, stop:0.5 #FF5722, stop:1 #E91E63);
                border: 3px solid #AD1457;
                padding: 9px 15px 7px 17px;
            }
        """)
        return_button.clicked.connect(self.hide)
        header_layout.addWidget(return_button)

        main_layout.addLayout(header_layout)

        method_layout = QHBoxLayout()
        method_label = QLabel("Select Method:")
        self.method_combo = QComboBox()
        self.method_combo.addItems(self.selected_methods)
        
        method_layout.addWidget(method_label)
        method_layout.addWidget(self.method_combo)
        method_layout.addStretch()
        
        main_layout.addLayout(method_layout)

        self.method_content = QWidget()
        self.method_content_layout = QVBoxLayout(self.method_content)
        
        self.method_widgets = {
            "Liquid weight": InputMethodCalibration(),
            "Number based": NumberMethodWidget(),
            "Mass based": MassMethodWidget()
        }
        
        for widget in self.method_widgets.values():
            widget.calibration_completed.connect(self.on_calibration_completed)
        
        if self.selected_methods:
            self.method_content_layout.addWidget(self.method_widgets[self.selected_methods[0]])
        
        main_layout.addWidget(self.method_content)

        scroll = QScrollArea()
        scroll.setWidget(main_widget)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(scroll)

        self.method_combo.currentIndexChanged.connect(self.show_selected_method)
        
        self.setMinimumSize(800, 600)

    def show_selected_method(self, index):
        """
        Display the calibration widget for the selected method.
        
        Args:
            index: Index of the selected method in the combo box
        """
        for i in reversed(range(self.method_content_layout.count())):
            self.method_content_layout.itemAt(i).widget().setParent(None)
        
        if index >= 0 and index < len(self.selected_methods):
            selected_method = self.selected_methods[index]
        else:
            selected_method = self.method_combo.currentText()
            if not selected_method or selected_method not in self.method_widgets:
                print(f"Warning: Invalid method selection: '{selected_method}'")
                if self.selected_methods:
                    selected_method = self.selected_methods[0]
                else:
                    return
        
        if selected_method in self.method_widgets:
            self.method_content_layout.addWidget(self.method_widgets[selected_method])
        else:
            print(f"Error: Method widget not found for: '{selected_method}'")
            print(f"Available methods: {list(self.method_widgets.keys())}")
            print(f"Selected methods: {self.selected_methods}")

    def on_calibration_completed(self, method, transport_rate):
        """
        Handle calibration completion from any calibration method widget.
        
        Args:
            method: Name of the calibration method that was completed
            transport_rate: Calculated transport rate value in μL/s
        """
        method_map = {
            "Liquid weight": "Weight Method",
            "Number based": "Particle Method",
            "Mass based": "Mass Method"
        }
        standardized_method = method_map.get(method, method)
        self.calibration_completed.emit(standardized_method, transport_rate)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TransportRateCalibrationWindow(["Liquid weight", "Number based", "Mass based"])
    window.showMaximized()
    sys.exit(app.exec())