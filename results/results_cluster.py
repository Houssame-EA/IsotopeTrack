from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                              QLabel, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                             QGroupBox, QPushButton, QFrame, QScrollArea, 
                              QWidget, QMessageBox, QColorDialog,
                              QTableWidget, QTableWidgetItem, QTabWidget,
                              QProgressBar)
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QColor, QFont
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter, SVGExporter
import numpy as np
from sklearn.cluster import (KMeans, DBSCAN, AgglomerativeClustering, 
                           SpectralClustering, MeanShift, OPTICS,
                           MiniBatchKMeans, Birch)
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.metrics import (silhouette_score, calinski_harabasz_score, 
                           davies_bouldin_score, adjusted_rand_score,
                           adjusted_mutual_info_score, v_measure_score,
                           fowlkes_mallows_score, homogeneity_score,
                           completeness_score)
import warnings
warnings.filterwarnings('ignore')
import gc
from results.utils_sort import (
    extract_mass_and_element,
    sort_elements_by_mass,
    format_element_label,
)


class SafePyQtGraphWidget(QWidget):
    """
    Safe PyQtGraph plotting widget with error handling and delayed rendering.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the safe plotting widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        self.status_label = QLabel("Initializing plot...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #F5F5F5;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 20px;
                font-size: 12px;
                color: #666666;
            }
        """)
        layout.addWidget(self.status_label)
        
        self.plot_widget = None
        self.plot_data = None
        self.plot_type = None

        self.plot_timer = QTimer()
        self.plot_timer.setSingleShot(True)
        self.plot_timer.timeout.connect(self._safe_plot)
        
    def set_plot_data(self, data, plot_type):
        """
        Set data to plot safely with delayed rendering.
        
        Args:
            data (dict): Plot data dictionary
            plot_type (str): Type of plot ('evaluation', 'clustering', 'characterization')
        
        Returns:
            None
        """
        self.plot_data = data
        self.plot_type = plot_type
        self.status_label.setText("Preparing plot...")
        self.plot_timer.start(100)
    
    def _safe_plot(self):
        """
        Safely create plot with error handling.
        
        Returns:
            None
        """
        try:
            if self.plot_widget:
                self.layout().removeWidget(self.plot_widget)
                self.plot_widget.deleteLater()
                self.plot_widget = None
            
            gc.collect()
            self._create_plot()
                
        except Exception as e:
            print(f"Plot creation failed: {str(e)}")
            self.status_label.setText(f"Plot failed: {str(e)}")
            self.status_label.show()
    
    def _create_plot(self):
        """
        Create the actual plot based on plot type.
        
        Returns:
            None
        """
        if not self.plot_data or not self.plot_type:
            self.status_label.setText("No data to plot")
            return
        
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_widget.setBackground('w')
        
        if self.plot_type == 'evaluation':
            self._create_evaluation_plot()
        elif self.plot_type == 'clustering':
            self._create_clustering_plot()
        elif self.plot_type == 'characterization':
            self._create_characterization_plot()
        
        self.layout().addWidget(self.plot_widget)
        self.status_label.hide()
    
    def _create_evaluation_plot(self):
        """
        Create evaluation plot with PyQtGraph.
        
        Returns:
            None
        """
        data = self.plot_data
        evaluation_results = data.get('evaluation_results', {})
        selected_algo = data.get('selected_algo', 'All Algorithms')
        metrics_checkboxes = data.get('metrics_checkboxes', {})
        optimal_k = data.get('optimal_k')
        
        if selected_algo == 'All Algorithms':
            algorithms_to_plot = list(evaluation_results.keys())
        else:
            algorithms_to_plot = [selected_algo] if selected_algo in evaluation_results else []
        
        if not algorithms_to_plot:
            plot_item = self.plot_widget.addPlot()
            text_item = pg.TextItem("No algorithm data to plot", anchor=(0.5, 0.5), color='gray')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)
            return
        
        active_metrics = []
        if metrics_checkboxes.get('Silhouette', False):
            active_metrics.append(('Silhouette Score', 'silhouette_scores'))
        if metrics_checkboxes.get('Calinski-Harabasz', False):
            active_metrics.append(('Calinski-Harabasz Index', 'calinski_harabasz_scores'))
        if metrics_checkboxes.get('Davies-Bouldin', False):
            active_metrics.append(('Davies-Bouldin Index', 'davies_bouldin_scores'))
        if metrics_checkboxes.get('Adjusted Rand', False):
            active_metrics.append(('Adjusted Rand Index', 'adjusted_rand_scores'))
        if metrics_checkboxes.get('V-Measure', False):
            active_metrics.append(('V-Measure Score', 'v_measure_scores'))
        if metrics_checkboxes.get('Fowlkes-Mallows', False):
            active_metrics.append(('Fowlkes-Mallows Index', 'fowlkes_mallows_scores'))
        
        n_metrics = len(active_metrics)
        if n_metrics == 0:
            plot_item = self.plot_widget.addPlot()
            text_item = pg.TextItem("No metrics selected", anchor=(0.5, 0.5), color='gray')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)
            return
        
        all_k_values = []
        colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
        
        for i, (metric_name, metric_key) in enumerate(active_metrics):
            plot_item = self.plot_widget.addPlot(row=i, col=0)
            
            color_idx = 0
            for algo_name in algorithms_to_plot:
                if algo_name in evaluation_results:
                    results = evaluation_results[algo_name]
                    k_values = results.get('k_values', [])
                    scores = results.get(metric_key, [])
                    
                    if k_values and scores and len(k_values) == len(scores):
                        color = colors[color_idx % len(colors)]
                        plot_item.plot(k_values, scores, pen=pg.mkPen(color, width=2), 
                                     symbol='o', symbolBrush=color, symbolSize=6, name=algo_name)
                        all_k_values.extend(k_values)
                        color_idx += 1
            
            if optimal_k and all_k_values and optimal_k in range(min(all_k_values), max(all_k_values) + 1):
                y_range = plot_item.getViewBox().state['viewRange'][1]
                optimal_line = pg.InfiniteLine(pos=optimal_k, angle=90, 
                                             pen=pg.mkPen('red', style=pg.QtCore.Qt.DashLine, width=2))
                plot_item.addItem(optimal_line)
            
            plot_item.setLabel('bottom', 'Number of Clusters (K)')
            plot_item.setLabel('left', metric_name)
            plot_item.setTitle(f'{metric_name} vs K')
            plot_item.addLegend()
            plot_item.showGrid(x=True, y=True, alpha=0.3)
    
    def _create_clustering_plot(self):
        """
        Create clustering plot with PyQtGraph.
        
        Returns:
            None
        """
        data = self.plot_data
        clustering_results = data.get('clustering_results', {})
        data_matrix = data.get('data_matrix')
        cluster_characterization = data.get('cluster_characterization', {})
        
        if not clustering_results or data_matrix is None:
            plot_item = self.plot_widget.addPlot()
            text_item = pg.TextItem("No clustering data to plot", anchor=(0.5, 0.5), color='gray')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)
            return
        
        n_algorithms = len(clustering_results)
        if n_algorithms == 0:
            return
        
        cols = min(3, n_algorithms)
        rows = (n_algorithms + cols - 1) // cols
        
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                 '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        
        for i, (algo_name, result) in enumerate(clustering_results.items()):
            row = i // cols
            col = i % cols
            plot_item = self.plot_widget.addPlot(row=row, col=col)
            
            labels = result.get('labels')
            if labels is None:
                continue
            
            if data_matrix.shape[1] >= 2:
                x, y = data_matrix[:, 0], data_matrix[:, 1]
            else:
                x = data_matrix[:, 0] if data_matrix.ndim > 1 else data_matrix
                y = np.zeros_like(x)
            
            unique_labels = np.unique(labels)
            
            for j, label in enumerate(unique_labels):
                mask = labels == label
                color = colors[j % len(colors)]
                
                if label == -1:
                    plot_item.plot(x[mask], y[mask], pen=None, symbol='x', 
                                 symbolBrush='black', symbolSize=8, name='Noise')
                else:
                    cluster_type = "Unknown"
                    if (algo_name in cluster_characterization and 
                        label in cluster_characterization[algo_name]):
                        cluster_type = cluster_characterization[algo_name][label].get('cluster_type', 'Unknown')
                    
                    plot_item.plot(x[mask], y[mask], pen=None, symbol='o', 
                                 symbolBrush=color, symbolSize=8, 
                                 name=f'C{label}: {cluster_type}')
            
            n_clusters = result.get('n_clusters', 0)
            n_noise = result.get('n_noise', 0)
            
            title = f'{algo_name} (K={n_clusters}'
            if n_noise > 0:
                title += f', {n_noise} noise'
            title += ')'
            
            plot_item.setTitle(title)
            plot_item.setLabel('bottom', 'Component 1')
            plot_item.setLabel('left', 'Component 2')
            if n_clusters <= 6:
                plot_item.addLegend()
            plot_item.showGrid(x=True, y=True, alpha=0.3)
    
    def _create_characterization_plot(self):
        """
        Create characterization plot with PyQtGraph.
        
        Returns:
            None
        """
        data = self.plot_data
        algo_name = data.get('algo_name')
        element = data.get('element')
        characterization = data.get('characterization', {})
        
        if not algo_name or not element or not characterization:
            plot_item = self.plot_widget.addPlot()
            text_item = pg.TextItem("No characterization data to plot", anchor=(0.5, 0.5), color='gray')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)
            return
        
        plot_item = self.plot_widget.addPlot()
        
        clusters = []
        means = []
        frequencies = []
        types = []
        
        for cluster_id, cluster_data in characterization.items():
            element_stats = cluster_data.get('element_stats', {}).get(element, {})
            clusters.append(f"C{cluster_id}")
            means.append(element_stats.get('mean', 0))
            frequencies.append(element_stats.get('frequency', 0) * 100)
            types.append(cluster_data.get('cluster_type', 'Unknown'))
        
        if not clusters:
            text_item = pg.TextItem("No cluster data available", anchor=(0.5, 0.5), color='gray')
            plot_item.addItem(text_item)
            text_item.setPos(0.5, 0.5)
            return
        
        x_pos = np.arange(len(clusters))
        
        bar_width = 0.35
        bg1 = pg.BarGraphItem(x=x_pos - bar_width/2, height=means, width=bar_width, 
                             brush='blue', pen='white', name=f'{element} Mean')
        plot_item.addItem(bg1)
        
        max_mean = max(means) if means else 1
        scaled_frequencies = [f * max_mean / 100 for f in frequencies]
        bg2 = pg.BarGraphItem(x=x_pos + bar_width/2, height=scaled_frequencies, width=bar_width, 
                             brush='orange', pen='white', name='Frequency %')
        plot_item.addItem(bg2)
        
        plot_item.setLabel('bottom', 'Clusters')
        plot_item.setLabel('left', f'{element} Mean Value')
        plot_item.setTitle(f'{element} Distribution Across Clusters ({algo_name})')
        
        x_labels = [f"{cluster}\n{type_}" for cluster, type_ in zip(clusters, types)]
        x_axis = plot_item.getAxis('bottom')
        x_axis.setTicks([list(zip(x_pos, x_labels))])
        
        plot_item.addLegend()
        plot_item.showGrid(x=False, y=True, alpha=0.3)
        
    def download_figure(self, filename):
        """
        Download the current figure.
        
        Args:
            filename (str): Path to save the figure
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.plot_widget:
                exporter = ImageExporter(self.plot_widget.scene())
                exporter.parameters()['width'] = 1920
                exporter.export(filename)
                return True
        except Exception as e:
            print(f"Export failed: {str(e)}")
            return False


class ClusteringDisplayDialog(QDialog):
    """
    Advanced clustering analysis dialog with PyQtGraph and all data types.
    """
    
    def __init__(self, clustering_node, parent_window=None):
        """
        Initialize the clustering display dialog.
        
        Args:
            clustering_node: Clustering node instance
            parent_window: Parent window widget
        """
        super().__init__(parent_window)
        self.clustering_node = clustering_node
        self.parent_window = parent_window
        
        self.setWindowTitle("Clustering Analysis - All Data Types & Complete Metrics")
        self.setMinimumSize(1600, 1000)
        
        self.evaluation_results = {}
        self.final_clustering_results = {}
        self.cluster_characterization = {}
        self.optimal_k_auto = None
        self.optimal_algorithm = None
        
        self.setup_ui()
        self.connect_signals()
        
        self.clustering_node.configuration_changed.connect(self.update_display)
        
    def is_multiple_sample_data(self):
        """
        Check if dealing with multiple sample data.
        
        Returns:
            bool: True if multiple sample data, False otherwise
        """
        return (hasattr(self.clustering_node, 'input_data') and 
                self.clustering_node.input_data and 
                self.clustering_node.input_data.get('type') == 'multiple_sample_data')

    def get_font_families(self):
        """
        Get list of available font families.
        
        Returns:
            list: List of font family names
        """
        return [
            "Times New Roman", "Arial", "Helvetica", "Calibri", "Verdana",
            "Tahoma", "Georgia", "Trebuchet MS", "Comic Sans MS", "Impact",
            "Lucida Console", "Courier New", "Palatino", "Garamond", "Book Antiqua"
        ]
        
    def setup_ui(self):
        """
        Set up the user interface.
        
        Returns:
            None
        """
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        
        config_panel = self.create_config_panel()
        main_layout.addWidget(config_panel)
        
        results_panel = self.create_results_panel()
        main_layout.addWidget(results_panel, stretch=1)
        
    def create_config_panel(self):
        """
        Create comprehensive configuration panel.
        
        Returns:
            QFrame: Configuration panel widget
        """
        frame = QFrame()
        frame.setFixedWidth(380)
        frame.setStyleSheet("""
            QFrame {
                background-color: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
        """)
        
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(380)
        
        content_widget = QWidget()
        content_widget.setFixedWidth(360)
        
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        title = QLabel("Clustering Analysis - All Data Types")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #333333;
                padding: 8px;
                background-color: #F5F5F5;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                margin-bottom: 5px;
            }
        """)
        layout.addWidget(title)
        
        layout.addWidget(self.create_data_type_group())
        layout.addWidget(self.create_font_group())
        layout.addWidget(self.create_preprocessing_group())
        layout.addWidget(self.create_algorithm_group())
        layout.addWidget(self.create_evaluation_group())
        layout.addWidget(self.create_actions_group())
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(15)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready for clustering analysis")
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 6px;
                background-color: #F0F0F0;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                color: #555555;
                font-size: 11px;
            }
        """)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        scroll_area.setWidget(content_widget)
        frame_layout.addWidget(scroll_area)
        
        return frame
    
    def create_data_type_group(self):
        """
        Create data type selection group.
        
        Returns:
            QGroupBox: Data type selection group widget
        """
        group = QGroupBox("Data Type")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #2196F3;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #F8F9FF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                background-color: #F8F9FF;
            }
        """)
        layout = QFormLayout(group)
        
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems([
            'Counts (Raw)',
            'Element Mass (fg)', 
            'Particle Mass (fg)',
            'Element Moles (fmol)',
            'Particle Moles (fmol)',
            'Element Diameter (nm)',
            'Particle Diameter (nm)',
            'Element Mass %',
            'Particle Mass %', 
            'Element Mole %',
            'Particle Mole %'
        ])
        self.data_type_combo.setCurrentText(self.clustering_node.config.get('data_type_display', 'Counts (Raw)'))
        layout.addRow("Data Type:", self.data_type_combo)
        
        self.data_info_label = QLabel()
        self.data_info_label.setStyleSheet("""
            QLabel {
                color: #059669;
                font-size: 10px;
                padding: 6px;
                background-color: rgba(236, 253, 245, 150);
                border-radius: 4px;
                border: 1px solid #10B981;
            }
        """)
        self.data_info_label.setWordWrap(True)
        self.update_data_info_label()
        layout.addRow(self.data_info_label)
        
        return group
    
    def create_font_group(self):
        """
        Create font settings group.
        
        Returns:
            QGroupBox: Font settings group widget
        """
        group = QGroupBox("Font Settings")
        group.setStyleSheet(self.get_group_style())
        layout = QFormLayout(group)
        
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(self.get_font_families())
        self.font_family_combo.setCurrentText(self.clustering_node.config.get('font_family', 'Times New Roman'))
        layout.addRow("Font Family:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(self.clustering_node.config.get('font_size', 12))
        layout.addRow("Font Size:", self.font_size_spin)
        
        self.font_color_button = QPushButton()
        self.font_color = QColor(self.clustering_node.config.get('font_color', '#000000'))
        self.font_color_button.setStyleSheet(f"background-color: {self.font_color.name()}; min-height: 25px;")
        self.font_color_button.clicked.connect(lambda: self.choose_color('font'))
        layout.addRow("Font Color:", self.font_color_button)
        
        return group
    
    def choose_color(self, color_type):
        """
        Open color dialog for font color.
        
        Args:
            color_type (str): Type of color to choose
        
        Returns:
            None
        """
        if color_type == 'font':
            color = QColorDialog.getColor(self.font_color, self, "Select Font Color")
            if color.isValid():
                self.font_color = color
                self.font_color_button.setStyleSheet(f"background-color: {color.name()}; min-height: 25px;")
    
    def create_preprocessing_group(self):
        """
        Create preprocessing options group.
        
        Returns:
            QGroupBox: Preprocessing options group widget
        """
        group = QGroupBox("Preprocessing")
        group.setStyleSheet(self.get_group_style())
        layout = QFormLayout(group)
        
        self.scaling_combo = QComboBox()
        self.scaling_combo.addItems(['StandardScaler', 'MinMaxScaler', 'None'])
        self.scaling_combo.setCurrentText(self.clustering_node.config.get('scaling', 'StandardScaler'))
        layout.addRow("Scaling:", self.scaling_combo)
        
        self.dim_reduction_combo = QComboBox()
        self.dim_reduction_combo.addItems(['None', 'PCA', 't-SNE'])
        self.dim_reduction_combo.setCurrentText(self.clustering_node.config.get('dim_reduction', 'None'))
        layout.addRow("Reduction:", self.dim_reduction_combo)
        
        self.n_components_spin = QSpinBox()
        self.n_components_spin.setRange(2, 5)
        self.n_components_spin.setValue(self.clustering_node.config.get('n_components', 2))
        layout.addRow("Components:", self.n_components_spin)
        
        self.filter_zeros_checkbox = QCheckBox("Filter zero values")
        self.filter_zeros_checkbox.setChecked(self.clustering_node.config.get('filter_zeros', True))
        layout.addRow(self.filter_zeros_checkbox)
        
        return group
    
    def create_algorithm_group(self):
        """
        Create algorithm selection group.
        
        Returns:
            QGroupBox: Algorithm selection group widget
        """
        group = QGroupBox("Algorithms")
        group.setStyleSheet(self.get_group_style())
        layout = QVBoxLayout(group)
        
        self.algorithm_checkboxes = {}
        algorithms = [
            'K-Means', 'Hierarchical', 'DBSCAN', 'Spectral', 
            'MiniBatch K-Means', 'Birch', 'Mean Shift', 'OPTICS'
        ]
        
        for algo in algorithms:
            checkbox = QCheckBox(algo)
            checkbox.setChecked(algo in ['K-Means', 'Hierarchical', 'DBSCAN'])
            self.algorithm_checkboxes[algo] = checkbox
            layout.addWidget(checkbox)
        
        params_layout = QFormLayout()
        
        dbscan_widget = QWidget()
        dbscan_layout = QHBoxLayout(dbscan_widget)
        dbscan_layout.setContentsMargins(0, 0, 0, 0)
        
        self.dbscan_eps_spin = QDoubleSpinBox()
        self.dbscan_eps_spin.setRange(0.1, 5.0)
        self.dbscan_eps_spin.setSingleStep(0.1)
        self.dbscan_eps_spin.setValue(0.5)
        self.dbscan_eps_spin.setMaximumWidth(60)
        
        self.dbscan_min_samples_spin = QSpinBox()
        self.dbscan_min_samples_spin.setRange(2, 10)
        self.dbscan_min_samples_spin.setValue(5)
        self.dbscan_min_samples_spin.setMaximumWidth(50)
        
        dbscan_layout.addWidget(QLabel("eps:"))
        dbscan_layout.addWidget(self.dbscan_eps_spin)
        dbscan_layout.addWidget(QLabel("samples:"))
        dbscan_layout.addWidget(self.dbscan_min_samples_spin)
        dbscan_layout.addStretch()
        
        params_layout.addRow("DBSCAN:", dbscan_widget)
        
        self.hier_linkage_combo = QComboBox()
        self.hier_linkage_combo.addItems(['ward', 'complete', 'average'])
        params_layout.addRow("Linkage:", self.hier_linkage_combo)
        
        layout.addLayout(params_layout)
        
        return group
    
    def create_evaluation_group(self):
        """
        Create evaluation settings group with all metrics.
        
        Returns:
            QGroupBox: Evaluation settings group widget
        """
        group = QGroupBox("Evaluation & Metrics")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #4CAF50;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #F8FFF8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                background-color: #F8FFF8;
            }
        """)
        layout = QFormLayout(group)
        
        range_widget = QWidget()
        range_layout = QHBoxLayout(range_widget)
        range_layout.setContentsMargins(0, 0, 0, 0)
        
        self.min_clusters_spin = QSpinBox()
        self.min_clusters_spin.setRange(2, 10)
        self.min_clusters_spin.setValue(2)
        self.min_clusters_spin.setMaximumWidth(50)
        
        self.max_clusters_spin = QSpinBox()
        self.max_clusters_spin.setRange(5, 50)
        self.max_clusters_spin.setValue(20)
        self.max_clusters_spin.setMaximumWidth(50)
        
        range_layout.addWidget(QLabel("From:"))
        range_layout.addWidget(self.min_clusters_spin)
        range_layout.addWidget(QLabel("To:"))
        range_layout.addWidget(self.max_clusters_spin)
        range_layout.addStretch()
        
        layout.addRow("K Range:", range_widget)
        
        self.auto_select_checkbox = QCheckBox("Auto-select optimal K")
        self.auto_select_checkbox.setChecked(True)
        layout.addRow(self.auto_select_checkbox)
        
        metrics_widget = QWidget()
        metrics_layout = QVBoxLayout(metrics_widget)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        
        self.metrics_checkboxes = {}
        metrics = [
            'Silhouette', 'Calinski-Harabasz', 'Davies-Bouldin',
            'Adjusted Rand', 'V-Measure', 'Fowlkes-Mallows'
        ]
        
        for metric in metrics:
            checkbox = QCheckBox(metric)
            checkbox.setChecked(metric in ['Silhouette', 'Calinski-Harabasz', 'Davies-Bouldin'])
            self.metrics_checkboxes[metric] = checkbox
            metrics_layout.addWidget(checkbox)
        
        layout.addRow("Metrics:", metrics_widget)
        
        return group
    
    def create_actions_group(self):
        """
        Create action buttons group.
        
        Returns:
            QGroupBox: Action buttons group widget
        """
        group = QGroupBox("Analysis")
        group.setStyleSheet(self.get_group_style())
        layout = QVBoxLayout(group)
        
        self.evaluate_button = QPushButton("Step 1: Evaluate Clusters")
        self.evaluate_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.evaluate_button.clicked.connect(self.run_cluster_evaluation)
        layout.addWidget(self.evaluate_button)
        
        self.optimal_k_label = QLabel("Optimal K: Not determined")
        self.optimal_k_label.setStyleSheet("""
            QLabel {
                padding: 4px;
                background-color: #FFFBF0;
                border: 1px solid #FFB74D;
                border-radius: 3px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.optimal_k_label)
        
        self.cluster_button = QPushButton("Step 2: Generate Clusters")
        self.cluster_button.setStyleSheet("""
            QPushButton {
                background-color: #9E9E9E;
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:enabled {
                background-color: #4CAF50;
            }
            QPushButton:enabled:hover {
                background-color: #45A049;
            }
        """)
        self.cluster_button.clicked.connect(self.run_final_clustering)
        self.cluster_button.setEnabled(False)
        layout.addWidget(self.cluster_button)
        
        self.export_button = QPushButton("Export Results")
        self.export_button.setStyleSheet("""
            QPushButton {
                background-color: #9E9E9E;
                color: white;
                padding: 6px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:enabled {
                background-color: #FF9800;
            }
            QPushButton:enabled:hover {
                background-color: #F57C00;
            }
        """)
        self.export_button.clicked.connect(self.export_results)
        self.export_button.setEnabled(False)
        layout.addWidget(self.export_button)
        
        return group
    
    def get_group_style(self):
        """
        Get standard group styling.
        
        Returns:
            str: CSS stylesheet string for group styling
        """
        return """
            QGroupBox {
                font-weight: bold;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                background-color: #FFFFFF;
            }
        """
    
    def create_results_panel(self):
        """
        Create results panel with tabs.
        
        Returns:
            QTabWidget: Tab widget containing results panels
        """
        tab_widget = QTabWidget()
        
        self.evaluation_tab = self.create_evaluation_tab()
        tab_widget.addTab(self.evaluation_tab, "Evaluation Results")
        
        self.clustering_tab = self.create_clustering_tab()
        tab_widget.addTab(self.clustering_tab, "Cluster Analysis")
        
        self.characterization_tab = self.create_characterization_tab()
        tab_widget.addTab(self.characterization_tab, "Cluster Characterization")
        
        return tab_widget
    
    def create_evaluation_tab(self):
        """
        Create evaluation results tab.
        
        Returns:
            QWidget: Evaluation tab widget
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        controls_layout = QHBoxLayout()
        
        self.algorithm_view_combo = QComboBox()
        self.algorithm_view_combo.addItems(['All Algorithms'])
        self.algorithm_view_combo.currentTextChanged.connect(self.update_evaluation_display)
        controls_layout.addWidget(QLabel("View:"))
        controls_layout.addWidget(self.algorithm_view_combo)
        
        controls_layout.addStretch()
        
        save_eval_btn = QPushButton("Save Evaluation")
        save_eval_btn.clicked.connect(self.save_evaluation)
        controls_layout.addWidget(save_eval_btn)
        
        layout.addLayout(controls_layout)
        
        self.evaluation_plot = SafePyQtGraphWidget()
        layout.addWidget(self.evaluation_plot)
        
        self.evaluation_summary = QLabel("Run evaluation to see results")
        self.evaluation_summary.setStyleSheet("""
            QLabel {
                padding: 10px;
                background-color: #F5F5F5;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        self.evaluation_summary.setWordWrap(True)
        layout.addWidget(self.evaluation_summary)
        
        return tab
    
    def create_clustering_tab(self):
        """
        Create clustering results tab.
        
        Returns:
            QWidget: Clustering tab widget
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        controls_layout = QHBoxLayout()
        
        controls_layout.addWidget(QLabel("Selected K:"))
        
        self.selected_k_combo = QComboBox()
        self.selected_k_combo.currentTextChanged.connect(self.update_clustering_display)
        controls_layout.addWidget(self.selected_k_combo)
        
        controls_layout.addStretch()
        
        save_cluster_btn = QPushButton("Save Clustering")
        save_cluster_btn.clicked.connect(self.save_clustering)
        controls_layout.addWidget(save_cluster_btn)
        
        layout.addLayout(controls_layout)
        
        self.clustering_plot = SafePyQtGraphWidget()
        layout.addWidget(self.clustering_plot)
        
        return tab
    
    def create_characterization_tab(self):
        """
        Create cluster characterization tab.
        
        Returns:
            QWidget: Characterization tab widget
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        controls_layout = QHBoxLayout()
        
        self.characterization_algo_combo = QComboBox()
        self.characterization_algo_combo.currentTextChanged.connect(self.update_characterization_display)
        controls_layout.addWidget(QLabel("Algorithm:"))
        controls_layout.addWidget(self.characterization_algo_combo)
        
        self.characterization_element_combo = QComboBox()
        self.characterization_element_combo.currentTextChanged.connect(self.update_characterization_display)
        controls_layout.addWidget(QLabel("Element:"))
        controls_layout.addWidget(self.characterization_element_combo)
        
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        self.characterization_table = QTableWidget()
        self.characterization_table.setAlternatingRowColors(True)
        layout.addWidget(self.characterization_table)
        
        self.characterization_plot = SafePyQtGraphWidget()
        layout.addWidget(self.characterization_plot)
        
        return tab
    
    def connect_signals(self):
        """
        Connect all signals.
        
        Returns:
            None
        """
        self.data_type_combo.currentTextChanged.connect(self.on_data_type_changed)
        self.font_family_combo.currentTextChanged.connect(self.on_config_changed)
        self.font_size_spin.valueChanged.connect(self.on_config_changed)
        self.scaling_combo.currentTextChanged.connect(self.on_config_changed)
        self.dim_reduction_combo.currentTextChanged.connect(self.on_config_changed)
        self.n_components_spin.valueChanged.connect(self.on_config_changed)
        self.filter_zeros_checkbox.stateChanged.connect(self.on_config_changed)
        self.dbscan_eps_spin.valueChanged.connect(self.on_config_changed)
        self.dbscan_min_samples_spin.valueChanged.connect(self.on_config_changed)
        self.min_clusters_spin.valueChanged.connect(self.on_config_changed)
        self.max_clusters_spin.valueChanged.connect(self.on_config_changed)
    
    def on_data_type_changed(self):
        """
        Handle data type selection change.
        
        Returns:
            None
        """
        self.update_data_info_label()
        self.on_config_changed()
    
    def update_data_info_label(self):
        """
        Update the data availability info label.
        
        Returns:
            None
        """
        if not self.clustering_node.input_data:
            info_text = "⚠️ No data source connected\nConnect a Sample Selector node"
        elif self.is_multiple_sample_data():
            sample_count = len(self.get_available_sample_names())
            data_type = self.data_type_combo.currentText()
            info_text = f"ℹ️ Source: {sample_count} samples\nData Type: {data_type}"
        else:
            data_type = self.data_type_combo.currentText()
            info_text = f"ℹ️ Single sample analysis\nData Type: {data_type}"
        
        self.data_info_label.setText(info_text)
    
    def get_available_sample_names(self):
        """
        Get available sample names from input data.
        
        Returns:
            list: List of sample names
        """
        if self.is_multiple_sample_data():
            return self.clustering_node.input_data.get('sample_names', [])
        return []
    
    def on_config_changed(self):
        """
        Handle configuration changes.
        
        Returns:
            None
        """
        self.clustering_node.config.update({
            'data_type_display': self.data_type_combo.currentText(),
            'font_family': self.font_family_combo.currentText(),
            'font_size': self.font_size_spin.value(),
            'font_color': self.font_color.name(),
            'scaling': self.scaling_combo.currentText(),
            'dim_reduction': self.dim_reduction_combo.currentText(),
            'n_components': self.n_components_spin.value(),
            'filter_zeros': self.filter_zeros_checkbox.isChecked(),
            'dbscan_eps': self.dbscan_eps_spin.value(),
            'dbscan_min_samples': self.dbscan_min_samples_spin.value(),
            'min_clusters': self.min_clusters_spin.value(),
            'max_clusters': self.max_clusters_spin.value(),
        })
    
    def get_selected_elements(self):
        """
        Get selected elements from input data, sorted by mass.
        
        Returns:
            list: Sorted list of element labels
        """
        if not self.clustering_node.input_data:
            return []
        
        data_type = self.clustering_node.input_data.get('type')
        
        if data_type in ['sample_data', 'multiple_sample_data']:
            selected_isotopes = self.clustering_node.input_data.get('selected_isotopes', [])
            if selected_isotopes:
                element_labels = [isotope['label'] for isotope in selected_isotopes]
                return sort_elements_by_mass(element_labels)
        
        return []
    
    def run_cluster_evaluation(self):
        """
        Run comprehensive cluster evaluation with all data types.
        
        Returns:
            None
        """
        try:
            self.status_label.setText("Evaluating cluster numbers...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.evaluate_button.setEnabled(False)
            
            selected_elements = self.get_selected_elements()
            if not selected_elements:
                QMessageBox.warning(self, "Warning", "No elements available from input data.")
                return
            
            self.progress_bar.setValue(20)
            data_matrix = self.prepare_clustering_data(selected_elements)
            
            if data_matrix is None or len(data_matrix) < 2:
                QMessageBox.warning(self, "Warning", "Insufficient data for clustering analysis.")
                return
            
            self.progress_bar.setValue(40)
            self.evaluate_cluster_numbers(data_matrix)
            
            self.progress_bar.setValue(70)
            self.determine_optimal_k()
            
            self.progress_bar.setValue(90)
            self.update_evaluation_display()
            self.update_optimal_k_display()
            
            self.progress_bar.setValue(100)
            self.status_label.setText("Evaluation completed. Optimal K determined.")
            self.cluster_button.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Evaluation failed:\n{str(e)}")
            self.status_label.setText("Evaluation failed")
            print(f"Evaluation error: {str(e)}")
            
        finally:
            self.progress_bar.setVisible(False)
            self.evaluate_button.setEnabled(True)
    
    def prepare_clustering_data(self, selected_elements):
        """
        Prepare data matrix for clustering with all data types.
        
        Args:
            selected_elements (list): List of selected element labels
        
        Returns:
            np.ndarray or None: Prepared data matrix
        """
        if not self.clustering_node.input_data:
            return None
        
        data_type_display = self.data_type_combo.currentText()
        input_type = self.clustering_node.input_data.get('type')
        
        data_key_mapping = {
            'Counts (Raw)': 'elements',
            'Element Mass (fg)': 'element_mass_fg',
            'Particle Mass (fg)': 'particle_mass_fg',
            'Element Moles (fmol)': 'element_moles_fmol',
            'Particle Moles (fmol)': 'particle_moles_fmol',
            'Element Diameter (nm)': 'element_diameter_nm',
            'Particle Diameter (nm)': 'particle_diameter_nm',
            'Element Mass %': 'element_mass_fg',
            'Particle Mass %': 'particle_mass_fg', 
            'Element Mole %': 'element_moles_fmol',
            'Particle Mole %': 'particle_moles_fmol'
        }
        
        data_key = data_key_mapping.get(data_type_display, 'elements')
        
        if input_type == 'sample_data':
            particles = self.clustering_node.input_data.get('particle_data', [])
        elif input_type == 'multiple_sample_data':
            particles = self.clustering_node.input_data.get('particle_data', [])
        else:
            return None
        
        if not particles:
            return None
        
        data_matrix = []
        
        for particle in particles:
            particle_data_dict = particle.get(data_key, {})
            row = []
            
            if data_type_display in ['Element Mass %', 'Particle Mass %', 'Element Mole %', 'Particle Mole %']:
                if 'Mass %' in data_type_display:
                    if data_type_display == 'Element Mass %':
                        total = sum(particle_data_dict.get(elem, 0) for elem in selected_elements)
                    else:
                        total = particle.get('particle_mass_fg', 0)
                else:
                    if data_type_display == 'Element Mole %':
                        total = sum(particle_data_dict.get(elem, 0) for elem in selected_elements)
                    else:
                        total = particle.get('particle_moles_fmol', 0)
                
                for element in selected_elements:
                    value = particle_data_dict.get(element, 0)
                    if total > 0:
                        percentage = (value / total) * 100
                        row.append(percentage)
                    else:
                        row.append(0)
            else:
                for element in selected_elements:
                    value = particle_data_dict.get(element, 0)
                    row.append(value)
            
            data_matrix.append(row)
        
        data_matrix = np.array(data_matrix)
        
        if self.filter_zeros_checkbox.isChecked():
            non_zero_mask = np.any(data_matrix > 0, axis=1)
            data_matrix = data_matrix[non_zero_mask]
        
        scaling_method = self.scaling_combo.currentText()
        if scaling_method == 'StandardScaler':
            scaler = StandardScaler()
            data_matrix = scaler.fit_transform(data_matrix)
        elif scaling_method == 'MinMaxScaler':
            scaler = MinMaxScaler()
            data_matrix = scaler.fit_transform(data_matrix)
        
        dim_reduction = self.dim_reduction_combo.currentText()
        if dim_reduction == 'PCA':
            n_components = min(self.n_components_spin.value(), data_matrix.shape[1])
            pca = PCA(n_components=n_components)
            data_matrix = pca.fit_transform(data_matrix)
        elif dim_reduction == 't-SNE':
            n_components = min(self.n_components_spin.value(), 3)
            tsne = TSNE(n_components=n_components, random_state=42)
            data_matrix = tsne.fit_transform(data_matrix)
        
        return data_matrix
    
    def evaluate_cluster_numbers(self, data_matrix):
        """
        Evaluate different cluster numbers with all metrics implemented.
        
        Args:
            data_matrix (np.ndarray): Prepared data matrix
        
        Returns:
            None
        """
        self.evaluation_results = {}
        
        min_k = self.min_clusters_spin.value()
        max_k = self.max_clusters_spin.value()
        
        selected_algorithms = [name for name, checkbox in self.algorithm_checkboxes.items() 
                             if checkbox.isChecked()]
        
        for algo_name in selected_algorithms:
            self.evaluation_results[algo_name] = {
                'k_values': [],
                'silhouette_scores': [],
                'calinski_harabasz_scores': [],
                'davies_bouldin_scores': [],
                'adjusted_rand_scores': [],
                'v_measure_scores': [],
                'fowlkes_mallows_scores': []
            }
            
            reference_labels = None
            
            for k in range(min_k, max_k + 1):
                try:
                    labels = self.run_single_clustering(algo_name, k, data_matrix)
                    
                    if labels is None or len(np.unique(labels)) < 2:
                        continue
                    
                    if reference_labels is None:
                        reference_labels = labels
                    
                    if self.metrics_checkboxes['Silhouette'].isChecked():
                        sil_score = silhouette_score(data_matrix, labels)
                        self.evaluation_results[algo_name]['silhouette_scores'].append(sil_score)
                    
                    if self.metrics_checkboxes['Calinski-Harabasz'].isChecked():
                        ch_score = calinski_harabasz_score(data_matrix, labels)
                        self.evaluation_results[algo_name]['calinski_harabasz_scores'].append(ch_score)
                    
                    if self.metrics_checkboxes['Davies-Bouldin'].isChecked():
                        db_score = davies_bouldin_score(data_matrix, labels)
                        self.evaluation_results[algo_name]['davies_bouldin_scores'].append(db_score)
                    
                    if self.metrics_checkboxes['Adjusted Rand'].isChecked() and reference_labels is not None:
                        ar_score = adjusted_rand_score(reference_labels, labels)
                        self.evaluation_results[algo_name]['adjusted_rand_scores'].append(ar_score)
                    
                    if self.metrics_checkboxes['V-Measure'].isChecked() and reference_labels is not None:
                        v_score = v_measure_score(reference_labels, labels)
                        self.evaluation_results[algo_name]['v_measure_scores'].append(v_score)
                    
                    if self.metrics_checkboxes['Fowlkes-Mallows'].isChecked() and reference_labels is not None:
                        fm_score = fowlkes_mallows_score(reference_labels, labels)
                        self.evaluation_results[algo_name]['fowlkes_mallows_scores'].append(fm_score)
                    
                    self.evaluation_results[algo_name]['k_values'].append(k)
                    
                except Exception as e:
                    print(f"Error evaluating {algo_name} with k={k}: {str(e)}")
                    continue
    
    def run_single_clustering(self, algo_name, k, data_matrix):
        """
        Run single clustering algorithm.
        
        Args:
            algo_name (str): Algorithm name
            k (int): Number of clusters
            data_matrix (np.ndarray): Data matrix
        
        Returns:
            np.ndarray or None: Cluster labels
        """
        try:
            if algo_name == 'K-Means':
                clusterer = KMeans(n_clusters=k, random_state=42, n_init=10)
                return clusterer.fit_predict(data_matrix)
            elif algo_name == 'Hierarchical':
                linkage = self.hier_linkage_combo.currentText()
                clusterer = AgglomerativeClustering(n_clusters=k, linkage=linkage)
                return clusterer.fit_predict(data_matrix)
            elif algo_name == 'Spectral':
                clusterer = SpectralClustering(n_clusters=k, random_state=42)
                return clusterer.fit_predict(data_matrix)
            elif algo_name == 'MiniBatch K-Means':
                clusterer = MiniBatchKMeans(n_clusters=k, random_state=42)
                return clusterer.fit_predict(data_matrix)
            elif algo_name == 'Birch':
                clusterer = Birch(n_clusters=k)
                return clusterer.fit_predict(data_matrix)
            elif algo_name == 'DBSCAN':
                eps = self.dbscan_eps_spin.value()
                min_samples = self.dbscan_min_samples_spin.value()
                clusterer = DBSCAN(eps=eps, min_samples=min_samples)
                return clusterer.fit_predict(data_matrix)
            elif algo_name == 'Mean Shift':
                clusterer = MeanShift()
                return clusterer.fit_predict(data_matrix)
            elif algo_name == 'OPTICS':
                min_samples = self.dbscan_min_samples_spin.value()
                clusterer = OPTICS(min_samples=min_samples)
                return clusterer.fit_predict(data_matrix)
            
        except Exception as e:
            print(f"Clustering failed for {algo_name}: {str(e)}")
            return None
        
        return None
    
    def determine_optimal_k(self):
        """
        Automatically determine optimal K.
        
        Returns:
            None
        """
        if not self.evaluation_results:
            return
        
        combined_scores = {}
        
        for algo_name, results in self.evaluation_results.items():
            k_values = results['k_values']
            
            for i, k in enumerate(k_values):
                if k not in combined_scores:
                    combined_scores[k] = {'total_score': 0, 'count': 0}
                
                score = 0
                count = 0
                
                if i < len(results['silhouette_scores']):
                    score += results['silhouette_scores'][i]
                    count += 1
                
                if i < len(results['calinski_harabasz_scores']):
                    all_ch = results['calinski_harabasz_scores']
                    if max(all_ch) > min(all_ch):
                        normalized = (results['calinski_harabasz_scores'][i] - min(all_ch)) / (max(all_ch) - min(all_ch))
                        score += normalized
                        count += 1
                
                if i < len(results['davies_bouldin_scores']):
                    all_db = results['davies_bouldin_scores']
                    if max(all_db) > min(all_db):
                        normalized = 1 - (results['davies_bouldin_scores'][i] - min(all_db)) / (max(all_db) - min(all_db))
                        score += normalized
                        count += 1
                
                if count > 0:
                    combined_scores[k]['total_score'] += score / count
                    combined_scores[k]['count'] += 1
        
        if combined_scores:
            avg_scores = {k: data['total_score'] / data['count'] 
                         for k, data in combined_scores.items() if data['count'] > 0}
            
            if avg_scores:
                self.optimal_k_auto = max(avg_scores.keys(), key=lambda k: avg_scores[k])
                
                best_algo = None
                best_score = -1
                
                for algo_name, results in self.evaluation_results.items():
                    if self.optimal_k_auto in results['k_values']:
                        k_idx = results['k_values'].index(self.optimal_k_auto)
                        if k_idx < len(results['silhouette_scores']):
                            if results['silhouette_scores'][k_idx] > best_score:
                                best_score = results['silhouette_scores'][k_idx]
                                best_algo = algo_name
                
                self.optimal_algorithm = best_algo
    
    def update_optimal_k_display(self):
        """
        Update optimal K display.
        
        Returns:
            None
        """
        if self.optimal_k_auto:
            text = f"Optimal K: {self.optimal_k_auto}"
            if self.optimal_algorithm:
                text += f" (Best: {self.optimal_algorithm})"
            self.optimal_k_label.setText(text)
            
            if self.auto_select_checkbox.isChecked():
                self.selected_k_combo.clear()
                all_k_values = set()
                for results in self.evaluation_results.values():
                    all_k_values.update(results['k_values'])
                
                for k in sorted(all_k_values):
                    self.selected_k_combo.addItem(str(k))
                
                self.selected_k_combo.setCurrentText(str(self.optimal_k_auto))
    
    def update_evaluation_display(self):
        """
        Update evaluation display.
        
        Returns:
            None
        """
        if not self.evaluation_results:
            return
        
        try:
            self.algorithm_view_combo.clear()
            self.algorithm_view_combo.addItem('All Algorithms')
            for algo_name in self.evaluation_results.keys():
                self.algorithm_view_combo.addItem(algo_name)
            
            selected_algo = self.algorithm_view_combo.currentText()
            
            plot_data = {
                'evaluation_results': self.evaluation_results,
                'selected_algo': selected_algo,
                'metrics_checkboxes': {
                    'Silhouette': self.metrics_checkboxes['Silhouette'].isChecked(),
                    'Calinski-Harabasz': self.metrics_checkboxes['Calinski-Harabasz'].isChecked(),
                    'Davies-Bouldin': self.metrics_checkboxes['Davies-Bouldin'].isChecked(),
                    'Adjusted Rand': self.metrics_checkboxes['Adjusted Rand'].isChecked(),
                    'V-Measure': self.metrics_checkboxes['V-Measure'].isChecked(),
                    'Fowlkes-Mallows': self.metrics_checkboxes['Fowlkes-Mallows'].isChecked()
                },
                'optimal_k': self.optimal_k_auto
            }
            
            self.evaluation_plot.set_plot_data(plot_data, 'evaluation')
            
            self.update_evaluation_summary()
            
        except Exception as e:
            print(f"Error in update_evaluation_display: {str(e)}")
    
    def update_evaluation_summary(self):
        """
        Update evaluation summary text.
        
        Returns:
            None
        """
        if not self.evaluation_results:
            return
        
        summary = "EVALUATION SUMMARY - ALL METRICS\n"
        summary += "=" * 50 + "\n\n"
        
        for algo_name, results in self.evaluation_results.items():
            summary += f"{algo_name}:\n"
            if results['k_values']:
                summary += f"  K range: {min(results['k_values'])} - {max(results['k_values'])}\n"
            
            if results['silhouette_scores']:
                best_k_sil = results['k_values'][np.argmax(results['silhouette_scores'])]
                best_sil = max(results['silhouette_scores'])
                summary += f"  Best Silhouette: K={best_k_sil} (score: {best_sil:.3f})\n"
            
            if results['calinski_harabasz_scores']:
                best_k_ch = results['k_values'][np.argmax(results['calinski_harabasz_scores'])]
                best_ch = max(results['calinski_harabasz_scores'])
                summary += f"  Best Calinski-Harabasz: K={best_k_ch} (score: {best_ch:.1f})\n"
            
            if results['davies_bouldin_scores']:
                best_k_db = results['k_values'][np.argmin(results['davies_bouldin_scores'])]
                best_db = min(results['davies_bouldin_scores'])
                summary += f"  Best Davies-Bouldin: K={best_k_db} (score: {best_db:.3f})\n"
            
            summary += "\n"
        
        if self.optimal_k_auto:
            summary += f"RECOMMENDED: K = {self.optimal_k_auto}"
            if self.optimal_algorithm:
                summary += f" using {self.optimal_algorithm}"
            summary += "\n"
        
        self.evaluation_summary.setText(summary)
    
    def run_final_clustering(self):
        """
        Run final clustering with selected K.
        
        Returns:
            None
        """
        try:
            selected_k = int(self.selected_k_combo.currentText()) if self.selected_k_combo.currentText() else self.optimal_k_auto
            
            self.status_label.setText(f"Generating clusters with K={selected_k}...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            selected_elements = self.get_selected_elements()
            data_matrix = self.prepare_clustering_data(selected_elements)
            
            self.progress_bar.setValue(30)
            
            self.final_clustering_results = {}
            
            for algo_name, checkbox in self.algorithm_checkboxes.items():
                if not checkbox.isChecked():
                    continue
                
                labels = self.run_single_clustering(algo_name, selected_k, data_matrix)
                
                if labels is not None:
                    self.final_clustering_results[algo_name] = {
                        'labels': labels,
                        'n_clusters': len(np.unique(labels[labels >= 0])),
                        'n_noise': np.sum(labels == -1) if np.any(labels == -1) else 0
                    }
            
            self.progress_bar.setValue(70)
            
            self.characterize_clusters(selected_elements, data_matrix)
            
            self.progress_bar.setValue(90)
            self.update_clustering_display()
            self.update_characterization_combos()
            
            self.export_button.setEnabled(True)
            self.status_label.setText("Clustering completed with characterization.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Clustering failed:\n{str(e)}")
            self.status_label.setText("Clustering failed")
            
        finally:
            self.progress_bar.setVisible(False)
    
    def characterize_clusters(self, selected_elements, data_matrix):
        """
        Generate cluster characterization based on element composition.
        
        Args:
            selected_elements (list): List of selected element labels
            data_matrix (np.ndarray): Data matrix
        
        Returns:
            None
        """
        if not self.final_clustering_results:
            return
        
        self.cluster_characterization = {}
        
        particles = self.clustering_node.input_data.get('particle_data', [])
        
        if self.filter_zeros_checkbox.isChecked():
            filtered_particles = []
            for particle in particles:
                elements = particle.get('elements', {})
                has_nonzero = any(elements.get(el, 0) > 0 for el in selected_elements)
                if has_nonzero:
                    filtered_particles.append(particle)
            particles = filtered_particles
        
        for algo_name, result in self.final_clustering_results.items():
            labels = result['labels']
            
            self.cluster_characterization[algo_name] = {}
            
            for cluster_id in np.unique(labels):
                if cluster_id == -1:
                    continue
                
                cluster_mask = labels == cluster_id
                cluster_particles = [particles[i] for i in range(len(particles)) if i < len(cluster_mask) and cluster_mask[i]]
                
                if not cluster_particles:
                    continue
                
                element_stats = {}
                for element in selected_elements:
                    values = [p.get('elements', {}).get(element, 0) for p in cluster_particles]
                    values = [v for v in values if v > 0]
                    
                    if values:
                        element_stats[element] = {
                            'mean': np.mean(values),
                            'median': np.median(values),
                            'std': np.std(values),
                            'count': len(values),
                            'total_particles': len(cluster_particles),
                            'frequency': len(values) / len(cluster_particles)
                        }
                    else:
                        element_stats[element] = {
                            'mean': 0, 'median': 0, 'std': 0, 'count': 0,
                            'total_particles': len(cluster_particles), 'frequency': 0
                        }
                
                element_frequencies = {el: stats['frequency'] for el, stats in element_stats.items()}
                dominant_elements = sorted(element_frequencies.items(), key=lambda x: x[1], reverse=True)[:3]
                
                cluster_type = "Mixed"
                if dominant_elements:
                    if dominant_elements[0][1] > 0.7:
                        cluster_type = f"{format_element_label(dominant_elements[0][0], False)}-dominant"
                    elif len(dominant_elements) >= 2 and dominant_elements[1][1] > 0.3:
                        elem1 = format_element_label(dominant_elements[0][0], False)
                        elem2 = format_element_label(dominant_elements[1][0], False)
                        cluster_type = f"{elem1}-{elem2} rich"
                
                self.cluster_characterization[algo_name][cluster_id] = {
                    'element_stats': element_stats,
                    'dominant_elements': dominant_elements,
                    'cluster_type': cluster_type,
                    'particle_count': len(cluster_particles)
                }
    
    def update_characterization_combos(self):
        """
        Update characterization combo boxes.
        
        Returns:
            None
        """
        self.characterization_algo_combo.clear()
        self.characterization_element_combo.clear()
        
        if self.cluster_characterization:
            for algo_name in self.cluster_characterization.keys():
                self.characterization_algo_combo.addItem(algo_name)
            
            if self.optimal_algorithm and self.optimal_algorithm in self.cluster_characterization:
                self.characterization_algo_combo.setCurrentText(self.optimal_algorithm)
        
        selected_elements = self.get_selected_elements()
        for element in selected_elements:
            self.characterization_element_combo.addItem(element)
    
    def update_clustering_display(self):
        """
        Update clustering visualization.
        
        Returns:
            None
        """
        if not self.final_clustering_results:
            return
        
        try:
            selected_elements = self.get_selected_elements()
            data_matrix = self.prepare_clustering_data(selected_elements)
            
            if data_matrix is None:
                return
            
            plot_data = {
                'clustering_results': self.final_clustering_results,
                'data_matrix': data_matrix,
                'cluster_characterization': self.cluster_characterization
            }
            
            self.clustering_plot.set_plot_data(plot_data, 'clustering')
            
        except Exception as e:
            print(f"Clustering visualization failed: {str(e)}")
    
    def update_characterization_display(self):
        """
        Update cluster characterization display.
        
        Returns:
            None
        """
        algo_name = self.characterization_algo_combo.currentText()
        element = self.characterization_element_combo.currentText()
        
        if not algo_name or not element or algo_name not in self.cluster_characterization:
            return
        
        characterization = self.cluster_characterization[algo_name]
        
        clusters = list(characterization.keys())
        self.characterization_table.setRowCount(len(clusters))
        self.characterization_table.setColumnCount(7)
        
        headers = ['Cluster', 'Type', 'Particles', 'Mean', 'Median', 'Std Dev', 'Frequency']
        self.characterization_table.setHorizontalHeaderLabels(headers)
        
        for i, cluster_id in enumerate(clusters):
            cluster_data = characterization[cluster_id]
            element_stats = cluster_data['element_stats'].get(element, {})
            
            self.characterization_table.setItem(i, 0, QTableWidgetItem(str(cluster_id)))
            self.characterization_table.setItem(i, 1, QTableWidgetItem(cluster_data['cluster_type']))
            self.characterization_table.setItem(i, 2, QTableWidgetItem(str(cluster_data['particle_count'])))
            self.characterization_table.setItem(i, 3, QTableWidgetItem(f"{element_stats.get('mean', 0):.2f}"))
            self.characterization_table.setItem(i, 4, QTableWidgetItem(f"{element_stats.get('median', 0):.2f}"))
            self.characterization_table.setItem(i, 5, QTableWidgetItem(f"{element_stats.get('std', 0):.2f}"))
            self.characterization_table.setItem(i, 6, QTableWidgetItem(f"{element_stats.get('frequency', 0):.2f}"))
        
        self.characterization_table.resizeColumnsToContents()
        
        plot_data = {
            'algo_name': algo_name,
            'element': element,
            'characterization': characterization
        }
        
        self.characterization_plot.set_plot_data(plot_data, 'characterization')
    
    def save_evaluation(self):
        """
        Save evaluation results.
        
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Evaluation", "cluster_evaluation.png",
            "PNG Files (*.png);;PDF Files (*.pdf);;All Files (*)"
        )
        
        if file_path:
            try:
                if self.evaluation_plot.download_figure(file_path):
                    QMessageBox.information(self, "Success", f"Saved to: {file_path}")
                else:
                    QMessageBox.warning(self, "Warning", "No plot to save")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Save failed: {str(e)}")
    
    def save_clustering(self):
        """
        Save clustering results.
        
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Clustering", "clustering_results.png",
            "PNG Files (*.png);;PDF Files (*.pdf);;All Files (*)"
        )
        
        if file_path:
            try:
                if self.clustering_plot.download_figure(file_path):
                    QMessageBox.information(self, "Success", f"Saved to: {file_path}")
                else:
                    QMessageBox.warning(self, "Warning", "No plot to save")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Save failed: {str(e)}")
    
    def export_results(self):
        """
        Export all results.
        
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog
        import json
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "clustering_analysis.json",
            "JSON Files (*.json);;CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            try:
                export_data = {
                    'configuration': self.clustering_node.config,
                    'optimal_k': self.optimal_k_auto,
                    'optimal_algorithm': self.optimal_algorithm,
                    'evaluation_results': self.evaluation_results,
                    'cluster_characterization': {}
                }
                
                for algo_name, clusters in self.cluster_characterization.items():
                    export_data['cluster_characterization'][algo_name] = {}
                    for cluster_id, cluster_data in clusters.items():
                        export_data['cluster_characterization'][algo_name][str(cluster_id)] = {
                            'cluster_type': cluster_data['cluster_type'],
                            'particle_count': cluster_data['particle_count'],
                            'dominant_elements': cluster_data['dominant_elements']
                        }
                
                if file_path.endswith('.json'):
                    with open(file_path, 'w') as f:
                        json.dump(export_data, f, indent=2, default=str)
                
                QMessageBox.information(self, "Success", f"Exported to: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")
    
    def update_display(self):
        """
        Update display when node configuration changes.
        
        Returns:
            None
        """
        self.update_data_info_label()


class ClusteringPlotNode(QObject):
    """
    Clustering analysis node with PyQtGraph and all data types.
    """
    
    position_changed = Signal(object)
    configuration_changed = Signal()
    
    def __init__(self, parent_window=None):
        """
        Initialize clustering plot node.
        
        Args:
            parent_window: Parent window widget
        """
        super().__init__()
        self.title = "Clustering Analysis"
        self.node_type = "clustering_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.config = {
            'data_type_display': 'Counts (Raw)',
            'font_family': 'Times New Roman',
            'font_size': 12,
            'font_color': '#000000',
            'scaling': 'StandardScaler',
            'dim_reduction': 'None',
            'n_components': 2,
            'filter_zeros': True,
            'dbscan_eps': 0.5,
            'dbscan_min_samples': 5,
            'hier_linkage': 'ward',
            'min_clusters': 2,
            'max_clusters': 20
        }
        
        self.input_data = None
        self.plot_widget = None
        
    def set_position(self, pos):
        """
        Set position of the node.
        
        Args:
            pos: Position coordinates
        
        Returns:
            None
        """
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)
        
    def configure(self, parent_window):
        """
        Show configuration dialog.
        
        Args:
            parent_window: Parent window widget
        
        Returns:
            bool: True if configuration was successful
        """
        dialog = ClusteringDisplayDialog(self, parent_window)
        dialog.exec()
        return True
        
    def process_data(self, input_data):
        """
        Process input data for clustering analysis.
        
        Args:
            input_data (dict): Input data dictionary
        
        Returns:
            None
        """
        if not input_data:
            print("No input data received for clustering analysis")
            return
            
        print(f"Clustering analysis received data: {input_data.get('type', 'unknown')}")
        self.input_data = input_data
        
        self.configuration_changed.emit()