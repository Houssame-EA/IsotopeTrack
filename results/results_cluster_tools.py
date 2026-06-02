"""Custom Cluster Test — exhaustive pipeline search against known components.

Standalone companion to ``results_cluster.py``.  It reads the same input data
and re-uses a few side-effect-free helpers when importable, but never modifies
the existing clustering behaviour.

You provide the components you prepared (for example ``Ag ; Ti ; Ce ; FeNiCo``)
and the tool sweeps a grid of complete pipelines — data type, scaling,
dimensionality reduction, algorithm and that algorithm's own hyper-parameters
(including the cluster count, left open) — scoring every result against the
ground truth derived from your component list, using external validity indices
(Adjusted Rand Index, AMI, V-measure, …) alongside the usual internal indices
(Silhouette, Calinski-Harabasz, …).

It answers two questions: which complete pipeline best reproduces your known
components, and which scoring metric to trust when no ground truth is available
(by correlating each internal metric against the external truth across the grid).

Ground truth is decided by each particle's dominant element: if a particle's
strongest element belongs to a named component the particle is that component,
otherwise it is the ``"other"`` group (coincidences, outliers, background).
Nothing is excluded; a pipeline that parks ``"other"`` particles in a noise
label or its own cluster is rewarded for it.

The engine (everything above the GUI guard) has no Qt dependency and is fully
usable and testable on its own.  The GUI is defined only when PySide6 imports.
"""

from __future__ import annotations

import time
import threading
import itertools

import numpy as np

from sklearn.cluster import (
    KMeans, MiniBatchKMeans, AgglomerativeClustering, SpectralClustering,
    Birch, DBSCAN, OPTICS, MeanShift,
)
from sklearn.mixture import GaussianMixture
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.metrics import (
    adjusted_rand_score, adjusted_mutual_info_score,
    normalized_mutual_info_score, fowlkes_mallows_score,
    homogeneity_completeness_v_measure,
)

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

try:
    from results.results_cluster import (
        _apply_clr, _apply_ilr, _apply_robust_zscore,
        DATA_KEY_MAP, DENSITY_BASED_ALGOS, CVI_FUNCS, METRIC_REGISTRY,
    )
    _HOST_OK = True
except Exception:
    _HOST_OK = False

    DATA_KEY_MAP = {
        'Counts': 'elements',
        'Element Mass (fg)': 'element_mass_fg',
        'Particle Mass (fg)': 'particle_mass_fg',
        'Element Moles (fmol)': 'element_moles_fmol',
        'Particle Moles (fmol)': 'particle_moles_fmol',
        'Element Mass %': 'element_mass_fg',
        'Particle Mass %': 'particle_mass_fg',
        'Element Mole %': 'element_moles_fmol',
        'Particle Mole %': 'particle_moles_fmol',
    }
    DENSITY_BASED_ALGOS = {'DBSCAN', 'HDBSCAN', 'OPTICS', 'Mean Shift'}

    def _apply_clr(matrix):
        """Centred-log-ratio transform of a non-negative composition matrix."""
        eps = 1e-10
        X = np.where(matrix <= 0, eps, matrix.astype(np.float64))
        log_X = np.log(X)
        return log_X - log_X.mean(axis=1, keepdims=True)

    def _apply_ilr(matrix):
        """Isometric-log-ratio transform yielding ``p - 1`` coordinates."""
        clr = _apply_clr(matrix)
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
        """Median / MAD robust z-score normalisation, column-wise."""
        X = matrix.astype(np.float64)
        med = np.median(X, axis=0)
        mad = np.median(np.abs(X - med), axis=0)
        mad = np.where(mad < 1e-10, 1e-10, mad)
        return (X - med) / mad

    from sklearn.metrics import (
        silhouette_score, calinski_harabasz_score, davies_bouldin_score,
    )
    CVI_FUNCS = {
        'silhouette_scores':        lambda d, l: float(silhouette_score(d, l)),
        'calinski_harabasz_scores': lambda d, l: float(calinski_harabasz_score(d, l)),
        'davies_bouldin_scores':    lambda d, l: float(davies_bouldin_score(d, l)),
    }
    METRIC_REGISTRY = {
        'Silhouette':        {'key': 'silhouette_scores',        'direction': 'max'},
        'Calinski-Harabasz': {'key': 'calinski_harabasz_scores', 'direction': 'max'},
        'Davies-Bouldin':    {'key': 'davies_bouldin_scores',    'direction': 'min'},
    }


def _v_measure(truth, pred):
    """V-measure (harmonic mean of homogeneity and completeness)."""
    return float(homogeneity_completeness_v_measure(truth, pred)[2])


def _homogeneity(truth, pred):
    """Homogeneity score: each cluster contains a single truth class."""
    return float(homogeneity_completeness_v_measure(truth, pred)[0])


def _completeness(truth, pred):
    """Completeness score: each truth class falls into a single cluster."""
    return float(homogeneity_completeness_v_measure(truth, pred)[1])


EXTERNAL_METRICS = {
    'ARI': {
        'display': 'Adjusted Rand Index',
        'func': lambda t, p: float(adjusted_rand_score(t, p)),
        'direction': 'max', 'range': (-0.5, 1.0),
    },
    'AMI': {
        'display': 'Adjusted Mutual Information',
        'func': lambda t, p: float(adjusted_mutual_info_score(t, p)),
        'direction': 'max', 'range': (0.0, 1.0),
    },
    'NMI': {
        'display': 'Normalized Mutual Information',
        'func': lambda t, p: float(normalized_mutual_info_score(t, p)),
        'direction': 'max', 'range': (0.0, 1.0),
    },
    'V-measure': {
        'display': 'V-measure',
        'func': _v_measure,
        'direction': 'max', 'range': (0.0, 1.0),
    },
    'Homogeneity': {
        'display': 'Homogeneity',
        'func': _homogeneity,
        'direction': 'max', 'range': (0.0, 1.0),
    },
    'Completeness': {
        'display': 'Completeness',
        'func': _completeness,
        'direction': 'max', 'range': (0.0, 1.0),
    },
    'FMI': {
        'display': 'Fowlkes-Mallows Index',
        'func': lambda t, p: float(fowlkes_mallows_score(t, p)),
        'direction': 'max', 'range': (0.0, 1.0),
    },
}

DEFAULT_EXTERNAL_METRICS = ['ARI', 'AMI', 'V-measure']
PRIMARY_EXTERNAL_METRIC = 'ARI'

OTHER_LABEL_NAME = 'other'

ALGO_PARAM_SPECS = {
    'K-Means': {
        'density': False, 'needs_k': True,
        'params': {
            'k':        {'kind': 'int_range', 'label': 'Clusters (K)',
                         'default': list(range(2, 11)), 'min': 2, 'max': 100},
            'n_init':   {'kind': 'int_range', 'label': 'n_init',
                         'default': [10], 'min': 1, 'max': 50},
            'max_iter': {'kind': 'int_range', 'label': 'max_iter',
                         'default': [300], 'min': 10, 'max': 2000},
        },
    },
    'MiniBatch K-Means': {
        'density': False, 'needs_k': True,
        'params': {
            'k':          {'kind': 'int_range', 'label': 'Clusters (K)',
                           'default': list(range(2, 11)), 'min': 2, 'max': 100},
            'n_init':     {'kind': 'int_range', 'label': 'n_init',
                           'default': [3], 'min': 1, 'max': 50},
            'batch_size': {'kind': 'int_range', 'label': 'batch_size',
                           'default': [1024], 'min': 32, 'max': 8192},
            'max_iter':   {'kind': 'int_range', 'label': 'max_iter',
                           'default': [100], 'min': 10, 'max': 2000},
        },
    },
    'Hierarchical': {
        'density': False, 'needs_k': True,
        'params': {
            'k':       {'kind': 'int_range', 'label': 'Clusters (K)',
                        'default': list(range(2, 11)), 'min': 2, 'max': 100},
            'linkage': {'kind': 'choice', 'label': 'linkage',
                        'options': ['ward', 'complete', 'average', 'single'],
                        'default': ['ward']},
            'metric':  {'kind': 'choice', 'label': 'metric',
                        'options': ['euclidean', 'manhattan', 'cosine'],
                        'default': ['euclidean']},
        },
    },
    'Spectral': {
        'density': False, 'needs_k': True,
        'params': {
            'k':           {'kind': 'int_range', 'label': 'Clusters (K)',
                            'default': list(range(2, 11)), 'min': 2, 'max': 60},
            'affinity':    {'kind': 'choice', 'label': 'affinity',
                            'options': ['rbf', 'nearest_neighbors'],
                            'default': ['rbf']},
            'n_neighbors': {'kind': 'int_range', 'label': 'n_neighbors',
                            'default': [10], 'min': 2, 'max': 50},
        },
    },
    'Birch': {
        'density': False, 'needs_k': True,
        'params': {
            'k':                {'kind': 'int_range', 'label': 'Clusters (K)',
                                 'default': list(range(2, 11)), 'min': 2, 'max': 100},
            'threshold':        {'kind': 'float_range', 'label': 'threshold',
                                 'default': [0.5], 'min': 0.05, 'max': 5.0},
            'branching_factor': {'kind': 'int_range', 'label': 'branching_factor',
                                 'default': [50], 'min': 10, 'max': 200},
        },
    },
    'Gaussian Mixture': {
        'density': False, 'needs_k': True,
        'params': {
            'k':               {'kind': 'int_range', 'label': 'Components (K)',
                                'default': list(range(2, 11)), 'min': 2, 'max': 60},
            'covariance_type': {'kind': 'choice', 'label': 'covariance_type',
                                'options': ['full', 'tied', 'diag', 'spherical'],
                                'default': ['full']},
        },
    },
    'DBSCAN': {
        'density': True, 'needs_k': False,
        'params': {
            'eps':         {'kind': 'float_range', 'label': 'eps',
                            'default': [0.3, 0.5, 0.7, 1.0], 'min': 0.01, 'max': 50.0},
            'min_samples': {'kind': 'int_range', 'label': 'min_samples',
                            'default': [5], 'min': 1, 'max': 100},
            'metric':      {'kind': 'choice', 'label': 'metric',
                            'options': ['euclidean', 'manhattan', 'cosine'],
                            'default': ['euclidean']},
        },
    },
    'HDBSCAN': {
        'density': True, 'needs_k': False,
        'params': {
            'min_cluster_size': {'kind': 'int_range', 'label': 'min_cluster_size',
                                 'default': [5, 10, 25], 'min': 2, 'max': 500},
            'min_samples':      {'kind': 'int_range', 'label': 'min_samples',
                                 'default': [5], 'min': 1, 'max': 100},
            'metric':           {'kind': 'choice', 'label': 'metric',
                                 'options': ['euclidean', 'manhattan'],
                                 'default': ['euclidean']},
        },
    },
    'OPTICS': {
        'density': True, 'needs_k': False,
        'params': {
            'min_samples':    {'kind': 'int_range', 'label': 'min_samples',
                               'default': [5, 10], 'min': 2, 'max': 100},
            'metric':         {'kind': 'choice', 'label': 'metric',
                               'options': ['euclidean', 'manhattan', 'cosine'],
                               'default': ['euclidean']},
            'cluster_method': {'kind': 'choice', 'label': 'cluster_method',
                               'options': ['xi', 'dbscan'], 'default': ['xi']},
        },
    },
    'Mean Shift': {
        'density': True, 'needs_k': False,
        'params': {
            'bandwidth':    {'kind': 'float_range', 'label': 'bandwidth (0 = auto)',
                             'default': [0.0], 'min': 0.0, 'max': 50.0},
            'min_bin_freq': {'kind': 'int_range', 'label': 'min_bin_freq',
                             'default': [1], 'min': 1, 'max': 100},
        },
    },
    'SOM': {
        'density': False, 'needs_k': True, 'needs_som': True,
        'som_param_keys': ('som_rows', 'som_cols', 'som_sigma', 'som_lr',
                           'som_n_iter', 'som_final_algo'),
        'params': {
            'k':              {'kind': 'int_range', 'label': 'Final clusters (K)',
                              'default': list(range(2, 11)), 'min': 2, 'max': 100},
            'som_rows':       {'kind': 'int_range', 'label': 'Grid rows',
                              'default': [10], 'min': 3, 'max': 30},
            'som_cols':       {'kind': 'int_range', 'label': 'Grid cols',
                              'default': [10], 'min': 3, 'max': 30},
            'som_sigma':      {'kind': 'float_range', 'label': 'Sigma (σ)',
                              'default': [1.0], 'min': 0.1, 'max': 10.0},
            'som_lr':         {'kind': 'float_range', 'label': 'Learning rate',
                              'default': [0.5], 'min': 0.01, 'max': 1.0},
            'som_n_iter':     {'kind': 'int_range', 'label': 'Iterations',
                              'default': [2000], 'min': 100, 'max': 20000},
            'som_final_algo': {'kind': 'choice', 'label': 'Final algorithm',
                              'options': ['Hierarchical (Ward)',
                                          'Hierarchical (Average)',
                                          'Hierarchical (Complete)',
                                          'K-Means', 'Gaussian Mixture',
                                          'Spectral'],
                              'default': ['Hierarchical (Ward)']},
        },
    },
}

ALGORITHMS = list(ALGO_PARAM_SPECS.keys())

DATA_TYPES = list(DATA_KEY_MAP.keys())
SCALINGS = ['None', 'Robust Z-score', 'CLR', 'ILR']
DIM_REDUCTIONS = ['None', 'PCA', 't-SNE']

DEFAULT_DATA_TYPES = ['Counts']
DEFAULT_SCALINGS = ['None']
DEFAULT_DIM_REDUCTIONS = ['None']
DEFAULT_ALGORITHMS = ['K-Means']


def parse_components(text):
    """Parse a component string into ``[(name, [elements]), ...]``.

    Groups are separated by ``;`` or newlines.  Within a group, elements may be
    joined with ``+`` (``Fe+Ni+Co``) or written fused (``FeNiCo``, split on
    capital-letter boundaries).  ``Name=El1+El2`` gives an explicit label; for a
    fused token the label is kept exactly as typed.

    Args:
        text (str): The raw component string.

    Returns:
        list[tuple[str, list[str]]]: Ordered component definitions.
    """
    import re
    comps = []
    raw = [c.strip() for c in re.split(r'[;\n]', text) if c.strip()]
    for token in raw:
        name = None
        body = token
        if '=' in token:
            name, body = token.split('=', 1)
            name = name.strip()
            body = body.strip()
        if '+' in body:
            elems = [e.strip() for e in body.split('+') if e.strip()]
        else:
            elems = re.findall(r'\d*[A-Z][a-z]?', body)
            if not elems:
                elems = [body]
        if name is None:
            name = body
        comps.append((name, elems))
    return comps


def build_ground_truth(raw_matrix, elements, components, other_flags=None):
    """Assign each particle to a named component or to ``"other"``.

    A particle's truth label is the component owning its single strongest
    element.  Particles whose dominant element is not part of any named
    component — and particles with no signal — become ``"other"``.  An optional
    boolean ``other_flags`` mask forces rows to ``"other"`` regardless of
    composition; this is where a future coincidence/outlier tag plugs in.
    Nothing is dropped.

    Args:
        raw_matrix (np.ndarray): Pre-scaling matrix ``(n_particles, n_elements)``
            of non-negative element intensities.
        elements (list[str]): Column names aligned to ``raw_matrix`` columns.
        components (list[tuple[str, list[str]]]): Output of :func:`parse_components`.
        other_flags (np.ndarray or None): Optional boolean mask forcing rows to
            ``"other"``.

    Returns:
        dict: ``{'labels', 'names', 'name_to_id', 'other_id', 'counts',
                 'unmatched'}``.
    """
    import re

    def _symbol(label):
        """Bare element symbol from a column/component token.

        ``107Ag`` -> ``Ag``, ``48Ti`` -> ``Ti``, ``Ce`` -> ``Ce``.  
        """
        m = re.search(r'[A-Z][a-z]?', str(label))
        return m.group(0) if m else str(label).strip()

    elem_index = {e: i for i, e in enumerate(elements)}
    sym_index = {}
    for i, e in enumerate(elements):
        sym_index.setdefault(_symbol(e), i)

    elem_to_comp = {}
    comp_names = []
    for name, elems in components:
        present = []
        for e in elems:
            if e in elem_index:
                present.append(e)
            elif _symbol(e) in sym_index:
                present.append(elements[sym_index[_symbol(e)]])
        if not present:
            continue
        comp_names.append(name)
        for col in present:
            elem_to_comp.setdefault(col, name)

    names = comp_names + [OTHER_LABEL_NAME]
    name_to_id = {n: i for i, n in enumerate(names)}
    other_id = name_to_id[OTHER_LABEL_NAME]

    n = raw_matrix.shape[0]
    col_to_id = np.full(max(raw_matrix.shape[1], 1), other_id, dtype=int)
    for c, e in enumerate(elements):
        comp = elem_to_comp.get(e)
        if comp is not None:
            col_to_id[c] = name_to_id[comp]

    if n == 0 or raw_matrix.shape[1] == 0:
        labels = np.full(n, other_id, dtype=int)
    else:
        dom_col = np.argmax(raw_matrix, axis=1)
        labels = col_to_id[dom_col]
        labels[raw_matrix.sum(axis=1) <= 0] = other_id

    if other_flags is not None:
        labels[np.asarray(other_flags, dtype=bool)] = other_id

    counts = {nm: int(np.sum(labels == name_to_id[nm])) for nm in names}
    return {
        'labels': labels,
        'names': names,
        'name_to_id': name_to_id,
        'other_id': other_id,
        'counts': counts,
        'unmatched': counts[OTHER_LABEL_NAME],
    }


def _row_for_particle(p, data_type, elements):
    """Build one matrix row for a particle in the requested representation.

    Args:
        p (dict): A particle record.
        data_type (str): A key from :data:`DATA_TYPES`.
        elements (list[str]): Element columns, in order.

    Returns:
        list[float]: The row values for the requested data type.
    """
    dk = DATA_KEY_MAP.get(data_type, 'elements')
    raw = p.get(dk, {})
    d = raw if isinstance(raw, dict) else {}
    if data_type in ('Element Mass %', 'Particle Mass %',
                     'Element Mole %', 'Particle Mole %'):
        if 'Mass %' in data_type:
            total = (sum(d.get(e, 0) for e in elements)
                     if data_type == 'Element Mass %'
                     else p.get('particle_mass_fg', 0))
        else:
            total = (sum(d.get(e, 0) for e in elements)
                     if data_type == 'Element Mole %'
                     else p.get('particle_moles_fmol', 0))
        return [(d.get(e, 0) / total * 100 if total > 0 else 0) for e in elements]
    return [d.get(e, 0) for e in elements]


class Preprocessor:
    """Builds and caches preprocessed matrices for the sweep.

    Each ``(data_type, scaling, dim_reduction)`` matrix is computed once and
    reused across every algorithm and cluster count, which is what keeps a large
    grid tractable.  The kept-row set is fixed once from the count matrix so
    ground-truth labels stay aligned across all data types.
    """

    def __init__(self, particle_data, elements, filter_zeros=True,
                 tsne_random_state=42, n_components=2):
        """Initialise the cache and the fixed kept-row mask.

        Args:
            particle_data (list[dict]): Particle records.
            elements (list[str]): Active element columns, in order.
            filter_zeros (bool): Drop all-zero rows to match the host pipeline.
            tsne_random_state (int): Seed for reproducible t-SNE.
            n_components (int): Target dimensionality for PCA / t-SNE.
        """
        self.elements = list(elements)
        self.n_components = int(n_components)
        self.tsne_rs = tsne_random_state

        counts = np.array([_row_for_particle(p, 'Counts', self.elements)
                           for p in particle_data], dtype=float)
        if counts.size == 0:
            self.keep_mask = np.zeros(len(particle_data), dtype=bool)
        elif filter_zeros:
            self.keep_mask = np.any(counts > 0, axis=1)
        else:
            self.keep_mask = np.ones(len(counts), dtype=bool)

        self._particles = [p for p, k in zip(particle_data, self.keep_mask) if k]
        self._raw_cache = {}
        self._scaled_cache = {}
        self._reduced_cache = {}

    @property
    def n_rows(self):
        """Number of kept particles."""
        return len(self._particles)

    def raw_matrix(self, data_type):
        """Return the kept, unscaled matrix for ``data_type`` (cached)."""
        if data_type not in self._raw_cache:
            self._raw_cache[data_type] = np.array(
                [_row_for_particle(p, data_type, self.elements)
                 for p in self._particles], dtype=float)
        return self._raw_cache[data_type]

    def counts_matrix(self):
        """Return the kept count matrix used to build ground truth."""
        return self.raw_matrix('Counts')

    def _scaled(self, data_type, scaling):
        """Return the scaled matrix for one ``(data_type, scaling)`` (cached)."""
        key = (data_type, scaling)
        if key in self._scaled_cache:
            return self._scaled_cache[key]
        m = self.raw_matrix(data_type)
        if scaling == 'Robust Z-score':
            out = _apply_robust_zscore(m)
        elif scaling == 'CLR':
            out = _apply_clr(m)
        elif scaling == 'ILR':
            out = _apply_ilr(m)
        else:
            out = m.astype(np.float64)
        self._scaled_cache[key] = out
        return out

    def matrix(self, data_type, scaling, dim_reduction):
        """Return the fully preprocessed matrix for one pipeline (cached)."""
        key = (data_type, scaling, dim_reduction, self.n_components)
        if key in self._reduced_cache:
            return self._reduced_cache[key]
        m = self._scaled(data_type, scaling)
        if dim_reduction == 'PCA' and m.shape[1] > 1:
            nc = min(self.n_components, m.shape[1])
            m = PCA(n_components=nc).fit_transform(m)
        elif dim_reduction == 't-SNE' and m.shape[1] > 1:
            nc = min(self.n_components, 3)
            perp = min(30, max(5, (m.shape[0] - 1) // 3))
            m = TSNE(n_components=nc, random_state=self.tsne_rs,
                     init='pca', perplexity=perp).fit_transform(m)
        self._reduced_cache[key] = m
        return m


def run_algorithm(name, params, data, som_runner=None):
    """Fit one algorithm with explicit ``params`` and return integer labels.

    Estimator construction is implemented here rather than delegated to the host
    so the host code stays untouched and parameters can vary freely from the
    sweep grid.

    Args:
        name (str): Algorithm key from :data:`ALGO_PARAM_SPECS`.
        params (dict): Concrete parameter values (includes ``k`` for K-based
            algorithms).
        data (np.ndarray): Preprocessed data matrix.
        som_runner (callable or None): Optional hook for the host's SOM. Called
            as ``som_runner(k, data, som_params)`` where ``som_params`` carries
            the per-fit map hyperparameters (``som_rows``, ``som_cols``,
            ``som_sigma``, ``som_lr``, ``som_n_iter``, ``som_final_algo``); a
            two-argument ``som_runner(k, data)`` is still accepted for backward
            compatibility. Required for ``name == 'SOM'``; without it that
            algorithm is silently skipped (returns ``None``).

    Returns:
        np.ndarray or None: Integer labels (``-1`` = noise) or ``None`` on
            failure / unsupported configuration.
    """
    try:
        k = int(params.get('k', 2))
        if name == 'K-Means':
            return KMeans(n_clusters=k, random_state=42,
                          n_init=int(params.get('n_init', 10)),
                          max_iter=int(params.get('max_iter', 300))).fit_predict(data)
        if name == 'MiniBatch K-Means':
            return MiniBatchKMeans(n_clusters=k, random_state=42,
                                   n_init=int(params.get('n_init', 3)),
                                   batch_size=int(params.get('batch_size', 1024)),
                                   max_iter=int(params.get('max_iter', 100))
                                   ).fit_predict(data)
        if name == 'Hierarchical':
            linkage = params.get('linkage', 'ward')
            metric = 'euclidean' if linkage == 'ward' else params.get('metric', 'euclidean')
            return AgglomerativeClustering(n_clusters=k, linkage=linkage,
                                           metric=metric).fit_predict(data)
        if name == 'Spectral':
            aff = params.get('affinity', 'rbf')
            kw = dict(n_clusters=k, random_state=42, affinity=aff,
                      assign_labels='kmeans')
            if aff == 'nearest_neighbors':
                kw['n_neighbors'] = int(params.get('n_neighbors', 10))
            return SpectralClustering(**kw).fit_predict(data)
        if name == 'Birch':
            return Birch(n_clusters=k,
                         threshold=float(params.get('threshold', 0.5)),
                         branching_factor=int(params.get('branching_factor', 50))
                         ).fit_predict(data)
        if name == 'Gaussian Mixture':
            return GaussianMixture(
                n_components=k, random_state=42,
                covariance_type=params.get('covariance_type', 'full')
            ).fit_predict(data)
        if name == 'DBSCAN':
            return DBSCAN(eps=float(params.get('eps', 0.5)),
                          min_samples=int(params.get('min_samples', 5)),
                          metric=params.get('metric', 'euclidean')).fit_predict(data)
        if name == 'HDBSCAN':
            if not _HDBSCAN_OK or _HDBSCAN_CLS is None:
                return None
            return _HDBSCAN_CLS(min_cluster_size=int(params.get('min_cluster_size', 5)),
                                min_samples=int(params.get('min_samples', 5)),
                                metric=params.get('metric', 'euclidean')
                                ).fit_predict(data)
        if name == 'OPTICS':
            return OPTICS(min_samples=int(params.get('min_samples', 5)),
                          metric=params.get('metric', 'euclidean'),
                          cluster_method=params.get('cluster_method', 'xi')
                          ).fit_predict(data)
        if name == 'Mean Shift':
            bw = float(params.get('bandwidth', 0.0))
            kw = {'min_bin_freq': int(params.get('min_bin_freq', 1))}
            if bw > 0:
                kw['bandwidth'] = bw
            return MeanShift(**kw).fit_predict(data)
        if name == 'SOM' and som_runner is not None:
            som_keys = ALGO_PARAM_SPECS['SOM'].get('som_param_keys', ())
            som_params = {key: params[key] for key in som_keys if key in params}
            try:
                return som_runner(k, data, som_params)
            except TypeError:
                return som_runner(k, data)
    except Exception:
        return None
    return None


def make_host_som_runner(host_dialog):
    """Build a SOM runner that does not disturb the host's SOM tab state.

    The host's :meth:`_run_som` has a deliberate side effect: it stashes the
    trained map on ``host_dialog._som_obj`` and the per-neuron labels on
    ``host_dialog._som_neuron_labels`` so the SOM tab can redraw the U-matrix,
    hit-count and cluster grid without retraining. The host's own evaluation
    sweep (``_evaluate_data``) backs those two attributes up before it runs and
    restores them afterwards, precisely so a sweep does not overwrite the SOM
    produced by the user's actual ② Cluster run.

    A custom sweep fits a SOM for every cluster count and preprocessing combo,
    and the detail panel re-fits on row selection, so without the same guard the
    host's SOM tab would end up showing whichever arbitrary grid cell was fitted
    last. This wrapper reproduces the host's save/restore around every call, so
    the sweep can use the identical SOM implementation while leaving the host's
    displayed SOM untouched.

    The per-fit SOM hyperparameters (``som_rows``, ``som_cols``, ``som_sigma``,
    ``som_lr``, ``som_n_iter``, ``som_final_algo``) are overlaid onto a shallow
    copy of the host configuration for the duration of each call, so the sweep
    can vary the whole map geometry without mutating ``node.config``. Keys the
    sweep does not specify fall back to the host's current configuration values.

    Args:
        host_dialog (QDialog): The owning clustering dialog exposing
            ``_run_som`` and ``node.config``.

    Returns:
        callable or None: ``f(k, data, som_params=None) -> labels`` mirroring the
            host's SOM, or ``None`` if the host cannot run a SOM.
    """
    if host_dialog is None or not hasattr(host_dialog, '_run_som'):
        return None

    def _runner(k, data, som_params=None):
        """Fit the host SOM for ``k`` clusters with optional per-fit params.

        Args:
            k (int): Final cluster count.
            data (np.ndarray): Preprocessed matrix to train the map on.
            som_params (dict or None): Optional overrides for the map
                hyperparameters; missing keys inherit the host configuration.

        Returns:
            np.ndarray or None: Cluster label per row.
        """
        obj_backup = getattr(host_dialog, '_som_obj', None)
        labels_backup = getattr(host_dialog, '_som_neuron_labels', None)
        cfg = dict(host_dialog.node.config)
        if som_params:
            cfg.update(som_params)
        try:
            return host_dialog._run_som(k, data, cfg)
        finally:
            host_dialog._som_obj = obj_backup
            host_dialog._som_neuron_labels = labels_backup

    return _runner


def build_param_grid(name, selections):
    """Expand per-parameter value lists into concrete parameter dicts.

    Numeric parameters carry a list of values to test; categorical parameters
    carry a list of selected options.  The grid is the Cartesian product of all
    those lists.

    Args:
        name (str): Algorithm key.
        selections (dict): ``{param_name: [values...]}``; missing parameters use
            their spec default list.

    Returns:
        list[dict]: One parameter dict per combination.
    """
    spec = ALGO_PARAM_SPECS[name]['params']
    keys, value_lists = [], []
    for pname, pspec in spec.items():
        vals = selections.get(pname)
        if not vals:
            vals = pspec['default']
        keys.append(pname)
        value_lists.append(list(vals))
    return [dict(zip(keys, combo)) for combo in itertools.product(*value_lists)]


def count_combinations(pre_combos, algo_selections):
    """Return the total number of fits a sweep would perform.

    Args:
        pre_combos (list): Preprocessing ``(data_type, scaling, reduction)`` tuples.
        algo_selections (dict): ``{algo: {param: [values]}}``.

    Returns:
        int: Total fit count for the pre-run estimate.
    """
    total = 0
    for name, sel in algo_selections.items():
        total += len(pre_combos) * len(build_param_grid(name, sel))
    return total


def _params_str(algo, params):
    """Return a compact human-readable parameter string for a result row."""
    order = list(ALGO_PARAM_SPECS[algo]['params'].keys())
    return ', '.join(f"{k}={params[k]}" for k in order if k in params)


def run_sweep(particle_data, elements, components, *,
              data_types, scalings, dim_reductions,
              algo_selections, internal_metrics, external_metrics,
              n_components=2, other_flags=None, filter_zeros=True,
              min_clusters=2, max_clusters=30,
              som_runner=None, progress_cb=None, cancel_event=None):
    """Run the full pipeline grid and score every result against ground truth.

    Args:
        particle_data (list[dict]): Particle records.
        elements (list[str]): Active element columns.
        components (list[tuple]): Parsed component definitions.
        data_types / scalings / dim_reductions (list[str]): Axis selections.
        algo_selections (dict): ``{algo: {param: [values]}}``.
        internal_metrics (list[str]): Internal index names to compute.
        external_metrics (list[str]): External (truth) index names to compute.
        n_components (int): PCA / t-SNE target dimensionality.
        other_flags (np.ndarray or None): Optional coincidence/outlier mask over
            the original particle rows.
        filter_zeros (bool): Drop all-zero rows.
        min_clusters / max_clusters (int): Accept only partitions whose cluster
            count falls in this inclusive range.
        som_runner (callable or None): Optional SOM hook.
        progress_cb (callable or None): ``f(done, total, message)``.
        cancel_event (threading.Event or None): Set to abort early.

    Returns:
        dict: ``{'results', 'truth', 'completed', 'total', 'cancelled'}`` and an
            optional ``'error'`` string.
    """
    pre = Preprocessor(particle_data, elements, filter_zeros=filter_zeros,
                       n_components=n_components)
    if pre.n_rows < 2:
        return {'results': [], 'truth': {}, 'completed': 0, 'total': 0,
                'cancelled': False, 'error': 'Insufficient data after filtering.'}

    kept_other = None
    if other_flags is not None:
        of = np.asarray(other_flags, dtype=bool)
        if len(of) == len(pre.keep_mask):
            kept_other = of[pre.keep_mask]
    truth = build_ground_truth(pre.counts_matrix(), elements, components,
                               other_flags=kept_other)
    truth_labels = truth['labels']

    pre_combos = [(dt, sc, dr)
                  for dt in data_types for sc in scalings for dr in dim_reductions]
    total = count_combinations(pre_combos, algo_selections)
    done = 0
    results = []
    cancelled = False

    for (dt, sc, dr) in pre_combos:
        if cancel_event is not None and cancel_event.is_set():
            cancelled = True
            break
        try:
            data = pre.matrix(dt, sc, dr)
        except Exception:
            done += sum(len(build_param_grid(a, s))
                        for a, s in algo_selections.items())
            if progress_cb:
                progress_cb(done, total, f"{dt} / {sc} / {dr}: skipped")
            continue

        for algo, sel in algo_selections.items():
            for params in build_param_grid(algo, sel):
                if cancel_event is not None and cancel_event.is_set():
                    cancelled = True
                    break
                t0 = time.perf_counter()
                labels = run_algorithm(algo, params, data, som_runner=som_runner)
                elapsed = time.perf_counter() - t0
                done += 1
                if progress_cb and (done % 5 == 0 or done == total):
                    progress_cb(done, total, f"{algo} · {dt}/{sc}/{dr}")
                if labels is None:
                    continue
                labels = np.asarray(labels)
                valid = labels[labels >= 0]
                n_clusters = int(len(np.unique(valid)))
                n_noise = int(np.sum(labels < 0))
                if n_clusters < min_clusters or n_clusters > max_clusters:
                    continue

                row = {
                    'algorithm': algo,
                    'data_type': dt,
                    'scaling': sc,
                    'dim_reduction': dr,
                    'params': dict(params),
                    'params_str': _params_str(algo, params),
                    'n_clusters': n_clusters,
                    'n_noise': n_noise,
                    'runtime_s': round(elapsed, 4),
                }
                for m in external_metrics:
                    try:
                        row[m] = EXTERNAL_METRICS[m]['func'](truth_labels, labels)
                    except Exception:
                        row[m] = float('nan')
                for m in internal_metrics:
                    spec = METRIC_REGISTRY.get(m)
                    if not spec:
                        row[m] = float('nan')
                        continue
                    try:
                        mask = labels >= 0
                        if len(np.unique(labels[mask])) < 2:
                            row[m] = float('nan')
                        else:
                            row[m] = CVI_FUNCS[spec['key']](data[mask], labels[mask])
                    except Exception:
                        row[m] = float('nan')
                results.append(row)
            if cancelled:
                break
        if cancelled:
            break

    return {'results': results, 'truth': truth, 'completed': done,
            'total': total, 'cancelled': cancelled}


def rank_results(results, metric=PRIMARY_EXTERNAL_METRIC):
    """Return results sorted best-first by ``metric`` (NaNs last).

    Args:
        results (list[dict]): Result rows from :func:`run_sweep`.
        metric (str): Metric name to rank by.

    Returns:
        list[dict]: A new list sorted best-first.
    """
    spec = EXTERNAL_METRICS.get(metric) or METRIC_REGISTRY.get(metric)
    reverse = (spec.get('direction', 'max') == 'max') if spec else True

    def key(r):
        """Sort key placing NaNs last and ordering by the metric direction."""
        v = r.get(metric, float('nan'))
        if v != v:
            return (1, 0.0)
        return (0, -v if reverse else v)

    return sorted(results, key=key)


def _spearman(a, b):
    """Return the Spearman rank correlation between two equal-length sequences."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3:
        return float('nan')
    ar = np.argsort(np.argsort(a[ok])).astype(float)
    br = np.argsort(np.argsort(b[ok])).astype(float)
    ar -= ar.mean()
    br -= br.mean()
    denom = np.sqrt((ar ** 2).sum() * (br ** 2).sum())
    if denom == 0:
        return float('nan')
    return float((ar * br).sum() / denom)


def analyze_metric_trust(results, internal_metrics,
                         reference=PRIMARY_EXTERNAL_METRIC):
    """Report how well each internal index tracks the ground-truth reference.

    For each internal metric this returns the external reference score of the
    configuration that metric ranks best, and the Spearman correlation between
    that metric and the reference across the whole grid.

    Args:
        results (list[dict]): Result rows from :func:`run_sweep`.
        internal_metrics (list[str]): Internal index names present in results.
        reference (str): External metric to validate against.

    Returns:
        list[dict]: One entry per internal metric, most trustworthy first.
    """
    out = []
    ref_vals = [r.get(reference, float('nan')) for r in results]
    for m in internal_metrics:
        spec = METRIC_REGISTRY.get(m, {})
        direction = spec.get('direction', 'max')
        vals = [r.get(m, float('nan')) for r in results]
        finite = [(i, v) for i, v in enumerate(vals) if v == v]
        if not finite:
            out.append({'metric': m, 'top_pick_ref': float('nan'),
                        'spearman': float('nan'), 'top_config': None})
            continue
        best_i = (max(finite, key=lambda iv: iv[1]) if direction == 'max'
                  else min(finite, key=lambda iv: iv[1]))[0]
        out.append({
            'metric': m,
            'top_pick_ref': ref_vals[best_i],
            'spearman': _spearman(vals, ref_vals),
            'top_config': results[best_i],
        })
    out.sort(key=lambda d: (d['top_pick_ref'] != d['top_pick_ref'],
                            -(d['top_pick_ref'] if d['top_pick_ref'] == d['top_pick_ref'] else 0)))
    return out


def per_cluster_silhouette(data, labels):
    """Return the mean silhouette width of each individual cluster.

    The silhouette width is defined per sample, so it decomposes naturally into
    a per-cluster mean: the average silhouette of the points assigned to one
    cluster measures how tight and well-separated that single cluster is, which
    is more diagnostic than the single global mean when one cluster is clean and
    another is smeared. Noise points (negative labels) are excluded, matching
    how the internal indices treat them elsewhere in this module.

    Reference:
        P. J. Rousseeuw, "Silhouettes: a graphical aid to the interpretation and
        validation of cluster analysis," *J. Comput. Appl. Math.* 20, 1987,
        53-65, doi:10.1016/0377-0427(87)90125-7.

    Args:
        data (np.ndarray): Preprocessed matrix the labels were produced on.
        labels (np.ndarray): Integer cluster label per row; negatives are noise.

    Returns:
        dict[int, float]: ``{cluster_id: mean_silhouette}``; empty when fewer
            than two non-noise clusters exist (silhouette is then undefined).
    """
    from sklearn.metrics import silhouette_samples

    labels = np.asarray(labels)
    mask = labels >= 0
    if mask.sum() < 2 or len(np.unique(labels[mask])) < 2:
        return {}
    try:
        sample_sil = silhouette_samples(data[mask], labels[mask])
    except Exception:
        return {}
    out = {}
    masked_labels = labels[mask]
    for c in np.unique(masked_labels):
        out[int(c)] = float(np.mean(sample_sil[masked_labels == c]))
    return out


try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
        QCheckBox, QGroupBox, QScrollArea, QWidget, QTableWidget,
        QTableWidgetItem, QProgressBar, QLineEdit, QSpinBox, QDoubleSpinBox,
        QComboBox, QTabWidget, QMessageBox, QFileDialog, QAbstractItemView,
    )
    from PySide6.QtCore import Qt, Signal, QThread
    from PySide6.QtGui import QColor, QFont
    _QT_OK = True
except Exception:
    _QT_OK = False


if _QT_OK:

    _BEST_ROW_COLOR = QColor("#57CB3A")

    class _RangeBuilder(QWidget):
        """A from / to / step selector for one numeric sweep parameter.

        The sweep tests every value the range produces; the values themselves
        are not displayed, only the bounds and the step (default derived from
        the parameter — 1 for integer cluster counts).
        """

        def __init__(self, spec, parent=None):
            """Build from/to/step spin boxes for a numeric parameter spec.

            Args:
                spec (dict): A numeric parameter spec from :data:`ALGO_PARAM_SPECS`.
                parent (QWidget or None): Optional parent.
            """
            super().__init__(parent)
            self._is_float = (spec['kind'] == 'float_range')
            self._min = spec.get('min', 0)
            self._max = spec.get('max', 10_000)
            lay = QHBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            mk = QDoubleSpinBox if self._is_float else QSpinBox
            self.f_from = mk()
            self.f_to = mk()
            self.f_step = mk()
            for sb in (self.f_from, self.f_to):
                sb.setMinimum(self._min if self._is_float else int(self._min))
                sb.setMaximum(self._max if self._is_float else int(self._max))
                if self._is_float:
                    sb.setDecimals(3)
                    sb.setSingleStep(0.1)
                sb.setFixedWidth(72)
            if self._is_float:
                self.f_step.setRange(0.001, max(1.0, float(self._max)))
                self.f_step.setDecimals(3)
            else:
                self.f_step.setRange(1, max(1, int(self._max)))
            self.f_step.setFixedWidth(72)
            defaults = sorted(spec.get('default', [0]))
            self.f_from.setValue(defaults[0])
            self.f_to.setValue(defaults[-1])
            self.f_step.setValue(self._default_step(defaults))
            lay.addWidget(QLabel("from"))
            lay.addWidget(self.f_from)
            lay.addWidget(QLabel("to"))
            lay.addWidget(self.f_to)
            lay.addWidget(QLabel("step"))
            lay.addWidget(self.f_step)
            lay.addStretch()

        def _default_step(self, sorted_defaults):
            """Return a sensible step: the smallest gap in the defaults, else 1/0.1."""
            if len(sorted_defaults) >= 2:
                gaps = [b - a for a, b in zip(sorted_defaults, sorted_defaults[1:]) if b > a]
                if gaps:
                    g = min(gaps)
                    return round(g, 6) if self._is_float else max(1, int(round(g)))
            return 0.1 if self._is_float else 1

        def values(self):
            """Return every value the current range produces."""
            a, b, s = self.f_from.value(), self.f_to.value(), self.f_step.value()
            if s <= 0 or b < a:
                return [round(a, 6) if self._is_float else int(a)]
            out, x, guard = [], a, 0
            while x <= b + 1e-9 and guard < 100000:
                out.append(round(x, 6) if self._is_float else int(round(x)))
                x += s
                guard += 1
            return out

        def set_values(self, vals):
            """Restore from/to/step to span the given list of values."""
            vals = sorted(set(vals))
            if not vals:
                return
            self.f_from.setValue(vals[0])
            self.f_to.setValue(vals[-1])
            self.f_step.setValue(self._default_step(vals))

    class _ChoiceList(QWidget):
        """A horizontal checkbox group for categorical parameter options."""

        def __init__(self, options, defaults, parent=None):
            """Build a checkbox per option.

            Args:
                options (list[str]): All selectable options.
                defaults (list[str]): Options checked initially.
                parent (QWidget or None): Optional parent.
            """
            super().__init__(parent)
            lay = QHBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            self.boxes = {}
            for opt in options:
                cb = QCheckBox(opt)
                cb.setChecked(opt in defaults)
                self.boxes[opt] = cb
                lay.addWidget(cb)
            lay.addStretch()

        def values(self):
            """Return the list of checked options."""
            return [o for o, cb in self.boxes.items() if cb.isChecked()]

        def set_values(self, vals):
            """Check exactly the options present in ``vals``."""
            for o, cb in self.boxes.items():
                cb.setChecked(o in vals)

    class _AlgoCard(QGroupBox):
        """One algorithm's enable checkbox plus its parameter controls."""

        def __init__(self, name, parent=None):
            """Build the card for algorithm ``name``.

            Args:
                name (str): Algorithm key from :data:`ALGO_PARAM_SPECS`.
                parent (QWidget or None): Optional parent.
            """
            super().__init__(name, parent)
            self.name = name
            self.setCheckable(True)
            self.setChecked(name in DEFAULT_ALGORITHMS)
            form = QGridLayout(self)
            form.setContentsMargins(8, 4, 8, 8)
            self.controls = {}
            r = 0
            for pname, pspec in ALGO_PARAM_SPECS[name]['params'].items():
                form.addWidget(QLabel(pspec['label'] + ':'), r, 0,
                               alignment=Qt.AlignTop)
                if pspec['kind'] in ('int_range', 'float_range'):
                    w = _RangeBuilder(pspec)
                else:
                    w = _ChoiceList(pspec['options'], pspec['default'])
                self.controls[pname] = w
                form.addWidget(w, r, 1)
                r += 1

        def selections(self):
            """Return ``{param: [values]}`` for this algorithm."""
            return {p: w.values() for p, w in self.controls.items()}

        def get_state(self):
            """Return a serialisable ``{'enabled', 'params'}`` snapshot."""
            return {'enabled': self.isChecked(), 'params': self.selections()}

        def set_state(self, state):
            """Restore enabled state and parameter values from a snapshot."""
            self.setChecked(bool(state.get('enabled', self.isChecked())))
            for p, vals in state.get('params', {}).items():
                if p in self.controls and vals:
                    self.controls[p].set_values(vals)

    class _SweepWorker(QThread):
        """Runs :func:`run_sweep` off the GUI thread."""

        progressed = Signal(int, int, str)
        done = Signal(object)
        failed = Signal(str)

        def __init__(self, kwargs, parent=None):
            """Store the sweep keyword arguments and a cancel flag.

            Args:
                kwargs (dict): Arguments forwarded to :func:`run_sweep`.
                parent (QObject or None): Optional parent.
            """
            super().__init__(parent)
            self._kwargs = kwargs
            self.cancel_event = threading.Event()

        def run(self):
            """Execute the sweep and emit progress, result or failure."""
            try:
                def cb(done, total, msg):
                    """Forward engine progress to the GUI thread."""
                    self.progressed.emit(done, total, msg)
                res = run_sweep(progress_cb=cb, cancel_event=self.cancel_event,
                                **self._kwargs)
                self.done.emit(res)
            except Exception as exc:
                self.failed.emit(str(exc))

    class CustomClusterTestDialog(QDialog):
        """Configure, run, and review a custom pipeline sweep against truth.

        Setup and results are persisted on the node between openings, so closing
        and reopening the dialog keeps the data until the user clears it.
        """

        def __init__(self, host_dialog=None, particle_data=None, elements=None,
                     node=None, som_runner=None, parent=None):
            """Build the dialog and restore any saved state from the node.

            Args:
                host_dialog (QDialog or None): The owning clustering dialog.
                particle_data (list or None): Explicit particle records.
                elements (list or None): Explicit element columns.
                node (object or None): The clustering node used for persistence.
                som_runner (callable or None): Optional SOM hook.
                parent (QWidget or None): Optional parent.
            """
            super().__init__(parent or host_dialog)
            self.host = host_dialog
            self.node = node or (host_dialog.node if host_dialog else None)
            self._particle_data = particle_data
            self._elements = elements
            self._som_runner = som_runner
            self._worker = None
            self._last = None
            self._last_ncomp = 2
            self._ranked = []
            self._detail_pre = None

            self.setWindowTitle("Everything everywhere all at once: custom cluster test")
            self.setMinimumSize(1000, 680)
            self.resize(1400, 900)
            self._build_ui()
            self._restore_state()

        def _get_particle_data(self):
            """Return particle records, resolving from the node if needed."""
            if self._particle_data is not None:
                return self._particle_data
            if self.node and getattr(self.node, 'input_data', None):
                return self.node.input_data.get('particle_data', [])
            return []

        def _get_elements(self):
            """Return element columns, resolving from the host or data."""
            if self._elements:
                return list(self._elements)
            if self.host is not None:
                for attr in ('_elements_filtered', '_elements_cache'):
                    val = getattr(self.host, attr, None)
                    if val:
                        return list(val)
            elems = set()
            for p in self._get_particle_data():
                d = p.get('elements', {})
                if isinstance(d, dict):
                    elems.update(d.keys())
            return sorted(elems)

        def _available_algorithms(self):
            """Return the algorithm keys whose cards should be shown.

            Every algorithm in :data:`ALGORITHMS` is offered except those flagged
            ``needs_som`` (currently ``SOM``) when no ``som_runner`` was supplied,
            since SOM cannot be fitted without the host's training routine and
            would otherwise appear as a card that always fails.

            Returns:
                list[str]: Algorithm keys to build cards for.
            """
            have_som = self._som_runner is not None
            return [n for n in ALGORITHMS
                    if have_som or not ALGO_PARAM_SPECS[n].get('needs_som')]

        def _build_ui(self):
            """Assemble the setup and results tabs."""
            root = QVBoxLayout(self)
            self.tabs = QTabWidget()
            self.tabs.addTab(self._build_setup_tab(), "① Setup")
            self.tabs.addTab(self._build_results_tab(), "② Results")
            root.addWidget(self.tabs)

        def _build_setup_tab(self):
            """Build the scrollable setup tab with pinned run controls."""
            tab = QWidget()
            outer = QVBoxLayout(tab)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            body = QWidget()
            v = QVBoxLayout(body)
            v.setSpacing(12)
            v.setContentsMargins(6, 6, 6, 6)

            gt = QGroupBox("Known components (ground truth)")
            gtl = QVBoxLayout(gt)
            gtl.addWidget(QLabel(
                "Enter the components you prepared, separated by ';'. "
                "Group alloys/molecules with '+' or fused symbols, e.g. "
                "<b>107Ag ; 48Ti ; 140Ce ; 56Fe+60Ni+59Co</b>"))
            self.components_edit = QLineEdit("107Ag ; 48Ti ; 140Ce ; 56Fe+60Ni+59Co")
            gtl.addWidget(self.components_edit)
            self.unknown_mode = QCheckBox(
                "Unknown components — rank by internal metrics only "
                "(no ground truth)")
            self.unknown_mode.toggled.connect(self._on_mode_changed)
            gtl.addWidget(self.unknown_mode)
            v.addWidget(gt)

            axes = QHBoxLayout()
            axes.setSpacing(10)
            axes.addWidget(self._axis_box("Data type", DATA_TYPES,
                                          DEFAULT_DATA_TYPES, 'data_boxes'))
            axes.addWidget(self._axis_box("Scaling", SCALINGS,
                                          DEFAULT_SCALINGS, 'scale_boxes'))
            dr_box = self._axis_box("Dim. reduction", DIM_REDUCTIONS,
                                    DEFAULT_DIM_REDUCTIONS, 'dr_boxes')
            ncrow = QHBoxLayout()
            ncrow.addWidget(QLabel("n_components:"))
            self.ncomp = QSpinBox()
            self.ncomp.setRange(2, 3)
            self.ncomp.setValue(2)
            ncrow.addWidget(self.ncomp)
            ncrow.addStretch()
            dr_box.layout().addLayout(ncrow)
            self.kfilter_cb = QCheckBox("Filter by cluster count")
            self.kfilter_cb.setToolTip(
                "Off (default): every algorithm keeps whatever number of "
                "clusters it finds — HDBSCAN may return hundreds and that is "
                "accepted. On: keep only results whose cluster count is within "
                "the range below.")
            self.kfilter_cb.toggled.connect(self._on_kfilter_toggled)
            dr_box.layout().addWidget(self.kfilter_cb)
            krow = QHBoxLayout()
            krow.addWidget(QLabel("from"))
            self.min_k = QSpinBox()
            self.min_k.setRange(2, 100)
            self.min_k.setValue(2)
            self.max_k = QSpinBox()
            self.max_k.setRange(2, 100000)
            self.max_k.setValue(30)
            krow.addWidget(self.min_k)
            krow.addWidget(QLabel("to"))
            krow.addWidget(self.max_k)
            krow.addStretch()
            dr_box.layout().addLayout(krow)
            self._on_kfilter_toggled(False)
            axes.addWidget(dr_box)
            axes.addWidget(self._axis_box(
                "External metrics (vs truth)", list(EXTERNAL_METRICS.keys()),
                DEFAULT_EXTERNAL_METRICS, 'ext_boxes'))
            axes.addWidget(self._axis_box(
                "Internal metrics", list(METRIC_REGISTRY.keys()),
                list(METRIC_REGISTRY.keys())[:3], 'int_boxes'))
            v.addLayout(axes)

            algo_group = QGroupBox("Algorithms & parameters "
                                   "(tick to include; ranges build the sweep)")
            grid = QGridLayout(algo_group)
            grid.setSpacing(10)
            self.algo_cards = {}
            available = self._available_algorithms()
            for i, name in enumerate(available):
                card = _AlgoCard(name)
                self.algo_cards[name] = card
                grid.addWidget(card, i // 2, i % 2)
            v.addWidget(algo_group)
            v.addStretch()

            scroll.setWidget(body)
            outer.addWidget(scroll, 1)

            ctl = QHBoxLayout()
            self.estimate_lbl = QLabel("")
            est_btn = QPushButton("Estimate size")
            est_btn.clicked.connect(self._update_estimate)
            self.run_btn = QPushButton("▶ Run sweep")
            self.run_btn.clicked.connect(self._run)
            self.cancel_btn = QPushButton("Cancel")
            self.cancel_btn.setEnabled(False)
            self.cancel_btn.clicked.connect(self._cancel)
            ctl.addWidget(est_btn)
            ctl.addWidget(self.estimate_lbl, 1)
            ctl.addWidget(self.cancel_btn)
            ctl.addWidget(self.run_btn)
            outer.addLayout(ctl)

            self.progress = QProgressBar()
            self.progress.setVisible(False)
            outer.addWidget(self.progress)
            return tab

        def _axis_box(self, title, options, defaults, attr):
            """Build a titled checkbox column and store its boxes on ``attr``."""
            box = QGroupBox(title)
            lay = QVBoxLayout(box)
            boxes = {}
            for opt in options:
                cb = QCheckBox(opt)
                cb.setChecked(opt in defaults)
                boxes[opt] = cb
                lay.addWidget(cb)
            lay.addStretch()
            setattr(self, attr, boxes)
            return box

        def _build_results_tab(self):
            """Build the results tab: leaderboard, detail panel and trust table."""
            tab = QWidget()
            v = QVBoxLayout(tab)
            top = QHBoxLayout()
            self.best_lbl = QLabel("Run a sweep to see results.")
            self.best_lbl.setWordWrap(True)
            top.addWidget(self.best_lbl, 1)
            top.addWidget(QLabel("Rank by:"))
            self.rank_combo = QComboBox()
            self.rank_combo.currentTextChanged.connect(self._repopulate_table)
            top.addWidget(self.rank_combo)
            self.run_cluster_cb = QCheckBox("Cluster now")
            self.run_cluster_cb.setChecked(True)
            self.run_boot_cb = QCheckBox("Bootstrap")
            self.run_boot_cb.setToolTip(
                "After applying, run the main K-stability bootstrap on this "
                "pipeline (prepares the data matrix first).")
            self.apply_btn = QPushButton("Apply selected")
            self.apply_btn.setEnabled(False)
            self.apply_btn.clicked.connect(self._apply_selected)
            self.export_btn = QPushButton("Export CSV")
            self.export_btn.setEnabled(False)
            self.export_btn.clicked.connect(self._export_csv)
            self.clear_btn = QPushButton("Delete data")
            self.clear_btn.clicked.connect(self._clear_data)
            top.addWidget(self.run_cluster_cb)
            top.addWidget(self.run_boot_cb)
            top.addWidget(self.apply_btn)
            top.addWidget(self.export_btn)
            top.addWidget(self.clear_btn)
            v.addLayout(top)
            self._refresh_rank_combo()

            self.table = QTableWidget()
            self.table.setSortingEnabled(True)
            self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.table.setSelectionMode(QAbstractItemView.SingleSelection)
            self.table.itemSelectionChanged.connect(self._on_row_selected)
            v.addWidget(self.table, 3)

            v.addWidget(QLabel("<b>Selected pipeline — cluster vs truth "
                               "breakdown</b> (click a row above)"))
            self.detail_table = QTableWidget()
            v.addWidget(self.detail_table, 2)

            v.addWidget(QLabel("<b>Which metric can you trust?</b> "
                               "(internal index vs the ranking metric across the grid)"))
            self.trust_table = QTableWidget()
            v.addWidget(self.trust_table, 1)
            return tab

        def _refresh_rank_combo(self):
            """Populate the ranking dropdown with the metrics valid for the mode."""
            current = self.rank_combo.currentText()
            if self.unknown_mode.isChecked():
                items = [o for o, cb in self.int_boxes.items() if cb.isChecked()]
                if not items:
                    items = list(METRIC_REGISTRY.keys())
            else:
                items = list(EXTERNAL_METRICS.keys())
            self.rank_combo.blockSignals(True)
            self.rank_combo.clear()
            self.rank_combo.addItems(items)
            if current in items:
                self.rank_combo.setCurrentText(current)
            self.rank_combo.blockSignals(False)

        def _on_mode_changed(self, checked):
            """Enable/disable truth-only controls when the mode toggles."""
            self.components_edit.setEnabled(not checked)
            for cb in self.ext_boxes.values():
                cb.setEnabled(not checked)
            self._refresh_rank_combo()

        def _on_kfilter_toggled(self, checked):
            """Enable the cluster-count bounds only when filtering is on."""
            self.min_k.setEnabled(checked)
            self.max_k.setEnabled(checked)

        def _gather_kwargs(self):
            """Collect the current setup into :func:`run_sweep` keyword args."""
            unknown = self.unknown_mode.isChecked()
            algo_selections = {}
            for name, card in self.algo_cards.items():
                if card.isChecked():
                    algo_selections[name] = card.selections()
            components = [] if unknown else parse_components(self.components_edit.text())
            external = ([] if unknown
                        else [o for o, cb in self.ext_boxes.items() if cb.isChecked()])
            if self.kfilter_cb.isChecked():
                min_c, max_c = self.min_k.value(), self.max_k.value()
            else:
                min_c, max_c = 1, 10 ** 9
            return dict(
                particle_data=self._get_particle_data(),
                elements=self._get_elements(),
                components=components,
                data_types=[o for o, cb in self.data_boxes.items() if cb.isChecked()],
                scalings=[o for o, cb in self.scale_boxes.items() if cb.isChecked()],
                dim_reductions=[o for o, cb in self.dr_boxes.items() if cb.isChecked()],
                algo_selections=algo_selections,
                internal_metrics=[o for o, cb in self.int_boxes.items() if cb.isChecked()],
                external_metrics=external,
                n_components=self.ncomp.value(),
                min_clusters=min_c,
                max_clusters=max_c,
                som_runner=self._som_runner,
            )

        def _update_estimate(self):
            """Show the estimated number of fits for the current setup."""
            kw = self._gather_kwargs()
            if not kw['algo_selections']:
                self.estimate_lbl.setText("Select at least one algorithm.")
                return 0
            pre = [(d, s, r) for d in kw['data_types']
                   for s in kw['scalings'] for r in kw['dim_reductions']]
            n = count_combinations(pre, kw['algo_selections'])
            self.estimate_lbl.setText(
                f"≈ {n:,} fits across {len(pre)} preprocessing combo(s).")
            return n

        def _run(self):
            """Validate the setup and start the sweep worker."""
            kw = self._gather_kwargs()
            if not kw['data_types'] or not kw['scalings'] or not kw['dim_reductions']:
                QMessageBox.warning(self, "Setup",
                                    "Pick at least one option on each axis.")
                return
            if not kw['algo_selections']:
                QMessageBox.warning(self, "Setup", "Select at least one algorithm.")
                return
            if self.unknown_mode.isChecked():
                if not kw['internal_metrics']:
                    QMessageBox.warning(self, "Setup",
                                        "Unknown mode needs at least one internal metric.")
                    return
            elif not kw['external_metrics']:
                QMessageBox.warning(self, "Setup",
                                    "Select at least one external metric.")
                return
            n = self._update_estimate()
            if n > 20000:
                ok = QMessageBox.question(
                    self, "Large sweep",
                    f"This will run about {n:,} fits and may take a while.\n"
                    "Proceed?")
                if ok != QMessageBox.Yes:
                    return
            self._last_ncomp = kw['n_components']
            self.run_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)
            self.progress.setVisible(True)
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self._worker = _SweepWorker(kw)
            self._worker.progressed.connect(self._on_progress)
            self._worker.done.connect(self._on_done)
            self._worker.failed.connect(self._on_failed)
            self._worker.start()

        def _cancel(self):
            """Request cancellation of the running sweep."""
            if self._worker is not None:
                self._worker.cancel_event.set()
                self.cancel_btn.setEnabled(False)

        def _on_progress(self, done, total, msg):
            """Update the progress bar from worker progress signals."""
            pct = int(100 * done / total) if total else 0
            self.progress.setValue(pct)
            self.progress.setFormat(f"{done}/{total} — {msg}")

        def _on_failed(self, msg):
            """Restore controls and report a sweep failure."""
            self.run_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress.setVisible(False)
            QMessageBox.critical(self, "Sweep failed", msg)

        def _on_done(self, payload):
            """Store and display results once the sweep finishes."""
            self.run_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress.setVisible(False)
            self._detail_pre = None
            if payload.get('error'):
                QMessageBox.warning(self, "No results", payload['error'])
                return
            self._last = payload
            self._last['unknown'] = self.unknown_mode.isChecked()
            self._show_results(payload)
            self._save_state()
            self.tabs.setCurrentIndex(1)

        def _show_results(self, payload):
            """Render the best-line summary, table and trust panel."""
            truth = payload.get('truth', {})
            counts = truth.get('counts', {})
            tsummary = ', '.join(f"{k}: {v}" for k, v in counts.items())
            results = payload.get('results', [])
            if not results:
                self.best_lbl.setText(
                    f"No partition fell within the cluster-count window. "
                    f"Truth groups — {tsummary}")
                return
            metric = self.rank_combo.currentText()
            best = rank_results(results, metric)[0]
            if payload.get('unknown'):
                self.best_lbl.setText(
                    f"<b>Best pipeline ({metric} = {best.get(metric, float('nan')):.3f}):</b> "
                    f"{best['data_type']} · {best['scaling']} · {best['dim_reduction']} · "
                    f"{best['algorithm']} ({best['params_str']}) → "
                    f"{best['n_clusters']} clusters, {best['n_noise']} noise."
                    f"<br><span style='color:#64748B'>No ground truth — ranked by "
                    f"internal metric only "
                    f"({payload.get('completed')}/{payload.get('total')} fits)</span>")
            else:
                n_truth = max(len(counts) - 1, 0)
                self.best_lbl.setText(
                    f"<b>Best pipeline ({metric} = {best.get(metric, float('nan')):.3f}):</b> "
                    f"{best['data_type']} · {best['scaling']} · {best['dim_reduction']} · "
                    f"{best['algorithm']} ({best['params_str']}) → "
                    f"{best['n_clusters']} clusters, {best['n_noise']} noise "
                    f"(you named {n_truth} components)."
                    f"<br><span style='color:#64748B'>Truth groups — {tsummary} "
                    f"({'cancelled, partial' if payload.get('cancelled') else 'complete'}; "
                    f"{payload.get('completed')}/{payload.get('total')} fits)</span>")
            self.apply_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            self._repopulate_table()
            self._populate_trust()

        def _repopulate_table(self):
            """Fill the leaderboard, ranked by the chosen metric, best row lit."""
            if not self._last or not self._last.get('results'):
                return
            metric = self.rank_combo.currentText()
            self._ranked = rank_results(self._last['results'], metric)
            ext = [o for o, cb in self.ext_boxes.items() if cb.isChecked()]
            intl = [o for o, cb in self.int_boxes.items() if cb.isChecked()]
            cols = (['#', 'Algorithm', 'Data type', 'Scaling', 'Reduction',
                     'Params', 'K', 'Noise'] + ext + intl)
            self.table.setSortingEnabled(False)
            self.table.setColumnCount(len(cols))
            self.table.setHorizontalHeaderLabels(cols)
            self.table.setRowCount(len(self._ranked))
            for r, row in enumerate(self._ranked):
                vals = [str(r + 1), row['algorithm'], row['data_type'],
                        row['scaling'], row['dim_reduction'], row['params_str'],
                        str(row['n_clusters']), str(row['n_noise'])]
                for m in ext + intl:
                    v = row.get(m, float('nan'))
                    vals.append('—' if v != v else f"{v:.3f}")
                for c, val in enumerate(vals):
                    item = QTableWidgetItem(val)
                    if c == 0:
                        item.setData(Qt.UserRole, r)
                    if r == 0:
                        item.setBackground(_BEST_ROW_COLOR)
                        f = item.font()
                        f.setBold(True)
                        item.setFont(f)
                    self.table.setItem(r, c, item)
            self.table.resizeColumnsToContents()
            self.table.setSortingEnabled(True)

        def _populate_trust(self):
            """Fill the metric-trust table for the enabled internal metrics."""
            if self._last.get('unknown'):
                self.trust_table.setRowCount(0)
                return
            intl = [o for o, cb in self.int_boxes.items() if cb.isChecked()]
            ref = self.rank_combo.currentText()
            trust = analyze_metric_trust(self._last['results'], intl, reference=ref)
            self.trust_table.setColumnCount(3)
            self.trust_table.setHorizontalHeaderLabels(
                ['Internal metric', f"{ref} of its top pick", f"Spearman vs {ref}"])
            self.trust_table.setRowCount(len(trust))
            for r, t in enumerate(trust):
                tp, sp = t['top_pick_ref'], t['spearman']
                self.trust_table.setItem(r, 0, QTableWidgetItem(t['metric']))
                self.trust_table.setItem(r, 1, QTableWidgetItem(
                    '—' if tp != tp else f"{tp:.3f}"))
                self.trust_table.setItem(r, 2, QTableWidgetItem(
                    '—' if sp != sp else f"{sp:.3f}"))
            self.trust_table.resizeColumnsToContents()

        def _selected_result(self):
            """Return the result dict for the currently selected table row."""
            r = self.table.currentRow()
            if r < 0:
                return None
            item = self.table.item(r, 0)
            if item is None:
                return None
            idx = item.data(Qt.UserRole)
            if idx is None or idx >= len(self._ranked):
                return None
            return self._ranked[idx]

        def _labels_for_row(self, result):
            """Re-fit one pipeline to obtain its data matrix and cluster labels.

            Returns:
                tuple[np.ndarray or None, np.ndarray or None]: ``(data, labels)``
                    where ``data`` is the preprocessed matrix the labels were
                    produced on (needed for the per-cluster silhouette), or
                    ``(None, None)`` on failure.
            """
            try:
                if self._detail_pre is None:
                    self._detail_pre = Preprocessor(
                        self._get_particle_data(), self._get_elements(),
                        n_components=self._last_ncomp)
                data = self._detail_pre.matrix(
                    result['data_type'], result['scaling'], result['dim_reduction'])
                labels = run_algorithm(result['algorithm'], result['params'], data,
                                       som_runner=self._som_runner)
                return data, labels
            except Exception:
                return None, None

        def _on_row_selected(self):
            """Show the cluster-vs-truth breakdown for the selected pipeline."""
            result = self._selected_result()
            if result is None or not self._last:
                return
            data, labels = self._labels_for_row(result)
            if labels is None:
                self.detail_table.setRowCount(0)
                return
            self._fill_detail_table(result, labels, data)

        def _fill_detail_table(self, result, labels, data=None):
            """Populate the detail table with per-cluster composition and quality.

            Each cluster row carries its size, its per-cluster mean silhouette (a
            tightness/separation read for that single cluster) and, in truth mode,
            its dominant truth group and the per-truth-name member counts. A final
            "missing / noise" row accounts for every particle not placed in a
            named cluster: rows the algorithm tagged as noise plus rows that were
            filtered out before clustering, so the column totals always reconcile
            with the original particle count.

            Args:
                result (dict): The selected result row.
                labels (np.ndarray): Cluster label per kept particle.
                data (np.ndarray or None): The matrix the labels came from, used
                    only for the per-cluster silhouette.
            """
            truth = self._last.get('truth', {})
            names = truth.get('names', [])
            name_to_id = truth.get('name_to_id', {})
            tlabels = truth.get('labels')
            labels = np.asarray(labels)
            sil = per_cluster_silhouette(data, labels) if data is not None else {}
            clusters = sorted(c for c in set(int(x) for x in np.unique(labels)) if c >= 0)
            n_noise = int(np.sum(labels < 0))
            n_original = len(self._get_particle_data())
            n_filtered = max(n_original - len(labels), 0)
            n_missing = n_noise + n_filtered
            unknown = (self._last.get('unknown')
                       or tlabels is None or len(tlabels) != len(labels))

            def _sil_cell(c):
                """Formatted per-cluster silhouette, or em dash when undefined."""
                v = sil.get(c)
                return '—' if v is None else f"{v:.3f}"

            if unknown:
                self.detail_table.setColumnCount(3)
                self.detail_table.setHorizontalHeaderLabels(
                    ['Cluster', 'Size', 'Silhouette'])
                self.detail_table.setRowCount(len(clusters) + 1)
                for r, c in enumerate(clusters):
                    size = int(np.sum(labels == c))
                    self.detail_table.setItem(r, 0, QTableWidgetItem(str(c)))
                    self.detail_table.setItem(r, 1, QTableWidgetItem(str(size)))
                    self.detail_table.setItem(r, 2, QTableWidgetItem(_sil_cell(c)))
                last = len(clusters)
                self.detail_table.setItem(last, 0, QTableWidgetItem('missing / noise'))
                self.detail_table.setItem(last, 1, QTableWidgetItem(str(n_missing)))
                self.detail_table.setItem(last, 2, QTableWidgetItem('—'))
                self.detail_table.resizeColumnsToContents()
                return

            headers = ['Cluster', 'Size', 'Silhouette', 'Dominant truth'] + names
            self.detail_table.setColumnCount(len(headers))
            self.detail_table.setHorizontalHeaderLabels(headers)
            self.detail_table.setRowCount(len(clusters) + 1)
            for r, c in enumerate(clusters):
                mask = labels == c
                size = int(mask.sum())
                counts = [int(np.sum(tlabels[mask] == name_to_id[nm])) for nm in names]
                dom = names[int(np.argmax(counts))] if counts else '—'
                cells = [str(c), str(size), _sil_cell(c), dom] + [str(x) for x in counts]
                for cc, val in enumerate(cells):
                    self.detail_table.setItem(r, cc, QTableWidgetItem(val))
            noise_mask = labels < 0
            noise_counts = ([int(np.sum(tlabels[noise_mask] == name_to_id[nm]))
                             for nm in names] if noise_mask.any() else [0] * len(names))
            last = len(clusters)
            last_cells = (['missing / noise', str(n_missing), '—', '—']
                          + [str(x) for x in noise_counts])
            for cc, val in enumerate(last_cells):
                self.detail_table.setItem(last, cc, QTableWidgetItem(val))
            self.detail_table.resizeColumnsToContents()

        def _apply_config(self, result):
            """Write a result's pipeline into the node's clustering config."""
            if result is None or self.node is None:
                return
            cfg = self.node.config
            cfg['data_type_display'] = result['data_type']
            cfg['scaling'] = {'None': 'Standard'}.get(
                result['scaling'], result['scaling'])
            cfg['dim_reduction'] = result['dim_reduction']
            cfg['n_components'] = self._last_ncomp
            cfg['selected_algorithm'] = result['algorithm']
            cfg['enabled_algorithms'] = [result['algorithm']]
            if 'k' in result['params']:
                cfg['min_clusters'] = cfg['max_clusters'] = int(result['params']['k'])
                cfg['auto_select_k'] = False
            try:
                self.node.configuration_changed.emit()
            except Exception:
                pass

        def _prepare_host_for_cluster(self, result):
            """Set the host's K and enable Cluster/Bootstrap without evaluation.

            This removes the requirement to run K-evaluation first: the chosen K
            is pushed into the host's combo and the trigger buttons are enabled,
            so the host's own Cluster button works directly.

            Args:
                result (dict): The applied result row.

            Returns:
                bool: True if the host was prepared successfully.
            """
            host = self.host
            if host is None:
                return False
            k = int(result['params'].get('k', result.get('n_clusters', 2)))
            try:
                if hasattr(host, 'k_combo'):
                    host.k_combo.blockSignals(True)
                    if host.k_combo.findText(str(k)) < 0:
                        host.k_combo.addItem(str(k))
                    host.k_combo.setCurrentText(str(k))
                    host.k_combo.setEnabled(True)
                    host.k_combo.blockSignals(False)
                host.optimal_k = k
                host.optimal_algo = result['algorithm']
                if hasattr(host, 'cluster_btn'):
                    host.cluster_btn.setEnabled(True)
                if hasattr(host, 'bs_btn'):
                    host.bs_btn.setEnabled(True)
                return True
            except Exception:
                return False

        def _host_cluster(self):
            """Trigger the host's clustering run directly."""
            try:
                self.host._run_clustering()
                return True
            except Exception:
                return False

        def _host_bootstrap(self):
            """Prepare the host data matrix and run its K-stability bootstrap."""
            host = self.host
            if host is None:
                return False
            try:
                elements = self._get_elements()
                data = host._prepare_data(elements)
                if data is None or len(data) < 10:
                    QMessageBox.information(self, "Bootstrap",
                                            "Too few particles for a bootstrap.")
                    return False
                host._data_matrix_cache = data
                cfg = host.node.config
                enabled_metrics = cfg.get('enabled_metrics', [])
                safe = [m for m in METRIC_REGISTRY
                        if METRIC_REGISTRY[m].get('bootstrap_safe')]
                if not any(m in enabled_metrics for m in safe):
                    pick = safe[0] if safe else None
                    if pick:
                        cfg['enabled_metrics'] = list(enabled_metrics) + [pick]
                if not host.eval_results:
                    host.eval_results = host._evaluate_data(
                        data,
                        enabled_algos=cfg.get('enabled_algorithms'),
                        enabled_metrics=[m for m in cfg.get('enabled_metrics', [])
                                         if m in METRIC_REGISTRY])
                host._run_bootstrap()
                return True
            except Exception as exc:
                QMessageBox.warning(self, "Bootstrap",
                                    f"Could not start bootstrap: {exc}")
                return False

        def _apply_selected(self):
            """Apply the highlighted row and hand off to the host as chosen."""
            result = self._selected_result()
            if result is None and self._ranked:
                result = self._ranked[0]
            if result is None or self.node is None:
                return
            self._apply_config(result)
            prepped = self._prepare_host_for_cluster(result)
            if self.run_cluster_cb.isChecked() and self._host_cluster():
                self.accept()
                return
            if self.run_boot_cb.isChecked() and self._host_bootstrap():
                self.accept()
                return
            msg = ("Pipeline written to the clustering configuration. "
                   "② Cluster is ready with the chosen K — no evaluation needed."
                   if prepped else
                   "Pipeline written to the clustering configuration.")
            QMessageBox.information(self, "Applied", msg)

        def _export_csv(self):
            """Export the ranked leaderboard to a CSV file."""
            if not self._last or not self._last.get('results'):
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "Export results", "cluster_test_results.csv", "CSV (*.csv)")
            if not path:
                return
            import csv
            results = rank_results(self._last['results'],
                                   self.rank_combo.currentText())
            metric_cols = ([m for m in EXTERNAL_METRICS if m in results[0]] +
                           [m for m in METRIC_REGISTRY if m in results[0]])
            with open(path, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['rank', 'algorithm', 'data_type', 'scaling',
                            'dim_reduction', 'params', 'n_clusters', 'n_noise',
                            'runtime_s'] + metric_cols)
                for i, row in enumerate(results):
                    w.writerow([i + 1, row['algorithm'], row['data_type'],
                                row['scaling'], row['dim_reduction'],
                                row['params_str'], row['n_clusters'],
                                row['n_noise'], row['runtime_s']]
                               + [row.get(m, '') for m in metric_cols])
            QMessageBox.information(self, "Exported", f"Saved to {path}")

        def _collect_state(self):
            """Return a serialisable snapshot of setup and results."""
            return {
                'components': self.components_edit.text(),
                'data_types': [o for o, cb in self.data_boxes.items() if cb.isChecked()],
                'scalings': [o for o, cb in self.scale_boxes.items() if cb.isChecked()],
                'dim_reductions': [o for o, cb in self.dr_boxes.items() if cb.isChecked()],
                'ext': [o for o, cb in self.ext_boxes.items() if cb.isChecked()],
                'int': [o for o, cb in self.int_boxes.items() if cb.isChecked()],
                'min_k': self.min_k.value(),
                'max_k': self.max_k.value(),
                'ncomp': self.ncomp.value(),
                'rank_by': self.rank_combo.currentText(),
                'unknown': self.unknown_mode.isChecked(),
                'kfilter': self.kfilter_cb.isChecked(),
                'algos': {n: c.get_state() for n, c in self.algo_cards.items()},
                'last': self._last,
                'last_ncomp': self._last_ncomp,
            }

        def _save_state(self):
            """Persist the current snapshot on the node for later openings."""
            if self.node is not None:
                try:
                    self.node._cluster_test_state = self._collect_state()
                except Exception:
                    pass

        def _restore_state(self):
            """Restore setup and results from the node, if any were saved."""
            state = getattr(self.node, '_cluster_test_state', None) if self.node else None
            if not state:
                return
            try:
                self.components_edit.setText(state.get('components', self.components_edit.text()))
                self._set_axis(self.data_boxes, state.get('data_types'))
                self._set_axis(self.scale_boxes, state.get('scalings'))
                self._set_axis(self.dr_boxes, state.get('dim_reductions'))
                self._set_axis(self.ext_boxes, state.get('ext'))
                self._set_axis(self.int_boxes, state.get('int'))
                self.unknown_mode.setChecked(bool(state.get('unknown', False)))
                self._on_mode_changed(self.unknown_mode.isChecked())
                self.kfilter_cb.setChecked(bool(state.get('kfilter', False)))
                self._on_kfilter_toggled(self.kfilter_cb.isChecked())
                if state.get('min_k'):
                    self.min_k.setValue(state['min_k'])
                if state.get('max_k'):
                    self.max_k.setValue(state['max_k'])
                if state.get('ncomp'):
                    self.ncomp.setValue(state['ncomp'])
                if state.get('rank_by'):
                    self._refresh_rank_combo()
                    self.rank_combo.setCurrentText(state['rank_by'])
                for n, st in state.get('algos', {}).items():
                    if n in self.algo_cards:
                        self.algo_cards[n].set_state(st)
                self._last_ncomp = state.get('last_ncomp', 2)
                self._last = state.get('last')
                if self._last:
                    self._show_results(self._last)
            except Exception:
                pass

        def _set_axis(self, boxes, values):
            """Check exactly the boxes whose option appears in ``values``."""
            if values is None:
                return
            for o, cb in boxes.items():
                cb.setChecked(o in values)

        def _clear_data(self):
            """Forget saved results and clear the results view for this node."""
            ok = QMessageBox.question(
                self, "Delete data",
                "Forget the saved sweep results for this node?")
            if ok != QMessageBox.Yes:
                return
            self._last = None
            self._ranked = []
            self._detail_pre = None
            if self.node is not None:
                try:
                    self.node._cluster_test_state = None
                except Exception:
                    pass
            self.table.setRowCount(0)
            self.detail_table.setRowCount(0)
            self.trust_table.setRowCount(0)
            self.best_lbl.setText("Run a sweep to see results.")
            self.apply_btn.setEnabled(False)
            self.export_btn.setEnabled(False)

        def closeEvent(self, event):
            """Persist setup and results when the dialog closes."""
            self._save_state()
            super().closeEvent(event)

    def attach_to_dialog(host_dialog):
        """Add a 'Custom Test' button to an existing clustering dialog.

        Inserts a button next to the host's Export button that opens the
        :class:`CustomClusterTestDialog`.  Returns the created button, or
        ``None`` if the host layout could not be found.

        Args:
            host_dialog (QDialog): The owning ``ClusteringDisplayDialog``.

        Returns:
            QPushButton or None: The created button.
        """
        btn = QPushButton("Everything at once")
        try:
            btn.setStyleSheet(host_dialog._btn_style("#2D839A"))
        except Exception:
            pass

        def _open():
            """Open the custom-test dialog wired to the host's data and SOM."""
            dlg = CustomClusterTestDialog(
                host_dialog=host_dialog,
                node=getattr(host_dialog, 'node', None),
                som_runner=make_host_som_runner(host_dialog),
            )
            dlg.exec()

        btn.clicked.connect(_open)
        try:
            export = getattr(host_dialog, 'export_btn', None)
            if export is not None and export.parent() is not None:
                lay = export.parent().layout()
                idx = lay.indexOf(export)
                lay.insertWidget(max(idx, 0), btn)
        except Exception:
            pass
        return btn