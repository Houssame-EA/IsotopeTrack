"""Multi-signal display dialog for selecting and plotting multiple ICP-MS signals simultaneously."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QCheckBox, QPushButton, QScrollArea, QWidget,
                               QColorDialog, QFrame)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
import pyqtgraph as pg
import numpy as np

class ColorButton(QPushButton):
    """
    Custom color picker button widget.
    """
    
    colorChanged = Signal(str)
    
    def __init__(self, color="#1f77b4"):
        """
        Initialize the color button.
        
        Args:
            color (str, optional): Initial color in hex format. Defaults to "#1f77b4"
            
        Returns:
            None
        """
        super().__init__()
        self.current_color = color
        self.setFixedSize(30, 25)
        self.update_color()
        self.clicked.connect(self.pick_color)
    
    def update_color(self):
        """
        Update the button appearance to reflect current color.
        
        Args:
            None
            
        Returns:
            None
        """
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.current_color};
                border: 2px solid #ccc;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid #333;
            }}
        """)
    
    def pick_color(self):
        """
        Open color picker dialog and update color.
        
        Args:
            None
            
        Returns:
            None
        """
        color = QColorDialog.getColor(QColor(self.current_color), self)
        if color.isValid():
            self.current_color = color.name()
            self.update_color()
            self.colorChanged.emit(self.current_color)
    
    def get_color(self):
        """
        Get the current color.
        
        Args:
            None
            
        Returns:
            str: Current color in hex format
        """
        return self.current_color
    
    def set_color(self, color):
        """
        Set the button color.
        
        Args:
            color (str): Color in hex format
            
        Returns:
            None
        """
        self.current_color = color
        self.update_color()

class SignalSelectorDialog(QDialog):
    """
    Dialog for selecting and configuring multiple signals for simultaneous display.
    """
    
    def __init__(self, main_window, parent=None):
        """
        Initialize the signal selector dialog.
        
        Args:
            main_window (MainWindow): Reference to main window
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.main_window = main_window
        self.signal_configs = {}
        
        self.setWindowTitle("Multi-Signal Display")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)
        self.resize(600, 700)
        
        self.setup_ui()
        self.populate_signals()
        
    def setup_ui(self):
        """
        Setup the user interface.
        
        Args:
            None
            
        Returns:
            None
        """
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        
        title = QLabel("Multi-Signal Display Configuration")
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 5px;
            }
        """)
        
        subtitle = QLabel("Select elements to display and customize their colors")
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #7f8c8d;
                margin-bottom: 10px;
            }
        """)
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        main_layout.addWidget(header_frame)
        
        signals_label = QLabel("Available Signals:")
        signals_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #34495e;
                margin: 10px 0px 5px 0px;
            }
        """)
        main_layout.addWidget(signals_label)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: white;
            }
        """)
        
        self.signals_widget = QWidget()
        self.signals_layout = QVBoxLayout(self.signals_widget)
        self.signals_layout.setSpacing(8)
        self.signals_layout.setContentsMargins(15, 15, 15, 15)
        
        scroll_area.setWidget(self.signals_widget)
        main_layout.addWidget(scroll_area)
        
        button_frame = QFrame()
        button_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        button_layout = QHBoxLayout(button_frame)
        
        select_all_btn = QPushButton("Select All")
        deselect_all_btn = QPushButton("Deselect All")
        
        for btn in [select_all_btn, deselect_all_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #95a5a6;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #7f8c8d;
                }
            """)
        
        select_all_btn.clicked.connect(self.select_all)
        deselect_all_btn.clicked.connect(self.deselect_all)
        
        plot_button = QPushButton("Plot Signals")
        cancel_button = QPushButton("Cancel")
        
        plot_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()
        button_layout.addWidget(plot_button)
        button_layout.addWidget(cancel_button)
        
        main_layout.addWidget(button_frame)
        
        plot_button.clicked.connect(self.plot_signals)
        cancel_button.clicked.connect(self.reject)
    
    def populate_signals(self):
        """
        Populate the signals list ordered by mass.
        
        Args:
            None
            
        Returns:
            None
        """
        default_colors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
            '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5'
        ]
        
        element_isotope_pairs = []
        for element, isotopes in self.main_window.selected_isotopes.items():
            for isotope in isotopes:
                element_isotope_pairs.append((element, isotope))
        
        element_isotope_pairs.sort(key=lambda x: x[1])
        
        color_index = 0
        
        for element, isotope in element_isotope_pairs:
            element_key = f"{element}-{isotope:.4f}"
            display_label = self.main_window.get_formatted_label(element_key)
            
            signal_row = QWidget()
            signal_row.setStyleSheet("""
                QWidget {
                    background-color: #ffffff;
                    border: 1px solid #e1e8ed;
                    border-radius: 6px;
                    padding: 8px;
                }
                QWidget:hover {
                    background-color: #f8f9fa;
                    border: 1px solid #3498db;
                }
            """)
            
            row_layout = QHBoxLayout(signal_row)
            row_layout.setContentsMargins(10, 8, 10, 8)
            
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                }
                QCheckBox::indicator:unchecked {
                    border: 2px solid #bdc3c7;
                    background-color: white;
                    border-radius: 3px;
                }
                QCheckBox::indicator:checked {
                    border: 2px solid #3498db;
                    background-color: #3498db;
                    border-radius: 3px;
                }
            """)
            
            label = QLabel(display_label)
            label.setStyleSheet("""
                QLabel {
                    font-size: 13px;
                    font-weight: 500;
                    color: #2c3e50;
                    margin-left: 8px;
                }
            """)
            
            color_button = ColorButton(default_colors[color_index % len(default_colors)])
            
            self.signal_configs[element_key] = {
                'checkbox': checkbox,
                'color_btn': color_button,
                'display_label': display_label,
                'element': element,
                'isotope': isotope
            }
            
            row_layout.addWidget(checkbox)
            row_layout.addWidget(label)
            row_layout.addStretch()
            row_layout.addWidget(QLabel("Color:"))
            row_layout.addWidget(color_button)
            
            self.signals_layout.addWidget(signal_row)
            color_index += 1
        
        self.signals_layout.addStretch()
        
    def select_all(self):
        """
        Select all signal checkboxes.
        
        Args:
            None
            
        Returns:
            None
        """
        for config in self.signal_configs.values():
            config['checkbox'].setChecked(True)
    
    def deselect_all(self):
        """
        Deselect all signal checkboxes.
        
        Args:
            None
            
        Returns:
            None
        """
        for config in self.signal_configs.values():
            config['checkbox'].setChecked(False)
    
    def plot_signals(self):
        """
        Plot all selected signals with optimized performance.
        
        Uses efficient batch plotting by grouping particles by color to minimize
        the number of scatter plot items created.
        
        Args:
            None
            
        Returns:
            None
        """
        selected_configs = {}
        for element_key, config in self.signal_configs.items():
            if config['checkbox'].isChecked():
                selected_configs[element_key] = {
                    'color': config['color_btn'].get_color(),
                    'display_label': config['display_label'],
                    'element': config['element'],
                    'isotope': config['isotope']
                }
        
        if not selected_configs:
            return
            
        self.main_window.plot_widget.clear()
        self.main_window.plot_widget.setBackground('w')
        self.main_window.plot_widget.showGrid(x=False, y=False, alpha=0.2)
        self.main_window.plot_widget.setLabel('left', 'Counts')
        self.main_window.plot_widget.setLabel('bottom', 'Time (s)')
    
        legend = self.main_window.plot_widget.addLegend(offset=(15, 15))
        
        particles_by_color = {}
        
        for element_key, config in selected_configs.items():
            element = config['element']
            isotope = config['isotope']
            color = config['color']
            display_label = config['display_label']
            
            closest_mass = self.main_window.find_closest_isotope(isotope)
            if closest_mass is None or closest_mass not in self.main_window.data:
                continue
                
            signal = self.main_window.data[closest_mass]
            time_array = self.main_window.time_array
            
            self.main_window.plot_widget.plot(
                time_array,
                signal,
                pen=pg.mkPen(color, width=1),
                name=display_label,
                antialias=True
            )
            
            if (element, isotope) in self.main_window.detected_peaks:
                particles = self.main_window.detected_peaks[(element, isotope)]
                if particles:
                    if color not in particles_by_color:
                        particles_by_color[color] = {'times': [], 'heights': []}
                    
                    for particle in particles:
                        if particle is None:
                            continue
                        
                        left_idx = particle['left_idx']
                        right_idx = particle['right_idx']
                        peak_idx = left_idx + np.argmax(signal[left_idx:right_idx+1])
                        
                        particles_by_color[color]['times'].append(time_array[peak_idx])
                        particles_by_color[color]['heights'].append(signal[peak_idx])
        
        for color, particle_data in particles_by_color.items():
            if particle_data['times']:
                times = np.array(particle_data['times'])
                heights = np.array(particle_data['heights'])
                
                scatter = pg.ScatterPlotItem(
                    x=times,
                    y=heights,
                    symbol='o',
                    size=6,
                    brush=pg.mkBrush(color),
                    pen=pg.mkPen(255, 255, 255, 100, width=1)
                )
                self.main_window.plot_widget.addItem(scatter)
        
        self.main_window.plot_widget.setMouseEnabled(x=True, y=True)
        self.main_window.plot_widget.enableAutoRange()
        self.accept()