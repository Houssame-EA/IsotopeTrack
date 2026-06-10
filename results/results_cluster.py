from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QPushButton,
    QFrame, QScrollArea, QWidget, QMenu, QTabWidget,
    QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QStackedWidget, QSlider,
)
from PySide6.QtCore import Qt, Signal, QObject, QThread, QTimer
from PySide6.QtGui import QColor, QCursor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import math
import sys
import warnings
warnings.filterwarnings('ignore')

from sklearn.cluster import (
    KMeans, DBSCAN, AgglomerativeClustering, SpectralClustering,
    MeanShift, OPTICS, MiniBatchKMeans, Birch,
)
from sklearn.mixture import GaussianMixture
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE

try:
    from sklearn.cluster import HDBSCAN as _HDBSCAN_CLS
    _HDBSCAN_OK = True
except ImportError:
    try:
        import hdbscan as _hm
        _HDBSCAN_CLS = _hm.HDBSCAN
        _HDBSCAN_OK = True
    except ImportError:
        _HDBSCAN_CLS = None
        _HDBSCAN_OK = False
from sklearn.metrics import (
    silhouette_score, calinski_harabasz_score, davies_bouldin_score,
)

from scipy.cluster.hierarchy import (
    dendrogram as scipy_dendrogram,
    linkage as scipy_linkage,
    fcluster as scipy_fcluster,
)

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS,
    get_font_config, make_font_properties,
    apply_font_to_matplotlib, apply_font_to_colorbar_standalone,
    FontSettingsGroup,
    download_matplotlib_figure,
    format_element_label, Renderer,
    per_ml_active, per_ml_factor, conc_meta_available, format_per_ml,
)
from results.utils_sort import (
    extract_mass_and_element, sort_elements_by_mass,
)
from results.results_heatmap import draw_combinations_heatmap


class _SafeFigureCanvas(FigureCanvas):
    """FigureCanvas subclass that suppresses the PySide6 installEventFilter crash.

    In certain PySide6 + matplotlib combinations, FigureCanvas.showEvent calls
    self.window().installEventFilter(self) but window() returns a QWidgetItem
    (a layout item) rather than a real QWidget, causing an AttributeError that
    crashes the dialog on first show.
    """

    def showEvent(self, event):
        """
        Args:
            event (QShowEvent): The show event forwarded by Qt.
        """
        try:
            super().showEvent(event)
        except AttributeError:
            pass

    def resizeEvent(self, event):
        """
        Args:
            event (QResizeEvent): The resize event forwarded by Qt.
        """
        try:
            super().resizeEvent(event)
        except AttributeError:
            pass


ALGORITHMS = [
    'K-Means', 'Hierarchical', 'DBSCAN', 'HDBSCAN', 'Spectral', 'SOM',
    'MiniBatch K-Means', 'Mean Shift', 'Birch', 'OPTICS', 'Gaussian Mixture',
]

def _cluster_centroids(data, labels, valid_labels):
    """Compute per-cluster centroids as the arithmetic mean of member points.

    Centroid-based cluster validity indices (Xie-Beni, PBM, S_Dbw, …) are
    originally defined for prototype-based partitions such as K-Means or fuzzy
    c-means, where a centroid is intrinsic to the model. For density- and
    connectivity-based partitions (DBSCAN, HDBSCAN, Spectral, Agglomerative)
    no centroid exists by construction, so the conventional remedy adopted by
    cluster-validation toolboxes is to substitute the empirical mean of each
    cluster's members. This is the convention used in the CVIK toolbox
    (José-García & Gómez-Flores, *SoftwareX* 22, 2023, 101359) and in the
    relative-validity review of Vendramin, Campello & Hruschka
    (*Stat. Anal. Data Min.* 3(4), 2010, 209-235).

    Args:
        data (np.ndarray): Data matrix of shape ``(n_samples, n_features)``.
        labels (np.ndarray): Integer cluster label per row; negative labels
            denote noise and are ignored.
        valid_labels (np.ndarray): The unique non-negative labels to build
            centroids for, in the order the centroids are returned.

    Returns:
        np.ndarray: Centroid matrix of shape ``(n_clusters, n_features)`` in
            the same order as ``valid_labels``.
    """
    return np.array([data[labels == lab].mean(axis=0) for lab in valid_labels])


def _xie_beni_score(data, labels):
    """Xie-Beni cluster validity index (lower is better).

    The Xie-Beni index is the ratio of the global within-cluster compactness
    (the mean squared distance of points to their centroid) to the minimum
    squared separation between cluster centroids. Minimising it favours
    partitions that are simultaneously compact and well separated. It was
    originally proposed for fuzzy c-means and is widely used as a fitness
    function in metaheuristic-based automatic clustering.

    Reference:
        X. L. Xie and G. Beni, "A validity measure for fuzzy clustering,"
        *IEEE Trans. Pattern Anal. Mach. Intell.* 13(8), 1991, 841-847,
        doi:10.1109/34.85677.

    Args:
        data (np.ndarray): Data matrix of shape ``(n_samples, n_features)``.
        labels (np.ndarray): Integer cluster label per row; negative labels
            denote noise and are excluded from the computation.

    Returns:
        float: The Xie-Beni index, or ``inf`` when it is undefined (fewer than
            two clusters, or coincident centroids giving zero separation).
    """
    mask = labels >= 0
    data = data[mask]
    labels = labels[mask]
    uniq = np.unique(labels)
    if len(uniq) < 2:
        return float('inf')
    cents = _cluster_centroids(data, labels, uniq)
    wgss = 0.0
    for ci, lab in enumerate(uniq):
        diff = data[labels == lab] - cents[ci]
        wgss += np.sum(diff * diff)
    diffs = cents[:, None, :] - cents[None, :, :]
    sq = np.sum(diffs * diffs, axis=2)
    np.fill_diagonal(sq, np.inf)
    min_sep = np.min(sq)
    n = len(data)
    if not np.isfinite(min_sep) or min_sep <= 0 or n == 0:
        return float('inf')
    return float(wgss / (n * min_sep))


def _pbm_score(data, labels):
    """PBM (I-index) cluster validity index (higher is better).

    The PBM index, named after Pakhira, Bandyopadhyay and Maulik, combines
    three factors: the inverse of the number of clusters, the ratio of total
    dispersion (distance of all points to the global centroid) to the total
    within-cluster dispersion, and the maximum separation between any two
    cluster centroids. The product is squared. Larger values indicate a more
    compact and better-separated partition.

    Reference:
        M. K. Pakhira, S. Bandyopadhyay and U. Maulik, "Validity index for
        crisp and fuzzy clusters," *Pattern Recognit.* 37(3), 2004, 487-501,
        doi:10.1016/j.patcog.2003.06.005.

    Args:
        data (np.ndarray): Data matrix of shape ``(n_samples, n_features)``.
        labels (np.ndarray): Integer cluster label per row; negative labels
            denote noise and are excluded from the computation.

    Returns:
        float: The PBM index, or ``0.0`` when it is undefined (fewer than two
            clusters or zero within-cluster dispersion).
    """
    mask = labels >= 0
    data = data[mask]
    labels = labels[mask]
    uniq = np.unique(labels)
    k = len(uniq)
    if k < 2:
        return 0.0
    cents = _cluster_centroids(data, labels, uniq)
    global_cent = data.mean(axis=0)
    e_t = np.sum(np.sqrt(np.sum((data - global_cent) ** 2, axis=1)))
    e_w = 0.0
    for ci, lab in enumerate(uniq):
        member = data[labels == lab]
        e_w += np.sum(np.sqrt(np.sum((member - cents[ci]) ** 2, axis=1)))
    if e_w <= 0:
        return 0.0
    diffs = cents[:, None, :] - cents[None, :, :]
    dist = np.sqrt(np.sum(diffs * diffs, axis=2))
    d_b = np.max(dist)
    return float(((1.0 / k) * (e_t / e_w) * d_b) ** 2)


def _sdbw_score(data, labels):
    """S_Dbw cluster validity index (lower is better).

    The S_Dbw index sums two terms: *Scat*, the average normalised
    within-cluster variance (compactness), and *Dens_bw*, the inter-cluster
    density measured at the midpoints between cluster centroids relative to the
    densities at the centroids themselves (separation). Low values reward
    compact clusters separated by low-density regions. In the comprehensive
    review by Ikotun, Habyarimana & Ezugwu (*Heliyon* 11, 2025, e41953) S_Dbw
    was among the most stable indices across datasets.

    References:
        M. Halkidi and M. Vazirgiannis, "Clustering validity assessment:
        finding the optimal partitioning of a data set," *Proc. IEEE ICDM*,
        2001, 187-194, doi:10.1109/icdm.2001.989517.
        O. Arbelaitz et al., "An extensive comparative study of cluster
        validity indices," *Pattern Recognit.* 46(1), 2013, 243-256,
        doi:10.1016/j.patcog.2012.07.021.

    Args:
        data (np.ndarray): Data matrix of shape ``(n_samples, n_features)``.
        labels (np.ndarray): Integer cluster label per row; negative labels
            denote noise and are excluded from the computation.

    Returns:
        float: The S_Dbw index, or ``inf`` when it is undefined (fewer than two
            clusters or zero dataset variance).
    """
    mask = labels >= 0
    data = data[mask]
    labels = labels[mask]
    uniq = np.unique(labels)
    k = len(uniq)
    if k < 2:
        return float('inf')
    cents = _cluster_centroids(data, labels, uniq)
    var_data = np.var(data, axis=0)
    norm_var_data = np.sqrt(np.sum(var_data * var_data))
    if norm_var_data <= 0:
        return float('inf')
    cluster_var_norms = []
    for ci, lab in enumerate(uniq):
        member = data[labels == lab]
        cv = np.var(member, axis=0)
        cluster_var_norms.append(np.sqrt(np.sum(cv * cv)))
    cluster_var_norms = np.array(cluster_var_norms)
    scat = np.mean(cluster_var_norms) / norm_var_data
    stdev = np.sqrt(np.sum(cluster_var_norms)) / k

    def _density(points, center):
        d = np.sqrt(np.sum((points - center) ** 2, axis=1))
        return np.sum(d <= stdev)

    dens_terms = []
    for i in range(k):
        for j in range(k):
            if i == j:
                continue
            mid = (cents[i] + cents[j]) / 2.0
            member_i = data[labels == uniq[i]]
            member_j = data[labels == uniq[j]]
            pair = np.vstack([member_i, member_j])
            dens_mid = _density(pair, mid)
            dens_i = _density(member_i, cents[i])
            dens_j = _density(member_j, cents[j])
            denom = max(dens_i, dens_j)
            if denom > 0:
                dens_terms.append(dens_mid / denom)
    dens_bw = (np.sum(dens_terms) / (k * (k - 1))) if dens_terms else 0.0
    return float(scat + dens_bw)


def _dunn_sym_score(data, labels, max_points=2000, random_state=0):
    """Dunn-Symmetric (Sym-Dunn) cluster validity index (higher is better).

    This is a point-symmetry variant of the classical Dunn index. The Dunn
    index is the ratio of the minimum inter-cluster distance to the maximum
    intra-cluster diameter; maximising it rewards compact, well-separated
    clusters. The symmetric variant replaces the plain Euclidean intra-cluster
    spread with a symmetry-aware spread, improving detection of symmetric and
    arbitrarily shaped clusters. In the Ikotun, Habyarimana & Ezugwu review
    (*Heliyon* 11, 2025, e41953) the Dunn-Symmetric index gave the best
    performance on the majority of the evaluated datasets, at a higher
    computational cost.

    The computation is O(n^2) in the number of points, so for large particle
    sets the data is sub-sampled to ``max_points`` rows before evaluation; this
    keeps the index usable in interactive runs while preserving its ranking
    behaviour. This index is therefore excluded from bootstrap stability runs
    by default (see the metric registry ``bootstrap_safe`` flag).

    References:
        J. C. Dunn, "Well-separated clusters and optimal fuzzy partitions,"
        *J. Cybern.* 4(1), 1974, 95-104, doi:10.1080/01969727408546059.
        S. Bandyopadhyay and S. Saha, "A point symmetry-based clustering
        technique for automatic evolution of clusters," *IEEE Trans. Knowl.
        Data Eng.* 20(11), 2008, 1441-1457, doi:10.1109/TKDE.2008.79.

    Args:
        data (np.ndarray): Data matrix of shape ``(n_samples, n_features)``.
        labels (np.ndarray): Integer cluster label per row; negative labels
            denote noise and are excluded from the computation.
        max_points (int): Upper bound on the number of points used; larger
            inputs are randomly sub-sampled to this size for tractability.
        random_state (int): Seed for the sub-sampling RNG, for reproducibility.

    Returns:
        float: The Dunn-Symmetric index, or ``0.0`` when it is undefined
            (fewer than two clusters or a degenerate intra-cluster diameter).
    """
    mask = labels >= 0
    data = data[mask]
    labels = labels[mask]
    uniq = np.unique(labels)
    if len(uniq) < 2:
        return 0.0
    if len(data) > max_points:
        rng = np.random.default_rng(random_state)
        sel = rng.choice(len(data), size=max_points, replace=False)
        data = data[sel]
        labels = labels[sel]
        uniq = np.unique(labels)
        if len(uniq) < 2:
            return 0.0
    cents = _cluster_centroids(data, labels, uniq)
    max_diam = 0.0
    for ci, lab in enumerate(uniq):
        member = data[labels == lab]
        if len(member) < 2:
            continue
        refl = 2.0 * cents[ci] - member
        d_sym = np.sqrt(np.sum((member[:, None, :] - refl[None, :, :]) ** 2,
                               axis=2))
        diam = np.max(d_sym)
        if diam > max_diam:
            max_diam = diam
    if max_diam <= 0:
        return 0.0
    min_sep = np.inf
    for i in range(len(uniq)):
        mi = data[labels == uniq[i]]
        for j in range(i + 1, len(uniq)):
            mj = data[labels == uniq[j]]
            d = np.sqrt(np.sum((mi[:, None, :] - mj[None, :, :]) ** 2, axis=2))
            sep = np.min(d)
            if sep < min_sep:
                min_sep = sep
    if not np.isfinite(min_sep):
        return 0.0
    return float(min_sep / max_diam)


def _c_index_score(data, labels, max_points=2000, random_state=0):
    """C-index cluster validity index (lower is better, bounded in ``[0, 1]``).

    The C-index compares the sum of within-cluster pairwise distances ``S_w``
    against the best and worst values that sum could take for the same number of
    within-cluster pairs ``N_w``. Writing ``S_min`` for the sum of the ``N_w``
    smallest and ``S_max`` for the sum of the ``N_w`` largest pairwise distances
    over the whole data set, the index is ``(S_w - S_min) / (S_max - S_min)``. It
    is zero only when every within-cluster pair is among the globally closest
    pairs — a perfectly compact partition — and approaches one for the worst.
    Being normalised and bounded, it is directly comparable across cluster counts
    and was among the better-performing indices in the comprehensive comparison
    of Arbelaitz et al.

    The computation is O(n^2) in the number of points, so large particle sets are
    randomly sub-sampled to ``max_points`` before evaluation; this keeps the index
    usable interactively while preserving its ranking behaviour. It is therefore
    excluded from bootstrap stability runs by default (the registry
    ``bootstrap_safe`` flag is ``False``).

    References:
        L. J. Hubert and J. R. Levin, "A general statistical framework for
        assessing categorical clustering in free recall," *Psychol. Bull.* 83(6),
        1976, 1072-1080, doi:10.1037/0033-2909.83.6.1072.
        O. Arbelaitz et al., "An extensive comparative study of cluster validity
        indices," *Pattern Recognit.* 46(1), 2013, 243-256,
        doi:10.1016/j.patcog.2012.07.021.

    Args:
        data (np.ndarray): Data matrix of shape ``(n_samples, n_features)``.
        labels (np.ndarray): Integer cluster label per row; negative labels
            denote noise and are excluded from the computation.
        max_points (int): Upper bound on the number of points used; larger inputs
            are randomly sub-sampled to this size for tractability.
        random_state (int): Seed for the sub-sampling RNG, for reproducibility.

    Returns:
        float: The C-index, or ``1.0`` (the worst attainable value) when it is
            undefined — fewer than two clusters, no within-cluster pairs, or all
            pairwise distances equal.
    """
    from scipy.spatial.distance import pdist

    mask = labels >= 0
    data = data[mask]
    labels = labels[mask]
    uniq = np.unique(labels)
    if len(uniq) < 2:
        return 1.0
    if len(data) > max_points:
        rng = np.random.default_rng(random_state)
        sel = rng.choice(len(data), size=max_points, replace=False)
        data = data[sel]
        labels = labels[sel]
        uniq = np.unique(labels)
        if len(uniq) < 2:
            return 1.0
    all_d = pdist(data)
    if all_d.size == 0:
        return 1.0
    s_w = 0.0
    n_w = 0
    for lab in uniq:
        member = data[labels == lab]
        if len(member) < 2:
            continue
        dm = pdist(member)
        s_w += float(dm.sum())
        n_w += dm.size
    if n_w <= 0:
        return 1.0
    sorted_d = np.sort(all_d)
    s_min = float(sorted_d[:n_w].sum())
    s_max = float(sorted_d[-n_w:].sum())
    if s_max <= s_min:
        return 1.0
    return float((s_w - s_min) / (s_max - s_min))


CVI_FUNCS = {
    'silhouette_scores':         lambda d, l: float(silhouette_score(d, l)),
    'calinski_harabasz_scores':  lambda d, l: float(calinski_harabasz_score(d, l)),
    'davies_bouldin_scores':     lambda d, l: float(davies_bouldin_score(d, l)),
    'sdbw_scores':               lambda d, l: _sdbw_score(d, l),
    'xie_beni_scores':           lambda d, l: _xie_beni_score(d, l),
    'pbm_scores':                lambda d, l: _pbm_score(d, l),
    'dunn_sym_scores':           lambda d, l: _dunn_sym_score(d, l),
    'c_index_scores':            lambda d, l: _c_index_score(d, l),
}


METRIC_REGISTRY = {
    'Silhouette': {
        'display':        'Silhouette Score',
        'key':            'silhouette_scores',
        'direction':      'max',
        'rule':           'max',
        'bootstrap_safe': True,
        'color':          '#2563EB',
    },
    'Calinski-Harabasz': {
        'display':        'Calinski-Harabasz Index',
        'key':            'calinski_harabasz_scores',
        'direction':      'max',
        'rule':           'elbow',
        'bootstrap_safe': True,
        'color':          '#2563EB',
    },
    'Davies-Bouldin': {
        'display':        'Davies-Bouldin Index',
        'key':            'davies_bouldin_scores',
        'direction':      'min',
        'rule':           'min',
        'bootstrap_safe': True,
        'color':          '#2563EB',
    },
    'S_Dbw': {
        'display':        'S_Dbw Index',
        'key':            'sdbw_scores',
        'direction':      'min',
        'rule':           'min',
        'bootstrap_safe': True,
        'color':          '#2563EB',
    },
    'Xie-Beni': {
        'display':        'Xie-Beni Index',
        'key':            'xie_beni_scores',
        'direction':      'min',
        'rule':           'min',
        'bootstrap_safe': True,
        'color':          '#2563EB',
    },
    'PBM': {
        'display':        'PBM (I-index)',
        'key':            'pbm_scores',
        'direction':      'max',
        'rule':           'max',
        'bootstrap_safe': True,
        'color':          '#2563EB',
    },
    'Dunn-Sym': {
        'display':        'Dunn-Symmetric Index',
        'key':            'dunn_sym_scores',
        'direction':      'max',
        'rule':           'max',
        'bootstrap_safe': False,
        'color':          '#2563EB',
    },
    'C-index': {
        'display':        'C-index',
        'key':            'c_index_scores',
        'direction':      'min',
        'rule':           'min',
        'bootstrap_safe': False,
        'color':          '#2563EB',
    },
}

METRICS = list(METRIC_REGISTRY.keys())

METRIC_KEYS = {
    name: (spec['display'], spec['key'])
    for name, spec in METRIC_REGISTRY.items()
}

DEFAULT_METRICS = ['Silhouette', 'Calinski-Harabasz', 'Davies-Bouldin']

METRIC_COLORS = {name: spec['color'] for name, spec in METRIC_REGISTRY.items()}


def _vote_optimal_per_metric(eval_results, elbow_fn, enabled_metrics=None):
    """Select an optimal K per metric by voting across algorithms.

    Generic replacement for the previously hard-coded three-metric blocks. For
    each enabled metric every algorithm casts one vote for the K it prefers
    under that metric's selection rule:

      * ``rule == 'max'``   → the K with the largest score (e.g. Silhouette,
        PBM, Dunn-Symmetric).
      * ``rule == 'min'``   → the K with the smallest score (e.g.
        Davies-Bouldin, Xie-Beni, S_Dbw).
      * ``rule == 'elbow'`` → the knee of the score curve via ``elbow_fn``
        (e.g. Calinski-Harabasz, which tends to rise monotonically with K);
        falls back to the ``direction`` extremum when fewer than three K values
        are available.

    Ties on votes are broken by the best mean score across algorithms at the
    tied K's, where "best" follows the metric ``direction``. This mirrors the
    consensus-plus-tiebreak procedure recommended for selecting cluster
    validity indices in Ikotun, Habyarimana & Ezugwu (*Heliyon* 11, 2025,
    e41953).

    Args:
        eval_results (dict): ``{algo: {'k_values': [...], '<key>': [...], ...}}``.
        elbow_fn (Callable): Function ``(k_values, scores) -> int`` returning
            the elbow/knee K for monotonic-rising metrics.
        enabled_metrics (list|None): Metric names to consider; defaults to all
            metrics present in the registry.

    Returns:
        tuple:
            * ``dict`` ``{metric: optimal_k}`` for every metric that could
              decide a K.
            * ``dict`` ``{metric: {k: [scores...]}}`` of the per-K score lists,
              kept so callers can reuse them for the best-algorithm lookup.
    """
    if enabled_metrics is None:
        enabled_metrics = list(METRIC_REGISTRY.keys())

    votes = {m: {} for m in enabled_metrics}
    scores_at_k = {m: {} for m in enabled_metrics}

    for algo, res in eval_results.items():
        k_vals = res.get('k_values', [])
        if not k_vals:
            continue
        for metric in enabled_metrics:
            spec = METRIC_REGISTRY[metric]
            scores = res.get(spec['key'], [])
            if not scores or len(scores) != len(k_vals):
                continue
            rule = spec['rule']
            direction = spec['direction']
            if rule == 'elbow' and len(scores) >= 3:
                best = elbow_fn(k_vals, scores)
            elif rule == 'min' or (rule == 'elbow' and direction == 'min'):
                best = k_vals[int(np.argmin(scores))]
            else:
                best = k_vals[int(np.argmax(scores))]
            votes[metric][best] = votes[metric].get(best, 0) + 1
            for k, s in zip(k_vals, scores):
                scores_at_k[metric].setdefault(k, []).append(s)

    out = {}
    for metric in enabled_metrics:
        mv = votes[metric]
        if not mv:
            continue
        max_v = max(mv.values())
        tied = [k for k, v in mv.items() if v == max_v]
        if len(tied) == 1:
            out[metric] = int(tied[0])
            continue
        sk = scores_at_k[metric]
        if METRIC_REGISTRY[metric]['direction'] == 'min':
            out[metric] = int(min(
                tied, key=lambda k: np.mean(sk.get(k, [np.inf]))))
        else:
            out[metric] = int(max(
                tied, key=lambda k: np.mean(sk.get(k, [-np.inf]))))
    return out, scores_at_k


DENSITY_BASED_ALGOS = {'DBSCAN', 'HDBSCAN', 'OPTICS', 'Mean Shift'}

PROGRESS_RESOLUTION = 1000

SCALING_OPTIONS = ['CLR', 'ILR', 'Robust Z-score', 'None']
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

try:
    from tools.theme import theme as _app_theme
except Exception: 
    try:
        from ..tools.theme import theme as _app_theme
    except Exception:
        _app_theme = None


def _palette_to_plot(pal):
    """Map an app ``Palette`` (or None) to the plot/theme keys used here.

    Centralises the translation between the application's rich palette and the
    small set of roles the matplotlib draw functions and local widget styles
    need, so the rest of this module never touches ``Palette`` field names
    directly.

    Args:
        pal: An app ``theme.Palette`` instance, or None to fall back to a
            sensible light default.

    Returns:
        dict: Plot/widget theme keys (bg, surface, border, text, accent, …).
    """
    if pal is None:
        return {
            'bg': '#FFFFFF', 'surface': '#F8FAFC', 'surface_alt': '#F1F5F9',
            'border': '#E2E8F0', 'border_str': '#CBD5E1',
            'text': '#1E293B', 'text_muted': '#64748B',
            'plot_bg': '#FFFFFF', 'plot_face': '#FAFAFA', 'grid': '#CBD5E1',
            'disabled': '#CBD5E1', 'accent': '#2563EB',
            'success': '#16A34A', 'warning': '#D97706', 'danger': '#DC2626',
            'dark': False,
        }
    dark = (getattr(pal, 'name', 'light') == 'dark')
    return {
        'bg':          pal.bg_secondary,
        'surface':     pal.bg_primary,
        'surface_alt': pal.bg_tertiary,
        'border':      pal.border_subtle,
        'border_str':  pal.border,
        'text':        pal.text_primary,
        'text_muted':  pal.text_muted,
        'plot_bg':     pal.plot_bg,
        'plot_face':   pal.bg_tertiary,
        'grid':        pal.border,
        'disabled':    pal.disabled,
        'accent':      pal.accent,
        'success':     pal.success,
        'warning':     pal.warning,
        'danger':      pal.danger,
        'dark':        dark,
    }


def _current_plot_palette():
    """Return the active plot/theme dict from the app ThemeManager.

    Returns:
        dict: Result of :func:`_palette_to_plot` for the current app palette,
            or the light fallback when the theme manager is unavailable.
    """
    if _app_theme is not None:
        try:
            return _palette_to_plot(_app_theme.palette)
        except Exception:
            pass
    return _palette_to_plot(None)

ALGO_LINE_STYLES = {
    'K-Means':           dict(color='#2563EB', ls='-',  marker='o'),
    'Hierarchical':      dict(color='#DC2626', ls='-',  marker='s'),
    'DBSCAN':            dict(color='#16A34A', ls='--', marker='^'),
    'HDBSCAN':           dict(color='#7C3AED', ls='--', marker='v'),
    'Spectral':          dict(color='#D97706', ls='-',  marker='D'),
    'SOM':               dict(color='#0891B2', ls='-',  marker='P'),
    'MiniBatch K-Means': dict(color='#4F46E5', ls='--', marker='p'),
    'Birch':             dict(color='#DB2777', ls='-',  marker='H'),
    'Mean Shift':        dict(color='#65A30D', ls='--', marker='X'),
    'OPTICS':            dict(color='#EA580C', ls='--', marker='*'),
    'Gaussian Mixture':  dict(color='#9333EA', ls='-',  marker='8'),
}


def multiplicative_replacement(matrix, frac=0.65, threshold=None):
    """Replace zeros in a non-negative composition matrix without distorting ratios.

    Log-ratio transforms are undefined at zero, and substituting a fixed tiny
    constant such as ``1e-10`` is statistically poor for sparse, zero-inflated
    data: every zero maps to an almost identical, very large negative log value,
    so the transformed coordinates end up encoding presence/absence at enormous
    magnitude and overwhelm genuine compositional differences. This is acute for
    single-particle ICP-ToF-MS matrices, where most particles carry signal in
    only one or a few element channels.

    Multiplicative (simple) replacement substitutes a small positive ``delta``
    for each zero and rescales the non-zero parts of the same row so the row
    total is preserved, leaving the ratios among the observed parts unchanged —
    the coherence property required for compositional data. ``delta`` is a
    fraction of a per-column detection floor (by default the smallest strictly
    positive value in each column), tying the imputed value to the instrument's
    effective detection limit rather than to an arbitrary constant.

    References:
        J. A. Martín-Fernández, C. Barceló-Vidal and V. Pawlowsky-Glahn,
        "Dealing with zeros and missing values in compositional data sets using
        nonparametric imputation," *Math. Geol.* 35(3), 2003, 253-278,
        doi:10.1023/A:1023866030544.
        J. Aitchison, *The Statistical Analysis of Compositional Data*, Chapman &
        Hall, 1986.

    Args:
        matrix (np.ndarray): Non-negative matrix ``(n_samples, n_parts)``; each
            row is one composition.
        frac (float): Fraction of the per-column detection floor used as the
            imputed value; ``0.65`` follows Martín-Fernández et al. (2003).
        threshold (np.ndarray or float or None): Explicit per-column (or scalar)
            detection floor; when ``None`` the smallest strictly positive entry
            of each column is used, with ``1.0`` for all-zero columns.

    Returns:
        np.ndarray: A float64 copy with zeros replaced and row totals preserved;
            all-zero rows are filled with the per-column floor ``delta`` so
            log-ratios stay finite.
    """
    X = np.array(matrix, dtype=np.float64, copy=True)
    if X.size == 0:
        return X
    n_parts = X.shape[1]
    if threshold is None:
        floor = np.full(n_parts, np.nan)
        for j in range(n_parts):
            col = X[:, j]
            pos = col[col > 0]
            floor[j] = pos.min() if pos.size else 1.0
    else:
        floor = np.asarray(threshold, dtype=np.float64)
        if floor.ndim == 0:
            floor = np.full(n_parts, float(floor))
    floor = np.where(np.isfinite(floor) & (floor > 0), floor, 1.0)
    delta = np.clip(float(frac), 1e-9, 1.0 - 1e-9) * floor

    totals = X.sum(axis=1)
    out = X.copy()
    for i in range(X.shape[0]):
        row = X[i]
        zero = row <= 0
        if not zero.any():
            continue
        if totals[i] <= 0:
            out[i] = delta
            continue
        removed = delta[zero].sum()
        scale = 1.0 - removed / totals[i]
        if scale <= 0:
            out[i, zero] = delta[zero]
            continue
        out[i, ~zero] = row[~zero] * scale
        out[i, zero] = delta[zero]
    return out


def _apply_clr(matrix, zero_replacement='additive'):
    """Centred-log-ratio transform of a non-negative composition matrix.

    The CLR maps a composition to log values centred on the per-row geometric
    mean, giving coordinates suitable for Euclidean-distance clustering of
    compositional data. Because the logarithm is undefined at zero, zeros must
    be handled first; the strategy is selectable.

    References:
        J. Aitchison, *The Statistical Analysis of Compositional Data*, Chapman &
        Hall, 1986.
        J. A. Martín-Fernández, C. Barceló-Vidal and V. Pawlowsky-Glahn,
        "Dealing with zeros and missing values in compositional data sets using
        nonparametric imputation," *Math. Geol.* 35(3), 2003, 253-278,
        doi:10.1023/A:1023866030544.

    Args:
        matrix (np.ndarray): Data matrix ``(n_samples, n_features)``, values >= 0.
        zero_replacement (str): ``'additive'`` adds a fixed ``1e-10`` floor
            (legacy behaviour, retained as the default for reproducibility);
            ``'multiplicative'`` uses ratio-preserving, detection-limit-aware
            replacement via :func:`multiplicative_replacement`, which is the
            statistically preferred treatment for the sparse single-particle case.

    Returns:
        np.ndarray: CLR-transformed matrix.
    """
    if zero_replacement == 'multiplicative':
        X = multiplicative_replacement(matrix)
    else:
        eps = 1e-10
        X = np.where(matrix <= 0, eps, matrix.astype(np.float64))
    log_X = np.log(X)
    return log_X - log_X.mean(axis=1, keepdims=True)


def _apply_ilr(matrix, zero_replacement='additive'):
    """Isometric-log-ratio transform yielding ``p - 1`` orthonormal coordinates.

    The ILR expresses a composition in an orthonormal basis of the Aitchison
    simplex, removing the singular covariance the CLR leaves behind while
    preserving Aitchison distances. It is built on the CLR and inherits its zero
    handling.

    References:
        J. J. Egozcue, V. Pawlowsky-Glahn, G. Mateu-Figueras and C.
        Barceló-Vidal, "Isometric logratio transformations for compositional data
        analysis," *Math. Geol.* 35(3), 2003, 279-300,
        doi:10.1023/A:1023818214614.

    Args:
        matrix (np.ndarray): Data matrix ``(n_samples, n_features)``, values >= 0.
        zero_replacement (str): Passed through to :func:`_apply_clr`.

    Returns:
        np.ndarray: ILR-transformed matrix with ``p - 1`` coordinates.
    """
    clr = _apply_clr(matrix, zero_replacement=zero_replacement)
    p = clr.shape[1]
    if p < 2:
        return clr
    V = np.zeros((p, p - 1), dtype=np.float64)
    for j in range(p - 1):
        k = j + 1
        scale = np.sqrt(k / (k + 1.0))
        V[:k, j] = scale / k
        V[k, j] = -scale
    return clr @ V


def _apply_robust_zscore(matrix):
    """Robust per-column z-score using a consistent scale estimate.

    Each column is centred on its median and divided by a robust estimate of its
    standard deviation. The estimate is ``1.4826 * MAD``, where ``1.4826`` is the
    consistency constant that makes the scaled MAD an unbiased estimator of the
    standard deviation for Gaussian data.

    The previous implementation divided by the bare MAD and, whenever the MAD was
    below ``1e-10``, clamped it to ``1e-10``. For single-particle ICP-ToF-MS data
    that clamp is a trap: any element detected in fewer than half the particles
    has a median and a MAD of exactly zero, so its column was divided by
    ``1e-10`` and inflated to magnitudes around ``1e10`` that then dominated every
    Euclidean distance. Because sparse columns are the rule rather than the
    exception here, most "Robust Z-score" results were dominated by that
    artefact. This version instead falls back to the column standard deviation
    when the MAD vanishes, and to a unit scale only when the column is genuinely
    constant (in which case the centred column is identically zero and carries no
    weight), so no column can explode.

    References:
        P. J. Rousseeuw and C. Croux, "Alternatives to the median absolute
        deviation," *J. Am. Stat. Assoc.* 88(424), 1993, 1273-1283,
        doi:10.1080/01621459.1993.10476408.

    Args:
        matrix (np.ndarray): Data matrix ``(n_samples, n_features)``.

    Returns:
        np.ndarray: Robust z-score normalised matrix with no column inflated by a
            near-zero scale.
    """
    X = matrix.astype(np.float64)
    med = np.median(X, axis=0)
    mad = np.median(np.abs(X - med), axis=0)
    scale = 1.4826 * mad
    std = np.std(X, axis=0)
    scale = np.where(scale > 1e-10, scale, std)
    scale = np.where(scale > 1e-10, scale, 1.0)
    return (X - med) / scale


def _filter_rare_particle_types(matrix, sample_labels, original_indices, min_count):
    """Remove particles whose elemental signature occurs fewer than min_count times.

    A particle's type is the frozen set of column indices (elements) whose
    value is strictly greater than zero. Groups whose total size is strictly
    less than min_count are dropped entirely before scaling or dim-reduction.

    Args:
        matrix (np.ndarray): Raw data matrix (n_particles, n_elements).
        sample_labels (np.ndarray): 1-D array of sample name strings.
        original_indices (np.ndarray): 1-D array of original particle indices.
        min_count (int): Minimum group size to retain.

    Returns:
        tuple[np.ndarray, np.ndarray, np.ndarray]: Filtered
            (matrix, sample_labels, original_indices).
    """
    from collections import Counter
    type_signatures = [frozenset(np.where(row > 0)[0]) for row in matrix]
    type_counts = Counter(type_signatures)
    keep = np.array([type_counts[sig] >= min_count for sig in type_signatures])
    return matrix[keep], sample_labels[keep], original_indices[keep]


class _SOM:
    def __init__(self, rows, cols, n_features, sigma=1.0, lr=0.5, n_iter=2000, random_state=42):
        """
        Args:
            rows (int): Grid rows.
            cols (int): Grid columns.
            n_features (int): Input feature count.
            sigma (float): Initial neighbourhood radius.
            lr (float): Initial learning rate.
            n_iter (int): Training iterations.
            random_state (int): Random seed.
        """
        rng = np.random.RandomState(random_state)
        self.weights = rng.randn(rows * cols, n_features).astype(np.float32)
        self.rows = rows
        self.cols = cols
        self.sigma = sigma
        self.lr = lr
        self.n_iter = n_iter
        ri, ci = np.meshgrid(np.arange(rows), np.arange(cols), indexing='ij')
        self._coords = np.column_stack([ri.ravel(), ci.ravel()]).astype(np.float32)

    def fit(self, X, progress_cb=None, snapshot_every=0):
        """Train the SOM, optionally reporting live convergence snapshots.

        Args:
            X (np.ndarray): Training data (n_samples, n_features).
            progress_cb (callable or None): Optional callback invoked as
                ``progress_cb(t, n_iter, weights_copy)`` every
                ``snapshot_every`` iterations (and once at the end), where
                ``t`` is the current iteration index and ``weights_copy`` is a
                detached copy of the neuron weights for safe cross-thread use.
            snapshot_every (int): Emit a snapshot every this many iterations.
                ``0`` disables snapshots (callback still fires once at the end).

        Returns:
            _SOM: self.
        """
        X = np.asarray(X, dtype=np.float32)
        n = len(X)
        rng = np.random.RandomState(42)
        idx_seq = rng.randint(0, n, self.n_iter)
        for t, idx in enumerate(idx_seq):
            frac = t / max(self.n_iter - 1, 1)
            lr_t = self.lr * np.exp(-frac * 4)
            sig_t = max(self.sigma * np.exp(-frac * 3), 0.3)
            x = X[idx]
            diff = self.weights - x
            bmu = int(np.argmin(np.sum(diff ** 2, axis=1)))
            gd2 = np.sum((self._coords - self._coords[bmu]) ** 2, axis=1)
            h = np.exp(-gd2 / (2 * sig_t ** 2))
            self.weights += lr_t * h[:, None] * (-diff)
            if (progress_cb is not None and snapshot_every > 0
                    and t > 0 and t % snapshot_every == 0):
                progress_cb(t, self.n_iter, self.weights.copy())
        if progress_cb is not None:
            progress_cb(self.n_iter, self.n_iter, self.weights.copy())
        return self

    def predict(self, X):
        """
        Args:
            X (np.ndarray): Input data (n_samples, n_features).
        Returns:
            np.ndarray: BMU index per sample.
        """
        X = np.asarray(X, dtype=np.float32)
        out = []
        for x in X:
            diff = self.weights - x
            out.append(int(np.argmin(np.sum(diff ** 2, axis=1))))
        return np.array(out)

    def get_weights(self):
        """
        Returns:
            np.ndarray: Neuron weight vectors (n_neurons, n_features).
        """
        return self.weights.copy()

    def get_grid_labels(self, neuron_cluster_labels):
        """
        Args:
            neuron_cluster_labels (np.ndarray): Cluster label per neuron.
        Returns:
            np.ndarray: 2-D grid of shape (rows, cols).
        """
        return neuron_cluster_labels.reshape(self.rows, self.cols)

    def get_u_matrix(self):
        """Compute the U-matrix: mean Euclidean distance from each neuron to
        its 8-connected grid neighbours. High values mark cluster boundaries
        (neighbouring neurons have very different weight vectors), low values
        mark cluster interiors.

        Returns:
            np.ndarray: 2-D array of shape (rows, cols), one mean-distance
            value per neuron. Values are NOT normalised — use the sequential
            colormap to render them.
        """
        w_grid = self.weights.reshape(self.rows, self.cols, -1)
        u = np.zeros((self.rows, self.cols), dtype=np.float32)
        for r in range(self.rows):
            for c in range(self.cols):
                dists = []
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.rows and 0 <= nc < self.cols:
                            dists.append(np.linalg.norm(
                                w_grid[r, c] - w_grid[nr, nc]))
                u[r, c] = float(np.mean(dists)) if dists else 0.0
        return u

    def get_hit_count(self, X):
        """Count how many input samples have each neuron as their BMU
        (best matching unit).

        Args:
            X (np.ndarray): Input data, shape (n_samples, n_features).

        Returns:
            np.ndarray: 2-D array of shape (rows, cols) with one integer per
            neuron — the number of samples mapped to it. Zero means a "dead"
            neuron that no input claimed.
        """
        bmu = self.predict(X)
        counts = np.zeros(self.rows * self.cols, dtype=int)
        for b in bmu:
            counts[b] += 1
        return counts.reshape(self.rows, self.cols)

    def get_quantization_error(self, X):
        """Mean Euclidean distance from each input to its BMU.

        Standard SOM diagnostic — lower = the map represents the data better.
        Doesn't tell you whether the map is well-organised (use topographic
        error for that), only how well it covers feature space.

        Args:
            X (np.ndarray): Input data, shape (n_samples, n_features).

        Returns:
            float: Mean distance over all samples.
        """
        X = np.asarray(X, dtype=np.float32)
        bmu = self.predict(X)
        return float(np.mean(np.linalg.norm(X - self.weights[bmu], axis=1)))


def _som_cluster_cmap(name, n_clusters):
    """Build a discrete categorical colormap for the SOM cluster grid.

    Uses the in-house ``CLUSTER_COLORS`` palette when ``name`` is
    ``'CLUSTER_COLORS'``; otherwise resolves ``name`` as a matplotlib named
    colormap and discretises it to ``n_clusters`` colours.

    Args:
        name (str): Colormap name or ``'CLUSTER_COLORS'`` for the app palette.
        n_clusters (int): Number of discrete colour steps required.

    Returns:
        matplotlib.colors.Colormap: Discrete colormap with ``n_clusters``
            entries.
    """
    from matplotlib.colors import ListedColormap
    n = max(int(n_clusters), 2)
    if name == 'CLUSTER_COLORS':
        return ListedColormap(
            [CLUSTER_COLORS[i % len(CLUSTER_COLORS)] for i in range(n)])
    try:
        return plt.get_cmap(name, n)
    except Exception:
        return plt.get_cmap('tab20', n)


def _contrast_text_for(cmap_name, norm_value):
    """Pick black or white text for legibility over a colormap cell.

    Computes the cell's fill colour from the colormap at ``norm_value`` and
    returns black or white based on its perceived luminance.  This keeps
    in-cell labels readable regardless of the app theme, because the contrast
    is judged against the *cell* colour, not the figure background.

    Args:
        cmap_name (str): Matplotlib colormap name.
        norm_value (float): Normalised value in [0, 1] for the cell.

    Returns:
        str: ``'#000000'`` or ``'#FFFFFF'``.
    """
    try:
        import matplotlib.cm as _cm
        r, g, b, _ = _cm.get_cmap(cmap_name)(max(0.0, min(1.0, norm_value)))
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        return '#000000' if lum > 0.6 else '#FFFFFF'
    except Exception:
        return '#FFFFFF'


def _draw_som_grid(fig, som_obj, neuron_cluster_labels, data_labels, cfg,
                   sample_labels=None, input_data=None):
    """Draw the SOM diagnostic panels: cluster grid, U-matrix, hit-count,
    and cluster size bar chart.

    Layout depends on which optional panels are enabled in the config:
        * Both U-matrix + hit-count on → 2×2 grid.
        * Only one extra on → 1×3 row.
        * Neither extra on → 1×2 (cluster grid + size bars), same as the
          original layout.

    Colormaps come from config: ``som_cluster_cmap`` (categorical, for the
    cluster grid) and ``som_sequential_cmap`` (perceptually uniform, for
    U-matrix and hit-count).

    Args:
        fig (Figure): Matplotlib figure.
        som_obj (_SOM): Trained SOM (with ``_fit_X`` cached on it).
        neuron_cluster_labels (np.ndarray): Cluster label per neuron.
        data_labels (np.ndarray): Cluster label per data point.
        cfg (dict): Configuration dictionary.
    """
    fig.clear()
    if som_obj is None:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, 'Run ② Cluster with SOM first',
                ha='center', va='center',
                fontproperties=_font_scale(cfg, 'label')[0],
                color=_muted_color(cfg),
                transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return

    fc = get_font_config(cfg)
    fp_title, col = _font_scale(cfg, 'title')
    fp_lbl, _ = _font_scale(cfg, 'label')
    fp_tick, _ = _font_scale(cfg, 'tick')
    fp_annot, _ = _font_scale(cfg, 'annot')
    fp_cell, _ = _font_scale(cfg, 'cell')
    fp = make_font_properties(cfg)

    rows, cols = som_obj.rows, som_obj.cols
    grid = som_obj.get_grid_labels(neuron_cluster_labels)
    n_clusters = len(np.unique(neuron_cluster_labels[neuron_cluster_labels >= 0]))

    show_u    = cfg.get('som_show_u_matrix', True)
    show_hits = cfg.get('som_show_hit_count', True)
    cluster_cmap_name = cfg.get('som_cluster_cmap', 'CLUSTER_COLORS')
    seq_cmap_name     = cfg.get('som_sequential_cmap', 'viridis')

    n_extras = (1 if show_u else 0) + (1 if show_hits else 0)
    if n_extras == 2:
        rows_layout, cols_layout = 2, 2
        positions = {'cluster': 1, 'u': 2, 'hit': 3, 'sizes': 4}
    elif n_extras == 1:
        rows_layout, cols_layout = 1, 3
        positions = {
            'cluster': 1,
            'u':       2 if show_u else None,
            'hit':     2 if show_hits else None,
            'sizes':   3,
        }
    else:
        rows_layout, cols_layout = 1, 2
        positions = {'cluster': 1, 'u': None, 'hit': None, 'sizes': 2}

    ax1 = fig.add_subplot(rows_layout, cols_layout, positions['cluster'])
    cmap = _som_cluster_cmap(cluster_cmap_name, max(n_clusters, 2))
    im = ax1.imshow(grid, cmap=cmap, vmin=-0.5, vmax=max(n_clusters - 0.5, 0.5),
                    interpolation='nearest', aspect='auto')
    ax1.set_title(f'Cluster Map  ({rows}×{cols})',
                  fontproperties=fp_title, color=col, pad=8)
    ax1.set_xlabel('Column', fontproperties=fp_lbl, color=col)
    ax1.set_ylabel('Row', fontproperties=fp_lbl, color=col)
    ax1.tick_params(labelsize=fp_tick.get_size_in_points(), colors=col)
    for r in range(rows):
        for c in range(cols):
            lbl = grid[r, c]
            txt = ax1.text(c, r, str(lbl) if lbl >= 0 else '•',
                           ha='center', va='center', fontproperties=fp_cell,
                           color='white' if lbl >= 0 else '#9CA3AF')
            txt.set_fontweight('bold')
    cb = fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)
    cb.set_label('Cluster', fontproperties=fp_annot, color=col)
    cb.ax.tick_params(labelsize=fp_tick.get_size_in_points(), colors=col)
    if n_clusters > 0:
        cb.set_ticks(range(n_clusters))

    if show_u and positions['u'] is not None:
        ax2 = fig.add_subplot(rows_layout, cols_layout, positions['u'])
        u = som_obj.get_u_matrix()
        im_u = ax2.imshow(u, cmap=seq_cmap_name,
                          interpolation='nearest', aspect='auto')
        ax2.set_title('U-matrix (boundary intensity)',
                      fontproperties=fp_title, color=col, pad=8)
        ax2.set_xlabel('Column', fontproperties=fp_lbl, color=col)
        ax2.set_ylabel('Row', fontproperties=fp_lbl, color=col)
        ax2.tick_params(labelsize=fp_tick.get_size_in_points(), colors=col)
        cb_u = fig.colorbar(im_u, ax=ax2, fraction=0.046, pad=0.04)
        cb_u.set_label('Mean neighbour distance', fontproperties=fp_annot, color=col)
        cb_u.ax.tick_params(labelsize=fp_tick.get_size_in_points(), colors=col)

    if show_hits and positions['hit'] is not None:
        ax3 = fig.add_subplot(rows_layout, cols_layout, positions['hit'])
        X = getattr(som_obj, '_fit_X', None)
        if X is not None:
            hits = som_obj.get_hit_count(X)
            im_h = ax3.imshow(hits, cmap=seq_cmap_name,
                              interpolation='nearest', aspect='auto')
            ax3.set_title('Hit count (BMU activations)',
                          fontproperties=fp_title, color=col, pad=8)
            ax3.set_xlabel('Column', fontproperties=fp_lbl, color=col)
            ax3.set_ylabel('Row', fontproperties=fp_lbl, color=col)
            ax3.tick_params(labelsize=fp_tick.get_size_in_points(), colors=col)

            hmax = hits.max() or 1
            for r in range(rows):
                for c in range(cols):
                    if hits[r, c] > 0:
                        ax3.text(c, r, str(int(hits[r, c])),
                                 ha='center', va='center', fontproperties=fp_cell,
                                 color=_contrast_text_for(
                                     seq_cmap_name, hits[r, c] / hmax))
            cb_h = fig.colorbar(im_h, ax=ax3, fraction=0.046, pad=0.04)
            cb_h.set_label('Particles per neuron', fontproperties=fp_annot, color=col)
            cb_h.ax.tick_params(labelsize=fp_tick.get_size_in_points(), colors=col)
            dead = int((hits == 0).sum())
            if dead:
                ax3.text(0.02, 0.98, f"{dead} dead",
                         transform=ax3.transAxes,
                         ha='left', va='top', fontproperties=fp_annot,
                         color='#DC2626',
                         bbox=dict(fc='#FEF2F2', ec='#DC2626', pad=2))
        else:
            ax3.text(0.5, 0.5, 'Input not cached', ha='center', va='center',
                     fontproperties=fp_annot, color=_muted_color(cfg),
                     transform=ax3.transAxes)
            ax3.set_xticks([]); ax3.set_yticks([])

    ax_s = fig.add_subplot(rows_layout, cols_layout, positions['sizes'])
    unique_c = np.unique(data_labels[data_labels >= 0])
    per_ml = per_ml_active(cfg, input_data)
    meta = (input_data or {}).get('concentration_meta', {}) if per_ml else {}
    single_key = None
    if per_ml and isinstance(meta, dict) and len(meta) == 1:
        single_key = next(iter(meta))
    if per_ml:
        labels_ok = (sample_labels is not None
                     and len(np.asarray(sample_labels)) == len(data_labels))
        sample_labels = np.asarray(sample_labels) if labels_ok else None
        sizes = []
        for c in unique_c:
            mask = data_labels == c
            total = 0.0
            if single_key is not None:
                total = int(np.sum(mask)) * per_ml_factor(input_data, single_key)
            elif sample_labels is not None:
                members = sample_labels[mask]
                for sn in np.unique(members):
                    f = per_ml_factor(input_data, str(sn))
                    total += int(np.sum(members == sn)) * f
            sizes.append(total)
    else:
        sizes = [int(np.sum(data_labels == c)) for c in unique_c]
    colors = [CLUSTER_COLORS[int(c) % len(CLUSTER_COLORS)] for c in unique_c]
    bars = ax_s.bar([_cluster_label_short(c) for c in unique_c], sizes,
                    color=colors, edgecolor='white', linewidth=0.6, alpha=0.9)
    _smax = max(sizes) if sizes else 0
    for bar, sz in zip(bars, sizes):
        ax_s.text(bar.get_x() + bar.get_width() / 2,
                  bar.get_height() + (_smax * 0.01 if _smax else 0),
                  (format_per_ml(sz, Renderer.MATHTEXT, cfg) if per_ml else f'n={sz}'), ha='center', va='bottom',
                  fontproperties=fp_annot, color=col)
    _style_ax(ax_s, cfg, xlabel='Cluster',
              ylabel='Particles/mL' if per_ml else 'Particle count',
              title='SOM Cluster Sizes')
    ax_s.set_ylim(0, _smax * 1.3 if _smax else 1)
    noise = int(np.sum(data_labels == -1))
    if noise > 0:
        ax_s.text(0.98, 0.98, f'Noise: {noise}', transform=ax_s.transAxes,
                  ha='right', va='top', fontproperties=fp_annot, color='#DC2626',
                  bbox=dict(fc='#FEF2F2', ec='#DC2626', pad=3))

    X = getattr(som_obj, '_fit_X', None)
    if X is not None:
        try:
            qe = som_obj.get_quantization_error(X)
            qe_fp = _font_scale(cfg, 'annot')[0]
            qe_fp.set_style('italic')
            fig.text(0.99, 0.005, f"Quantization error: {qe:.4f}",
                     ha='right', va='bottom', fontproperties=qe_fp, color=col)
        except Exception:
            pass

    fig.tight_layout(pad=1.4)


class ClusteringSettingsDialog(QDialog):
    """Full settings dialog opened from right-click → Configure."""

    def __init__(self, config, parent=None, input_data=None):
        """Initialise the dialog and build the UI from the supplied config.

        Args:
            config (dict): Current node configuration dictionary; a shallow
                copy is taken so the original is not mutated until ``collect``
                is called and the caller applies the result.
            parent (QWidget | None): Optional parent widget.
            input_data (dict | None): Node input payload, used to detect whether
                a transport rate is available for particles-per-mL output.
        """
        super().__init__(parent)
        self.setWindowTitle("Clustering Analysis Settings")
        self.setMinimumWidth(480)
        self._cfg = dict(config)
        self._input_data = input_data
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
        self.y_axis_unit = QComboBox()
        self.y_axis_unit.addItem("Particle", "count")
        self.y_axis_unit.addItem("Particle per mL", "per_ml")
        _cu = self._cfg.get('y_axis_unit', 'count')
        self.y_axis_unit.setCurrentIndex(1 if _cu == 'per_ml' else 0)
        if not conc_meta_available(getattr(self, '_input_data', None)):
            _ix = self.y_axis_unit.findData('per_ml')
            _itm = self.y_axis_unit.model().item(_ix)
            if _itm is not None:
                _itm.setEnabled(False)
            if _cu == 'per_ml':
                self.y_axis_unit.setCurrentIndex(0)
        fl.addRow("Cluster size unit:", self.y_axis_unit)
        layout.addWidget(g)

        g = QGroupBox("Preprocessing")
        fl = QFormLayout(g)
        self.scaling = QComboBox()
        self.scaling.addItems(SCALING_OPTIONS)
        self.scaling.setCurrentText(self._cfg.get('scaling', 'CLR'))
        fl.addRow("Scaling:", self.scaling)

        self.dim_red = QComboBox()
        self.dim_red.addItems(DIM_REDUCTION_OPTIONS)
        self.dim_red.setCurrentText(self._cfg.get('dim_reduction', 'None'))
        fl.addRow("Dim. Reduction:", self.dim_red)

        self.n_comp = QSpinBox()
        self.n_comp.setRange(2, 100)
        self.n_comp.setValue(self._cfg.get('n_components', 2))
        fl.addRow("Components:", self.n_comp)

        self.filter_zeros = QCheckBox("Filter zero-only particles")
        self.filter_zeros.setChecked(self._cfg.get('filter_zeros', True))
        fl.addRow(self.filter_zeros)

        self.min_type_count = QSpinBox()
        self.min_type_count.setRange(1, 100000)
        self.min_type_count.setValue(
            self._cfg.get('min_particle_type_count', 5))
        self.min_type_count.setMaximumWidth(80)
        fl.addRow("Min. particles per type:", self.min_type_count)
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
        self._algo_pages = {}

        p0 = QWidget(); f0 = QFormLayout(p0); f0.setContentsMargins(4, 4, 4, 4)
        self.km_n_init = QSpinBox(); self.km_n_init.setRange(1, 50)
        self.km_n_init.setValue(self._cfg.get('kmeans_n_init', 10))
        self.km_max_iter = QSpinBox(); self.km_max_iter.setRange(50, 2000)
        self.km_max_iter.setValue(self._cfg.get('kmeans_max_iter', 300))
        f0.addRow("n_init:", self.km_n_init)
        f0.addRow("max_iter:", self.km_max_iter)
        self._algo_pages['K-Means'] = self.algo_stack.addWidget(p0)

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
            """Disable the metric picker when Ward linkage is selected.

            Args:
                txt (str): Currently selected linkage method name.
            """
            self.hier_metric.setEnabled(txt != 'ward')
            if txt == 'ward':
                self.hier_metric.setCurrentText('euclidean')
        self.hier_linkage.currentTextChanged.connect(_sync_hier_metric)
        _sync_hier_metric(self.hier_linkage.currentText())
        self._algo_pages['Hierarchical'] = self.algo_stack.addWidget(p1)

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
        self._algo_pages['DBSCAN'] = self.algo_stack.addWidget(p2)

        p8 = QWidget(); f8 = QFormLayout(p8); f8.setContentsMargins(4, 4, 4, 4)
        self.hdbscan_min_cluster = QSpinBox(); self.hdbscan_min_cluster.setRange(2, 200)
        self.hdbscan_min_cluster.setValue(self._cfg.get('hdbscan_min_cluster_size', 5))
        self.hdbscan_min_samp = QSpinBox(); self.hdbscan_min_samp.setRange(1, 100)
        self.hdbscan_min_samp.setValue(self._cfg.get('hdbscan_min_samples', 5))
        self.hdbscan_metric = QComboBox()
        self.hdbscan_metric.addItems(['euclidean', 'manhattan', 'cosine', 'l2'])
        self.hdbscan_metric.setCurrentText(self._cfg.get('hdbscan_metric', 'euclidean'))
        _hdbscan_warn = QLabel("⚠ Requires scikit-learn ≥ 1.3 or: pip install hdbscan")
        _hdbscan_warn.setStyleSheet("color:#D97706; font-size:10px;")
        _hdbscan_warn.setVisible(not _HDBSCAN_OK)
        f8.addRow(_hdbscan_warn)
        f8.addRow("min_cluster_size:", self.hdbscan_min_cluster)
        f8.addRow("min_samples:", self.hdbscan_min_samp)
        f8.addRow("metric:", self.hdbscan_metric)
        self._algo_pages['HDBSCAN'] = self.algo_stack.addWidget(p8)

        p3 = QWidget(); f3 = QFormLayout(p3); f3.setContentsMargins(4, 4, 4, 4)
        self.spec_n_neighbors = QSpinBox(); self.spec_n_neighbors.setRange(2, 50)
        self.spec_n_neighbors.setValue(self._cfg.get('spectral_n_neighbors', 10))
        self.spec_affinity = QComboBox()
        self.spec_affinity.addItems(['rbf', 'nearest_neighbors', 'cosine'])
        self.spec_affinity.setCurrentText(self._cfg.get('spectral_affinity', 'rbf'))
        f3.addRow("n_neighbors:", self.spec_n_neighbors)
        f3.addRow("affinity:", self.spec_affinity)
        self._algo_pages['Spectral'] = self.algo_stack.addWidget(p3)

        p9 = QWidget(); f9 = QFormLayout(p9); f9.setContentsMargins(4, 4, 4, 4)
        self.som_rows = QSpinBox(); self.som_rows.setRange(3, 30)
        self.som_rows.setValue(self._cfg.get('som_rows', 10))
        self.som_cols = QSpinBox(); self.som_cols.setRange(3, 30)
        self.som_cols.setValue(self._cfg.get('som_cols', 10))
        self.som_sigma = QDoubleSpinBox(); self.som_sigma.setRange(0.1, 10.0)
        self.som_sigma.setSingleStep(0.1); self.som_sigma.setDecimals(2)
        self.som_sigma.setValue(self._cfg.get('som_sigma', 1.0))
        self.som_lr = QDoubleSpinBox(); self.som_lr.setRange(0.01, 1.0)
        self.som_lr.setSingleStep(0.05); self.som_lr.setDecimals(3)
        self.som_lr.setValue(self._cfg.get('som_lr', 0.5))
        self.som_n_iter = QSpinBox(); self.som_n_iter.setRange(100, 20000)
        self.som_n_iter.setSingleStep(500)
        self.som_n_iter.setValue(self._cfg.get('som_n_iter', 2000))
        self.som_final_algo = QComboBox()
        self.som_final_algo.addItems([
            'Hierarchical (Ward)',
            'Hierarchical (Average)',
            'Hierarchical (Complete)',
            'K-Means',
            'Gaussian Mixture',
            'Spectral',
        ])
        self.som_final_algo.setCurrentText(
            self._cfg.get('som_final_algo', 'Hierarchical (Ward)'))
        self.som_cluster_cmap = QComboBox()
        self.som_cluster_cmap.addItems([
            'CLUSTER_COLORS', 'tab20', 'tab10', 'Set1', 'Set2', 'Set3',
            'Paired', 'Pastel1', 'Accent',
        ])
        self.som_cluster_cmap.setCurrentText(
            self._cfg.get('som_cluster_cmap', 'CLUSTER_COLORS'))
        self.som_seq_cmap = QComboBox()
        self.som_seq_cmap.addItems([
            'viridis', 'cividis', 'plasma', 'magma', 'inferno',
            'turbo', 'Blues', 'Greys',
        ])
        self.som_seq_cmap.setCurrentText(
            self._cfg.get('som_sequential_cmap', 'viridis'))
        self.som_show_u = QCheckBox("Show U-matrix")
        self.som_show_u.setChecked(self._cfg.get('som_show_u_matrix', True))
        self.som_show_hits = QCheckBox("Show hit-count map")
        self.som_show_hits.setChecked(self._cfg.get('som_show_hit_count', True))
        f9.addRow("Grid rows:", self.som_rows)
        f9.addRow("Grid cols:", self.som_cols)
        f9.addRow("Sigma (σ):", self.som_sigma)
        f9.addRow("Learning rate:", self.som_lr)
        f9.addRow("Iterations:", self.som_n_iter)
        f9.addRow("Final clustering:", self.som_final_algo)
        f9.addRow("Cluster colormap:", self.som_cluster_cmap)
        f9.addRow("Sequential colormap:", self.som_seq_cmap)
        f9.addRow(self.som_show_u)
        f9.addRow(self.som_show_hits)
        self._algo_pages['SOM'] = self.algo_stack.addWidget(p9)

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
        self._algo_pages['MiniBatch K-Means'] = self.algo_stack.addWidget(p4)

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
        self._algo_pages['Mean Shift'] = self.algo_stack.addWidget(p6)

        p_birch = QWidget(); f_birch = QFormLayout(p_birch)
        f_birch.setContentsMargins(4, 4, 4, 4)
        self.birch_threshold = QDoubleSpinBox(); self.birch_threshold.setRange(0.05, 5.0)
        self.birch_threshold.setSingleStep(0.05); self.birch_threshold.setDecimals(3)
        self.birch_threshold.setValue(self._cfg.get('birch_threshold', 0.5))
        self.birch_branching = QSpinBox(); self.birch_branching.setRange(10, 200)
        self.birch_branching.setValue(self._cfg.get('birch_branching_factor', 50))
        f_birch.addRow("threshold:", self.birch_threshold)
        f_birch.addRow("branching_factor:", self.birch_branching)
        self._algo_pages['Birch'] = self.algo_stack.addWidget(p_birch)

        p_optics = QWidget(); f_optics = QFormLayout(p_optics)
        f_optics.setContentsMargins(4, 4, 4, 4)
        self.optics_min_samp = QSpinBox(); self.optics_min_samp.setRange(2, 100)
        self.optics_min_samp.setValue(self._cfg.get('optics_min_samples', 5))
        self.optics_metric = QComboBox()
        self.optics_metric.addItems(['euclidean', 'manhattan', 'cosine', 'l1', 'l2'])
        self.optics_metric.setCurrentText(self._cfg.get('optics_metric', 'euclidean'))
        self.optics_cluster_method = QComboBox()
        self.optics_cluster_method.addItems(['xi', 'dbscan'])
        self.optics_cluster_method.setCurrentText(
            self._cfg.get('optics_cluster_method', 'xi'))
        f_optics.addRow("min_samples:", self.optics_min_samp)
        f_optics.addRow("metric:", self.optics_metric)
        f_optics.addRow("cluster_method:", self.optics_cluster_method)
        self._algo_pages['OPTICS'] = self.algo_stack.addWidget(p_optics)

        p_gmm = QWidget(); f_gmm = QFormLayout(p_gmm)
        f_gmm.setContentsMargins(4, 4, 4, 4)
        self.gmm_cov = QComboBox()
        self.gmm_cov.addItems(['full', 'tied', 'diag', 'spherical'])
        self.gmm_cov.setCurrentText(self._cfg.get('gmm_covariance_type', 'full'))
        f_gmm.addRow("covariance_type:", self.gmm_cov)
        self._algo_pages['Gaussian Mixture'] = self.algo_stack.addWidget(p_gmm)

        def _switch_page(text):
            """Show the settings panel for the chosen algorithm.

            Args:
                text (str): Algorithm name as it appears in ``ALGORITHMS``.
            """
            idx = self._algo_pages.get(text, 0)
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
        self.max_k.setRange(3, 500)
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
                                  list(DEFAULT_METRICS))
        self.metric_cbs = {}
        for m in METRICS:
            cb = QCheckBox(m)
            cb.setChecked(m in enabled_m)
            self.metric_cbs[m] = cb
            fl.addRow(cb)

        bs_w = QWidget()
        bs_hl = QHBoxLayout(bs_w)
        bs_hl.setContentsMargins(0, 0, 0, 0)
        bs_hl.setSpacing(6)
        self.bs_n = QSpinBox()
        self.bs_n.setRange(10, 1000)
        self.bs_n.setSingleStep(10)
        self.bs_n.setValue(self._cfg.get('bootstrap_n', 50))
        self.bs_n.setMaximumWidth(70)
        self.bs_seed = QSpinBox()
        self.bs_seed.setRange(0, 2_000_000_000)
        self.bs_seed.setValue(self._cfg.get('bootstrap_seed', 42))
        self.bs_seed.setMaximumWidth(90)
        bs_hl.addWidget(QLabel("n ="))
        bs_hl.addWidget(self.bs_n)
        bs_hl.addWidget(QLabel("seed ="))
        bs_hl.addWidget(self.bs_seed)
        bs_hl.addStretch()
        fl.addRow("Bootstrap:", bs_w)

        layout.addWidget(g)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def collect(self) -> dict:
        """Collect all widget values into a configuration dictionary.

        Returns:
            dict: Updated configuration with every setting reflected from the
                current widget state; safe to pass directly to
                ``node.config.update()``.
        """
        out = dict(self._cfg)
        out['data_type_display'] = self.data_type.currentText()
        out['y_axis_unit'] = self.y_axis_unit.currentData()
        out['scaling'] = self.scaling.currentText()
        out['dim_reduction'] = self.dim_red.currentText()
        out['n_components'] = self.n_comp.value()
        out['filter_zeros'] = self.filter_zeros.isChecked()
        out['min_particle_type_count'] = self.min_type_count.value()
        out['min_clusters'] = self.min_k.value()
        out['max_clusters'] = self.max_k.value()
        out['auto_select_k'] = self.auto_k.isChecked()
        out['enabled_metrics'] = [m for m, cb in self.metric_cbs.items() if cb.isChecked()]
        out['bootstrap_n']    = self.bs_n.value()
        out['bootstrap_seed'] = self.bs_seed.value()

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

        out['meanshift_auto_bw']      = self.ms_auto_bw.isChecked()
        out['meanshift_bandwidth']    = self.ms_bandwidth.value()
        out['meanshift_min_bin_freq'] = self.ms_min_bin_freq.value()

        out['hdbscan_min_cluster_size'] = self.hdbscan_min_cluster.value()
        out['hdbscan_min_samples']      = self.hdbscan_min_samp.value()
        out['hdbscan_metric']           = self.hdbscan_metric.currentText()

        out['som_rows']       = self.som_rows.value()
        out['som_cols']       = self.som_cols.value()
        out['som_sigma']      = self.som_sigma.value()
        out['som_lr']         = self.som_lr.value()
        out['som_n_iter']     = self.som_n_iter.value()
        out['som_final_algo']      = self.som_final_algo.currentText()
        out['som_cluster_cmap']    = self.som_cluster_cmap.currentText()
        out['som_sequential_cmap'] = self.som_seq_cmap.currentText()
        out['som_show_u_matrix']   = self.som_show_u.isChecked()
        out['som_show_hit_count']  = self.som_show_hits.isChecked()

        out['birch_threshold']        = self.birch_threshold.value()
        out['birch_branching_factor'] = self.birch_branching.value()

        out['optics_min_samples']    = self.optics_min_samp.value()
        out['optics_metric']         = self.optics_metric.currentText()
        out['optics_cluster_method'] = self.optics_cluster_method.currentText()

        out['gmm_covariance_type'] = self.gmm_cov.currentText()

        return out


def _font_scale(cfg, role='label'):
    """Return a (FontProperties, color) pair scaled for a given text role.

    All figure text derives its family, style, weight and color from the user's
    font settings via :func:`make_font_properties`.  This helper additionally
    applies a consistent *relative* size offset per role so the visual
    hierarchy (title > label > tick/legend > cell) scales proportionally with
    the chosen base size.  For example, at base size 12 the legend renders at
    10; at base size 16 it renders at 14.

    Role offsets (relative to the base size, floored so text never vanishes):
        * ``'title'``  → base + 1, bold
        * ``'label'``  → base + 0
        * ``'tick'``   → base - 2
        * ``'legend'`` → base - 3
        * ``'annot'``  → base - 2
        * ``'cell'``   → base - 5

    Args:
        cfg (dict): Configuration dictionary providing font settings.
        role (str): One of ``'title'``, ``'label'``, ``'tick'``, ``'legend'``,
            ``'annot'`` or ``'cell'``.

    Returns:
        tuple[matplotlib.font_manager.FontProperties, str]: A freshly-copied
            FontProperties sized for the role, and the text color string.
    """
    offsets = {'title': 1, 'label': 0, 'tick': -2,
               'legend': -3, 'annot': -2, 'cell': -5}
    floors = {'title': 8, 'label': 7, 'tick': 6,
              'legend': 6, 'annot': 6, 'cell': 5}
    fp = make_font_properties(cfg).copy()
    fc = get_font_config(cfg)
    base = fp.get_size_in_points() or fc['size']
    fp.set_size(max(base + offsets.get(role, 0), floors.get(role, 6)))
    if role == 'title':
        fp.set_weight('bold')
    return fp, _text_color(cfg)


def _text_color(cfg):
    """Resolve the colour for figure text in a theme-consistent way.

    The user's explicit font colour (``font_color``) always wins. When it is
    left at the default black (``#000000``) — i.e. the user never overrode it —
    the active theme's text colour is used instead, so titles, labels, ticks
    and annotations read correctly in both light and dark mode across every
    figure in the dialog.

    Args:
        cfg (dict): Configuration dictionary.

    Returns:
        str: Hex colour string for figure text.
    """
    fc = get_font_config(cfg)
    user_col = (fc.get('color') or '').strip().lower()
    if user_col not in ('', '#000000', '#000', 'black'):
        return fc['color']
    return _plot_theme(cfg)['text']


def _muted_color(cfg):
    """Theme-aware muted colour for placeholder / empty-state text."""
    pal = cfg.get('_theme') or _current_plot_palette()
    return pal.get('text_muted', '#64748B')


def _empty_message(ax, cfg, text):
    """Draw a centered, theme- and font-consistent placeholder message.

    Used for empty/no-data states so they share the same font family and a
    legible muted colour across every figure instead of a bare hardcoded
    ``fontsize`` + grey.

    Args:
        ax (matplotlib.axes.Axes): Target axes.
        cfg (dict): Configuration dictionary.
        text (str): Message to display.
    """
    fp_lbl, _ = _font_scale(cfg, 'label')
    ax.text(0.5, 0.5, text, ha='center', va='center',
            transform=ax.transAxes,
            fontproperties=fp_lbl, color=_muted_color(cfg))


def _plot_theme(cfg):
    """Return plot colours (face, grid, text) for the active theme.

    Reads the palette stashed in ``cfg['_theme']`` by the dialog's
    ``_apply_theme``; falls back to light-mode values when absent (e.g. when a
    figure is drawn before the theme is applied or outside the dialog).

    Args:
        cfg (dict): Configuration dictionary.

    Returns:
        dict: Keys ``face``, ``grid``, ``text``, ``dark`` (bool).
    """
    pal = cfg.get('_theme') or _current_plot_palette()
    return {
        'face': pal.get('plot_face', '#FAFAFA'),
        'grid': pal.get('grid', '#CBD5E1'),
        'text': pal.get('text', '#1E293B'),
        'border': pal.get('border_str', '#CBD5E1'),
        'dark': bool(pal.get('dark', cfg.get('_dark', False))),
    }


def _style_ax(ax, cfg, xlabel='', ylabel='', title=''):
    """Apply consistent visual styling to a matplotlib Axes.

    Args:
        ax (matplotlib.axes.Axes): Target axes to style.
        cfg (dict): Configuration dictionary providing font settings.
        xlabel (str): X-axis label text; omitted when empty.
        ylabel (str): Y-axis label text; omitted when empty.
        title (str): Axes title text; omitted when empty.
    """
    th = _plot_theme(cfg)
    fp_lbl, _ = _font_scale(cfg, 'label')
    fp_title, _ = _font_scale(cfg, 'title')
    fp_tick, _ = _font_scale(cfg, 'tick')
    col = th['text']
    ax.set_facecolor(th['face'])
    ax.grid(True, alpha=0.25, linewidth=0.5, color=th['grid'])
    for spine in ax.spines.values():
        spine.set_color(th['border'])
        spine.set_linewidth(0.8)
    if xlabel:
        ax.set_xlabel(xlabel, fontproperties=fp_lbl, color=col)
    if ylabel:
        ax.set_ylabel(ylabel, fontproperties=fp_lbl, color=col)
    if title:
        ax.set_title(title, fontproperties=fp_title, color=col, pad=10)
    ax.tick_params(labelsize=fp_tick.get_size_in_points(), colors=col)
    for lab in (*ax.get_xticklabels(), *ax.get_yticklabels()):
        lab.set_fontproperties(fp_tick)
        lab.set_color(col)


_ELEMENT_PALETTE = [
    '#2563EB', '#DC2626', '#16A34A', '#D97706', '#7C3AED',
    '#0891B2', '#DB2777', '#65A30D', '#EA580C', '#4F46E5',
    '#0D9488', '#C026D3', '#CA8A04', '#E11D48', '#2DD4BF',
    '#6366F1', '#F59E0B', '#10B981', '#EF4444', '#8B5CF6',
    '#0EA5E9', '#A855F7', '#F97316', '#84CC16', '#06B6D4',
]


def _element_color(element, all_elements_sorted):
    """Return a deterministic colour for an element symbol.

    The palette index is the element's position in the mass-sorted list, so
    the same symbol always maps to the same colour within a given dataset.
    That keeps the strip legend and the right-side panel visually
    consistent across re-draws.

    Args:
        element (str): Element symbol to look up.
        all_elements_sorted (list[str]): Full element list sorted by mass.
    Returns:
        str: Hex colour string from ``_ELEMENT_PALETTE``.
    """
    try:
        idx = all_elements_sorted.index(element)
    except ValueError:

        idx = abs(hash(element)) % len(_ELEMENT_PALETTE)
    return _ELEMENT_PALETTE[idx % len(_ELEMENT_PALETTE)]


def _cluster_label_short(cid):
    """Return a user-facing display tag for a cluster ID.

    sklearn returns 0-indexed labels; displayed labels are shifted by +1 so
    the first cluster reads C1. Noise (label -1) renders as 'Noise'. Internal
    dict keys and label arrays stay 0-based — this only affects what the user sees. Noise
    (label -1, from the density-based algorithms) renders as 'Noise'.

    Args:
        cid (int | str): Internal cluster identifier.
    Returns:
        str: Display label such as 'C1', 'C2', or 'Noise'.
    """
    try:
        c = int(cid)
    except (TypeError, ValueError):
        return f'C{cid}'
    return 'Noise' if c < 0 else f'C{c + 1}'


def _cluster_per_ml_value(cd, input_data):
    """Convert a cluster's particle count to particles per mL.

    Uses the per-sample breakdown when available (multi-sample input) so each
    sample's particles are scaled by its own transport factor, mirroring the
    heatmap convention. Falls back to ``particle_count`` times the single
    sample factor otherwise.

    Args:
        cd (dict): Cluster characterisation dict (holds ``particle_count`` and
            optionally ``sample_breakdown``).
        input_data (dict | None): Node input payload carrying concentration
            metadata.

    Returns:
        float: Concentration in particles per mL for this cluster.
    """
    meta = (input_data or {}).get('concentration_meta', {})
    breakdown = cd.get('sample_breakdown') or {}
    if isinstance(meta, dict) and len(breakdown) > 1:
        total = 0.0
        for sname, info in breakdown.items():
            total += int(info.get('count', 0)) * per_ml_factor(input_data, str(sname))
        return total
    single_key = None
    if isinstance(meta, dict) and len(meta) == 1:
        single_key = next(iter(meta))
    elif isinstance(meta, dict) and len(breakdown) == 1:
        single_key = next(iter(breakdown))
    return int(cd.get('particle_count', 0)) * per_ml_factor(input_data, single_key)


def _cluster_size_str(cd, cfg, input_data, renderer=Renderer.MATHTEXT):
    """Return the size annotation for a cluster honouring the y-axis unit.

    When the per-mL unit is active a transport-scaled concentration string is
    returned; otherwise the plain comma-grouped particle count is returned.

    Args:
        cd (dict): Cluster characterisation dict.
        cfg (dict): Plot configuration.
        input_data (dict | None): Node input payload.
        renderer (Renderer): Renderer for the per-mL formatter.

    Returns:
        str: Formatted size string (no surrounding parentheses).
    """
    if per_ml_active(cfg, input_data):
        return format_per_ml(_cluster_per_ml_value(cd, input_data), renderer, cfg)
    return f"{int(cd.get('particle_count', 0)):,}"


def _build_cluster_label(cd, threshold_pct=0.1, max_elems=5, include_count=True,
                         label_mode='Symbol', cfg=None, input_data=None):
    """Build a "Fe, O, Si (1,234)" style row label from a cluster's
    characterisation dict, honouring the user's threshold + cap settings.

    Uses ``composition`` (already sorted descending) if present, else
    falls back to ``dominant_elements``. Caps the element list so a really
    mixed cluster doesn't produce a 12-element label that breaks the axis.

    Args:
        include_count: When False, returns the bare element signature with no
            trailing "(count)". The heatmap renderer appends the count itself,
            so the count-free form avoids a doubled "(245) (245)" label.
        label_mode: Element label style ('Symbol' | 'Mass + Symbol' |
            'Atomic Notation'). Applied to every element token so the row
            labels match the rest of the figures.
    

    Returns:
        str: Formatted label such as ``'Fe, O, Si (1,234)'``.
    """
    sig = cd.get('composition') or []
    keep = [e for e, p in sig if p >= threshold_pct]
    if not keep:
        dom = cd.get('dominant_elements') or []
        keep = [e for e, _ in dom[:1]] or ['?']
    ellipsis = len(keep) > max_elems
    if ellipsis:
        keep = keep[:max_elems]
    disp = [format_element_label(e, label_mode, Renderer.MATHTEXT) for e in keep]
    if ellipsis:
        disp.append('…')
    sig_str = ', '.join(disp)
    if not include_count:
        return sig_str
    if cfg is not None and per_ml_active(cfg, input_data):
        return f"{sig_str} ({_cluster_size_str(cd, cfg, input_data)})"
    n = cd.get('particle_count', 0)
    return f"{sig_str} ({n:,})"


def _cluster_primary(cd):
    """Return the primary dominant element of a cluster.

    Args:
        cd (dict): Cluster characterisation dict.

    Returns:
        str: Element symbol of the most dominant element, or '?' when none
            is available.
    """
    dom = cd.get('dominant_elements') or []
    if dom:
        return dom[0][0]
    sig = cd.get('composition') or []
    if sig:
        return sig[0][0]
    return '?'


def _order_clusters(char_for_algo, group_by_dominant=True):
    """Return cluster IDs in display order.

    With ``group_by_dominant=True`` (default), clusters sharing the same
    primary dominant element are placed adjacent (Fe-block, then Ti-block,
    etc.); within a group, sorted by particle count descending. Returns
    a list of ``(cid, primary_elem)`` tuples so the caller can insert
    small visual gaps between groups.
    

    Args:
        char_for_algo (dict): ``{cluster_id: characterisation_dict}`` for one
            algorithm.
        group_by_dominant (bool): Whether to group by primary element.

    Returns:
        list[tuple[int, str]]: Ordered ``(cluster_id, primary_element)`` pairs.
    """
    items = list(char_for_algo.items())
    if not group_by_dominant:
        items.sort(key=lambda kv: kv[1].get('particle_count', 0), reverse=True)
        return [(cid, _cluster_primary(cd)) for cid, cd in items]

    buckets = {}
    for cid, cd in items:
        buckets.setdefault(_cluster_primary(cd), []).append((cid, cd))
    bucket_totals = {
        elem: sum(cd.get('particle_count', 0) for _, cd in lst)
        for elem, lst in buckets.items()
    }
    out = []
    for elem in sorted(buckets, key=lambda e: bucket_totals[e], reverse=True):
        lst = sorted(buckets[elem],
                     key=lambda kv: kv[1].get('particle_count', 0),
                     reverse=True)
        for cid, cd in lst:
            out.append((cid, elem))
    return out


def _build_sample_data_from_characterisation(char_for_algo, elements,
                                             threshold_pct=0.1,
                                             max_elems=5,
                                             group_by_dominant=True,
                                             label_mode='Symbol',
                                             input_data=None):
    """Synthesise a ``sample_data`` dict from per-cluster characterisation data.

    Each cluster becomes one row in the heatmap. The row's ``total_values``
    carries the per-element mean wrapped in a single-element list so that
    ``draw_combinations_heatmap``'s internal ``np.mean(vals)`` collapses
    back to the original mean.

    Args:
        char_for_algo (dict): ``{cluster_id: characterisation_dict}`` for one
            algorithm.
        elements (list[str]): Full element list used as heatmap columns.
        threshold_pct (float): Minimum percentage threshold for row labels.
        max_elems (int): Maximum elements shown per row label.
        group_by_dominant (bool): Whether to group rows by primary element.
        label_mode (str): Element label style for row label tokens.

    Returns:
        dict: Mapping of row label strings to dicts with keys ``count``,
            ``particle_count``, and ``total_values``.
    """
    ordered = _order_clusters(char_for_algo, group_by_dominant=group_by_dominant)
    out = {}
    for cid, _primary in ordered:
        cd = char_for_algo[cid]

        label = _build_cluster_label(cd, threshold_pct, max_elems,
                                     include_count=False,
                                     label_mode=label_mode)

        if label in out:
            label = f"{label} #{cid}"
        total_values = {}
        estats = cd.get('element_stats', {})
        for el in elements:
            mean = estats.get(el, {}).get('mean', 0)
            if mean and mean > 0:
                total_values[el] = [float(mean)]
        out[label] = {
            'count': cd.get('particle_count', 0),
            'particle_count': cd.get('particle_count', 0),
            'pml': _cluster_per_ml_value(cd, input_data),
            'total_values': total_values,
        }
    return out


def _draw_composition_strips(ax, char_for_algo, elements, cfg,
                              algo_name='', input_data=None):
    """Draw one horizontal stacked bar per cluster showing mass composition.

    Each bar is normalised to 100% so segment widths read as composition
    proportions. Rows are grouped by primary dominant element with a small
    visual gap between groups when ``overview_group_by_dominant`` is enabled.

    Args:
        ax (matplotlib.axes.Axes): Target axes.
        char_for_algo (dict): ``{cluster_id: characterisation_dict}`` for one
            algorithm.
        elements (list[str]): Element list; used for colour assignment.
        cfg (dict): Configuration dictionary.
        algo_name (str): Algorithm name appended to the axes title.
    """
    threshold = cfg.get('display_min_pct', 1.0)
    max_elems = int(cfg.get('display_max_isotopes', 4))
    group = cfg.get('overview_group_by_dominant', True)
    fp_title, col = _font_scale(cfg, 'title')
    fp_lbl, _ = _font_scale(cfg, 'label')
    fp_tick, _ = _font_scale(cfg, 'tick')
    fp_legend, _ = _font_scale(cfg, 'legend')
    fp_cell, _ = _font_scale(cfg, 'cell')

    lm = cfg.get('label_mode', cfg.get('overview_label_mode', 'Symbol'))

    ordered = _order_clusters(char_for_algo, group_by_dominant=group)
    if not ordered:
        ax.text(0.5, 0.5, 'No clusters to display',
                ha='center', va='center', transform=ax.transAxes,
                fontproperties=fp_lbl, color=_muted_color(cfg))
        return

    sorted_elements = sort_elements_by_mass(list(elements))

    y_pos = []
    labels = []
    primaries = []
    prev = None
    cursor = 0.0
    for cid, primary in ordered:
        if prev is not None and primary != prev and group:
            cursor += 0.5
        cd = char_for_algo[cid]
        y_pos.append(cursor)
        labels.append(_build_cluster_label(
            cd, threshold, max_elems,
            label_mode=cfg.get('label_mode',
                               cfg.get('overview_label_mode', 'Symbol')),
            cfg=cfg, input_data=input_data))
        primaries.append(primary)
        cursor += 1.0
        prev = primary

    rendered_elements = set()
    for (cid, _), y in zip(ordered, y_pos):
        cd = char_for_algo[cid]

        estats = cd.get('element_stats') or {}
        raw = {e: float(estats.get(e, {}).get('mean', 0.0) or 0.0)
               for e in sorted_elements}
        raw_total = sum(v for v in raw.values() if v > 0)
        if raw_total > 0:
            pcts = {e: (v / raw_total * 100.0) for e, v in raw.items() if v > 0}
        else:
            pcts = cd.get('element_pcts') or {}

        ordered_pcts = [(e, pcts.get(e, 0.0)) for e in sorted_elements
                        if pcts.get(e, 0.0) > 0]
    
        kept = [(e, p) for e, p in ordered_pcts if p >= threshold]
        if not kept and ordered_pcts:
            kept = ordered_pcts[:1]
        total = sum(p for _, p in kept) or 1.0
        kept = [(e, p / total * 100.0) for e, p in kept]

        left = 0.0
        for elem, pct in kept:
            color = _element_color(elem, sorted_elements)
            ax.barh(y, pct, left=left, height=0.85, color=color,
                    edgecolor='white', linewidth=0.6)
            rendered_elements.add(elem)

            if pct >= 8:
                t = ax.text(left + pct / 2, y,
                            format_element_label(elem, lm, Renderer.MATHTEXT),
                            ha='center', va='center',
                            color='white', fontproperties=fp_cell)
                t.set_fontweight('bold')
            left += pct

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, color=col)
    for lab in ax.get_yticklabels():
        lab.set_fontproperties(fp_tick)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(['0%', '25%', '50%', '75%', '100%'], color=col)
    for lab in ax.get_xticklabels():
        lab.set_fontproperties(fp_tick)
    dt_label = cfg.get('data_type_display', 'Counts')
    ax.set_xlabel(f'Composition (% of cluster {dt_label.lower()})',
                  fontproperties=fp_lbl, color=col)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    ax.grid(axis='x', alpha=0.25, linewidth=0.5, color=_plot_theme(cfg)['grid'])
    ax.set_axisbelow(True)
    ax.tick_params(colors=col)

    legend_elems = [e for e in sorted_elements if e in rendered_elements]
    if legend_elems:
        from matplotlib.patches import Patch
        handles = [Patch(facecolor=_element_color(e, sorted_elements),
                         edgecolor='white',
                         label=format_element_label(e, lm,
                                                    Renderer.MATHTEXT))
                   for e in legend_elems]
        ax.legend(handles=handles,
                  loc='lower center',
                  bbox_to_anchor=(0.5, 1.0),
                  ncol=min(len(handles), 12),
                  frameon=False,
                  prop=fp_legend,
                  handlelength=1.0,
                  handletextpad=0.5,
                  columnspacing=1.2,
                  borderaxespad=0.3)


def _draw_sample_share_strip(ax, char_for_algo, sample_names, cfg,
                              group_by_dominant=True):
    """Draw a per-cluster sample-fraction strip for multi-sample input.

    Each horizontal bar represents one cluster; segments are coloured by
    source sample and widths represent the fraction of particles from each
    sample. Rows are aligned with ``_draw_composition_strips``.

    Args:
        ax (matplotlib.axes.Axes): Target axes (right panel).
        char_for_algo (dict): ``{cluster_id: characterisation_dict}`` for one
            algorithm.
        sample_names (list[str]): Ordered list of sample identifiers.
        cfg (dict): Configuration dictionary.
        group_by_dominant (bool): Whether to apply the same group gaps as
            the left strip panel.
    """
    fp_title, col = _font_scale(cfg, 'title')
    fp_tick, _ = _font_scale(cfg, 'tick')
    fp_legend, _ = _font_scale(cfg, 'legend')
    ordered = _order_clusters(char_for_algo,
                              group_by_dominant=group_by_dominant)


    sample_colors = {sn: DEFAULT_SAMPLE_COLORS[i % len(DEFAULT_SAMPLE_COLORS)]
                     for i, sn in enumerate(sample_names)}

    y_pos = []
    prev = None
    cursor = 0.0
    for cid, primary in ordered:
        if prev is not None and primary != prev and group_by_dominant:
            cursor += 0.5
        y_pos.append(cursor)
        cursor += 1.0
        prev = primary

    for (cid, _), y in zip(ordered, y_pos):
        cd = char_for_algo[cid]
        breakdown = cd.get('sample_breakdown') or {}
        total = sum(d.get('count', 0) for d in breakdown.values()) or 1
        left = 0.0
        for sn in sample_names:
            d = breakdown.get(sn) or breakdown.get(str(sn)) or {}
            frac = d.get('count', 0) / total * 100.0
            if frac <= 0:
                continue
            ax.barh(y, frac, left=left, height=0.85,
                    color=sample_colors[sn], edgecolor='white',
                    linewidth=0.6)
            left += frac

    ax.set_yticks([])
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 50, 100])
    ax.set_xticklabels(['0%', '50%', '100%'], color=col)
    for lab in ax.get_xticklabels():
        lab.set_fontproperties(fp_tick)
    ax.set_title('Sample share', fontproperties=fp_title, color=col, pad=10)
    ax.tick_params(colors=col)
    ax.invert_yaxis()
    for spine in ('top', 'right', 'left'):
        ax.spines[spine].set_visible(False)
    ax.grid(axis='x', alpha=0.25, linewidth=0.5, color=_plot_theme(cfg)['grid'])
    ax.set_axisbelow(True)

    from matplotlib.patches import Patch
    handles = [Patch(facecolor=sample_colors[sn], edgecolor='white', label=sn)
               for sn in sample_names]
    ax.legend(handles=handles, loc='upper center',
              bbox_to_anchor=(0.5, -0.12),
              ncol=min(len(handles), 3), frameon=False,
              prop=fp_legend)


def _draw_detection_panel(ax, char_for_algo, selected_elements, cfg,
                           group_by_dominant=True, input_data=None):
    """Draw per-cluster real detection counts for selected elements.

    For each cluster, shows ``particle_count × frequency[elem]`` — the
    number of particles where ``elem`` was actually detected. Falls back
    to a plain cluster-size bar when no elements are selected.

    Args:
        ax (matplotlib.axes.Axes): Target axes (right panel).
        char_for_algo (dict): ``{cluster_id: characterisation_dict}`` for one
            algorithm.
        selected_elements (list[str]): Elements to validate; empty list
            triggers the cluster-size fallback.
        cfg (dict): Configuration dictionary.
        group_by_dominant (bool): Whether to apply group gaps matching
            the left strip panel.
    """
    fp_title, col = _font_scale(cfg, 'title')
    fp_lbl, _ = _font_scale(cfg, 'label')
    fp_annot, _ = _font_scale(cfg, 'annot')
    metric = cfg.get('overview_panel_metric', 'Detections')
    ordered = _order_clusters(char_for_algo,
                              group_by_dominant=group_by_dominant)
    sel = list(selected_elements or [])

    y_pos = []
    prev = None
    cursor = 0.0
    for cid, primary in ordered:
        if prev is not None and primary != prev and group_by_dominant:
            cursor += 0.5
        y_pos.append(cursor)
        cursor += 1.0
        prev = primary

    per_ml = per_ml_active(cfg, input_data)
    if not sel:
        sizes = [(_cluster_per_ml_value(char_for_algo[cid], input_data)
                  if per_ml else char_for_algo[cid].get('particle_count', 0))
                 for cid, _ in ordered]
        all_elements = sorted({
            _cluster_primary(char_for_algo[cid]) for cid, _ in ordered
        })
        for (cid, _), y, sz in zip(ordered, y_pos, sizes):
            primary = _cluster_primary(char_for_algo[cid])
            color = _element_color(primary, all_elements) if primary != '?' else '#94A3B8'
            ax.barh(y, sz, left=0, height=0.85, color=color,
                    edgecolor='white', linewidth=0.6)
            txt = (format_per_ml(sz, Renderer.MATHTEXT, cfg) if per_ml
                   else f'{sz:,}')
            ax.text(sz, y, f' {txt}', va='center', ha='left',
                    fontproperties=fp_annot, color=col)
        ax.set_yticks([])
        ax.set_xlabel('Particles/mL' if per_ml else 'Particle count',
                      fontproperties=fp_lbl, color=col)
        ax.set_title('Cluster sizes', fontproperties=fp_title, color=col, pad=10)
        ax.tick_params(colors=col)
        if sizes:
            ax.set_xlim(0, max(sizes) * 1.18)
        ax.invert_yaxis()
        for spine in ('top', 'right', 'left'):
            ax.spines[spine].set_visible(False)
        ax.grid(axis='x', alpha=0.25, linewidth=0.5, color=_plot_theme(cfg)['grid'])
        ax.set_axisbelow(True)
        return

    sorted_elements = sort_elements_by_mass(sel)
    n_sel = len(sorted_elements)
    bar_h = 0.85 / max(n_sel, 1)

    is_pct = metric == 'Detections %'
    is_mean = metric == 'Mean'

    max_val = 0.0
    for (cid, _), y in zip(ordered, y_pos):
        cd = char_for_algo[cid]
        n = cd.get('particle_count', 0)
        n_scaled = _cluster_per_ml_value(cd, input_data) if per_ml else n
        estats = cd.get('element_stats', {})
        for i, elem in enumerate(sorted_elements):
            es = estats.get(elem, {})
            freq = es.get('frequency', 0.0)
            mean = es.get('mean', 0.0)
            if is_pct:
                value = freq * 100.0
            elif is_mean:
                value = mean
            else:
                value = freq * n_scaled
            max_val = max(max_val, value)
            color = _element_color(elem, sorted_elements)
            yi = y - 0.425 + (i + 0.5) * bar_h
            ax.barh(yi, value, left=0, height=bar_h * 0.92, color=color,
                    edgecolor='white', linewidth=0.4)

            if value > 0:
                sym = format_element_label(
                    elem,
                    cfg.get('label_mode',
                            cfg.get('overview_label_mode', 'Symbol')),
                    Renderer.MATHTEXT)
                if is_pct:
                    vtxt = f'{value:.1f}%'
                elif is_mean:
                    vtxt = f'{value:.2f}'
                elif per_ml:
                    vtxt = format_per_ml(value, Renderer.MATHTEXT, cfg)
                else:
                    vtxt = f'{int(round(value)):,}'
                ax.text(value, yi, f'  {sym} ({vtxt})', va='center', ha='left',
                        fontproperties=fp_annot, color=col)

    ax.set_yticks([])
    if is_pct:
        ax.set_xlabel('Detection frequency (%)',
                      fontproperties=fp_lbl, color=col)
        ax.set_xlim(0, 125)
    elif is_mean:
        ax.set_xlabel('Mean per particle',
                      fontproperties=fp_lbl, color=col)
        if max_val > 0:
            ax.set_xlim(0, max_val * 1.30)
    else:
        ax.set_xlabel('Detected particles/mL' if per_ml else 'Detected particles',
                      fontproperties=fp_lbl, color=col)
        if max_val > 0:
            ax.set_xlim(0, max_val * 1.30)
    ax.set_title('Real detections', fontproperties=fp_title, color=col, pad=10)
    ax.tick_params(colors=col)
    ax.invert_yaxis()
    for spine in ('top', 'right', 'left'):
        ax.spines[spine].set_visible(False)
    ax.grid(axis='x', alpha=0.25, linewidth=0.5, color=_plot_theme(cfg)['grid'])
    ax.set_axisbelow(True)


def _draw_evaluation(fig, eval_results, cfg, optimal_k=None,
                     view_algo='All Algorithms',
                     optimal_per_metric=None, selected_metric=None):
    """Draw evaluation metric curves on a matplotlib Figure.
    Args:
        fig (Any): The fig.
        eval_results (Any): The eval results.
        cfg (Any): The cfg.
        optimal_k (Any): Currently-selected K (kept for backward compat).
        view_algo (Any): Algorithm filter.
        optimal_per_metric (dict|None): {metric_label: k} suggested per metric.
        selected_metric (str|None): Which metric's K is the user-active choice.
    """
    fig.clear()

    enabled_metrics = cfg.get('enabled_metrics',
                              list(DEFAULT_METRICS))
    active = [(m, METRIC_KEYS[m][0], METRIC_KEYS[m][1])
              for m in enabled_metrics if m in METRIC_KEYS]

    if not active:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, 'No metrics selected', ha='center', va='center',
                fontproperties=_font_scale(cfg, 'label')[0],
                color=_muted_color(cfg), transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        return

    algos = list(eval_results.keys()) if view_algo == 'All Algorithms' else (
        [view_algo] if view_algo in eval_results else [])

    if not algos:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, 'No algorithm data', ha='center', va='center',
                fontproperties=_font_scale(cfg, 'label')[0],
                color=_muted_color(cfg), transform=ax.transAxes)
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

    for i, (metric_label, metric_name, metric_key) in enumerate(active):
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

        panel_opt_k = None
        if optimal_per_metric and metric_label in optimal_per_metric:
            panel_opt_k = optimal_per_metric[metric_label]
            is_active = (metric_label == selected_metric)
            ax.axvline(
                panel_opt_k,
                color='#DC2626' if is_active else '#94A3B8',
                linestyle='--',
                linewidth=2.0 if is_active else 1.0,
                alpha=0.9 if is_active else 0.55,
                label=(f'{metric_label} K={panel_opt_k}'
                       + ('  ★ selected' if is_active else '')),
            )
        elif optimal_k is not None:
            ax.axvline(optimal_k, color='#DC2626', linestyle='--',
                       linewidth=1.5, alpha=0.7,
                       label=f'Optimal K={optimal_k}')

        title = metric_name + (f'  →  K={panel_opt_k}' if panel_opt_k is not None else '')
        _style_ax(ax, cfg, xlabel='Number of Clusters (K)',
                  ylabel=metric_name, title=title)

        leg = ax.legend(prop=_font_scale(cfg, 'legend')[0],
                        loc='best', framealpha=0.9, edgecolor='#CBD5E1')
        if leg:
            leg.get_frame().set_linewidth(0.5)

        ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    total = rows * cols
    for j in range(n, total):
        fig.add_subplot(rows, cols, j + 1).set_visible(False)

    fig.tight_layout(pad=1.5)


def _draw_evaluation_per_sample(fig, per_sample_eval, cfg,
                                per_sample_optk=None,
                                view_algo='All Algorithms',
                                selected_metric=None):
    """Draw per-sample evaluation curves as a single metric × sample grid.

    Multi-sample verification view. Layout: one COLUMN per sample, one ROW per
    enabled metric. Inside each cell, one line per algorithm (same colours and
    markers as the pooled :func:`_draw_evaluation`) plus a dashed vertical line
    at *that sample's own* optimal K for the row's metric. A single shared
    legend lists the algorithms. Everything lands in this one figure.

    Cells auto-scale their y-axis independently — the point of comparison is the
    shape of each curve and where each sample's K lands, not absolute values
    across samples (the metrics aren't on a common scale between subsets).

    Args:
        fig (Figure): Target figure (cleared and redrawn).
        per_sample_eval (dict): ``{sample_name: eval_results_dict}``.
        cfg (dict): Config (fonts, metric set, line/marker sizing).
        per_sample_optk (dict|None): ``{sample_name: {metric_label: k}}``.
        view_algo (str): ``'All Algorithms'`` or a single algorithm name.
        selected_metric (str|None): Reserved for parity with _draw_evaluation.
    """
    fig.clear()
    per_sample_optk = per_sample_optk or {}

    enabled_metrics = cfg.get('enabled_metrics',
                              list(DEFAULT_METRICS))
    active = [(m, METRIC_KEYS[m][0], METRIC_KEYS[m][1])
              for m in enabled_metrics if m in METRIC_KEYS]
    samples = list(per_sample_eval.keys())

    if not active or not samples:
        ax = fig.add_subplot(111)
        msg = 'No metrics selected' if not active else 'No per-sample data'
        ax.text(0.5, 0.5, msg, ha='center', va='center',
                fontproperties=_font_scale(cfg, 'label')[0],
                color=_muted_color(cfg), transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        return

    fc = get_font_config(cfg)
    base = fc['size']
    fp_annot, _acol = _font_scale(cfg, 'annot')
    n_rows = len(active)
    n_cols = len(samples)

    legend_handles = {}

    for r, (metric_label, metric_name, metric_key) in enumerate(active):
        for c, sname in enumerate(samples):
            ax = fig.add_subplot(n_rows, n_cols, r * n_cols + c + 1)
            ev = per_sample_eval.get(sname, {}) or {}

            algos = (list(ev.keys()) if view_algo == 'All Algorithms'
                     else ([view_algo] if view_algo in ev else []))

            drew_any = False
            for algo_name in algos:
                res = ev.get(algo_name, {})
                k_vals = res.get('k_values', [])
                scores = res.get(metric_key, [])
                if not k_vals or not scores or len(k_vals) != len(scores):
                    continue
                style = ALGO_LINE_STYLES.get(
                    algo_name, dict(color='#64748B', ls='-', marker='o'))
                line, = ax.plot(
                    k_vals, scores,
                    color=style['color'], linestyle=style['ls'],
                    marker=style['marker'],
                    markersize=cfg.get('eval_marker_size', 4),
                    linewidth=cfg.get('eval_line_width', 1.6),
                    alpha=0.85, label=algo_name)
                legend_handles.setdefault(algo_name, line)
                drew_any = True

            opt_k = (per_sample_optk.get(sname, {}) or {}).get(metric_label)
            if opt_k is not None:
                ax.axvline(opt_k, color='#DC2626', linestyle='--',
                           linewidth=1.5, alpha=0.8)
                ax.annotate(f'K={opt_k}', xy=(0.97, 0.05),
                            xycoords='axes fraction', ha='right', va='bottom',
                            fontproperties=fp_annot, color='#DC2626')

            if not drew_any:
                ax.text(0.5, 0.5, 'insufficient\ndata', ha='center',
                        va='center', fontproperties=fp_annot,
                        color='#9CA3AF', transform=ax.transAxes)

            top_title = str(sname) if r == 0 else ''
            y_label = metric_name if c == 0 else ''
            x_label = 'Number of Clusters (K)' if r == n_rows - 1 else ''
            _style_ax(ax, cfg, xlabel=x_label, ylabel=y_label, title=top_title)
            ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    if legend_handles:
        fig.legend(list(legend_handles.values()), list(legend_handles.keys()),
                   loc='lower center', ncol=min(len(legend_handles), 6),
                   prop=_font_scale(cfg, 'legend')[0], framealpha=0.9,
                   edgecolor='#CBD5E1', bbox_to_anchor=(0.5, 0.0))
        fig.tight_layout(rect=(0, 0.06, 1, 1), pad=1.2)
    else:
        fig.tight_layout(pad=1.2)


SAMPLE_MARKERS = ['o', 's', '^', 'D', 'v', 'P', 'X', '*', 'h', '<', '>', 'p']
SAMPLE_PALETTE = ['#2563EB', '#DC2626', '#16A34A', '#D97706', '#7C3AED',
                  '#0891B2', '#DB2777', '#65A30D', '#EA580C', '#4F46E5',
                  '#0D9488', '#C026D3']


def _consensus_k(per_metric_k):
    """Return the consensus K and its agreement fraction from per-metric picks.

    Implements the simple majority-vote consensus that the cluster-validity
    literature recommends when several indices disagree: the value chosen by
    the largest number of indices is taken as the consensus, with ties broken
    towards the smaller K (the more parsimonious partition). This mirrors the
    "use several indices and let agreement decide" conclusion of Ikotun,
    Habyarimana & Ezugwu (*Heliyon* 11, 2025, e41953) and the majority-rule
    aggregation popularised by the NbClust package (Charrad et al., *J. Stat.
    Softw.* 61(6), 2014, 1-36).

    Args:
        per_metric_k (dict): ``{metric: k}`` picks for one data scope.

    Returns:
        tuple: ``(consensus_k, agreement_fraction)``; ``(None, 0.0)`` when no
            metric produced a pick.
    """
    if not per_metric_k:
        return None, 0.0
    counter = {}
    for k in per_metric_k.values():
        counter[k] = counter.get(k, 0) + 1
    best = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    frac = counter[best] / len(per_metric_k)
    return int(best), float(frac)


def _draw_consensus_summary(fig, eval_results, per_sample_eval, cfg,
                            elbow_fn, optimal_per_metric=None,
                            bootstrap_stability=None, selected_metric=None):
    """Draw a metric × scope consensus decision table for choosing K.

    This is the multi-sample-aware summary view. Rows are the enabled cluster
    validity indices; columns are the pooled dataset and each individual
    sample. Every cell shows the K that the metric selected for that scope,
    shaded by how well it agrees with the column's consensus K so disagreements
    are visible at a glance. A bottom "Consensus" row gives the majority-vote K
    per scope with its agreement fraction, and (when a bootstrap has been run)
    the pooled column annotates each metric's stability percentage.

    Presenting the decision this way — a compact agreement matrix rather than
    only score curves — directly addresses the core difficulty highlighted by
    Ikotun, Habyarimana & Ezugwu (*Heliyon* 11, 2025, e41953): different
    indices give different answers, so the practitioner needs to see agreement,
    stability, and per-sample reproducibility together. The majority-vote
    consensus follows the aggregation used by NbClust (Charrad et al.,
    *J. Stat. Softw.* 61(6), 2014, 1-36) and the stability column follows the
    non-parametric bootstrap assessment of Efron & Tibshirani (*An Introduction
    to the Bootstrap*, Chapman & Hall, 1993).

    Args:
        fig (Figure): Target figure (cleared and redrawn).
        eval_results (dict): Pooled ``{algo: eval_dict}`` results.
        per_sample_eval (dict): ``{sample_name: {algo: eval_dict}}`` or empty.
        cfg (dict): Configuration (fonts, enabled metrics).
        elbow_fn (Callable): ``(k_values, scores) -> int`` knee selector for
            elbow-rule metrics, passed through to :func:`_vote_optimal_per_metric`.
        optimal_per_metric (dict|None): Precomputed pooled ``{metric: k}``; when
            omitted it is recomputed from ``eval_results``.
        bootstrap_stability (dict|None): ``{metric: {'distribution', 'n', ...}}``
            from a completed bootstrap, used for the stability column.
        selected_metric (str|None): Metric to highlight as the active choice.
    """
    fig.clear()
    bootstrap_stability = bootstrap_stability or {}

    enabled = cfg.get('enabled_metrics', list(DEFAULT_METRICS))
    metrics = [m for m in enabled if m in METRIC_REGISTRY]
    if not metrics or not eval_results:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, 'Run ① Evaluate K to populate the summary',
                ha='center', va='center',
                fontproperties=_font_scale(cfg, 'label')[0],
                color=_muted_color(cfg),
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        return

    pooled_picks = optimal_per_metric
    if pooled_picks is None:
        pooled_picks, _ = _vote_optimal_per_metric(eval_results, elbow_fn, metrics)

    columns = ['Pooled']
    col_picks = [pooled_picks]
    for sname, ev in per_sample_eval.items():
        picks, _ = _vote_optimal_per_metric(ev, elbow_fn, metrics)
        columns.append(sname)
        col_picks.append(picks)

    consensus = [_consensus_k(p) for p in col_picks]

    fc = get_font_config(cfg)
    base = fc['size']
    tcol = _text_color(cfg)
    _th = _plot_theme(cfg)
    _empty_face = _th['face']
    _empty_edge = _th['border']
    n_rows = len(metrics) + 1
    n_cols = len(columns)

    ax = fig.add_subplot(111)
    ax.set_xlim(0, n_cols + 1.4)
    ax.set_ylim(0, n_rows + 1)
    ax.invert_yaxis()
    ax.axis('off')

    header_y = 0.5
    for ci, col in enumerate(columns):
        ax.text(ci + 1.5, header_y, col, ha='center', va='center',
                fontsize=base, fontweight='bold',
                fontfamily=fc['family'], color=tcol)
    if bootstrap_stability:
        ax.text(n_cols + 1.0, header_y, 'Stability', ha='center', va='center',
                fontsize=base, fontweight='bold',
                fontfamily=fc['family'], color=tcol)

    for ri, metric in enumerate(metrics):
        row_y = ri + 1.5
        is_sel = (metric == selected_metric)
        ax.text(0.95, row_y, metric, ha='right', va='center',
                fontsize=base, fontfamily=fc['family'],
                fontweight='bold' if is_sel else 'normal',
                color=METRIC_COLORS.get(metric, tcol))
        for ci, picks in enumerate(col_picks):
            k = picks.get(metric)
            cons_k = consensus[ci][0]
            if k is None:
                txt, face = '—', _empty_face
            else:
                if cons_k is not None and k == cons_k:
                    face = '#16A34A'
                elif cons_k is not None and abs(k - cons_k) <= 1:
                    face = '#D97706'
                else:
                    face = '#DC2626'
                txt = f'K={k}'
            rect = plt.Rectangle((ci + 1.05, row_y - 0.42), 0.9, 0.84,
                                 facecolor=face, alpha=0.22 if txt != '—' else 0.5,
                                 edgecolor=face if txt != '—' else _empty_edge,
                                 linewidth=1.4)
            ax.add_patch(rect)
            ax.text(ci + 1.5, row_y, txt, ha='center', va='center',
                    fontsize=base, fontfamily=fc['family'],
                    color=tcol)
        if bootstrap_stability:
            stab = bootstrap_stability.get(metric)
            k_pool = col_picks[0].get(metric)
            if stab and k_pool is not None and stab.get('n', 0) > 0:
                frac = stab['distribution'].get(k_pool, 0) / stab['n']
                ax.text(n_cols + 1.0, row_y, f'{frac:.0%}',
                        ha='center', va='center', fontsize=base,
                        fontfamily=fc['family'], color=tcol)
            else:
                ax.text(n_cols + 1.0, row_y, '–', ha='center', va='center',
                        fontsize=base, fontfamily=fc['family'],
                        color='#94A3B8')

    cons_y = n_rows + 0.4
    ax.text(0.95, cons_y, 'Consensus', ha='right', va='center',
            fontsize=base, fontweight='bold', fontfamily=fc['family'],
            color=tcol)
    for ci, (ck, frac) in enumerate(consensus):
        if ck is None:
            txt = '—'
        else:
            txt = f'K={ck}  ({frac:.0%})'
        rect = plt.Rectangle((ci + 1.05, cons_y - 0.42), 0.9, 0.84,
                             facecolor='#2563EB', alpha=0.16,
                             edgecolor='#2563EB', linewidth=1.6)
        ax.add_patch(rect)
        ax.text(ci + 1.5, cons_y, txt, ha='center', va='center',
                fontsize=base, fontweight='bold', fontfamily=fc['family'],
                color=tcol)

    fig.tight_layout(pad=1.0)


def _draw_clustering(fig, clustering_results, data_matrix, characterisation, cfg,
                     input_data=None):
    """Draw cluster scatter plots on a matplotlib Figure.

    Visual encoding:
        * Marker SHAPE encodes the source sample (multi-sample input only).
          Single-sample input uses circles everywhere.
        * Marker FILL color encodes either the cluster or the sample,
          depending on ``cfg['cluster_color_by']``:
              'Cluster' → fill = cluster color, shape = sample shape
              'Sample'  → fill = sample color, shape = sample shape
        * Noise (label -1, density-based algos only) is always rendered as
          a small grey '×'.

    Args:
        fig: Target matplotlib Figure (will be cleared).
        clustering_results: ``{algo_name: {'labels': np.array, 'n_clusters', 'n_noise'}}``.
        data_matrix: 2D-or-higher embedding for the scatter (uses first two cols).
        characterisation: ``{algo_name: {cluster_id: {...characterisation dict...}}}``.
        cfg: Display configuration dict.
    """
    fig.clear()

    if not clustering_results or data_matrix is None:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, 'No clustering data\nRun Step 2 first',
                ha='center', va='center',
                fontproperties=_font_scale(cfg, 'label')[0],
                color=_muted_color(cfg),
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        return

    n = len(clustering_results)
    cols = min(3, n)
    rows = math.ceil(n / cols)

    sample_arr = cfg.get('_sample_arr', None)
    unique_samples = (list(np.unique(sample_arr))
                      if sample_arr is not None else [])
    multi = len(unique_samples) > 1
    color_by = cfg.get('cluster_color_by', 'Cluster')
    sample_to_marker = {s: SAMPLE_MARKERS[i % len(SAMPLE_MARKERS)]
                        for i, s in enumerate(unique_samples)}
    sample_to_color  = {s: SAMPLE_PALETTE[i % len(SAMPLE_PALETTE)]
                        for i, s in enumerate(unique_samples)}

    pt_size   = cfg.get('scatter_point_size', 18)
    alpha     = cfg.get('scatter_alpha', 0.65)
    centroids = cfg.get('scatter_show_centroids', True)

    for idx, (algo_name, result) in enumerate(clustering_results.items()):
        ax = fig.add_subplot(rows, cols, idx + 1)
        ax._algo_name = algo_name
        labels = result.get('labels')
        if labels is None:
            ax.text(0.5, 0.5, 'No labels', ha='center', va='center',
                    fontproperties=_font_scale(cfg, 'label')[0],
                    color=_muted_color(cfg), transform=ax.transAxes)
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
                           label='_nolegend_', zorder=2)
                continue

            cluster_color = CLUSTER_COLORS[j % len(CLUSTER_COLORS)]

            if multi and sample_arr is not None and len(sample_arr) == len(x):
                for sname in unique_samples:
                    smask = mask & (sample_arr == sname)
                    if not smask.any():
                        continue
                    marker = sample_to_marker[sname]
                    fill = (sample_to_color[sname]
                            if color_by == 'Sample' else cluster_color)
                    ax.scatter(x[smask], y[smask], s=pt_size, marker=marker,
                               color=fill, alpha=alpha,
                               edgecolors='white', linewidths=0.3,
                               label='_nolegend_', zorder=3)
            else:
                ax.scatter(x[mask], y[mask], s=pt_size, marker='o',
                           color=cluster_color, alpha=alpha,
                           edgecolors='white', linewidths=0.3,
                           label='_nolegend_', zorder=3)

            if centroids:
                cx, cy = x[mask].mean(), y[mask].mean()
                ax.scatter(cx, cy, s=90, marker='*', color=cluster_color,
                           edgecolors='black', linewidths=0.8,
                           label='_nolegend_', zorder=5)

        from matplotlib.lines import Line2D
        legend_handles = []

        n_clusters = result.get('n_clusters', 0)
        n_noise = result.get('n_noise', 0)

        if color_by == 'Cluster' or not multi:
            for j, lab in enumerate(unique_labels):
                if lab == -1:
                    continue
                cluster_color = CLUSTER_COLORS[j % len(CLUSTER_COLORS)]
                ctype = ''
                cd = None
                if (algo_name in characterisation
                        and lab in characterisation[algo_name]):
                    cd = characterisation[algo_name][lab]
                    ctype = cd.get(
                        'cluster_type_short',
                        cd.get('cluster_type', ''))
                base = _cluster_label_short(lab)
                if ctype:
                    base = f'{base}: {ctype}'
                if cd is not None and per_ml_active(cfg, input_data):
                    base = f'{base} ({_cluster_size_str(cd, cfg, input_data)})'
                legend_handles.append(Line2D(
                    [0], [0], marker='o', linestyle='',
                    markerfacecolor=cluster_color, markeredgecolor='white',
                    markeredgewidth=0.4, markersize=7,
                    label=base))

        if multi:
            for sname in unique_samples:
                marker = sample_to_marker[sname]
                if color_by == 'Sample':
                    facecolor = sample_to_color[sname]
                else:
                    facecolor = '#475569'
                legend_handles.append(Line2D(
                    [0], [0], marker=marker, linestyle='',
                    markerfacecolor=facecolor, markeredgecolor='white',
                    markeredgewidth=0.4, markersize=7, label=str(sname)))

        if n_noise > 0:
            legend_handles.append(Line2D(
                [0], [0], marker='x', linestyle='', color='#9CA3AF',
                markersize=6, label='Noise'))

        title = f'{algo_name}  (K={n_clusters}'
        if n_noise > 0:
            title += f', noise={n_noise}'
        title += ')'

        _style_ax(ax, cfg, xlabel='Component 1', ylabel='Component 2', title=title)

        if legend_handles and len(legend_handles) <= 14:
            _fp_leg = _font_scale(cfg, 'legend')[0]
            leg = ax.legend(handles=legend_handles,
                            prop=_fp_leg,
                            loc='best', framealpha=0.9, edgecolor='#CBD5E1',
                            markerscale=0.9, handletextpad=0.3)
            if leg:
                leg.get_frame().set_linewidth(0.5)

    total = rows * cols
    for j in range(n, total):
        fig.add_subplot(rows, cols, j + 1).set_visible(False)

    fig.tight_layout(pad=1.2)


class _ClusterWorker(QThread):
    """Background worker that runs the clustering pipeline off the UI thread.

    The worker performs the expensive, CPU-bound stages — data preparation,
    fitting every enabled algorithm, and characterisation — without blocking
    the GUI.  Progress and results are delivered back to the main thread via
    signals; the dialog connects to these and does all drawing on the main
    thread, since matplotlib/Qt widgets are not thread-safe.

    Signals:
        progressed (int, str): Percent complete (0-100) and a status message.
        som_snapshot (object, int, int): Live SOM convergence frame —
            ``(weights_copy, current_iter, total_iter)``.
        done (object): Emitted on success with a results payload dict.
        failed (str): Emitted on error with the exception message.
    """

    progressed = Signal(float, str)
    som_snapshot = Signal(object, int, int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, dialog, sel_k, elements, data, enabled, parent=None):
        """
        Args:
            dialog (ClusteringDisplayDialog): Owning dialog (for compute helpers).
            sel_k (int): Selected number of clusters.
            elements (list[str]): Active element list.
            data (np.ndarray or None): Cached preprocessed matrix, or None to
                trigger preparation inside the worker.
            enabled (list[str]): Algorithm names to run.
            parent (QObject): Optional Qt parent.
        """
        super().__init__(parent)
        self._dlg = dialog
        self._sel_k = sel_k
        self._elements = elements
        self._data = data
        self._enabled = enabled

    def run(self):
        """Execute the pipeline on the worker thread and emit results."""
        try:
            dlg = self._dlg
            data = self._data
            if data is None:
                self.progressed.emit(10, "Preparing data…")
                data = dlg._prepare_data(self._elements)
            if data is None:
                self.failed.emit("No data available after preparation.")
                return

            elements_eff = dlg._elements_filtered or self._elements

            final_results = {}
            n_algos = max(len(self._enabled), 1)
            for i, algo in enumerate(self._enabled):
                pct = 20 + int(50 * i / n_algos)
                self.progressed.emit(pct, f"Fitting {algo}…")
                if algo == 'SOM':
                    labels = dlg._run_som(
                        self._sel_k, data, dlg.node.config,
                        progress_cb=lambda t, tot, w: self.som_snapshot.emit(w, t, tot),
                    )
                else:
                    labels = dlg._run_algo(algo, self._sel_k, data)
                if labels is not None:
                    final_results[algo] = {
                        'labels': labels,
                        'n_clusters': len(np.unique(labels[labels >= 0])),
                        'n_noise': int(np.sum(labels == -1)),
                    }

            dlg.final_results = final_results
            self.progressed.emit(75, "Characterising clusters…")
            dlg._characterise(elements_eff, data)

            self.progressed.emit(95, "Rendering…")
            self.done.emit({
                'data': data,
                'elements_eff': elements_eff,
                'sel_k': self._sel_k,
            })
        except Exception as exc: 
            self.failed.emit(str(exc))


class _EvalWorker(QThread):
    """Background worker that runs K-evaluation off the UI thread.

    Mirrors :class:`_ClusterWorker` but for the ① Evaluate K step: it prepares
    the data and runs the (potentially slow) multi-K, multi-algorithm scoring
    sweep — plus the per-sample sweep for multi-sample input — without freezing
    the GUI.  All widget updates happen on the main thread in the dialog's
    ``_on_eval_done`` handler.

    Signals:
        progressed (int, str): Percent complete (0-100) and a status message.
        done (object): Emitted on success with a results payload dict.
        failed (str): Emitted on error with the exception message.
    """

    progressed = Signal(float, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, dialog, elements, parent=None):
        """
        Args:
            dialog (ClusteringDisplayDialog): Owning dialog (for compute helpers).
            elements (list[str]): Active element list.
            parent (QObject): Optional Qt parent.
        """
        super().__init__(parent)
        self._dlg = dialog
        self._elements = elements

    def run(self):
        """Run preparation and K-evaluation, emitting progress and results."""
        try:
            dlg = self._dlg
            self.progressed.emit(5.0, "Preparing data…")
            data = dlg._prepare_data(self._elements)
            if data is None or len(data) < 2:
                self.failed.emit("Insufficient data for clustering.")
                return

            multi = dlg._is_multi()
            pooled_span = (10.0, 55.0) if multi else (10.0, 90.0)

            def _pooled_progress(frac):
                lo, hi = pooled_span
                self.progressed.emit(lo + (hi - lo) * frac,
                                     "Scoring cluster counts…")

            eval_results = dlg._evaluate_data(
                data, collect_som=True, progress_cb=_pooled_progress)

            if multi:
                self.progressed.emit(58.0, "Scoring per sample…")
                per_sample_eval, per_sample_optk = dlg._evaluate_per_sample(data)
            else:
                per_sample_eval, per_sample_optk = {}, {}

            self.progressed.emit(95.0, "Selecting optimal K…")
            self.done.emit({
                'data': data,
                'eval_results': eval_results,
                'per_sample_eval': per_sample_eval,
                'per_sample_optk': per_sample_optk,
            })
        except Exception as exc: 
            self.failed.emit(str(exc))


class _BootstrapWorker(QThread):
    """Background worker that runs the K-stability bootstrap off the UI thread.

    For each of ``n_boot`` resamples drawn with replacement from the prepared
    data matrix, the full evaluation pipeline is rerun and the per-metric
    optimal K is recorded. Aggregating across resamples yields, per metric, the
    most-frequently selected K and the fraction of resamples that agreed — a
    direct, non-parametric measure of how stable each metric's K choice is to
    sampling variation. This is the bootstrap-stability assessment recommended
    for cluster-validity selection by Ikotun, Habyarimana & Ezugwu
    (*Heliyon* 11, 2025, e41953) and follows the classic non-parametric
    bootstrap of Efron & Tibshirani (*An Introduction to the Bootstrap*,
    Chapman & Hall, 1993).

    Running this on a :class:`QThread` (rather than a ``processEvents`` loop on
    the GUI thread) keeps the interface fully responsive and lets the user
    cancel cleanly via a thread-safe flag. Only bootstrap-safe metrics are
    evaluated, so expensive O(n^2) indices are skipped automatically.

    Signals:
        progressed (float, str): Percent complete (0-100) and a status message.
        done (object): Emitted on success with
            ``{'stability': {...}, 'results': {...}, 'cancelled': bool,
            'completed': int, 'n_boot': int}``.
        failed (str): Emitted on error with the exception message.
    """

    progressed = Signal(float, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, dialog, data, enabled_algos, bootstrap_metrics,
                 n_boot, seed, parent=None):
        """
        Args:
            dialog (ClusteringDisplayDialog): Owning dialog (for compute helpers).
            data (np.ndarray): Prepared (scaled + reduced) data matrix.
            enabled_algos (list[str]): Non-SOM algorithms to evaluate.
            bootstrap_metrics (list[str]): Bootstrap-safe metric names to track.
            n_boot (int): Number of bootstrap resamples.
            seed (int): RNG seed for reproducible resampling.
            parent (QObject): Optional Qt parent.
        """
        super().__init__(parent)
        self._dlg = dialog
        self._data = data
        self._enabled_algos = enabled_algos
        self._metrics = bootstrap_metrics
        self._n_boot = n_boot
        self._seed = seed
        self._cancel = False

    def cancel(self):
        """Request cancellation; the loop stops after the current resample."""
        self._cancel = True

    def run(self):
        """Execute the bootstrap loop on the worker thread and emit results."""
        try:
            dlg = self._dlg
            data = self._data
            rng = np.random.default_rng(self._seed)
            n_rows = len(data)
            tally = {m: [] for m in self._metrics}

            completed = 0
            for b in range(self._n_boot):
                if self._cancel:
                    break
                idx = rng.integers(0, n_rows, size=n_rows)
                data_b = data[idx]
                try:
                    eb = dlg._evaluate_data(
                        data_b, enabled_algos=self._enabled_algos,
                        enabled_metrics=self._metrics, collect_som=False)
                    picks = dlg._pick_optimal_per_metric(eb)
                except Exception:
                    picks = {}
                for metric, k in picks.items():
                    if metric in tally:
                        tally[metric].append(k)
                completed = b + 1
                self.progressed.emit(
                    100.0 * completed / self._n_boot,
                    f"Bootstrapping K stability ({completed}/{self._n_boot})…")

            results = {m: list(v) for m, v in tally.items() if v}
            stability = {}
            for metric, ks in results.items():
                counter = {}
                for k in ks:
                    counter[k] = counter.get(k, 0) + 1
                mode_k = sorted(counter.items(),
                                key=lambda kv: (-kv[1], kv[0]))[0][0]
                stability[metric] = {
                    'mode_k': int(mode_k),
                    'mode_frac': float(counter[mode_k] / len(ks)),
                    'distribution': counter,
                    'n': len(ks),
                }

            self.done.emit({
                'stability': stability,
                'results': results,
                'cancelled': self._cancel,
                'completed': completed,
                'n_boot': self._n_boot,
            })
        except Exception as exc: 
            self.failed.emit(str(exc))


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
        self.setWindowModality(Qt.NonModal)
        self.setWindowFlags(self.windowFlags() | Qt.Window)

        self.eval_results = {}
        self.final_results = {}
        self.characterisation = {}
        self.optimal_k = None
        self.optimal_algo = None
        self.optimal_per_metric = {}
        self.optimal_algo_per_metric = {}
        self.selected_metric = None
        self.bootstrap_results = {}
        self.bootstrap_stability = {}
        self._bootstrap_cancel = False
        self.per_sample_eval = {}
        self.per_sample_optk = {}
        self._data_matrix_cache = None
        self._raw_matrix = None
        self._elements_cache = []
        self._elements_filtered = []
        self._particle_samples = None
        self._particle_indices = None
        self._cluster_worker = None
        self._eval_worker = None
        self._bootstrap_worker = None
        self._live_k_timer = QTimer(self)
        self._live_k_timer.setSingleShot(True)
        self._live_k_timer.setInterval(150)
        self._live_k_timer.timeout.connect(self._do_live_k)
        self._linkage_cache = None
        self._linkage_cache_key = None
        self._hover_ann = {}
        self._som_obj = None
        self._som_neuron_labels = None

        self._pal = _current_plot_palette()
        self._dark = self._pal['dark']

        self._build_ui()
        self._apply_theme()
        self.node.configuration_changed.connect(self._on_node_changed)

        if _app_theme is not None:
            try:
                _app_theme.themeChanged.connect(self._on_app_theme_changed)
            except Exception:
                pass

        try:
            from results.results_cluster_tools import attach_to_dialog
            attach_to_dialog(self)
        except Exception:
            pass

    def _on_app_theme_changed(self, _name=None):
        """Re-theme the dialog and redraw figures when the app theme changes.

        Connected to the application's ``ThemeManager.themeChanged`` signal so
        switching dark/light anywhere in the app instantly restyles this dialog
        and its plots without needing to reopen it.

        Args:
            _name (str): Palette name emitted by the signal (unused).
        """
        self._pal = _current_plot_palette()
        self._dark = self._pal['dark']
        self._apply_theme()
        try:
            if self.eval_results:
                self._refresh_eval_plot()
            if self.final_results and self._data_matrix_cache is not None:
                _draw_clustering(self.cluster_fig, self.final_results,
                                 self._data_matrix_cache,
                                 self.characterisation, self.node.config,
                                 input_data=self.node.input_data)
                self.cluster_canvas.draw()
                if self._data_matrix_cache.shape[1] >= 3:
                    self._draw_3d()
                self._draw_overview()
        except Exception:
            pass

    def _apply_theme(self):
        """Apply the active palette to the whole dialog as one stylesheet.

        Builds a single Qt stylesheet from ``self._pal`` covering the dialog,
        toolbar, tabs, combos, spinboxes, slider, checkboxes, progress bar and
        status strip, then sets matplotlib figure facecolors to match so the
        plots blend into the surrounding chrome in both light and dark modes.
        Re-callable at any time (e.g. when the OS theme changes).
        """
        p = self._pal
        self.node.config['_theme'] = dict(p)
        self.node.config['_dark'] = self._dark
        self.setStyleSheet(f"""
            QDialog, QWidget {{
                background: {p['bg']};
                color: {p['text']};
            }}
            QFrame#toolbar {{
                background: {p['surface']};
                border-bottom: 1px solid {p['border']};
            }}
            QFrame#statusbar {{
                background: {p['surface']};
                border-top: 1px solid {p['border']};
            }}
            QLabel {{ color: {p['text']}; background: transparent; }}
            QComboBox {{
                background: {p['bg']}; color: {p['text']};
                border: 1px solid {p['border_str']};
                border-radius: 4px; padding: 3px 6px;
            }}
            QComboBox:disabled {{ color: {p['text_muted']};
                background: {p['surface_alt']}; }}
            QComboBox QAbstractItemView {{
                background: {p['bg']}; color: {p['text']};
                selection-background-color: {p['accent']};
                selection-color: white;
            }}
            QSpinBox, QDoubleSpinBox {{
                background: {p['bg']}; color: {p['text']};
                border: 1px solid {p['border_str']};
                border-radius: 4px; padding: 2px 4px;
            }}
            QCheckBox {{ color: {p['text']}; background: transparent; }}
            QCheckBox:disabled {{ color: {p['text_muted']}; }}
            QSlider::groove:horizontal {{
                height: 4px; border-radius: 2px;
                background: {p['border_str']};
            }}
            QSlider::sub-page:horizontal {{
                height: 4px; border-radius: 2px;
                background: {p['accent']};
            }}
            QSlider::handle:horizontal {{
                background: {p['accent']};
                width: 14px; margin: -6px 0; border-radius: 7px;
            }}
            QSlider::handle:horizontal:disabled {{
                background: {p['disabled']};
            }}
            QProgressBar {{
                border: 1px solid {p['border_str']};
                border-radius: 4px; background: {p['surface_alt']};
                text-align: center; color: {p['text']};
            }}
            QProgressBar::chunk {{
                background: {p['accent']}; border-radius: 3px;
            }}
            QTabWidget::pane {{
                border: 1px solid {p['border']};
                background: {p['bg']};
            }}
            QTabBar::tab {{
                padding: 6px 18px; font-size: 12px;
                color: {p['text_muted']};
                background: {p['surface']};
                border: 1px solid {p['border']};
                border-bottom: none;
                border-top-left-radius: 4px; border-top-right-radius: 4px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                font-weight: bold; color: {p['text']};
                background: {p['bg']};
            }}
            QTableWidget {{
                background: {p['bg']}; color: {p['text']};
                gridline-color: {p['border']};
                selection-background-color: {p['accent']};
                selection-color: white;
            }}
            QHeaderView::section {{
                background: {p['surface_alt']}; color: {p['text']};
                border: 1px solid {p['border']}; padding: 3px;
            }}
            QMenu {{
                background: {p['bg']}; color: {p['text']};
                border: 1px solid {p['border_str']};
            }}
            QMenu::item:selected {{
                background: {p['accent']}; color: white;
            }}
            QScrollArea {{ background: {p['bg']}; border: none; }}
        """)

        if hasattr(self, 'optimal_label'):
            self.optimal_label.setStyleSheet(
                f"font-weight: bold; color: {p['accent']}; "
                f"padding: 0 8px; font-size: 12px; background: transparent;")
        if hasattr(self, 'status'):
            self.status.setStyleSheet(
                f"color: {p['text_muted']}; font-size: 11px; "
                f"padding: 2px 8px; background: transparent;")

        for fig in (getattr(self, n, None) for n in (
                'eval_fig', 'summary_fig', 'cluster_fig', '_3d_fig',
                'overview_fig', 'dendro_fig', 'som_fig')):
            if fig is not None:
                fig.patch.set_facecolor(p['plot_bg'])
        for canvas in (getattr(self, n, None) for n in (
                'eval_canvas', 'summary_canvas', 'cluster_canvas', '_3d_canvas',
                'overview_canvas', 'dendro_canvas', 'som_canvas')):
            if canvas is not None:
                try:
                    canvas.draw_idle()
                except Exception:
                    pass



    def _is_multi(self):
        """
        Returns:
            object: Result of the operation.
        """
        return (self.node.input_data and
                self.node.input_data.get('type') == 'multiple_sample_data')

    def _update_color_by_visibility(self):
        """Hide the Color-by picker for single-sample input."""
        show = self._is_multi()
        if hasattr(self, 'color_by_combo'):
            self.color_by_combo.setVisible(show)
            self.color_by_label.setVisible(show)
            if not show:
                self.color_by_combo.blockSignals(True)
                self.color_by_combo.setCurrentText('Cluster')
                self.color_by_combo.blockSignals(False)
                self.node.config['cluster_color_by'] = 'Cluster'

    def _update_eval_scope_visibility(self):
        """Hide the Pooled/Per-sample scope toggle for single-sample input.

        With one sample the per-sample grid is identical to the pooled view, so
        the toggle would be noise. We hide it and force 'Pooled' so
        _refresh_eval_plot always takes the standard single-figure path.
        """
        show = self._is_multi()
        if hasattr(self, 'eval_scope_combo'):
            self.eval_scope_combo.setVisible(show)
            self.eval_scope_label.setVisible(show)
            if not show:
                self.eval_scope_combo.blockSignals(True)
                self.eval_scope_combo.setCurrentText('Pooled')
                self.eval_scope_combo.blockSignals(False)

    def _on_color_by_changed(self, text):
        """Redraw the cluster scatter when the user changes the Color-by selection.

    Only the scatter fill changes; clustering, characterisation, overview,
    dendrogram, and SOM grid are unaffected.

    Args:
        text (str): Newly selected value, either 'Cluster' or 'Sample'.
    """
        self.node.config['cluster_color_by'] = text
        if not self.final_results:
            return
        try:
            data = self._data_matrix_cache
            if data is not None:
                _draw_clustering(self.cluster_fig, self.final_results,
                                 data, self.characterisation,
                                 self.node.config,
                                 input_data=self.node.input_data)
                self.cluster_canvas.draw()
                if data.shape[1] >= 3:
                    self._draw_3d()
        except Exception:
            pass


    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        toolbar.setFixedHeight(48)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(8, 4, 8, 4)

        self.eval_btn = self._make_btn("① Evaluate K", '#2563EB', self._run_evaluation)
        tl.addWidget(self.eval_btn)

        self.bs_btn = self._make_btn("↻ Bootstrap K", '#2563EB', self._run_bootstrap)
        self.bs_btn.setEnabled(False)
        self.bs_btn.setToolTip(
            "Resample the data with replacement and rerun K selection "
            "B times. The chip then shows the fraction of bootstraps "
            "that picked the same K — high = stable choice.")
        tl.addWidget(self.bs_btn)

        self.optimal_label = QLabel("Optimal K: —")
        tl.addWidget(self.optimal_label)

        self.metric_picks_widget = QWidget()
        self.metric_picks_layout = QHBoxLayout(self.metric_picks_widget)
        self.metric_picks_layout.setContentsMargins(0, 0, 8, 0)
        self.metric_picks_layout.setSpacing(4)
        tl.addWidget(self.metric_picks_widget)

        tl.addWidget(QLabel("K:"))
        self.k_combo = QComboBox()
        self.k_combo.setFixedWidth(60)
        self.k_combo.setEnabled(False)
        self.k_combo.currentTextChanged.connect(self._on_k_combo_changed)
        tl.addWidget(self.k_combo)

        self.k_slider = QSlider(Qt.Horizontal)
        self.k_slider.setFixedWidth(120)
        self.k_slider.setEnabled(False)
        self.k_slider.setToolTip(
            "Drag to change K live (Hierarchical / K-Means only)")
        self.k_slider.valueChanged.connect(self._on_k_slider_changed)
        tl.addWidget(self.k_slider)

        self.live_k_check = QCheckBox("Live")
        self.live_k_check.setToolTip(
            "Re-cluster live as you drag K.\n"
            "Hierarchical recuts its tree instantly; K-Means refits fast.\n"
            "Other algorithms stay on the Cluster button.")
        self.live_k_check.setEnabled(False)
        tl.addWidget(self.live_k_check)

        self.color_by_label = QLabel("Color by:")
        tl.addWidget(self.color_by_label)
        self.color_by_combo = QComboBox()
        self.color_by_combo.addItems(['Cluster', 'Sample'])
        self.color_by_combo.setFixedWidth(90)
        self.color_by_combo.setCurrentText(
            self.node.config.get('cluster_color_by', 'Cluster'))
        self.color_by_combo.currentTextChanged.connect(self._on_color_by_changed)
        tl.addWidget(self.color_by_combo)

        self.cluster_btn = self._make_btn("② Cluster", '#2563EB', self._run_clustering)
        self.cluster_btn.setEnabled(False)
        tl.addWidget(self.cluster_btn)

        tl.addStretch()

        self.export_btn = self._make_btn("Export", '#2563EB', self._export_results)
        self.export_btn.setEnabled(False)
        tl.addWidget(self.export_btn)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(200)
        self.progress.setFixedHeight(20)
        self.progress.setRange(0, PROGRESS_RESOLUTION)
        self.progress.setTextVisible(True)
        self._set_progress(0.0)
        self.progress.setVisible(False)
        tl.addWidget(self.progress)

        layout.addWidget(toolbar)

        self.tabs = QTabWidget()

        self._build_eval_tab()
        self._build_summary_tab()
        self._build_cluster_tab()
        self._build_overview_tab()
        self._build_dendrogram_tab()
        self._build_som_tab()

        layout.addWidget(self.tabs)

        self.status = QLabel("Ready — connect data and run evaluation")
        self.status.setObjectName("statusbar")
        layout.addWidget(self.status)

        self._update_color_by_visibility()
        self._update_eval_scope_visibility()

    def _btn_style(self, color):
        """Return the stylesheet for a flat coloured action button.

    Args:
        color (str): Hex background colour for the button.

    Returns:
        str: Qt stylesheet string.
    """
        disabled = self._pal['disabled']
        return (
            f"QPushButton {{"
            f"  background: {color}; color: white; padding: 6px 14px;"
            f"  border-radius: 4px; font-weight: bold; font-size: 11px;"
            f"}}"
            f"QPushButton:hover {{ opacity: 0.9; }}"
            f"QPushButton:disabled {{ background: {disabled}; "
            f"color: {self._pal['text_muted']}; }}"
        )

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
        btn.setStyleSheet(self._btn_style(color))
        btn.clicked.connect(slot)
        return btn


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
        self.eval_scope_label = QLabel("Scope:")
        hl.addWidget(self.eval_scope_label)
        self.eval_scope_combo = QComboBox()
        self.eval_scope_combo.addItems(['Pooled', 'Per-sample'])
        self.eval_scope_combo.setCurrentText('Per-sample')
        self.eval_scope_combo.currentTextChanged.connect(self._refresh_eval_plot)
        hl.addWidget(self.eval_scope_combo)
        hl.addStretch()
        po = self._make_popout_btn(lambda: self._pop_out_figure('eval'))
        hl.addWidget(po)
        vl.addLayout(hl)

        self.eval_fig = Figure(figsize=(12, 8), dpi=120, tight_layout=True)
        self.eval_canvas = _SafeFigureCanvas(self.eval_fig)
        self.eval_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.eval_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, 'eval'))
        self.eval_canvas.mpl_connect('pick_event', self._on_eval_pick)
        vl.addWidget(self.eval_canvas, stretch=1)

        self.tabs.addTab(tab, "① Evaluation")


    def _build_summary_tab(self):
        """Build the Summary tab holding the consensus decision matrix.

        The summary renders :func:`_draw_consensus_summary` onto its own figure
        so it pops out, themes, and exports exactly like the other tabs. It is
        the primary multi-sample-aware view for deciding K: a metric × scope
        agreement table with a consensus row and (after a bootstrap) a
        stability column.
        """
        tab = QWidget()
        vl = QVBoxLayout(tab)
        vl.setContentsMargins(4, 4, 4, 4)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("Consensus across metrics & samples"))
        hl.addStretch()
        po = self._make_popout_btn(lambda: self._pop_out_figure('summary'))
        hl.addWidget(po)
        vl.addLayout(hl)

        self.summary_fig = Figure(figsize=(12, 8), dpi=120, tight_layout=True)
        self.summary_canvas = _SafeFigureCanvas(self.summary_fig)
        self.summary_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.summary_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, 'summary'))
        vl.addWidget(self.summary_canvas, stretch=1)

        self.tabs.addTab(tab, "② Summary")

    def _refresh_summary(self):
        """Redraw the consensus summary table from the latest evaluation state.

        Safe to call before any evaluation has run; the drawing function shows
        a placeholder until ``eval_results`` is populated.
        """
        if not hasattr(self, 'summary_fig'):
            return
        _draw_consensus_summary(
            self.summary_fig, self.eval_results,
            self.per_sample_eval if self._is_multi() else {},
            self.node.config, self._elbow_k,
            optimal_per_metric=self.optimal_per_metric,
            bootstrap_stability=self.bootstrap_stability,
            selected_metric=self.selected_metric)
        self.summary_canvas.draw()


    def _build_cluster_tab(self):
        """Build the Clusters tab containing both 2-D and 3-D scatter views,
        toggled via a 2D / 3D button pair in the toolbar.
        """
        tab = QWidget()
        vl = QVBoxLayout(tab)
        vl.setContentsMargins(4, 4, 4, 4)

        hl = QHBoxLayout()

        _p = self._pal
        _tog = (
            "QPushButton{{padding:3px 12px;border-radius:3px;font-size:11px;"
            "font-weight:bold;border:1px solid {border};}}"
            "QPushButton:checked{{background:{accent};color:white;"
            "border-color:{accent};}}"
            "QPushButton:!checked{{background:{surf};color:{muted};}}"
        ).format(border=_p['border_str'], accent=_p['accent'],
                 surf=_p['surface_alt'], muted=_p['text_muted'])
        self._cluster_view_2d = QPushButton("2D")
        self._cluster_view_2d.setCheckable(True)
        self._cluster_view_2d.setChecked(True)
        self._cluster_view_2d.setStyleSheet(_tog)
        self._cluster_view_2d.clicked.connect(lambda: self._switch_cluster_view('2d'))
        hl.addWidget(self._cluster_view_2d)

        self._cluster_view_3d = QPushButton("3D")
        self._cluster_view_3d.setCheckable(True)
        self._cluster_view_3d.setChecked(False)
        self._cluster_view_3d.setStyleSheet(_tog)
        self._cluster_view_3d.clicked.connect(lambda: self._switch_cluster_view('3d'))
        hl.addWidget(self._cluster_view_3d)

        hl.addSpacing(12)

        self._3d_controls_widget = QWidget()
        _3d_hl = QHBoxLayout(self._3d_controls_widget)
        _3d_hl.setContentsMargins(0, 0, 0, 0)
        _3d_hl.setSpacing(6)

        _3d_hl.addWidget(QLabel("Pt size:"))
        self.sc3_pt = QSpinBox()
        self.sc3_pt.setRange(4, 120)
        self.sc3_pt.setValue(22)
        self.sc3_pt.setFixedWidth(52)
        self.sc3_pt.valueChanged.connect(self._draw_3d)
        _3d_hl.addWidget(self.sc3_pt)

        _3d_hl.addWidget(QLabel("Opacity:"))
        self.sc3_alpha = QDoubleSpinBox()
        self.sc3_alpha.setRange(0.05, 1.0)
        self.sc3_alpha.setSingleStep(0.05)
        self.sc3_alpha.setDecimals(2)
        self.sc3_alpha.setValue(0.70)
        self.sc3_alpha.setFixedWidth(56)
        self.sc3_alpha.valueChanged.connect(self._draw_3d)
        _3d_hl.addWidget(self.sc3_alpha)

        self.sc3_centroids = QCheckBox("Centroids")
        self.sc3_centroids.setChecked(True)
        self.sc3_centroids.toggled.connect(self._draw_3d)
        _3d_hl.addWidget(self.sc3_centroids)

        self.sc3_samples_btn = QPushButton("Samples")
        self.sc3_samples_btn.setToolTip("Show / hide individual samples")
        self.sc3_samples_btn.clicked.connect(self._open_3d_sample_picker)
        self.sc3_samples_btn.setVisible(False)
        _3d_hl.addWidget(self.sc3_samples_btn)

        _3d_hl.addSpacing(8)
        for _lbl, _elev, _azim in [("XY", 90, -90), ("XZ", 0, -90), ("YZ", 0, 0)]:
            _vbtn = QPushButton(_lbl)
            _vbtn.setFixedSize(32, 22)
            _vbtn.setToolTip(f"View from {_lbl} plane")
            _vbtn.setStyleSheet(
                "QPushButton{background:#E2E8F0;border:1px solid #CBD5E1;"
                "border-radius:3px;font-size:10px;font-weight:bold;color:#334155;}"
                "QPushButton:hover{background:#CBD5E1;}")
            _vbtn.clicked.connect(
                lambda _, e=_elev, a=_azim: self._set_3d_view(e, a))
            _3d_hl.addWidget(_vbtn)

        self._3d_info = QLabel("ℹ Set Dim. Reduction = PCA or t-SNE, Components = 3")
        self._3d_info.setStyleSheet("color:#6B7280;font-size:10px;")
        _3d_hl.addWidget(self._3d_info)

        self._3d_controls_widget.setVisible(False)
        hl.addWidget(self._3d_controls_widget)

        hl.addStretch()
        po = self._make_popout_btn(
            lambda: self._pop_out_figure(
                '3d' if self._cluster_stack.currentIndex() == 1 else 'cluster'))
        hl.addWidget(po)
        vl.addLayout(hl)

        self._cluster_stack = QStackedWidget()

        self.cluster_fig = Figure(figsize=(14, 9), dpi=120, tight_layout=True)
        self.cluster_canvas = _SafeFigureCanvas(self.cluster_fig)
        self.cluster_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.cluster_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, 'cluster'))
        self.cluster_canvas.mpl_connect('motion_notify_event', self._on_cluster_hover)
        self._cl_drag_ax = None
        self._cl_drag_start = None
        self._cl_drag_pos0 = None
        self.cluster_canvas.mpl_connect('button_press_event', self._cl_drag_press)
        self.cluster_canvas.mpl_connect('motion_notify_event', self._cl_drag_motion)
        self.cluster_canvas.mpl_connect('button_release_event', self._cl_drag_release)
        self._cluster_stack.addWidget(self.cluster_canvas)

        self._3d_fig = Figure(figsize=(13, 9), dpi=110)
        self._3d_canvas = _SafeFigureCanvas(self._3d_fig)
        self._3d_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self._3d_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, '3d'))
        self._3d_hover_ann = {}
        self._3d_point_cache = {}
        self._3d_canvas.mpl_connect('motion_notify_event', self._on_3d_hover)
        self._3d_canvas.mpl_connect('scroll_event', self._on_3d_scroll)
        self._cluster_stack.addWidget(self._3d_canvas)

        vl.addWidget(self._cluster_stack, stretch=1)
        self.tabs.addTab(tab, "② Clusters")

    def _switch_cluster_view(self, mode):
        """Toggle between 2-D scatter and 3-D scatter within the Clusters tab.

        Args:
            mode (str): ``'2d'`` or ``'3d'``.
        """
        is_3d = (mode == '3d')
        self._cluster_view_2d.setChecked(not is_3d)
        self._cluster_view_3d.setChecked(is_3d)
        self._cluster_stack.setCurrentIndex(1 if is_3d else 0)
        self._3d_controls_widget.setVisible(is_3d)
        if is_3d:
            self._draw_3d()




    def _ctx_menu(self, pos, tab):
        """
        Args:
            pos (Any): Position point.
            tab (Any): The tab.
        """
        menu = QMenu(self)

        edit_action = menu.addAction("✎  Edit Figure…")
        edit_action.triggered.connect(lambda: self._edit_figure(tab))

        cfg_action = menu.addAction("⚙  Configure…")
        cfg_action.triggered.connect(self._open_settings)

        fig_map = {'eval': self.eval_fig, 'summary': self.summary_fig,
                   'cluster': self.cluster_fig,
                   'overview': self.overview_fig,
                   'dendro': self.dendro_fig, '3d': self._3d_fig,
                   'som': self.som_fig}
        names   = {'eval': 'evaluation.png', 'summary': 'consensus_summary.png',
                   'cluster': 'clusters.png',
                   'overview': 'overview.png',
                   'dendro': 'dendrogram.png', '3d': '3d_scatter.png',
                   'som': 'som_grid.png'}
        dl = menu.addAction("Export Figure…")
        dl.triggered.connect(
            lambda: download_matplotlib_figure(fig_map.get(tab, self.eval_fig),
                                               self, names.get(tab, 'figure.png')))

        menu.exec(QCursor.pos())


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
        titles = {'eval': 'Evaluation Metrics',
                  'summary': 'Consensus Summary',
                  'cluster': 'Cluster Scatter',
                  'overview': 'Overview Heatmap',
                  'dendro': 'Dendrogram', '3d': '3D Scatter'}
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Clustering — {titles.get(tab, tab)}")
        dlg.setMinimumSize(900, 620)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        vl = QVBoxLayout(dlg)
        vl.setContentsMargins(6, 6, 6, 6)

        new_fig = Figure(figsize=(13, 8), dpi=110, tight_layout=True)
        new_canvas = _SafeFigureCanvas(new_fig)
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
            scope = (self.eval_scope_combo.currentText()
                     if hasattr(self, 'eval_scope_combo') else 'Pooled')
            if (scope == 'Per-sample' and self._is_multi()
                    and self.per_sample_eval):
                _draw_evaluation_per_sample(
                    new_fig, self.per_sample_eval, self.node.config,
                    per_sample_optk=self.per_sample_optk, view_algo=view,
                    selected_metric=self.selected_metric)
            else:
                _draw_evaluation(new_fig, self.eval_results, self.node.config,
                                 self.optimal_k, view,
                                 optimal_per_metric=self.optimal_per_metric,
                                 selected_metric=self.selected_metric)
        elif tab == 'summary':
            _draw_consensus_summary(
                new_fig, self.eval_results,
                self.per_sample_eval if self._is_multi() else {},
                self.node.config, self._elbow_k,
                optimal_per_metric=self.optimal_per_metric,
                bootstrap_stability=self.bootstrap_stability,
                selected_metric=self.selected_metric)
        elif tab == 'cluster':
            if (self.final_results
                    and self._data_matrix_cache is not None):
                _draw_clustering(new_fig, self.final_results,
                                 self._data_matrix_cache,
                                 self.characterisation,
                                 self.node.config,
                                 input_data=self.node.input_data)
        elif tab == 'overview':
            self._draw_overview_into(new_fig)
        elif tab == 'dendro':
            self._draw_dendrogram_into(new_fig)
        elif tab == '3d':
            self._draw_3d_into(new_fig)
        elif tab == 'som':
            if self._som_obj is not None and self._som_neuron_labels is not None:
                som_labels = self.final_results.get('SOM', {}).get('labels')
                if som_labels is not None:
                    _draw_som_grid(new_fig, self._som_obj, self._som_neuron_labels,
                                   som_labels, self.node.config,
                                   sample_labels=self._particle_samples,
                                   input_data=self.node.input_data)

        new_canvas.draw()
        dlg.show()


    def _edit_figure(self, tab: str):
        """Open the per-figure display settings dialog.

        Every tab shows a shared Display section (element label mode, isotope
        cap, threshold) plus a Font Settings group. Tab-specific options appear
        above the shared section.

        Args:
            tab (str): Identifier of the calling tab.
        """
        cfg = self.node.config
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit Figure — {tab.capitalize()}")
        dlg.setMinimumWidth(340)
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

        elif tab in ('cluster', '3d'):
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

        elif tab == 'overview':
            view_cb = QComboBox()
            view_cb.addItems(['Strips', 'Heatmap'])
            view_cb.setCurrentText(cfg.get('overview_view', 'Strips'))

            cmap_cb = QComboBox()
            cmaps = ['YlOrRd', 'Blues', 'Greens', 'Purples', 'RdYlGn',
                     'coolwarm', 'viridis', 'plasma', 'magma', 'cividis']
            cmap_cb.addItems(cmaps)
            cur_cmap = cfg.get('overview_colormap', 'YlOrRd')
            if cur_cmap in cmaps:
                cmap_cb.setCurrentText(cur_cmap)

            av = QCheckBox("Show cell values (heatmap mode)")
            av.setChecked(cfg.get('overview_show_values', True))

            grp = QCheckBox("Group rows by dominant element")
            grp.setChecked(cfg.get('overview_group_by_dominant', True))

            metric_cb = QComboBox()
            metric_cb.addItems(['Detections', 'Detections %', 'Mean'])
            metric_cb.setCurrentText(cfg.get('overview_panel_metric', 'Detections'))

            sstrip = QCheckBox("Show sample-share strip (multi-sample)")
            sstrip.setChecked(cfg.get('overview_show_sample_strip', True))

            form.addRow("View:", view_cb)
            form.addRow("Colormap:", cmap_cb)
            form.addRow("", av)
            form.addRow("", grp)
            form.addRow("Detection panel metric:", metric_cb)
            form.addRow("", sstrip)
            widgets = {
                'overview_view':                  view_cb,
                'overview_colormap':              cmap_cb,
                'overview_show_values':           av,
                'overview_group_by_dominant':     grp,
                'overview_panel_metric':          metric_cb,
                'overview_show_sample_strip':     sstrip,
            }

        outer.addLayout(form)

        disp_grp = QGroupBox("Display Settings")
        disp_form = QFormLayout(disp_grp)

        lm = QComboBox()
        lm.addItems(['Symbol', 'Mass + Symbol', 'Atomic Notation'])
        lm.setCurrentText(cfg.get('label_mode', cfg.get('overview_label_mode', 'Symbol')))
        disp_form.addRow("Element labels:", lm)

        cap = QSpinBox(); cap.setRange(1, 20)
        cap.setValue(int(cfg.get('display_max_isotopes', 4)))
        disp_form.addRow("Max isotopes to display:", cap)

        thr = QDoubleSpinBox(); thr.setRange(0.0, 100.0)
        thr.setSingleStep(0.5); thr.setDecimals(1); thr.setSuffix(" %")
        thr.setValue(cfg.get('display_min_pct', 1.0))
        disp_form.addRow("Min. display threshold:", thr)

        outer.addWidget(disp_grp)

        font_grp = FontSettingsGroup(cfg)
        outer.addWidget(font_grp.build())

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
            cfg['label_mode'] = lm.currentText()
            cfg['overview_label_mode'] = lm.currentText()
            cfg['display_max_isotopes'] = cap.value()
            cfg['display_min_pct'] = thr.value()
            cfg.update(font_grp.collect())
            self._apply_display_settings()

    def _redraw_figure(self, tab: str):
        """
        Args:
            tab (str): The tab.
        """
        if tab == 'eval':
            self._refresh_eval_plot()
        elif tab == 'cluster':
            if (self.final_results
                    and self._data_matrix_cache is not None):
                _draw_clustering(self.cluster_fig, self.final_results,
                                 self._data_matrix_cache,
                                 self.characterisation,
                                 self.node.config,
                                 input_data=self.node.input_data)
                self.cluster_canvas.draw()
        elif tab == 'overview':
            self._draw_overview()
        elif tab == 'dendro':
            self._draw_dendrogram()
        elif tab == '3d':
            self._draw_3d()
        elif tab == 'som':
            if (self._som_obj is not None
                    and self._som_neuron_labels is not None):
                som_labels = self.final_results.get('SOM', {}).get('labels')
                if som_labels is not None:
                    _draw_som_grid(self.som_fig, self._som_obj,
                                   self._som_neuron_labels, som_labels,
                                   self.node.config,
                                   sample_labels=self._particle_samples,
                                   input_data=self.node.input_data)
                    self.som_canvas.draw()


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


    def _build_overview_tab(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        vl.setContentsMargins(4, 4, 4, 4)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("Algorithm:"))
        self.ov_algo = QComboBox()
        self.ov_algo.currentTextChanged.connect(self._draw_overview)
        hl.addWidget(self.ov_algo)

        hl.addSpacing(12)
        hl.addWidget(QLabel("View:"))
        self.ov_view = QComboBox()
        self.ov_view.addItems(['Strips', 'Heatmap'])
        self.ov_view.setCurrentText(
            self.node.config.get('overview_view', 'Strips'))
        self.ov_view.currentTextChanged.connect(self._on_overview_view_changed)
        hl.addWidget(self.ov_view)

        hl.addSpacing(12)
        hl.addWidget(QLabel("Detections for:"))
        self.ov_elem_btn = QPushButton("(none)")
        self.ov_elem_btn.setMinimumWidth(140)
        self.ov_elem_btn.clicked.connect(self._open_overview_element_picker)
        hl.addWidget(self.ov_elem_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setMaximumWidth(60)
        clear_btn.clicked.connect(self._clear_overview_elements)
        hl.addWidget(clear_btn)

        hl.addStretch()
        po = self._make_popout_btn(lambda: self._pop_out_figure('overview'))
        hl.addWidget(po)
        vl.addLayout(hl)

        self.overview_fig = Figure(figsize=(14, 7), dpi=110, tight_layout=True)
        self.overview_canvas = _SafeFigureCanvas(self.overview_fig)
        self.overview_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.overview_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, 'overview'))
        vl.addWidget(self.overview_canvas, stretch=1)

        self.tabs.addTab(tab, "③ Overview")

    def _on_overview_view_changed(self, text):
        """Handle a change to the Strips/Heatmap toggle in the Overview toolbar.

    Args:
        text (str): Newly selected view mode ('Strips' or 'Heatmap').
    """
        self.node.config['overview_view'] = text
        self._draw_overview()

    def _open_overview_element_picker(self):
        """Pop a small multi-select menu of available elements.

        Elements come from ``self._elements_cache`` which is populated once
        characterisation runs. The current selection lives in
        ``cfg['overview_selected_elements']`` so it survives re-draws and
        export.
        """
        elements = list(getattr(self, '_elements_cache', []) or [])
        if not elements:
            return
        sorted_elems = sort_elements_by_mass(elements)
        current = set(self.node.config.get('overview_selected_elements', []))
        menu = QMenu(self.ov_elem_btn)
        for el in sorted_elems:
            act = menu.addAction(el)
            act.setCheckable(True)
            act.setChecked(el in current)

        def _accept(action):
            el = action.text()
            sel = list(self.node.config.get('overview_selected_elements', []))
            if action.isChecked():
                if el not in sel:
                    sel.append(el)
            else:
                if el in sel:
                    sel.remove(el)
            self.node.config['overview_selected_elements'] = sel
            self._refresh_overview_elem_btn()
            self._draw_overview()

        menu.triggered.connect(_accept)
        menu.exec(QCursor.pos())

    def _clear_overview_elements(self):
        """Empty the selected-elements list and redraw."""
        self.node.config['overview_selected_elements'] = []
        self._refresh_overview_elem_btn()
        self._draw_overview()

    def _refresh_overview_elem_btn(self):
        """Sync the picker button's label with the current selection."""
        sel = list(self.node.config.get('overview_selected_elements', []))
        if not sel:
            self.ov_elem_btn.setText("(none)")
        elif len(sel) <= 3:
            self.ov_elem_btn.setText(", ".join(sel))
        else:
            self.ov_elem_btn.setText(f"{len(sel)} elements")

    def _build_dendrogram_tab(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        vl.setContentsMargins(4, 4, 4, 4)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("Truncate (last p leaves):"))
        self.dendro_p = QSpinBox()
        self.dendro_p.setRange(0, 10000)
        self.dendro_p.setValue(0)
        self.dendro_p.setToolTip("0 = full dendrogram (no truncation)")
        self.dendro_p.setFixedWidth(60)
        hl.addWidget(self.dendro_p)
        hl.addWidget(QLabel("  Color threshold (0 = auto):"))
        self.dendro_thresh = QDoubleSpinBox()
        self.dendro_thresh.setRange(0.0, 90000.0)
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
        self.dendro_canvas = _SafeFigureCanvas(self.dendro_fig)
        self.dendro_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.dendro_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, 'dendro'))
        vl.addWidget(self.dendro_canvas, stretch=1)

        self.dendro_tab_idx = self.tabs.addTab(tab, "④ Dendrogram")


    def _open_3d_sample_picker(self):
        """Checkable menu to show/hide samples in the 3D scatter."""
        samples = list(self.node.config.get('_sample_names', []) or [])
        if not samples:
            return
        hidden = set(self.node.config.get('plot3d_hidden_samples', []))
        menu = QMenu(self.sc3_samples_btn)
        show_all = menu.addAction("Show all")
        show_all.triggered.connect(self._show_all_3d_samples)
        menu.addSeparator()
        for s in samples:
            act = menu.addAction(str(s))
            act.setCheckable(True)
            act.setChecked(s not in hidden)

        def _toggle(action):
            name = action.text()
            if name == "Show all":
                return
            hid = set(self.node.config.get('plot3d_hidden_samples', []))
            if action.isChecked():
                hid.discard(name)
            else:
                hid.add(name)
            self.node.config['plot3d_hidden_samples'] = list(hid)
            self._draw_3d()

        menu.triggered.connect(_toggle)
        menu.exec(QCursor.pos())

    def _show_all_3d_samples(self):
        """Clear the hidden-sample set and redraw the 3D scatter."""
        self.node.config['plot3d_hidden_samples'] = []
        self._draw_3d()

    def _on_3d_scroll(self, event):
        """Zoom the 3D axes under the cursor in/out on mouse-wheel scroll.

        Scaling all three axis limits about their midpoints emulates a
        camera dolly; scroll up zooms in, scroll down zooms out.
        """
        ax = getattr(event, 'inaxes', None)
        if ax is None or not hasattr(ax, 'get_zlim3d'):
            return
        scale = 0.85 if event.button == 'up' else 1.0 / 0.85
        for get_lim, set_lim in (
            (ax.get_xlim3d, ax.set_xlim3d),
            (ax.get_ylim3d, ax.set_ylim3d),
            (ax.get_zlim3d, ax.set_zlim3d),
        ):
            lo, hi = get_lim()
            mid = 0.5 * (lo + hi)
            half = 0.5 * (hi - lo) * scale
            set_lim(mid - half, mid + half)
        self._3d_canvas.draw_idle()

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

    def _on_3d_hover(self, event):
        """Show a tooltip with cluster and element information on 3D hover.

    Hit-testing is performed by projecting the cached (x, y, z) points
    through the axes' current 3D projection to 2D display coordinates
    and picking the nearest point within a pixel threshold.

    Args:
        event (matplotlib.backend_bases.MouseEvent): Mouse motion event.
    """
        ax = getattr(event, 'inaxes', None)
        cache = self._3d_point_cache.get(ax) if ax is not None else None

        if cache is None or event.x is None or event.y is None:
            changed = False
            for a, ann in self._3d_hover_ann.items():
                if ann.get_visible():
                    ann.set_visible(False)
                    changed = True
            if changed:
                self._3d_canvas.draw_idle()
            return

        xs, ys, zs, labels_arr, sample_arr = cache
        if xs is None or len(xs) == 0:
            return

        try:
            from mpl_toolkits.mplot3d import proj3d
            xp, yp, _ = proj3d.proj_transform(xs, ys, zs, ax.get_proj())
            disp = ax.transData.transform(np.column_stack([xp, yp]))
            dx = disp[:, 0] - event.x
            dy = disp[:, 1] - event.y
            dist = np.hypot(dx, dy)
        except Exception:
            return

        nearest = int(np.argmin(dist))
        THRESHOLD_PX = 16
        if dist[nearest] > THRESHOLD_PX:
            ann = self._3d_hover_ann.get(ax)
            if ann is not None and ann.get_visible():
                ann.set_visible(False)
                self._3d_canvas.draw_idle()
            return

        cid = int(labels_arr[nearest])
        lines = ['Noise' if cid < 0 else f'Cluster {cid + 1}']
        if sample_arr is not None:
            lines[0] += f'  ·  {sample_arr[nearest]}'

        algo_name = getattr(ax, '_algo_name', None)
        if algo_name and algo_name in self.characterisation:
            cd = self.characterisation[algo_name].get(cid)
            if cd:
                comp = cd.get('composition', [])[:3]
                if comp:
                    lines.append('  '.join(f'{e} {p:.0f}%' for e, p in comp))

        tip = '\n'.join(lines)
        ann = self._3d_hover_ann.get(ax)
        if ann is None:
            ann = ax.annotate(
                tip, xy=(event.x, event.y), xycoords='figure pixels',
                xytext=(14, 14), textcoords='offset pixels',
                fontsize=8,
                bbox=dict(boxstyle='round,pad=0.4', fc='#FFFBEB',
                          ec='#D97706', alpha=0.96, lw=0.9),
                zorder=30,
            )
            self._3d_hover_ann[ax] = ann
        else:
            ann.set_text(tip)
            ann.xy = (event.x, event.y)
        ann.set_visible(True)
        self._3d_canvas.draw_idle()

    def _draw_3d_into(self, target_fig):
        """
        Args:
            target_fig (Any): The target fig.
        """
        target_fig.clear()

        data    = self._data_matrix_cache
        results = self.final_results
        active_char = self.characterisation
        cfg     = self.node.config

        dr = cfg.get('dim_reduction', 'None')

        if data is None or data.shape[1] < 3 or not results:
            ax = target_fig.add_subplot(111)
            msg = ("No 3D data available.\n\n"
                   "In ⚙ Configure → Preprocessing:\n"
                   "  • Dim. Reduction = PCA  or  t-SNE\n"
                   "  • Components = 3\n\n"
                   "Then re-run ① Evaluate K → ② Cluster.")
            ax.text(0.5, 0.5, msg, ha='center', va='center',
                    fontproperties=_font_scale(cfg, 'label')[0],
                    color=_muted_color(cfg), linespacing=1.6,
                    transform=ax.transAxes,
                    bbox=dict(boxstyle='round,pad=0.6',
                              fc=_plot_theme(cfg)['face'],
                              ec=_plot_theme(cfg)['border'], lw=1))
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_facecolor(_plot_theme(cfg)['face'])
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
        unique_samples = (list(np.unique(sample_arr))
                          if sample_arr is not None else [])
        multi = len(unique_samples) > 1
        color_by = cfg.get('cluster_color_by', 'Cluster')
        sample_to_marker = {s: SAMPLE_MARKERS[i % len(SAMPLE_MARKERS)]
                            for i, s in enumerate(unique_samples)}
        sample_to_color = {s: SAMPLE_PALETTE[i % len(SAMPLE_PALETTE)]
                           for i, s in enumerate(unique_samples)}

        if hasattr(self, 'sc3_samples_btn'):
            self.sc3_samples_btn.setVisible(multi)

        hidden = set(cfg.get('plot3d_hidden_samples', []))
        if multi and sample_arr is not None and hidden:
            visible_mask = np.array([s not in hidden for s in sample_arr])
        else:
            visible_mask = np.ones(len(x), dtype=bool)

        fp = make_font_properties(cfg)
        fc = get_font_config(cfg)
        fp_title, _col3d = _font_scale(cfg, 'title')
        fp_lbl3d, _ = _font_scale(cfg, 'label')
        fp_tick3d, _ = _font_scale(cfg, 'tick')
        fp_leg3d, _ = _font_scale(cfg, 'legend')

        self._3d_point_cache = {}

        n_algos = len(results)
        cols    = min(2, n_algos)
        rows    = math.ceil(n_algos / cols)

        for idx, (algo_name, result) in enumerate(results.items()):
            ax = target_fig.add_subplot(rows, cols, idx + 1,
                                        projection='3d')
            ax.set_facecolor(_plot_theme(cfg)['face'])
            ax._algo_name = algo_name
       
            try:
                ax.set_box_aspect(None, zoom=1.2)
            except Exception:
                pass
            labels_arr  = result.get('labels')
            if labels_arr is None:
                continue

            unique_labs = np.unique(labels_arr)

            vis = visible_mask
            self._3d_point_cache[ax] = (
                x[vis], y[vis], z[vis],
                labels_arr[vis],
                (sample_arr[vis] if sample_arr is not None else None),
            )

            for j, lab in enumerate(unique_labs):
                mask = (labels_arr == lab) & visible_mask
                if lab == -1:
                    if mask.any():
                        ax.scatter(x[mask], y[mask], z[mask],
                                   s=10, marker='x', color='#9CA3AF',
                                   alpha=0.4, linewidths=0.8,
                                   label='_nolegend_', depthshade=True)
                    continue

                cluster_color = CLUSTER_COLORS[j % len(CLUSTER_COLORS)]

                if multi and sample_arr is not None and len(sample_arr) == len(x):
                    for sname in unique_samples:
                        smask = mask & (sample_arr == sname)
                        if not smask.any():
                            continue
                        marker = sample_to_marker[sname]
                        fill = (sample_to_color[sname]
                                if color_by == 'Sample' else cluster_color)
                        ax.scatter(x[smask], y[smask], z[smask],
                                   s=pt_size, marker=marker, color=fill,
                                   alpha=alpha, edgecolors='white',
                                   linewidths=0.3, label='_nolegend_',
                                   depthshade=True)
                else:
                    ax.scatter(x[mask], y[mask], z[mask],
                               s=pt_size, marker='o', color=cluster_color,
                               alpha=alpha, edgecolors='white',
                               linewidths=0.3, label='_nolegend_',
                               depthshade=True)

                if show_cent:
                    cx, cy, cz = (x[mask].mean(),
                                  y[mask].mean(),
                                  z[mask].mean())
                    ax.scatter(cx, cy, cz, s=120, marker='*',
                               color=cluster_color, edgecolors='black',
                               linewidths=0.9, zorder=6,
                               depthshade=False)

            from matplotlib.lines import Line2D
            legend_handles = []
            if color_by == 'Cluster' or not multi:
                for j, lab in enumerate(unique_labs):
                    if lab == -1:
                        continue
                    cc = CLUSTER_COLORS[j % len(CLUSTER_COLORS)]
                    ctype = ''
                    cd = None
                    if (algo_name in active_char
                            and lab in active_char[algo_name]):
                        cd = active_char[algo_name][lab]
                        ctype = cd.get(
                            'cluster_type_short',
                            cd.get('cluster_type', ''))
                    base = _cluster_label_short(lab)
                    if ctype:
                        base = f'{base}: {ctype}'
                    if cd is not None and per_ml_active(self.node.config,
                                                        self.node.input_data):
                        base = f'{base} ({_cluster_size_str(cd, self.node.config, self.node.input_data)})'
                    legend_handles.append(Line2D(
                        [0], [0], marker='o', linestyle='',
                        markerfacecolor=cc, markeredgecolor='white',
                        markeredgewidth=0.4, markersize=7,
                        label=base))
            if multi:
                for sname in unique_samples:
                    marker = sample_to_marker[sname]
                    facecolor = (sample_to_color[sname]
                                 if color_by == 'Sample' else '#475569')
                    legend_handles.append(Line2D(
                        [0], [0], marker=marker, linestyle='',
                        markerfacecolor=facecolor, markeredgecolor='white',
                        markeredgewidth=0.4, markersize=7, label=str(sname)))

            n_cl    = result.get('n_clusters', 0)
            n_noise = result.get('n_noise', 0)
            title   = f'{algo_name}  (K={n_cl}'
            if n_noise:
                title += f', noise={n_noise}'
            title += ')'

            ax.set_title(title, fontproperties=fp_title, color=fc['color'], pad=8)
            ax.set_xlabel(ax_labels[0], fontproperties=fp_lbl3d,
                          color=fc['color'], labelpad=6)
            ax.set_ylabel(ax_labels[1], fontproperties=fp_lbl3d,
                          color=fc['color'], labelpad=6)
            ax.set_zlabel(ax_labels[2], fontproperties=fp_lbl3d,
                          color=fc['color'], labelpad=6)
            ax.tick_params(labelsize=fp_tick3d.get_size_in_points(),
                           colors=fc['color'])
            ax.xaxis.pane.fill = False
            ax.yaxis.pane.fill = False
            ax.zaxis.pane.fill = False
            ax.xaxis.pane.set_edgecolor('#E2E8F0')
            ax.yaxis.pane.set_edgecolor('#E2E8F0')
            ax.zaxis.pane.set_edgecolor('#E2E8F0')
            ax.grid(True, alpha=0.2, linewidth=0.4)

            if legend_handles and len(legend_handles) <= 14:
                leg = ax.legend(handles=legend_handles,
                                prop=fp_leg3d,
                                loc='upper left', framealpha=0.85,
                                edgecolor='#CBD5E1', markerscale=0.8)
                if leg:
                    leg.get_frame().set_linewidth(0.5)

        self._3d_info.setText(
            f"3D  [{dr}]  —  drag to rotate · scroll to zoom · Shift+drag to pan")
        self._3d_info.setStyleSheet("color:#2563EB;font-size:10px;font-weight:bold;")

        target_fig.tight_layout(pad=1.2)
        target_fig.subplots_adjust(left=0.03, right=0.97, top=0.95,
                                   bottom=0.04, wspace=0.04, hspace=0.18)

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
                    ha='center', va='center',
                    fontproperties=_font_scale(self.node.config, 'label')[0],
                    color=_muted_color(self.node.config),
                    transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([])
            return

        cfg            = self.node.config
        linkage_method = cfg.get('hier_linkage', 'ward')
        metric         = (cfg.get('hier_metric', 'euclidean')
                          if linkage_method != 'ward' else 'euclidean')
        n              = data.shape[0]

        try:
            Z = scipy_linkage(
                np.ascontiguousarray(data, dtype=np.float64),
                method=linkage_method,
                metric=metric,
            )
        except Exception as e:
            ax.text(0.5, 0.5, f'Linkage failed:\n{e}',
                    ha='center', va='center',
                    fontproperties=_font_scale(self.node.config, 'tick')[0],
                    color='#DC2626',
                    transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([])
            return

        algo_name = cfg.get('selected_algorithm', 'Hierarchical')
        labels_arr = None
        if algo_name in self.final_results:
            labels_arr = self.final_results[algo_name].get('labels')

        sample_arr = self._particle_samples

        leaf_labels = []
        for i in range(n):
            parts = [str(i)]
            if labels_arr is not None and i < len(labels_arr):
                parts.append(_cluster_label_short(int(labels_arr[i])))
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

        fp_title, _dcol = _font_scale(cfg, 'title')
        fp_lbl, _ = _font_scale(cfg, 'label')
        fp_tick, _ = _font_scale(cfg, 'tick')

        trunc_note = ''
        if use_trunc:
            if trunc_auto:
                trunc_note = f'  [auto-truncated → last {p_eff} leaves, n={n}]'
            else:
                trunc_note = f'  [truncated → last {p_eff} leaves]'

        title = (f"Dendrogram — Hierarchical  "
                 f"[linkage={linkage_method}, metric={metric}]{trunc_note}")
        ax.set_title(title, fontproperties=fp_title, color=_dcol, pad=10)
        ax.set_xlabel(
            'Particle index  |  Cluster  |  Sample' if not use_trunc
            else 'Cluster node (count = leaf size)',
            fontproperties=fp_lbl, color=_dcol)
        ax.set_ylabel('Distance', fontproperties=fp_lbl, color=_dcol)
        _dth = _plot_theme(cfg)
        ax.set_facecolor(_dth['face'])
        ax.grid(axis='y', alpha=0.25, linewidth=0.5, color=_dth['grid'])
        for spine in ax.spines.values():
            spine.set_color(_dth['border'])
            spine.set_linewidth(0.8)
        ax.tick_params(labelsize=fp_tick.get_size_in_points(), colors=_dcol)
        for lab in (*ax.get_xticklabels(), *ax.get_yticklabels()):
            lab.set_fontproperties(fp_tick)
            lab.set_color(_dcol)

        target_fig.tight_layout(pad=1.5)

    def _draw_overview(self):
        """Render the Overview tab: composition strips (or heatmap) on the
        left, detection / sample-share panel on the right."""
        self._draw_overview_into(self.overview_fig)
        self.overview_canvas.draw()

    def _draw_overview_into(self, target_fig):
        """Draw the Overview content into an arbitrary Figure.

    Left panel: composition strips or a heatmap depending on
    ``overview_view``. Right panel: detection counts for selected
    elements, sample-share strip for multi-sample input without a
    selection, or plain cluster-size bars as fallback.

    Args:
        target_fig (Figure): Target matplotlib Figure (cleared on entry).
    """
        algo = self.ov_algo.currentText()
        if not algo or algo not in self.characterisation:
            return
        char = self.characterisation[algo]
        elements = self._elements_cache
        if not char or not elements:
            return

        cfg = self.node.config
        target_fig.clear()

        view = cfg.get('overview_view', 'Strips')
        group = cfg.get('overview_group_by_dominant', True)
        sel = list(cfg.get('overview_selected_elements', []) or [])

        is_multi = (self.node.input_data is not None
                    and self.node.input_data.get('type') == 'multiple_sample_data')
        sample_names = (self.node.input_data.get('sample_names', [])
                        if is_multi else [])
        show_sample_strip = (is_multi
                             and cfg.get('overview_show_sample_strip', True)
                             and not sel)

        gs = target_fig.add_gridspec(1, 2, width_ratios=[3.2, 1.0],
                                     wspace=0.05)
        ax_left = target_fig.add_subplot(gs[0, 0])
        ax_right = target_fig.add_subplot(gs[0, 1])

        _face = _plot_theme(cfg)['face']
        ax_left.set_facecolor(_face)
        ax_right.set_facecolor(_face)

        right_group = group if view == 'Strips' else False

        if view == 'Heatmap':
            label_mode = cfg.get('label_mode',
                                  cfg.get('overview_label_mode', 'Symbol'))
            sample_data = _build_sample_data_from_characterisation(
                char, elements,
                threshold_pct=cfg.get('display_min_pct', 1.0),
                max_elems=int(cfg.get('display_max_isotopes', 4)),
                group_by_dominant=group,
                label_mode=label_mode,
                input_data=self.node.input_data,
            )
            hm_cfg = dict(cfg)
            hm_cfg.setdefault('colorscale',
                              cfg.get('overview_colormap', 'YlOrRd'))
            hm_cfg.setdefault('show_numbers',
                              cfg.get('overview_show_values', True))
            hm_cfg.setdefault('show_colorbar', True)
            hm_cfg.setdefault('start_range', 1)
            hm_cfg.setdefault('end_range', max(1, len(sample_data)))
            hm_cfg.setdefault('min_particles', 1)
            hm_cfg.setdefault('data_type_display',
                              cfg.get('data_type_display', 'Counts'))
            hm_cfg['label_mode'] = label_mode
            hm_cfg['show_mass_numbers'] = (label_mode != 'Symbol')
            hm_cfg['y_axis_unit'] = cfg.get('y_axis_unit', 'count')
            draw_combinations_heatmap(
                ax_left, target_fig, sample_data, hm_cfg,
                title=f'Cluster overview — {algo}',
                is_multi=False,
            )
            self._restyle_heatmap_axes(ax_left, target_fig, cfg)
        else:
            _draw_composition_strips(ax_left, char, elements, cfg,
                                      algo_name=algo,
                                      input_data=self.node.input_data)

        if show_sample_strip:
            _draw_sample_share_strip(ax_right, char, sample_names, cfg,
                                      group_by_dominant=right_group)
        else:
            _draw_detection_panel(ax_right, char, sel, cfg,
                                   group_by_dominant=right_group,
                                   input_data=self.node.input_data)

        try:
            ax_right.set_ylim(ax_left.get_ylim())
        except Exception:
            pass

        target_fig.tight_layout(pad=1.2)


    def _restyle_heatmap_axes(self, ax, fig, cfg):
        """Re-apply font and theme to an externally-drawn heatmap axes.

        ``draw_combinations_heatmap`` lives in another module and uses its own
        default fonts/colours, so after it draws we override the title, axis
        labels, tick labels and any in-cell/annotation text on the axes (and
        attached colorbars) to match the current font settings and theme.  This
        is what makes the Overview heatmap's text follow the app theme and the
        font controls consistently.

        Args:
            ax (matplotlib.axes.Axes): The heatmap axes to restyle.
            fig (matplotlib.figure.Figure): Owning figure (for colorbar axes).
            cfg (dict): Configuration dictionary.
        """
        th = _plot_theme(cfg)
        col = th['text']
        fp_title, _ = _font_scale(cfg, 'title')
        fp_lbl, _ = _font_scale(cfg, 'label')
        fp_tick, _ = _font_scale(cfg, 'tick')
        fp_cell, _ = _font_scale(cfg, 'cell')

        ax.set_facecolor(th['face'])

        if ax.get_title():
            ax.set_title(ax.get_title(), fontproperties=fp_title, color=col)
        if ax.get_xlabel():
            ax.set_xlabel(ax.get_xlabel(), fontproperties=fp_lbl, color=col)
        if ax.get_ylabel():
            ax.set_ylabel(ax.get_ylabel(), fontproperties=fp_lbl, color=col)
        ax.tick_params(colors=col)
        for lab in (*ax.get_xticklabels(), *ax.get_yticklabels()):
            lab.set_fontproperties(fp_tick)
            lab.set_color(col)

        for txt in ax.texts:
            txt.set_fontproperties(fp_cell)

        for other in fig.axes:
            if other is ax:
                continue
            if getattr(other, '_colorbar', None) is not None or \
                    other.get_label() == '<colorbar>':
                other.tick_params(colors=col)
                for lab in other.get_yticklabels():
                    lab.set_fontproperties(fp_tick)
                    lab.set_color(col)
                if other.yaxis.label.get_text():
                    other.yaxis.label.set_fontproperties(fp_lbl)
                    other.yaxis.label.set_color(col)


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
        _cl = 'Noise' if cid < 0 else f'Cluster {cid + 1}'
        lines = [f'Particle #{nearest}  |  {_cl}']
        if self._raw_matrix is not None and nearest < len(self._raw_matrix):
            raw = self._raw_matrix[nearest]
            total_raw = sum(raw) or 1.0
            _max_iso = int(self.node.config.get('display_max_isotopes', 4))
            _min_pct = self.node.config.get('display_min_pct', 1.0)
            el_vals = [
                (elements[i], raw[i])
                for i in range(min(len(elements), len(raw)))
                if raw[i] > 0 and (raw[i] / total_raw * 100) >= _min_pct
            ]
            el_vals.sort(key=lambda t: t[1], reverse=True)
            for el, v in el_vals[:_max_iso]:
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


    def _open_settings(self):
        dlg = ClusteringSettingsDialog(self.node.config, self,
                                       input_data=self.node.input_data)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._apply_display_settings()
            self._data_matrix_cache = None
            self._linkage_cache = None
            self._linkage_cache_key = None
            self._update_live_k_availability()
            self.status.setText("Settings updated — re-run ① Evaluate K if preprocessing changed")

    def _on_node_changed(self):
        self._data_matrix_cache = None
        self._update_color_by_visibility()


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

        Side effects:
            - Sets ``self._raw_matrix`` to the pre-scaling matrix (rows already
              filtered, columns matching the filtered element list).
            - Sets ``self._particle_samples`` to the per-row sample name array.
            - Sets ``self._elements_filtered`` to the elements that survived the
              optional low-detection filter. Callers (evaluation, clustering,
              characterisation) should use this list rather than the original
              ``elements`` argument because the data matrix is built from it.
        """
        if not self.node.input_data or not elements:
            self._elements_filtered = list(elements) if elements else []
            return None

        cfg = self.node.config
        dt = cfg.get('data_type_display', 'Counts')
        dk = DATA_KEY_MAP.get(dt, 'elements')
        particles = self.node.input_data.get('particle_data', [])
        if not particles:
            self._elements_filtered = list(elements)
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

        original_indices = np.arange(len(particles))

        if cfg.get('filter_zeros', True):
            mask = np.any(matrix > 0, axis=1)
            matrix = matrix[mask]
            sample_labels = sample_labels[mask]
            original_indices = original_indices[mask]


        filtered_elements = list(elements)
        if matrix.size > 0:
            min_count = int(cfg.get('min_particle_type_count', 5))
            matrix, sample_labels, original_indices = _filter_rare_particle_types(
                matrix, sample_labels, original_indices, min_count
            )

        self._elements_filtered = filtered_elements
        self._particle_indices = original_indices
        self._raw_matrix = matrix.copy()
        self._particle_samples = sample_labels

        scaling = cfg.get('scaling', 'CLR')
        if scaling == 'CLR':
            matrix = _apply_clr(matrix)
        elif scaling == 'ILR':
            matrix = _apply_ilr(matrix)
        elif scaling == 'Robust Z-score':
            matrix = _apply_robust_zscore(matrix)

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

            elif name == 'Gaussian Mixture':
                return GaussianMixture(
                    n_components=k,
                    covariance_type=cfg.get('gmm_covariance_type', 'full'),
                    random_state=42,
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

            elif name == 'HDBSCAN':
                if not _HDBSCAN_OK or _HDBSCAN_CLS is None:
                    return None
                return _HDBSCAN_CLS(
                    min_cluster_size=cfg.get('hdbscan_min_cluster_size', 5),
                    min_samples=cfg.get('hdbscan_min_samples', 5),
                    metric=cfg.get('hdbscan_metric', 'euclidean'),
                ).fit_predict(data)

            elif name == 'SOM':
                return self._run_som(k, data, cfg)

        except Exception as e:
            print(f"Clustering failed for {name}: {e}")
        return None

    def _run_som(self, k, data, cfg, progress_cb=None):
        """Train a SOM and cluster the resulting neuron weight vectors.

        Two-stage pipeline:
          1. Train a (rows × cols) self-organising map on the input data.
          2. Cluster the neuron weight vectors into K groups using
             ``som_final_algo``. Each input is then labelled by the cluster of
             its BMU (best matching unit).

        Args:
            k (int): Number of final clusters.
            data (np.ndarray): Preprocessed data matrix.
            cfg (dict): Configuration dictionary.
            progress_cb (callable or None): Optional live-convergence callback
                forwarded to :meth:`_SOM.fit`; receives
                ``(current_iter, total_iter, weights_copy)``.

        Returns:
            np.ndarray or None: Cluster label per data point.

        Notes:
            * The fitted SOM is stashed on ``self._som_obj`` and the per-neuron
              cluster labels on ``self._som_neuron_labels`` so the SOM tab can
              re-render U-matrix / hit-count / cluster maps without retraining.
            * The input data is cached on the SOM as ``som._fit_X`` so
              hit-count and quantisation-error queries don't need it re-passed.
        """
        rows = cfg.get('som_rows', 10)
        cols = cfg.get('som_cols', 10)
        sigma = cfg.get('som_sigma', 1.0)
        lr = cfg.get('som_lr', 0.5)
        n_iter = cfg.get('som_n_iter', 2000)
        final_algo = cfg.get('som_final_algo', 'Hierarchical (Ward)')

        som = _SOM(rows, cols, data.shape[1], sigma=sigma, lr=lr, n_iter=n_iter)
        snap_every = max(n_iter // 40, 1) if progress_cb is not None else 0
        som.fit(data, progress_cb=progress_cb, snapshot_every=snap_every)
        som._fit_X = data
        weights = som.get_weights()
        bmu_labels = som.predict(data)

        n_neurons = len(weights)
        k_eff = min(k, n_neurons)

        def _cluster_neurons(algo):
            """Run ``algo`` on the neuron weight vectors, return labels.

            Reasonable defaults are used for hyperparams since the user only
            picks the algorithm name in this UI; the neuron count is tiny
            (≤900 typically) so quality matters more than speed.
            """
            if algo == 'Hierarchical (Ward)':
                return AgglomerativeClustering(
                    n_clusters=k_eff, linkage='ward', metric='euclidean',
                ).fit_predict(weights)
            if algo == 'Hierarchical (Average)':
                return AgglomerativeClustering(
                    n_clusters=k_eff, linkage='average', metric='euclidean',
                ).fit_predict(weights)
            if algo == 'Hierarchical (Complete)':
                return AgglomerativeClustering(
                    n_clusters=k_eff, linkage='complete', metric='euclidean',
                ).fit_predict(weights)
            if algo == 'K-Means':
                return KMeans(
                    n_clusters=k_eff, random_state=42, n_init=10,
                ).fit_predict(weights)
            if algo == 'Gaussian Mixture':
                return GaussianMixture(
                    n_components=k_eff, random_state=42,
                    covariance_type='full', n_init=3,
                ).fit_predict(weights)
            if algo == 'Spectral':
                nn = min(10, max(2, n_neurons - 1))
                return SpectralClustering(
                    n_clusters=k_eff, affinity='nearest_neighbors',
                    n_neighbors=nn, random_state=42,
                    assign_labels='kmeans',
                ).fit_predict(weights)
            return AgglomerativeClustering(
                n_clusters=k_eff, linkage='ward', metric='euclidean',
            ).fit_predict(weights)

        try:
            neuron_cluster_labels = _cluster_neurons(final_algo)
        except Exception:
            neuron_cluster_labels = KMeans(
                n_clusters=k_eff, random_state=42, n_init=5,
            ).fit_predict(weights)

        self._som_obj = som
        self._som_neuron_labels = neuron_cluster_labels
        return neuron_cluster_labels[bmu_labels]

    def _evaluate_data(self, data, *, enabled_algos=None,
                       enabled_metrics=None, min_k=None, max_k=None,
                       collect_som=False, progress_cb=None):
        """Run the full algorithm × K × metric sweep on ``data`` once.

        Pulled out of :meth:`_run_evaluation` so that the same logic can be
        reused for bootstrap iterations without duplicating the metric-
        computation tree (which had subtle aligned-with-k_values guards that
        we don't want to reimplement).

        Args:
            data (np.ndarray): The (already scaled + reduced) data matrix.
            enabled_algos (list, optional): Algorithms to include; default
                pulls from ``self.node.config['enabled_algorithms']``.
            enabled_metrics (list, optional): Metrics to compute; default
                pulls from config.
            min_k (int, optional): Minimum K to test; default from config.
            max_k (int, optional): Maximum K to test; default from config.
            collect_som (bool): If True, allow SOM to populate
                ``self._som_obj``. Bootstrap iterations pass False so they
                don't trample the main run's SOM state.
            progress_cb (Callable, optional): Called as ``progress_cb(frac)``
                with a 0-1 completion fraction over the algorithm × K grid, so
                callers can drive a fine-grained progress bar.

        Returns:
            dict: ``{algo: {'k_values': [...], 'silhouette_scores': [...], ...}}``
            keyed exactly like ``self.eval_results``.
        """
        cfg = self.node.config
        if enabled_algos is None:
            enabled_algos = cfg.get('enabled_algorithms',
                                    ['K-Means', 'Hierarchical', 'DBSCAN'])
        if enabled_metrics is None:
            enabled_metrics = cfg.get(
                'enabled_metrics', list(DEFAULT_METRICS))
        if min_k is None:
            min_k = cfg.get('min_clusters', 2)
        if max_k is None:
            max_k = cfg.get('max_clusters', 20)

        som_obj_backup = self._som_obj
        som_labels_backup = self._som_neuron_labels

        total_steps = 0
        for algo in enabled_algos:
            total_steps += 1 if algo in DENSITY_BASED_ALGOS else (max_k - min_k + 1)
        total_steps = max(total_steps, 1)
        step = 0

        results = {}
        for algo in enabled_algos:
            res = {mk: [] for _, mk in METRIC_KEYS.values()}
            res['k_values'] = []

            if algo in DENSITY_BASED_ALGOS:
                labels = self._run_algo(algo, min_k, data)
                if labels is not None:
                    valid = labels[labels >= 0]
                    n_clusters = len(np.unique(valid)) if len(valid) else 0
                    if n_clusters >= 2:
                        pending = {}
                        try:
                            for metric in enabled_metrics:
                                if metric not in METRIC_REGISTRY:
                                    continue
                                key = METRIC_REGISTRY[metric]['key']
                                pending[key] = CVI_FUNCS[key](data, labels)
                            res['k_values'].append(n_clusters)
                            for mk, sv in pending.items():
                                res[mk].append(sv)
                        except Exception:
                            pass
                step += 1
                if progress_cb is not None:
                    progress_cb(step / total_steps)
                results[algo] = res
                continue

            for k in range(min_k, max_k + 1):
                labels = self._run_algo(algo, k, data)
                if labels is None or len(np.unique(labels)) < 2:
                    step += 1
                    if progress_cb is not None:
                        progress_cb(step / total_steps)
                    continue
                pending = {}
                try:
                    for metric in enabled_metrics:
                        if metric not in METRIC_REGISTRY:
                            continue
                        key = METRIC_REGISTRY[metric]['key']
                        pending[key] = CVI_FUNCS[key](data, labels)
                except Exception:
                    step += 1
                    if progress_cb is not None:
                        progress_cb(step / total_steps)
                    continue
                res['k_values'].append(k)
                for mk, sv in pending.items():
                    res[mk].append(sv)
                step += 1
                if progress_cb is not None:
                    progress_cb(step / total_steps)
            results[algo] = res

        if not collect_som:
            self._som_obj = som_obj_backup
            self._som_neuron_labels = som_labels_backup

        return results

    def _pick_optimal_per_metric(self, eval_results):
        """Reduce an eval-results dict to ``{metric: K}`` using vote+tiebreak.

        Thin wrapper over :func:`_vote_optimal_per_metric`, restricted to the
        metrics currently enabled in the node configuration. Each algorithm
        votes once per metric under that metric's registry selection rule
        (max / min / elbow) and ties are broken by the best mean score in the
        metric's ``direction``. Used both by the per-sample evaluation and by
        each bootstrap iteration so the bootstrap distribution is directly
        comparable to the user's active chip picks.

        Args:
            eval_results: Output of :meth:`_evaluate_data`.

        Returns:
            dict: ``{metric: optimal_k}`` — empty if no metric could decide.
        """
        if not eval_results:
            return {}
        enabled = self.node.config.get('enabled_metrics', list(DEFAULT_METRICS))
        enabled = [m for m in enabled if m in METRIC_REGISTRY]
        picks, _ = _vote_optimal_per_metric(eval_results, self._elbow_k, enabled)
        return picks


    def _evaluate_per_sample(self, data):
        """Run the evaluation sweep independently on each sample's particles.

        Multi-sample only. The prepared (scaled + reduced) matrix is sliced by
        the row-aligned sample labels in ``self._particle_samples`` and the same
        algorithm × K × metric sweep is rerun on each subset, so every sample
        gets its OWN metric curves and its OWN per-metric optimal K.

        The feature set (element columns) is the one chosen on the pooled data
        in :meth:`_prepare_data`; we deliberately do NOT re-filter columns per
        sample so the samples stay directly comparable on the same axes.

        Note: this validates each sample as if it were clustered on its own. The
        clustering the app actually performs is still pooled (all samples in a
        single fit — see :meth:`_run_clustering`); these per-sample scores are a
        verification view, not a redefinition of the clustering.

        Args:
            data (np.ndarray): The pooled, prepared data matrix.

        Returns:
            tuple(dict, dict):
                * ``per_sample_eval``  — ``{sample_name: eval_results_dict}``
                  keyed exactly like ``self.eval_results``.
                * ``per_sample_optk``  — ``{sample_name: {metric_label: k}}``.
        """
        per_sample_eval = {}
        per_sample_optk = {}
        if self._particle_samples is None or data is None:
            return per_sample_eval, per_sample_optk

        samples = self._particle_samples
        if len(samples) != len(data):
            return per_sample_eval, per_sample_optk

        seen = []
        for s in samples:
            if s not in seen:
                seen.append(s)

        cfg = self.node.config
        enabled_algos = [a for a in cfg.get(
            'enabled_algorithms', ['K-Means', 'Hierarchical', 'DBSCAN'])
            if a != 'SOM']
        if not enabled_algos:
            return per_sample_eval, per_sample_optk

        for sname in seen:
            mask = (samples == sname)
            sub = data[mask]
            if len(sub) < 3:
                per_sample_eval[sname] = {}
                per_sample_optk[sname] = {}
                continue
            ev = self._evaluate_data(sub, enabled_algos=enabled_algos,
                                     collect_som=False)
            per_sample_eval[sname] = ev
            per_sample_optk[sname] = self._pick_optimal_per_metric(ev)

        return per_sample_eval, per_sample_optk


    def _run_evaluation(self):
        """Launch K-evaluation on a background worker thread.

        Validates inputs, disables the trigger, and starts an
        :class:`_EvalWorker`.  Results are applied on the main thread in
        :meth:`_on_eval_done` as the worker signals arrive, so the progress bar
        animates and the UI stays responsive during the scoring sweep.
        """
        if getattr(self, '_eval_worker', None) is not None \
                and self._eval_worker.isRunning():
            return

        elements = self._get_elements()
        if not elements:
            QMessageBox.warning(self, "Warning", "No elements available.")
            return

        self.status.setText("Evaluating cluster numbers…")
        self.progress.setVisible(True)
        self._set_progress(0.0)
        self.eval_btn.setEnabled(False)
        self.bootstrap_results = {}
        self.bootstrap_stability = {}

        worker = _EvalWorker(self, elements)
        worker.progressed.connect(self._on_cluster_progress)
        worker.done.connect(self._on_eval_done)
        worker.failed.connect(self._on_eval_failed)
        worker.finished.connect(self._on_eval_thread_finished)
        self._eval_worker = worker
        worker.start()

    def _on_eval_done(self, payload):
        """Apply evaluation results on the main thread and refresh the UI.

        Args:
            payload (dict): Bundle from the worker with the prepared ``data``,
                ``eval_results`` and the per-sample results.
        """
        try:
            self._data_matrix_cache = payload['data']
            self.eval_results = payload['eval_results']
            self.per_sample_eval = payload['per_sample_eval']
            self.per_sample_optk = payload['per_sample_optk']

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
            sorted_k = sorted(all_k)
            for k in sorted_k:
                self.k_combo.addItem(str(k))
            if self.optimal_k:
                self.k_combo.setCurrentText(str(self.optimal_k))
            self.k_combo.setEnabled(True)

            if sorted_k:
                self.k_slider.blockSignals(True)
                self.k_slider.setRange(min(sorted_k), max(sorted_k))
                self.k_slider.setValue(self.optimal_k or sorted_k[0])
                self.k_slider.blockSignals(False)
                self.k_slider.setEnabled(True)
            self._update_live_k_availability()

            self._refresh_eval_plot()
            self._refresh_summary()
            self._update_optimal_label()
            self._update_metric_picks_ui()

            self._set_progress(100.0)
            self.cluster_btn.setEnabled(True)
            self.bs_btn.setEnabled(True)
            if self.optimal_k:
                tail = f" via {self.selected_metric}" if self.selected_metric else ""
                self.status.setText(
                    f"Evaluation complete — suggested K={self.optimal_k}{tail}."
                    " Click a metric chip to switch, or pick K manually.")
            else:
                self.status.setText(
                    "Evaluation complete — no K could be selected (try a wider K range).")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Evaluation failed:\n{e}")
            self.status.setText("Evaluation failed")

    def _on_eval_failed(self, message):
        """Report an evaluation-worker failure to the user.

        Args:
            message (str): Exception message from the worker.
        """
        if "Insufficient data" in message:
            QMessageBox.warning(self, "Warning", message)
        else:
            QMessageBox.critical(self, "Error", f"Evaluation failed:\n{message}")
        self.status.setText("Evaluation failed")

    def _on_eval_thread_finished(self):
        """Clean up after the evaluation worker terminates."""
        self.progress.setVisible(False)
        self.eval_btn.setEnabled(True)
        self._eval_worker = None

    def _run_bootstrap(self):
        """Launch the K-stability bootstrap on a background worker thread.

        Validates inputs, filters to bootstrap-safe metrics and non-SOM
        algorithms, then starts a :class:`_BootstrapWorker`. Results are
        applied on the main thread in :meth:`_on_bootstrap_done`, so the UI
        stays responsive and the high-resolution progress bar animates smoothly
        across resamples. The toolbar button toggles to a Stop control that
        requests cooperative cancellation from the worker.
        """
        if getattr(self, '_bootstrap_worker', None) is not None \
                and self._bootstrap_worker.isRunning():
            return

        if self._data_matrix_cache is None or not self.eval_results:
            QMessageBox.information(
                self, "Bootstrap K",
                "Run ① Evaluate K first — bootstrap reuses that data matrix.")
            return

        data = self._data_matrix_cache
        cfg = self.node.config
        n_boot = int(cfg.get('bootstrap_n', 50))
        seed = int(cfg.get('bootstrap_seed', 42))
        n_rows = len(data)
        if n_rows < 10:
            QMessageBox.information(
                self, "Bootstrap K",
                "Too few particles for a meaningful bootstrap.")
            return

        enabled_algos = [a for a in cfg.get(
            'enabled_algorithms', ['K-Means', 'Hierarchical', 'DBSCAN'])
            if a != 'SOM']
        if not enabled_algos:
            QMessageBox.information(
                self, "Bootstrap K",
                "Bootstrap needs at least one non-SOM algorithm enabled.")
            return

        enabled_metrics = cfg.get('enabled_metrics', list(DEFAULT_METRICS))
        bootstrap_metrics = [
            m for m in enabled_metrics
            if m in METRIC_REGISTRY and METRIC_REGISTRY[m]['bootstrap_safe']]
        if not bootstrap_metrics:
            QMessageBox.information(
                self, "Bootstrap K",
                "None of the enabled metrics are bootstrap-safe. Enable a "
                "cheaper index (e.g. Silhouette, S_Dbw, Xie-Beni) to bootstrap.")
            return

        self.bs_btn.setText("✕ Stop")
        self.bs_btn.setStyleSheet(self._btn_style('#DC2626'))
        try:
            self.bs_btn.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.bs_btn.clicked.connect(self._cancel_bootstrap)

        self.progress.setVisible(True)
        self._set_progress(0.0)
        self.eval_btn.setEnabled(False)
        self.cluster_btn.setEnabled(False)
        self.status.setText(f"Bootstrapping K stability (n={n_boot})…")

        worker = _BootstrapWorker(self, data, enabled_algos,
                                  bootstrap_metrics, n_boot, seed)
        worker.progressed.connect(self._on_cluster_progress)
        worker.done.connect(self._on_bootstrap_done)
        worker.failed.connect(self._on_bootstrap_failed)
        worker.finished.connect(self._on_bootstrap_thread_finished)
        self._bootstrap_worker = worker
        worker.start()

    def _on_bootstrap_done(self, payload):
        """Apply bootstrap stability results on the main thread.

        Args:
            payload (dict): Bundle from :class:`_BootstrapWorker` with the
                aggregated ``stability`` dict, the raw ``results`` distribution,
                a ``cancelled`` flag, and the completed / requested counts.
        """
        self.bootstrap_results = payload.get('results', {})
        self.bootstrap_stability = payload.get('stability', {})
        self._update_metric_picks_ui()
        if hasattr(self, '_refresh_summary'):
            self._refresh_summary()

        completed = payload.get('completed', 0)
        n_boot = payload.get('n_boot', 0)
        if payload.get('cancelled'):
            self.status.setText(
                f"Bootstrap stopped after {completed} iterations — "
                f"stability shown is partial.")
        elif self.bootstrap_stability:
            bits = [
                f"{m}: K={s['mode_k']} ({s['mode_frac']:.0%})"
                for m, s in self.bootstrap_stability.items()]
            self.status.setText(
                f"Bootstrap done (n={n_boot}) — " + " · ".join(bits))
        else:
            self.status.setText(
                "Bootstrap done — no metric could pick K consistently.")

    def _on_bootstrap_failed(self, message):
        """Report a bootstrap-worker failure to the user.

        Args:
            message (str): Exception message from the worker.
        """
        QMessageBox.critical(self, "Error", f"Bootstrap failed:\n{message}")
        self.status.setText("Bootstrap failed")

    def _on_bootstrap_thread_finished(self):
        """Restore the toolbar and progress state after the worker terminates."""
        try:
            self.bs_btn.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.bs_btn.setText("↻ Bootstrap K")
        self.bs_btn.setStyleSheet(self._btn_style('#7C3AED'))
        self.bs_btn.clicked.connect(self._run_bootstrap)
        self.progress.setVisible(False)
        self.eval_btn.setEnabled(True)
        self.cluster_btn.setEnabled(bool(self.eval_results))
        self._bootstrap_worker = None

    def _cancel_bootstrap(self):
        """Request the running bootstrap worker to stop after the current pass."""
        worker = getattr(self, '_bootstrap_worker', None)
        if worker is not None and worker.isRunning():
            worker.cancel()
            self.status.setText("Cancelling bootstrap…")

    def _determine_optimal_k(self):
        """Compute the optimal K independently for each enabled metric.

        Each algorithm casts one vote per metric for the K it prefers under
        that metric's registry selection rule (maximisation, minimisation, or
        elbow/Kneedle), and ties are broken by the best mean score in the
        metric's ``direction``. The per-metric winners populate the toolbar
        chips, and the best-scoring algorithm at each winning K is recorded for
        the chip tooltip. This follows the "use several indices and let
        agreement decide" guidance of Ikotun, Habyarimana & Ezugwu
        (*Heliyon* 11, 2025, e41953); the per-metric voting and tie-break are
        delegated to :func:`_vote_optimal_per_metric`.
        """
        self.optimal_per_metric = {}
        self.optimal_algo_per_metric = {}

        if not self.eval_results:
            self.optimal_k = None
            self.optimal_algo = None
            self.selected_metric = None
            return

        enabled = self.node.config.get('enabled_metrics', list(DEFAULT_METRICS))
        enabled = [m for m in enabled if m in METRIC_REGISTRY]

        picks, _ = _vote_optimal_per_metric(
            self.eval_results, self._elbow_k, enabled)

        for metric, chosen_k in picks.items():
            self.optimal_per_metric[metric] = int(chosen_k)
            scores_key = METRIC_REGISTRY[metric]['key']
            lower_better = (METRIC_REGISTRY[metric]['direction'] == 'min')
            best_score = np.inf if lower_better else -np.inf
            best_algo = None
            for algo, res in self.eval_results.items():
                k_vals = res.get('k_values', [])
                scores = res.get(scores_key, [])
                if chosen_k in k_vals and len(scores) == len(k_vals):
                    s = scores[k_vals.index(chosen_k)]
                    better = s < best_score if lower_better else s > best_score
                    if better:
                        best_score = s
                        best_algo = algo
            self.optimal_algo_per_metric[metric] = best_algo

        if self.optimal_per_metric:
            default = ('Silhouette' if 'Silhouette' in self.optimal_per_metric
                       else next(iter(self.optimal_per_metric)))
            self.selected_metric = default
            self.optimal_k = self.optimal_per_metric[default]
            self.optimal_algo = self.optimal_algo_per_metric.get(default)
        else:
            self.selected_metric = None
            self.optimal_k = None
            self.optimal_algo = None

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
            if self.selected_metric:
                txt += f"  [{self.selected_metric}]"
            if self.optimal_algo:
                txt += f"  ({self.optimal_algo})"
            self.optimal_label.setText(txt)
        else:
            self.optimal_label.setText("Optimal K: —")

    def _update_metric_picks_ui(self):
        """Rebuild the per-metric K-pick chips in the toolbar.

        When bootstrap data is available, each chip also displays the
        fraction of bootstraps that picked the same K, e.g. "Silhouette:
        K=4 (87%)". The chip tooltip lists the top-3 K's seen in the
        bootstrap distribution.
        """
        while self.metric_picks_layout.count():
            item = self.metric_picks_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        if not self.optimal_per_metric:
            return

        for metric, k in self.optimal_per_metric.items():
            color = METRIC_COLORS.get(metric, '#64748B')
            selected = (metric == self.selected_metric)
            bg = color if selected else '#FFFFFF'
            fg = 'white' if selected else color
            algo_hint = self.optimal_algo_per_metric.get(metric, '')

            stab = self.bootstrap_stability.get(metric)
            stab_pct = None
            if stab and stab.get('n', 0) > 0:
                dist = stab.get('distribution', {})
                stab_pct = dist.get(k, 0) / stab['n']
                label_text = f"{metric}: K={k} ({stab_pct:.0%})"
            else:
                label_text = f"{metric}: K={k}"

            btn = QPushButton(label_text)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {bg}; color: {fg};
                    border: 1.4px solid {color}; padding: 3px 10px;
                    border-radius: 11px; font-size: 11px;
                    font-weight: {'bold' if selected else 'normal'};
                }}
                QPushButton:hover {{ background: {color}; color: white; }}
            """)
            tip = f"Use K={k} (best by {metric}"
            if algo_hint:
                tip += f", top algo: {algo_hint}"
            tip += ")"
            if stab:
                top3 = sorted(stab['distribution'].items(),
                              key=lambda kv: -kv[1])[:3]
                lines = [
                    f"\n\nBootstrap stability (n={stab['n']}):",
                    f"  • This K ({k}): {stab_pct:.0%}",
                ]
                for kk, count in top3:
                    if kk == k:
                        continue
                    lines.append(
                        f"  • K={kk}: {count / stab['n']:.0%}")
                lines.append(
                    f"  Most-picked K in bootstrap: "
                    f"{stab['mode_k']} ({stab['mode_frac']:.0%})")
                tip += '\n'.join(lines)
            btn.setToolTip(tip)
            btn.clicked.connect(
                lambda _, m=metric, kk=k: self._select_metric_pick(m, kk))
            self.metric_picks_layout.addWidget(btn)

    def _select_metric_pick(self, metric, k):
        """Switch the active K selection to the given metric's suggestion.

    Args:
        metric (str): Metric name whose K should become active.
        k (int): K value to select.
    """
        self.selected_metric = metric
        self.optimal_k = k
        self.optimal_algo = self.optimal_algo_per_metric.get(metric)
        idx = self.k_combo.findText(str(k))
        if idx >= 0:
            self.k_combo.setCurrentIndex(idx)
        self._update_optimal_label()
        self._update_metric_picks_ui()
        self._refresh_eval_plot()
        self.status.setText(
            f"K={k} selected via {metric} — click ② Cluster to apply")

    def _refresh_eval_plot(self):
        if not self.eval_results:
            return
        view = self.algo_view.currentText() or 'All Algorithms'
        scope = (self.eval_scope_combo.currentText()
                 if hasattr(self, 'eval_scope_combo') else 'Pooled')
        if scope == 'Per-sample' and self._is_multi() and self.per_sample_eval:
            _draw_evaluation_per_sample(
                self.eval_fig, self.per_sample_eval, self.node.config,
                per_sample_optk=self.per_sample_optk, view_algo=view,
                selected_metric=self.selected_metric)
        else:
            _draw_evaluation(self.eval_fig, self.eval_results, self.node.config,
                             self.optimal_k, view,
                             optimal_per_metric=self.optimal_per_metric,
                             selected_metric=self.selected_metric)
        self.eval_canvas.draw()


    def _run_clustering(self):
        """Launch the clustering pipeline on a background worker thread.

        Validates the selected K, prepares the cached data reference, disables
        the trigger button, and starts a :class:`_ClusterWorker`.  All drawing
        happens later on the main thread in :meth:`_on_cluster_done` as the
        worker's signals arrive, so the UI never freezes during computation.
        """
        k_text = self.k_combo.currentText()
        sel_k = int(k_text) if k_text else self.optimal_k
        if not sel_k:
            return
        if getattr(self, '_cluster_worker', None) is not None \
                and self._cluster_worker.isRunning():
            return

        elements = self._get_elements()
        enabled = self.node.config.get('enabled_algorithms',
                                       ['K-Means', 'Hierarchical', 'DBSCAN'])

        self.status.setText(f"Clustering with K={sel_k}…")
        self.progress.setVisible(True)
        self._set_progress(0.0)
        self.cluster_btn.setEnabled(False)

        if 'SOM' in enabled:
            self.tabs.setCurrentIndex(self.som_tab_idx)

        worker = _ClusterWorker(self, sel_k, elements,
                                self._data_matrix_cache, enabled)
        worker.progressed.connect(self._on_cluster_progress)
        worker.som_snapshot.connect(self._on_som_snapshot)
        worker.done.connect(self._on_cluster_done)
        worker.failed.connect(self._on_cluster_failed)
        worker.finished.connect(self._on_cluster_thread_finished)
        self._cluster_worker = worker
        worker.start()

    def _set_progress(self, pct):
        """Set the toolbar progress bar from a 0-100 percentage.

        The underlying bar runs on a high-resolution integer scale
        (``PROGRESS_RESOLUTION`` steps) so fractional percentages from the
        evaluation and bootstrap workers render smoothly with one decimal of
        precision rather than snapping to whole percents.

        Args:
            pct (float): Completion percentage in the range 0-100.
        """
        pct = max(0.0, min(100.0, float(pct)))
        self.progress.setValue(int(round(pct / 100.0 * PROGRESS_RESOLUTION)))
        self.progress.setFormat("%.1f%%" % pct)

    def _on_cluster_progress(self, pct, message):
        """Update the progress bar and status text from worker signals.

        Args:
            pct (float): Percent complete (0-100); fractional values are
                rendered at one-decimal resolution.
            message (str): Status message to display.
        """
        self._set_progress(pct)
        self.status.setText(message)

    def _on_som_snapshot(self, weights, t, total):
        """Render a live SOM convergence frame during training.

        Builds a lightweight transient SOM view from the in-progress weights so
        the user can watch the map self-organise.  Cluster labels aren't final
        yet, so neurons are coloured by a quick provisional grouping.

        Args:
            weights (np.ndarray): Snapshot copy of neuron weights.
            t (int): Current training iteration.
            total (int): Total training iterations.
        """
        try:
            cfg = self.node.config
            rows = cfg.get('som_rows', 10)
            cols = cfg.get('som_cols', 10)
            self.som_fig.clear()
            ax = self.som_fig.add_subplot(111)
            u = np.linalg.norm(
                weights.reshape(rows, cols, -1), axis=2)
            im = ax.imshow(u, cmap=cfg.get('som_sequential_cmap', 'viridis'),
                           interpolation='nearest', aspect='auto')
            fp_title, col = _font_scale(cfg, 'title')
            fp_lbl, _ = _font_scale(cfg, 'label')
            ax.set_title(f'SOM training… iteration {t}/{total}',
                         fontproperties=fp_title, color=col, pad=8)
            ax.set_xlabel('Column', fontproperties=fp_lbl, color=col)
            ax.set_ylabel('Row', fontproperties=fp_lbl, color=col)
            self.som_fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            self.som_canvas.draw()
        except Exception:
            pass

    def _on_cluster_done(self, payload):
        """Finalise clustering results on the main thread and draw all figures.

        Args:
            payload (dict): Result bundle from the worker containing ``data``,
                ``elements_eff`` and ``sel_k``.
        """
        try:
            data = payload['data']
            elements_eff = payload['elements_eff']
            sel_k = payload['sel_k']
            self._data_matrix_cache = data

            self.node.config['_sample_arr'] = self._particle_samples
            self.node.config['_sample_names'] = (
                list(np.unique(self._particle_samples))
                if self._particle_samples is not None else [])

            _draw_clustering(self.cluster_fig, self.final_results, data,
                             self.characterisation, self.node.config,
                             input_data=self.node.input_data)
            self.cluster_canvas.draw()

            self._hover_ann = {}
            self._elements_cache = elements_eff

            prev_sel = list(self.node.config.get(
                'overview_selected_elements', []))
            self.node.config['overview_selected_elements'] = [
                e for e in prev_sel if e in elements_eff
            ]
            self._refresh_overview_elem_btn()

            self.ov_algo.blockSignals(True)
            self.ov_algo.clear()
            for a in self.characterisation:
                self.ov_algo.addItem(a)
            if self.optimal_algo and self.optimal_algo in self.characterisation:
                self.ov_algo.setCurrentText(self.optimal_algo)
            self.ov_algo.blockSignals(False)
            self._draw_overview()

            self.export_btn.setEnabled(True)
            self._set_progress(100.0)
            self.status.setText(f"Clustering complete — K={sel_k}")

            if data.shape[1] >= 3:
                self._draw_3d()

            if 'SOM' in self.final_results and self._som_obj is not None:
                som_labels = self.final_results['SOM'].get('labels')
                if som_labels is not None:
                    _draw_som_grid(self.som_fig, self._som_obj,
                                   self._som_neuron_labels, som_labels,
                                   self.node.config,
                                   sample_labels=self._particle_samples,
                                   input_data=self.node.input_data)
                    self.som_canvas.draw()
                    self.tabs.setCurrentIndex(self.som_tab_idx)
                    return
            if (self.node.config.get('selected_algorithm') == 'Hierarchical'
                    and self.node.config.get('hier_show_dendrogram', False)):
                self._draw_dendrogram()
                self.tabs.setCurrentIndex(self.dendro_tab_idx)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Rendering failed:\n{e}")
            self.status.setText("Clustering failed")

    def _on_cluster_failed(self, message):
        """Report a worker-thread failure to the user.

        Args:
            message (str): Exception message from the worker.
        """
        QMessageBox.critical(self, "Error", f"Clustering failed:\n{message}")
        self.status.setText("Clustering failed")

    def _on_cluster_thread_finished(self):
        """Clean up after the worker thread terminates (success or failure)."""
        self.progress.setVisible(False)
        self.cluster_btn.setEnabled(True)
        self._cluster_worker = None

    def closeEvent(self, event):
        """Ensure a running clustering worker finishes before teardown.

        Args:
            event (QCloseEvent): The close event forwarded by Qt.
        """
        worker = getattr(self, '_cluster_worker', None)
        if worker is not None and worker.isRunning():
            worker.wait(5000)
        ev = getattr(self, '_eval_worker', None)
        if ev is not None and ev.isRunning():
            ev.wait(5000)
        super().closeEvent(event)

    def _live_k_supported(self):
        """Return whether the current algorithm supports live K dragging.

        Live mode is only offered for algorithms that re-solve cheaply for a
        new K on already-prepared data: Hierarchical (recut of a cached tree)
        and K-Means (fast refit).  All others stay on the explicit button.

        Returns:
            bool: True if the single selected algorithm supports live K.
        """
        enabled = self.node.config.get('enabled_algorithms',
                                       ['K-Means', 'Hierarchical', 'DBSCAN'])
        return len(enabled) == 1 and enabled[0] in ('Hierarchical', 'K-Means')

    def _update_live_k_availability(self):
        """Enable or disable the Live checkbox based on the current algorithm.

        Called when eval finishes or the algorithm changes.  When live mode is
        not supported, the checkbox is unchecked and disabled with an
        explanatory tooltip so the user understands why.
        """
        ok = self._live_k_supported()
        self.live_k_check.setEnabled(ok)
        if not ok:
            self.live_k_check.setChecked(False)
            enabled = self.node.config.get('enabled_algorithms', [])
            if len(enabled) != 1:
                self.live_k_check.setToolTip(
                    "Live K needs exactly one algorithm selected.")
            else:
                self.live_k_check.setToolTip(
                    f"{enabled[0]} is too slow for live K — use the Cluster "
                    f"button.\nLive K supports Hierarchical and K-Means.")
        else:
            self.live_k_check.setToolTip(
                "Re-cluster live as you drag K.\n"
                "Hierarchical recuts its tree instantly; K-Means refits fast.")

    def _on_k_combo_changed(self, text):
        """Sync the slider to the combo when the combo changes.

        Args:
            text (str): New combo text (the selected K as a string).
        """
        if not text:
            return
        try:
            k = int(text)
        except ValueError:
            return
        if self.k_slider.value() != k:
            self.k_slider.blockSignals(True)
            self.k_slider.setValue(k)
            self.k_slider.blockSignals(False)

    def _on_k_slider_changed(self, k):
        """Sync the combo to the slider and, if live mode is on, schedule a recut.

        Args:
            k (int): New K value from the slider.
        """
        txt = str(k)
        if self.k_combo.currentText() != txt:
            self.k_combo.blockSignals(True)
            idx = self.k_combo.findText(txt)
            if idx >= 0:
                self.k_combo.setCurrentIndex(idx)
            self.k_combo.blockSignals(False)
        if (self.live_k_check.isChecked()
                and self._live_k_supported()
                and self._data_matrix_cache is not None):
            self.status.setText(f"K = {k} …")
            self._live_k_timer.start()

    def _do_live_k(self):
        """Recompute clustering for the current slider K on the main thread.

        Debounced via ``_live_k_timer``.  Hierarchical uses a cached linkage
        tree and recuts with ``fcluster`` (near-instant); K-Means does a fast
        refit.  Both are quick enough to run inline without freezing the UI, so
        no worker thread is needed here — that keeps the animation snappy.
        """
        if self._data_matrix_cache is None or not self._live_k_supported():
            return
        if getattr(self, '_cluster_worker', None) is not None \
                and self._cluster_worker.isRunning():
            self._live_k_timer.start()
            return

        k = self.k_slider.value()
        data = self._data_matrix_cache
        algo = self.node.config['enabled_algorithms'][0]
        cfg = self.node.config

        try:
            if algo == 'Hierarchical':
                labels = self._hier_recut(data, k, cfg)
            else:
                labels = KMeans(
                    n_clusters=k, random_state=42,
                    n_init=cfg.get('kmeans_n_init', 10),
                    max_iter=cfg.get('kmeans_max_iter', 300),
                ).fit_predict(data)

            self.final_results = {algo: {
                'labels': labels,
                'n_clusters': len(np.unique(labels[labels >= 0])),
                'n_noise': int(np.sum(labels == -1)),
            }}
            elements_eff = self._elements_cache or self._get_elements()
            self._characterise(elements_eff, data)
            self._rebuild_display_labels()

            _draw_clustering(self.cluster_fig, self.final_results, data,
                             self.characterisation, cfg,
                             input_data=self.node.input_data)
            self.cluster_canvas.draw()
            self._hover_ann = {}
            if data.shape[1] >= 3:
                self._draw_3d()

            self.ov_algo.blockSignals(True)
            self.ov_algo.clear()
            for a in self.characterisation:
                self.ov_algo.addItem(a)
            self.ov_algo.blockSignals(False)
            self._draw_overview()

            n_cl = self.final_results[algo]['n_clusters']
            self.status.setText(f"Live K = {k}  →  {n_cl} clusters")
        except Exception as e:
            self.status.setText(f"Live K failed: {e}")

    def _hier_recut(self, data, k, cfg):
        """Cut a cached hierarchical linkage tree at K clusters.

        The linkage tree is the expensive part of hierarchical clustering and
        is independent of K, so it is computed once and cached keyed on the
        data identity plus linkage/metric settings.  Subsequent K changes only
        recut the cached tree with ``fcluster`` — effectively instant — which
        is what makes the live K slider animate clusters merging and splitting.

        Args:
            data (np.ndarray): Preprocessed data matrix.
            k (int): Desired number of clusters.
            cfg (dict): Configuration dictionary (linkage/metric).

        Returns:
            np.ndarray: Zero-based cluster label per sample.
        """
        linkage_method = cfg.get('hier_linkage', 'ward')
        metric = (cfg.get('hier_metric', 'euclidean')
                  if linkage_method != 'ward' else 'euclidean')
        key = (id(data), data.shape, linkage_method, metric)
        if self._linkage_cache_key != key or self._linkage_cache is None:
            self._linkage_cache = scipy_linkage(
                data, method=linkage_method, metric=metric)
            self._linkage_cache_key = key
        labels = scipy_fcluster(self._linkage_cache, t=k, criterion='maxclust')
        return labels - 1


    def _build_som_tab(self):
        tab = QWidget()
        vl = QVBoxLayout(tab)
        vl.setContentsMargins(4, 4, 4, 4)
        hl = QHBoxLayout()
        hl.addWidget(QLabel("SOM Grid Map — active only when SOM algorithm is selected"))
        hl.addStretch()
        po = self._make_popout_btn(lambda: self._pop_out_figure('som'))
        hl.addWidget(po)
        vl.addLayout(hl)
        self.som_fig = Figure(figsize=(12, 6), dpi=110, tight_layout=True)
        self.som_canvas = _SafeFigureCanvas(self.som_fig)
        self.som_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.som_canvas.customContextMenuRequested.connect(
            lambda pos: self._ctx_menu(pos, 'som'))
        vl.addWidget(self.som_canvas, stretch=1)
        self.som_tab_idx = self.tabs.addTab(tab, "⑤ SOM Grid")

    def _characterise(self, elements, data):
        """Generate cluster characterisation with real element-% composition labels.

        Args:
            elements (Any): The element list used to build the data matrix.
                When the low-detection filter dropped columns this is the
                filtered list (``self._elements_filtered``).
            data (Any): The embedded data matrix (unused here — kept for
                signature compatibility).
        """
        if not self.final_results:
            return
        self.characterisation = {}
        dt = self.node.config.get('data_type_display', 'Counts')
        data_key = DATA_KEY_MAP.get(dt, 'elements')

        all_particles = self.node.input_data.get('particle_data', [])
        if self._particle_indices is not None:
            particles = [all_particles[i] for i in self._particle_indices
                         if i < len(all_particles)]
        else:
            particles = list(all_particles)

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
                    vals = [p.get(data_key, {}).get(el, 0) for p in cp]
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

                means_all = {}
                for el in elements:
                    all_vals = [p.get(data_key, {}).get(el, 0) for p in cp]
                    means_all[el] = np.mean(all_vals)

                total_mean = sum(means_all.values())
                if total_mean > 0:
                    pcts = {e: (v / total_mean * 100)
                            for e, v in means_all.items()}
                else:
                    pcts = {e: 0.0 for e in elements}

                sig = sorted(
                    [(e, p) for e, p in pcts.items() if p > 0],
                    key=lambda t: t[1], reverse=True,
                )

                dom = [(e, p / 100) for e, p in sig[:3]]

                sample_breakdown = {}
                if self._particle_samples is not None:
                    cluster_samples = self._particle_samples[mask]
                    total = len(cluster_samples)
                    if total > 0:
                        for sname in np.unique(cluster_samples):
                            count = int(np.sum(cluster_samples == sname))
                            sample_breakdown[str(sname)] = {
                                'count': count,
                                'fraction': count / total,
                            }

                self.characterisation[algo][cid] = {
                    'element_stats':      estats,
                    'element_pcts':       pcts,
                    'composition':        sig,
                    'dominant_elements':  dom,
                    'cluster_type':       '',
                    'cluster_type_short': '',
                    'particle_count':     len(cp),
                    'sample_breakdown':   sample_breakdown,
                }

        self._rebuild_display_labels()


    def _rebuild_display_labels(self):
        """Recompute cluster_type_short and cluster_type from stored composition.

        Reads display_min_pct and display_max_isotopes from the current config
        to filter and cap the element list shown in every figure label.  Called
        once at the end of _characterise and again whenever display settings
        change, so labels stay live without re-clustering.
        """
        cfg = self.node.config
        _min_pct = cfg.get('display_min_pct', 1.0)
        _max_iso = int(cfg.get('display_max_isotopes', 4))
        _lm = cfg.get('label_mode', cfg.get('overview_label_mode', 'Symbol'))
        for algo in self.characterisation:
            for cd in self.characterisation[algo].values():
                full_sig = cd.get('composition', [])
                sig = [(e, p) for e, p in full_sig if p >= _min_pct]
                if sig:
                    ctype_full = '  '.join(
                        f"{format_element_label(e, _lm, Renderer.MATHTEXT)} {p:.1f}%"
                        for e, p in sig
                    )
                    ctype_short = '+'.join(
                        format_element_label(e, _lm, Renderer.MATHTEXT)
                        for e, _ in sig[:_max_iso]
                    )
                    if len(sig) > _max_iso:
                        ctype_short += f'+{len(sig) - _max_iso}…'
                else:
                    ctype_full = 'No signal'
                    ctype_short = 'No signal'
                cd['cluster_type'] = ctype_full
                cd['cluster_type_short'] = ctype_short

    def _apply_display_settings(self):
        """Rebuild display labels and redraw all figures without re-clustering.

        Safe to call whenever display-only settings change.  Skips silently if
        no clustering results are available yet.
        """
        if not self.characterisation:
            return
        self._rebuild_display_labels()
        cfg = self.node.config
        data = self._data_matrix_cache
        if data is not None and self.final_results:
            _draw_clustering(self.cluster_fig, self.final_results, data,
                             self.characterisation, cfg,
                             input_data=self.node.input_data)
            self.cluster_canvas.draw()
            self._hover_ann = {}
            if data.shape[1] >= 3:
                self._draw_3d()
        self._draw_overview()
        if self.eval_results:
            self._refresh_eval_plot()
        if (getattr(self, '_som_obj', None) is not None
                and self.final_results):
            som_labels = self.final_results.get('SOM', {}).get('labels')
            if som_labels is not None:
                _draw_som_grid(self.som_fig, self._som_obj,
                               self._som_neuron_labels, som_labels,
                               cfg,
                               sample_labels=self._particle_samples,
                               input_data=self.node.input_data)
                self.som_canvas.draw()

    def _export_results(self):
        """Serialise clustering results and characterisation to a JSON file.

        Opens a save-file dialog, then writes configuration, optimal K,
        evaluation results, and per-cluster characterisation.
        """
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
                    entry = {
                        'cluster_label': _cluster_label_short(cid),
                        'cluster_type': cd['cluster_type'],
                        'particle_count': cd['particle_count'],
                        'dominant_elements': cd['dominant_elements'],
                    }
                    if cd.get('sample_breakdown'):
                        entry['sample_breakdown'] = cd['sample_breakdown']
                    export['cluster_characterisation'][algo][str(cid)] = entry
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
        'scaling': 'CLR',
        'dim_reduction': 'None',
        'n_components': 2,
        'filter_zeros': True,
        'min_particle_type_count': 5,
        'cluster_color_by': 'Cluster',
        'bootstrap_n': 50,
        'bootstrap_seed': 42,
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
        'hdbscan_min_cluster_size': 5,
        'hdbscan_min_samples': 5,
        'hdbscan_metric': 'euclidean',
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
        'gmm_covariance_type': 'full',
        'som_rows': 10,
        'som_cols': 10,
        'som_sigma': 1.0,
        'som_lr': 0.5,
        'som_n_iter': 2000,
        'som_final_algo': 'Hierarchical (Ward)',
        'som_cluster_cmap': 'CLUSTER_COLORS',
        'y_axis_unit': 'count',
        'som_sequential_cmap': 'viridis',
        'som_show_u_matrix': True,
        'som_show_hit_count': True,
        'min_clusters': 2,
        'max_clusters': 20,
        'auto_select_k': True,
        'enabled_metrics': list(DEFAULT_METRICS),
        'font_family': 'Times New Roman',
        'font_size': 12,
        'font_bold': False,
        'font_italic': False,
        'font_color': '#000000',
        'label_mode': 'Symbol',
        'overview_view':            'Strips',
        'overview_colormap':        'YlOrRd',
        'overview_show_values':     True,
        'display_min_pct':             1.0,
        'display_max_isotopes':        4,
        'overview_group_by_dominant':  True,
        'overview_selected_elements': [],
        'overview_panel_metric':       'Detections',
        'overview_show_sample_strip':  True,
        'overview_label_mode':         'Symbol',
        'plot3d_hidden_samples':       [],
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
        self._active_dialog = ClusteringDisplayDialog(self, parent_window)
        self._active_dialog.show()
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