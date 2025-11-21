"""File information display dialogs and menus for viewing method and run information."""
from PySide6.QtWidgets import (QMenu, QDialog, QVBoxLayout, QTextEdit, QLabel, 
                              QScrollArea, QWidget, QFrame, QPushButton, QHBoxLayout)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette, QColor, QIcon
from pathlib import Path
import json
import numpy as np

class FileInfoDialog(QDialog):
    """
    Dialog for displaying detailed file information including method and acquisition parameters.
    """
    
    def __init__(self, sample_name, run_info, method_info, time_array, masses, parent=None):
        """
        Initialize the file information dialog.
        
        Args:
            sample_name (str): Name of the sample
            run_info (dict): Run information dictionary
            method_info (dict): Method information dictionary
            time_array (np.ndarray): Time array data
            masses (np.ndarray): Mass array data
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.sample_name = sample_name
        self.run_info = run_info
        self.method_info = method_info
        self.time_array = time_array
        self.masses = masses
        
        self.setWindowTitle(f"Method Information - {sample_name}")
        self.setMinimumSize(900, 700)
        self.setup_ui()
        self.load_file_info()

    def setup_ui(self):
        """
        Setup the user interface.
        
        Args:
            None
            
        Returns:
            None
        """
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #f8f9fa, stop:1 #e9ecef);
            }
            QLabel {
                color: #2c3e50;
            }
            QTextEdit {
                border: none;
                background-color: #ffffff;
                font-size: 14px;
                line-height: 1.6;
                border-radius: 8px;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 15px;
                padding: 25px;
            }
        """)
        header_layout = QHBoxLayout(header)
        
        title_section = QVBoxLayout()
        title = QLabel("Method & Acquisition Information")
        title.setStyleSheet("""
            color: white;
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 5px;
        """)
        title_section.addWidget(title)
        
        subtitle = QLabel(f"Sample: {self.sample_name}")
        subtitle.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-size: 18px;")
        title_section.addWidget(subtitle)
        
        header_layout.addLayout(title_section)
        header_layout.addStretch()
        
        layout.addWidget(header)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 12px;
            }
            QScrollBar:vertical {
                border: none;
                background: #f1f3f4;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #c1c8cd;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a8b2bd;
            }
        """)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        scroll_area.setWidget(self.info_text)
        layout.addWidget(scroll_area)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)

    def load_file_info(self):
        """
        Load and display file information in HTML format.
        
        Args:
            None
            
        Returns:
            None
        """
        try:
            if not self.run_info:
                self.info_text.setHtml("""
                    <div style="padding: 40px; text-align: center;">
                        <h2 style="color: #e74c3c;">⚠️ No Run Information Available</h2>
                        <p style="color: #7f8c8d; font-size: 16px;">
                            Run information was not stored with this sample data.
                        </p>
                    </div>
                """)
                return

            seg = self.run_info["SegmentInfo"][0]
            acqtime = seg["AcquisitionPeriodNs"] * 1e-9
            accumulations = self.run_info["NumAccumulations1"] * self.run_info["NumAccumulations2"]
            dwell_time = acqtime * accumulations
            total_time = self.time_array[-1] - self.time_array[0] if self.time_array is not None else 0

            info_text = """
            <style>
                body { 
                    margin: 0; 
                    padding: 20px;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                    min-height: 100vh;
                }
                .container { 
                    max-width: 1000px;
                    margin: 0 auto;
                }
                .section {
                    margin: 20px 0;
                    background: white;
                    border-radius: 15px;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.1);
                    overflow: hidden;
                    transition: transform 0.3s ease;
                }
                .section:hover {
                    transform: translateY(-2px);
                }
                .header {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    font-size: 20px;
                    font-weight: bold;
                    padding: 20px 25px;
                    margin: 0;
                    display: flex;
                    align-items: center;
                }
                .header::before {
                    content: attr(data-icon);
                    font-size: 24px;
                    margin-right: 12px;
                }
                .content {
                    padding: 25px;
                    line-height: 1.8;
                }
                .parameter {
                    display: flex;
                    justify-content: space-between;
                    margin: 15px 0;
                    padding: 10px 15px;
                    background: #f8f9fa;
                    border-radius: 8px;
                    border-left: 4px solid #667eea;
                }
                .parameter-label {
                    font-weight: 600;
                    color: #2c3e50;
                }
                .parameter-value {
                    color: #667eea;
                    font-weight: bold;
                }
                .unit {
                    color: #7f8c8d;
                    font-style: italic;
                    margin-left: 5px;
                }
                .subsection {
                    margin: 20px 0;
                    padding: 20px;
                    background: linear-gradient(135deg, #ffeef8 0%, #f0f8ff 100%);
                    border-radius: 10px;
                    border: 1px solid #e1e8ed;
                }
                .subsection h3 {
                    color: #5d4e75;
                    margin: 0 0 15px 0;
                    font-size: 18px;
                    display: flex;
                    align-items: center;
                }
                .subsection h3::before {
                    content: "⚙️";
                    margin-right: 8px;
                }
                .grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 15px;
                    margin: 15px 0;
                }
                .card {
                    background: white;
                    padding: 15px;
                    border-radius: 8px;
                    border: 1px solid #e1e8ed;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                }
                .highlight {
                    background: linear-gradient(135deg, #ffeaa7 0%, #fab1a0 100%);
                    color: #2d3436;
                    padding: 20px;
                    border-radius: 10px;
                    text-align: center;
                    margin: 20px 0;
                    font-weight: bold;
                    font-size: 18px;
                }
                .status-enabled {
                    color: #27ae60;
                    font-weight: bold;
                }
                .status-disabled {
                    color: #e74c3c;
                    font-weight: bold;
                }
            </style>
            <body>
            <div class="container">
            """

            info_text += f"""
            <div class="highlight">
                <strong>{len(self.time_array):,}</strong> data points 
                over <strong>{total_time/60:.1f}</strong> minutes
            </div>
            """

            if self.method_info:
                segment = self.method_info["Segments"][0]
                info_text += self._create_method_section(segment)

            info_text += f"""
            <div class="section">
                <div class="header" data-icon="📊">Acquisition Parameters</div>
                <div class="content">
                    <div class="grid">
                        <div class="parameter">
                            <span class="parameter-label">Dwell Time</span>
                            <span class="parameter-value">{dwell_time*1000:.3f}<span class="unit">ms</span></span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">Total Acquisition Time</span>
                            <span class="parameter-value">{total_time:.2f}<span class="unit">seconds</span> ({total_time/60:.1f}<span class="unit">min</span>)</span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">Total Data Points</span>
                            <span class="parameter-value">{len(self.time_array):,}</span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">Sampling Rate</span>
                            <span class="parameter-value">{1/(dwell_time):.1f}<span class="unit">Hz</span></span>
                        </div>
                    </div>
                </div>
            </div>
            """

            if self.masses is not None and len(self.masses) > 0:
                info_text += f"""
                <div class="section">
                    <div class="header" data-icon="⚗️">Mass Analysis Configuration</div>
                    <div class="content">
                        <div class="grid">
                            <div class="parameter">
                                <span class="parameter-label">Mass Range</span>
                                <span class="parameter-value">{min(self.masses):.3f} - {max(self.masses):.3f}<span class="unit">amu</span></span>
                            </div>
                            <div class="parameter">
                                <span class="parameter-label">Mass Points</span>
                                <span class="parameter-value">{len(self.masses)}</span>
                            </div>
                            <div class="parameter">
                                <span class="parameter-label">Mass Resolution</span>
                                <span class="parameter-value">{(max(self.masses) - min(self.masses))/len(self.masses):.4f}<span class="unit">amu/point</span></span>
                            </div>
                            <div class="parameter">
                                <span class="parameter-label">Mass Step Size</span>
                                <span class="parameter-value">{np.median(np.diff(self.masses)):.4f}<span class="unit">amu</span></span>
                            </div>
                        </div>
                    </div>
                </div>
                """

            info_text += self._create_run_info_section()

            info_text += "</div></body>"
            self.info_text.setHtml(info_text)

        except Exception as e:
            error_text = f"""
            <div style="padding: 40px; background: linear-gradient(135deg, #ffebee 0%, #fce4ec 100%); 
                        border-radius: 15px; text-align: center; margin: 20px;">
                <h2 style="color: #c62828; margin-bottom: 20px;">🚨 Error Loading Information</h2>
                <div style="background: white; padding: 20px; border-radius: 10px; border-left: 5px solid #f44336;">
                    <code style="color: #b71c1c; font-size: 14px;">{str(e)}</code>
                </div>
                <p style="color: #757575; margin-top: 20px; font-style: italic;">
                    This may occur with older project files or corrupted data.
                </p>
            </div>
            """
            self.info_text.setHtml(error_text)

    def _create_method_section(self, segment):
        """
        Create HTML section for method configuration.
        
        Args:
            segment (dict): Segment configuration dictionary
            
        Returns:
            str: HTML string for method section
        """
        hex_config = segment["HexapoleConfig"]
        quad_config = segment["QuadrupoleConfig"]
        ab_config = segment["AutoBlankingConfig"]
        
        return f"""
        <div class="section">
            <div class="header" data-icon="🔬">Method Configuration</div>
            <div class="content">
                <div class="subsection">
                    <h3>Data Acquisition Setup</h3>
                    <div class="grid">
                        <div class="parameter">
                            <span class="parameter-label">Mass Range</span>
                            <span class="parameter-value">{segment['StartMass']:.1f} - {segment['EndMass']:.1f}<span class="unit">amu</span></span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">Total Acquisitions</span>
                            <span class="parameter-value">{segment['AcquisitionCount']:,}</span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">Acquisition Period</span>
                            <span class="parameter-value">{segment['AcquisitionPeriod']}<span class="unit">ns</span></span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">Tick Frequency</span>
                            <span class="parameter-value">{self.method_info['InstrumentTickFrequencyNs']}<span class="unit">ns</span></span>
                        </div>
                    </div>
                </div>

                <div class="subsection">
                    <h3>Hexapole Configuration</h3>
                    <div class="grid">
                        <div class="parameter">
                            <span class="parameter-label">Cell Entrance Voltage</span>
                            <span class="parameter-value">{hex_config['CellEntranceVoltage']:.1f}<span class="unit">V</span></span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">Entrance Aperture</span>
                            <span class="parameter-value">{hex_config['EntranceApertureVoltage']:.1f}<span class="unit">V</span></span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">Exit Aperture</span>
                            <span class="parameter-value">{hex_config['ExitApertureVoltage']:.1f}<span class="unit">V</span></span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">Cell Exit Voltage</span>
                            <span class="parameter-value">{hex_config['CellExitVoltage']:.1f}<span class="unit">V</span></span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">RF Reference</span>
                            <span class="parameter-value">{hex_config['RfReference']:.1f}</span>
                        </div>
                    </div>
                </div>

                <div class="subsection">
                    <h3>Quadrupole Settings</h3>
                    <div class="grid">
                        <div class="parameter">
                            <span class="parameter-label">Bias Voltage</span>
                            <span class="parameter-value">{quad_config['BiasVoltage']:.1f}<span class="unit">V</span></span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">RF Reference</span>
                            <span class="parameter-value">{quad_config['RfReference']:.1f}</span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">DC Reference</span>
                            <span class="parameter-value">{quad_config['DcReference']:.1f}</span>
                        </div>
                    </div>
                </div>

                <div class="subsection">
                    <h3>Autoblanking Configuration</h3>
                    <div class="grid">
                        <div class="parameter">
                            <span class="parameter-label">Status</span>
                            <span class="parameter-value {'status-enabled' if ab_config['IsEnabled'] else 'status-disabled'}">
                                {'✅ Enabled' if ab_config['IsEnabled'] else '❌ Disabled'}
                            </span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">Blanker</span>
                            <span class="parameter-value">{ab_config['BlankerToUse']}</span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">Combine Threshold</span>
                            <span class="parameter-value">{ab_config['CombineThreshold']}</span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">Filter Threshold</span>
                            <span class="parameter-value">{ab_config['FilterThreshold']}</span>
                        </div>
                        <div class="parameter">
                            <span class="parameter-label">Min Blanking Width</span>
                            <span class="parameter-value">{ab_config['MinBlankingWidth']}</span>
                        </div>
                    </div>
                </div>

                {'<div class="subsection"><h3>Skip Mass Ranges</h3><div class="grid">' + 
                 ''.join([f'<div class="parameter"><span class="parameter-label">Range {i+1}</span><span class="parameter-value">{r["StartMass"]:.1f} - {r["EndMass"]:.1f}<span class="unit">amu</span></span></div>' 
                         for i, r in enumerate(segment.get("SkipMassRanges", []))]) + 
                 '</div></div>' if segment.get("SkipMassRanges") else ''}
            </div>
        </div>
        """

    def _create_run_info_section(self):
        """
        Create HTML section for run information.
        
        Args:
            None
            
        Returns:
            str: HTML string for run info section
        """
        segments = self.run_info["SegmentInfo"]
        
        segment_info = ""
        if len(segments) > 1:
            segment_info = '<div class="grid">'
            for segment in segments:
                segment_info += f'''
                <div class="card">
                    <h4>Segment {segment['Num']}</h4>
                    <div class="parameter">
                        <span class="parameter-label">Trigger Delay</span>
                        <span class="parameter-value">{segment['AcquisitionTriggerDelayNs']/1000:.2f}<span class="unit">μs</span></span>
                    </div>
                    <div class="parameter">
                        <span class="parameter-label">Acquisition Period</span>
                        <span class="parameter-value">{segment['AcquisitionPeriodNs']/1000:.2f}<span class="unit">μs</span></span>
                    </div>
                </div>
                '''
            segment_info += '</div>'
        
        return f"""
        <div class="section">
            <div class="header" data-icon="📋">Run Information</div>
            <div class="content">
                <div class="grid">
                    <div class="parameter">
                        <span class="parameter-label">Number of Segments</span>
                        <span class="parameter-value">{len(segments)}</span>
                    </div>
                    <div class="parameter">
                        <span class="parameter-label">Base Acquisition Period</span>
                        <span class="parameter-value">{segments[0]["AcquisitionPeriodNs"]/1000:.2f}<span class="unit">μs</span></span>
                    </div>
                    <div class="parameter">
                        <span class="parameter-label">Accumulations 1</span>
                        <span class="parameter-value">{self.run_info['NumAccumulations1']}</span>
                    </div>
                    <div class="parameter">
                        <span class="parameter-label">Accumulations 2</span>
                        <span class="parameter-value">{self.run_info['NumAccumulations2']}</span>
                    </div>
                </div>
                {segment_info}
            </div>
        </div>
        """

class FileInfoMenu:
    """
    Static class for creating file information menus and dialogs.
    """
    
    @staticmethod
    def create_menu(sample_name, run_info, method_info, time_array, masses, parent=None):
        """
        Create a menu with file information action.
        
        Args:
            sample_name (str): Name of the sample
            run_info (dict): Run information dictionary
            method_info (dict): Method information dictionary
            time_array (np.ndarray): Time array data
            masses (np.ndarray): Mass array data
            parent (QWidget, optional): Parent widget
            
        Returns:
            QMenu: Created menu
        """
        menu = QMenu(parent)
        info_action = menu.addAction("Show Method Information")
        info_action.triggered.connect(lambda: FileInfoMenu.show_file_info(
            sample_name, run_info, method_info, time_array, masses, parent
        ))
        return menu

    @staticmethod
    def show_file_info(sample_name, run_info, method_info, time_array, masses, parent=None):
        """
        Show the file information dialog.
        
        Args:
            sample_name (str): Name of the sample
            run_info (dict): Run information dictionary
            method_info (dict): Method information dictionary
            time_array (np.ndarray): Time array data
            masses (np.ndarray): Mass array data
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        dialog = FileInfoDialog(sample_name, run_info, method_info, time_array, masses, parent)
        dialog.exec()