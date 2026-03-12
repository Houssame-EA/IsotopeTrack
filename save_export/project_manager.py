import sys
import pickle
import gzip
import datetime
import platform
import os
import subprocess
from pathlib import Path
from PySide6.QtWidgets import QMessageBox, QFileDialog, QProgressDialog, QApplication
from PySide6.QtCore import Qt, QPointF
from save_export.fast_project_io import (
    save_project_v2, load_project_auto, detect_format, estimate_project_size
)


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
        self.project_version = '1.0.1'
        
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self.icon_path = os.path.join(base_path, 'images', 'save_icon.ico')
        self.icon_path_mac = os.path.join(base_path, 'images', 'save_icon.icns')
        
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
Version=1.0.1
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
        filepath, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Save Project",
            "",
            "IsotopeTrack Project (*.itproj)"
        )
        if not filepath:
            return False

        if not filepath.endswith('.itproj'):
            filepath += '.itproj'

        try:
            self.main_window.save_current_parameters()

            self.main_window.progress_bar.setVisible(True)
            self.main_window.progress_bar.setValue(0)

            def progress_callback(pct, msg):
                self.main_window.progress_bar.setValue(pct)
                self.main_window.status_label.setText(msg)
                QApplication.processEvents()

            save_project_v2(filepath, self.main_window, progress_callback)

            self._set_file_icon_cross_platform(filepath)

            self.main_window.progress_bar.setVisible(False)
            self.main_window.unsaved_changes = False
            self.main_window.status_label.setText(f"Project saved: {filepath}")
            return True

        except Exception as e:
            self.main_window.progress_bar.setVisible(False)
            QMessageBox.critical(
                self.main_window, "Save Error",
                f"Error saving project: {str(e)}"
            )
            return False
        
    def load_project(self):
        """
        Load a previously saved project.
        
        Args:
            None
            
        Returns:
            bool: True if load was successful, False otherwise
        """
        filepath, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Load Project",
            "",
            "IsotopeTrack Project (*.itproj)"
        )
        if not filepath:
            return False

        try:
            self.main_window.reset_data_structures()

            self.main_window.progress_bar.setVisible(True)
            self.main_window.progress_bar.setValue(0)

            def progress_callback(pct, msg):
                self.main_window.progress_bar.setValue(pct)
                self.main_window.status_label.setText(msg)
                QApplication.processEvents()

            # Auto-detect format and load
            result = load_project_auto(filepath, self.main_window, progress_callback)

            if isinstance(result, dict):
                # V1 format returned raw dict -> use existing restore logic
                self._restore_project_data(result)
            # else: V2 format already restored data directly to main_window

            # Post-load setup (same for both formats)
            self._finalize_load()

            self.main_window.progress_bar.setVisible(False)
            self.main_window.unsaved_changes = False
            self.main_window.status_label.setText(f"Project loaded: {filepath}")
            return True

        except Exception as e:
            self.main_window.progress_bar.setVisible(False)
            QMessageBox.critical(
                self.main_window, "Load Error",
                f"Error loading project: {str(e)}"
            )
            return False
        
    def _finalize_load(self):
        """Common post-load setup for both v1 and v2 formats."""
        mw = self.main_window

        # Rebuild UI
        mw.update_sample_table()

        # Select first sample
        if mw.current_sample and mw.current_sample in mw.data_by_sample:
            mw.data = mw.data_by_sample[mw.current_sample].copy()
            mw.time_array = mw.time_array_by_sample[mw.current_sample].copy()
            if mw.current_sample in mw.sample_detected_peaks:
                mw.detected_peaks = mw.sample_detected_peaks[mw.current_sample].copy()

        # Restore periodic table
        if mw.selected_isotopes:
            all_masses = set()
            for isotopes in mw.selected_isotopes.values():
                all_masses.update(isotopes)
            mw.all_masses = sorted(all_masses)

            if not mw.periodic_table_widget:
                from widget.periodic_table_widget import PeriodicTableWidget
                mw.periodic_table_widget = PeriodicTableWidget()
                mw.periodic_table_widget.selection_confirmed.connect(
                    mw.handle_isotopes_selected
                )
            mw.periodic_table_widget.update_available_masses(mw.all_masses)
            mw._update_periodic_table_selections()

        # Update parameters table
        mw.update_parameters_table()

        # Restore sigma
        if hasattr(mw, '_global_sigma') and hasattr(mw, 'sigma_spinbox'):
            mw.sigma_spinbox.setValue(mw._global_sigma)

        # Select current sample in table
        if mw.current_sample:
            for row in range(mw.sample_table.rowCount()):
                item = mw.sample_table.item(row, 0)
                if item and item.text() == mw.current_sample:
                    mw.sample_table.selectRow(row)
                    mw.on_sample_selected(item)
                    break

        # ---- FIX: Actually restore canvas workflow ----
        canvas_state = getattr(mw, '_pending_canvas_workflow', None)
        if canvas_state:
            try:
                self._deserialize_canvas_state(canvas_state)
            except Exception as e:
                print(f"Warning: Could not restore canvas workflow: {e}")
            finally:
                mw._pending_canvas_workflow = None

        mw._build_element_lookup_cache()
            
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
            'application_version': '1.0.1',
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
        
        # ---- FIX: Store canvas state for _finalize_load to restore ----
        canvas_state = project_data.get('canvas_state', None)
        if canvas_state:
            self.main_window._pending_canvas_workflow = canvas_state
    
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
            'sample_config',
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
                IsotopicRatioPlotNode, TrianglePlotNode,ClusteringPlotNode, AIAssistantNode, MolarRatioPlotNode, BoxPlotNode,
                CorrelationMatrixNode, ConcentrationComparisonNode, NetworkDiagramNode
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
            "ai_assistant": AIAssistantNode,
            "correlation_matrix": CorrelationMatrixNode,
            "concentration_comparison": ConcentrationComparisonNode,    
            "network_diagram": NetworkDiagramNode
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
        # ---- FIX: Added 'sample_config' (was missing, causing group names to be lost) ----
        config_attributes = [
            'selected_sample', 'selected_samples', 'selected_data_type',
            'selected_isotopes', 'sum_replicates', 'replicate_samples',
            'sample_config',
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