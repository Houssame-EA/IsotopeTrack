import pickle
import gzip
import datetime
import platform
import subprocess
from pathlib import Path
from PySide6.QtWidgets import QMessageBox, QFileDialog, QProgressDialog, QApplication
from PySide6.QtCore import Qt, QPointF


class ProjectManager:
    """
    Handles saving and loading of IsotopeTrack project files.
    Manages project state serialization/deserialization including canvas workflows.
    """
    
    def __init__(self, main_window):
        """
        Initialize the ProjectManager with a reference to the main window.
        
        Args:
            main_window (object): Reference to the MainWindow instance
            
        Returns:
            None
        """
        self.main_window = main_window
        self.project_version = '1.0'
        self.icon_path = '/Users/Houssame/Desktop/App_mac/images/save_icon.ico'
    
    def _set_file_icon_cross_platform(self, file_path):
        """
        Set custom icon for the saved project file on both Windows and macOS.
        
        Args:
            file_path (str): Path to the saved project file
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not Path(self.icon_path).exists():
            print(f"Icon file not found at: {self.icon_path}")
            return False
        
        system = platform.system()
        
        try:
            if system == "Darwin":  
                return self._set_icon_macos(file_path)
            elif system == "Windows":
                return self._set_icon_windows(file_path)
            else:  
                return self._set_icon_linux(file_path)
        except Exception as e:
            print(f"Error setting file icon: {str(e)}")
            return False
    
    def _set_icon_macos(self, file_path):
        """
        Set custom icon for macOS using native tools.
        
        Args:
            file_path (str): Path to the saved project file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            try:
                from Foundation import NSWorkspace, NSImage
                
                workspace = NSWorkspace.sharedWorkspace()
                image = NSImage.alloc().initWithContentsOfFile_(self.icon_path)
                
                if image:
                    success = workspace.setIcon_forFile_options_(
                        image,
                        str(file_path),
                        0
                    )
                    if success:
                        return True
            except ImportError:
                pass
            
            applescript = f'''
            use framework "Foundation"
            use framework "AppKit"
            
            set sourcePath to "{self.icon_path}"
            set destPath to "{str(file_path)}"
            
            set sourceImage to current application's NSImage's alloc()'s initWithContentsOfFile:sourcePath
            if sourceImage is not missing value then
                set workspace to current application's NSWorkspace's sharedWorkspace()
                set success to workspace's setIcon:sourceImage forFile:destPath options:0
                return success as boolean
            else
                return false
            end if
            '''
            
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"macOS icon setting error: {str(e)}")
            return False
    
    def _set_icon_windows(self, file_path):
        """
        Set custom icon for Windows by registering file type.
        
        Args:
            file_path (str): Path to the saved project file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            import winreg
            
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.itproj") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "IsotopeTrackProject")
            
            icon_key_path = r"Software\Classes\IsotopeTrackProject\DefaultIcon"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, icon_key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f"{self.icon_path},0")
            
            name_key_path = r"Software\Classes\IsotopeTrackProject"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, name_key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "IsotopeTrack Project File")
            
            try:
                import ctypes
                SHCNE_ASSOCCHANGED = 0x08000000
                SHCNF_IDLIST = 0x0000
                ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
            except:
                pass
            
            return True
            
        except Exception as e:
            print(f"Windows icon setting error: {str(e)}")
            return False
    
    def _set_icon_linux(self, file_path):
        """
        Set custom icon for Linux.
        
        Args:
            file_path (str): Path to the saved project file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            desktop_file = Path(file_path).with_suffix('.desktop')
            
            desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=IsotopeTrack Project
Icon={self.icon_path}
Terminal=false
"""
            
            with open(desktop_file, 'w') as f:
                f.write(desktop_content)
            
            desktop_file.chmod(0o755)
            return True
            
        except Exception as e:
            print(f"Linux icon setting error: {str(e)}")
            return False
    
    def save_project(self):
        """
        Save the current project state to a compressed file.
        
        Args:
            None
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        if not self.main_window.data_by_sample:
            QMessageBox.warning(
                self.main_window, 
                "No Data", 
                "No data to save. Please load data first."
            )
            return False
            
        default_filename = f"IsotopeTrack_Project_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.itproj"
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Save Project",
            default_filename,
            "IsotopeTrack Project Files (*.itproj)"
        )
        
        if not file_path:
            return False
            
        progress_dialog = QProgressDialog("Saving project...", "Cancel", 0, 100, self.main_window)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.show()
        QApplication.processEvents()
        
        try:
            progress_dialog.setValue(10)
            progress_dialog.setLabelText("Saving canvas workflow...")
            QApplication.processEvents()
            
            canvas_state = self._serialize_canvas_state()
            
            progress_dialog.setValue(20)
            progress_dialog.setLabelText("Collecting project data...")
            QApplication.processEvents()
            
            project_data = self._collect_project_data(canvas_state)
            
            progress_dialog.setValue(60)
            progress_dialog.setLabelText("Compressing and saving...")
            QApplication.processEvents()
            
            with gzip.open(file_path, 'wb') as f:
                pickle.dump(project_data, f)
            
            progress_dialog.setValue(85)
            progress_dialog.setLabelText("Setting file icon...")
            QApplication.processEvents()
            
            self._set_file_icon_cross_platform(file_path)
                
            progress_dialog.setValue(100)
            self.main_window.status_label.setText(f"Project saved to {file_path}")
            QMessageBox.information(
                self.main_window, 
                "Save Complete", 
                f"Project saved successfully to:\n{file_path}"
            )
            
            self.main_window.unsaved_changes = False
            return True
            
        except Exception as e:
            QMessageBox.critical(
                self.main_window, 
                "Save Error", 
                f"Error saving project: {str(e)}"
            )
            return False
        finally:
            progress_dialog.close()
    
    def load_project(self):
        """
        Load a previously saved project.
        
        Args:
            None
            
        Returns:
            bool: True if load was successful, False otherwise
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Load Project",
            "",
            "IsotopeTrack Project Files (*.itproj)"
        )
        
        if not file_path:
            return False

        progress_dialog = QProgressDialog("Loading project...", "Cancel", 0, 100, self.main_window)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.show()
        QApplication.processEvents()
        
        try:
            progress_dialog.setValue(10)
            progress_dialog.setLabelText("Reading project file...")
            QApplication.processEvents()
            
            with gzip.open(file_path, 'rb') as f:
                project_data = pickle.load(f)
                
            progress_dialog.setValue(30)
            progress_dialog.setLabelText("Restoring project data...")
            QApplication.processEvents()
            
            file_version = project_data.get('version', '1.0')
            if not self._check_version_compatibility(file_version):
                QMessageBox.warning(
                    self.main_window,
                    "Version Warning",
                    f"This project was saved with version {file_version}. "
                    f"Current version is {self.project_version}. "
                    "Some features may not work correctly."
                )
            
            self._reset_data_structures()
            self._restore_project_data(project_data)
            
            progress_dialog.setValue(60)
            progress_dialog.setLabelText("Updating user interface...")
            QApplication.processEvents()
            
            self._update_ui_after_load()
            
            progress_dialog.setValue(80)
            progress_dialog.setLabelText("Restoring canvas workflow...")
            QApplication.processEvents()
            
            canvas_state = project_data.get('canvas_state')
            if canvas_state:
                self._deserialize_canvas_state(canvas_state)
            
            progress_dialog.setValue(100)
            self.main_window.status_label.setText(f"Project loaded from {file_path}")
            
            self.main_window.unsaved_changes = False
            return True
            
        except Exception as e:
            QMessageBox.critical(
                self.main_window, 
                "Load Error", 
                f"Error loading project: {str(e)}"
            )
            return False
        finally:
            progress_dialog.close()
    
    def _collect_project_data(self, canvas_state):
        """
        Collect all project data for saving.
        
        Args:
            canvas_state (dict): Serialized canvas state
            
        Returns:
            dict: Project data dictionary
        """
        return {
            'selected_isotopes': self.main_window.selected_isotopes,
            'data_by_sample': self.main_window.data_by_sample,
            'time_array_by_sample': self.main_window.time_array_by_sample,
            'sample_parameters': self.main_window.sample_parameters,
            'sample_detected_peaks': self.main_window.sample_detected_peaks,
            'sample_dwell_times': self.main_window.sample_dwell_times,
            'sample_results_data': self.main_window.sample_results_data,
            'isotope_method_preferences': self.main_window.isotope_method_preferences,
            'sample_particle_data': self.main_window.sample_particle_data,
            'sample_analysis_dates': self.main_window.sample_analysis_dates,
            'sample_to_folder_map': self.main_window.sample_to_folder_map,
            'element_thresholds': self.main_window.element_thresholds,
            'element_limits': getattr(self.main_window, 'element_limits', {}),
            'sample_run_info': self.main_window.sample_run_info,
            'sample_method_info': getattr(self.main_window, 'sample_method_info', {}),
            
            'calibration_results': self.main_window.calibration_results,
            'average_transport_rate': self.main_window.average_transport_rate,
            'selected_transport_rate_methods': self.main_window.selected_transport_rate_methods,
            'transport_rate_methods': getattr(self.main_window, 'transport_rate_methods', ["Liquid weight", "Number based", "Mass based"]),
            
            'element_mass_fractions': getattr(self.main_window, 'element_mass_fractions', {}),
            'element_densities': getattr(self.main_window, 'element_densities', {}),
            'element_molecular_weights': getattr(self.main_window, 'element_molecular_weights', {}),  
            'sample_mass_fractions': getattr(self.main_window, 'sample_mass_fractions', {}),
            'sample_densities': getattr(self.main_window, 'sample_densities', {}),
            'sample_molecular_weights': getattr(self.main_window, 'sample_molecular_weights', {}), 
            
            'overlap_threshold_percentage': getattr(self.main_window, 'overlap_threshold_percentage', 50.0),
            '_global_sigma': getattr(self.main_window, '_global_sigma', 0.47),
            'multi_element_particles': getattr(self.main_window, 'multi_element_particles', []),
            'detection_states': getattr(self.main_window, 'detection_states', {}),
            'needs_initial_detection': list(getattr(self.main_window, 'needs_initial_detection', set())),
            
            'sidebar_width': getattr(self.main_window, 'sidebar_width', 200),
            'sidebar_visible': getattr(self.main_window, 'sidebar_visible', True),
            'current_sample': self.main_window.current_sample,
            
            'csv_config': getattr(self.main_window, 'csv_config', None),
            'pending_csv_processing': getattr(self.main_window, 'pending_csv_processing', False),
            
            'element_parameter_hashes': getattr(self.main_window, 'element_parameter_hashes', {}),
            '_display_label_to_element': getattr(self.main_window, '_display_label_to_element', {}),
            
            'all_masses': self.main_window.all_masses,
            'folder_paths': getattr(self.main_window, 'folder_paths', []),
            
            'canvas_state': canvas_state,
            
            'version': self.project_version,
            'save_timestamp': datetime.datetime.now().isoformat(),
            'application_version': '1.0',
        }
    
    def _restore_project_data(self, project_data):
        """
        Restore project data from loaded file.
        
        Args:
            project_data (dict): Dictionary containing project data
            
        Returns:
            None
        """
        self.main_window.selected_isotopes = project_data.get('selected_isotopes', {})
        self.main_window.data_by_sample = project_data.get('data_by_sample', {})
        self.main_window.time_array_by_sample = project_data.get('time_array_by_sample', {})
        self.main_window.sample_parameters = project_data.get('sample_parameters', {})
        self.main_window.sample_detected_peaks = project_data.get('sample_detected_peaks', {})
        self.main_window.sample_dwell_times = project_data.get('sample_dwell_times', {})
        self.main_window.sample_results_data = project_data.get('sample_results_data', {})
        self.main_window.isotope_method_preferences = project_data.get('isotope_method_preferences', {})
        self.main_window.sample_particle_data = project_data.get('sample_particle_data', {})
        self.main_window.sample_analysis_dates = project_data.get('sample_analysis_dates', {})
        self.main_window.sample_to_folder_map = project_data.get('sample_to_folder_map', {})
        self.main_window.element_thresholds = project_data.get('element_thresholds', {})
        self.main_window.element_limits = project_data.get('element_limits', {})
        self.main_window.sample_run_info = project_data.get('sample_run_info', {})
        self.main_window.sample_method_info = project_data.get('sample_method_info', {})
        
        self.main_window.calibration_results = project_data.get('calibration_results', {})
        self.main_window.average_transport_rate = project_data.get('average_transport_rate', 0)
        self.main_window.selected_transport_rate_methods = project_data.get('selected_transport_rate_methods', [])
        self.main_window.transport_rate_methods = project_data.get('transport_rate_methods', ["Liquid weight", "Number based", "Mass based"])
        
        self.main_window.element_mass_fractions = project_data.get('element_mass_fractions', {})
        self.main_window.element_densities = project_data.get('element_densities', {})
        self.main_window.element_molecular_weights = project_data.get('element_molecular_weights', {})  
        self.main_window.sample_mass_fractions = project_data.get('sample_mass_fractions', {})
        self.main_window.sample_densities = project_data.get('sample_densities', {})
        self.main_window.sample_molecular_weights = project_data.get('sample_molecular_weights', {})  
        
        self.main_window.overlap_threshold_percentage = project_data.get('overlap_threshold_percentage', 50.0)
        self.main_window._global_sigma = project_data.get('_global_sigma', 0.47)
        self.main_window.multi_element_particles = project_data.get('multi_element_particles', [])
        self.main_window.detection_states = project_data.get('detection_states', {})
        
        needs_initial_detection_list = project_data.get('needs_initial_detection', [])
        self.main_window.needs_initial_detection = set(needs_initial_detection_list)
        
        self.main_window.sidebar_width = project_data.get('sidebar_width', 200)
        self.main_window.sidebar_visible = project_data.get('sidebar_visible', True)
        self.main_window.current_sample = project_data.get('current_sample', None)
        
        self.main_window.csv_config = project_data.get('csv_config', None)
        self.main_window.pending_csv_processing = project_data.get('pending_csv_processing', False)
        
        self.main_window.element_parameter_hashes = project_data.get('element_parameter_hashes', {})
        self.main_window._display_label_to_element = project_data.get('_display_label_to_element', {})
        
        self.main_window._formatted_label_cache = {}
        self.main_window._element_data_cache = {}
        
        self.main_window.all_masses = project_data.get('all_masses', None)
        self.main_window.folder_paths = project_data.get('folder_paths', [])
        
        if self.main_window.current_sample:
            if self.main_window.current_sample in self.main_window.data_by_sample:
                self.main_window.data = self.main_window.data_by_sample[self.main_window.current_sample].copy()
            if self.main_window.current_sample in self.main_window.time_array_by_sample:
                self.main_window.time_array = self.main_window.time_array_by_sample[self.main_window.current_sample].copy()
            if self.main_window.current_sample in self.main_window.sample_detected_peaks:
                self.main_window.detected_peaks = self.main_window.sample_detected_peaks[self.main_window.current_sample].copy()
            else:
                self.main_window.detected_peaks = {}
        else:
            self.main_window.data = {}
            self.main_window.time_array = None
            self.main_window.detected_peaks = {}
    
    def _serialize_canvas_state(self):
        """
        Serialize the current canvas state for saving.
        
        Args:
            None
            
        Returns:
            dict | None: Serialized canvas state or None if no canvas exists
        """
        if not hasattr(self.main_window, 'canvas_results_dialog') or not self.main_window.canvas_results_dialog:
            return None
        
        scene = self.main_window.canvas_results_dialog.canvas.scene
        if not scene:
            return None
        
        canvas_state = {
            'workflow_nodes': [],
            'workflow_links': [],
            'scene_rect': {
                'x': scene.sceneRect().x(),
                'y': scene.sceneRect().y(),
                'width': scene.sceneRect().width(),
                'height': scene.sceneRect().height()
            }
        }
        
        node_id_map = {}
        
        for i, node in enumerate(scene.workflow_nodes):
            node_id = f"node_{i}"
            node_id_map[node] = node_id
            
            node_data = {
                'id': node_id,
                'title': node.title,
                'node_type': node.node_type,
                'position': {
                    'x': node.position.x(),
                    'y': node.position.y()
                }
            }
            
            self._serialize_node_config(node, node_data)
            canvas_state['workflow_nodes'].append(node_data)
        
        for link in scene.workflow_links:
            if link.source_node in node_id_map and link.sink_node in node_id_map:
                link_data = {
                    'source_node_id': node_id_map[link.source_node],
                    'source_channel': link.source_channel,
                    'sink_node_id': node_id_map[link.sink_node],
                    'sink_channel': link.sink_channel,
                    'enabled': link.enabled
                }
                canvas_state['workflow_links'].append(link_data)
        
        return canvas_state
    
    def _serialize_node_config(self, node, node_data):
        """
        Serialize node-specific configuration.
        
        Args:
            node (object): Workflow node to serialize
            node_data (dict): Dictionary to store node data
            
        Returns:
            None
        """
        config_attributes = [
            'selected_sample', 'selected_samples', 'selected_data_type',
            'selected_isotopes', 'sum_replicates', 'replicate_samples',
            'config', '_has_input', '_has_output', 'input_channels', 'output_channels'
        ]
        
        for attr in config_attributes:
            if hasattr(node, attr):
                value = getattr(node, attr)
                if isinstance(value, set):
                    value = list(value)
                node_data[attr] = value
    
    def _deserialize_canvas_state(self, canvas_state):
        """
        Recreate the canvas state from saved data.
        
        Args:
            canvas_state (dict): Serialized canvas state dictionary
            
        Returns:
            None
        """
        if not canvas_state:
            return
        
        try:
            from widget.canvas_widgets import (BatchSampleSelectorNode,
                CanvasResultsDialog, SampleSelectorNode, MultipleSampleSelectorNode,
                HistogramPlotNode, ElementBarChartPlotNode, CorrelationPlotNode,
                PieChartPlotNode, ElementCompositionPlotNode, HeatmapPlotNode,
                IsotopicRatioPlotNode, TrianglePlotNode,ClusteringPlotNode, AIAssistantNode, MolarRatioPlotNode, BoxPlotNode
            )
        except ImportError as e:
            QMessageBox.warning(
                self.main_window,
                "Canvas Import Error",
                f"Could not import canvas components: {str(e)}\n"
                "Canvas workflow will not be restored."
            )
            return
        
        if not hasattr(self.main_window, 'canvas_results_dialog') or not self.main_window.canvas_results_dialog:
            self.main_window.canvas_results_dialog = CanvasResultsDialog(self.main_window)
        
        scene = self.main_window.canvas_results_dialog.canvas.scene
        
        scene.workflow_nodes.clear()
        scene.workflow_links.clear()
        scene.node_items.clear()
        scene.link_items.clear()
        scene.clear()
        
        scene_rect = canvas_state.get('scene_rect', {})
        if scene_rect:
            scene.setSceneRect(
                scene_rect.get('x', -1000),
                scene_rect.get('y', -1000), 
                scene_rect.get('width', 2000),
                scene_rect.get('height', 2000)
            )
        
        node_map = {}
        
        node_type_map = {
            "batch_sample_selector": BatchSampleSelectorNode,
            "sample_selector": SampleSelectorNode,
            "multiple_sample_selector": MultipleSampleSelectorNode,
            
            "histogram_plot": HistogramPlotNode,
            "element_bar_chart_plot": ElementBarChartPlotNode,
            "correlation_plot": CorrelationPlotNode,
            "pie_chart_plot": PieChartPlotNode,
            "element_composition_plot": ElementCompositionPlotNode,
            "heatmap_plot": HeatmapPlotNode,
            "molar_ratio_plot": MolarRatioPlotNode,
            "box_plot": BoxPlotNode,
            "isotopic_ratio_plot": IsotopicRatioPlotNode,
            "triangle_plot": TrianglePlotNode,
            "clustering_plot": ClusteringPlotNode,
            "ai_assistant": AIAssistantNode
        }
        
        for node_data in canvas_state.get('workflow_nodes', []):
            node_type = node_data.get('node_type')
            node_id = node_data.get('id')
            
            if node_type in node_type_map:
                workflow_node = node_type_map[node_type](self.main_window)
                
                self._deserialize_node_config(workflow_node, node_data)
                
                position = node_data.get('position', {'x': 0, 'y': 0})
                pos = QPointF(position['x'], position['y'])
                
                scene.add_node(workflow_node, pos)
                node_map[node_id] = workflow_node
        
        for link_data in canvas_state.get('workflow_links', []):
            source_node_id = link_data.get('source_node_id')
            sink_node_id = link_data.get('sink_node_id')
            
            if source_node_id in node_map and sink_node_id in node_map:
                source_node = node_map[source_node_id]
                sink_node = node_map[sink_node_id]
                source_channel = link_data.get('source_channel', 'output')
                sink_channel = link_data.get('sink_channel', 'input')
                
                link = scene.add_link(source_node, source_channel, sink_node, sink_channel)
                if link and 'enabled' in link_data:
                    link.enabled = link_data['enabled']
    
    def _deserialize_node_config(self, workflow_node, node_data):
        """
        Restore node configuration from saved data.
        
        Args:
            workflow_node (object): Node to configure
            node_data (dict): Saved node configuration
            
        Returns:
            None
        """
        config_attributes = [
            'selected_sample', 'selected_samples', 'selected_data_type',
            'selected_isotopes', 'sum_replicates', 'replicate_samples',
            'config', '_has_input', '_has_output', 'input_channels', 'output_channels'
        ]
        
        for attr in config_attributes:
            if attr in node_data:
                value = node_data[attr]
                if attr in ['needs_initial_detection'] and isinstance(value, list):
                    value = set(value)
                setattr(workflow_node, attr, value)
    
    def _reset_data_structures(self):
        """
        Reset all data structures before loading a saved project.
        
        Args:
            None
            
        Returns:
            None
        """
        data_structures = [
            'selected_isotopes', 'data_by_sample', 'time_array_by_sample',
            'sample_parameters', 'sample_detected_peaks', 'sample_dwell_times',
            'sample_results_data', 'isotope_method_preferences', 'sample_particle_data',
            'sample_analysis_dates', 'sample_to_folder_map', 'element_thresholds',
            'element_limits', 'sample_run_info', 'sample_method_info',
            'element_mass_fractions', 'element_densities', 'element_molecular_weights', 
            'sample_mass_fractions', 'sample_densities', 'sample_molecular_weights'  
        ]
        
        for attr in data_structures:
            setattr(self.main_window, attr, {})
        
        self.main_window.needs_initial_detection = set()
        
        self.main_window.multi_element_particles = []
        self.main_window.folder_paths = []
        
        self.main_window._formatted_label_cache = {}
        self.main_window._element_data_cache = {}
        self.main_window._display_label_to_element = {}
        
        self.main_window.current_sample = None
        self.main_window.data = {}
        self.main_window.time_array = None
        self.main_window.detected_peaks = {}
        self.main_window.all_masses = None
        
        self.main_window.overlap_threshold_percentage = 50.0
        self.main_window._global_sigma = 0.47
        self.main_window.sidebar_width = 200
        self.main_window.sidebar_visible = True
        self.main_window.csv_config = None
        self.main_window.pending_csv_processing = False
        
        self.main_window.calibration_results = {
            "Liquid weight": {},
            "Number based": {},
            "Mass based": {},
            "Ionic Calibration": {}
        }
        self.main_window.average_transport_rate = 0
        self.main_window.selected_transport_rate_methods = []
        self.main_window.transport_rate_methods = ["Liquid weight", "Number based", "Mass based"]
        
        self.main_window.sample_table.setRowCount(0)
        self.main_window.parameters_table.setRowCount(0)
        self.main_window.results_table.setRowCount(0)
        self.main_window.multi_element_table.setRowCount(0)
        
        self.main_window.plot_widget.clear()
        
        if hasattr(self.main_window, 'summary_label'):
            self.main_window.summary_label.setText("Select an element to view summary statistics")
    
    def _update_ui_after_load(self):
        """
        Update UI components after loading project.
        
        Args:
            None
            
        Returns:
            None
        """
        if hasattr(self.main_window, 'sigma_spinbox'):
            self.main_window.sigma_spinbox.setValue(self.main_window._global_sigma)
        
        self.main_window._build_element_lookup_cache()
        
        if (self.main_window.selected_isotopes and 
            self.main_window.all_masses and 
            not self.main_window.periodic_table_widget):
            
            from widget.periodic_table_widget import PeriodicTableWidget
            self.main_window.periodic_table_widget = PeriodicTableWidget()
            self.main_window.periodic_table_widget.selection_confirmed.connect(
                self.main_window.handle_isotopes_selected
            )
        
        if self.main_window.periodic_table_widget and self.main_window.all_masses:
            self.main_window.periodic_table_widget.update_available_masses(self.main_window.all_masses)
            if self.main_window.selected_isotopes:
                self.main_window._update_periodic_table_selections()
        
        self.main_window.update_sample_table()
        
        if self.main_window.current_sample and self.main_window.sample_table.rowCount() > 0:
            for row in range(self.main_window.sample_table.rowCount()):
                item = self.main_window.sample_table.item(row, 0)
                if item and item.text() == self.main_window.current_sample:
                    self.main_window.sample_table.selectRow(row)
                    self.main_window.on_sample_selected(item)
                    break
        elif self.main_window.sample_table.rowCount() > 0:
            item = self.main_window.sample_table.item(0, 0)
            if item:
                self.main_window.sample_table.selectRow(0)
                self.main_window.on_sample_selected(item)
        
        if hasattr(self.main_window, 'update_calibration_display'):
            self.main_window.update_calibration_display()
        
        if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window, 'sidebar_visible'):
            if not self.main_window.sidebar_visible:
                self.main_window.toggle_sidebar()
    
    def _check_version_compatibility(self, file_version):
        """
        Check if the file version is compatible with current version.
        
        Args:
            file_version (str): Version string from saved file
            
        Returns:
            bool: True if compatible, False if there might be issues
        """
        try:
            file_major, file_minor = map(float, file_version.split('.'))
            current_major, current_minor = map(float, self.project_version.split('.'))
            
            if file_major == current_major:
                return True
            
            if file_major > current_major:
                return False
                
            return True
            
        except (ValueError, AttributeError):
            return True
    
    def get_project_info(self, file_path):
        """
        Get basic information about a project file without fully loading it.
        
        Args:
            file_path (str): Path to the project file
            
        Returns:
            dict | None: Project information dictionary or None if error
        """
        try:
            with gzip.open(file_path, 'rb') as f:
                project_data = pickle.load(f)
                
            return {
                'version': project_data.get('version', 'Unknown'),
                'save_timestamp': project_data.get('save_timestamp', 'Unknown'),
                'application_version': project_data.get('application_version', 'Unknown'),
                'sample_count': len(project_data.get('data_by_sample', {})),
                'element_count': len(project_data.get('selected_isotopes', {})),
                'has_canvas_state': project_data.get('canvas_state') is not None,
                'file_size_mb': Path(file_path).stat().st_size / (1024 * 1024)
            }
        except Exception as e:
            print(f"Error reading project info: {str(e)}")
            return None