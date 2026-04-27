from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QPushButton,
    QFrame, QScrollArea, QWidget, QMenu, QTabWidget, QToolBar,
    QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QSlider, QLineEdit, QSizePolicy, QStackedWidget,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QCursor, QAction
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from mpl_toolkits.mplot3d import Axes3D
import numpy as np
import math
import gc
import sys
import warnings
warnings.filterwarnings('ignore')

from sklearn.cluster import (
    KMeans, DBSCAN, AgglomerativeClustering, SpectralClustering,
    MeanShift, OPTICS, MiniBatchKMeans, Birch,
)
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.metrics import (
    silhouette_score, calinski_harabasz_score, davies_bouldin_score,
    adjusted_rand_score, v_measure_score, fowlkes_mallows_score,
)

from scipy.cluster.hierarchy import (
    dendrogram as scipy_dendrogram,
    linkage as scipy_linkage,
)

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS,
    get_font_config, make_font_properties,
    apply_font_to_matplotlib, apply_font_to_colorbar_standalone,
    FontSettingsGroup,
    download_matplotlib_figure,
)
from results.utils_sort import (
    extract_mass_and_element, sort_elements_by_mass, format_element_label,
)


ALGORITHMS = [
    'K-Means', 'Hierarchical', 'DBSCAN', 'Spectral',
    'MiniBatch K-Means', 'Birch', 'Mean Shift', 'OPTICS',
]

METRICS = [
    'Silhouette', 'Calinski-Harabasz', 'Davies-Bouldin',
    'Adjusted Rand', 'V-Measure', 'Fowlkes-Mallows',
]

METRIC_KEYS = {
    'Silhouette':        ('Silhouette Score',       'silhouette_scores'),
    'Calinski-Harabasz': ('Calinski-Harabasz Index', 'calinski_harabasz_scores'),
    'Davies-Bouldin':    ('Davies-Bouldin Index',    'davies_bouldin_scores'),
    'Adjusted Rand':     ('Adjusted Rand Index',     'adjusted_rand_scores'),
    'V-Measure':         ('V-Measure Score',         'v_measure_scores'),
    'Fowlkes-Mallows':   ('Fowlkes-Mallows Index',   'fowlkes_mallows_scores'),
}

SCALING_OPTIONS = ['StandardScaler', 'MinMaxScaler', 'None']
DIM_REDUCTION_OPTIONS = ['None', 'PCA', 't-SNE']

DATA_TYPE_OPTIONS = [
    'Counts', 'Element Mass (fg)', 'Particle Mass (fg)',
    'Element Moles (fmol)', 'Particle Moles (fmol)',
    'Element Diameter (nm)', 'Particle Diameter (nm)',
    'Element Mass %', 'Particle Mass %',
    'Element Mole %', 'Particle Mole %',
]

DATA_KEY_MAP = {
    'Counts': 'elements',
    'Element Mass (fg)': 'element_mass_fg',
    'Particle Mass (fg)': 'particle_mass_fg',
    'Element Moles (fmol)': 'element_moles_fmol',
    'Particle Moles (fmol)': 'particle_moles_fmol',
    'Element Diameter (nm)': 'element_diameter_nm',
    'Particle Diameter (nm)': 'particle_diameter_nm',
    'Element Mass %': 'element_mass_fg',
    'Particle Mass %': 'particle_mass_fg',
    'Element Mole %': 'element_moles_fmol',
    'Particle Mole %': 'particle_moles_fmol',
}

CLUSTER_COLORS = [
    '#2563EB', '#DC2626', '#16A34A', '#D97706', '#7C3AED',
    '#0891B2', '#DB2777', '#65A30D', '#EA580C', '#4F46E5',
    '#0D9488', '#C026D3', '#CA8A04', '#E11D48', '#2DD4BF',
    '#6366F1', '#F59E0B', '#10B981', '#EF4444', '#8B5CF6',
]

ALGO_LINE_STYLES = {
    'K-Means':           dict(color='#2563EB', ls='-',  marker='o'),
    'Hierarchical':      dict(color='#DC2626', ls='-',  marker='s'),
    'DBSCAN':            dict(color='#16A34A', ls='--', marker='^'),
    'Spectral':          dict(color='#D97706', ls='-',  marker='D'),
    'MiniBatch K-Means': dict(color='#7C3AED', ls='--', marker='v'),
    'Birch':             dict(color='#0891B2', ls='-',  marker='P'),
    'Mean Shift':        dict(color='#DB2777', ls='--', marker='X'),
    'OPTICS':            dict(color='#65A30D', ls='--', marker='*'),
}


class ClusteringSettingsDialog(QDialog):
    """Full settings dialog opened from right-click → Configure."""

    def __init__(self, config, parent=None):
        """
        Args:
            config (Any): Configuration dictionary.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Clustering Analysis Settings")
        self.setMinimumWidth(480)
        self._cfg = dict(config)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        g = QGroupBox("Data Type")
        fl = QFormLayout(g)
        self.data_type = QComboBox()
        self.data_type.addItems(DATA_TYPE_OPTIONS)
        self.data_type.setCurrentText(self._cfg.get('data_type_display', 'Counts'))
        fl.addRow("Data:", self.data_type)
        layout.addWidget(g)

        g = QGroupBox("Preprocessing")
        fl = QFormLayout(g)
        self.scaling = QComboBox()
        self.scaling.addItems(SCALING_OPTIONS)
        self.scaling.setCurrentText(self._cfg.get('scaling', 'StandardScaler'))
        fl.addRow("Scaling:", self.scaling)

        self.dim_red = QComboBox()
        self.dim_red.addItems(DIM_REDUCTION_OPTIONS)
        self.dim_red.setCurrentText(self._cfg.get('dim_reduction', 'None'))
        fl.addRow("Dim. Reduction:", self.dim_red)

        self.n_comp = QSpinBox()
        self.n_comp.setRange(2, 5)
        self.n_comp.setValue(self._cfg.get('n_components', 2))
        fl.addRow("Components:", self.n_comp)

        self.filter_zeros = QCheckBox("Filter zero-only particles")
        self.filter_zeros.setChecked(self._cfg.get('filter_zeros', True))
        fl.addRow(self.filter_zeros)
        layout.addWidget(g)

        g = QGroupBox("Algorithm")
        vl = QVBoxLayout(g)

        sel_hl = QHBoxLayout()
        sel_hl.addWidget(QLabel("Select:"))
        self.algo_combo = QComboBox()
        self.algo_combo.addItems(ALGORITHMS)
        self.algo_combo.setCurrentText(self._cfg.get('selected_algorithm', 'K-Means'))
        sel_hl.addWidget(self.algo_combo)
        sel_hl.addStretch()
        vl.addLayout(sel_hl)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setStyleSheet("color:#E2E8F0;")
        vl.addWidget(sep)

        self.algo_stack = QStackedWidget()

        # ── 0: K-Means ──────────────────────────────────────────────
        p0 = QWidget(); f0 = QFormLayout(p0); f0.setContentsMargins(4, 4, 4, 4)
        self.km_n_init = QSpinBox(); self.km_n_init.setRange(1, 50)
        self.km_n_init.setValue(self._cfg.get('kmeans_n_init', 10))
        self.km_max_iter = QSpinBox(); self.km_max_iter.setRange(50, 2000)
        self.km_max_iter.setValue(self._cfg.get('kmeans_max_iter', 300))
        f0.addRow("n_init:", self.km_n_init)
        f0.addRow("max_iter:", self.km_max_iter)
        self.algo_stack.addWidget(p0)

        # ── 1: Hierarchical ─────────────────────────────────────────
        p1 = QWidget(); f1 = QFormLayout(p1); f1.setContentsMargins(4, 4, 4, 4)
        self.hier_linkage = QComboBox()
        self.hier_linkage.addItems(['ward', 'complete', 'average', 'single'])
        self.hier_linkage.setCurrentText(self._cfg.get('hier_linkage', 'ward'))
        self.hier_metric = QComboBox()
        self.hier_metric.addItems([
            'euclidean', 'l1', 'l2', 'manhattan', 'cosine',
            'chebyshev', 'canberra', 'braycurtis', 'correlation',
        ])
        self.hier_metric.setCurrentText(self._cfg.get('hier_metric', 'euclidean'))
        self.hier_show_dendro = QCheckBox("Show dendrogram after clustering")
        self.hier_show_dendro.setChecked(self._cfg.get('hier_show_dendrogram', False))
        f1.addRow("Linkage:", self.hier_linkage)
        f1.addRow("Distance metric:", self.hier_metric)
        f1.addRow(self.hier_show_dendro)
        def _sync_hier_metric(txt):
            """
            Args:
                txt (Any): The txt.
            """
            self.hier_metric.setEnabled(txt != 'ward')
            if txt == 'ward':
                self.hier_metric.setCurrentText('euclidean')
        self.hier_linkage.currentTextChanged.connect(_sync_hier_metric)
        _sync_hier_metric(self.hier_linkage.currentText())
        self.algo_stack.addWidget(p1)

        # ── 2: DBSCAN ───────────────────────────────────────────────
        p2 = QWidget(); f2 = QFormLayout(p2); f2.setContentsMargins(4, 4, 4, 4)
        self.dbscan_eps = QDoubleSpinBox(); self.dbscan_eps.setRange(0.01, 50.0)
        self.dbscan_eps.setSingleStep(0.05); self.dbscan_eps.setDecimals(3)
        self.dbscan_eps.setValue(self._cfg.get('dbscan_eps', 0.5))
        self.dbscan_min_samp = QSpinBox(); self.dbscan_min_samp.setRange(2, 100)
        self.dbscan_min_samp.setValue(self._cfg.get('dbscan_min_samples', 5))
        self.dbscan_metric = QComboBox()
        self.dbscan_metric.addItems(['euclidean', 'manhattan', 'cosine', 'l1', 'l2'])
        self.dbscan_metric.setCurrentText(self._cfg.get('dbscan_metric', 'euclidean'))
        f2.addRow("eps:", self.dbscan_eps)
        f2.addRow("min_samples:", self.dbscan_min_samp)
        f2.addRow("metric:", self.dbscan_metric)
        self.algo_stack.addWidget(p2)

        # ── 3: Spectral ─────────────────────────────────────────────
        p3 = QWidget(); f3 = QFormLayout(p3); f3.setContentsMargins(4, 4, 4, 4)
        self.spec_n_neighbors = QSpinBox(); self.spec_n_neighbors.setRange(2, 50)
        self.spec_n_neighbors.setValue(self._cfg.get('spectral_n_neighbors', 10))
        self.spec_affinity = QComboBox()
        self.spec_affinity.addItems(['rbf', 'nearest_neighbors', 'cosine'])
        self.spec_affinity.setCurrentText(self._cfg.get('spectral_affinity', 'rbf'))
        f3.addRow("n_neighbors:", self.spec_n_neighbors)
        f3.addRow("affinity:", self.spec_affinity)
        self.algo_stack.addWidget(p3)

        # ── 4: MiniBatch K-Means ────────────────────────────────────
        p4 = QWidget(); f4 = QFormLayout(p4); f4.setContentsMargins(4, 4, 4, 4)
        self.mbkm_n_init = QSpinBox(); self.mbkm_n_init.setRange(1, 50)
        self.mbkm_n_init.setValue(self._cfg.get('mbkm_n_init', 3))
        self.mbkm_batch = QSpinBox(); self.mbkm_batch.setRange(32, 10000)
        self.mbkm_batch.setSingleStep(64)
        self.mbkm_batch.setValue(self._cfg.get('mbkm_batch_size', 1024))
        self.mbkm_max_iter = QSpinBox(); self.mbkm_max_iter.setRange(10, 1000)
        self.mbkm_max_iter.setValue(self._cfg.get('mbkm_max_iter', 100))
        f4.addRow("n_init:", self.mbkm_n_init)
        f4.addRow("batch_size:", self.mbkm_batch)
        f4.addRow("max_iter:", self.mbkm_max_iter)
        self.algo_stack.addWidget(p4)

        # ── 5: Birch ────────────────────────────────────────────────
        p5 = QWidget(); f5 = QFormLayout(p5); f5.setContentsMargins(4, 4, 4, 4)
        self.birch_thresh = QDoubleSpinBox(); self.birch_thresh.setRange(0.01, 5.0)
        self.birch_thresh.setSingleStep(0.05); self.birch_thresh.setDecimals(3)
        self.birch_thresh.setValue(self._cfg.get('birch_threshold', 0.5))
        self.birch_branch = QSpinBox(); self.birch_branch.setRange(10, 500)
        self.birch_branch.setValue(self._cfg.get('birch_branching_factor', 50))
        f5.addRow("threshold:", self.birch_thresh)
        f5.addRow("branching_factor:", self.birch_branch)
        self.algo_stack.addWidget(p5)

        # ── 6: Mean Shift ───────────────────────────────────────────
        p6 = QWidget(); f6 = QFormLayout(p6); f6.setContentsMargins(4, 4, 4, 4)
        self.ms_auto_bw = QCheckBox("Auto bandwidth (estimate_bandwidth)")
        self.ms_auto_bw.setChecked(self._cfg.get('meanshift_auto_bw', True))
        self.ms_bandwidth = QDoubleSpinBox(); self.ms_bandwidth.setRange(0.01, 100.0)
        self.ms_bandwidth.setSingleStep(0.1); self.ms_bandwidth.setDecimals(3)
        self.ms_bandwidth.setValue(self._cfg.get('meanshift_bandwidth', 1.0))
        self.ms_bandwidth.setEnabled(not self.ms_auto_bw.isChecked())
        self.ms_auto_bw.toggled.connect(lambda c: self.ms_bandwidth.setEnabled(not c))
        self.ms_min_bin_freq = QSpinBox(); self.ms_min_bin_freq.setRange(1, 20)
        self.ms_min_bin_freq.setValue(self._cfg.get('meanshift_min_bin_freq', 1))
        f6.addRow(self.ms_auto_bw)
        f6.addRow("bandwidth:", self.ms_bandwidth)
        f6.addRow("min_bin_freq:", self.ms_min_bin_freq)
        self.algo_stack.addWidget(p6)

        # ── 7: OPTICS ───────────────────────────────────────────────
        p7 = QWidget(); f7 = QFormLayout(p7); f7.setContentsMargins(4, 4, 4, 4)
        self.optics_min_samp = QSpinBox(); self.optics_min_samp.setRange(2, 100)
        self.optics_min_samp.setValue(self._cfg.get('optics_min_samples', 5))
        self.optics_metric = QComboBox()
        self.optics_metric.addItems(['euclidean', 'manhattan', 'cosine', 'l1', 'l2'])
        self.optics_metric.setCurrentText(self._cfg.get('optics_metric', 'euclidean'))
        self.optics_cluster_method = QComboBox()
        self.optics_cluster_method.addItems(['xi', 'dbscan'])
        self.optics_cluster_method.setCurrentText(
            self._cfg.get('optics_cluster_method', 'xi'))
        f7.addRow("min_samples:", self.optics_min_samp)
        f7.addRow("metric:", self.optics_metric)
        f7.addRow("cluster_method:", self.optics_cluster_method)
        self.algo_stack.addWidget(p7)

        def _switch_page(text):
            """
            Args:
                text (Any): Text string.
            """
            idx = ALGORITHMS.index(text) if text in ALGORITHMS else 0
            self.algo_stack.setCurrentIndex(idx)
        self.algo_combo.currentTextChanged.connect(_switch_page)
        _switch_page(self.algo_combo.currentText())

        vl.addWidget(self.algo_stack)
        layout.addWidget(g)

        g = QGroupBox("Evaluation & Metrics")
        fl = QFormLayout(g)
        w = QWidget()
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        self.min_k = QSpinBox()
        self.min_k.setRange(2, 10)
        self.min_k.setValue(self._cfg.get('min_clusters', 2))
        self.min_k.setMaximumWidth(55)
        self.max_k = QSpinBox()
        self.max_k.setRange(3, 50)
        self.max_k.setValue(self._cfg.get('max_clusters', 20))
        self.max_k.setMaximumWidth(55)
        hl.addWidget(QLabel("K from"))
        hl.addWidget(self.min_k)
        hl.addWidget(QLabel("to"))
        hl.addWidget(self.max_k)
        hl.addStretch()
        fl.addRow("K Range:", w)

        self.auto_k = QCheckBox("Auto-select optimal K")
        self.auto_k.setChecked(self._cfg.get('auto_select_k', True))
        fl.addRow(self.auto_k)

        enabled_m = self._cfg.get('enabled_metrics',
                                  ['Silhouette', 'Calinski-Harabasz', 'Davies-Bouldin'])
        self.metric_cbs = {}
        for m in METRICS:
            cb = QCheckBox(m)
            cb.setChecked(m in enabled_m)
            self.metric_cbs[m] = cb
            fl.addRow(cb)
        layout.addWidget(g)

        self._font_grp = FontSettingsGroup(self._cfg)
        layout.addWidget(self._font_grp.build())

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        out = dict(self._cfg)
        out['data_type_display'] = self.data_type.currentText()
        out['scaling'] = self.scaling.currentText()
        out['dim_reduction'] = self.dim_red.currentText()
        out['n_components'] = self.n_comp.value()
        out['filter_zeros'] = self.filter_zeros.isChecked()
        out['min_clusters'] = self.min_k.value()
        out['max_clusters'] = self.max_k.value()
        out['auto_select_k'] = self.auto_k.isChecked()
        out['enabled_metrics'] = [m for m, cb in self.metric_cbs.items() if cb.isChecked()]

        selected = self.algo_combo.currentText()
        out['selected_algorithm'] = selected
        out['enabled_algorithms'] = [selected]

        out['kmeans_n_init']    = self.km_n_init.value()
        out['kmeans_max_iter']  = self.km_max_iter.value()

        out['hier_linkage']          = self.hier_linkage.currentText()
        out['hier_metric']           = self.hier_metric.currentText()
        out['hier_show_dendrogram']  = self.hier_show_dendro.isChecked()

        out['dbscan_eps']         = self.dbscan_eps.value()
        out['dbscan_min_samples'] = self.dbscan_min_samp.value()
        out['dbscan_metric']      = self.dbscan_metric.currentText()

        out['spectral_n_neighbors'] = self.spec_n_neighbors.value()
        out['spectral_affinity']    = self.spec_affinity.currentText()

        out['mbkm_n_init']      = self.mbkm_n_init.value()
        out['mbkm_batch_size']  = self.mbkm_batch.value()
        out['mbkm_max_iter']    = self.mbkm_max_iter.value()

        out['birch_threshold']       = self.birch_thresh.value()
        out['birch_branching_factor'] = self.birch_branch.value()

        out['meanshift_auto_bw']      = self.ms_auto_bw.isChecked()
        out['meanshift_bandwidth']    = self.ms_bandwidth.value()
        out['meanshift_min_bin_freq'] = self.ms_min_bin_freq.value()

        out['optics_min_samples']     = self.optics_min_samp.value()
        out['optics_metric']          = self.optics_metric.currentText()
        out['optics_cluster_method']  = self.optics_cluster_method.currentText()

        out.update(self._font_grp.collect())
        return out


def _style_ax(ax, cfg, xlabel='', ylabel='', title=''):
    """Apply consistent styling to a matplotlib axes.
    Args:
        ax (Any): The ax.
        cfg (Any): The cfg.
        xlabel (Any): The xlabel.
        ylabel (Any): The ylabel.
        title (Any): Window or dialog title.
    """
    fp = make_font_properties(cfg)
    fc = get_font_config(cfg)
    ax.set_facecolor('#FAFAFA')
    ax.grid(True, alpha=0.25, linewidth=0.5, color='#CBD5E1')
    for spine in ax.spines.values():
        spine.set_color('#CBD5E1')
        spine.set_linewidth(0.8)
    if xlabel:
        ax.set_xlabel(xlabel, fontproperties=fp, color=fc['color'])
    if ylabel:
        ax.set_ylabel(ylabel, fontproperties=fp, color=fc['color'])
    if title:
        ax.set_title(title, fontproperties=fp, color=fc['color'], pad=10)
    ax.tick_params(labelsize=max(fc['size'] - 3, 7), colors=fc['color'])


def _draw_evaluation(fig, eval_results, cfg, optimal_k=None, view_algo='All Algorithms'):
    """Draw evaluation metric curves on a matplotlib Figure.
    Args:
        fig (Any): The fig.
        eval_results (Any): The eval results.
        cfg (Any): The cfg.
        optimal_k (Any): The optimal k.
        view_algo (Any): The view algo.
    """
    fig.clear()

    enabled_metrics = cfg.get('enabled_metrics',
                              ['Silhouette', 'Calinski-Harabasz', 'Davies-Bouldin'])
    active = [(METRIC_KEYS[m][0], METRIC_KEYS[m][1])
              for m in enabled_metrics if m in METRIC_KEYS]

    if not active:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, 'No metrics selected', ha='center', va='center',
                fontsize=13, color='gray', transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        return

    algos = list(eval_results.keys()) if view_algo == 'All Algorithms' else (
        [view_algo] if view_algo in eval_results else [])

    if not algos:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, 'No algorithm data', ha='center', va='center',
                fontsize=13, color='gray', transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        return

    n = len(active)
    cols = min(2, n)
    rows = math.ceil(n / cols)

    axes = []
    for i in range(n):
        ax = fig.add_subplot(rows, cols, i + 1)
        axes.append(ax)

    for i, (metric_name, metric_key) in enumerate(active):
        ax = axes[i]

        for algo_name in algos:
            res = eval_results.get(algo_name, {})
            k_vals = res.get('k_values', [])
            scores = res.get(metric_key, [])
            if not k_vals or not scores or len(k_vals) != len(scores):
                continue

            style = ALGO_LINE_STYLES.get(algo_name,
                                         dict(color='#64748B', ls='-', marker='o'))
            ax.plot(k_vals, scores,
                    color=style['color'], linestyle=style['ls'],
                    marker=style['marker'],
                    markersize=cfg.get('eval_marker_size', 5),
                    linewidth=cfg.get('eval_line_width', 1.8),
                    label=algo_name, alpha=0.85, picker=5)

        if optimal_k is not None:
            ax.axvline(optimal_k, color='#DC2626', linestyle='--',
                       linewidth=1.5, alpha=0.7, label=f'Optimal K={optimal_k}')

        _style_ax(ax, cfg, xlabel='Number of Clusters (K)',
                  ylabel=metric_name, title=metric_name)

        leg = ax.legend(fontsize=max(get_font_config(cfg)['size'] - 4, 7),
                        loc='best', framealpha=0.9, edgecolor='#CBD5E1')
        if leg:
            leg.get_frame().set_linewidth(0.5)

        ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    total = rows * cols
    for j in range(n, total):
        fig.add_subplot(rows, cols, j + 1).set_visible(False)

    fig.tight_layout(pad=1.5)


def _draw_clustering(fig, clustering_results, data_matrix, characterisation, cfg):
    """Draw cluster scatter plots on a matplotlib Figure.
    Args:
        fig (Any): The fig.
        clustering_results (Any): The clustering results.
        data_matrix (Any): The data matrix.
        characterisation (Any): The characterisation.
        cfg (Any): The cfg.
    """
    fig.clear()

    if not clustering_results or data_matrix is None:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, 'No clustering data\nRun Step 2 first',
                ha='center', va='center', fontsize=13, color='gray',
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        return

    n = len(clustering_results)
    cols = min(3, n)
    rows = math.ceil(n / cols)

    for idx, (algo_name, result) in enumerate(clustering_results.items()):
        ax = fig.add_subplot(rows, cols, idx + 1)
        ax._algo_name = algo_name
        labels = result.get('labels')
        if labels is None:
            ax.text(0.5, 0.5, 'No labels', ha='center', va='center',
                    color='gray', transform=ax.transAxes)
            continue

        if data_matrix.shape[1] >= 2:
            x, y = data_matrix[:, 0], data_matrix[:, 1]
        else:
            x = data_matrix[:, 0] if data_matrix.ndim > 1 else data_matrix
            y = np.zeros_like(x)

        unique_labels = np.unique(labels)

        pt_size  = cfg.get('scatter_point_size', 18)
        alpha    = cfg.get('scatter_alpha', 0.65)
        centroids = cfg.get('scatter_show_centroids', True)

        sample_arr   = cfg.get('_sample_arr', None)
        sample_names = cfg.get('_sample_names', [])
        SAMPLE_EDGE  = ['#1D4ED8','#B45309','#166534','#7C3AED',
                        '#9F1239','#0F766E','#92400E','#1E40AF']

        for j, lab in enumerate(unique_labels):
            mask = labels == lab

            if lab == -1:
                ax.scatter(x[mask], y[mask], s=12, marker='x',
                           color='#9CA3AF', alpha=0.5, linewidths=0.8,
                           label='Noise', zorder=2)
            else:
                color = CLUSTER_COLORS[j % len(CLUSTER_COLORS)]
                ctype = 'Unknown'
                if (algo_name in characterisation and
                        lab in characterisation[algo_name]):
                    ctype = characterisation[algo_name][lab].get(
                        'cluster_type_short',
                        characterisation[algo_name][lab].get('cluster_type', 'Unknown'))

                if sample_arr is not None and len(sample_arr) == len(x):
                    unique_samples = np.unique(sample_arr)
                    for si, sname in enumerate(unique_samples):
                        smask = mask & (sample_arr == sname)
                        if smask.any():
                            ec = SAMPLE_EDGE[si % len(SAMPLE_EDGE)]
                            lbl = f'C{lab}: {ctype} [{sname}]' if len(unique_samples) > 1 else f'C{lab}: {ctype}'
                            ax.scatter(x[smask], y[smask], s=pt_size, marker='o',
                                       color=color, alpha=alpha,
                                       edgecolors=ec, linewidths=0.9,
                                       label=lbl, zorder=3)
                else:
                    ax.scatter(x[mask], y[mask], s=pt_size, marker='o',
                               color=color, alpha=alpha, edgecolors='white',
                               linewidths=0.3, label=f'C{lab}: {ctype}',
                               zorder=3)

                if centroids:
                    cx, cy = x[mask].mean(), y[mask].mean()
                    ax.scatter(cx, cy, s=90, marker='*', color=color,
                               edgecolors='black', linewidths=0.8, zorder=5)

        n_clusters = result.get('n_clusters', 0)
        n_noise = result.get('n_noise', 0)
        title = f'{algo_name}  (K={n_clusters}'
        if n_noise > 0:
            title += f', noise={n_noise}'
        title += ')'

        _style_ax(ax, cfg, xlabel='Component 1', ylabel='Component 2', title=title)

        if n_clusters <= 8:
            leg = ax.legend(fontsize=max(get_font_config(cfg)['size'] - 5, 6),
                            loc='best', framealpha=0.9, edgecolor='#CBD5E1',
                            markerscale=0.7, handletextpad=0.3)
            if leg:
                leg.get_frame().set_linewidth(0.5)

    total = rows * cols
    for j in range(n, total):
        fig.add_subplot(rows, cols, j + 1).set_visible(False)

    fig.tight_layout(pad=1.2)


def _draw_characterisation(fig, algo_name, element, characterisation, cfg):
    """Draw cluster characterisation bar chart on a matplotlib Figure.
    Args:
        fig (Any): The fig.
        algo_name (Any): The algo name.
        element (Any): The element.
        characterisation (Any): The characterisation.
        cfg (Any): The cfg.
    """
    fig.clear()

    if not algo_name or not element or algo_name not in characterisation:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, 'Select algorithm and element',
                ha='center', va='center', fontsize=13, color='gray',
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        return

    data = characterisation[algo_name]
    cluster_ids = sorted(data.keys())
    if not cluster_ids:
        return

    labels_x  = []
    means     = []
    medians   = []
    freqs     = []
    pct_vals  = []
    counts    = []
    comp_strs = []

    for cid in cluster_ids:
        cd  = data[cid]
        es  = cd.get('element_stats', {}).get(element, {})
        pct = cd.get('element_pcts', {}).get(element, 0.0)
        labels_x.append(f'C{cid}')
        means.append(es.get('mean', 0))
        medians.append(es.get('median', 0))
        freqs.append(es.get('frequency', 0) * 100)
        pct_vals.append(pct)
        counts.append(cd.get('particle_count', 0))
        sig = cd.get('composition', [])[:3]
        comp_strs.append('\n'.join(f"{e} {p:.1f}%" for e, p in sig) or 'No signal')

    x = np.arange(len(labels_x))
    w = 0.28

    fp = make_font_properties(cfg)
    fc = get_font_config(cfg)

    ax1 = fig.add_subplot(111)
    ax2 = ax1.twinx()
    ax3 = ax1.twinx()
    ax3.spines['right'].set_position(('outward', 55))

    bars_mean = ax1.bar(x - w / 2, means, w, color='#2563EB',
                        alpha=cfg.get('char_bar_alpha', 0.8),
                        edgecolor='white', linewidth=0.5, label='Mean')
    bars_med  = ax1.bar(x + w / 2, medians, w, color='#7C3AED',
                        alpha=cfg.get('char_bar_alpha', 0.8),
                        edgecolor='white', linewidth=0.5, label='Median')

    ax2.plot(x, freqs, color='#DC2626', marker='D', markersize=6,
             linewidth=2, label='Detection %', zorder=5)

    colors_pct = ['#16A34A' if p >= 0.1 else '#CBD5E1' for p in pct_vals]
    ax3.plot(x, pct_vals, color='#16A34A', marker='s', markersize=5,
             linewidth=1.6, linestyle='--', label=f'{element} Contr. %', zorder=4)
    for xi, pv, c in zip(x, pct_vals, colors_pct):
        ax3.scatter(xi, pv, s=30, color=c, zorder=5)

    for i, (c, m, pv) in enumerate(zip(counts, means, pct_vals)):
        ax1.annotate(f'n={c}', (x[i], m), textcoords='offset points',
                     xytext=(0, 5), ha='center', fontsize=max(fc['size'] - 4, 7),
                     color='#475569')
        sym = '✓' if pv >= 0.1 else '✗'
        clr = '#16A34A' if pv >= 0.1 else '#DC2626'
        ax3.annotate(f'{sym}{pv:.1f}%', (xi, pv),
                     textcoords='offset points',
                     xytext=(0, 6), ha='center',
                     fontsize=max(fc['size'] - 5, 6), color=clr)

    xtick_labels = [f'{lbl}\n{cs}' for lbl, cs in zip(labels_x, comp_strs)]
    ax1.set_xticks(x)
    ax1.set_xticklabels(xtick_labels, fontproperties=fp, color=fc['color'],
                        fontsize=max(fc['size'] - 3, 7), linespacing=1.3)

    _style_ax(ax1, cfg, xlabel='',
              ylabel=f'{element}  (value)',
              title=f'{element} Distribution — {algo_name}  [composition threshold > 0.1%]')

    ax2.set_ylabel('Detection Frequency (%)', fontproperties=fp, color='#DC2626')
    ax2.tick_params(axis='y', labelcolor='#DC2626',
                    labelsize=max(fc['size'] - 3, 7))
    ax2.set_ylim(0, 115)
    ax2.spines['right'].set_color('#DC2626')

    ax3.set_ylabel(f'{element} Signal Contribution (%)',
                   fontproperties=fp, color='#16A34A')
    ax3.tick_params(axis='y', labelcolor='#16A34A',
                    labelsize=max(fc['size'] - 3, 7))
    ax3.spines['right'].set_color('#16A34A')
    ax3.axhline(0.1, color='#16A34A', linestyle=':', linewidth=1.0,
                alpha=0.7, label='0.1% threshold')

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    lines3, labels3 = ax3.get_legend_handles_labels()
    leg = ax1.legend(lines1 + lines2 + lines3, labels1 + labels2 + labels3,
                     loc='upper right', fontsize=max(fc['size'] - 4, 7),
                     framealpha=0.9, edgecolor='#CBD5E1')
    if leg:
        leg.get_frame().set_linewidth(0.5)

    fig.tight_layout(pad=1.5)


class ClusteringDisplayDialog(QDialog):
    """
    Main clustering dialog with toolbar, tabs, and right-click menus.
    """

    def __init__(self, node, parent_window=None):
        """
        Args:
            node (Any): Tree or graph node.
            parent_window (Any): The parent window.
        """
        super().__init__(parent_window)
        self.node = node
        self.parent_window = parent_window
        self.setWindowTitle("Clustering Analysis")
        self.setMinimumSize(1200, 800)

        self.eval_results = {}
        self.final_results = {}
        self.characterisation = {}
        self.optimal_k = None
        self.optimal_algo = None
        self._data_matrix_cache = None
        self._raw_matrix = None
        self._elements_cache = []
        self._particle_samples = None
        self._hover_ann = {}

        self._build_ui()
        self.node.configuration_changed.connect(self._on_node_changed)

    def _is_multi(self):
        """
        Returns:
            object: Result of the operation.
        """
        return (self.node.input_data and
                self.node.input_data.get('type') == 'multiple_sample_data')

    # ── UI ──────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        toolbar = QFrame()
        toolbar.setStyleSheet(
            "QFrame { background: #F8FAFC; border-bottom: 1px solid #E2E8F0; }")
        toolbar.setFixedHeight(48)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(8, 4, 8, 4)

        self.eval_btn = self._make_btn("① Evaluate K", '#2563EB', self._run_evaluation)
        tl.addWidget(self.eval_btn)

        self.optimal_label = QLabel("Optimal K: —")
        self.optimal_label.setStyleSheet(
            "font-weight: bold; color: #D97706; padding: 0 12px; font-size: 12px;")
        tl.addWidget(self.optimal_label)

        tl.addWidget(QLabel("K:"))
        self.k_combo = QComboBox()
        self.k_combo.setFixedWidth(60)
        self.k_combo.setEnabled(False)
        tl.addWidget(self.k_combo)

        self.cluster_btn = self._make_btn("② Cluster", '#16A34A', self._run_clustering)
        self.cluster_btn.setEnabled(False)
        tl.addWidget(self.cluster_btn)

        tl.addStretch()

        self.export_btn = self._make_btn("Export", '#D97706', self._export_results)
        self.export_btn.setEnabled(False)
        tl.addWidget(self.export_btn)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(120)
        self.progress.setFixedHeight(16)
        self.progress.setVisible(False)
        tl.addWidget(self.progress)

        layout.addWidget(toolbar)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab { padding: 6px 18px; font-size: 12px; }
            QTabBar::tab:selected { font-weight: bold; }
        """)

        self._build_eval_tab()
        self._build_cluster_tab()
        self._build_char_tab()
        self._build_overview_tab()
        self._build_dendrogram_tab()
        self._build_3d_tab()

        layout.addWidget(self.tabs)

        self.status = QLabel("Ready — connect data and run evaluation")
        self.status.setStyleSheet(
            "color: #6B7280; font-size: 11px; padding: 2px 8px; "
            "background: #F8FAFC; border-top: 1px solid #E2E8F0;")
        layout.addWidget(self.status)

    def _make_btn(self, text, color, slot):
        """
        Args:
            text (Any): Text string.
            color (Any): Colour value.
            slot (Any): The slot.
        Returns:
            object: Result of the operation.
        """
        btn = QPushButton(text)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {color}; color: white; padding: 6px 14px;
                border-radius: 4px; font-weight: bold; font-size: 11px;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
            QPushButton:disabled {{ background: #CBD5E1; }}
        """)
        btn.clicked.connect(slot)
        return btn

    # ── Evaluation tab ──────────────────────

    def _build_eval_tab(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        vl.setContentsMargins(4, 4, 4, 4)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("View:"))
        self.algo_view = QComboBox()
        self.algo_view.addItem('All Algorithms')
        self.algo_view.currentTextChanged.connect(self._refresh_eval_plot)
        hl.addWidget(self.algo_view)
        hl.addStretch()
        po = self._make_popout_btn(lambda: self._pop_out_figure('eval'))
        hl.addWidget(po)
        vl.addLayout(hl)

        self.eval_fig = Figure(figsize=(12, 8), dpi=120, tight_layout=True)
        self.eval_canvas = FigureCanvas(self.eval_fig)
        self.eval_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.eval_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, 'eval'))
        self.eval_canvas.mpl_connect('pick_event', self._on_eval_pick)
        vl.addWidget(self.eval_canvas, stretch=1)

        self.tabs.addTab(tab, "① Evaluation")

    # ── Clustering tab ──────────────────────

    def _build_cluster_tab(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        vl.setContentsMargins(4, 4, 4, 4)

        hl = QHBoxLayout()
        hl.addStretch()
        po = self._make_popout_btn(lambda: self._pop_out_figure('cluster'))
        hl.addWidget(po)
        vl.addLayout(hl)

        self.cluster_fig = Figure(figsize=(14, 9), dpi=120, tight_layout=True)
        self.cluster_canvas = FigureCanvas(self.cluster_fig)
        self.cluster_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.cluster_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, 'cluster'))
        self.cluster_canvas.mpl_connect('motion_notify_event', self._on_cluster_hover)
        self._cl_drag_ax    = None
        self._cl_drag_start = None
        self._cl_drag_pos0  = None
        self.cluster_canvas.mpl_connect('button_press_event',   self._cl_drag_press)
        self.cluster_canvas.mpl_connect('motion_notify_event',  self._cl_drag_motion)
        self.cluster_canvas.mpl_connect('button_release_event', self._cl_drag_release)
        vl.addWidget(self.cluster_canvas, stretch=1)

        self.tabs.addTab(tab, "② Clusters")

    # ── Characterisation tab ────────────────

    def _build_char_tab(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        vl.setContentsMargins(4, 4, 4, 4)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("Algorithm:"))
        self.char_algo = QComboBox()
        self.char_algo.currentTextChanged.connect(self._refresh_char)
        hl.addWidget(self.char_algo)

        hl.addWidget(QLabel("Element:"))
        self.char_elem = QComboBox()
        self.char_elem.currentTextChanged.connect(self._refresh_char)
        hl.addWidget(self.char_elem)
        hl.addStretch()
        po = self._make_popout_btn(lambda: self._pop_out_figure('char'))
        hl.addWidget(po)
        vl.addLayout(hl)

        self.char_table = QTableWidget()
        self.char_table.setAlternatingRowColors(True)
        self.char_table.setMaximumHeight(200)
        self.char_table.setStyleSheet(
            "QTableWidget { font-size: 11px; gridline-color: #E2E8F0; }"
            "QHeaderView::section { background: #F1F5F9; font-weight: bold; "
            "border: 1px solid #E2E8F0; padding: 4px; }")
        vl.addWidget(self.char_table)

        charts_hl = QHBoxLayout()

        self.char_fig = Figure(figsize=(7, 5), dpi=110, tight_layout=True)
        self.char_canvas = FigureCanvas(self.char_fig)
        self.char_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.char_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, 'char'))
        charts_hl.addWidget(self.char_canvas, stretch=1)

        self.radar_fig = Figure(figsize=(5, 5), dpi=110, tight_layout=True)
        self.radar_canvas = FigureCanvas(self.radar_fig)
        charts_hl.addWidget(self.radar_canvas, stretch=1)

        vl.addLayout(charts_hl, stretch=1)

        self.tabs.addTab(tab, "③ Characterisation")

    # ── Context menu ────────────────────────

    def _ctx_menu(self, pos, tab):
        """
        Args:
            pos (Any): Position point.
            tab (Any): The tab.
        """
        menu = QMenu(self)

        dt_menu = menu.addMenu("Data Type")
        cur = self.node.config.get('data_type_display', 'Counts')
        for dt in DATA_TYPE_OPTIONS:
            a = dt_menu.addAction(dt)
            a.setCheckable(True)
            a.setChecked(dt == cur)
            a.triggered.connect(lambda _, d=dt: self._set('data_type_display', d))

        menu.addSeparator()

        edit_action = menu.addAction("✎  Edit Figure…")
        edit_action.triggered.connect(lambda: self._edit_figure(tab))

        cfg_action = menu.addAction("⚙  Configure…")
        cfg_action.triggered.connect(self._open_settings)

        fig_map = {'eval': self.eval_fig, 'cluster': self.cluster_fig,
                   'char': self.char_fig, 'overview': self.overview_fig,
                   'dendro': self.dendro_fig, '3d': self._3d_fig}
        names   = {'eval': 'evaluation.png', 'cluster': 'clusters.png',
                   'char': 'characterisation.png', 'overview': 'overview.png',
                   'dendro': 'dendrogram.png', '3d': '3d_scatter.png'}
        dl = menu.addAction("💾 Download Figure…")
        dl.triggered.connect(
            lambda: download_matplotlib_figure(fig_map.get(tab, self.eval_fig),
                                               self, names.get(tab, 'figure.png')))

        menu.exec(QCursor.pos())

    # ── Pop-out button factory ───────────────

    def _make_popout_btn(self, slot):
        """
        Args:
            slot (Any): The slot.
        Returns:
            object: Result of the operation.
        """
        btn = QPushButton("⤢")
        btn.setToolTip("Open in separate window")
        btn.setFixedSize(26, 22)
        btn.setStyleSheet(
            "QPushButton { background: #F1F5F9; border: 1px solid #CBD5E1; "
            "border-radius: 3px; font-size: 13px; color: #475569; }"
            "QPushButton:hover { background: #E2E8F0; }")
        btn.clicked.connect(slot)
        return btn

    def _pop_out_figure(self, tab: str):
        """Redraw the requested figure into a standalone resizable window.
        Args:
            tab (str): The tab.
        """
        titles = {'eval': 'Evaluation Metrics', 'cluster': 'Cluster Scatter',
                  'char': 'Characterisation', 'overview': 'Overview Heatmap',
                  'dendro': 'Dendrogram', '3d': '3D Scatter'}
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Clustering — {titles.get(tab, tab)}")
        dlg.setMinimumSize(900, 620)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        vl = QVBoxLayout(dlg)
        vl.setContentsMargins(6, 6, 6, 6)

        new_fig = Figure(figsize=(13, 8), dpi=110, tight_layout=True)
        new_canvas = FigureCanvas(new_fig)
        vl.addWidget(new_canvas, stretch=1)

        btn_hl = QHBoxLayout()
        dl_btn = QPushButton("💾  Save Figure…")
        dl_btn.setStyleSheet(
            "QPushButton { background:#2563EB; color:white; padding:5px 12px; "
            "border-radius:4px; font-size:11px; }")
        dl_btn.clicked.connect(
            lambda: download_matplotlib_figure(new_fig, dlg,
                                               f'{tab}_figure.png'))
        btn_hl.addStretch()
        btn_hl.addWidget(dl_btn)
        vl.addLayout(btn_hl)

        if tab == 'eval':
            view = self.algo_view.currentText() or 'All Algorithms'
            _draw_evaluation(new_fig, self.eval_results, self.node.config,
                             self.optimal_k, view)
        elif tab == 'cluster':
            if self.final_results and self._data_matrix_cache is not None:
                _draw_clustering(new_fig, self.final_results,
                                 self._data_matrix_cache,
                                 self.characterisation, self.node.config)
        elif tab == 'char':
            algo = self.char_algo.currentText()
            elem = self.char_elem.currentText()
            if algo and elem:
                _draw_characterisation(new_fig, algo, elem,
                                       self.characterisation, self.node.config)
        elif tab == 'overview':
            self._draw_overview_into(new_fig)
        elif tab == 'dendro':
            self._draw_dendrogram_into(new_fig)
        elif tab == '3d':
            self._draw_3d_into(new_fig)

        new_canvas.draw()
        dlg.show()

    # ── Per-figure edit dialog ───────────────

    def _edit_figure(self, tab: str):
        """Open a lightweight per-figure settings dialog.
        Args:
            tab (str): The tab.
        """
        cfg = self.node.config
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit Figure — {tab.capitalize()}")
        dlg.setMinimumWidth(320)
        outer = QVBoxLayout(dlg)
        form = QFormLayout()

        widgets = {}

        if tab == 'eval':
            lw = QDoubleSpinBox(); lw.setRange(0.5, 5.0); lw.setSingleStep(0.2)
            lw.setValue(cfg.get('eval_line_width', 1.8))
            ms = QSpinBox(); ms.setRange(2, 14)
            ms.setValue(cfg.get('eval_marker_size', 5))
            form.addRow("Line Width:", lw)
            form.addRow("Marker Size:", ms)
            widgets = {'eval_line_width': lw, 'eval_marker_size': ms}

        elif tab == 'cluster':
            ps = QSpinBox(); ps.setRange(4, 80)
            ps.setValue(cfg.get('scatter_point_size', 18))
            al = QDoubleSpinBox(); al.setRange(0.1, 1.0); al.setSingleStep(0.05)
            al.setValue(cfg.get('scatter_alpha', 0.65))
            cc = QCheckBox("Show Centroids")
            cc.setChecked(cfg.get('scatter_show_centroids', True))
            form.addRow("Point Size:", ps)
            form.addRow("Opacity:", al)
            form.addRow("", cc)
            widgets = {'scatter_point_size': ps, 'scatter_alpha': al,
                       'scatter_show_centroids': cc}

        elif tab == 'char':
            ba = QDoubleSpinBox(); ba.setRange(0.1, 1.0); ba.setSingleStep(0.05)
            ba.setValue(cfg.get('char_bar_alpha', 0.8))
            ra = QDoubleSpinBox(); ra.setRange(0.05, 0.5); ra.setSingleStep(0.05)
            ra.setValue(cfg.get('radar_fill_alpha', 0.12))
            rl = QDoubleSpinBox(); rl.setRange(0.5, 4.0); rl.setSingleStep(0.2)
            rl.setValue(cfg.get('radar_line_width', 1.8))
            form.addRow("Bar Opacity:", ba)
            form.addRow("Radar Fill Opacity:", ra)
            form.addRow("Radar Line Width:", rl)
            widgets = {'char_bar_alpha': ba, 'radar_fill_alpha': ra,
                       'radar_line_width': rl}

        elif tab == 'overview':
            cmap_cb = QComboBox()
            cmaps = ['YlOrRd', 'Blues', 'Greens', 'Purples', 'RdYlGn',
                     'coolwarm', 'viridis', 'plasma', 'magma', 'cividis']
            cmap_cb.addItems(cmaps)
            cur_cmap = cfg.get('overview_colormap', 'YlOrRd')
            if cur_cmap in cmaps:
                cmap_cb.setCurrentText(cur_cmap)
            av = QCheckBox("Show Cell Values")
            av.setChecked(cfg.get('overview_show_values', True))
            form.addRow("Colormap:", cmap_cb)
            form.addRow("", av)
            widgets = {'overview_colormap': cmap_cb, 'overview_show_values': av}

        outer.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        outer.addWidget(btns)

        if dlg.exec() == QDialog.Accepted:
            for key, w in widgets.items():
                if isinstance(w, QCheckBox):
                    cfg[key] = w.isChecked()
                elif isinstance(w, QComboBox):
                    cfg[key] = w.currentText()
                else:
                    cfg[key] = w.value()
            self._redraw_figure(tab)

    def _redraw_figure(self, tab: str):
        """
        Args:
            tab (str): The tab.
        """
        if tab == 'eval':
            self._refresh_eval_plot()
        elif tab == 'cluster':
            if self.final_results and self._data_matrix_cache is not None:
                _draw_clustering(self.cluster_fig, self.final_results,
                                 self._data_matrix_cache,
                                 self.characterisation, self.node.config)
                self.cluster_canvas.draw()
        elif tab == 'char':
            self._refresh_char()
        elif tab == 'overview':
            self._draw_overview()

    # ── Subplot drag (cluster tab) ───────────

    def _cl_drag_press(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        if event.button != 1 or event.inaxes is None:
            return
        self._cl_drag_ax    = event.inaxes
        self._cl_drag_start = (event.x, event.y)
        self._cl_drag_pos0  = event.inaxes.get_position()

    def _cl_drag_motion(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        if self._cl_drag_ax is None or event.x is None:
            return
        w_px, h_px = (self.cluster_fig.get_size_inches()
                      * self.cluster_fig.dpi)
        dx = (event.x - self._cl_drag_start[0]) / w_px
        dy = (event.y - self._cl_drag_start[1]) / h_px
        p  = self._cl_drag_pos0
        self._cl_drag_ax.set_position(
            [p.x0 + dx, p.y0 + dy, p.width, p.height])
        self.cluster_canvas.draw_idle()

    def _cl_drag_release(self, _event):
        """
        Args:
            _event (Any): The  event.
        """
        self._cl_drag_ax    = None
        self._cl_drag_start = None
        self._cl_drag_pos0  = None

    def _set(self, key, value):
        """
        Args:
            key (Any): Dictionary or storage key.
            value (Any): Value to set or process.
        """
        self.node.config[key] = value
        self._data_matrix_cache = None
        self.status.setText(f"Changed {key} → re-run evaluation for updated results")

    # ── Overview tab ────────────────────────

    def _build_overview_tab(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        vl.setContentsMargins(4, 4, 4, 4)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("Algorithm:"))
        self.ov_algo = QComboBox()
        self.ov_algo.currentTextChanged.connect(self._draw_overview)
        hl.addWidget(self.ov_algo)
        hl.addStretch()
        po = self._make_popout_btn(lambda: self._pop_out_figure('overview'))
        hl.addWidget(po)
        vl.addLayout(hl)

        self.overview_fig = Figure(figsize=(14, 7), dpi=110, tight_layout=True)
        self.overview_canvas = FigureCanvas(self.overview_fig)
        vl.addWidget(self.overview_canvas, stretch=1)

        self.tabs.addTab(tab, "④ Overview")

    def _build_dendrogram_tab(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        vl.setContentsMargins(4, 4, 4, 4)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("Truncate (last p leaves):"))
        self.dendro_p = QSpinBox()
        self.dendro_p.setRange(0, 50)
        self.dendro_p.setValue(0)
        self.dendro_p.setToolTip("0 = full dendrogram (no truncation)")
        self.dendro_p.setFixedWidth(60)
        hl.addWidget(self.dendro_p)
        hl.addWidget(QLabel("  Color threshold (0 = auto):"))
        self.dendro_thresh = QDoubleSpinBox()
        self.dendro_thresh.setRange(0.0, 100.0)
        self.dendro_thresh.setSingleStep(0.5)
        self.dendro_thresh.setDecimals(2)
        self.dendro_thresh.setValue(0.0)
        self.dendro_thresh.setFixedWidth(70)
        hl.addWidget(self.dendro_thresh)
        redraw_btn = QPushButton("↺ Redraw")
        redraw_btn.setFixedWidth(70)
        redraw_btn.setStyleSheet(
            "QPushButton{background:#475569;color:white;border-radius:3px;"
            "font-size:11px;padding:3px 8px;}"
            "QPushButton:hover{background:#334155;}")
        redraw_btn.clicked.connect(self._draw_dendrogram)
        hl.addWidget(redraw_btn)
        hl.addStretch()
        po = self._make_popout_btn(lambda: self._pop_out_figure('dendro'))
        hl.addWidget(po)
        vl.addLayout(hl)

        self.dendro_fig = Figure(figsize=(14, 7), dpi=110, tight_layout=True)
        self.dendro_canvas = FigureCanvas(self.dendro_fig)
        self.dendro_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.dendro_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, 'dendro'))
        vl.addWidget(self.dendro_canvas, stretch=1)

        self.dendro_tab_idx = self.tabs.addTab(tab, "⑤ Dendrogram")

    # ── 3D Scatter tab ──────────────────────────────────────────────────────

    def _build_3d_tab(self):
        tab = QWidget()
        vl  = QVBoxLayout(tab)
        vl.setContentsMargins(4, 4, 4, 4)

        # ── Toolbar ──────────────────────────────────────────
        hl = QHBoxLayout()

        hl.addWidget(QLabel("Point size:"))
        self.sc3_pt = QSpinBox(); self.sc3_pt.setRange(4, 120)
        self.sc3_pt.setValue(22); self.sc3_pt.setFixedWidth(56)
        self.sc3_pt.valueChanged.connect(self._draw_3d)
        hl.addWidget(self.sc3_pt)

        hl.addWidget(QLabel("  Opacity:"))
        self.sc3_alpha = QDoubleSpinBox()
        self.sc3_alpha.setRange(0.05, 1.0); self.sc3_alpha.setSingleStep(0.05)
        self.sc3_alpha.setDecimals(2); self.sc3_alpha.setValue(0.70)
        self.sc3_alpha.setFixedWidth(60)
        self.sc3_alpha.valueChanged.connect(self._draw_3d)
        hl.addWidget(self.sc3_alpha)

        self.sc3_centroids = QCheckBox("Centroids")
        self.sc3_centroids.setChecked(True)
        self.sc3_centroids.toggled.connect(self._draw_3d)
        hl.addWidget(self.sc3_centroids)

        hl.addSpacing(12)
        for label, elev, azim in [("XY", 90, -90), ("XZ", 0, -90), ("YZ", 0, 0)]:
            btn = QPushButton(label)
            btn.setFixedSize(34, 22)
            btn.setToolTip(f"View from {label} plane")
            btn.setStyleSheet(
                "QPushButton{background:#E2E8F0;border:1px solid #CBD5E1;"
                "border-radius:3px;font-size:10px;font-weight:bold;color:#334155;}"
                "QPushButton:hover{background:#CBD5E1;}")
            btn.clicked.connect(
                lambda _, e=elev, a=azim: self._set_3d_view(e, a))
            hl.addWidget(btn)

        hl.addStretch()
        self._3d_info = QLabel("ℹ Set Dim. Reduction = PCA or t-SNE and Components = 3")
        self._3d_info.setStyleSheet("color:#6B7280;font-size:10px;")
        hl.addWidget(self._3d_info)

        po = self._make_popout_btn(lambda: self._pop_out_figure('3d'))
        hl.addWidget(po)
        vl.addLayout(hl)

        # ── 3D canvas ────────────────────────────────────────
        self._3d_fig    = Figure(figsize=(13, 9), dpi=110)
        self._3d_canvas = FigureCanvas(self._3d_fig)
        self._3d_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self._3d_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, '3d'))
        vl.addWidget(self._3d_canvas, stretch=1)

        self._3d_tab_idx = self.tabs.addTab(tab, "⑥ 3D View")

    def _set_3d_view(self, elev, azim):
        """Snap all 3D axes to a preset view angle.
        Args:
            elev (Any): The elev.
            azim (Any): The azim.
        """
        for ax in self._3d_fig.get_axes():
            ax.view_init(elev=elev, azim=azim)
        self._3d_canvas.draw_idle()

    def _draw_3d(self):
        self._draw_3d_into(self._3d_fig)
        self._3d_canvas.draw()

    def _draw_3d_into(self, target_fig):
        """
        Args:
            target_fig (Any): The target fig.
        """
        target_fig.clear()

        data    = self._data_matrix_cache
        results = self.final_results
        cfg     = self.node.config

        dr = cfg.get('dim_reduction', 'None')

        # ── Guard: need 3-column data ────────────────────────
        if data is None or data.shape[1] < 3 or not results:
            ax = target_fig.add_subplot(111)
            msg = ("No 3D data available.\n\n"
                   "In ⚙ Configure → Preprocessing:\n"
                   "  • Dim. Reduction = PCA  or  t-SNE\n"
                   "  • Components = 3\n\n"
                   "Then re-run ① Evaluate K → ② Cluster.")
            ax.text(0.5, 0.5, msg, ha='center', va='center',
                    fontsize=11, color='#475569', linespacing=1.6,
                    transform=ax.transAxes,
                    bbox=dict(boxstyle='round,pad=0.6', fc='#F8FAFC',
                              ec='#CBD5E1', lw=1))
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_facecolor('#F8FAFC')
            for sp in ax.spines.values():
                sp.set_visible(False)
            target_fig.tight_layout()
            return

        if dr == 'PCA':
            ax_labels = ('PC 1', 'PC 2', 'PC 3')
        elif dr == 't-SNE':
            ax_labels = ('t-SNE 1', 't-SNE 2', 't-SNE 3')
        else:
            ax_labels = ('Feature 1', 'Feature 2', 'Feature 3')

        x, y, z = data[:, 0], data[:, 1], data[:, 2]

        pt_size    = self.sc3_pt.value()
        alpha      = self.sc3_alpha.value()
        show_cent  = self.sc3_centroids.isChecked()
        sample_arr = cfg.get('_sample_arr', None)

        SAMPLE_EDGE = ['#1D4ED8', '#B45309', '#166534', '#7C3AED',
                       '#9F1239', '#0F766E', '#92400E', '#1E40AF']

        fp = make_font_properties(cfg)
        fc = get_font_config(cfg)

        n_algos = len(results)
        cols    = min(2, n_algos)
        rows    = math.ceil(n_algos / cols)

        for idx, (algo_name, result) in enumerate(results.items()):
            ax = target_fig.add_subplot(rows, cols, idx + 1,
                                        projection='3d')
            ax.set_facecolor('#FAFAFA')
            labels_arr  = result.get('labels')
            if labels_arr is None:
                continue

            unique_labs = np.unique(labels_arr)

            for j, lab in enumerate(unique_labs):
                mask = labels_arr == lab
                if lab == -1:
                    ax.scatter(x[mask], y[mask], z[mask],
                               s=10, marker='x', color='#9CA3AF',
                               alpha=0.4, linewidths=0.8,
                               label='Noise', depthshade=True)
                    continue

                color = CLUSTER_COLORS[j % len(CLUSTER_COLORS)]
                ctype = 'Unknown'
                if (algo_name in self.characterisation
                        and lab in self.characterisation[algo_name]):
                    ctype = self.characterisation[algo_name][lab].get(
                        'cluster_type_short',
                        self.characterisation[algo_name][lab].get('cluster_type', 'Unknown'))

                if sample_arr is not None and len(sample_arr) == len(x):
                    unique_samp = np.unique(sample_arr)
                    for si, sname in enumerate(unique_samp):
                        smask = mask & (sample_arr == sname)
                        if smask.any():
                            ec  = SAMPLE_EDGE[si % len(SAMPLE_EDGE)]
                            lbl = (f'C{lab}: {ctype} [{sname}]'
                                   if len(unique_samp) > 1
                                   else f'C{lab}: {ctype}')
                            ax.scatter(x[smask], y[smask], z[smask],
                                       s=pt_size, marker='o', color=color,
                                       alpha=alpha, edgecolors=ec,
                                       linewidths=0.8, label=lbl,
                                       depthshade=True)
                else:
                    ax.scatter(x[mask], y[mask], z[mask],
                               s=pt_size, marker='o', color=color,
                               alpha=alpha, edgecolors='white',
                               linewidths=0.3,
                               label=f'C{lab}: {ctype}',
                               depthshade=True)

                if show_cent:
                    cx, cy, cz = (x[mask].mean(),
                                  y[mask].mean(),
                                  z[mask].mean())
                    ax.scatter(cx, cy, cz, s=120, marker='*',
                               color=color, edgecolors='black',
                               linewidths=0.9, zorder=6,
                               depthshade=False)

            n_cl    = result.get('n_clusters', 0)
            n_noise = result.get('n_noise', 0)
            title   = f'{algo_name}  (K={n_cl}'
            if n_noise:
                title += f', noise={n_noise}'
            title += ')'

            ax.set_title(title, fontproperties=fp, color=fc['color'], pad=8)
            ax.set_xlabel(ax_labels[0], fontsize=max(fc['size'] - 3, 7),
                          color=fc['color'], labelpad=6)
            ax.set_ylabel(ax_labels[1], fontsize=max(fc['size'] - 3, 7),
                          color=fc['color'], labelpad=6)
            ax.set_zlabel(ax_labels[2], fontsize=max(fc['size'] - 3, 7),
                          color=fc['color'], labelpad=6)
            ax.tick_params(labelsize=max(fc['size'] - 4, 6),
                           colors=fc['color'])
            ax.xaxis.pane.fill = False
            ax.yaxis.pane.fill = False
            ax.zaxis.pane.fill = False
            ax.xaxis.pane.set_edgecolor('#E2E8F0')
            ax.yaxis.pane.set_edgecolor('#E2E8F0')
            ax.zaxis.pane.set_edgecolor('#E2E8F0')
            ax.grid(True, alpha=0.2, linewidth=0.4)

            if n_cl <= 8:
                leg = ax.legend(fontsize=max(fc['size'] - 5, 6),
                                loc='upper left', framealpha=0.85,
                                edgecolor='#CBD5E1', markerscale=0.8)
                if leg:
                    leg.get_frame().set_linewidth(0.5)

        self._3d_info.setText(
            f"3D  [{dr}]  —  drag to rotate · scroll to zoom · Shift+drag to pan")
        self._3d_info.setStyleSheet("color:#2563EB;font-size:10px;font-weight:bold;")

        target_fig.tight_layout(pad=1.2)

    def _draw_dendrogram(self):
        self._draw_dendrogram_into(self.dendro_fig)
        self.dendro_canvas.draw()

    def _draw_dendrogram_into(self, target_fig):
        """
        Args:
            target_fig (Any): The target fig.
        """
        target_fig.clear()
        ax = target_fig.add_subplot(111)

        data = self._data_matrix_cache
        if data is None or data.shape[0] < 2:
            ax.text(0.5, 0.5, 'Run ② Cluster first with Hierarchical algorithm',
                    ha='center', va='center', fontsize=12, color='gray',
                    transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([])
            return

        cfg            = self.node.config
        linkage_method = cfg.get('hier_linkage', 'ward')
        metric         = (cfg.get('hier_metric', 'euclidean')
                          if linkage_method != 'ward' else 'euclidean')
        n              = data.shape[0]

        # ── Build linkage matrix ─────────────────────────────────────────────
        try:
            Z = scipy_linkage(
                np.ascontiguousarray(data, dtype=np.float64),
                method=linkage_method,
                metric=metric,
            )
        except Exception as e:
            ax.text(0.5, 0.5, f'Linkage failed:\n{e}',
                    ha='center', va='center', fontsize=10, color='#DC2626',
                    transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([])
            return

        # ── Leaf labels: particle index + cluster id + sample name ───────────
        algo_name = cfg.get('selected_algorithm', 'Hierarchical')
        labels_arr = None
        if algo_name in self.final_results:
            labels_arr = self.final_results[algo_name].get('labels')

        sample_arr = self._particle_samples

        leaf_labels = []
        for i in range(n):
            parts = [str(i)]
            if labels_arr is not None and i < len(labels_arr):
                parts.append(f'C{int(labels_arr[i])}')
            if sample_arr is not None and i < len(sample_arr):
                parts.append(str(sample_arr[i]))
            leaf_labels.append('\n'.join(parts))

        AUTO_TRUNC_THRESHOLD = 200
        p_user = self.dendro_p.value()

        if n > AUTO_TRUNC_THRESHOLD and p_user == 0:
            p_eff        = min(50, n)
            trunc_auto   = True
        else:
            p_eff      = p_user if p_user > 0 else 0
            trunc_auto = False

        use_trunc = (p_eff > 0)

        # ── scipy dendrogram call ────────────────────────────────────────────
        thresh = self.dendro_thresh.value()

        dkw = dict(
            Z=Z,
            ax=ax,
            leaf_rotation=90,
            leaf_font_size=6,
            above_threshold_color='#94A3B8',
        )
        if thresh > 0:
            dkw['color_threshold'] = thresh

        if use_trunc:
            dkw['truncate_mode'] = 'lastp'
            dkw['p']             = p_eff
        else:
            dkw['labels'] = leaf_labels

        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(old_limit, n * 12 + 3000))
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                scipy_dendrogram(**dkw)
        except RecursionError:
            sys.setrecursionlimit(old_limit)
            target_fig.clear()
            ax = target_fig.add_subplot(111)
            dkw2 = {k: v for k, v in dkw.items()
                    if k not in ('labels', 'truncate_mode', 'p')}
            dkw2['truncate_mode'] = 'lastp'
            dkw2['p']             = min(30, n)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                scipy_dendrogram(**dkw2)
        finally:
            sys.setrecursionlimit(old_limit)

        # ── Styling ──────────────────────────────────────────────────────────
        fp  = make_font_properties(cfg)
        fc  = get_font_config(cfg)

        trunc_note = ''
        if use_trunc:
            if trunc_auto:
                trunc_note = f'  [auto-truncated → last {p_eff} leaves, n={n}]'
            else:
                trunc_note = f'  [truncated → last {p_eff} leaves]'

        title = (f"Dendrogram — Hierarchical  "
                 f"[linkage={linkage_method}, metric={metric}]{trunc_note}")
        ax.set_title(title, fontproperties=fp, color=fc['color'], pad=10)
        ax.set_xlabel(
            'Particle index  |  Cluster  |  Sample' if not use_trunc
            else 'Cluster node (count = leaf size)',
            fontproperties=fp, color=fc['color'])
        ax.set_ylabel('Distance', fontproperties=fp, color=fc['color'])
        ax.set_facecolor('#FAFAFA')
        ax.grid(axis='y', alpha=0.25, linewidth=0.5, color='#CBD5E1')
        for spine in ax.spines.values():
            spine.set_color('#CBD5E1')
            spine.set_linewidth(0.8)
        ax.tick_params(labelsize=max(fc['size'] - 4, 6), colors=fc['color'])

        target_fig.tight_layout(pad=1.5)

    def _draw_overview(self):
        """Heatmap (elements × clusters) + cluster size bar chart."""
        self._draw_overview_into(self.overview_fig)
        self.overview_canvas.draw()

    def _draw_overview_into(self, target_fig):
        """Draw the overview content into an arbitrary Figure (used for pop-out).
        Args:
            target_fig (Any): The target fig.
        """
        algo = self.ov_algo.currentText()
        if not algo or algo not in self.characterisation:
            return
        char = self.characterisation[algo]
        elements = self._elements_cache
        clusters = sorted(char.keys())
        if not clusters or not elements:
            return
        freq_matrix = np.zeros((len(elements), len(clusters)))
        for j, cid in enumerate(clusters):
            for i, el in enumerate(elements):
                es = char[cid].get('element_stats', {}).get(el, {})
                freq_matrix[i, j] = es.get('frequency', 0) * 100
        cfg = self.node.config
        target_fig.clear()
        ax1 = target_fig.add_subplot(121)
        show_vals = cfg.get('overview_show_values', True)
        cmap = cfg.get('overview_colormap', 'YlOrRd')
        im = ax1.imshow(freq_matrix, aspect='auto', cmap=cmap,
                        vmin=0, vmax=100, interpolation='nearest')
        ax1.set_xticks(range(len(clusters)))
        ax1.set_xticklabels([f'C{c}' for c in clusters], fontsize=9)
        ax1.set_yticks(range(len(elements)))
        ax1.set_yticklabels(elements, fontsize=8)
        ax1.set_title(f'Detection Frequency (%)  —  {algo}', fontsize=10,
                      fontweight='bold', pad=8)
        if show_vals:
            for i in range(len(elements)):
                for j in range(len(clusters)):
                    v = freq_matrix[i, j]
                    tc = 'white' if v > 60 else '#1E293B'
                    ax1.text(j, i, f'{v:.0f}', ha='center', va='center',
                             fontsize=7, color=tc, fontweight='bold')
        target_fig.colorbar(im, ax=ax1, fraction=0.03, pad=0.02).set_label('Detection %', fontsize=8)
        ax2 = target_fig.add_subplot(122)
        sizes = [char[cid]['particle_count'] for cid in clusters]
        colors_bar = [CLUSTER_COLORS[i % len(CLUSTER_COLORS)] for i in range(len(clusters))]
        bars = ax2.bar([f'C{c}' for c in clusters], sizes, color=colors_bar,
                       edgecolor='white', linewidth=0.6, alpha=0.9)
        for bar, cid, sz in zip(bars, clusters, sizes):
            dom = char[cid].get('dominant_elements', [])
            lbl = format_element_label(dom[0][0], False) if dom else '?'
            ax2.text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() + max(sizes) * 0.01,
                     f'{lbl}\n(n={sz})', ha='center', va='bottom',
                     fontsize=7, color='#1E293B')
        _style_ax(ax2, cfg, xlabel='Cluster', ylabel='Particle count',
                  title='Cluster sizes')
        ax2.set_ylim(0, max(sizes) * 1.25)
        target_fig.tight_layout(pad=1.5)


    def _on_eval_pick(self, event):
        """Click a point on an evaluation curve to set K directly.
        Args:
            event (Any): Qt event object.
        """
        if not hasattr(event, 'ind') or len(event.ind) == 0:
            return
        line = event.artist
        xdata = line.get_xdata()
        idx = event.ind[0]
        k = int(round(float(xdata[idx])))
        combo_idx = self.k_combo.findText(str(k))
        if combo_idx >= 0:
            self.k_combo.setCurrentIndex(combo_idx)
            self.status.setText(
                f"K set to {k} from evaluation curve — click ② Cluster to apply")


    def _on_cluster_hover(self, event):
        """Show a floating tooltip with element values when hovering scatter points.
        Args:
            event (Any): Qt event object.
        """
        if not self.final_results or self._data_matrix_cache is None:
            return

        data = self._data_matrix_cache
        elements = self._elements_cache

        if event.inaxes is None:
            changed = False
            for ann in self._hover_ann.values():
                if ann.get_visible():
                    ann.set_visible(False)
                    changed = True
            if changed:
                self.cluster_canvas.draw_idle()
            return

        ax = event.inaxes
        algo_name = getattr(ax, '_algo_name', None)
        if algo_name is None or algo_name not in self.final_results:
            return

        labels = self.final_results[algo_name]['labels']
        x_ev, y_ev = event.xdata, event.ydata
        if x_ev is None or y_ev is None:
            return

        pts_x = data[:, 0]
        pts_y = data[:, 1] if data.shape[1] > 1 else np.zeros(len(data))

        try:
            xy_disp = ax.transData.transform(
                np.column_stack([pts_x, pts_y]))
            ev_disp = ax.transData.transform([[x_ev, y_ev]])[0]
            dists = np.sqrt(((xy_disp - ev_disp) ** 2).sum(axis=1))
        except Exception:
            return

        nearest = int(np.argmin(dists))
        THRESHOLD_PX = 18

        for other_ax, ann in self._hover_ann.items():
            if other_ax is not ax and ann.get_visible():
                ann.set_visible(False)

        if dists[nearest] > THRESHOLD_PX:
            if ax in self._hover_ann:
                self._hover_ann[ax].set_visible(False)
            self.cluster_canvas.draw_idle()
            return

        cid = int(labels[nearest])
        lines = [f'Particle #{nearest}  |  Cluster {cid}']
        if self._raw_matrix is not None and nearest < len(self._raw_matrix):
            raw = self._raw_matrix[nearest]
            el_vals = [(elements[i], raw[i])
                       for i in range(min(len(elements), len(raw)))
                       if raw[i] > 0]
            el_vals.sort(key=lambda t: t[1], reverse=True)
            for el, v in el_vals[:5]:
                lines.append(f'  {el}: {v:.2f}')
        tip_text = '\n'.join(lines)

        if ax not in self._hover_ann:
            ann = ax.annotate(
                tip_text,
                xy=(pts_x[nearest], pts_y[nearest]),
                xytext=(12, 12), textcoords='offset points',
                fontsize=7.5,
                bbox=dict(boxstyle='round,pad=0.4', fc='#FFFBEB',
                          ec='#D97706', alpha=0.96, lw=0.9),
                arrowprops=dict(arrowstyle='->', color='#D97706', lw=0.9),
                zorder=20,
            )
            self._hover_ann[ax] = ann
        else:
            ann = self._hover_ann[ax]
            ann.set_text(tip_text)
            ann.xy = (pts_x[nearest], pts_y[nearest])

        ann.set_visible(True)
        self.cluster_canvas.draw_idle()


    def _draw_radar(self, algo):
        """Spider/radar chart: detection frequency per element per cluster.
        Args:
            algo (Any): The algo.
        """
        self.radar_fig.clear()

        if not algo or algo not in self.characterisation:
            return

        char = self.characterisation[algo]
        elements = self._elements_cache
        clusters = sorted(char.keys())

        if len(elements) < 3 or not clusters:
            ax = self.radar_fig.add_subplot(111)
            ax.text(0.5, 0.5, 'Need ≥ 3 elements for radar',
                    ha='center', va='center', color='gray', fontsize=10,
                    transform=ax.transAxes)
            self.radar_canvas.draw()
            return

        N = len(elements)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        angles += angles[:1]

        ax = self.radar_fig.add_subplot(111, polar=True)
        ax.set_facecolor('#FAFAFA')
        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(elements, fontsize=7.5)
        ax.set_ylim(0, 100)
        ax.set_yticks([25, 50, 75, 100])
        ax.set_yticklabels(['25', '50', '75', '100%'], fontsize=6, color='#94A3B8')
        ax.grid(color='#CBD5E1', linewidth=0.5, alpha=0.7)
        ax.spines['polar'].set_color('#CBD5E1')

        for i, cid in enumerate(clusters):
            vals = []
            for el in elements:
                es = char[cid].get('element_stats', {}).get(el, {})
                vals.append(es.get('frequency', 0) * 100)
            vals += vals[:1]

            color = CLUSTER_COLORS[i % len(CLUSTER_COLORS)]
            rlw   = self.node.config.get('radar_line_width', 1.8)
            rfa   = self.node.config.get('radar_fill_alpha', 0.12)
            ax.plot(angles, vals, color=color, linewidth=rlw,
                    linestyle='solid', label=f'C{cid}')
            ax.fill(angles, vals, color=color, alpha=rfa)

        ax.set_title('Detection frequency (%)\nper cluster',
                     fontsize=9, fontweight='bold', pad=18, color='#1E293B')
        ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.15),
                  fontsize=7.5, framealpha=0.9)

        self.radar_fig.tight_layout()
        self.radar_canvas.draw()

    def _open_settings(self):
        dlg = ClusteringSettingsDialog(self.node.config, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._data_matrix_cache = None
            self.status.setText("Settings updated — re-run evaluation if needed")

    def _on_node_changed(self):
        self._data_matrix_cache = None


    def _get_elements(self):
        """
        Returns:
            list: Result of the operation.
        """
        if not self.node.input_data:
            return []
        isotopes = self.node.input_data.get('selected_isotopes', [])
        if isotopes:
            labels = [iso['label'] for iso in isotopes]
            return sort_elements_by_mass(labels)
        return []

    def _prepare_data(self, elements):
        """Prepare data matrix — identical logic to original.
        Args:
            elements (Any): The elements.
        Returns:
            object: Result of the operation.
        """
        if not self.node.input_data or not elements:
            return None

        cfg = self.node.config
        dt = cfg.get('data_type_display', 'Counts')
        dk = DATA_KEY_MAP.get(dt, 'elements')
        particles = self.node.input_data.get('particle_data', [])
        if not particles:
            return None

        is_multi = self.node.input_data.get('type') == 'multiple_sample_data'
        sample_names = self.node.input_data.get('sample_names', [])

        matrix = []
        sample_labels = []
        for p in particles:
            d = p.get(dk, {})
            if dt in ('Element Mass %', 'Particle Mass %',
                      'Element Mole %', 'Particle Mole %'):
                if 'Mass %' in dt:
                    total = (sum(d.get(e, 0) for e in elements)
                             if dt == 'Element Mass %'
                             else p.get('particle_mass_fg', 0))
                else:
                    total = (sum(d.get(e, 0) for e in elements)
                             if dt == 'Element Mole %'
                             else p.get('particle_moles_fmol', 0))
                row = [(d.get(e, 0) / total * 100 if total > 0 else 0)
                       for e in elements]
            else:
                row = [d.get(e, 0) for e in elements]
            matrix.append(row)
            sample_labels.append(p.get('source_sample', 'Sample') if is_multi
                                  else 'Sample')

        matrix = np.array(matrix)
        sample_labels = np.array(sample_labels)

        if cfg.get('filter_zeros', True):
            mask = np.any(matrix > 0, axis=1)
            matrix = matrix[mask]
            sample_labels = sample_labels[mask]

        self._raw_matrix = matrix.copy()
        self._particle_samples = sample_labels

        scaling = cfg.get('scaling', 'StandardScaler')
        if scaling == 'StandardScaler':
            matrix = StandardScaler().fit_transform(matrix)
        elif scaling == 'MinMaxScaler':
            matrix = MinMaxScaler().fit_transform(matrix)

        dr = cfg.get('dim_reduction', 'None')
        if dr == 'PCA':
            nc = min(cfg.get('n_components', 2), matrix.shape[1])
            matrix = PCA(n_components=nc).fit_transform(matrix)
        elif dr == 't-SNE':
            nc = min(cfg.get('n_components', 2), 3)
            matrix = TSNE(n_components=nc, random_state=42).fit_transform(matrix)

        return matrix


    def _run_algo(self, name, k, data):
        """
        Args:
            name (Any): Name string.
            k (Any): The k.
            data (Any): Input data.
        Returns:
            None
        """
        cfg = self.node.config
        try:
            if name == 'K-Means':
                return KMeans(
                    n_clusters=k,
                    random_state=42,
                    n_init=cfg.get('kmeans_n_init', 10),
                    max_iter=cfg.get('kmeans_max_iter', 300),
                ).fit_predict(data)

            elif name == 'Hierarchical':
                linkage = cfg.get('hier_linkage', 'ward')
                metric  = cfg.get('hier_metric', 'euclidean') if linkage != 'ward' else 'euclidean'
                return AgglomerativeClustering(
                    n_clusters=k,
                    linkage=linkage,
                    metric=metric,
                ).fit_predict(data)

            elif name == 'Spectral':
                affinity = cfg.get('spectral_affinity', 'rbf')
                kw = dict(n_clusters=k, random_state=42, affinity=affinity)
                if affinity == 'nearest_neighbors':
                    kw['n_neighbors'] = cfg.get('spectral_n_neighbors', 10)
                return SpectralClustering(**kw).fit_predict(data)

            elif name == 'MiniBatch K-Means':
                return MiniBatchKMeans(
                    n_clusters=k,
                    random_state=42,
                    n_init=cfg.get('mbkm_n_init', 3),
                    batch_size=cfg.get('mbkm_batch_size', 1024),
                    max_iter=cfg.get('mbkm_max_iter', 100),
                ).fit_predict(data)

            elif name == 'Birch':
                return Birch(
                    n_clusters=k,
                    threshold=cfg.get('birch_threshold', 0.5),
                    branching_factor=cfg.get('birch_branching_factor', 50),
                ).fit_predict(data)

            elif name == 'DBSCAN':
                return DBSCAN(
                    eps=cfg.get('dbscan_eps', 0.5),
                    min_samples=cfg.get('dbscan_min_samples', 5),
                    metric=cfg.get('dbscan_metric', 'euclidean'),
                ).fit_predict(data)

            elif name == 'Mean Shift':
                bw_kw = {}
                if not cfg.get('meanshift_auto_bw', True):
                    bw_kw['bandwidth'] = cfg.get('meanshift_bandwidth', 1.0)
                return MeanShift(
                    min_bin_freq=cfg.get('meanshift_min_bin_freq', 1),
                    **bw_kw,
                ).fit_predict(data)

            elif name == 'OPTICS':
                return OPTICS(
                    min_samples=cfg.get('optics_min_samples', 5),
                    metric=cfg.get('optics_metric', 'euclidean'),
                    cluster_method=cfg.get('optics_cluster_method', 'xi'),
                ).fit_predict(data)

        except Exception as e:
            print(f"Clustering failed for {name}: {e}")
        return None

    # ── Step 1: Evaluate ────────────────────

    def _run_evaluation(self):
        try:
            self.status.setText("Evaluating cluster numbers…")
            self.progress.setVisible(True)
            self.progress.setValue(0)
            self.eval_btn.setEnabled(False)

            elements = self._get_elements()
            if not elements:
                QMessageBox.warning(self, "Warning", "No elements available.")
                return

            self.progress.setValue(15)
            data = self._prepare_data(elements)
            if data is None or len(data) < 2:
                QMessageBox.warning(self, "Warning", "Insufficient data for clustering.")
                return
            self._data_matrix_cache = data

            self.progress.setValue(30)
            cfg = self.node.config
            enabled_algos = cfg.get('enabled_algorithms',
                                    ['K-Means', 'Hierarchical', 'DBSCAN'])
            enabled_metrics = cfg.get('enabled_metrics',
                                      ['Silhouette', 'Calinski-Harabasz', 'Davies-Bouldin'])
            min_k = cfg.get('min_clusters', 2)
            max_k = cfg.get('max_clusters', 20)

            self.eval_results = {}
            for algo in enabled_algos:
                res = {mk: [] for _, mk in METRIC_KEYS.values()}
                res['k_values'] = []
                ref_labels = None

                for k in range(min_k, max_k + 1):
                    labels = self._run_algo(algo, k, data)
                    if labels is None or len(np.unique(labels)) < 2:
                        continue
                    if ref_labels is None:
                        ref_labels = labels

                    try:
                        if 'Silhouette' in enabled_metrics:
                            res['silhouette_scores'].append(
                                silhouette_score(data, labels))
                        if 'Calinski-Harabasz' in enabled_metrics:
                            res['calinski_harabasz_scores'].append(
                                calinski_harabasz_score(data, labels))
                        if 'Davies-Bouldin' in enabled_metrics:
                            res['davies_bouldin_scores'].append(
                                davies_bouldin_score(data, labels))
                        if 'Adjusted Rand' in enabled_metrics and ref_labels is not None:
                            res['adjusted_rand_scores'].append(
                                adjusted_rand_score(ref_labels, labels))
                        if 'V-Measure' in enabled_metrics and ref_labels is not None:
                            res['v_measure_scores'].append(
                                v_measure_score(ref_labels, labels))
                        if 'Fowlkes-Mallows' in enabled_metrics and ref_labels is not None:
                            res['fowlkes_mallows_scores'].append(
                                fowlkes_mallows_score(ref_labels, labels))
                        res['k_values'].append(k)
                    except Exception:
                        continue

                self.eval_results[algo] = res

            self.progress.setValue(75)
            self._determine_optimal_k()

            self.algo_view.blockSignals(True)
            self.algo_view.clear()
            self.algo_view.addItem('All Algorithms')
            for a in self.eval_results:
                self.algo_view.addItem(a)
            self.algo_view.blockSignals(False)

            all_k = set()
            for r in self.eval_results.values():
                all_k.update(r['k_values'])
            self.k_combo.clear()
            for k in sorted(all_k):
                self.k_combo.addItem(str(k))
            if self.optimal_k:
                self.k_combo.setCurrentText(str(self.optimal_k))
            self.k_combo.setEnabled(True)

            self._refresh_eval_plot()
            self._update_optimal_label()

            self.progress.setValue(100)
            self.cluster_btn.setEnabled(True)
            self.status.setText(
                f"Evaluation complete — Optimal K={self.optimal_k}"
                f" ({self.optimal_algo})" if self.optimal_algo else "")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Evaluation failed:\n{e}")
            self.status.setText("Evaluation failed")
        finally:
            self.progress.setVisible(False)
            self.eval_btn.setEnabled(True)

    def _determine_optimal_k(self):
        """
        Robust optimal-K selection via per-metric voting:
          • Silhouette  → global maximum  (higher = better)
          • Calinski-Harabasz → elbow (kneedle) NOT max — CH always rises with K
          • Davies-Bouldin    → global minimum (lower = better)
        Each metric casts one vote per algorithm. The K with the most votes wins.
        """
        if not self.eval_results:
            return

        k_votes: dict[int, int] = {}

        for algo, res in self.eval_results.items():
            k_vals = res.get('k_values', [])
            if not k_vals:
                continue

            sil = res.get('silhouette_scores', [])
            if sil and len(sil) == len(k_vals):
                best = k_vals[int(np.argmax(sil))]
                k_votes[best] = k_votes.get(best, 0) + 1

            ch = res.get('calinski_harabasz_scores', [])
            if ch and len(ch) == len(k_vals) and len(ch) >= 3:
                best = self._elbow_k(k_vals, ch)
                k_votes[best] = k_votes.get(best, 0) + 1

            db = res.get('davies_bouldin_scores', [])
            if db and len(db) == len(k_vals):
                best = k_vals[int(np.argmin(db))]
                k_votes[best] = k_votes.get(best, 0) + 1

        if not k_votes:
            return

        self.optimal_k = max(k_votes, key=k_votes.get)

        best_a, best_s = None, -1
        for algo, res in self.eval_results.items():
            k_vals = res.get('k_values', [])
            sil = res.get('silhouette_scores', [])
            if self.optimal_k in k_vals and sil:
                idx = k_vals.index(self.optimal_k)
                if idx < len(sil) and sil[idx] > best_s:
                    best_s = sil[idx]
                    best_a = algo
        self.optimal_algo = best_a

    @staticmethod
    def _elbow_k(k_vals: list, scores: list) -> int:
        """
        Kneedle algorithm: find the K at the elbow of a monotone curve.
        Normalises both axes to [0,1] and returns the point furthest from
        the straight line joining the first and last points.
        Args:
            k_vals (list): The k vals.
            scores (list): The scores.
        Returns:
            int: Result of the operation.
        """
        k = np.array(k_vals, dtype=float)
        v = np.array(scores, dtype=float)
        if len(k) < 3:
            return k_vals[0]
        k_n = (k - k.min()) / max(k.max() - k.min(), 1e-10)
        v_n = (v - v.min()) / max(v.max() - v.min(), 1e-10)
        p1, p2 = np.array([k_n[0], v_n[0]]), np.array([k_n[-1], v_n[-1]])
        d = p2 - p1
        dists = np.abs(
            d[1] * k_n - d[0] * v_n + p2[0] * p1[1] - p2[1] * p1[0]
        ) / (np.linalg.norm(d) + 1e-10)
        return k_vals[int(np.argmax(dists))]

    def _update_optimal_label(self):
        if self.optimal_k:
            txt = f"Optimal K: {self.optimal_k}"
            if self.optimal_algo:
                txt += f"  ({self.optimal_algo})"
            self.optimal_label.setText(txt)

    def _refresh_eval_plot(self):
        if not self.eval_results:
            return
        view = self.algo_view.currentText() or 'All Algorithms'
        _draw_evaluation(self.eval_fig, self.eval_results, self.node.config,
                         self.optimal_k, view)
        self.eval_canvas.draw()

    # ── Step 2: Cluster ─────────────────────

    def _run_clustering(self):
        try:
            k_text = self.k_combo.currentText()
            sel_k = int(k_text) if k_text else self.optimal_k
            if not sel_k:
                return

            self.status.setText(f"Clustering with K={sel_k}…")
            self.progress.setVisible(True)
            self.progress.setValue(0)

            elements = self._get_elements()
            data = self._data_matrix_cache
            if data is None:
                data = self._prepare_data(elements)
                self._data_matrix_cache = data
            if data is None:
                return

            self.progress.setValue(30)
            enabled = self.node.config.get('enabled_algorithms',
                                           ['K-Means', 'Hierarchical', 'DBSCAN'])
            self.final_results = {}
            for algo in enabled:
                labels = self._run_algo(algo, sel_k, data)
                if labels is not None:
                    self.final_results[algo] = {
                        'labels': labels,
                        'n_clusters': len(np.unique(labels[labels >= 0])),
                        'n_noise': int(np.sum(labels == -1)),
                    }

            self.progress.setValue(60)
            self._characterise(elements, data)

            self.progress.setValue(85)
            self.node.config['_sample_arr'] = self._particle_samples
            self.node.config['_sample_names'] = (
                list(np.unique(self._particle_samples))
                if self._particle_samples is not None else [])
            _draw_clustering(self.cluster_fig, self.final_results, data,
                             self.characterisation, self.node.config)
            self.cluster_canvas.draw()

            self._hover_ann = {}
            self._elements_cache = elements

            self._populate_char_combos(elements)

            self.ov_algo.blockSignals(True)
            self.ov_algo.clear()
            for a in self.characterisation:
                self.ov_algo.addItem(a)
            if self.optimal_algo and self.optimal_algo in self.characterisation:
                self.ov_algo.setCurrentText(self.optimal_algo)
            self.ov_algo.blockSignals(False)
            self._draw_overview()

            self.export_btn.setEnabled(True)
            self.tabs.setCurrentIndex(1)
            self.progress.setValue(100)
            self.status.setText(f"Clustering complete — K={sel_k}")

            if data.shape[1] >= 3:
                self._draw_3d()

            if (self.node.config.get('selected_algorithm') == 'Hierarchical'
                    and self.node.config.get('hier_show_dendrogram', False)):
                self._draw_dendrogram()
                self.tabs.setCurrentIndex(self.dendro_tab_idx)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Clustering failed:\n{e}")
            self.status.setText("Clustering failed")
        finally:
            self.progress.setVisible(False)


    def _characterise(self, elements, data):
        """Generate cluster characterisation with real element-% composition labels.
        Args:
            elements (Any): The elements.
            data (Any): Input data.
        """
        if not self.final_results:
            return
        self.characterisation = {}
        particles = self.node.input_data.get('particle_data', [])

        if self.node.config.get('filter_zeros', True):
            particles = [p for p in particles
                         if any(p.get('elements', {}).get(e, 0) > 0 for e in elements)]

        for algo, result in self.final_results.items():
            labels = result['labels']
            self.characterisation[algo] = {}

            for cid in np.unique(labels):
                if cid == -1:
                    continue
                mask = labels == cid
                cp = [particles[i] for i in range(min(len(particles), len(mask)))
                      if mask[i]]
                if not cp:
                    continue

                # ── Per-element stats ─────────────────────────────────────
                estats = {}
                for el in elements:
                    vals = [p.get('elements', {}).get(el, 0) for p in cp]
                    nonzero = [v for v in vals if v > 0]
                    if nonzero:
                        estats[el] = {
                            'mean': np.mean(nonzero),
                            'median': np.median(nonzero),
                            'std': np.std(nonzero),
                            'count': len(nonzero),
                            'total_particles': len(cp),
                            'frequency': len(nonzero) / len(cp),
                        }
                    else:
                        estats[el] = {
                            'mean': 0, 'median': 0, 'std': 0, 'count': 0,
                            'total_particles': len(cp), 'frequency': 0,
                        }

                # ── Composition label based on mean-signal % ──────────────
                means_all = {}
                for el in elements:
                    all_vals = [p.get('elements', {}).get(el, 0) for p in cp]
                    means_all[el] = np.mean(all_vals)

                total_mean = sum(means_all.values())
                if total_mean > 0:
                    pcts = {e: (v / total_mean * 100)
                            for e, v in means_all.items()}
                else:
                    pcts = {e: 0.0 for e in elements}

                sig = sorted(
                    [(e, p) for e, p in pcts.items() if p > 0.1],
                    key=lambda t: t[1], reverse=True,
                )

                if sig:
                    ctype_full = '  '.join(
                        f"{format_element_label(e, False)} {p:.1f}%"
                        for e, p in sig
                    )
                else:
                    ctype_full = 'No signal'

                if sig:
                    ctype_short = '+'.join(
                        format_element_label(e, False) for e, _ in sig[:4]
                    )
                    if len(sig) > 4:
                        ctype_short += f'+{len(sig)-4}…'
                else:
                    ctype_short = 'No signal'

                dom = [(e, p / 100) for e, p in sig[:3]]

                self.characterisation[algo][cid] = {
                    'element_stats':    estats,
                    'element_pcts':     pcts,
                    'composition':      sig,
                    'dominant_elements': dom,
                    'cluster_type':     ctype_full,
                    'cluster_type_short': ctype_short,
                    'particle_count':   len(cp),
                }

    def _populate_char_combos(self, elements):
        """
        Args:
            elements (Any): The elements.
        """
        self.char_algo.blockSignals(True)
        self.char_elem.blockSignals(True)
        self.char_algo.clear()
        self.char_elem.clear()
        for a in self.characterisation:
            self.char_algo.addItem(a)
        if self.optimal_algo and self.optimal_algo in self.characterisation:
            self.char_algo.setCurrentText(self.optimal_algo)
        for e in elements:
            self.char_elem.addItem(e)
        self.char_algo.blockSignals(False)
        self.char_elem.blockSignals(False)
        self._refresh_char()

    def _refresh_char(self):
        algo = self.char_algo.currentText()
        elem = self.char_elem.currentText()
        if not algo or not elem or algo not in self.characterisation:
            return

        char = self.characterisation[algo]
        clusters = sorted(char.keys())

        # ── Table — 8 columns now ────────────────────────────────────────────
        self.char_table.setRowCount(len(clusters))
        self.char_table.setColumnCount(8)
        self.char_table.setHorizontalHeaderLabels([
            'Cluster', 'Composition (>0.1%)', 'n Particles',
            f'{elem} Mean', f'{elem} Median', f'{elem} Std',
            f'{elem} Freq %', f'{elem} Contr. %',
        ])

        for i, cid in enumerate(clusters):
            cd  = char[cid]
            es  = cd.get('element_stats', {}).get(elem, {})
            pct = cd.get('element_pcts', {}).get(elem, 0.0)

            comp_item = QTableWidgetItem(cd.get('cluster_type', ''))
            if pct >= 50:
                comp_item.setBackground(QColor('#DCFCE7'))
            elif pct >= 10:
                comp_item.setBackground(QColor('#FEF9C3'))
            elif pct >= 0.1:
                comp_item.setBackground(QColor('#F1F5F9'))

            self.char_table.setItem(i, 0, QTableWidgetItem(str(cid)))
            self.char_table.setItem(i, 1, comp_item)
            self.char_table.setItem(i, 2, QTableWidgetItem(str(cd['particle_count'])))
            self.char_table.setItem(i, 3, QTableWidgetItem(f"{es.get('mean', 0):.3g}"))
            self.char_table.setItem(i, 4, QTableWidgetItem(f"{es.get('median', 0):.3g}"))
            self.char_table.setItem(i, 5, QTableWidgetItem(f"{es.get('std', 0):.3g}"))
            self.char_table.setItem(i, 6, QTableWidgetItem(
                f"{es.get('frequency', 0) * 100:.1f}%"))
            pct_item = QTableWidgetItem(f"{pct:.2f}%")
            if pct >= 0.1:
                pct_item.setForeground(QColor('#16A34A'))
            self.char_table.setItem(i, 7, pct_item)

        self.char_table.resizeColumnsToContents()

        # ── Plot ─────────────────────────────────────────────────────────────
        _draw_characterisation(self.char_fig, algo, elem, self.characterisation,
                               self.node.config)
        self.char_canvas.draw()
        self._draw_radar(algo)

    # ── Export ──────────────────────────────

    def _export_results(self):
        from PySide6.QtWidgets import QFileDialog
        import json

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "clustering_analysis.json",
            "JSON (*.json);;All Files (*)")
        if not path:
            return
        try:
            export = {
                'configuration': self.node.config,
                'optimal_k': self.optimal_k,
                'optimal_algorithm': self.optimal_algo,
                'evaluation_results': self.eval_results,
                'cluster_characterisation': {},
            }
            for algo, clusters in self.characterisation.items():
                export['cluster_characterisation'][algo] = {}
                for cid, cd in clusters.items():
                    export['cluster_characterisation'][algo][str(cid)] = {
                        'cluster_type': cd['cluster_type'],
                        'particle_count': cd['particle_count'],
                        'dominant_elements': cd['dominant_elements'],
                    }
            with open(path, 'w') as f:
                json.dump(export, f, indent=2, default=str)
            QMessageBox.information(self, "Success", f"Exported to: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed: {e}")


class ClusteringPlotNode(QObject):
    """Clustering analysis node with matplotlib figures."""

    position_changed = Signal(object)
    configuration_changed = Signal()

    DEFAULT_CONFIG = {
        'data_type_display': 'Counts',
        'scaling': 'StandardScaler',
        'dim_reduction': 'None',
        'n_components': 2,
        'filter_zeros': True,
        'selected_algorithm': 'K-Means',
        'enabled_algorithms': ['K-Means'],
        'kmeans_n_init': 10,
        'kmeans_max_iter': 300,
        'hier_linkage': 'ward',
        'hier_metric': 'euclidean',
        'hier_show_dendrogram': False,
        'dbscan_eps': 0.5,
        'dbscan_min_samples': 5,
        'dbscan_metric': 'euclidean',
        'spectral_n_neighbors': 10,
        'spectral_affinity': 'rbf',
        'mbkm_n_init': 3,
        'mbkm_batch_size': 1024,
        'mbkm_max_iter': 100,
        'birch_threshold': 0.5,
        'birch_branching_factor': 50,
        'meanshift_auto_bw': True,
        'meanshift_bandwidth': 1.0,
        'meanshift_min_bin_freq': 1,
        'optics_min_samples': 5,
        'optics_metric': 'euclidean',
        'optics_cluster_method': 'xi',
        'min_clusters': 2,
        'max_clusters': 20,
        'auto_select_k': True,
        'enabled_metrics': ['Silhouette', 'Calinski-Harabasz', 'Davies-Bouldin'],
        'font_family': 'Times New Roman',
        'font_size': 12,
        'font_bold': False,
        'font_italic': False,
        'font_color': '#000000',
    }

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
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
        self.config = dict(self.DEFAULT_CONFIG)
        self.input_data = None
        self.plot_widget = None

    def set_position(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        """
        Args:
            parent_window (Any): The parent window.
        Returns:
            bool: Result of the operation.
        """
        dlg = ClusteringDisplayDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
        """
        Args:
            input_data (Any): The input data.
        """
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()