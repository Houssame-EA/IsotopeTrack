"""Interactive *live* clustering tab for the Clustering Analysis dialog.

Adds a QWebEngineView-backed tab that animates *how each clustering algorithm
builds its answer* — centroids sliding, densities flooding, neuron grids
unfolding — on the same particle data the rest of the dialog uses. Python does
the maths (``live_engine`` — pure NumPy steppers); a small JS/Canvas
frontend renders it and talks back over ``QWebChannel``.

The tab is **read-only** with respect to the dialog: it builds its own 2-D PCA
view of the data and never mutates the dialog's caches, so it can't interfere
with the real evaluate/cluster pipeline or the strips/heatmap figures. It
follows the application's dark/light palette live.

If QtWebEngine is unavailable the tab degrades to a short message and the rest
of the dialog is unaffected.
"""

from __future__ import annotations

import json
import os
import sys
import logging

import numpy as np

from PySide6.QtCore import QObject, Signal, Slot, QThread, QUrl, QTimer, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

_log = logging.getLogger("IsotopeTrack.results.cluster.live")


def _safe_dumps(obj):
    """json.dumps that never emits bare NaN/Infinity (invalid JSON for JS).

    Non-finite numbers are written as ``null`` so ``JSON.parse`` on the page
    always succeeds.
    """
    return json.dumps(obj).replace("NaN", "null").replace(
        "-Infinity", "null").replace("Infinity", "null")

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from PySide6.QtWebChannel import QWebChannel
    WEBENGINE_OK = True
except Exception:
    _log.warning("QtWebEngine not available; live cluster tab disabled")
    WEBENGINE_OK = False

try:
    from results.cluster import live_engine as engine
except Exception:
    from . import live_engine as engine

from utils.numba_guard import numba_serial

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
    from results.cluster.prep import reduction_components
except ImportError:
    from .palette import (
        CLUSTER_COLORS, NOISE_COLOR, clear_color_overrides, color_overrides,
        set_color_override,
    )
    from .prep import reduction_components

ALGO_PARAM_MAP = {
    'K-Means': {'max_iter': 'kmeans_max_iter', 'n_init': 'kmeans_n_init'},
    'MiniBatch K-Means': {'batch_size': 'mbkm_batch_size',
                          'max_iter': 'mbkm_max_iter', 'n_init': 'mbkm_n_init'},
    'Gaussian Mixture': {'covariance_type': 'gmm_covariance_type'},
    'Hierarchical': {'linkage': 'hier_linkage', 'metric': 'hier_metric'},
    'DBSCAN': {'eps': 'dbscan_eps', 'min_samples': 'dbscan_min_samples',
               'metric': 'dbscan_metric'},
    'Mean Shift': {'bandwidth': 'meanshift_bandwidth',
                   'min_bin_freq': 'meanshift_min_bin_freq',
                   'auto_bw': 'meanshift_auto_bw'},
    'OPTICS': {'min_samples': 'optics_min_samples',
               'metric': 'optics_metric',
               'cluster_method': 'optics_cluster_method'},
    'Birch': {'threshold': 'birch_threshold',
              'branching_factor': 'birch_branching_factor'},
    'Spectral': {'n_neighbors': 'spectral_n_neighbors',
                 'affinity': 'spectral_affinity'},
    'HDBSCAN': {'min_cluster_size': 'hdbscan_min_cluster_size',
                'min_samples': 'hdbscan_min_samples',
                'metric': 'hdbscan_metric'},
    'SOM': {'som_rows': 'som_rows', 'som_cols': 'som_cols',
            'som_iter': 'som_n_iter', 'som_sigma': 'som_sigma',
            'som_lr': 'som_lr'},
}

PROJECTION_TO_DIMRED = {'PCA': 'PCA', 't-SNE': 't-SNE', 'UMAP': 'UMAP',
                        'None': 'None'}


def _last_dir():
    """Folder that file dialogs should open in, via the app's shared memory."""
    try:
        from utils.file_dialog_memory import load_last_directory
        return load_last_directory()
    except Exception:
        return os.path.expanduser("~")


def _remember_dir(path):
    """Persist *path* as the folder future file dialogs should start in."""
    try:
        from utils.file_dialog_memory import save_last_directory
        save_last_directory(path)
    except Exception:
        _log.debug("Handled exception remembering the export folder")


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


def _propagate_labels(sub_raw, sub_labels, raw_full):
    """Give every particle the label of its nearest labelled sample particle.

    The Cluster tab clusters a representative sample; this extends those exact
    labels to all particles (nearest neighbour in composition space) so the
    Overview strips/heatmap cover the full dataset while matching what the
    Cluster tab shows.

    Args:
        sub_raw (np.ndarray): Composition rows of the sampled particles.
        sub_labels (np.ndarray): Their cluster labels.
        raw_full (np.ndarray): Composition rows of all particles.

    Returns:
        np.ndarray: A cluster label for every row of ``raw_full``.
    """
    sub_raw = np.asarray(sub_raw, float)
    raw_full = np.asarray(raw_full, float)
    sub_labels = np.asarray(sub_labels)
    try:
        from scipy.spatial import cKDTree
        _, idx = cKDTree(sub_raw).query(raw_full, k=1)
        return sub_labels[idx]
    except Exception:
        out = np.empty(len(raw_full), dtype=int)
        step = 2000
        for i in range(0, len(raw_full), step):
            chunk = raw_full[i:i + step]
            d = ((chunk[:, None, :] - sub_raw[None, :, :]) ** 2).sum(2)
            out[i:i + step] = sub_labels[d.argmin(1)]
        return out


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


def _embed(Xs, projection, n_dims):
    """Project the scaled matrix to ``n_dims`` (2 or 3) with the chosen method.

    Returns (P, var_ratio, projection_used, loadings). ``loadings`` is the
    ``(n_features, n_dims)`` matrix of principal-component coefficients used to
    draw the biplot arrows, and is None for the embeddings — t-SNE and UMAP are
    non-linear, so no feature maps onto a straight direction in their output.

    t-SNE/UMAP fall back to PCA if scikit-learn / umap aren't importable, so
    this never hard-fails.
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
            perp = min(30, max(5, (len(Xf) - 1) // 3))
            Pf = TSNE(n_components=n_dims, random_state=42, init="pca",
                      perplexity=perp).fit_transform(Xf)
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
            nn = min(15, max(2, len(Xf) - 1))
            with numba_serial("UMAP (live projection)"):
                model = UMAP(n_components=n_dims, n_neighbors=nn,
                             random_state=42).fit(Xf)
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
    view is randomly subsampled to ``max_points`` particles for the animation;
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
        P, var, proj_used, loadings = _embed(Xs, projection, n_dims)

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


def sklearn_cluster(Xs, cfg, k):
    """Cluster ``Xs`` exactly the way the ② Cluster tab would.

    Applies the configured ``dim_reduction`` to the scaled matrix and fits the
    configured algorithm with scikit-learn, so the result is the authoritative
    one rather than the educational NumPy stepper's.

    Args:
        Xs (np.ndarray): Scaled full-feature matrix for the displayed particles.
        cfg (dict): The shared ``node.config``.
        k (int): Cluster count for the algorithms that take one.

    Returns:
        tuple: ``(labels, info)`` where ``labels`` is an int array aligned with
        ``Xs`` rows (-1 marks noise) and ``info`` is a dict describing what was
        fitted (``note``, ``fit_dims``, ``fit_space``). On failure ``labels`` is
        None and ``info`` is a plain string explaining why.
    """
    try:
        from results.cluster import tools as _tools
    except Exception:
        from . import tools as _tools

    X = np.asarray(Xs, float)
    dr = cfg.get("dim_reduction", "None")
    nc = reduction_components(dr, X.shape[1])
    try:
        if dr == "PCA" and X.shape[1] > 1:
            from sklearn.decomposition import PCA
            X = PCA(n_components=min(nc, X.shape[0])).fit_transform(X)
        elif dr == "t-SNE" and X.shape[1] > 1:
            from sklearn.manifold import TSNE
            X = TSNE(n_components=nc, random_state=42).fit_transform(X)
        elif dr == "UMAP" and X.shape[1] > 1:
            from umap import UMAP
            nn = min(15, max(2, X.shape[0] - 1))
            with numba_serial("UMAP (comparison pane)"):
                X = UMAP(n_components=nc, n_neighbors=nn,
                         random_state=42).fit_transform(X)
    except Exception:
        _log.exception("comparison reduction failed; using the scaled matrix")

    algo = cfg.get("selected_algorithm", "K-Means")
    params = _sklearn_params(algo, cfg, k)
    try:
        labels = _tools.run_algorithm(algo, params, X)
    except Exception:
        _log.exception("sklearn comparison run failed")
        return None, "scikit-learn run failed"
    if labels is None:
        return None, f"{algo} is unavailable in this install"
    labels = np.asarray(labels, int)
    space = "scaled features" if dr in (None, "None") else f"{dr} space"
    return labels, {"note": f"{algo} on {X.shape[1]}-D {space}",
                    "fit_dims": int(X.shape[1]), "fit_space": space}


def _sklearn_params(algo, cfg, k):
    """Translate ``node.config`` into the parameter names run_algorithm expects.

    Inverts :data:`ALGO_PARAM_MAP`, which maps engine parameter keys to their
    config keys, and adds the shared cluster count.

    Args:
        algo (str): Algorithm name.
        cfg (dict): The shared ``node.config``.
        k (int): Cluster count.

    Returns:
        dict: Parameters for :func:`results.cluster.tools.run_algorithm`.
    """
    params = {"k": int(k), "n_clusters": int(k)}
    for pkey, cfgkey in ALGO_PARAM_MAP.get(algo, {}).items():
        if cfgkey in cfg:
            params[pkey] = cfg[cfgkey]
    return params


class _FrameWorker(QThread):
    """QThread that streams one clustering run's frames as JSON."""
    frame = Signal(str)
    done = Signal(str)

    def __init__(self, xy, algo, params, seed=42, parent=None):
        """Store the run configuration."""
        super().__init__(parent)
        self._xy = xy
        self._algo = algo
        self._params = params
        self._seed = seed
        self._cancel = False
        self.last_labels = None

    def cancel(self):
        """Request cancellation of the running stream."""
        self._cancel = True

    def run(self):
        """Iterate the engine and emit each frame as JSON, then emit done."""
        n = 0
        try:
            for fr in engine.run(self._algo, self._params, {"xy": self._xy},
                                 self._seed):
                if self._cancel:
                    break
                self.last_labels = fr.get("labels")
                self.frame.emit(_safe_dumps(fr))
                n += 1
        except Exception as exc:
            _log.exception("live cluster worker failed")
            self.done.emit(json.dumps({"error": str(exc), "frames": n}))
            return
        self.done.emit(json.dumps({"error": None, "frames": n,
                                   "cancelled": self._cancel}))


class _SkWorker(QThread):
    """QThread that computes the authoritative scikit-learn labels."""
    done = Signal(str)

    def __init__(self, Xs, xy, cfg, k, seq=0, settle=False, parent=None):
        """Store the matrices and config for one comparison run.

        Args:
            Xs (np.ndarray): Scaled full-feature matrix for the shown particles.
            xy (np.ndarray): Display coordinates, row-aligned with ``Xs``.
            cfg (dict): Snapshot of the shared node config.
            k (int): Cluster count.
            seq (int): State sequence this fit belongs to, so the page can
                discard a result that a later projection change superseded.
            settle (bool): Whether the page should adopt this as the final
                animation frame rather than only as a comparison.
        """
        super().__init__(parent)
        self._Xs = Xs
        self._xy = np.asarray(xy, float)
        self._cfg = dict(cfg or {})
        self._k = int(k)
        self._seq = int(seq)
        self._settle = bool(settle)

    def run(self):
        """Fit with scikit-learn and emit one frame in the page's frame shape."""
        try:
            labels, info = sklearn_cluster(self._Xs, self._cfg, self._k)
        except Exception as exc:
            _log.exception("sklearn comparison worker failed")
            self.done.emit(json.dumps({"error": str(exc)}))
            return
        if labels is None:
            self.done.emit(json.dumps({"error": str(info),
                                       "settle": self._settle}))
            return

        centroids = []
        for c in sorted({int(v) for v in labels if v >= 0}):
            pts = self._xy[labels == c]
            if pts.size:
                centroids.append(np.nan_to_num(pts.mean(axis=0)).tolist())
        payload = {
            "error": None,
            "seq": self._seq,
            "settle": self._settle,
            "note": info["note"],
            "fit_dims": info["fit_dims"],
            "fit_space": info["fit_space"],
            "labels": labels.astype(int).tolist(),
            "centroids": centroids,
            "metrics": engine.cheap_metrics(self._xy, labels),
        }
        self.done.emit(_safe_dumps(payload))


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


class ClusterLiveBridge(QObject):
    """QWebChannel object bridging the NumPy engine to the web page."""
    stateReady = Signal(str)
    frameReady = Signal(str)
    runFinished = Signal(str)
    status = Signal(str)

    def __init__(self, dialog, parent=None):
        """Initialise the bridge's state from the shared node config."""
        super().__init__(parent)
        self._dialog = dialog
        self._view = None
        self._worker = None
        self._page = None
        self._pending = []
        self._proj_worker = None
        self._sk_worker = None
        self._sk_again = False
        self._sk_again_settle = False
        self._color_timer = None
        self._anim_labels = None
        self._last_labels = None
        self._state_seq = 0
        self._ov_timer = QTimer(self)
        self._ov_timer.setSingleShot(True)
        self._ov_timer.setInterval(600)
        self._ov_timer.timeout.connect(self._apply_to_overview)
        self._next_animate = False
        self._armed = False
        cfg = getattr(dialog.node, "config", {}) or {}
        dr = cfg.get("dim_reduction", "PCA")
        self._proj = dr if dr in PROJECTION_TO_DIMRED else "PCA"
        self._dims = 3 if int(cfg.get("live_dims", 2)) == 3 else 2

    def attach_page(self, page):
        """Give the bridge direct access to the page for runJavaScript pushes.

        Python→JS delivery uses ``runJavaScript`` rather than QWebChannel
        signals: in some PySide6 builds signal relay to the page silently
        drops, while method returns and runJavaScript always work (observed:
        get_state/theme arrived, signal-delivered frames never did).
        """
        self._page = page

    def _push_js(self, code):
        """Run a snippet of JavaScript on the page if one is attached."""
        if self._page is not None:
            try:
                self._page.runJavaScript(code)
            except Exception:
                _log.exception("runJavaScript push failed")

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

    def rebuild_async(self, animate=False):
        """Compute the projection on a worker thread, then push state to JS.

        ``animate`` marks whether the resulting run should play the animation
        (True for a user parameter change, False for just opening the tab).
        Used for every projection/dimension change so t-SNE / UMAP never freeze
        the UI. The page shows a 'computing…' note until the state arrives.

        Does nothing until the tab has been armed by a clustering run, so the
        page loading or restoring its own defaults cannot start a run the user
        never asked for.
        """
        if not self._armed:
            return
        self._next_animate = bool(animate)
        try:
            elements = self._dialog._get_elements()
            input_data = self._dialog.node.input_data
            cfg = self._dialog.node.config
        except Exception:
            _log.exception("live async rebuild setup failed")
            return
        if self._proj_worker is not None and self._proj_worker.isRunning():
            self._proj_worker.wait(50)
        self._push_js("window.__clusterLive && "
                      "window.__clusterLive.projecting && "
                      "window.__clusterLive.projecting('%s', %d);"
                      % (self._proj, self._dims))
        w = _ProjWorker(input_data, cfg, elements, self._proj, self._dims)
        w.done.connect(self._on_projected)
        self._proj_worker = w
        w.start()

    def _on_projected(self, view):
        """Store the finished view and push the new state to the page."""
        self._view = view
        self._last_labels = None
        self._state_seq += 1
        payload = _safe_dumps(self._state_payload())
        self._push_js("window.__clusterLive && "
                      "window.__clusterLive.setState(%s);" % payload)
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
        """Assemble the full state dict that is sent to the page."""
        v = self._view
        cfg = getattr(self._dialog.node, "config", {}) or {}
        base = {"config": self._cfg_snapshot(), "palette": CLUSTER_COLORS,
                "noise_color": NOISE_COLOR,
                "cluster_colors": {str(k): v
                                   for k, v in color_overrides(cfg).items()},
                "sample_shapes": sample_shape_overrides(cfg),
                "overlay_colormap": overlay_colormap(cfg),
                "algorithm": self._cfg_snapshot()["algorithm"], "seq": self._state_seq,
                "animate": self._next_animate,
                "param_values": self._param_values(), "theme": _theme_vars()}
        if v is None:
            base.update({"n": 0, "empty": True})
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

    @Slot(result=str)
    def get_schema(self):
        """Return algorithms, scalings, data types and projections as JSON."""
        return json.dumps({
            "algorithms": engine.algorithm_schema(),
            "scalings": SCALING_OPTIONS,
            "data_types": DATA_TYPE_OPTIONS,
            "projections": _projection_options(),
            "colormaps": colormap_stops(),
            "colormap_order": list(OVERLAY_COLORMAPS),
        })

    @Slot(result=str)
    def get_theme(self):
        """Return the current theme CSS variables as JSON."""
        return json.dumps(_theme_vars())

    @Slot(result=str)
    def get_state(self):
        """Return the current view state as JSON, building it if needed.

        Before the tab is armed the projection is not built, so the payload
        reports itself as empty and the page leaves the canvas blank instead
        of scheduling a run of its own.
        """
        if self._view is None and self._armed:
            self.rebuild()
        return _safe_dumps(self._state_payload())

    @Slot(str)
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

    @Slot(int, str)
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

    @Slot()
    def reset_cluster_colors(self):
        """Drop every colour override and repaint the other views."""
        cfg = getattr(self._dialog.node, "config", None)
        if cfg is None:
            return
        if clear_color_overrides(cfg):
            self._redraw_host_figures()

    @Slot(str, str)
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

    @Slot()
    def reset_sample_shapes(self):
        """Drop every marker-shape assignment, restoring the default cycle."""
        cfg = getattr(self._dialog.node, "config", None)
        if cfg is None or not cfg.get(SHAPE_OVERRIDE_KEY):
            return
        cfg[SHAPE_OVERRIDE_KEY] = {}

    @Slot(str)
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

    @Slot(str, result=str)
    def pick_color(self, initial):
        """Open the native colour dialog and return the chosen ``#RRGGBB``.

        Qt WebEngine ships no colour chooser, so ``<input type="color">`` on
        the page is inert; the JS picker calls this instead. Returns an empty
        string when the user cancels (or on any failure), which the page reads
        as "keep the current colour".

        :param initial: Starting colour as ``#RRGGBB``.
        :returns: Chosen colour as ``#RRGGBB``, or ``''`` if cancelled.
        """
        try:
            from PySide6.QtWidgets import QColorDialog
            from PySide6.QtGui import QColor
            start = QColor(initial or "#2563EB")
            if not start.isValid():
                start = QColor("#2563EB")
            parent = self._dialog if isinstance(self._dialog, QWidget) else None
            col = QColorDialog.getColor(start, parent, "Cluster colour")
            if col.isValid():
                return col.name()          # '#rrggbb'
        except Exception:
            _log.exception("Handled exception opening colour dialog")
        return ""

    @Slot(str, int)
    def set_projection(self, projection, dims):
        """Change projection / dimensionality, persist to config, re-project.

        Mirrors the app's ``dim_reduction`` so the Settings dialog and the
        Cluster tab stay in sync. The 2-D/3-D choice is display-only and does
        not change the space the clustering runs in.
        """
        self._proj = projection or "PCA"
        self._dims = 3 if int(dims) == 3 else 2
        cfg = self._dialog.node.config
        cfg["dim_reduction"] = PROJECTION_TO_DIMRED.get(self._proj, "PCA")
        cfg["live_dims"] = self._dims
        self._invalidate_host_matrix()
        self.rebuild_async(animate=True)

    @Slot(str)
    def set_config(self, payload_json):
        """Update the shared node config from the panel, then re-project.

        Writes to ``node.config`` (the same dict the whole dialog uses) so a
        change here is consistent with the rest of the analysis. Handles
        scaling, data type, zero filter, rare-type count and the selected
        algorithm.
        """
        try:
            patch = json.loads(payload_json or "{}")
        except Exception:
            return
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
        self.rebuild_async(animate=True)

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

    @Slot(str, str, str)
    def set_param(self, algo, key, value_json):
        """Persist one algorithm parameter to the shared node config.

        Maps the engine parameter ``key`` to its ``node.config`` key via
        ``ALGO_PARAM_MAP`` and stores the JSON-decoded value, so the Settings
        dialog and the authoritative run pick up the same value. ``k`` is stored
        as the shared cluster count.
        """
        try:
            value = json.loads(value_json)
        except Exception:
            value = value_json
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

    @Slot(str, str)
    def run(self, algo, params_json):
        """Start a clustering run and stream its frames to the page.

        Records the algorithm on the shared config so a run also keeps
        ``selected_algorithm`` in step with the Cluster tab.
        """
        if self._view is None:
            self.rebuild()
        if self._view is None:
            self.runFinished.emit(json.dumps({"error": "no data"}))
            return
        self.stop()
        params = json.loads(params_json or "{}")
        try:
            self._dialog.node.config["selected_algorithm"] = algo
        except Exception:
            pass
        self.status.emit(f"Running {algo}…")
        w = _FrameWorker(self._view["xy"], algo, params)
        w.frame.connect(self._relay_frame)
        w.done.connect(self._on_done)
        self._worker = w
        w.start()

    @Slot()
    @Slot(bool)
    def run_sklearn(self, settle=False):
        """Compute the authoritative scikit-learn labels for the shown particles.

        Fits in the same space the ② Cluster tab uses (scaled features, then the
        configured ``dim_reduction``). The result reaches the page through
        ``__clusterLive.compareReady``.

        Args:
            settle: When True the page also appends the result as the final
                animation frame, so the view settles on the real answer instead
                of the stepper's approximation.
        """
        if self._view is None:
            self.rebuild()
        if self._view is None or self._view.get("scaled") is None:
            self._push_compare(json.dumps({"error": "no data"}))
            return
        if self._sk_worker is not None and self._sk_worker.isRunning():
            self._sk_again = True
            self._sk_again_settle = self._sk_again_settle or bool(settle)
            return
        self._sk_again = False
        cfg = getattr(self._dialog.node, "config", {}) or {}
        self.status.emit("Computing result…")
        w = _SkWorker(self._view["scaled"], self._view["xy"], cfg,
                      self._current_k(), self._state_seq, bool(settle))
        w.done.connect(self._push_compare)
        w.done.connect(self._sk_finished)
        self._sk_worker = w
        w.start()

    @Slot(str)
    def _sk_finished(self, payload):
        """Adopt the settled labels, then re-run if a request was queued."""
        try:
            res = json.loads(payload or "{}")
            if res.get("settle") and res.get("labels") is not None:
                self._last_labels = np.asarray(res["labels"], int)
                self.status.emit("Done")
                self._ov_timer.start()
        except Exception:
            _log.exception("Handled exception adopting the settled labels")
        if self._sk_again:
            self._sk_again = False
            again_settle = self._sk_again_settle
            self._sk_again_settle = False
            QTimer.singleShot(0, lambda: self.run_sklearn(again_settle))

    @Slot(str)
    def _push_compare(self, s):
        """Main-thread relay: deliver the comparison result to the page."""
        self._push_js(
            "window.__clusterLive && window.__clusterLive.compareReady(%s);" % s)

    @Slot(str)
    def _relay_frame(self, s):
        """Main-thread relay: deliver a frame to the page.

        Primary path is runJavaScript (reliable); the signal is kept as a
        secondary path for environments where it does work. Frames are batched
        per event-loop turn to keep runJavaScript call count low.
        """
        self._pending.append(s)
        if len(self._pending) == 1:
            QTimer.singleShot(0, self._flush_frames)
        self.frameReady.emit(s)

    def _flush_frames(self):
        """Push any buffered frames to the page in a single batch."""
        if not self._pending:
            return
        batch = "[" + ",".join(self._pending) + "]"
        self._pending = []
        self._push_js(
            "window.__clusterLive && window.__clusterLive.pushFrames(%s);"
            % batch)

    @Slot()
    def stop(self):
        """Cancel and dispose of the running frame worker."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)
        self._worker = None

    def _on_done(self, summary):
        """Flush remaining frames, then settle the view on the real result.

        The animation illustrates the method; the answer it leaves on screen is
        replaced by the scikit-learn fit so the tab, ② Cluster and the Overview
        all show one clustering. That also restores the algorithms the stepper
        can only approximate — most importantly HDBSCAN, whose cluster count is
        derived from the data rather than taken from the shared ``k``.
        """
        self._flush_frames()
        self._push_js(
            "window.__clusterLive && window.__clusterLive.runDone(%s);" % summary)
        self.runFinished.emit(summary)
        if self._worker is not None:
            self._anim_labels = self._worker.last_labels
        self.run_sklearn(settle=True)

    def _apply_to_overview(self):
        """Feed the Cluster tab's result into the Overview strips/heatmap.

        Runs on the *settled* labels — the scikit-learn fit adopted in
        :meth:`_sk_finished`, not the animation's approximation — so the strips
        and heatmap show the same clustering as ② Cluster. This is why the feed
        is safe to enable: the tab no longer has an answer of its own that could
        overwrite the official figures.

        Extends those labels to every particle and populates the dialog's
        ``final_results``/``characterisation`` caches, then draws the Overview.
        Skipped while an authoritative cluster/eval/bootstrap run is active (the
        only case that could race the shared caches). Fully guarded.
        """
        dlg = self._dialog
        if self._view is None or self._last_labels is None:
            return
        if not hasattr(dlg, "final_results") or not hasattr(dlg, "_characterise"):
            return
        for attr in ("_cluster_worker", "_eval_worker", "_bootstrap_worker"):
            w = getattr(dlg, attr, None)
            try:
                if w is not None and w.isRunning():
                    return
            except Exception:
                pass
        try:
            elements = list(self._view["elements"])
            algo = dlg.node.config.get("selected_algorithm", "K-Means")
            full = build_view(dlg.node.input_data, dlg.node.config, elements,
                              projection="None", n_dims=2, max_points=10 ** 9)
            if full is None:
                return
            raw_full = np.asarray(full["raw"], float)
            labels_full = _propagate_labels(
                np.asarray(self._view["raw"], float),
                np.asarray(self._last_labels), raw_full)
            dlg._particle_indices = np.asarray(full["kept_index"])
            dlg._particle_samples = np.asarray(full["samples"])
            dlg._elements_filtered = elements
            dlg._raw_matrix = raw_full
            dlg.final_results = {algo: {"labels": labels_full}}
            dlg._characterise(elements, None)
            try:
                if hasattr(dlg, "ov_algo"):
                    dlg.ov_algo.blockSignals(True)
                    dlg.ov_algo.clear()
                    dlg.ov_algo.addItem(algo)
                    dlg.ov_algo.setCurrentText(algo)
                    dlg.ov_algo.blockSignals(False)
            except Exception:
                _log.exception("overview algo selector update failed")
            if hasattr(dlg, "_draw_overview"):
                dlg._draw_overview()
        except Exception:
            _log.exception("apply_to_overview failed")


class ClusterLiveTab(QWidget):
    """QWidget hosting the interactive clustering web view."""

    def __init__(self, dialog):
        """Set up the tab shell without starting the web engine."""
        super().__init__()
        self._dialog = dialog
        self._loaded = False
        self._dirty = True
        self._armed = False
        self.view = None
        self.backend = None
        self.channel = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        if not WEBENGINE_OK:
            msg = QLabel("The interactive clustering view needs QtWebEngine, "
                         "which isn't available in this build.\nThe other tabs "
                         "work as usual.")
            msg.setWordWrap(True)
            self._layout.addWidget(msg)
            self._placeholder = None
            return

        self._placeholder = QLabel(
            "Run ② Cluster to build the interactive view.")
        self._placeholder.setWordWrap(True)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._placeholder)

    def ensure_view(self):
        """Create the web view the first time this tab is actually shown.

        Constructing a ``QWebEngineView`` starts a Chromium child process,
        which is the most environment-sensitive part of the application: it
        depends on the graphics driver, the sandbox and the OS build, and a
        failure there aborts the whole process below Python where no
        ``try``/``except`` can intercept it. Building it on demand keeps that
        risk out of every session that never opens this tab.
        """
        if not WEBENGINE_OK or self.view is not None:
            return

        if self._placeholder is not None:
            self._layout.removeWidget(self._placeholder)
            self._placeholder.deleteLater()
            self._placeholder = None

        self.view = QWebEngineView(self)
        st = self.view.settings()
        st.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        st.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)

        self._inject_qwebchannel()

        self.backend = ClusterLiveBridge(self._dialog, self)
        self.backend._armed = self._armed
        self.backend._view_widget = self.view
        self.backend.attach_page(self.view.page())
        self.channel = QWebChannel(self.view.page())
        self.channel.registerObject("backend", self.backend)
        self.view.page().setWebChannel(self.channel)
        self.view.loadFinished.connect(self._on_load_finished)
        self._connect_downloads()

        base = getattr(sys, "_MEIPASS", None)
        if base:
            index = os.path.join(base, "results", "cluster",
                                 "live_ui", "index.html")
        else:
            index = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "live_ui", "index.html")
        if not os.path.isfile(index):
            _log.error("live_ui assets missing at %s", index)
        self.view.load(QUrl.fromLocalFile(index))
        self._layout.addWidget(self.view)

    def showEvent(self, event):
        """Build the web view on first display, then behave normally.

        Args:
            event (QShowEvent): The show event delivered by Qt.
        """
        super().showEvent(event)
        self.ensure_view()

    def arm(self):
        """Allow the view to draw, once a clustering run has produced results.

        Until this is called the tab stays blank even if it is opened, so
        merely opening the dialog never triggers an animation the user did
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

    def _connect_downloads(self):
        """Accept image exports from the page and let the user choose where.

        Qt cancels any ``QWebEngineDownloadRequest`` that nothing accepts, so
        without this the page's ``<a download>`` exports are silently discarded
        while the page still reports success.
        """
        try:
            profile = self.view.page().profile()
            profile.downloadRequested.connect(self._on_download)
        except Exception:
            _log.exception("could not connect the download handler")

    def _on_download(self, item):
        """Prompt for a destination and accept or cancel the download.

        Args:
            item (QWebEngineDownloadRequest): The pending download.
        """
        from PySide6.QtWidgets import QFileDialog

        try:
            name = item.downloadFileName() or "cluster-lab.png"
        except Exception:
            name = "cluster-lab.png"
        try:
            start = os.path.join(_last_dir(), name)
            path, _ = QFileDialog.getSaveFileName(
                self, "Save image", start, "PNG image (*.png);;All files (*)")
            if not path:
                item.cancel()
                return
            if not os.path.splitext(path)[1]:
                path += ".png"
            item.setDownloadDirectory(os.path.dirname(path))
            item.setDownloadFileName(os.path.basename(path))
            for sig in ("isFinishedChanged", "stateChanged"):
                s = getattr(item, sig, None)
                if s is not None:
                    s.connect(lambda *_a, it=item: self._on_download_done(it))
                    break
            item.accept()
            _remember_dir(os.path.dirname(path))
        except Exception:
            _log.exception("download handling failed")
            try:
                item.cancel()
            except Exception:
                pass

    def _on_download_done(self, item):
        """Report the saved path (or the failure) on the page's status line."""
        try:
            if not item.isFinished():
                return
            state = item.state()
            done = getattr(type(item).DownloadState, "DownloadCompleted", None)
            ok = (state == done) if done is not None else True
            path = os.path.join(item.downloadDirectory(), item.downloadFileName())
            msg = ("Saved " + path) if ok else ("Export failed: " + path)
            self.backend.status.emit(msg)
            self.backend._push_js(
                "window.showStatus && window.showStatus(%s);" % json.dumps(msg))
        except Exception:
            _log.exception("Handled exception reporting a finished download")

    def _inject_qwebchannel(self):
        """Load qwebchannel.js from the Qt resource and inject at doc creation."""
        try:
            from PySide6.QtWebEngineCore import QWebEngineScript
            from PySide6.QtCore import QFile, QIODevice
        except Exception:
            _log.exception("QWebEngineScript unavailable for injection")
            return
        try:
            f = QFile(":/qtwebchannel/qwebchannel.js")
            if not f.open(QIODevice.ReadOnly):
                _log.warning("qwebchannel.js resource missing; relying on qrc tag")
                return
            try:
                src = bytes(f.readAll().data()).decode("utf-8")
            finally:
                f.close()
            script = QWebEngineScript()
            script.setName("qwebchannel.js")
            script.setSourceCode(src)
            ip = getattr(QWebEngineScript, "InjectionPoint", QWebEngineScript)
            wid = getattr(QWebEngineScript, "ScriptWorldId", QWebEngineScript)
            script.setInjectionPoint(getattr(ip, "DocumentCreation"))
            script.setWorldId(getattr(wid, "MainWorld"))
            script.setRunsOnSubFrames(False)
            self.view.page().scripts().insert(script)
        except Exception:
            _log.exception("qwebchannel.js injection failed; relying on qrc tag")

    def _on_load_finished(self, ok):
        """Apply the theme and push data once the page has loaded."""
        self._loaded = bool(ok)
        if ok:
            self.apply_theme()
            self._dirty = True
            self.refresh_data()

    def mark_dirty(self):
        """Flag that the data/config changed, so the next show rebuilds."""
        self._dirty = True

    def refresh_data(self, force=False):
        """Rebuild the view only when the data changed since last time.

        Called on tab-show and on external config changes. Switching tabs with
        no data change is a no-op, so the existing result stays put and the
        animation is not replayed — it only runs on a parameter change or the
        Cluster button.
        """
        if self.view is None or not self._loaded or not self._armed:
            return
        if not (force or self._dirty):
            return
        self._dirty = False
        self.backend.rebuild_async()

    def apply_theme(self):
        """Push the current app palette into the page (dark/light switch)."""
        if self.view is None or not self._loaded:
            return
        try:
            payload = json.dumps(_theme_vars())
            self.view.page().runJavaScript(
                f"window.applyTheme && window.applyTheme({payload});")
        except Exception:
            _log.exception("apply_theme failed")
