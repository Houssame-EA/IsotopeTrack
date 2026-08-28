"""Interactive clustering tab for the Clustering Analysis dialog.

Shows the clustering the rest of the dialog computed, in a 2-D or 3-D view of
the same particles, alongside a detail figure and a worked example describing
that fit. :mod:`results.cluster.detail` derives both from the fit;
:mod:`results.cluster.live_qt` draws everything.

**The clustering is computed once.** When ② Cluster has already fitted this
configuration over these particles, its labels are adopted as they are — see
:meth:`ClusterLiveController._reusable_labels`. Only a configuration ② Cluster
has not fitted causes this tab to fit, and then only once, off the UI thread.
That is also why the two tabs cannot show different answers.

The tab builds its own display projection and does not mutate the dialog's
caches while an authoritative run is active. It follows the application's
dark/light palette live.
"""

from __future__ import annotations

import hashlib
import logging

import numpy as np

from PySide6.QtCore import QObject, Signal, QThread, QTimer, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

_log = logging.getLogger("IsotopeTrack.results.cluster.live")


try:
    from results.cluster.live_qt.view import LiveView
except Exception:
    from .live_qt.view import LiveView

try:
    from results.cluster import live_engine as engine
except Exception:
    from . import live_engine as engine

try:
    from results.cluster import detail
except Exception:
    from . import detail

from utils.numba_guard import numba_serial

try:
    from results.cluster.prep import reduction_kwargs, supported_kwargs
except ImportError:
    from .prep import reduction_kwargs, supported_kwargs

try:
    from results.compositional import (
        _apply_clr, _apply_ilr, _apply_robust_zscore,
    )
except Exception:
    from results.compositional import _apply_clr, _apply_ilr, _apply_robust_zscore

try:
    from tools.theme import theme as _app_theme
except Exception:
    try:
        from tools.theme import theme as _app_theme
    except Exception:
        _app_theme = None


SCALING_OPTIONS = ['CLR', 'ILR', 'Robust Z-score', 'None']
DATA_TYPE_OPTIONS = [
    'Counts', 'Element Mass (fg)', 'Particle Mass (fg)',
    'Element Moles (fmol)', 'Particle Moles (fmol)',
    'Element Diameter (nm)', 'Particle Diameter (nm)',
    'Element Mass %', 'Particle Mass %', 'Element Mole %', 'Particle Mole %',
]


PROJECTION_ORDER = ['PCA', 't-SNE', 'UMAP', 'None']


def _projection_options():
    """Return every projection method, each flagged with its availability.

    All four methods are always reported so the panel can list them; the ones
    whose optional dependency is missing come back with ``available`` False and
    a short reason, and the dropdown shows them greyed out rather than hiding
    them. ``PCA`` and ``None`` are pure NumPy and therefore always available;
    ``t-SNE`` needs scikit-learn and ``UMAP`` needs umap-learn.

    Returns:
        list[dict]: ``{'name': str, 'available': bool, 'reason': str}`` in
        display order.
    """
    def _probe(module):
        """Return an empty string if ``module`` imports, else why it did not."""
        try:
            __import__(module)
            return ''
        except Exception as exc:
            return f"{module} not installed ({type(exc).__name__})"

    reasons = {'PCA': '', 'None': '',
               't-SNE': _probe('sklearn.manifold'),
               'UMAP': _probe('umap')}
    return [{'name': n, 'available': not reasons[n], 'reason': reasons[n]}
            for n in PROJECTION_ORDER]


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

try:
    from results.cluster.palette import (
        CLUSTER_COLORS, NOISE_COLOR, clear_color_overrides, color_overrides,
        set_color_override,
    )
except ImportError:
    from .palette import (
        CLUSTER_COLORS, NOISE_COLOR, clear_color_overrides, color_overrides,
        set_color_override,
    )

ALGO_PARAM_MAP = {
    'K-Means': {'max_iter': 'kmeans_max_iter', 'n_init': 'kmeans_n_init',
                'tol': 'kmeans_tol', 'algorithm': 'kmeans_algorithm'},
    'MiniBatch K-Means': {'batch_size': 'mbkm_batch_size',
                          'max_iter': 'mbkm_max_iter', 'n_init': 'mbkm_n_init',
                          'max_no_improvement': 'mbkm_max_no_improvement',
                          'reassignment_ratio': 'mbkm_reassignment_ratio'},
    'Gaussian Mixture': {'covariance_type': 'gmm_covariance_type',
                         'n_init': 'gmm_n_init',
                         'init_params': 'gmm_init_params',
                         'tol': 'gmm_tol', 'reg_covar': 'gmm_reg_covar'},
    'Hierarchical': {'linkage': 'hier_linkage', 'metric': 'hier_metric'},
    'DBSCAN': {'eps': 'dbscan_eps', 'min_samples': 'dbscan_min_samples',
               'metric': 'dbscan_metric', 'algorithm': 'dbscan_algorithm',
               'leaf_size': 'dbscan_leaf_size'},
    'Mean Shift': {'bandwidth': 'meanshift_bandwidth',
                   'min_bin_freq': 'meanshift_min_bin_freq',
                   'auto_bw': 'meanshift_auto_bw',
                   'max_iter': 'meanshift_max_iter',
                   'cluster_all': 'meanshift_cluster_all'},
    'OPTICS': {'min_samples': 'optics_min_samples',
               'metric': 'optics_metric',
               'cluster_method': 'optics_cluster_method',
               'xi': 'optics_xi', 'max_eps': 'optics_max_eps',
               'min_cluster_size': 'optics_min_cluster_size',
               'predecessor_correction': 'optics_predecessor_correction'},
    'Birch': {'threshold': 'birch_threshold',
              'branching_factor': 'birch_branching_factor'},
    'Spectral': {'n_neighbors': 'spectral_n_neighbors',
                 'affinity': 'spectral_affinity',
                 'gamma': 'spectral_gamma', 'n_init': 'spectral_n_init',
                 'assign_labels': 'spectral_assign_labels'},
    'HDBSCAN': {'min_cluster_size': 'hdbscan_min_cluster_size',
                'min_samples': 'hdbscan_min_samples',
                'metric': 'hdbscan_metric',
                'cluster_selection_method':
                    'hdbscan_cluster_selection_method',
                'cluster_selection_epsilon':
                    'hdbscan_cluster_selection_epsilon',
                'alpha': 'hdbscan_alpha',
                'max_cluster_size': 'hdbscan_max_cluster_size',
                'allow_single_cluster': 'hdbscan_allow_single_cluster'},
    'SOM': {'som_rows': 'som_rows', 'som_cols': 'som_cols',
            'som_iter': 'som_n_iter', 'som_n_iter': 'som_n_iter',
            'som_sigma': 'som_sigma', 'som_lr': 'som_lr',
            'som_final_algo': 'som_final_algo'},
}
"""Engine parameter name to ``node.config`` key, per algorithm.

Every parameter the custom sweep can vary appears here, because this map is
what carries a swept pipeline into the shared configuration when a result is
applied — a parameter missing from it is silently dropped, and the Settings
panel then reproduces a different fit from the one that won. It is equally the
map :func:`fit_fingerprint` walks to decide whether two fits are the same, so
an omission also lets a stale cached fit stand in for a changed one.

``SOM`` accepts both ``som_iter`` and ``som_n_iter`` for the iteration count:
the animated engine names it the first way, the sweep grid the second, and
both must land on the same config key.
"""


PROJECTION_TO_DIMRED = {'PCA': 'PCA', 't-SNE': 't-SNE', 'UMAP': 'UMAP',
                        'None': 'None'}

FIT_CONFIG_KEYS = ('scaling', 'data_type_display', 'filter_zeros',
                   'min_particle_type_count', 'dim_reduction',
                   'dim_reduction_params')


def fit_fingerprint(cfg, algo, k):
    """Identify a clustering fit by everything that can change its answer.

    Two fits with equal fingerprints over the same particles must produce the
    same labels, so one can stand in for the other. Covers the preprocessing
    that builds the matrix, the dimensionality reduction, the algorithm, the
    cluster count and that algorithm's own parameters.

    Args:
        cfg (dict): The shared ``node.config``.
        algo (str): Algorithm name.
        k (int): Cluster count.

    Returns:
        str: An opaque key, safe to compare but not to parse.
    """
    cfg = cfg or {}
    parts = [str(algo), str(int(k))]
    for key in FIT_CONFIG_KEYS:
        parts.append('%s=%r' % (key, cfg.get(key)))
    for pkey, cfgkey in sorted(ALGO_PARAM_MAP.get(algo, {}).items()):
        parts.append('%s=%r' % (pkey, cfg.get(cfgkey)))
    return '|'.join(parts)


def index_signature(idx):
    """Return an exact, cheap identity for a particle index array.

    Used to confirm that two code paths kept the same particles in the same
    order before one reuses the other's labels.

    Args:
        idx (array-like | None): Indices into the unfiltered particle list.

    Returns:
        str: A hex digest, or ``''`` when there is nothing to identify.
    """
    if idx is None:
        return ''
    arr = np.ascontiguousarray(np.asarray(idx).ravel(), dtype=np.int64)
    return hashlib.blake2b(arr.tobytes(), digest_size=12).hexdigest()


def _compare_payload(labels, xy, info, seq):
    """Build the result payload the view expects from a fit.

    Args:
        labels (np.ndarray): Cluster id per row of ``xy``, -1 for noise.
        xy (np.ndarray): Display coordinates, row-aligned with ``labels``.
        info (dict): ``note``, ``fit_dims`` and ``fit_space`` describing the fit.
        seq (int): State sequence this fit belongs to.

    Returns:
        dict: The payload for ``result_ready``.
    """
    labels = np.asarray(labels, int)
    xy = np.asarray(xy, float)
    centroids = []
    for c in sorted({int(v) for v in labels if v >= 0}):
        pts = xy[labels == c]
        if pts.size:
            centroids.append(np.nan_to_num(pts.mean(axis=0)).tolist())
    cents = np.asarray(centroids, float) if centroids else None
    return {
        'error': None,
        'seq': int(seq),
        'note': info.get('note', ''),
        'fit_dims': info.get('fit_dims'),
        'fit_space': info.get('fit_space'),
        'labels': labels.tolist(),
        'centroids': centroids,
        'extra': {},
        'metrics': engine.full_metrics(xy, labels, cents),
    }






def _theme_vars():
    """Map the active app Palette to the CSS variables the page consumes."""
    pal = getattr(_app_theme, "palette", None) if _app_theme is not None else None
    if pal is None:
        return {
            "bg": "#ffffff", "bg2": "#f6f8fb", "panel": "#ffffff",
            "chip": "#f1f5f9", "stroke": "#e2e8f0", "stroke2": "#cbd5e1",
            "text": "#1e293b", "muted": "#64748b", "muted2": "#94a3b8",
            "accent": "#2563eb", "accent2": "#1d4ed8", "good": "#16a34a",
            "warn": "#d97706", "bad": "#dc2626", "dark": False,
        }
    return {
        "bg": pal.bg_secondary, "bg2": pal.bg_tertiary, "panel": pal.bg_secondary,
        "chip": pal.bg_tertiary, "stroke": pal.border_subtle, "stroke2": pal.border,
        "text": pal.text_primary, "muted": pal.text_muted, "muted2": pal.text_secondary,
        "accent": pal.accent, "accent2": pal.accent_hover, "good": pal.success,
        "warn": pal.warning, "bad": pal.danger, "dark": (pal.name == "dark"),
    }


#: ``node.config`` key holding ``{sample_name: shape}`` marker assignments.
SHAPE_OVERRIDE_KEY = 'cluster_sample_shapes'

#: ``node.config`` key holding the colour-by-element colormap name.
OVERLAY_CMAP_KEY = 'cluster_overlay_colormap'

try:
    from widget.colors import colorheatmap as OVERLAY_COLORMAPS
except Exception:
    _log.exception("widget.colors unavailable; falling back to viridis only")
    OVERLAY_COLORMAPS = ['viridis']

DEFAULT_OVERLAY_CMAP = OVERLAY_COLORMAPS[0] if OVERLAY_COLORMAPS else 'viridis'

_CMAP_STOPS = None


def colormap_stops(n_stops=32):
    """Sample every offered colormap into plain hex stops for the web view.

    The ② Cluster tab paints on a canvas and has no access to matplotlib, so
    each colormap in :data:`OVERLAY_COLORMAPS` is evaluated here and handed
    over as a short list of hex colours that the page interpolates between.
    Sampling once and caching keeps this off the per-state path — the stops
    never change during a session.

    Args:
        n_stops (int): Colours sampled per map. 32 is dense enough that the
            kinked maps (turbo, cubehelix) interpolate without visible banding.

    Returns:
        dict: Colormap name to a list of ``'#RRGGBB'`` strings. Empty when
            matplotlib cannot be imported, in which case the page uses its own
            built-in viridis.
    """
    global _CMAP_STOPS
    if _CMAP_STOPS is not None:
        return _CMAP_STOPS
    out = {}
    try:
        from matplotlib import colormaps
        from matplotlib.colors import to_hex
        for name in OVERLAY_COLORMAPS:
            try:
                cmap = colormaps[name]
            except Exception:
                _log.debug("Unknown colormap %r, skipping", name)
                continue
            out[name] = [to_hex(cmap(i / (n_stops - 1))) for i in range(n_stops)]
    except Exception:
        _log.exception("matplotlib unavailable; the page will use its own ramp")
    _CMAP_STOPS = out
    return out


def overlay_colormap(cfg):
    """Return the colour-by-element colormap saved on the node config.

    Args:
        cfg (dict | None): The node config.

    Returns:
        str: A name from :data:`OVERLAY_COLORMAPS`, defaulting to the first.
    """
    name = (cfg or {}).get(OVERLAY_CMAP_KEY)
    return name if name in OVERLAY_COLORMAPS else DEFAULT_OVERLAY_CMAP


def sample_shape_overrides(cfg):
    """Return the per-sample marker shapes stored on the node config.

    Colour encodes the cluster in every clustering view, so the marker shape is
    the channel left for telling samples apart. The mapping is saved with the
    project, which keeps a figure looking the same when the dialog is reopened.

    Args:
        cfg (dict | None): The node config.

    Returns:
        dict: Sample name to shape key. Empty when nothing was assigned.
    """
    raw = (cfg or {}).get(SHAPE_OVERRIDE_KEY) or {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if v}


def _rare_filter(matrix, samples, min_count):
    """Drop particles whose non-zero element signature is rarer than min_count."""
    from collections import Counter
    sigs = [frozenset(np.where(r > 0)[0]) for r in matrix]
    counts = Counter(sigs)
    keep = np.array([counts[s] >= min_count for s in sigs])
    return matrix[keep], samples[keep], keep




#: Particles used to *fit* t-SNE and UMAP. Both scale poorly, so the embedding
#: is learned from this many and every remaining particle is then placed into
#: it. All particles are drawn either way.
EMBED_FIT_MAX = 3000


def _embed_fit_index(n):
    """Row indices used to fit an embedding.

    Args:
        n (int): Number of particles available.

    Returns:
        np.ndarray: Sorted indices — all of them when the set is small enough,
        otherwise a reproducible random sample of :data:`EMBED_FIT_MAX`.
    """
    if n <= EMBED_FIT_MAX:
        return np.arange(n)
    rng = np.random.default_rng(0)
    return np.sort(rng.choice(n, EMBED_FIT_MAX, replace=False))


def _place_rest(Xs, fit_idx, Pf):
    """Give every particle a position in an embedding fitted on a subset.

    t-SNE has no out-of-sample transform, so particles outside the fitted
    subset take the position of their nearest fitted neighbour in the scaled
    feature space. Their coordinates are therefore approximate — they show
    where a particle belongs rather than an independently optimised position —
    but no particle is left out of the plot.

    Args:
        Xs (np.ndarray): Scaled matrix for every particle.
        fit_idx (np.ndarray): Rows the embedding was fitted on.
        Pf (np.ndarray): Embedded coordinates of those rows.

    Returns:
        np.ndarray: Coordinates for every row of ``Xs``.
    """
    n = len(Xs)
    if len(fit_idx) == n:
        return Pf
    P = np.zeros((n, Pf.shape[1]), float)
    P[fit_idx] = Pf
    rest = np.setdiff1d(np.arange(n), fit_idx, assume_unique=True)
    ref = Xs[fit_idx]
    step = max(1, int(2e6 // max(1, ref.shape[0] * ref.shape[1])))
    for i in range(0, len(rest), step):
        chunk = Xs[rest[i:i + step]]
        d = ((chunk[:, None, :] - ref[None, :, :]) ** 2).sum(2)
        P[rest[i:i + step]] = Pf[d.argmin(1)]
    return P


def _embed(Xs, projection, n_dims, params=None):
    """Project the scaled matrix to ``n_dims`` (2 or 3) with the chosen method.

    Returns (P, var_ratio, projection_used, loadings). ``loadings`` is the
    ``(n_features, n_dims)`` matrix of principal-component coefficients used to
    draw the biplot arrows, and is None for the embeddings — t-SNE and UMAP are
    non-linear, so no feature maps onto a straight direction in their output.

    t-SNE/UMAP fall back to PCA if scikit-learn / umap aren't importable, so
    this never hard-fails.

    ``params`` are the app's shared reduction settings (``dim_reduction_params``
    in the node config), so the panel draws the embedding the clustering
    actually ran in rather than one built from different hard-coded values. The
    component count is *not* taken from them: this output has to be 2-D or 3-D
    to be drawable, so ``n_dims`` always wins.
    """
    n_dims = 3 if int(n_dims) == 3 else 2
    n = len(Xs)
    if Xs.shape[1] < 2:
        P = np.column_stack([Xs[:, 0]] + [np.zeros(n)] * (n_dims - 1))
        return P, [1.0] + [0.0] * (n_dims - 1), "PCA", None

    if projection == "t-SNE" and n >= 5:
        try:
            from sklearn.manifold import TSNE
            fit_idx = _embed_fit_index(n)
            Xf = Xs[fit_idx]
            kw = reduction_kwargs("t-SNE", params, len(Xf), Xf.shape[1],
                                  n_components=n_dims)
            Pf = TSNE(**supported_kwargs(TSNE, kw)).fit_transform(Xf)
            P = _place_rest(Xs, fit_idx, np.asarray(Pf, float))
            return P, [float("nan")] * n_dims, "t-SNE", None
        except Exception:
            _log.exception("t-SNE unavailable; using PCA")
    elif projection == "UMAP" and n >= 5:
        try:
            import os as _os
            _os.environ.setdefault("NUMBA_THREADING_LAYER", "workqueue")
            from umap import UMAP
            fit_idx = _embed_fit_index(n)
            Xf = Xs[fit_idx]
            kw = reduction_kwargs("UMAP", params, len(Xf), Xf.shape[1],
                                  n_components=n_dims)
            with numba_serial("UMAP (live projection)"):
                model = UMAP(**supported_kwargs(UMAP, kw)).fit(Xf)
                if len(fit_idx) == n:
                    P = np.asarray(model.embedding_, float)
                else:
                    P = np.asarray(model.transform(Xs), float)
            return P, [float("nan")] * n_dims, "UMAP", None
        except Exception:
            _log.exception("UMAP unavailable; using PCA")

    Xc = Xs - Xs.mean(axis=0)
    U, Sv, Vt = np.linalg.svd(Xc, full_matrices=False)
    max_abs = np.argmax(np.abs(Vt), axis=1)
    signs = np.sign(Vt[range(Vt.shape[0]), max_abs])
    signs[signs == 0] = 1.0
    Vt = Vt * signs[:, np.newaxis]
    comps = Vt[:n_dims]
    P = Xc @ comps.T
    if P.shape[1] < n_dims:
        P = np.column_stack([P] + [np.zeros(n)] * (n_dims - P.shape[1]))
    var = Sv ** 2
    ratio = (var / var.sum()) if var.sum() > 0 else var
    vr = [float(v) for v in ratio[:n_dims]] + [0.0] * max(0, n_dims - len(ratio))
    loadings = comps.T
    if loadings.shape[1] < n_dims:
        pad = np.zeros((loadings.shape[0], n_dims - loadings.shape[1]))
        loadings = np.hstack([loadings, pad])
    return P, vr[:n_dims], "PCA", loadings


def _raw_axes(Xs, elements, n_dims):
    """Select raw feature axes for the 'None' (no-reduction) projection.

    Picks the ``n_dims`` highest-variance columns of the scaled matrix so the
    scatter is informative, and labels them with element names when the scaling
    preserves the element columns (CLR / Robust Z-score / None); otherwise uses
    generic feature names.

    Args:
        Xs (np.ndarray): Scaled data matrix (n_samples, n_features).
        elements (list[str]): Element names for the original columns.
        n_dims (int): Number of display axes (2 or 3).

    Returns:
        tuple: (P, var_ratio, projection_used, axis_labels).
    """
    n_dims = 3 if int(n_dims) == 3 else 2
    k = min(n_dims, Xs.shape[1])
    var = Xs.var(axis=0)
    cols = np.sort(np.argsort(var)[::-1][:k])
    P = Xs[:, cols]
    if P.shape[1] < n_dims:
        P = np.column_stack([P] + [np.zeros(len(P))] * (n_dims - P.shape[1]))
    if Xs.shape[1] == len(elements):
        labels = [elements[c] for c in cols]
    else:
        labels = ["Feature %d" % (c + 1) for c in cols]
    while len(labels) < n_dims:
        labels.append("")
    return P, [float("nan")] * n_dims, "None", labels


def build_view(input_data, cfg, elements, projection="PCA", n_dims=2,
               max_points=None):
    """Build an N-D projection view + aligned raw matrix from the dialog's data.

    Mirrors ``ClusteringDisplayDialog._prepare_data`` (scaling, zero filter,
    rare-type filter) but always projects to 2-D for display and touches no
    shared state. For responsiveness (and to keep O(n^2) algorithms sane) the
    view is randomly subsampled to ``max_points`` particles when one is given;
    ``n_total`` reports the full count.

    Returns dict(xy, raw, samples, sample_names, elements, n, n_total,
    var_ratio) or None.
    """
    if not input_data or not elements:
        return None
    particles = input_data.get("particle_data", [])
    if not particles:
        return None

    dt = cfg.get("data_type_display", "Counts")
    dk = DATA_KEY_MAP.get(dt, "elements")
    is_multi = input_data.get("type") == "multiple_sample_data"
    sample_names = input_data.get("sample_names", [])

    rows, samples = [], []
    for p in particles:
        d = p.get(dk, {})
        if dt in ("Element Mass %", "Particle Mass %",
                  "Element Mole %", "Particle Mole %"):
            if "Mass %" in dt:
                total = (sum(d.get(e, 0) for e in elements)
                         if dt == "Element Mass %" else p.get("particle_mass_fg", 0))
            else:
                total = (sum(d.get(e, 0) for e in elements)
                         if dt == "Element Mole %" else p.get("particle_moles_fmol", 0))
            row = [(d.get(e, 0) / total * 100 if total > 0 else 0) for e in elements]
        else:
            row = [d.get(e, 0) for e in elements]
        rows.append(row)
        samples.append(p.get("source_sample", "Sample") if is_multi else "Sample")

    matrix = np.array(rows, dtype=float)
    samples = np.array(samples)
    kept = np.arange(matrix.shape[0])
    if matrix.size == 0:
        return None

    if cfg.get("filter_zeros", True):
        mask = np.any(matrix > 0, axis=1)
        matrix, samples, kept = matrix[mask], samples[mask], kept[mask]

    if matrix.size:
        matrix, samples, keep = _rare_filter(
            matrix, samples, int(cfg.get("min_particle_type_count", 5)))
        kept = kept[keep]
    if matrix.shape[0] < 2:
        return None

    raw = matrix.copy()

    scaling = cfg.get("scaling", "CLR")
    if scaling == "CLR":
        Xs = _apply_clr(matrix)
    elif scaling == "ILR":
        Xs = _apply_ilr(matrix)
    elif scaling == "Robust Z-score":
        Xs = _apply_robust_zscore(matrix)
    else:
        Xs = matrix.astype(float)

    n_total = int(Xs.shape[0])
    if max_points is not None and n_total > max_points:
        rng = np.random.default_rng(0)
        sel = np.sort(rng.choice(n_total, max_points, replace=False))
        Xs, raw, samples, kept = Xs[sel], raw[sel], samples[sel], kept[sel]

    axis_labels = None
    loadings = None
    if projection == "None":
        P, var, proj_used, axis_labels = _raw_axes(Xs, elements, n_dims)
    else:
        P, var, proj_used, loadings = _embed(
            Xs, projection, n_dims, (cfg or {}).get("dim_reduction_params"))

    # ILR replaces the elements with D-1 balance coordinates, so a loading no
    # longer belongs to any single element and cannot be drawn as its arrow.
    if loadings is not None and loadings.shape[0] != len(elements):
        loadings = None

    return {
        "xy": P, "raw": raw, "samples": samples, "kept_index": kept,
        "scaled": Xs,
        "sample_names": list(sample_names) if is_multi else ["Sample"],
        "elements": list(elements), "n": int(P.shape[0]), "n_total": n_total,
        "dims": int(P.shape[1]), "projection": proj_used,
        "var_ratio": [float(v) for v in var], "axis_labels": axis_labels,
        "loadings": loadings,
    }




def _sklearn_params(algo, cfg, k):
    """Translate ``node.config`` into an algorithm's own parameter names.

    Inverts :data:`ALGO_PARAM_MAP`, which maps engine parameter keys to their
    config keys, and adds the shared cluster count. Used to tell
    :mod:`results.cluster.detail` what the fit ran with, so the worked example
    quotes the values you actually set.

    Args:
        algo (str): Algorithm name.
        cfg (dict): The shared ``node.config``.
        k (int): Cluster count.

    Returns:
        dict: Parameter values keyed the way the algorithm names them.
    """
    params = {"k": int(k), "n_clusters": int(k)}
    for pkey, cfgkey in ALGO_PARAM_MAP.get(algo, {}).items():
        if cfgkey in cfg:
            params[pkey] = cfg[cfgkey]
    return params




def describe_fit(cfg, k, labels, info, xy=None, som=None):
    """Derive the detail view and worked example from a finished fit.

    For SOM the neuron grid is placed in display coordinates too, so the map
    still draws over the scatter.

    Args:
        cfg (dict): The shared ``node.config``.
        k (int): Cluster count.
        labels (np.ndarray): Cluster id per particle.
        info (dict): Fit description — ``note``, ``fit_dims``, ``fit_space``,
            the ``matrix`` that was clustered and the fitted ``estimator``.
        xy (np.ndarray | None): Display coordinates, for the SOM overlay.
        som: The host's trained map, for ``selected_algorithm == 'SOM'``.

    Returns:
        dict: ``{'inset': ..., 'equation': ...}``, empty when it cannot be built.
    """
    algo = (cfg or {}).get("selected_algorithm", "K-Means")
    X = (info or {}).get("matrix")
    if X is None:
        return {}
    out = detail.build(algo, _sklearn_params(algo, cfg or {}, k), X, labels, k,
                       estimator=(info or {}).get("estimator"), som=som)
    if algo == "SOM" and xy is not None:
        grid = detail.som_overlay(som, X, xy)
        if grid:
            out = dict(out)
            out["som_nodes"] = grid["nodes"]
            out["som_edges"] = grid["edges"]
    return out


class _ProjWorker(QThread):
    """Compute a projection off the UI thread (t-SNE/UMAP can take seconds)."""
    done = Signal(object)

    def __init__(self, input_data, cfg, elements, projection, dims, parent=None):
        """Store the projection arguments."""
        super().__init__(parent)
        self._args = (input_data, cfg, elements, projection, dims)

    def run(self):
        """Build the projection view off the UI thread and emit it."""
        input_data, cfg, elements, projection, dims = self._args
        try:
            v = build_view(input_data, cfg, elements, projection=projection,
                           n_dims=dims)
        except Exception:
            _log.exception("projection build failed")
            v = None
        self.done.emit(v)


class ClusterLiveController(QObject):
    """Drives the live view: owns the projection, the fit and the config.

    Holds the built view for the current projection, produces the tab's one
    clustering result off the UI thread, and is the single place where the
    shared ``node.config`` is written.
    """
    stateReady = Signal(object)
    runFinished = Signal(object)
    status = Signal(str)

    def __init__(self, dialog, parent=None):
        """Initialise the bridge's state from the shared node config."""
        super().__init__(parent)
        self._dialog = dialog
        self._view = None
        self._view_widget = None
        self._proj_worker = None
        self._retired_projs = set()
        self._requested = None
        self._color_timer = None
        self._last_labels = None
        self._state_seq = 0
        self._fit_cache = None
        self._armed = False
        cfg = getattr(dialog.node, "config", {}) or {}
        dr = cfg.get("dim_reduction", "PCA")
        self._proj = dr if dr in PROJECTION_TO_DIMRED else "PCA"
        self._dims = 3 if int(cfg.get("live_dims", 2)) == 3 else 2

    def attach_view(self, view):
        """Adopt the :class:`~results.cluster.live_qt.view.LiveView` to drive.

        Args:
            view (LiveView): The widget that state and results are pushed to.
        """
        self._view_widget = view

    def rebuild(self):
        """Synchronous rebuild (used for the fast PCA path / fallbacks)."""
        try:
            elements = self._dialog._get_elements()
            self._view = build_view(self._dialog.node.input_data,
                                    self._dialog.node.config, elements,
                                    projection=self._proj, n_dims=self._dims)
        except Exception:
            _log.exception("live view build failed")
            self._view = None
        return self._view

    def rebuild_async(self):
        """Compute the projection on a worker thread, then push state to the view.

        Used for every projection/dimension change so t-SNE / UMAP never freeze
        the UI. The view shows a 'computing…' note until the state arrives.

        Does nothing until the tab has been armed by a clustering run, so the
        page loading or restoring its own defaults cannot start a run the user
        never asked for.
        """
        if not self._armed:
            return
        try:
            elements = self._dialog._get_elements()
            input_data = self._dialog.node.input_data
            cfg = self._dialog.node.config
        except Exception:
            _log.exception("live async rebuild setup failed")
            return
        old = self._proj_worker
        if old is not None and old.isRunning():
            self._retire_proj_worker(old)
        if self._view_widget is not None:
            self._view_widget.projecting(self._proj, self._dims)
        w = _ProjWorker(input_data, cfg, elements, self._proj, self._dims)
        w.done.connect(self._on_projected)
        self._proj_worker = w
        w.start()

    def _retire_proj_worker(self, worker):
        """Park a superseded projection worker until its thread has stopped.

        Reassigning ``_proj_worker`` used to drop the last Python reference to
        a thread that was still running, which deletes the underlying QThread
        mid-run and makes Qt abort the process. Holding the worker here keeps
        it alive; its ``done`` signal is disconnected first so the superseded
        projection is ignored when it eventually finishes.

        Args:
            worker (_ProjWorker): The worker being replaced.
        """
        try:
            worker.done.disconnect()
        except Exception:
            _log.exception("disconnecting a superseded projection failed")
        self._retired_projs.add(worker)
        worker.finished.connect(self._on_retired_proj_finished)

    def _on_retired_proj_finished(self):
        """Release a retired worker once its thread has fully stopped.

        Runs on the bridge's thread, so ``wait`` returns at once and the
        reference can be dropped safely.
        """
        worker = self.sender()
        if worker is None:
            return
        try:
            worker.wait()
        except Exception:
            _log.exception("waiting on a retired projection worker failed")
        self._retired_projs.discard(worker)

    def _on_projected(self, view):
        """Store the finished view and hand the new state to the widget."""
        self._view = view
        self._last_labels = None
        self._state_seq += 1
        payload = self._state_payload()
        if self._view_widget is not None:
            self._view_widget.set_state(payload)
        self.stateReady.emit(payload)

    def _current_k(self):
        """Return the cluster count K shared with the app (toolbar / config)."""
        cfg = getattr(self._dialog.node, "config", {}) or {}
        try:
            t = self._dialog.k_combo.currentText()
            if t:
                return int(t)
        except Exception:
            pass
        return int(cfg.get("live_k", 4))

    def _param_values(self):
        """Config-derived value for every algorithm's parameters.

        Maps each engine parameter to its ``node.config`` key (see
        ``ALGO_PARAM_MAP``) so the panel shows the same values as the Settings
        dialog. ``k`` comes from the shared cluster count.

        Returns:
            dict: ``{algorithm: {engine_param_key: value}}``.
        """
        cfg = getattr(self._dialog.node, "config", {}) or {}
        out = {}
        for algo, spec in engine.ALGORITHMS.items():
            vals = {}
            for p in spec["params"]:
                key = p["key"]
                if key == "k":
                    vals[key] = self._current_k()
                    continue
                cfgkey = ALGO_PARAM_MAP.get(algo, {}).get(key)
                vals[key] = cfg.get(cfgkey, p["default"]) if cfgkey else p["default"]
            out[algo] = vals
        return out

    def _cfg_snapshot(self):
        """Return the current preprocessing/algorithm config as a plain dict."""
        cfg = getattr(self._dialog.node, "config", {}) or {}
        return {
            "scaling": cfg.get("scaling", "CLR"),
            "data_type": cfg.get("data_type_display", "Counts"),
            "filter_zeros": cfg.get("filter_zeros", True),
            "min_particle_type_count": int(cfg.get("min_particle_type_count", 5)),
            "algorithm": cfg.get("selected_algorithm", "K-Means"),
            "label_mode": cfg.get("label_mode",
                                  cfg.get("overview_label_mode", "Symbol")),
            "display_max_isotopes": int(cfg.get("display_max_isotopes", 4)),
            "display_min_pct": float(cfg.get("display_min_pct", 1.0)),
        }

    def _state_payload(self):
        """Assemble the full state dict that is sent to the page.

        Both branches emit the same set of keys. Before a clustering run the
        projection does not exist, and the payload used to collapse to just
        ``{"n": 0, "empty": True}`` — so opening the Clusters tab first handed
        the view a dict with no ``xy``, ``elements``, ``samples``, ``dims``,
        ``axis_labels`` or ``loadings`` at all. The panel, overlay and legend
        are all rebuilt before ``_on_state`` reaches its ``empty`` guard, and a
        failure raised in there runs inside a Qt virtual called from C++, which
        takes the process down rather than surfacing as an exception. Emitting
        empty values instead of omitting the keys keeps that path safe while
        leaving the panel fully populated; ``empty`` alone decides whether the
        scatter is drawn.
        """
        v = self._view
        cfg = getattr(self._dialog.node, "config", {}) or {}
        base = {"config": self._cfg_snapshot(), "palette": CLUSTER_COLORS,
                "noise_color": NOISE_COLOR,
                "cluster_colors": {str(k): v
                                   for k, v in color_overrides(cfg).items()},
                "sample_shapes": sample_shape_overrides(cfg),
                "overlay_colormap": overlay_colormap(cfg),
                "algorithm": self._cfg_snapshot()["algorithm"], "seq": self._state_seq,
                "param_values": self._param_values(), "theme": _theme_vars()}
        if v is None:
            base.update({
                "n": 0, "n_total": 0, "empty": True,
                "elements": [],
                "xy": [], "raw": [], "samples": [], "sample_names": [],
                "var_ratio": [0.0, 0.0],
                "dims": self._dims, "projection": self._proj,
                "axis_labels": None, "loadings": None,
            })
            return base
        base.update({
            "n": v["n"], "n_total": v.get("n_total", v["n"]), "empty": False,
            "elements": v["elements"],
            "xy": np.round(v["xy"], 4).tolist(),
            "raw": np.round(v["raw"], 3).tolist(),
            "samples": v["samples"].tolist(),
            "sample_names": v["sample_names"],
            "var_ratio": v["var_ratio"],
            "dims": v.get("dims", 2), "projection": v.get("projection", "PCA"),
            "axis_labels": v.get("axis_labels"),
            "loadings": (None if v.get("loadings") is None
                         else np.round(v["loadings"], 5).tolist()),
        })
        return base

    def get_schema(self):
        """Return algorithms, scalings, data types and projections."""
        return {
            "algorithms": engine.algorithm_schema(),
            "scalings": SCALING_OPTIONS,
            "data_types": DATA_TYPE_OPTIONS,
            "projections": _projection_options(),
            "colormaps": colormap_stops(),
            "colormap_order": list(OVERLAY_COLORMAPS),
        }

    def get_theme(self):
        """Return the current theme colours."""
        return _theme_vars()

    def get_state(self):
        """Return the current view state, building it if needed.

        Before the tab is armed the projection is not built, so the payload
        reports itself as empty and the view stays blank instead of scheduling
        a run of its own.
        """
        if self._view is None and self._armed:
            self.rebuild()
        return self._state_payload()

    def set_label_mode(self, mode):
        """Persist the element label style and repaint the other views.

        Args:
            mode (str): 'Symbol', 'Mass + Symbol' or 'Atomic Notation'.
        """
        cfg = getattr(self._dialog.node, "config", None)
        if cfg is None or not mode:
            return
        if cfg.get("label_mode") == mode:
            return
        cfg["label_mode"] = mode
        try:
            self._dialog._rebuild_display_labels()
        except Exception:
            _log.exception("Handled exception rebuilding display labels")
        self._redraw_host_figures()

    def set_cluster_color(self, cid, color):
        """Persist one cluster's colour and repaint the other views.

        Stored on ``node.config`` so the ② Cluster scatters, the Overview
        strips and the heatmap use the same colour, and so the choice is saved
        with the project.

        Args:
            cid (int): Cluster label (0-based, as the engine emits it).
            color (str): ``#RRGGBB``, or empty to revert to the palette.
        """
        cfg = getattr(self._dialog.node, "config", None)
        if cfg is None:
            return
        if set_color_override(cfg, cid, color or None):
            self._redraw_host_figures()

    def reset_cluster_colors(self):
        """Drop every colour override and repaint the other views."""
        cfg = getattr(self._dialog.node, "config", None)
        if cfg is None:
            return
        if clear_color_overrides(cfg):
            self._redraw_host_figures()

    def set_sample_shape(self, sample, shape):
        """Persist the marker shape used for one sample.

        Args:
            sample (str): Sample name as it appears in the particle data.
            shape (str): Shape key chosen in the page, e.g. 'square'.
        """
        cfg = getattr(self._dialog.node, "config", None)
        if cfg is None or not sample:
            return
        current = sample_shape_overrides(cfg)
        if current.get(sample) == shape:
            return
        current[sample] = shape
        cfg[SHAPE_OVERRIDE_KEY] = current

    def reset_sample_shapes(self):
        """Drop every marker-shape assignment, restoring the default cycle."""
        cfg = getattr(self._dialog.node, "config", None)
        if cfg is None or not cfg.get(SHAPE_OVERRIDE_KEY):
            return
        cfg[SHAPE_OVERRIDE_KEY] = {}

    def set_overlay_colormap(self, name):
        """Persist the colormap used by the colour-by-element overlay.

        Args:
            name (str): A colormap name from :data:`OVERLAY_COLORMAPS`.
        """
        cfg = getattr(self._dialog.node, "config", None)
        if cfg is None or name not in OVERLAY_COLORMAPS:
            return
        cfg[OVERLAY_CMAP_KEY] = name

    def _redraw_host_figures(self):
        """Redraw the dialog's figures after a shared appearance change.

        Coalesced through a short timer because the colour picker fires on
        every drag, and each redraw rebuilds several matplotlib figures.
        """
        try:
            if self._color_timer is None:
                self._color_timer = QTimer(self)
                self._color_timer.setSingleShot(True)
                self._color_timer.setInterval(180)
                self._color_timer.timeout.connect(self._do_redraw_host)
            self._color_timer.start()
        except Exception:
            _log.exception("Handled exception scheduling a host redraw")

    def _do_redraw_host(self):
        """Repaint the dialog's figures without re-running the clustering."""
        fn = getattr(self._dialog, "_apply_display_settings", None)
        if fn is None:
            return
        try:
            fn()
        except Exception:
            _log.exception("Handled exception redrawing the host figures")


    def set_projection(self, projection, dims):
        """Change projection / dimensionality, persist to config, re-project.

        Mirrors the app's ``dim_reduction`` so the Settings dialog and the
        Cluster tab stay in sync. The 2-D/3-D choice is display-only and does
        not change the space the clustering runs in.

        Changing the reduction clears ``dim_reduction_params``: parameters
        belong to the reduction they were set for, and carrying them across
        would reinterpret shared names such as ``n_components``.
        """
        self._proj = projection or "PCA"
        self._dims = 3 if int(dims) == 3 else 2
        cfg = self._dialog.node.config
        new_dr = PROJECTION_TO_DIMRED.get(self._proj, "PCA")
        if cfg.get("dim_reduction") != new_dr:
            cfg["dim_reduction_params"] = {}
        cfg["dim_reduction"] = new_dr
        cfg["live_dims"] = self._dims
        self._invalidate_host_matrix()
        self.rebuild_async()

    def set_config(self, patch):
        """Update the shared node config from the panel, then re-project.

        Writes to ``node.config`` (the same dict the whole dialog uses) so a
        change here is consistent with the rest of the analysis. Handles
        scaling, data type, zero filter, rare-type count and the selected
        algorithm.

        """
        patch = dict(patch or {})
        cfg = self._dialog.node.config
        if "scaling" in patch:
            cfg["scaling"] = patch["scaling"]
        if "data_type" in patch:
            cfg["data_type_display"] = patch["data_type"]
        if "filter_zeros" in patch:
            cfg["filter_zeros"] = bool(patch["filter_zeros"])
        if "min_particle_type_count" in patch:
            try:
                cfg["min_particle_type_count"] = int(patch["min_particle_type_count"])
            except Exception:
                pass
        if "algorithm" in patch:
            cfg["selected_algorithm"] = patch["algorithm"]
            cfg["enabled_algorithms"] = [patch["algorithm"]]
        self._invalidate_host_matrix()
        self.rebuild_async()

    def _invalidate_host_matrix(self):
        """Drop the dialog's cached matrix so the next run re-prepares it."""
        dlg = self._dialog
        for attr in ("_data_matrix_cache", "_linkage_cache",
                     "_linkage_cache_key"):
            try:
                if hasattr(dlg, attr):
                    setattr(dlg, attr, None)
            except Exception:
                _log.exception("Handled exception invalidating %s", attr)

    def set_param(self, algo, key, value):
        """Persist one algorithm parameter to the shared node config.

        Maps the engine parameter ``key`` to its ``node.config`` key via
        ``ALGO_PARAM_MAP``, so the Settings dialog and the authoritative run
        pick up the same value. ``k`` is stored as the shared cluster count.
        """
        cfg = self._dialog.node.config
        if key == "k":
            cfg["live_k"] = int(value)
            try:
                self._dialog.k_combo.setCurrentText(str(int(value)))
            except Exception:
                pass
            return
        cfgkey = ALGO_PARAM_MAP.get(algo, {}).get(key)
        if cfgkey:
            cfg[cfgkey] = value

    def run(self, algo, params=None):
        """Produce the tab's clustering result for ``algo``.

        Records the algorithm on the shared config so the tab keeps
        ``selected_algorithm`` in step with ② Cluster, then hands off to
        :meth:`fit`, which reuses an existing result whenever one applies.

        Args:
            algo (str): Algorithm name.
            params (dict | None): Unused; the parameters come from the shared
                config so the two tabs cannot drift apart.
        """
        if self._view is None:
            self.rebuild()
        if self._view is None:
            self.runFinished.emit({"error": "no data"})
            return
        try:
            self._dialog.node.config["selected_algorithm"] = algo
        except Exception:
            pass
        self.fit()

    def _cache_fit(self, res):
        """Remember a completed fit so an identical request need not redo it.

        Args:
            res (dict): A result payload carrying ``labels``.
        """
        if self._view is None:
            return
        try:
            cfg = getattr(self._dialog.node, "config", {}) or {}
            algo = cfg.get("selected_algorithm", "K-Means")
            key = fit_fingerprint(cfg, algo, self._current_k())
            info = {"note": res.get("note", ""),
                    "fit_dims": res.get("fit_dims"),
                    "fit_space": res.get("fit_space")}
            self._fit_cache = (key, index_signature(self._view.get("kept_index")),
                               np.asarray(res["labels"], int), info)
        except Exception:
            _log.exception("Handled exception caching the fit")

    def _reusable_labels(self, algo, k):
        """Return an existing fit for ``algo`` that this run can adopt as-is.

        Looks first at the ② Cluster tab's own result and then at this
        controller's cache of its previous fit. Both are accepted only when the
        fingerprint matches — same preprocessing, reduction, algorithm, k and
        parameters — *and* the particle set is identical, index for index. Any
        doubt returns None and the fit is redone.

        Reusing the ② Cluster result is what stops the tab from computing the
        same clustering a second time, and it also removes the chance of the two
        answers disagreeing.

        Args:
            algo (str): Algorithm name.
            k (int): Cluster count.

        Returns:
            tuple | None: ``(labels, info)``, or None when nothing matches.
        """
        if self._view is None:
            return None
        cfg = getattr(self._dialog.node, "config", {}) or {}
        want = fit_fingerprint(cfg, algo, k)
        sig = index_signature(self._view.get("kept_index"))
        n = len(self._view.get("xy", ()))

        cached = self._fit_cache
        if cached and cached[0] == want and cached[1] == sig:
            info = dict(cached[3])
            info["matrix"] = self._host_matrix()
            info["estimator"] = self._host_estimator(algo)
            return cached[2], info

        stamp = cfg.get("_fit_stamp") or {}
        if stamp.get("fingerprints", {}).get(algo) != want:
            return None
        if stamp.get("index_sig") != sig:
            return None
        res = (getattr(self._dialog, "final_results", None) or {}).get(algo)
        labels = (res or {}).get("labels")
        if labels is None:
            return None
        labels = np.asarray(labels, int).ravel()
        if labels.shape[0] != n:
            return None
        space = stamp.get("fit_space") or "scaled features"
        info = {"note": f"{algo} from ② Cluster",
                "fit_dims": stamp.get("fit_dims"), "fit_space": space,
                "matrix": self._host_matrix(), "estimator": self._host_estimator(algo)}
        self._fit_cache = (want, sig, labels, dict(info))
        return labels, info

    def _host_matrix(self):
        """Return the matrix ② Cluster clustered, when it is still cached."""
        m = getattr(self._dialog, "_data_matrix_cache", None)
        return None if m is None else np.asarray(m, float)

    def _host_estimator(self, algo):
        """Return the estimator ② Cluster fitted for ``algo``, if it kept one."""
        return (getattr(self._dialog, "_fit_estimators", None) or {}).get(algo)

    def _host_som(self):
        """Return the host's trained self-organising map, if there is one."""
        return getattr(self._dialog, "_som_obj", None)

    def fit(self):
        """Show the clustering for the current configuration.

        The tab never fits anything itself. It either adopts the result ②
        Cluster already produced, or asks ② Cluster to produce it — that is the
        one and only place in the application a clustering is computed, so the
        two tabs cannot disagree and the same work is never done twice.
        """
        if self._view is None:
            self.rebuild()
        if self._view is None or self._view.get("scaled") is None:
            self._push_result({"error": "no data"})
            return
        cfg = getattr(self._dialog.node, "config", {}) or {}
        algo = cfg.get("selected_algorithm", "K-Means")
        k = self._current_k()
        reused = self._reusable_labels(algo, k)
        if reused is None:
            self._request_host_run(algo, k)
            return
        self._requested = None
        payload = _compare_payload(reused[0], self._view["xy"], reused[1],
                                   self._state_seq)
        payload["extra"] = describe_fit(cfg, k, reused[0], reused[1],
                                        xy=self._view["xy"],
                                        som=self._host_som())
        self._push_result(payload)
        self._adopt(payload)

    def _request_host_run(self, algo, k):
        """Ask ② Cluster to compute the configuration the tab is showing.

        Asked at most once per configuration. Without that guard a fit whose
        result still fails to match — a stale cluster count, an algorithm the
        install cannot provide — would ask again the moment it came back, and
        the two would trade requests forever.

        Args:
            algo (str): Algorithm the tab wants.
            k (int): Cluster count the tab wants.
        """
        want = fit_fingerprint(getattr(self._dialog.node, "config", {}) or {},
                               algo, k)
        if self._requested == want:
            self._push_result({"error": f"{algo} is unavailable for this data"})
            return
        self._requested = want
        dlg = self._dialog
        runner = getattr(dlg, "_run_clustering", None)
        if runner is None:
            self._push_result({"error": "clustering is unavailable"})
            return
        for attr in ("_cluster_worker", "_eval_worker", "_bootstrap_worker"):
            w = getattr(dlg, attr, None)
            try:
                if w is not None and w.isRunning():
                    return
            except Exception:
                pass
        try:
            dlg.node.config["enabled_algorithms"] = [algo]
        except Exception:
            pass
        self.status.emit(f"Clustering with {algo}…")
        if self._view_widget is not None:
            self._view_widget.set_busy(True, f"Clustering with {algo}…")
        QTimer.singleShot(0, runner)

    def _adopt(self, payload):
        """Take on a result and report it.

        Args:
            payload (dict): A result payload carrying ``labels``.
        """
        try:
            res = payload or {}
            if res.get("labels") is not None:
                self._cache_fit(res)
                self._last_labels = np.asarray(res["labels"], int)
                self.status.emit("Done")
            self.runFinished.emit(res)
        except Exception:
            _log.exception("Handled exception adopting the result")

    def _push_result(self, res):
        """Main-thread relay: deliver the clustering result to the view."""
        if self._view_widget is not None:
            self._view_widget.result_ready(res)

    def stop(self):
        """No-op: the tab owns no worker of its own."""




class ClusterLiveTab(QWidget):
    """QWidget hosting the interactive clustering view.

    ``dialog.py`` constructs this with the dialog, then calls :meth:`arm`,
    :meth:`mark_dirty`, :meth:`refresh_data` and :meth:`apply_theme`.
    """

    def __init__(self, dialog):
        """Set up the tab shell without building the view."""
        super().__init__()
        self._dialog = dialog
        self._loaded = False
        self._dirty = True
        self._armed = False
        self.view = None
        self.backend = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._placeholder = QLabel(
            "Run \u2461 Cluster to build the interactive view.")
        self._placeholder.setWordWrap(True)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._placeholder)

    def ensure_view(self):
        """Create the view the first time this tab is actually shown.

        Deferred so a session that never opens this tab never pays for it.

        The view is built whether or not a clustering run has happened yet, so
        the settings panel, algorithm picker and projection controls are all
        usable straight away. Only the scatter waits for results: an unarmed
        controller reports ``empty``, and :meth:`LiveView._on_state` hides the
        plot and shows its "run ② Cluster" note while leaving the panel alone.

        The wiring order matters: schema, then theme, then state. The panel has
        to exist before a state can be reflected into it.
        """
        if self.view is not None:
            return

        if self._placeholder is not None:
            self._layout.removeWidget(self._placeholder)
            self._placeholder.deleteLater()
            self._placeholder = None

        self.view = LiveView(self)
        self.backend = ClusterLiveController(self._dialog, self)
        self.backend._armed = self._armed
        self.backend.attach_view(self.view)

        self.view.request_run.connect(self.backend.run)
        self.view.request_config.connect(self.backend.set_config)
        self.view.request_projection.connect(self.backend.set_projection)
        self.view.request_param.connect(self.backend.set_param)
        self.view.request_cluster_color.connect(self.backend.set_cluster_color)
        self.view.request_reset_colors.connect(self.backend.reset_cluster_colors)
        self.view.request_sample_shape.connect(self.backend.set_sample_shape)
        self.view.request_reset_shapes.connect(self.backend.reset_sample_shapes)
        self.view.request_label_mode.connect(self.backend.set_label_mode)
        self.view.request_overlay_colormap.connect(
            self.backend.set_overlay_colormap)
        self.backend.status.connect(self.view.set_status)

        self.view.set_schema(self.backend.get_schema())
        self.view.apply_theme(self.backend.get_theme())
        self._layout.addWidget(self.view)
        self._loaded = True
        self.view.set_state(self.backend.get_state())
        self.refresh_data()

    def showEvent(self, event):
        """Build the view on first display, then behave normally.

        Args:
            event (QShowEvent): The show event delivered by Qt.
        """
        super().showEvent(event)
        self.ensure_view()

    def arm(self):
        """Allow the view to draw, once a clustering run has produced results.

        The panel is usable before this; arming is what lets the scatter draw,
        so merely opening the dialog never triggers an animation the user did
        not ask for. When the tab is already visible the redraw is deferred to
        the event loop so it runs after the calling handler has finished
        publishing its results.
        """
        self._armed = True
        self._dirty = True
        if self.backend is not None:
            self.backend._armed = True
        if self.isVisible():
            QTimer.singleShot(0, self.refresh_data)

    def mark_dirty(self):
        """Flag that the data/config changed, so the next show rebuilds."""
        self._dirty = True

    def refresh_data(self, force=False):
        """Rebuild the view only when the data changed since last time.

        Called on tab-show and on external config changes. Switching tabs with
        no data change is a no-op, so the existing result stays put and the
        animation is not replayed \u2014 it only runs on a parameter change or the
        Cluster button.
        """
        if self.view is None or not self._loaded or not self._armed:
            return
        if not (force or self._dirty):
            return
        self._dirty = False
        self.backend.rebuild_async()

    def apply_theme(self):
        """Push the current app palette into the view (dark/light switch)."""
        if self.view is None or not self._loaded:
            return
        try:
            self.view.apply_theme(_theme_vars())
        except Exception:
            _log.exception("apply_theme failed")
