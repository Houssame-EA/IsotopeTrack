"""Help system and interactive educational dialogs for ICP-MS analysis methods."""
from PySide6.QtWidgets import (QApplication, QDialog, QTabWidget, QTextEdit, QVBoxLayout, 
                              QPushButton, QMainWindow, QLabel, QScrollArea, QWidget, QHBoxLayout,
                              QSlider, QSpinBox, QComboBox, QFrame, QSplitter, 
                              QGridLayout, QGroupBox, QCheckBox, QFileDialog, QDoubleSpinBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QFont
import sys
import numpy as np
import pyqtgraph as pg
import csv
from pathlib import Path
from statistics import NormalDist
from processing.peak_detection import CompoundPoissonLognormal
import sys

from tools.tutorial import UserGuideDialog

def get_resource_path(relative_path):
    """    
    Args:
        relative_path (str): Relative path to resource
        
    Returns:
        Path: Absolute path to resource
    """
    try:
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        base_path = Path(__file__).parent.parent
    
    return base_path / relative_path


class HelpManager:
    """
    Manager class for all help dialogs.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the help manager.
        
        Args:
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        self.parent = parent
        self.user_guide_dialog = None
        self.detection_dialog = None
        self.calibration_dialog = None
        
    def show_user_guide(self):
        """
        Show the user guide dialog.
        
        Args:
            None
            
        Returns:
            None
        """
        if not self.user_guide_dialog:
            self.user_guide_dialog = UserGuideDialog(self.parent)
        self.user_guide_dialog.show()
        self.user_guide_dialog.raise_()
        
    def show_detection_methods(self):
        """
        Show the detection methods dialog.
        
        Args:
            None
            
        Returns:
            None
        """
        if not self.detection_dialog:
            self.detection_dialog = DetectionMethodsDialog(self.parent)
        self.detection_dialog.show()
        self.detection_dialog.raise_()
        
    def show_calibration_methods(self):
        """
        Show the calibration methods dialog.
        
        Args:
            None
            
        Returns:
            None
        """
        if not self.calibration_dialog:
            self.calibration_dialog = CalibrationMethodsDialog(self.parent)
        self.calibration_dialog.show()
        self.calibration_dialog.raise_()


class InteractiveEquationVisualizer(QWidget):
    """
    Enhanced interactive visualization with automatic demo loading and signal processing.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the interactive equation visualizer.
        
        Args:
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.setMinimumHeight(800)
        layout = QVBoxLayout(self)
        
        self.compound_poisson_lognormal = CompoundPoissonLognormal()
        
        self.original_time_data = []
        self.original_signal_data = []
        self.current_time_data = []
        self.current_signal_data = []
        self.original_dwell_time_us = 100.0
        
        controls_group = QGroupBox("SP-ICP-MS Detection Parameters with Signal Processing")
        controls_layout = QVBoxLayout(controls_group)
        
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Detection Method:"))
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Currie", 
            "Formula_C", 
            "Compound_Poisson", 
            "Manual"
        ])
        self.method_combo.currentTextChanged.connect(self.update_visualization)
        method_layout.addWidget(self.method_combo)
        method_layout.addStretch()
        controls_layout.addLayout(method_layout)
        
        params_grid = QGridLayout()
        
        params_grid.addWidget(QLabel("Base Background (λ):"), 0, 0)
        self.bg_slider = QSlider(Qt.Horizontal)
        self.bg_slider.setRange(1, 1000)
        self.bg_slider.setValue(100)
        self.bg_slider.valueChanged.connect(self.fast_update)
        self.bg_spinbox = QDoubleSpinBox()
        self.bg_spinbox.setRange(0.01, 10.0)
        self.bg_spinbox.setDecimals(3)
        self.bg_spinbox.setValue(1.0)
        params_grid.addWidget(self.bg_slider, 0, 1)
        params_grid.addWidget(self.bg_spinbox, 0, 2)
        
        params_grid.addWidget(QLabel("Alpha (α):"), 0, 3)
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(0, 90)
        self.alpha_slider.setValue(60)
        self.alpha_slider.valueChanged.connect(self.fast_update)
        self.alpha_spinbox = QDoubleSpinBox()
        self.alpha_spinbox.setRange(1e-9, 1.0)
        self.alpha_spinbox.setDecimals(9)
        self.alpha_spinbox.setValue(1e-6)
        params_grid.addWidget(self.alpha_slider, 0, 4)
        params_grid.addWidget(self.alpha_spinbox, 0, 5)
        
        params_grid.addWidget(QLabel("Dwell Time (μs):"), 1, 0)
        self.dwell_slider = QSlider(Qt.Horizontal)
        self.dwell_slider.setRange(1, 10000)
        self.dwell_slider.setValue(1000)
        self.dwell_slider.valueChanged.connect(self.fast_update)
        self.dwell_spinbox = QDoubleSpinBox()
        self.dwell_spinbox.setRange(0.1, 10000.0)
        self.dwell_spinbox.setDecimals(1)
        self.dwell_spinbox.setValue(100.0)
        self.dwell_spinbox.setSuffix(" μs")
        params_grid.addWidget(self.dwell_slider, 1, 1)
        params_grid.addWidget(self.dwell_spinbox, 1, 2)
        
        params_grid.addWidget(QLabel("Sigma (σ):"), 1, 3)
        self.sigma_slider = QSlider(Qt.Horizontal)
        self.sigma_slider.setRange(1, 200)
        self.sigma_slider.setValue(47)
        self.sigma_slider.valueChanged.connect(self.fast_update)
        self.sigma_spinbox = QDoubleSpinBox()
        self.sigma_spinbox.setRange(0.01, 2.0)
        self.sigma_spinbox.setDecimals(3)
        self.sigma_spinbox.setValue(0.47)
        params_grid.addWidget(self.sigma_slider, 1, 4)
        params_grid.addWidget(self.sigma_spinbox, 1, 5)
        
        params_grid.addWidget(QLabel("Number of Particles:"), 2, 0)
        self.particles_slider = QSlider(Qt.Horizontal)
        self.particles_slider.setRange(1, 30)
        self.particles_slider.setValue(15)
        self.particles_slider.valueChanged.connect(self.fast_update)
        self.particles_spinbox = QSpinBox()
        self.particles_spinbox.setRange(1, 30)
        self.particles_spinbox.setValue(15)
        params_grid.addWidget(self.particles_slider, 2, 1)
        params_grid.addWidget(self.particles_spinbox, 2, 2)
        
        params_grid.addWidget(QLabel("Manual Threshold:"), 2, 3)
        self.manual_slider = QSlider(Qt.Horizontal)
        self.manual_slider.setRange(1, 200)
        self.manual_slider.setValue(50)
        self.manual_slider.valueChanged.connect(self.fast_update)
        self.manual_spinbox = QDoubleSpinBox()
        self.manual_spinbox.setRange(0.01, 1000.0)
        self.manual_spinbox.setDecimals(3)
        self.manual_spinbox.setValue(5.0)
        params_grid.addWidget(self.manual_slider, 2, 4)
        params_grid.addWidget(self.manual_spinbox, 2, 5)
        
        controls_layout.addLayout(params_grid)
        layout.addWidget(controls_group)
        
        self.equation_label = QLabel()
        self.equation_label.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                border: 4px solid #007bff;
                border-radius: 16px;
                padding: 20px;
                font-family: 'Courier New', monospace;
                font-size: 16px;
                max-height: 200px;
            }
        """)
        self.equation_label.setWordWrap(True)
        layout.addWidget(self.equation_label)
        
        self.results_label = QLabel()
        self.results_label.setStyleSheet("""
            QLabel {
                background-color: #e8f5e8;
                border: 2px solid #28a745;
                border-radius: 8px;
                padding: 8px;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.results_label)
        
        self.plot = pg.PlotWidget()
        self.plot.setBackground('w')
        self.plot.setLabel('left', 'Signal Intensity (counts)')
        self.plot.setLabel('bottom', 'Time (seconds)')
        self.plot.setTitle('SP-ICP-MS Simulation with Real Signal Processing')
        layout.addWidget(self.plot)
        
        self.bg_spinbox.valueChanged.connect(self.update_bg_slider)
        self.alpha_spinbox.valueChanged.connect(self.update_alpha_slider)
        self.dwell_spinbox.valueChanged.connect(self.update_dwell_slider)
        self.sigma_spinbox.valueChanged.connect(self.update_sigma_slider)
        self.manual_spinbox.valueChanged.connect(self.update_manual_slider)
        self.particles_spinbox.valueChanged.connect(self.update_particles_slider)
        
        self.last_params = {}
        
        self.load_demo_signal()
    
    def load_demo_signal(self):
        """
        Args:
            None
            
        Returns:
            None
        """
        try:
            demo_file = get_resource_path("data/examplesignal.csv")
            self.load_csv_file(str(demo_file))
        except FileNotFoundError:
            self.create_demo_signal()
        
    def load_csv_file(self, file_path):
        """
        Load and parse CSV file using dwell time processing method.
        
        Args:
            file_path (str): Path to CSV file
            
        Returns:
            None
        """
        try:
            self.original_time_data = []
            self.original_signal_data = []
            
            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.reader(csvfile, delimiter=delimiter)
                rows = list(reader)
                
                if len(rows) >= 3 and len(rows[2]) >= 1:
                    try:
                        dwell_time_seconds = float(rows[2][0])
                        self.original_dwell_time_us = dwell_time_seconds * 1000000
                        self.dwell_spinbox.setValue(self.original_dwell_time_us)
                    except (ValueError, IndexError):
                        self.original_dwell_time_us = 100.0
                        self.dwell_spinbox.setValue(100.0)
                else:
                    self.original_dwell_time_us = 100.0
                    self.dwell_spinbox.setValue(100.0)
                
                for row in rows:
                    if len(row) >= 2:
                        try:
                            time_val = float(row[0])
                            signal_val = float(row[1])
                            self.original_time_data.append(time_val)
                            self.original_signal_data.append(signal_val)
                        except ValueError:
                            continue
            
            if not self.original_time_data or not self.original_signal_data:
                raise ValueError("No valid data found in the CSV file")
            
            self.current_time_data = self.original_time_data.copy()
            self.current_signal_data = self.original_signal_data.copy()
            
            self.update_visualization()
            
        except Exception as e:
            print(f"Error loading CSV: {e}")
            self.create_demo_signal()
    
    def create_demo_signal(self):
        """
        Create a demo signal if CSV file is not available.
        
        Args:
            None
            
        Returns:
            None
        """
        time_points = np.arange(0, 10, 0.001)
        signal = np.random.poisson(10, len(time_points)).astype(float)
        
        for peak_time in [2.0, 4.5, 7.2]:
            peak_idx = int(peak_time / 0.001)
            peak_width = 50
            for i in range(max(0, peak_idx-peak_width//2), min(len(signal), peak_idx+peak_width//2)):
                signal[i] += 100 * np.exp(-((i-peak_idx)/20)**2)
        
        self.original_time_data = time_points.tolist()
        self.original_signal_data = signal.tolist()
        self.current_time_data = self.original_time_data.copy()
        self.current_signal_data = self.original_signal_data.copy()
        self.original_dwell_time_us = 1000.0
    
    def apply_dwell_time_binning(self, new_dwell_time_us):
        """
        Apply dwell time binning using sum method.
        
        Args:
            new_dwell_time_us (float): New dwell time in microseconds
            
        Returns:
            None
        """
        if not self.original_signal_data:
            return
        
        new_dwell_time_s = new_dwell_time_us / 1000000.0
        original_dwell_time_s = self.original_dwell_time_us / 1000000.0
        
        bin_size = new_dwell_time_s / original_dwell_time_s
        
        if bin_size >= 1:
            self.current_time_data = []
            self.current_signal_data = []
            
            current_time = self.original_time_data[0]
            i = 0
            
            while i < len(self.original_time_data) and current_time <= self.original_time_data[-1]:
                bin_counts = []
                bin_end_time = current_time + new_dwell_time_s
                
                while i < len(self.original_time_data) and self.original_time_data[i] < bin_end_time:
                    bin_counts.append(self.original_signal_data[i])
                    i += 1
                
                if bin_counts:
                    binned_value = np.sum(bin_counts)
                    self.current_time_data.append(current_time)
                    self.current_signal_data.append(binned_value)
                
                current_time += new_dwell_time_s
        else:
            self.current_time_data = self.original_time_data.copy()
            self.current_signal_data = self.original_signal_data.copy()
    
    def update_bg_slider(self, value):
        """Update background slider from spinbox value."""
        self.bg_slider.setValue(int(value * 100))
    
    def update_alpha_slider(self, value):
        """Update alpha slider from spinbox value."""
        if value >= 1.0:
            self.alpha_slider.setValue(0)
        else:
            log_value = -np.log10(value)
            self.alpha_slider.setValue(int(log_value * 10))
    
    def update_dwell_slider(self, value):
        """Update dwell time slider from spinbox value."""
        self.dwell_slider.setValue(int(value * 10))
    
    def update_sigma_slider(self, value):
        """Update sigma slider from spinbox value."""
        self.sigma_slider.setValue(int(value * 100))
    
    def update_manual_slider(self, value):
        """Update manual threshold slider from spinbox value."""
        self.manual_slider.setValue(int(value * 10))
    
    def update_particles_slider(self, value):
        """Update particles slider from spinbox value."""
        self.particles_slider.setValue(value)
    
    def fast_update(self):
        """
        Optimized update function for faster response.
        
        Args:
            None
            
        Returns:
            None
        """
        self.bg_spinbox.setValue(self.bg_slider.value() / 100.0)
        
        if self.alpha_slider.value() == 0:
            alpha = 1.0
        else:
            alpha = 10**(-self.alpha_slider.value() / 10.0)
        self.alpha_spinbox.setValue(alpha)
        
        self.dwell_spinbox.setValue(self.dwell_slider.value() / 10.0)
        self.sigma_spinbox.setValue(self.sigma_slider.value() / 100.0)
        self.manual_spinbox.setValue(self.manual_slider.value() / 10.0)
        self.particles_spinbox.setValue(self.particles_slider.value())
        
        self.update_visualization()
    
    def update_visualization(self):
        """
        Update the visualization with current parameters.
        
        Args:
            None
            
        Returns:
            None
        """
        method = self.method_combo.currentText()
        base_background = self.bg_spinbox.value()
        alpha = self.alpha_spinbox.value()
        dwell_time_us = self.dwell_spinbox.value()
        sigma = self.sigma_spinbox.value()
        manual_threshold = self.manual_spinbox.value()
        num_particles = self.particles_spinbox.value()
        
        self.apply_dwell_time_binning(dwell_time_us)
        
        dwell_time_ms = dwell_time_us / 1000.0
        actual_background = base_background * dwell_time_ms
        
        current_params = (method, base_background, alpha, dwell_time_us, sigma,
                         manual_threshold, num_particles)
        
        if hasattr(self, 'last_params') and self.last_params == current_params:
            return
        self.last_params = current_params
        
        threshold, equation_text, reference_text = self.calculate_threshold(
            method, actual_background, alpha, manual_threshold, sigma)
        
        self.equation_label.setText(f"""
            <b>{method}:</b> {equation_text}<br>
            <b>{reference_text}</b>
        """)
        
        results_text = f"""
            Background: <b>{actual_background:.1f}</b> | 
            Threshold: <b>{threshold:.1f}</b> | 
            Dwell: {dwell_time_us:.1f}μs | 
            Sigma: {sigma:.3f} | 
            Points: Original: {len(self.original_signal_data)} → Current: {len(self.current_signal_data)}
        """
        self.results_label.setText(results_text)
        
        self.update_signal_simulation(actual_background, threshold, num_particles)
    
    def update_signal_simulation(self, actual_background, threshold, num_particles):
        """
        Update simulation using real or demo signal.
        
        Args:
            actual_background (float): Background level
            threshold (float): Detection threshold
            num_particles (int): Number of synthetic particles to add
            
        Returns:
            None
        """
        self.plot.clear()
        
        if not self.current_signal_data:
            return
        
        time_points = np.array(self.current_time_data)
        signal = np.array(self.current_signal_data)
        
        if num_particles > 0:
            for i in range(num_particles):
                if i < len(time_points) // 3:
                    peak_idx = int(i * len(time_points) / (num_particles * 3))
                    if peak_idx < len(signal):
                        signal[peak_idx] += np.random.uniform(threshold * 2, threshold * 5)
        
        self.plot.plot(time_points, signal, pen='b', name='Signal with Dwell Time Processing')
        self.plot.plot(time_points, [actual_background] * len(time_points), 
                     pen=pg.mkPen('g', style=Qt.DashLine, width=2), 
                     name=f'Background ({actual_background:.1f})')
        self.plot.plot(time_points, [threshold] * len(time_points), 
                     pen=pg.mkPen('r', style=Qt.DashLine, width=2), 
                     name=f'Threshold ({threshold:.1f})')
        
        above_threshold = signal > threshold
        if np.any(above_threshold):
            above_indices = np.where(above_threshold)[0]
            scatter = pg.ScatterPlotItem(
                time_points[above_indices], signal[above_indices],
                symbol='o', size=8, brush='red', pen='darkred'
            )
            self.plot.addItem(scatter)
        
        self.plot.setLabel('left', 'Signal Intensity (counts)')
        self.plot.setLabel('bottom', 'Time (seconds)')
        self.plot.setTitle(f'Real Signal with SP-ICP-MS Detection - Dwell: {self.dwell_spinbox.value():.1f}μs')
        
        self.plot.addLegend()
    
    def calculate_threshold(self, method, background, alpha, manual_threshold, sigma):
        """
        Calculate threshold using all imported methods with sigma parameter.
        
        Args:
            method (str): Detection method name
            background (float): Background level
            alpha (float): Significance level
            manual_threshold (float): Manual threshold value
            sigma (float): Sigma parameter for compound Poisson
            
        Returns:
            tuple: (threshold, equation_text, reference_text)
        """
        if method == "Currie":
            z_a = NormalDist().inv_cdf(1.0 - alpha)
            epsilon = 0.5 if background < 10 else 0.0
            eta = 2.0
            threshold = background + z_a * np.sqrt((background + epsilon) * eta)
            
            equation_text = """Threshold = λ + z<sub>α</sub> × √[(λ + ε) × η]<br>
            Where: λ=background, z<sub>α</sub>=critical value, ε=continuity correction, η=time ratio"""
            
            reference_text = """Currie, L.A. J Radioanal Nucl Chem 276, 285–297 (2008) """
            
        elif method == "Formula_C":
            z_a = NormalDist().inv_cdf(1.0 - alpha)
            tr = 1.0
            threshold = background + (z_a**2 / 2.0 * tr + z_a * np.sqrt(
                z_a**2 / 4.0 * tr * tr + background * tr * (1.0 + tr)))
            
            equation_text = """Threshold = λ + z<sub>α</sub>²/2×t<sub>r</sub> + z<sub>α</sub>×√[z<sub>α</sub>²/4×t<sub>r</sub>² + λ×t<sub>r</sub>×(1+t<sub>r</sub>)]<br>
            Where: λ=background, z<sub>α</sub>=critical value, t<sub>r</sub>=time ratio"""
            
            reference_text = """MARLAP Manual Volume III: Chapter 20, Detection and Quantification Capabilities Overview : Formula C 20.52"""
            
        elif method == "Compound_Poisson":
            threshold = self.compound_poisson_lognormal.get_threshold(background, alpha, sigma=sigma)
            
            equation_text = f"""Analytical Compound Poisson-LogNormal Approximation: Uses Fenton-Wilkinson method for sum of lognormal distributions<br>
            Parameters: σ = {sigma:.3f} (log standard deviation)<br>
            1. Generate zero-truncated Poisson quantile: q₀ = (q - e⁻λ)/(1 - e⁻λ)<br>
            2. For each k ions, apply Fenton-Wilkinson: μ_sum, σ_sum = f(k, μ, σ)<br>
            3. Weight by Poisson probabilities: P(k|λ)<br>
            4. Solve: Σ P(k|λ) × LogNormal_CDF(x; μ_sum, σ_sum) = q₀<br>
            Lockwood, T. E.; Schlatt, L.; Clases, D. SPCal – an open source, easy-to-use processing platform for ICP-TOFMS-based single event data. Journal of Analytical Atomic Spectrometry 2025.<br>
            Fenton, L. The Sum of Log-Normal Probability Distributions in Scatter Transmission Systems. IRE Transactions on Communications Systems 1960.<br>
            """
            
            reference_text = """"""
            
        elif method == "Manual":
            threshold = manual_threshold
            
            equation_text = """Threshold = User-Defined Value<br>
            No statistical calculation - direct threshold specification"""
            
            reference_text = """User-defined threshold"""
        
        return threshold, equation_text, reference_text


class PeakIntegrationVisualizer(QWidget):
    """
    Interactive visualization of peak integration methods.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the peak integration visualizer.
        
        Args:
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.setMinimumHeight(400)
        layout = QVBoxLayout(self)
        
        self.plot = pg.PlotWidget()
        self.plot.setBackground('w')
        layout.addWidget(self.plot)
        
        controls = QHBoxLayout()
        
        background_layout = QVBoxLayout()
        background_layout.addWidget(QLabel("Background Level:"))
        self.background_slider = QSlider(Qt.Horizontal)
        self.background_slider.setRange(5, 30)
        self.background_slider.setValue(10)
        self.background_slider.valueChanged.connect(self.update_visualization)
        background_layout.addWidget(self.background_slider)
        
        threshold_layout = QVBoxLayout()
        threshold_layout.addWidget(QLabel("Threshold Level:"))
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setRange(20, 70)
        self.threshold_slider.setValue(40)
        self.threshold_slider.valueChanged.connect(self.update_visualization)
        threshold_layout.addWidget(self.threshold_slider)
        
        controls.addLayout(background_layout)
        controls.addLayout(threshold_layout)
        layout.addLayout(controls)
        
        self.generate_peak_data()
        self.update_visualization()
    
    def generate_peak_data(self):
        """
        Generate a sample peak for integration demo.
        
        Args:
            None
            
        Returns:
            None
        """
        self.x = np.linspace(0, 10, 500)
        
        peak_position = 5
        peak_height = 100
        peak_width = 0.5
        
        self.peak = peak_height * np.exp(-(self.x - peak_position)**2 / peak_width)
        
        self.background_level = 10
        self.background = np.full_like(self.x, self.background_level)
        
        np.random.seed(42)
        noise = np.random.normal(0, 2, size=len(self.x))
        
        self.signal = self.peak + self.background + noise
    
    def update_visualization(self):
        """
        Update the visualization with current parameters.
        
        Args:
            None
            
        Returns:
            None
        """
        self.plot.clear()
        
        background_level = self.background_slider.value()
        threshold_level = self.threshold_slider.value()
        
        signal = self.signal - self.background + background_level
        
        self.plot.plot(self.x, signal, pen='b', name='Signal')
        
        self.plot.plot(self.x, [background_level] * len(self.x), 
                     pen=pg.mkPen('g', style=Qt.DashLine, width=2), name='Background')
        self.plot.plot(self.x, [threshold_level] * len(self.x), 
                     pen=pg.mkPen('r', style=Qt.DashLine, width=2), name='Threshold')
        
        boundary_level = background_level
        
        self.plot.plot(self.x, [boundary_level] * len(self.x), 
                     pen=pg.mkPen('m', style=Qt.DashLine, width=2), name='Background Integration Boundary')
        
        left_idx = 0
        right_idx = len(signal) - 1
        
        for i in range(len(signal)//2, 0, -1):
            if signal[i] <= boundary_level:
                left_idx = i
                break
        
        for i in range(len(signal)//2, len(signal)):
            if signal[i] <= boundary_level:
                right_idx = i
                break
        
        self.plot.plot([self.x[left_idx], self.x[left_idx]], [0, signal[left_idx]], 
                     pen=pg.mkPen('y', width=2), name='Left Boundary')
        self.plot.plot([self.x[right_idx], self.x[right_idx]], [0, signal[right_idx]], 
                     pen=pg.mkPen('y', width=2), name='Right Boundary')
        
        fillcolor = pg.mkBrush(100, 100, 255, 100)
        fillcurve = pg.FillBetweenItem(
            pg.PlotDataItem(self.x[left_idx:right_idx+1], signal[left_idx:right_idx+1]), 
            pg.PlotDataItem(self.x[left_idx:right_idx+1], [background_level] * (right_idx-left_idx+1)), 
            brush=fillcolor
        )
        self.plot.addItem(fillcurve)
        
        area = np.sum(signal[left_idx:right_idx+1] - background_level)
        info_text = f"Background Integration\nTotal counts: {area:.1f}\nLeft bound: {self.x[left_idx]:.2f}s\nRight bound: {self.x[right_idx]:.2f}s"
        text_item = pg.TextItem(info_text, color='k', anchor=(0, 0))
        text_item.setPos(self.x[left_idx], signal[left_idx] + 5)
        self.plot.addItem(text_item)
        
        self.plot.setLabel('left', 'Signal')
        self.plot.setLabel('bottom', 'Time (s)')
        self.plot.setTitle('Background Integration Method (Used in IsotopeTrack)')
        self.plot.addLegend()


class DetectionMethodsDialog(QDialog):
    """
    Dialog explaining detection methods with interactive visualizations.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the detection methods dialog.
        
        Args:
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.setWindowTitle("Detection Methods Explained")
        self.resize(1400, 1000)
        
        layout = QVBoxLayout(self)
        
        tabs = QTabWidget()
        
        tabs.addTab(self.create_detection_methods_tab(), "Detection Methods")
        tabs.addTab(self.create_integration_tab(), "Peak Integration")
        
        layout.addWidget(tabs)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignRight)
    
    def create_detection_methods_tab(self):
        """
        Create detection methods tab with enhanced interactive features.
        
        Args:
            None
            
        Returns:
            QWidget: Detection methods tab widget
        """
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        interactive_header = QLabel("""
            <h2>Interactive Detection Explorer with Real Signal Processing</h2>
            <p>Automatically loads demonstration data to show how detection methods work with real signals</p>
            <p>Features: Dwell time binning (sum method), Sigma parameter for Compound Poisson, All detection methods (Currie, Formula C, Compound Poisson LogNormal, Manual)</p>
        """)
        interactive_header.setWordWrap(True)
        interactive_header.setTextFormat(Qt.RichText)
        content_layout.addWidget(interactive_header)
        
        visualizer = InteractiveEquationVisualizer()
        visualizer.setMinimumHeight(700)
        content_layout.addWidget(visualizer)
        
        scroll_area.setWidget(content_widget)
        
        return scroll_area
    
    def create_integration_tab(self):
        """
        Create integration tab with all content in one scrollable area.
        
        Args:
            None
            
        Returns:
            QWidget: Integration tab widget
        """
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        explanation = QLabel("""
            <h2>Peak Integration - Background Method</h2>
            <p>IsotopeTrack uses the Background Integration Method for all peak quantification.
            This method provides the most complete capture of peak area by integrating from 
            background level to background level.</p>
            
            <h3>Background Integration Process:</h3>
            <ol>
                <li>Peak Detection: Identify regions where signal exceeds threshold</li>
                <li>Boundary Finding: Locate where signal returns to background level</li>
                <li>Area Calculation: Sum all signal points within boundaries</li>
                <li>Background Subtraction: Subtract background from each integrated point</li>
            </ol>
            
            <h3>Mathematical Implementation:</h3>
            <p>Total Counts = Σ(Signal[i] - Background) for i ∈ [left_boundary, right_boundary]</p>
            <p>Where:</p>
            <ul>
                <li>left_boundary: First point where signal drops to background level (before peak)</li>
                <li>right_boundary: Last point where signal drops to background level (after peak)</li>
                <li>Background: Mean background level calculated from quiet regions</li>
                <li>Signal[i]: Raw signal intensity at point i</li>
            </ul>
            
            <h3>Why Background Integration?</h3>
            <ul>
                <li>Maximum Sensitivity: Captures entire peak including low-intensity tails</li>
                <li>Physical Meaning: Represents total analyte signal above baseline</li>
                <li>Robust Detection: Less sensitive to threshold selection variations</li>
                <li>Complete Information: Uses all available signal information</li>
                <li>Noise Tolerance: Averages out random fluctuations over peak width</li>
            </ul>
        """)
        explanation.setWordWrap(True)
        explanation.setTextFormat(Qt.RichText)
        content_layout.addWidget(explanation)
        
        separator = QLabel("<hr>")
        separator.setTextFormat(Qt.RichText)
        content_layout.addWidget(separator)
        
        interactive_header = QLabel("""
            <h2>Interactive Integration Demo</h2>
            <p>Adjust the background and threshold levels to see how integration boundaries change.</p>
        """)
        interactive_header.setWordWrap(True)
        interactive_header.setTextFormat(Qt.RichText)
        content_layout.addWidget(interactive_header)
        
        integration_demo = PeakIntegrationVisualizer()
        integration_demo.setMinimumHeight(500)
        content_layout.addWidget(integration_demo)
        
        scroll_area.setWidget(content_widget)
        return scroll_area


class CalibrationMethodsDialog(QDialog):
    """
    Dialog explaining calibration methods with visual examples.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the calibration methods dialog.
        
        Args:
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.setWindowTitle("Calibration Methods Explained")
        self.resize(900, 700)
        
        layout = QVBoxLayout(self)
        
        tabs = QTabWidget()
        
        tabs.addTab(self.create_overview_tab(), "Overview")
        tabs.addTab(self.create_ionic_tab(), "Ionic Calibration")
        tabs.addTab(self.create_transport_tab(), "Transport Rate")
        
        layout.addWidget(tabs)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignRight)
    
    def load_image_safe(self, image_path):
        """
        Safely load an image and return a QLabel with proper scaling.
        
        Args:
            image_path (str): Path to image file
            
        Returns:
            QLabel: Label containing scaled image or error message
        """
        try:
            full_path = get_resource_path(image_path)
            pixmap = QPixmap(str(full_path))
            
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(600, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                image_label = QLabel()
                image_label.setPixmap(scaled_pixmap)
                image_label.setAlignment(Qt.AlignCenter)
                return image_label
            else:
                error_label = QLabel(f"Could not load image: {image_path}")
                error_label.setStyleSheet("color: red; font-style: italic;")
                return error_label
        except Exception as e:
            error_label = QLabel(f"Error loading image {image_path}: {str(e)}")
            error_label.setStyleSheet("color: red; font-style: italic;")
            return error_label
        
    def create_overview_tab(self):
        """
        Create calibration overview tab.
        
        Args:
            None
            
        Returns:
            QWidget: Overview tab widget
        """
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        
        explanation = QLabel("""
            <h2>Calibration Overview</h2>
            <p>To convert instrument signals (counts) into meaningful physical quantities like 
            particle mass and size, IsotopeTrack uses two types of calibration:</p>
            
            <ol>
                <li>Ionic Calibration: Establishes the relationship between analyte concentration 
                and signal intensity (counts per second)</li>
                <li>Transport Rate Calibration: Determines the rate at which sample solution 
                is introduced into the instrument (μL/s)</li>
            </ol>
            
            <p>Together, these calibrations allow IsotopeTrack to calculate:</p>
            <ul>
                <li>Particle mass (femtograms)</li>
                <li>Particle diameter (nanometers)</li>
                <li>Particle number concentration (particles/mL)</li>
                <li>Detection/quantification limits</li>
            </ul>
            
            <h3>Calibration Workflow:</h3>
            <ol>
                <li>Load calibration standards and reference materials</li>
                <li>Configure ionic calibration with multiple calibration sets</li>
                <li>System tests three calibration methods and selects best R²</li>
                <li>Perform transport rate calibration using reference nanoparticles</li>
                <li>Validate calibration accuracy with known standards</li>
                <li>Apply calibration to unknown samples</li>
            </ol>
        """)
        explanation.setWordWrap(True)
        explanation.setTextFormat(Qt.RichText)
        layout.addWidget(explanation)
        
        layout.addWidget(QLabel("<h3>Calibration Methods Overview:</h3>"))
        calibration_overview_image = self.load_image_safe("images/calibration_overview.png")
        layout.addWidget(calibration_overview_image)
        
        scroll_area.setWidget(content_widget)
        return scroll_area
    
    def create_ionic_tab(self):
        """
        Create ionic calibration tab.
        
        Args:
            None
            
        Returns:
            QWidget: Ionic calibration tab widget
        """
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        
        explanation = QLabel("""
            <h2>Ionic Calibration</h2>
            <p>Ionic calibration establishes the relationship between element concentration and 
            instrument response by analyzing a series of standard solutions.</p>
            
            <h3>The Process:</h3>
            <ol>
                <li>Prepare standard solutions of known concentrations</li>
                <li>Selected isotopes from main window appear automatically in calibration</li>
                <li>Set up multiple calibration sets for different experimental conditions</li>
                <li>Use "-1" in table to exclude samples from specific calibration sets</li>
                <li>System automatically tests three calibration methods</li>
                <li>IsotopeTrack selects the method with best R² value</li>
                <li>Manual override available for user preference</li>
            </ol>
            
            <h3>Three Calibration Methods:</h3>
            <ul>
                <li>Simple Linear: Basic linear regression through origin</li>
                <li>Linear: Linear regression with intercept</li>
                <li>Weighted: Weighted linear regression for improved accuracy at low concentrations</li>
            </ul>
            
            <h3>Key Outputs:</h3>
            <ul>
                <li>Sensitivity (slope): The signal response per unit concentration (counts/ppb)</li>
                <li>R²: A measure of calibration quality (should be >0.99)</li>
                <li>BEC: Background Equivalent Concentration</li>
                <li>LOD: Limit of Detection</li>
                <li>LOQ: Limit of Quantification</li>
            </ul>
        """)
        explanation.setWordWrap(True)
        explanation.setTextFormat(Qt.RichText)
        layout.addWidget(explanation)
        
        layout.addWidget(QLabel("<h3>Example Ionic Calibration Curve:</h3>"))
        ionic_calibration_image = self.load_image_safe("images/ionic_calibration.png")
        layout.addWidget(ionic_calibration_image)
        
        scroll_area.setWidget(content_widget)
        return scroll_area
    
    def create_transport_tab(self):
        """
        Create transport rate calibration tab.
        
        Args:
            None
            
        Returns:
            QWidget: Transport rate tab widget
        """
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        
        explanation = QLabel("""
            <h2>Transport Rate Calibration</h2>
            <h3>Reference:</h3>
            <p>Pace, H.E., et al. (2011) "Determining transport efficiency for the purpose of counting 
            and sizing nanoparticles via single particle inductively coupled plasma-mass spectrometry" 
            Analytical Chemistry 83:9361-9369</p>
            
            <h3>Impact of Transport Efficiency Errors:</h3>
            <p>The following figure demonstrates how errors in transport efficiency (TE) measurement 
            directly affect particle size and concentration calculations:</p>
        """)
        explanation.setWordWrap(True)
        explanation.setTextFormat(Qt.RichText)
        layout.addWidget(explanation)
        
        transport_error_image = self.load_image_safe("images/methods.png")
        layout.addWidget(transport_error_image)
        
        citation1 = QLabel("""
            <p><i>Source: "Determining transport efficiency for the purpose of counting and sizing nanoparticles 
            via single particle inductively coupled plasma-mass spectrometry"</i></p>
        """)
        citation1.setTextFormat(Qt.RichText)
        citation1.setStyleSheet("font-style: italic; color: #666666;")
        layout.addWidget(citation1)
        
        layout.addWidget(QLabel("<hr>"))
        
        size_comparison_label = QLabel("""
            <h3>Particle size distribution analysis and number of concentration:</h3>
            <p>The following comparison shows particle size distributions and number of concentration obtained using different methods,
            demonstrating the importance of accurate transport rate calibration for reliable sizing and particle number:</p>
        """)
        size_comparison_label.setWordWrap(True)
        size_comparison_label.setTextFormat(Qt.RichText)
        layout.addWidget(size_comparison_label)
        
        size_distribution_image = self.load_image_safe("images/transport_effect.png")
        layout.addWidget(size_distribution_image)
        
        citation2 = QLabel("""
            <p><i>Source: "Lowering the Size Detection Limits of Ag and TiO<sub>2</sub> Nanoparticles by Single Particle ICP-MS"</i></p>
        """)
        citation2.setTextFormat(Qt.RichText)
        citation2.setStyleSheet("font-style: italic; color: #666666;")
        layout.addWidget(citation2)
        
        post_calibration_label = QLabel("""
            <h3>Post-Calibration Options:</h3>
            <ul>
                <li>Calculate average of multiple transport rate measurements</li>
                <li>Select the most reliable single calibrated rate</li>
                <li>Use different transport rates for different sample types</li>
                <li>Validate transport efficiency with independent methods</li>
            </ul>
        """)
        post_calibration_label.setWordWrap(True)
        post_calibration_label.setTextFormat(Qt.RichText)
        layout.addWidget(post_calibration_label)
        
        scroll_area.setWidget(content_widget)
        return scroll_area


class AboutDialog(QDialog):
    """
    About dialog for IsotopeTrack application.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the about dialog.
        
        Args:
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.setWindowTitle("About IsotopeTrack")
        self.setFixedSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        title = QLabel("<h1>IsotopeTrack</h1>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        
        try:
            logo_path = get_resource_path("images/isotrack_icon.png")
            logo_pixmap = QPixmap(str(logo_path))

            if not logo_pixmap.isNull():
                scaled_logo = logo_pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(scaled_logo)
        except Exception as e:
            logo_label.setText("🔬")
            logo_label.setStyleSheet("font-size: 48px;")
        
        layout.addWidget(logo_label)
        
        layout.addSpacing(10)
        
        version = QLabel("<h3>Version 1.0.0</h3>")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)
        
        description = QLabel("""
            <p align="center">
            A software for analyzing single particle ICP-ToF-MS data.<br><br>
            IsotopeTrack provides advanced tools for peak detection, calibration,<br>
            and quantitative analysis of nanoparticles.
            </p>
        """)
        description.setWordWrap(True)
        layout.addWidget(description)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignCenter)


class TabbedHelpWindow(QMainWindow):
    """
    Main help window with tabbed interface for all help content.
    """
    
    def __init__(self):
        """
        Initialize the tabbed help window.
        
        Args:
            None
            
        Returns:
            None
        """
        super().__init__()
        self.setWindowTitle("IsotopeTrack Help")
        self.resize(1000, 800)

        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self.tab_widget.addTab(UserGuideDialog(self), "User Guide")
        self.tab_widget.addTab(DetectionMethodsDialog(self), "Detection Methods")
        self.tab_widget.addTab(CalibrationMethodsDialog(self), "Calibration Methods")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    help_center = TabbedHelpWindow()
    help_center.showMaximized()
    sys.exit(app.exec())