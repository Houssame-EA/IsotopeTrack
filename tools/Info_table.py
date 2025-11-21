"""Information tooltip widget for displaying sample analysis statistics and quality metrics."""
from PySide6.QtWidgets import (QVBoxLayout, QWidget, QLabel, QHBoxLayout, QScrollArea,
                               QDialog, QTableWidget, QTableWidgetItem, QCheckBox, 
                               QComboBox, QPushButton, QGroupBox, QHeaderView, 
                               QTabWidget, QProgressBar, QFrame, QSpinBox, QTextEdit,
                               QSplitter, QGridLayout, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QColor, QBrush, QFont
import numpy as np
import json
from pathlib import Path

class InfoTooltip(QWidget):
    """
    Custom tooltip widget for displaying sample analysis information and quality metrics.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the information tooltip widget.
        
        Args:
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setup_ui()
        self.cached_stats = {}
        self.cached_isotopes = {}
        
    def setup_ui(self):
        """
        Setup the user interface.
        
        Args:
            None
            
        Returns:
            None
        """
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(25, 25, 25, 25)
        self.main_layout.setSpacing(20)
        
        self.datetime_widget = QWidget()
        self.datetime_layout = QVBoxLayout(self.datetime_widget)
        self.datetime_layout.setSpacing(5)
        
        self.date_label = QLabel("Analysis Date: Not available")
        self.time_label = QLabel("Analysis Time: Not available")
        
        self.date_label.setStyleSheet("font-size: 15px; font-weight: bold; color: black;")
        self.time_label.setStyleSheet("font-size: 15px; font-weight: bold; color: black;")
        
        self.datetime_layout.addWidget(self.date_label)
        self.datetime_layout.addWidget(self.time_label)
        
        self.datetime_widget.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        
        self.main_layout.addWidget(self.datetime_widget)
        self.datetime_widget.setVisible(False)
        
        self.stats_widget = QWidget()
        self.stats_layout = QHBoxLayout(self.stats_widget)
        self.stats_layout.setSpacing(20)
        
        self.stat_boxes = {}
        stat_types = ["Active Samples", "Elements", "Suspected %", "Quality Score"]
        for stat_type in stat_types:
            stat_box = self.create_stat_box()
            self.stat_boxes[stat_type] = stat_box
            self.stats_layout.addWidget(stat_box)
        
        self.main_layout.addWidget(self.stats_widget)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setMinimumHeight(200)
        self.scroll_area.setMaximumHeight(600)
        
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(255, 255, 255, 0.1);
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.3);
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        self.sample_content = QWidget()
        self.sample_layout = QVBoxLayout(self.sample_content)
        self.scroll_area.setWidget(self.sample_content)
        self.main_layout.addWidget(self.scroll_area)
        
        self.setFixedWidth(700)
        
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8860D0, stop:1 #5AB9EA);
                border-radius: 20px;
            }
        """)

    def create_stat_box(self):
        """
        Create a statistics display box.
        
        Args:
            None
            
        Returns:
            QWidget: Created stat box widget
        """
        stat_box = QWidget()
        stat_layout = QVBoxLayout(stat_box)
        
        value_label = QLabel()
        desc_label = QLabel()
        
        value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        desc_label.setStyleSheet("font-size: 11px; color: rgba(255, 255, 255, 0.8);")
        
        stat_layout.addWidget(value_label)
        stat_layout.addWidget(desc_label)
        
        stat_box.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 12px;
            }
        """)
        
        return stat_box
        
    def update_stats(self, active_samples, total_elements, Suspected_percentage, analysis_date_info=None):
        """
        Update the statistics display.
        
        Args:
            active_samples (int): Number of active samples
            total_elements (int): Total number of elements
            Suspected_percentage (float): Percentage of suspected values
            analysis_date_info (dict, optional): Dictionary with 'date' and 'time' keys
            
        Returns:
            None
        """
        quality_score = max(0, 100 - Suspected_percentage)
        
        new_stats = {
            "Active Samples": str(active_samples),
            "Elements": str(total_elements),
            "Suspected %": f"{Suspected_percentage}%",
            "Quality Score": f"{quality_score:.0f}"
        }
        
        if analysis_date_info:
            self.datetime_widget.setVisible(True)
            if 'date' in analysis_date_info:
                self.date_label.setText(f"Analysis Date: {analysis_date_info['date']}")
            if 'time' in analysis_date_info:
                self.time_label.setText(f"Analysis Time: {analysis_date_info['time']}")
        else:
            self.datetime_widget.setVisible(False)
        
        if new_stats != self.cached_stats:
            self.cached_stats = new_stats
            for stat_type, value in new_stats.items():
                stat_box = self.stat_boxes[stat_type]
                value_label = stat_box.layout().itemAt(0).widget()
                desc_label = stat_box.layout().itemAt(1).widget()
                
                if stat_type == "Suspected %":
                    Suspected_value = float(value.strip('%'))
                    if Suspected_value >= 50:
                        value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #FF4444;")
                    elif Suspected_value >= 30:
                        value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #FFAA33;")
                    else:
                        value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #44FF44;")
                elif stat_type == "Quality Score":
                    score = float(value)
                    if score >= 70:
                        value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #44FF44;")
                    elif score >= 50:
                        value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #FFAA33;")
                    else:
                        value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #FF4444;")
                
                value_label.setText(value)
                desc_label.setText(stat_type)

    def update_sample_content(self, current_sample, selected_isotopes, detected_peaks, multi_element_particles):
        """
        Update the sample content display with isotope information and quality metrics.
        
        Args:
            current_sample (str): Name of current sample
            selected_isotopes (dict): Dictionary of selected isotopes by element
            detected_peaks (dict): Dictionary of detected peaks
            multi_element_particles (list): List of multi-element particles
            
        Returns:
            None
        """
        new_isotopes = {
            'sample': current_sample,
            'isotopes': selected_isotopes.copy() if selected_isotopes else {},
            'peaks': detected_peaks.copy() if detected_peaks else {},
            'multi': len(multi_element_particles) if multi_element_particles else 0
        }
        
        if new_isotopes == self.cached_isotopes:
            return
            
        self.cached_isotopes = new_isotopes
        
        for i in reversed(range(self.sample_layout.count())):
            self.sample_layout.itemAt(i).widget().setParent(None)
            
        if not current_sample:
            return
            
        sample_box = QWidget()
        sample_layout = QVBoxLayout(sample_box)
        
        sample_title = QLabel(f"Current Sample: {current_sample}")
        sample_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        sample_layout.addWidget(sample_title)
        
        if selected_isotopes:
            total_particles = 0
            total_strong = 0
            element_count = 0
            valid_elements = 0
            
            for element, isotopes in selected_isotopes.items():
                for isotope in isotopes:
                    element_count += 1
                    peaks = detected_peaks.get((element, isotope), [])
                    peak_count = len(peaks)
                    total_particles += peak_count
                    
                    isotope_widget = QWidget()
                    isotope_layout = QHBoxLayout(isotope_widget)
                    
                    if peak_count < 5:
                        if peak_count == 0:
                            color = "gray"
                            status = "No Data"
                        else:
                            color = "lightblue"
                            status = f"Too Few ({peak_count})"
                        
                        indicator = QLabel("●")
                        indicator.setStyleSheet(f"color: {color}; font-size: 16px;")
                        isotope_layout.addWidget(indicator, 0, Qt.AlignLeft)
                        
                        element_label = QLabel(f"{element}-{isotope:.3f}")
                        element_label.setStyleSheet("color: white; font-weight: bold;")
                        isotope_layout.addWidget(element_label, 1)
                        
                        stats_text = f"{peak_count} particles | {status}"
                        stats_label = QLabel(stats_text)
                        stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-size: 11px;")
                        isotope_layout.addWidget(stats_label, 0, Qt.AlignRight)
                    else:
                        valid_elements += 1
                        strong_peaks = sum(1 for p in peaks if p.get('SNR', 0) >= 1.5)
                        total_strong += strong_peaks
                        
                        strong_percentage = (strong_peaks / peak_count * 100) if peak_count > 0 else 0
                        Suspected_percentage = 100 - strong_percentage
                        
                        if Suspected_percentage >= 50:
                            color = "red"
                            status = "Poor"
                        elif Suspected_percentage >= 30:
                            color = "yellow"
                            status = "Warning"
                        else:
                            color = "lime"
                            status = "Good"
                        
                        indicator = QLabel("●")
                        indicator.setStyleSheet(f"color: {color}; font-size: 16px;")
                        isotope_layout.addWidget(indicator, 0, Qt.AlignLeft)
                        
                        element_label = QLabel(f"{element}-{isotope:.3f}")
                        element_label.setStyleSheet("color: white; font-weight: bold;")
                        isotope_layout.addWidget(element_label, 1)
                        
                        stats_text = f"{strong_peaks}/{peak_count} strong ({strong_percentage:.1f}%) | {status}"
                        stats_label = QLabel(stats_text)
                        stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-size: 11px;")
                        isotope_layout.addWidget(stats_label, 0, Qt.AlignRight)
                    
                    sample_layout.addWidget(isotope_widget)
            
            if valid_elements > 0:
                overall_widget = QWidget()
                overall_layout = QVBoxLayout(overall_widget)
                
                overall_title = QLabel("Overall Statistics (5+ particles only)")
                overall_title.setStyleSheet("font-size: 14px; font-weight: bold; color: white; margin-top: 10px;")
                overall_layout.addWidget(overall_title)
                
                overall_strong_pct = (total_strong / total_particles * 100) if total_particles > 0 else 0
                overall_Suspected_pct = 100 - overall_strong_pct
                
                stats_text = f"Total peaks: {total_particles} | Strong Signals: {overall_strong_pct:.1f}% | Valid Elements: {valid_elements}/{element_count}"
                overall_stats = QLabel(stats_text)
                overall_stats.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-size: 12px;")
                overall_layout.addWidget(overall_stats)
                
                if overall_Suspected_pct <= 10:
                    quality_text = "Quality: Excellent"
                    quality_color = "lime"
                elif overall_Suspected_pct <= 30:
                    quality_text = "Quality: Good"
                    quality_color = "lightgreen"
                elif overall_Suspected_pct <= 50:
                    quality_text = "Quality: Fair"
                    quality_color = "yellow"
                else:
                    quality_text = "Quality: Needs Attention"
                    quality_color = "red"
                    
                quality_label = QLabel(quality_text)
                quality_label.setStyleSheet(f"color: {quality_color}; font-size: 12px; font-weight: bold;")
                overall_layout.addWidget(quality_label)
                
                overall_widget.setStyleSheet("""
                    QWidget {
                        background: rgba(255, 255, 255, 0.05);
                        border-radius: 8px;
                        padding: 8px;
                        margin-top: 5px;
                    }
                """)
                sample_layout.addWidget(overall_widget)
                
        sample_box.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 15px;
            }
        """)
        self.sample_layout.addWidget(sample_box)
        
        if multi_element_particles is not None:
            multi_box = QWidget()
            multi_layout = QVBoxLayout(multi_box)
            
            multi_title = QLabel("Multi-element Particles")
            multi_count = QLabel(str(len(multi_element_particles)))
            
            multi_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
            multi_count.setStyleSheet("font-size: 24px; color: white; margin-top: 5px;")
            
            multi_layout.addWidget(multi_title)
            multi_layout.addWidget(multi_count)
            
            if len(multi_element_particles) > 0:
                complexity_text = f"Sample Complexity: {'High' if len(multi_element_particles) > 100 else 'Medium' if len(multi_element_particles) > 20 else 'Low'}"
                complexity_label = QLabel(complexity_text)
                complexity_label.setStyleSheet("font-size: 11px; color: rgba(255, 255, 255, 0.8);")
                multi_layout.addWidget(complexity_label)
            
            multi_box.setStyleSheet("""
                QWidget {
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 10px;
                    padding: 15px;
                }
            """)
            self.sample_layout.addWidget(multi_box)