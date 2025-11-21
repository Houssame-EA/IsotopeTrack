"""
Unified Single Ion Distribution Manager
Supports both Nu Vitesse and TOFWERK ICP-ToF instruments
"""

import numpy as np
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QFileDialog, QMessageBox, QApplication, QRadioButton, QButtonGroup)
from PySide6.QtCore import Qt, QThread, QObject, Signal, Slot
import pyqtgraph as pg
import qtawesome as qta
from scipy import stats
from scipy.special import gammainc
import traceback

import data_loading.vitesse_loading
import data_loading.tofwerk_loading
from processing.peak_detection import erf, erfinv


def lognormal_pdf_scipy(x: np.ndarray, mu: float, sigma: float) -> np.ndarray:
    """
    Scipy lognormal probability density function.
    
    Args:
        x (np.ndarray): Input values
        mu (float): Mean parameter
        sigma (float): Standard deviation parameter
        
    Returns:
        np.ndarray: PDF values
    """
    return stats.lognorm.pdf(x, s=sigma, scale=np.exp(mu))


class SIAWorker(QObject):
    """
    Worker class for processing Single-Ion Distribution data in a separate thread.
    """
    
    progress = Signal(int)
    status_update = Signal(str)
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self):
        """
        Initialize the SIA worker.
        
        Args:
            None
            
        Returns:
            None
        """
        super().__init__()
        self.data_path = None
        self.file_type = None
        self._should_stop = False
    
    @Slot(str, str)
    def process_sia_data(self, data_path, file_type="nu"):
        """
        Process SIA data from Nu or TOFWERK files.
        
        Args:
            data_path (str): Path to data file or folder
            file_type (str): Type of file ('nu' or 'tofwerk')
            
        Returns:
            None
        """
        try:
            self.data_path = Path(data_path)
            self.file_type = file_type
            self._should_stop = False
            
            if file_type == "nu":
                self._process_nu_data()
            elif file_type == "tofwerk":
                self._process_tofwerk_data()
            else:
                self.error.emit(f"Unknown file type: {file_type}")
                
        except Exception as e:
            error_msg = f"Error processing single-ion distribution: {str(e)}"
            self.error.emit(error_msg)
            print(f"SIA Worker Error: {error_msg}")
            print(f"Traceback: {traceback.format_exc()}")
    
    def _process_nu_data(self):
        """
        Process Nu Vitesse data.
        
        Args:
            None
            
        Returns:
            None
        """
        run_info_path = self.data_path / "run.info"
        if not run_info_path.exists():
            self.error.emit("Selected folder does not contain run.info file.\nPlease select a Nu Vitesse data folder.")
            return
        
        self.status_update.emit("Loading Nu Vitesse data...")
        self.progress.emit(10)
        
        if self._should_stop:
            return
        
        self.status_update.emit("Reading Nu directory...")
        self.progress.emit(20)
        
        masses, signals, run_info = data_loading.vitesse_loading.read_nu_directory(
            path=str(self.data_path),
            max_integ_files=None,
            autoblank=True,
            raw=True
        )
        
        if self._should_stop:
            return
        
        self.progress.emit(50)
        self.status_update.emit("Calculating single-ion distribution...")
        
        single_ion_dist = data_loading.vitesse_loading.single_ion_distribution(
            counts=signals,
            bins="auto"
        )
        
        if self._should_stop:
            return
        
        self.progress.emit(70)
        self.status_update.emit("Processing distribution statistics...")
        
        run_info['InstrumentType'] = 'Nu Vitesse'
        
        processed_data = self._process_distribution_data(
            single_ion_dist, str(self.data_path), run_info, masses, signals
        )
        
        if self._should_stop:
            return
        
        self.progress.emit(100)
        self.finished.emit(processed_data)
    
    def _process_tofwerk_data(self):
        """
        Process TOFWERK data.
        
        Args:
            None
            
        Returns:
            None
        """
        if not self.data_path.exists():
            self.error.emit("Selected file does not exist.")
            return
        
        if not data_loading.tofwerk_loading.is_tofwerk_file(self.data_path):
            self.error.emit("Selected file is not a valid TOFWERK .h5 file.")
            return
        
        self.status_update.emit("Loading TOFWERK data...")
        self.progress.emit(10)
        
        if self._should_stop:
            return
        
        self.status_update.emit("Reading TOFWERK file...")
        self.progress.emit(20)
        
        try:
            import h5py
            
            with h5py.File(self.data_path, "r") as h5:
                if "PeakData" in h5["PeakData"]:
                    data = h5["PeakData"]["PeakData"][...]
                else:
                    data = data_loading.tofwerk_loading.integrate_tof_data(h5, idx=None)
                
                factor = data_loading.tofwerk_loading.factor_extraction_to_acquisition(h5)
                data *= factor
                
                single_ion_signal = float(h5["FullSpectra"].attrs["Single Ion Signal"][0])
                
                peak_table = h5["PeakData"]["PeakTable"]
                masses = peak_table["mass"].astype(np.float32)
                
                signals = data * single_ion_signal
                
                run_info = {
                    "SampleName": self.data_path.stem,
                    "AnalysisDateTime": "Unknown",
                    "AverageSingleIonArea": single_ion_signal,
                    "InstrumentType": "TOFWERK",
                    "TotalAcquisitions": data.shape[0],
                }
            
        except Exception as e:
            self.error.emit(f"Error reading TOFWERK file: {str(e)}")
            return
        
        if self._should_stop:
            return
        
        self.progress.emit(50)
        self.status_update.emit("Calculating single-ion distribution...")
        
        pzeros = np.count_nonzero(signals, axis=0) / signals.shape[0]
        poi2 = gammainc(3, pzeros)
        x = signals[:, (poi2 > 1e-5) & (poi2 < 1e-3)]
        
        hist, bins = np.histogram(x[x > 0], bins="auto")
        single_ion_dist = np.stack(((bins[1:] + bins[:-1]) / 2.0, hist), axis=1)
        
        if self._should_stop:
            return
        
        self.progress.emit(70)
        self.status_update.emit("Processing distribution statistics...")
        
        processed_data = self._process_distribution_data(
            single_ion_dist, str(self.data_path), run_info, masses, signals
        )
        
        if self._should_stop:
            return
        
        self.progress.emit(100)
        self.finished.emit(processed_data)
    
    def _process_distribution_data(self, single_ion_dist, data_path, run_info, masses, signals):
        """
        Process the SIA data and calculate statistics.
        
        Args:
            single_ion_dist (np.ndarray): Single ion distribution data
            data_path (str): Path to data source
            run_info (dict): Run information dictionary
            masses (np.ndarray): Array of masses
            signals (np.ndarray): Signal data
            
        Returns:
            dict: Processed distribution data
        """
        average_single_ion_area = run_info.get("AverageSingleIonArea", 1.0)
        
        if average_single_ion_area <= 0 or not np.isfinite(average_single_ion_area):
            print(f"Warning: Invalid average_single_ion_area ({average_single_ion_area}), using 1.0")
            average_single_ion_area = 1.0
        
        instrument_type = run_info.get("InstrumentType", "Unknown")
        
        signal_values = single_ion_dist[:, 0]
        weights = single_ion_dist[:, 1]
        weights = weights / np.sum(weights)
        
        mean_signal = np.average(signal_values, weights=weights)
        variance = np.average((signal_values - mean_signal)**2, weights=weights)
        std_signal = np.sqrt(variance)
        
        if mean_signal > 0:
            cv = std_signal / mean_signal
            calculated_sigma = np.sqrt(np.log(1 + cv**2))
        else:
            calculated_sigma = 0.47
        
        per_mass_distributions = {}
        
        if signals.ndim == 1:
            signals = signals.reshape(-1, 1)
        
        pzeros = np.count_nonzero(signals, axis=0) / signals.shape[0]
        poi2 = gammainc(3, pzeros)
        
        masses = np.atleast_1d(masses)
        
        poi2 = np.atleast_1d(poi2).flatten()
        if len(poi2) != len(masses):
            print(f"Warning: poi2 length ({len(poi2)}) != masses length ({len(masses)})")
            min_len = min(len(poi2), len(masses))
            poi2 = poi2[:min_len]
            masses = masses[:min_len]
        
        for i, mass in enumerate(masses):
            poi2_value = float(poi2[i]) if hasattr(poi2[i], '__float__') else poi2[i]
            
            try:
                if poi2_value > 1e-5 and poi2_value < 1e-3:
                    mass_signals = signals[:, i]
                    mass_signals = mass_signals[mass_signals > 0]
                    
                    if len(mass_signals) > 10:
                        hist, bins = np.histogram(mass_signals, bins="auto")
                        mass_dist = np.stack(((bins[1:] + bins[:-1]) / 2.0, hist), axis=1)
                        
                        mass_signal_values = mass_dist[:, 0]
                        mass_weights = mass_dist[:, 1]
                        
                        if np.sum(mass_weights) > 0:
                            mass_weights = mass_weights / np.sum(mass_weights)
                            
                            mass_mean = np.average(mass_signal_values, weights=mass_weights)
                            mass_var = np.average((mass_signal_values - mass_mean)**2, weights=mass_weights)
                            mass_std = np.sqrt(mass_var)
                            
                            if mass_mean > 0:
                                mass_cv = mass_std / mass_mean
                                mass_sigma = np.sqrt(np.log(1 + mass_cv**2))
                            else:
                                mass_sigma = calculated_sigma
                            
                            per_mass_distributions[f"{mass:.4f}"] = {
                                'distribution': mass_dist,
                                'mass': float(mass),
                                'mean_signal': float(mass_mean),
                                'std_signal': float(mass_std),
                                'sigma': float(mass_sigma),
                                'num_points': len(mass_signals)
                            }
            except Exception as e:
                print(f"Warning: Failed to process mass {mass}: {e}")
                continue
        
        sample_name = run_info.get("SampleName", Path(data_path).name)
        total_counts = np.sum(signals)
        num_acquisitions = len(signals)
        
        result = {
            'single_ion_distribution_data': single_ion_dist,
            'single_ion_source_folder': str(data_path),
            'per_mass_distributions': per_mass_distributions,
            'single_ion_info': {
                'source_folder': str(data_path),
                'sample_name': sample_name,
                'instrument_type': instrument_type,
                'total_counts': total_counts,
                'num_acquisitions': num_acquisitions,
                'num_masses': len(masses),
                'mass_range': (float(np.min(masses)), float(np.max(masses))),
                'distribution_points': len(single_ion_dist),
                'mean_signal': float(mean_signal),
                'std_signal': float(std_signal),
                'calculated_sigma': float(calculated_sigma),
                'analysis_datetime': run_info.get("AnalysisDateTime", "Unknown"),
                'signal_values': signal_values.copy(),
                'weights': weights.copy(),
                'average_single_ion_area': float(average_single_ion_area),
                'num_valid_masses': len(per_mass_distributions)
            }
        }
        
        return result
        
    @Slot()
    def stop_processing(self):
        """
        Stop the current processing.
        
        Args:
            None
            
        Returns:
            None
        """
        self._should_stop = True


class SingleIonDistributionManager:
    """
    Unified Single-Ion Distribution Manager
    Supports both Nu Vitesse and TOFWERK instruments
    """
    
    def __init__(self, main_window):
        """
        Initialize the SIA manager.
        
        Args:
            main_window (object): Reference to main window
            
        Returns:
            None
        """
        self.main_window = main_window
        self.single_ion_distribution_data = None
        self.single_ion_source_folder = None
        self.single_ion_info = {}
        self.upload_sid_button = None
        self.info_sid_button = None
        self.clear_sid_button = None
        
        self.sia_thread = None
        self.sia_worker = None
        self._is_processing = False
    
    def create_sia_buttons(self, parent_layout):
        """
        Create and configure SIA control buttons.
        
        Args:
            parent_layout (QLayout): Layout to add buttons to
            
        Returns:
            None
        """
        self.upload_sid_button = QPushButton()
        self.upload_sid_button.setIcon(qta.icon('fa6s.folder-open', color="#2196F3"))
        self.upload_sid_button.setToolTip("Upload single-ion distribution from Nu Vitesse or TOFWERK")
        self.upload_sid_button.setFixedSize(32, 32)
        self.upload_sid_button.clicked.connect(self.upload_single_ion_distribution)
        
        self.info_sid_button = QPushButton()
        self.info_sid_button.setIcon(qta.icon('fa6s.circle-info', color="#4CAF50"))
        self.info_sid_button.setToolTip("Show single-ion distribution information")
        self.info_sid_button.setFixedSize(32, 32)
        self.info_sid_button.setEnabled(False)
        self.info_sid_button.clicked.connect(self.show_single_ion_info)
        
        self.clear_sid_button = QPushButton()
        self.clear_sid_button.setIcon(qta.icon('fa6s.trash', color="#f44336"))
        self.clear_sid_button.setToolTip("Clear loaded single-ion distribution")
        self.clear_sid_button.setFixedSize(32, 32)
        self.clear_sid_button.setEnabled(False)
        self.clear_sid_button.clicked.connect(self.clear_single_ion_distribution)
        
        parent_layout.addWidget(self.upload_sid_button)
        parent_layout.addWidget(self.info_sid_button)
        parent_layout.addWidget(self.clear_sid_button)
    
    def upload_single_ion_distribution(self):
        """
        Upload single-ion distribution - auto-detect file type.
        
        Args:
            None
            
        Returns:
            None
        """
        if self._is_processing:
            QMessageBox.information(
                self.main_window,
                "Processing in Progress",
                "SIA processing is already in progress. Please wait for completion."
            )
            return
        
        try:
            msg_box = QMessageBox(self.main_window)
            msg_box.setWindowTitle("Select Data Type")
            msg_box.setText("What type of data do you want to load for SIA calculation?")
            msg_box.setInformativeText(
                "Nu Vitesse: Folder containing run.info\n"
                "TOFWERK: Single .h5 file"
            )
            
            nu_button = msg_box.addButton("Nu Vitesse Folder", QMessageBox.ActionRole)
            tof_button = msg_box.addButton("TOFWERK .h5 File", QMessageBox.ActionRole)
            cancel_button = msg_box.addButton(QMessageBox.Cancel)
            
            msg_box.exec()
            clicked = msg_box.clickedButton()
            
            if clicked == cancel_button:
                return
            elif clicked == nu_button:
                folder_path = QFileDialog.getExistingDirectory(
                    self.main_window,
                    "Select Nu Vitesse Folder with run.info",
                    "",
                    QFileDialog.ShowDirsOnly
                )
                if folder_path:
                    self._start_sia_processing(folder_path, file_type="nu")
                    
            elif clicked == tof_button:
                file_path, _ = QFileDialog.getOpenFileName(
                    self.main_window,
                    "Select TOFWERK .h5 File",
                    "",
                    "HDF5 Files (*.h5 *.hdf5);;All Files (*.*)"
                )
                if file_path:
                    self._start_sia_processing(file_path, file_type="tofwerk")
                
        except Exception as e:
            error_msg = f"Error starting SIA processing: {str(e)}"
            self.main_window.status_label.setText(error_msg)
            QMessageBox.critical(self.main_window, "Processing Error", error_msg)
    
    def _start_sia_processing(self, data_path, file_type="nu"):
        """
        Start SIA processing in a separate thread.
        
        Args:
            data_path (str): Path to data file or folder
            file_type (str): Type of file ('nu' or 'tofwerk')
            
        Returns:
            None
        """
        try:
            self._is_processing = True
            
            self.upload_sid_button.setEnabled(False)
            self.upload_sid_button.setText("Processing...")
            
            self.main_window.progress_bar.setVisible(True)
            self.main_window.progress_bar.setValue(0)
            
            self.sia_thread = QThread()
            self.sia_worker = SIAWorker()
            
            self.sia_worker.moveToThread(self.sia_thread)
            
            self.sia_thread.started.connect(
                lambda: self.sia_worker.process_sia_data(data_path, file_type)
            )
            self.sia_worker.progress.connect(self._on_progress_update)
            self.sia_worker.status_update.connect(self._on_status_update)
            self.sia_worker.finished.connect(self._on_sia_processing_finished)
            self.sia_worker.error.connect(self._on_sia_processing_error)
            
            self.sia_worker.finished.connect(self.sia_thread.quit)
            self.sia_worker.error.connect(self.sia_thread.quit)
            self.sia_thread.finished.connect(self.sia_worker.deleteLater)
            self.sia_thread.finished.connect(self.sia_thread.deleteLater)
            self.sia_thread.finished.connect(self._on_thread_cleanup)
            
            self.sia_thread.start()
            
        except Exception as e:
            self._reset_processing_state()
            error_msg = f"Error starting SIA thread: {str(e)}"
            self.main_window.status_label.setText(error_msg)
            QMessageBox.critical(self.main_window, "Thread Error", error_msg)
    
    def _on_progress_update(self, progress):
        """
        Handle progress updates.
        
        Args:
            progress (int): Progress percentage
            
        Returns:
            None
        """
        self.main_window.progress_bar.setValue(progress)
        QApplication.processEvents()
    
    def _on_status_update(self, status):
        """
        Handle status updates.
        
        Args:
            status (str): Status message
            
        Returns:
            None
        """
        self.main_window.status_label.setText(status)
        QApplication.processEvents()
    
    def _on_sia_processing_finished(self, result_data):
        """
        Handle completion of SIA processing.
        
        Args:
            result_data (dict): Processing results
            
        Returns:
            None
        """
        try:
            self.single_ion_distribution_data = result_data['single_ion_distribution_data']
            self.single_ion_source_folder = result_data['single_ion_source_folder']
            self.single_ion_info = result_data['single_ion_info']
            self.per_mass_distributions = result_data.get('per_mass_distributions', {})
        
                
            self._update_ui_after_load()
            
            total_elements_updated, total_samples_updated = self._apply_sia_to_all_samples()
            
            self._show_success_message(total_elements_updated, total_samples_updated)
            
            calculated_sigma = self.single_ion_info['calculated_sigma']
            sample_name = self.single_ion_info['sample_name']
            instrument_type = self.single_ion_info['instrument_type']
            
            self.main_window.status_label.setText(
                f"SIA loaded from {instrument_type}: {sample_name}, "
                f"σ updated to {calculated_sigma:.3f}"
            )
            
        except Exception as e:
            error_msg = f"Error processing SIA results: {str(e)}"
            self.main_window.status_label.setText(error_msg)
            QMessageBox.critical(self.main_window, "Results Error", error_msg)
        finally:
            self._reset_processing_state()
    
    def _on_sia_processing_error(self, error_message):
        """
        Handle errors.
        
        Args:
            error_message (str): Error message
            
        Returns:
            None
        """
        self._reset_processing_state()
        self.main_window.status_label.setText(f"SIA Error: {error_message}")
        QMessageBox.critical(self.main_window, "SIA Processing Error", error_message)
    
    def _on_thread_cleanup(self):
        """
        Clean up thread references.
        
        Args:
            None
            
        Returns:
            None
        """
        self.sia_thread = None
        self.sia_worker = None
    
    def _reset_processing_state(self):
        """
        Reset processing state.
        
        Args:
            None
            
        Returns:
            None
        """
        self._is_processing = False
        self.upload_sid_button.setEnabled(True)
        self.upload_sid_button.setText("")
        self.main_window.progress_bar.setVisible(False)
    
    def _update_ui_after_load(self):
        """
        Update UI after SIA is loaded.
        
        Args:
            None
            
        Returns:
            None
        """
        if hasattr(self.main_window, 'sigma_spinbox'):
            calculated_sigma = self.single_ion_info['calculated_sigma']
            self.main_window.sigma_spinbox.valueChanged.disconnect()
            self.main_window.sigma_spinbox.setValue(calculated_sigma)
            self.main_window.sigma_spinbox.valueChanged.connect(self.main_window.on_sigma_changed)
        
        self.info_sid_button.setEnabled(True)
        self.clear_sid_button.setEnabled(True)
        
        self.upload_sid_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: 2px solid #45a049;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
    
    def _apply_sia_to_all_samples(self):
        """
        Apply SIA parameters to all samples.
        
        Args:
            None
            
        Returns:
            tuple: (total_elements_updated, total_samples_updated)
        """
        total_elements_updated = 0
        total_samples_updated = 0
        
        if hasattr(self.main_window, 'parameters_table'):
            self.main_window.update_parameters_table()
        
        return total_elements_updated, total_samples_updated
    
    def _show_success_message(self, total_elements_updated, total_samples_updated):
        """
        Show success message.
        
        Args:
            total_elements_updated (int): Number of elements updated
            total_samples_updated (int): Number of samples updated
            
        Returns:
            None
        """
        calculated_sigma = self.single_ion_info['calculated_sigma']
        sample_name = self.single_ion_info['sample_name']
        distribution_points = self.single_ion_info['distribution_points']
        mean_signal = self.single_ion_info['mean_signal']
        instrument_type = self.single_ion_info['instrument_type']
        
        QMessageBox.information(
            self.main_window,
            "Success",
            f"Single-ion distribution loaded successfully!\n\n"
            f"Instrument: {instrument_type}\n"
            f"Source: {sample_name}\n"
            f"Distribution points: {distribution_points}\n"
            f"Calculated σ: {calculated_sigma:.3f}\n"
            f"Mean signal: {mean_signal:.1f} counts\n\n"
            f"Applied real single-ion distribution to analysis"
        )
    
    def show_single_ion_info(self):
        """
        Show information and plot.
        
        Args:
            None
            
        Returns:
            None
        """
        if self.single_ion_distribution_data is None or not self.single_ion_info:
            QMessageBox.warning(self.main_window, "No Data", "No single-ion distribution loaded.")
            return
        
        info = self.single_ion_info
        
        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("Single-Ion Distribution Information")
        dialog.setMinimumWidth(900)
        dialog.setMinimumHeight(700)
        
        layout = QVBoxLayout(dialog)
        
        info_text = self._create_info_html(info)
        info_label = QLabel(info_text)
        info_label.setTextFormat(Qt.RichText)
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignTop)
        info_label.setMaximumHeight(200)
        
        layout.addWidget(info_label)
        
        if hasattr(self, 'per_mass_distributions') and self.per_mass_distributions:
            from PySide6.QtWidgets import QComboBox, QCheckBox
            
            control_layout = QHBoxLayout()
            
            self.view_toggle = QCheckBox("View individual mass")
            self.view_toggle.setStyleSheet("font-weight: bold; font-size: 12pt;")
            control_layout.addWidget(self.view_toggle)
            
            self.mass_selector = QComboBox()
            self.mass_selector.setEnabled(False)
            self.mass_selector.setMinimumWidth(200)
            
            mass_items = []
            for mass_key, mass_data in self.per_mass_distributions.items():
                mass_items.append((mass_data['mass'], mass_key))
            mass_items.sort()
            
            for mass_val, mass_key in mass_items:
                self.mass_selector.addItem(f"m/z {mass_val:.4f}", mass_key)
            
            control_layout.addWidget(QLabel("Select mass:"))
            control_layout.addWidget(self.mass_selector)
            control_layout.addStretch()
            
            layout.addLayout(control_layout)
            
            view_type_layout = QHBoxLayout()
            self.view_type_group = QButtonGroup()
            
            self.radio_distribution = QRadioButton("Individual Distribution")
            self.radio_sigma_comparison = QRadioButton("Sigma Comparison")
            self.radio_distribution.setChecked(True)
            self.radio_distribution.setEnabled(False)
            self.radio_sigma_comparison.setEnabled(False)
            
            self.view_type_group.addButton(self.radio_distribution)
            self.view_type_group.addButton(self.radio_sigma_comparison)
            
            view_type_layout.addWidget(QLabel("View Type:"))
            view_type_layout.addWidget(self.radio_distribution)
            view_type_layout.addWidget(self.radio_sigma_comparison)
            view_type_layout.addStretch()
            
            layout.addLayout(view_type_layout)
        
        plot_widget = self._create_sia_plot(info, None)
        layout.addWidget(plot_widget)
        
        if hasattr(self, 'per_mass_distributions') and self.per_mass_distributions:
            def update_plot():
                nonlocal plot_widget
                
                layout.removeWidget(plot_widget)
                plot_widget.deleteLater()
                
                if self.view_toggle.isChecked():
                    self.mass_selector.setEnabled(True)
                    self.radio_distribution.setEnabled(True)
                    self.radio_sigma_comparison.setEnabled(True)
                    
                    if self.radio_sigma_comparison.isChecked():
                        new_plot = self._create_sigma_comparison_plot(info)
                    else:
                        mass_key = self.mass_selector.currentData()
                        new_plot = self._create_sia_plot(info, mass_key)
                else:
                    self.mass_selector.setEnabled(False)
                    self.radio_distribution.setEnabled(False)
                    self.radio_sigma_comparison.setEnabled(False)
                    new_plot = self._create_sia_plot(info, None)
                
                layout.insertWidget(layout.count() - 1, new_plot)
                plot_widget = new_plot
            
            self.view_toggle.stateChanged.connect(update_plot)
            self.mass_selector.currentIndexChanged.connect(
                lambda: update_plot() if self.view_toggle.isChecked() and self.radio_distribution.isChecked() else None
            )
            self.radio_distribution.toggled.connect(
                lambda: update_plot() if self.view_toggle.isChecked() else None
            )
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #545b62;
            }
        """)
        layout.addWidget(close_button)
        
        dialog.show()
            
    def _create_info_html(self, info):
        """
        Create HTML info table.
        
        Args:
            info (dict): SIA information dictionary
            
        Returns:
            str: HTML formatted information
        """
        instrument_type = info.get('instrument_type', 'Unknown')
        
        return f"""
        <h3>Single-Ion Distribution Information</h3>
        
        <table style="width: 100%; border-collapse: collapse;">
            <tr style="background-color: #f0f0f0;">
                <td style="padding: 8px; border: 1px solid #ddd;"><b>Sample Name:</b></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{info['sample_name']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><b>Calculated σ (SIA):</b></td>
                <td style="padding: 8px; border: 1px solid #ddd;"><b>{info['calculated_sigma']:.3f}</b></td>
            </tr>
            <tr style="background-color: #f0f0f0;">
                <td style="padding: 8px; border: 1px solid #ddd;"><b>Distribution Points:</b></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{info['distribution_points']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><b>Mean Signal:</b></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{info['mean_signal']:.1f} counts</td>
            </tr>
        </table>
        """
    
    def _create_sigma_comparison_plot(self, info):
        """
        Create sigma comparison plot showing all masses and their sigma values.
        
        Args:
            info (dict): Overall SIA info dict
            
        Returns:
            pg.PlotWidget: Plot widget with sigma comparison
        """
        from PySide6.QtGui import QFont, QPen, QColor
        from widget.custom_plot_widget import CustomPlotItem
        
        custom_plot_item = CustomPlotItem()
        plot_widget = pg.PlotWidget(plotItem=custom_plot_item)
        custom_plot_item.plot_widget = plot_widget
        
        plot_widget.persistent_dialog_settings = {}
        plot_widget.custom_settings = {}
        
        plot_widget.custom_axis_labels = {
            'left': {'text': 'Sigma (σ)', 'units': None},
            'bottom': {'text': 'Mass (m/z)', 'units': None}
        }
        
        def open_plot_settings():
            from widget.custom_plot_widget import PlotSettingsDialog
            dialog = PlotSettingsDialog(plot_widget, self.main_window)
            if dialog.exec():
                pass
        
        plot_widget.open_plot_settings = open_plot_settings
        
        plot_widget.setBackground('w')
        
        plot_item = plot_widget.getPlotItem()
        plot_item.showGrid(x=True, y=True, alpha=0.3)
        
        axis_pen = QPen(QColor("#000000"), 2)
        text_color = QColor("#000000")
        
        tick_font = QFont('Times New Roman', 20)
        tick_font.setBold(True)
        
        for axis_name in ['left', 'bottom', 'top', 'right']:
            ax = plot_item.getAxis(axis_name)
            ax.setPen(axis_pen)
            ax.setTextPen(text_color)
            ax.setStyle(
                tickFont=tick_font,
                tickTextOffset=10,
                tickLength=10
            )
        
        plot_widget.setLabel('left', 'Sigma (σ)', color="#000000", 
                            font='bold 20pt Times New Roman')
        plot_widget.setLabel('bottom', 'Mass (m/z)', color="#000000", 
                            font='bold 20pt Times New Roman')
        
        plot_item.getAxis('top').setStyle(showValues=False)
        plot_item.getAxis('right').setStyle(showValues=False)
        
        if hasattr(self, 'per_mass_distributions') and self.per_mass_distributions:
            masses = []
            sigmas = []
            
            for mass_key, mass_data in self.per_mass_distributions.items():
                masses.append(mass_data['mass'])
                sigmas.append(mass_data['sigma'])
            
            masses = np.array(masses)
            sigmas = np.array(sigmas)
            
            sort_idx = np.argsort(masses)
            masses = masses[sort_idx]
            sigmas = sigmas[sort_idx]
            
            mean_sigma = np.mean(sigmas)
            std_sigma = np.std(sigmas)
            
            line_1sd_upper = pg.InfiniteLine(
                pos=mean_sigma + std_sigma,
                angle=0,
                pen=pg.mkPen(color=(128, 128, 128), width=2, style=Qt.DashLine),
                label=None
            )
            plot_widget.addItem(line_1sd_upper)
            
            line_1sd_lower = pg.InfiniteLine(
                pos=mean_sigma - std_sigma,
                angle=0,
                pen=pg.mkPen(color=(128, 128, 128), width=2, style=Qt.DashLine),
                label=None
            )
            plot_widget.addItem(line_1sd_lower)
            
            line_2sd_upper = pg.InfiniteLine(
                pos=mean_sigma + 2*std_sigma,
                angle=0,
                pen=pg.mkPen(color=(180, 180, 180), width=2, style=Qt.DotLine),
                label=None
            )
            plot_widget.addItem(line_2sd_upper)
            
            line_2sd_lower = pg.InfiniteLine(
                pos=mean_sigma - 2*std_sigma,
                angle=0,
                pen=pg.mkPen(color=(180, 180, 180), width=2, style=Qt.DotLine),
                label=None
            )
            plot_widget.addItem(line_2sd_lower)
            
            mean_line = pg.InfiniteLine(
                pos=mean_sigma,
                angle=0,
                pen=pg.mkPen(color=(100, 100, 100), width=2, style=Qt.SolidLine),
                label=None
            )
            plot_widget.addItem(mean_line)
            
            scatter = pg.ScatterPlotItem(
                x=masses,
                y=sigmas,
                symbol='o',
                size=10,
                pen=pg.mkPen('b', width=2),
                brush=pg.mkBrush(65, 105, 225, 200)
            )
            plot_widget.addItem(scatter)
            
            mean_text = pg.TextItem(
                f'Mean σ = {mean_sigma:.3f}',
                color=(100, 100, 100),
                anchor=(0, 2),
                html=f'<div style="font-size: 18pt; font-family: Times New Roman; font-weight: bold; color: rgb(100, 100, 100);">Mean σ = {mean_sigma:.3f}</div>'
            )
            mean_text.setPos(masses[0], mean_sigma * 1.02)
            plot_widget.addItem(mean_text)
            
            sd_text_upper = pg.TextItem(
                f'+1 SD',
                color=(128, 128, 128),
                anchor=(1, 1),
                html=f'<div style="font-size: 18pt; font-family: Times New Roman; color: rgb(128, 128, 128);">+1 SD</div>'
            )
            sd_text_upper.setPos(masses[-1], mean_sigma + std_sigma)
            plot_widget.addItem(sd_text_upper)
            
            sd_text_lower = pg.TextItem(
                f'-1 SD',
                color=(128, 128, 128),
                anchor=(1, 0),
                html=f'<div style="font-size: 18pt; font-family: Times New Roman; color: rgb(128, 128, 128);">-1 SD</div>'
            )
            sd_text_lower.setPos(masses[-1], mean_sigma - std_sigma)
            plot_widget.addItem(sd_text_lower)
            
            sd2_text_upper = pg.TextItem(
                f'+2 SD (95%)',
                color=(180, 180, 180),
                anchor=(1, 1),
                html=f'<div style="font-size: 18pt; font-family: Times New Roman; color: black;"> (95%)</div>'
            )
            sd2_text_upper.setPos(masses[-1], mean_sigma + 2*std_sigma)
            plot_widget.addItem(sd2_text_upper)
            
            sd2_text_lower = pg.TextItem(
                f'-2 SD (95%)',
                color=(180, 180, 180),
                anchor=(1, 0),
                html=f'<div style="font-size: 18pt; font-family: Times New Roman; color: black;"> (95%)</div>'
            )
            sd2_text_lower.setPos(masses[-1], mean_sigma - 2*std_sigma)
            plot_widget.addItem(sd2_text_lower)
            
            plot_widget.setXRange(masses.min() * 0.99, masses.max() * 1.01, padding=0)
            y_min = min(sigmas.min(), mean_sigma - 2*std_sigma) * 0.9
            y_max = max(sigmas.max(), mean_sigma + 2*std_sigma) * 1.1
            plot_widget.setYRange(y_min, y_max, padding=0)
        
        plot_widget.setMinimumHeight(400)
        
        return plot_widget
        
    def _create_sia_plot(self, info, mass_key=None):
        """
        Create SIA plot widget with customizable fonts via right-click menu.
        
        Args:
            info (dict): Overall SIA info dict
            mass_key (str | None): If provided, plot for specific mass. If None, plot overall.
            
        Returns:
            pg.PlotWidget: Plot widget with custom settings dialog
        """
        from PySide6.QtGui import QFont, QPen, QColor
        from widget.custom_plot_widget import CustomPlotItem
        
        custom_plot_item = CustomPlotItem()
        plot_widget = pg.PlotWidget(plotItem=custom_plot_item)
        custom_plot_item.plot_widget = plot_widget
        
        plot_widget.persistent_dialog_settings = {}
        plot_widget.custom_settings = {}
        
        plot_widget.custom_axis_labels = {
            'left': {'text': 'Probability Density', 'units': None},
            'bottom': {'text': 'Counts', 'units': None}
        }
        
        def open_plot_settings():
            from widget.custom_plot_widget import PlotSettingsDialog
            dialog = PlotSettingsDialog(plot_widget, self.main_window)
            if dialog.exec():
                pass
        
        plot_widget.open_plot_settings = open_plot_settings
        
        plot_widget.setBackground('w')
        
        instrument_type = info.get('instrument_type', 'Unknown')
        
        if mass_key is not None and hasattr(self, 'per_mass_distributions'):
            mass_data = self.per_mass_distributions[mass_key]
            signal_values_raw = mass_data['distribution'][:, 0]
            weights = mass_data['distribution'][:, 1]
            mean_signal = mass_data['mean_signal']
            calculated_sigma = mass_data['sigma']
            mass_value = mass_data['mass']
        else:
            signal_values_raw = info['signal_values']
            weights = info['weights']
            mean_signal = info['mean_signal']
            calculated_sigma = info['calculated_sigma']
        
        average_single_ion_area = info.get('average_single_ion_area', 1.0)
        
        plot_item = plot_widget.getPlotItem()
        plot_item.showGrid(x=False, y=False)
        
        axis_pen = QPen(QColor("#000000"), 2)
        text_color = QColor("#000000")
        
        tick_font = QFont('Times New Roman', 20)
        tick_font.setBold(True)
        
        for axis_name in ['left', 'bottom', 'top', 'right']:
            ax = plot_item.getAxis(axis_name)
            ax.setPen(axis_pen)
            ax.setTextPen(text_color)
            ax.setStyle(
                tickFont=tick_font,
                tickTextOffset=10,
                tickLength=10
            )
        
        plot_widget.setLabel('left', 'Probability Density', color="#000000", 
                            font='bold 20pt Times New Roman')
        plot_widget.setLabel('bottom', 'Counts', color="#000000", 
                            font='bold 20pt Times New Roman')
        
        plot_item.getAxis('top').setStyle(showValues=False)
        plot_item.getAxis('right').setStyle(showValues=False)
        
        signal_values = signal_values_raw / average_single_ion_area
        weights_normalized = weights / (np.sum(weights) * np.mean(np.diff(signal_values)))
        bar_width = np.diff(signal_values).mean() if len(signal_values) > 1 else 1
        
        for x, h in zip(signal_values, weights_normalized):
            bar = pg.BarGraphItem(
                x=[x],
                height=[h],
                width=bar_width * 0.9,
                brush=pg.mkBrush(220, 220, 220, 255),
                pen=pg.mkPen('k', width=1)
            )
            plot_widget.addItem(bar)
        
        try:
            mu_adc = np.log(mean_signal) - 0.5 * calculated_sigma**2
            sigma_adc = calculated_sigma
            
            mu_ion = mu_adc - np.log(average_single_ion_area)
            sigma_ion = sigma_adc
            
            x_smooth = np.linspace(0.01, np.max(signal_values) * 1.5, 500)
            pdf_values = lognormal_pdf_scipy(x_smooth, mu_ion, sigma_ion)
            
            plot_widget.plot(x_smooth, pdf_values, 
                            pen=pg.mkPen(color='r', width=2.5), 
                            name=None)
        except Exception as e:
            print(f"Lognormal fit failed: {e}")
        
        quantile_value = None
        try:
            mu_adc = np.log(mean_signal) - 0.5 * calculated_sigma**2
            sigma_adc = calculated_sigma
            quantile_value_adc = np.exp(mu_adc + np.sqrt(2.0 * sigma_adc**2) * erfinv(2.0 * 0.9999 - 1.0))
            quantile_value = quantile_value_adc / average_single_ion_area
            
            if not np.isfinite(quantile_value) or quantile_value <= 0:
                raise ValueError("Invalid quantile value")
                
        except Exception as e:
            print(f"Quantile calculation failed, using fallback: {e}")
            try:
                cumulative_weights = np.cumsum(weights)
                cumulative_weights = cumulative_weights / cumulative_weights[-1]
                quantile_idx = np.searchsorted(cumulative_weights, 0.9999)
                quantile_value = signal_values[min(quantile_idx, len(signal_values)-1)]
                
                if not np.isfinite(quantile_value) or quantile_value <= 0:
                    quantile_value = None
            except:
                quantile_value = None
        
        if quantile_value is not None and np.isfinite(quantile_value):
            quantile_line = pg.InfiniteLine(
                pos=quantile_value, 
                angle=90, 
                pen=pg.mkPen(color='r', width=2, style=Qt.DotLine),
                label=None
            )
            plot_widget.addItem(quantile_line)
            
            quantile_text = pg.TextItem(
                '0.9999ᵗʰ quantile', 
                color='r', 
                anchor=(0.5, 0),
                html='<div style="font-size: 20pt; font-family: Times New Roman; font-weight: bold; color: black;">0.9999<sup>th</sup> quantile</div>'
            )
            quantile_text.setPos(quantile_value, np.max(weights_normalized) * 1)
            plot_widget.addItem(quantile_text)
        
        sigma_text = pg.TextItem(
            f'σ = {calculated_sigma:.2f}', 
            color='k', 
            anchor=(0, 1),
            html=f'<div style="font-size: 20pt; font-family: Times New Roman; font-weight: bold; color: black;">σ = {calculated_sigma:.2f}</div>'
        )
        sigma_text.setPos(signal_values[int(len(signal_values)*0.15)], 
                        np.max(weights_normalized) * 0.95)
        plot_widget.addItem(sigma_text)
        
        plot_widget.setXRange(0, np.max(signal_values) * 1.3)
        plot_widget.setYRange(0, np.max(weights_normalized) * 1.15)
        
        plot_widget.showGrid(x=False, y=False, alpha=0)
        
        plot_widget.setMinimumHeight(400)
        
        return plot_widget
                
    def clear_single_ion_distribution(self):
        """
        Clear the loaded SIA.
        
        Args:
            None
            
        Returns:
            None
        """
        if self._is_processing:
            QMessageBox.information(
                self.main_window,
                "Processing in Progress",
                "Cannot clear SIA while processing."
            )
            return
        
        reply = QMessageBox.question(
            self.main_window,
            "Clear Single-Ion Distribution",
            "Are you sure you want to clear the loaded single-ion distribution?\n\n"
            "This will reset σ to default value (0.47)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            total_elements_updated, total_samples_updated = self._clear_sia_data()
            self._update_ui_after_clear()
            self._show_clear_success_message(total_elements_updated, total_samples_updated)
    
    def _clear_sia_data(self):
        """
        Clear SIA data.
        
        Args:
            None
            
        Returns:
            tuple: (total_elements_updated, total_samples_updated)
        """
        self.single_ion_distribution_data = None
        self.single_ion_source_folder = None
        self.single_ion_info = {}
        
        default_sigma = 0.47
        total_elements_updated = 0
        total_samples_updated = 0
        
        if hasattr(self.main_window, 'sigma_spinbox'):
            self.main_window.sigma_spinbox.valueChanged.disconnect()
            self.main_window.sigma_spinbox.setValue(default_sigma)
            self.main_window.sigma_spinbox.valueChanged.connect(self.main_window.on_sigma_changed)
            
            for sample_name in self.main_window.sample_parameters:
                for element_key in self.main_window.sample_parameters[sample_name]:
                    if 'sigma' not in self.main_window.sample_parameters[sample_name][element_key]:
                        self.main_window.sample_parameters[sample_name][element_key]['sigma'] = 0.47
                    else:
                        self.main_window.sample_parameters[sample_name][element_key]['sigma'] = default_sigma
        
        if hasattr(self.main_window, 'parameters_table'):
            self.main_window.update_parameters_table()
        
        return total_elements_updated, total_samples_updated
    
    def _update_ui_after_clear(self):
        """
        Update UI after clear.
        
        Args:
            None
            
        Returns:
            None
        """
        self.info_sid_button.setEnabled(False)
        self.clear_sid_button.setEnabled(False)
        self.upload_sid_button.setStyleSheet("")
        
        default_sigma = 0.47
        self.main_window.status_label.setText(
            f"SIA cleared. σ reset to {default_sigma}"
        )
    
    def _show_clear_success_message(self, total_elements_updated, total_samples_updated):
        """
        Show clear success message.
        
        Args:
            total_elements_updated (int): Number of elements updated
            total_samples_updated (int): Number of samples updated
            
        Returns:
            None
        """
        default_sigma = 0.47
        
        QMessageBox.information(
            self.main_window,
            "Cleared",
            f"Single-ion distribution cleared successfully.\n\n"
            f"σ parameter reset to {default_sigma}"
        )
    
    def is_sia_loaded(self):
        """
        Check if SIA is loaded.
        
        Args:
            None
            
        Returns:
            bool: True if SIA is loaded
        """
        return self.single_ion_distribution_data is not None
    
    def get_sia_info(self):
        """
        Get SIA info.
        
        Args:
            None
            
        Returns:
            dict: Copy of SIA info dictionary
        """
        return self.single_ion_info.copy() if self.single_ion_info else {}
    
    def get_calculated_sigma(self):
        """
        Get calculated sigma.
        
        Args:
            None
            
        Returns:
            float: Calculated sigma value
        """
        return self.single_ion_info.get('calculated_sigma', 0.47)
    
    def stop_processing(self):
        """
        Stop processing.
        
        Args:
            None
            
        Returns:
            None
        """
        if self._is_processing and self.sia_worker:
            self.sia_worker.stop_processing()
            self._reset_processing_state()
    
    def cleanup(self):
        """
        Clean up resources.
        
        Args:
            None
            
        Returns:
            None
        """
        if self.sia_thread and self.sia_thread.isRunning():
            if self.sia_worker:
                self.sia_worker.stop_processing()
            self.sia_thread.quit()
            self.sia_thread.wait(3000)
        
        self.sia_thread = None
        self.sia_worker = None
        self._is_processing = False