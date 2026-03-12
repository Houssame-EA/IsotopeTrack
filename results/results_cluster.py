
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QPushButton,
    QFrame, QScrollArea, QWidget, QMenu, QTabWidget, QToolBar,
    QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QSlider, QLineEdit, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QCursor, QAction
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import math
import gc
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


# ═══════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════

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

# Professional cluster palette — distinct, colourblind-safe
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


# ═══════════════════════════════════════════════
# Settings Dialog
# ═══════════════════════════════════════════════

class ClusteringSettingsDialog(QDialog):
    """Full settings dialog opened from right-click → Configure."""

    def __init__(self, config, parent=None):
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

        # Data type
        g = QGroupBox("Data Type")
        fl = QFormLayout(g)
        self.data_type = QComboBox()
        self.data_type.addItems(DATA_TYPE_OPTIONS)
        self.data_type.setCurrentText(self._cfg.get('data_type_display', 'Counts'))
        fl.addRow("Data:", self.data_type)
        layout.addWidget(g)

        # Preprocessing
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

        # Algorithms
        g = QGroupBox("Algorithms")
        vl = QVBoxLayout(g)
        enabled = self._cfg.get('enabled_algorithms', ['K-Means', 'Hierarchical', 'DBSCAN'])
        self.algo_cbs = {}
        for a in ALGORITHMS:
            cb = QCheckBox(a)
            cb.setChecked(a in enabled)
            self.algo_cbs[a] = cb
            vl.addWidget(cb)

        fl2 = QFormLayout()
        w = QWidget()
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        self.eps = QDoubleSpinBox()
        self.eps.setRange(0.01, 20.0)
        self.eps.setSingleStep(0.1)
        self.eps.setValue(self._cfg.get('dbscan_eps', 0.5))
        self.eps.setMaximumWidth(70)
        self.min_samp = QSpinBox()
        self.min_samp.setRange(2, 50)
        self.min_samp.setValue(self._cfg.get('dbscan_min_samples', 5))
        self.min_samp.setMaximumWidth(55)
        hl.addWidget(QLabel("eps:"))
        hl.addWidget(self.eps)
        hl.addWidget(QLabel("min_samples:"))
        hl.addWidget(self.min_samp)
        hl.addStretch()
        fl2.addRow("DBSCAN/OPTICS:", w)

        self.linkage = QComboBox()
        self.linkage.addItems(['ward', 'complete', 'average', 'single'])
        self.linkage.setCurrentText(self._cfg.get('hier_linkage', 'ward'))
        fl2.addRow("Linkage:", self.linkage)
        vl.addLayout(fl2)
        layout.addWidget(g)

        # Evaluation
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

        # Font
        self._font_grp = FontSettingsGroup(self._cfg)
        layout.addWidget(self._font_grp.build())

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def collect(self) -> dict:
        out = dict(self._cfg)
        out['data_type_display'] = self.data_type.currentText()
        out['scaling'] = self.scaling.currentText()
        out['dim_reduction'] = self.dim_red.currentText()
        out['n_components'] = self.n_comp.value()
        out['filter_zeros'] = self.filter_zeros.isChecked()
        out['enabled_algorithms'] = [a for a, cb in self.algo_cbs.items() if cb.isChecked()]
        out['dbscan_eps'] = self.eps.value()
        out['dbscan_min_samples'] = self.min_samp.value()
        out['hier_linkage'] = self.linkage.currentText()
        out['min_clusters'] = self.min_k.value()
        out['max_clusters'] = self.max_k.value()
        out['auto_select_k'] = self.auto_k.isChecked()
        out['enabled_metrics'] = [m for m, cb in self.metric_cbs.items() if cb.isChecked()]
        out.update(self._font_grp.collect())
        return out


# ═══════════════════════════════════════════════
# Matplotlib plot helpers
# ═══════════════════════════════════════════════

def _style_ax(ax, cfg, xlabel='', ylabel='', title=''):
    """Apply consistent styling to a matplotlib axes."""
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
    """Draw evaluation metric curves on a matplotlib Figure."""
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
                    marker=style['marker'], markersize=5, linewidth=1.8,
                    label=algo_name, alpha=0.85)

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

    # Hide unused subplots
    total = rows * cols
    for j in range(n, total):
        fig.add_subplot(rows, cols, j + 1).set_visible(False)

    fig.tight_layout(pad=1.5)


def _draw_clustering(fig, clustering_results, data_matrix, characterisation, cfg):
    """Draw cluster scatter plots on a matplotlib Figure."""
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
                        'cluster_type', 'Unknown')

                ax.scatter(x[mask], y[mask], s=18, marker='o',
                           color=color, alpha=0.65, edgecolors='white',
                           linewidths=0.3, label=f'C{lab}: {ctype}',
                           zorder=3)

                # Centroid marker
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

        # Legend only if manageable
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
    """Draw cluster characterisation bar chart on a matplotlib Figure."""
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

    labels_x = []
    means = []
    medians = []
    freqs = []
    types = []
    counts = []

    for cid in cluster_ids:
        cd = data[cid]
        es = cd.get('element_stats', {}).get(element, {})
        labels_x.append(f'C{cid}')
        means.append(es.get('mean', 0))
        medians.append(es.get('median', 0))
        freqs.append(es.get('frequency', 0) * 100)
        types.append(cd.get('cluster_type', ''))
        counts.append(cd.get('particle_count', 0))

    x = np.arange(len(labels_x))
    w = 0.28

    fp = make_font_properties(cfg)
    fc = get_font_config(cfg)

    # Two-axis plot: bars for mean/median, line for frequency
    ax1 = fig.add_subplot(111)
    ax2 = ax1.twinx()

    bars_mean = ax1.bar(x - w / 2, means, w, color='#2563EB', alpha=0.8,
                        edgecolor='white', linewidth=0.5, label='Mean')
    bars_med = ax1.bar(x + w / 2, medians, w, color='#7C3AED', alpha=0.8,
                       edgecolor='white', linewidth=0.5, label='Median')

    ax2.plot(x, freqs, color='#DC2626', marker='D', markersize=6,
             linewidth=2, label='Detection %', zorder=5)

    # Particle count annotations
    for i, (c, m) in enumerate(zip(counts, means)):
        ax1.annotate(f'n={c}', (x[i], m), textcoords='offset points',
                     xytext=(0, 5), ha='center', fontsize=max(fc['size'] - 4, 7),
                     color='#475569')

    # X labels with cluster type
    xtick_labels = [f'{lbl}\n{t}' for lbl, t in zip(labels_x, types)]
    ax1.set_xticks(x)
    ax1.set_xticklabels(xtick_labels, fontproperties=fp, color=fc['color'],
                        fontsize=max(fc['size'] - 3, 7))

    _style_ax(ax1, cfg, xlabel='',
              ylabel=f'{element}  (value)',
              title=f'{element} Distribution — {algo_name}')

    ax2.set_ylabel('Detection Frequency (%)', fontproperties=fp, color='#DC2626')
    ax2.tick_params(axis='y', labelcolor='#DC2626',
                    labelsize=max(fc['size'] - 3, 7))
    ax2.set_ylim(0, 110)
    ax2.spines['right'].set_color('#DC2626')

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    leg = ax1.legend(lines1 + lines2, labels1 + labels2,
                     loc='upper right', fontsize=max(fc['size'] - 4, 7),
                     framealpha=0.9, edgecolor='#CBD5E1')
    if leg:
        leg.get_frame().set_linewidth(0.5)

    fig.tight_layout(pad=1.5)


# ═══════════════════════════════════════════════
# Display Dialog
# ═══════════════════════════════════════════════

class ClusteringDisplayDialog(QDialog):
    """
    Main clustering dialog with toolbar, tabs, and right-click menus.
    """

    def __init__(self, node, parent_window=None):
        super().__init__(parent_window)
        self.node = node
        self.parent_window = parent_window
        self.setWindowTitle("Clustering Analysis")
        self.setMinimumSize(1200, 800)

        # State
        self.eval_results = {}
        self.final_results = {}
        self.characterisation = {}
        self.optimal_k = None
        self.optimal_algo = None
        self._data_matrix_cache = None

        self._build_ui()
        self.node.configuration_changed.connect(self._on_node_changed)

    def _is_multi(self):
        return (self.node.input_data and
                self.node.input_data.get('type') == 'multiple_sample_data')

    # ── UI ──────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Top toolbar with workflow buttons
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

        # K selector
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

        # Progress
        self.progress = QProgressBar()
        self.progress.setFixedWidth(120)
        self.progress.setFixedHeight(16)
        self.progress.setVisible(False)
        tl.addWidget(self.progress)

        layout.addWidget(toolbar)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab { padding: 6px 18px; font-size: 12px; }
            QTabBar::tab:selected { font-weight: bold; }
        """)

        self._build_eval_tab()
        self._build_cluster_tab()
        self._build_char_tab()

        layout.addWidget(self.tabs)

        # Status bar
        self.status = QLabel("Ready — connect data and run evaluation")
        self.status.setStyleSheet(
            "color: #6B7280; font-size: 11px; padding: 2px 8px; "
            "background: #F8FAFC; border-top: 1px solid #E2E8F0;")
        layout.addWidget(self.status)

    def _make_btn(self, text, color, slot):
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
        vl.addLayout(hl)

        self.eval_fig = Figure(figsize=(12, 8), dpi=120, tight_layout=True)
        self.eval_canvas = FigureCanvas(self.eval_fig)
        self.eval_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.eval_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, 'eval'))
        vl.addWidget(self.eval_canvas, stretch=1)

        self.eval_summary = QLabel("Run evaluation to see results")
        self.eval_summary.setStyleSheet(
            "padding: 8px; background: #F8FAFC; border: 1px solid #E2E8F0; "
            "border-radius: 4px; font-family: monospace; font-size: 11px;")
        self.eval_summary.setWordWrap(True)
        self.eval_summary.setMaximumHeight(140)
        vl.addWidget(self.eval_summary)

        self.tabs.addTab(tab, "① Evaluation")

    # ── Clustering tab ──────────────────────

    def _build_cluster_tab(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        vl.setContentsMargins(4, 4, 4, 4)

        self.cluster_fig = Figure(figsize=(14, 9), dpi=120, tight_layout=True)
        self.cluster_canvas = FigureCanvas(self.cluster_fig)
        self.cluster_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.cluster_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, 'cluster'))
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
        vl.addLayout(hl)

        self.char_table = QTableWidget()
        self.char_table.setAlternatingRowColors(True)
        self.char_table.setMaximumHeight(200)
        self.char_table.setStyleSheet(
            "QTableWidget { font-size: 11px; gridline-color: #E2E8F0; }"
            "QHeaderView::section { background: #F1F5F9; font-weight: bold; "
            "border: 1px solid #E2E8F0; padding: 4px; }")
        vl.addWidget(self.char_table)

        self.char_fig = Figure(figsize=(12, 6), dpi=120, tight_layout=True)
        self.char_canvas = FigureCanvas(self.char_fig)
        self.char_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.char_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, 'char'))
        vl.addWidget(self.char_canvas, stretch=1)

        self.tabs.addTab(tab, "③ Characterisation")

    # ── Context menu ────────────────────────

    def _ctx_menu(self, pos, tab):
        menu = QMenu(self)

        # Data type
        dt_menu = menu.addMenu("Data Type")
        cur = self.node.config.get('data_type_display', 'Counts')
        for dt in DATA_TYPE_OPTIONS:
            a = dt_menu.addAction(dt)
            a.setCheckable(True)
            a.setChecked(dt == cur)
            a.triggered.connect(lambda _, d=dt: self._set('data_type_display', d))

        menu.addSeparator()
        cfg_action = menu.addAction("⚙  Configure…")
        cfg_action.triggered.connect(self._open_settings)

        # Download appropriate figure
        fig_map = {'eval': self.eval_fig, 'cluster': self.cluster_fig,
                   'char': self.char_fig}
        names = {'eval': 'evaluation.png', 'cluster': 'clusters.png',
                 'char': 'characterisation.png'}
        dl = menu.addAction("💾 Download Figure…")
        dl.triggered.connect(
            lambda: download_matplotlib_figure(fig_map[tab], self, names[tab]))

        menu.exec(QCursor.pos())

    def _set(self, key, value):
        self.node.config[key] = value
        self._data_matrix_cache = None
        self.status.setText(f"Changed {key} → re-run evaluation for updated results")

    def _open_settings(self):
        dlg = ClusteringSettingsDialog(self.node.config, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._data_matrix_cache = None
            self.status.setText("Settings updated — re-run evaluation if needed")

    def _on_node_changed(self):
        self._data_matrix_cache = None

    # ── Data preparation (identical logic) ──

    def _get_elements(self):
        if not self.node.input_data:
            return []
        isotopes = self.node.input_data.get('selected_isotopes', [])
        if isotopes:
            labels = [iso['label'] for iso in isotopes]
            return sort_elements_by_mass(labels)
        return []

    def _prepare_data(self, elements):
        """Prepare data matrix — identical logic to original."""
        if not self.node.input_data or not elements:
            return None

        cfg = self.node.config
        dt = cfg.get('data_type_display', 'Counts')
        dk = DATA_KEY_MAP.get(dt, 'elements')
        particles = self.node.input_data.get('particle_data', [])
        if not particles:
            return None

        matrix = []
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

        matrix = np.array(matrix)

        if cfg.get('filter_zeros', True):
            mask = np.any(matrix > 0, axis=1)
            matrix = matrix[mask]

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

    # ── Single clustering (identical logic) ─

    def _run_algo(self, name, k, data):
        cfg = self.node.config
        try:
            if name == 'K-Means':
                return KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(data)
            elif name == 'Hierarchical':
                lnk = cfg.get('hier_linkage', 'ward')
                return AgglomerativeClustering(n_clusters=k, linkage=lnk).fit_predict(data)
            elif name == 'Spectral':
                return SpectralClustering(n_clusters=k, random_state=42).fit_predict(data)
            elif name == 'MiniBatch K-Means':
                return MiniBatchKMeans(n_clusters=k, random_state=42).fit_predict(data)
            elif name == 'Birch':
                return Birch(n_clusters=k).fit_predict(data)
            elif name == 'DBSCAN':
                return DBSCAN(eps=cfg.get('dbscan_eps', 0.5),
                              min_samples=cfg.get('dbscan_min_samples', 5)).fit_predict(data)
            elif name == 'Mean Shift':
                return MeanShift().fit_predict(data)
            elif name == 'OPTICS':
                return OPTICS(min_samples=cfg.get('dbscan_min_samples', 5)).fit_predict(data)
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

            # Update algo view combo
            self.algo_view.blockSignals(True)
            self.algo_view.clear()
            self.algo_view.addItem('All Algorithms')
            for a in self.eval_results:
                self.algo_view.addItem(a)
            self.algo_view.blockSignals(False)

            # Update K combo
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
            self._update_eval_summary()
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
        """Auto-determine optimal K (identical logic to original)."""
        if not self.eval_results:
            return
        combined = {}
        for algo, res in self.eval_results.items():
            for i, k in enumerate(res['k_values']):
                if k not in combined:
                    combined[k] = {'score': 0, 'n': 0}
                s, n = 0, 0
                if i < len(res['silhouette_scores']):
                    s += res['silhouette_scores'][i]; n += 1
                if i < len(res['calinski_harabasz_scores']):
                    ch = res['calinski_harabasz_scores']
                    if max(ch) > min(ch):
                        s += (ch[i] - min(ch)) / (max(ch) - min(ch)); n += 1
                if i < len(res['davies_bouldin_scores']):
                    db = res['davies_bouldin_scores']
                    if max(db) > min(db):
                        s += 1 - (db[i] - min(db)) / (max(db) - min(db)); n += 1
                if n > 0:
                    combined[k]['score'] += s / n
                    combined[k]['n'] += 1

        avg = {k: d['score'] / d['n'] for k, d in combined.items() if d['n'] > 0}
        if avg:
            self.optimal_k = max(avg, key=avg.get)
            best_a, best_s = None, -1
            for algo, res in self.eval_results.items():
                if self.optimal_k in res['k_values']:
                    idx = res['k_values'].index(self.optimal_k)
                    if idx < len(res['silhouette_scores']):
                        if res['silhouette_scores'][idx] > best_s:
                            best_s = res['silhouette_scores'][idx]
                            best_a = algo
            self.optimal_algo = best_a

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

    def _update_eval_summary(self):
        if not self.eval_results:
            return
        lines = ["EVALUATION SUMMARY", "=" * 50, ""]
        for algo, res in self.eval_results.items():
            lines.append(f"▸ {algo}:")
            if res['k_values']:
                lines.append(f"   K range: {min(res['k_values'])}–{max(res['k_values'])}")
            if res['silhouette_scores']:
                bi = np.argmax(res['silhouette_scores'])
                lines.append(
                    f"   Best Silhouette: K={res['k_values'][bi]}  "
                    f"({res['silhouette_scores'][bi]:.3f})")
            if res['calinski_harabasz_scores']:
                bi = np.argmax(res['calinski_harabasz_scores'])
                lines.append(
                    f"   Best CH Index:   K={res['k_values'][bi]}  "
                    f"({res['calinski_harabasz_scores'][bi]:.1f})")
            if res['davies_bouldin_scores']:
                bi = np.argmin(res['davies_bouldin_scores'])
                lines.append(
                    f"   Best DB Index:   K={res['k_values'][bi]}  "
                    f"({res['davies_bouldin_scores'][bi]:.3f})")
            lines.append("")

        if self.optimal_k:
            lines.append(f"✦ RECOMMENDED: K = {self.optimal_k}"
                         + (f"  using {self.optimal_algo}" if self.optimal_algo else ""))
        self.eval_summary.setText("\n".join(lines))

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
            _draw_clustering(self.cluster_fig, self.final_results, data,
                             self.characterisation, self.node.config)
            self.cluster_canvas.draw()

            self._populate_char_combos(elements)

            self.export_btn.setEnabled(True)
            self.tabs.setCurrentIndex(1)
            self.progress.setValue(100)
            self.status.setText(f"Clustering complete — K={sel_k}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Clustering failed:\n{e}")
            self.status.setText("Clustering failed")
        finally:
            self.progress.setVisible(False)

    # ── Characterisation (identical logic) ──

    def _characterise(self, elements, data):
        """Generate cluster characterisation — identical logic to original."""
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

                estats = {}
                for el in elements:
                    vals = [p.get('elements', {}).get(el, 0) for p in cp]
                    vals = [v for v in vals if v > 0]
                    if vals:
                        estats[el] = {
                            'mean': np.mean(vals), 'median': np.median(vals),
                            'std': np.std(vals), 'count': len(vals),
                            'total_particles': len(cp),
                            'frequency': len(vals) / len(cp),
                        }
                    else:
                        estats[el] = {
                            'mean': 0, 'median': 0, 'std': 0, 'count': 0,
                            'total_particles': len(cp), 'frequency': 0,
                        }

                freqs = {e: s['frequency'] for e, s in estats.items()}
                dom = sorted(freqs.items(), key=lambda x: x[1], reverse=True)[:3]
                ctype = "Mixed"
                if dom and dom[0][1] > 0.7:
                    ctype = f"{format_element_label(dom[0][0], False)}-dominant"
                elif len(dom) >= 2 and dom[1][1] > 0.3:
                    ctype = (f"{format_element_label(dom[0][0], False)}-"
                             f"{format_element_label(dom[1][0], False)} rich")

                self.characterisation[algo][cid] = {
                    'element_stats': estats, 'dominant_elements': dom,
                    'cluster_type': ctype, 'particle_count': len(cp),
                }

    def _populate_char_combos(self, elements):
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

        # Table
        self.char_table.setRowCount(len(clusters))
        self.char_table.setColumnCount(7)
        self.char_table.setHorizontalHeaderLabels(
            ['Cluster', 'Type', 'Particles', 'Mean', 'Median', 'Std Dev', 'Freq %'])

        for i, cid in enumerate(clusters):
            cd = char[cid]
            es = cd.get('element_stats', {}).get(elem, {})
            self.char_table.setItem(i, 0, QTableWidgetItem(str(cid)))
            self.char_table.setItem(i, 1, QTableWidgetItem(cd['cluster_type']))
            self.char_table.setItem(i, 2, QTableWidgetItem(str(cd['particle_count'])))
            self.char_table.setItem(i, 3, QTableWidgetItem(f"{es.get('mean', 0):.2f}"))
            self.char_table.setItem(i, 4, QTableWidgetItem(f"{es.get('median', 0):.2f}"))
            self.char_table.setItem(i, 5, QTableWidgetItem(f"{es.get('std', 0):.2f}"))
            self.char_table.setItem(i, 6, QTableWidgetItem(
                f"{es.get('frequency', 0) * 100:.1f}%"))

        self.char_table.resizeColumnsToContents()

        # Plot
        _draw_characterisation(self.char_fig, algo, elem, self.characterisation,
                               self.node.config)
        self.char_canvas.draw()

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


# ═══════════════════════════════════════════════
# Node
# ═══════════════════════════════════════════════

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
        'enabled_algorithms': ['K-Means', 'Hierarchical', 'DBSCAN'],
        'dbscan_eps': 0.5,
        'dbscan_min_samples': 5,
        'hier_linkage': 'ward',
        'min_clusters': 2,
        'max_clusters': 20,
        'auto_select_k': True,
        'enabled_metrics': ['Silhouette', 'Calinski-Harabasz', 'Davies-Bouldin'],
        # Font
        'font_family': 'Times New Roman',
        'font_size': 12,
        'font_bold': False,
        'font_italic': False,
        'font_color': '#000000',
    }

    def __init__(self, parent_window=None):
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
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        dlg = ClusteringDisplayDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()