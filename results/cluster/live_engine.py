"""Preprocessing, metrics and the parameter schema behind the Cluster Lab tab.

This module used to carry a second, hand-written NumPy implementation of every
clustering algorithm, exposed as generators that yielded one frame per iteration
so the tab could animate the answer being built. That meant every clustering was
computed twice — once here to be watched, once with scikit-learn to be believed —
and the two could disagree. The steppers are gone. The tab now shows the single
scikit-learn fit the rest of the app already performs, and
:mod:`results.cluster.detail` derives the detail view and worked example from
that same fit.

What remains here is everything that was never about animation:

``preprocess`` / ``build_matrix``
    Turn the dialog's particle records into a matrix, apply the zero filter and
    the configured scaling, and project to the 2-D display coordinates the
    scatter draws in.
``silhouette`` / ``davies_bouldin`` / ``cheap_metrics`` / ``full_metrics``
    The validity scores shown beside the plot.
``ALGORITHMS`` / ``algorithm_schema``
    The parameter schema that builds the control panel — which algorithms exist,
    what each one is for, and the range and default of every knob.
``_inset`` / ``_eq`` / ``_n``
    Payload builders for the two boxes, shared with
    :mod:`results.cluster.detail`.

Depends only on NumPy.
"""

from __future__ import annotations

import logging
import math

import numpy as np

_log = logging.getLogger("IsotopeTrack.results.cluster.live_engine")


SCALINGS = ["None", "CLR", "Robust Z-score", "Standardize"]


def _multiplicative_replacement(X, frac=0.65):
    """Replace zeros with a fraction of each column's smallest positive value."""
    X = np.array(X, dtype=np.float64)
    if X.size == 0:
        return X
    out = X.copy()
    for j in range(X.shape[1]):
        col = X[:, j]
        pos = col[col > 0]
        floor = pos.min() if pos.size else 1.0
        delta = frac * floor
        out[col == 0, j] = delta
    row_tot = X.sum(axis=1, keepdims=True)
    row_tot[row_tot == 0] = 1.0
    new_tot = out.sum(axis=1, keepdims=True)
    out = out * (row_tot / new_tot)
    return out


def _clr(X):
    """Centred log-ratio transform of a composition matrix."""
    Xp = _multiplicative_replacement(X)
    logX = np.log(Xp)
    return logX - logX.mean(axis=1, keepdims=True)


def _robust_z(X):
    """Median/MAD robust z-score standardisation."""
    med = np.median(X, axis=0)
    mad = np.median(np.abs(X - med), axis=0)
    mad[mad == 0] = 1.0
    return (X - med) / (1.4826 * mad)


def _standardize(X):
    """Mean/standard-deviation standardisation."""
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd == 0] = 1.0
    return (X - mu) / sd


def _pca_2d(X):
    """Project to 2 components; returns (P, explained_variance_ratio[:2])."""
    Xc = X - X.mean(axis=0)
    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    comps = Vt[:2]
    P = Xc @ comps.T
    var = (S ** 2)
    ratio = var / var.sum() if var.sum() > 0 else var
    return P, ratio[:2]


def build_matrix(input_data, elements, cfg):
    """Turn ``input_data`` into (raw_matrix, sample_labels) for ``elements``."""
    particles = input_data.get("particle_data", [])
    is_multi = input_data.get("type") == "multiple_sample_data"
    rows, samples = [], []
    for p in particles:
        d = p.get("elements", {})
        rows.append([float(d.get(e, 0.0)) for e in elements])
        samples.append(p.get("source_sample", "Sample") if is_multi else "Sample")
    M = np.array(rows, dtype=np.float64) if rows else np.zeros((0, len(elements)))
    return M, np.array(samples)


def preprocess(input_data, elements, cfg):
    """Full pipeline: matrix -> filter -> scale -> PCA-2D display projection.

    Returns a dict with keys: xy (n,2), raw (n,e), samples (n,), elements,
    var_ratio (2,), n, kept_index (into original particles).
    """
    M, samples = build_matrix(input_data, elements, cfg)
    if M.shape[0] == 0:
        return None
    idx = np.arange(M.shape[0])

    if cfg.get("filter_zeros", True):
        mask = np.any(M > 0, axis=1)
        M, samples, idx = M[mask], samples[mask], idx[mask]

    scaling = cfg.get("scaling", "CLR")
    if scaling == "CLR":
        Xs = _clr(M)
    elif scaling == "Robust Z-score":
        Xs = _robust_z(M)
    elif scaling == "Standardize":
        Xs = _standardize(M)
    else:
        Xs = M.astype(np.float64)

    P, var_ratio = _pca_2d(Xs)
    span = np.percentile(np.abs(P), 99, axis=0)
    span[span == 0] = 1.0
    P = P / span

    return {
        "xy": P,
        "raw": M,
        "samples": samples,
        "elements": list(elements),
        "var_ratio": [float(v) for v in var_ratio],
        "n": int(P.shape[0]),
        "kept_index": idx.tolist(),
    }


def _inertia(P, labels, centroids):
    """Total within-cluster squared distance to the centroids."""
    if centroids is None or len(centroids) == 0:
        return 0.0
    tot = 0.0
    for k, c in enumerate(centroids):
        pts = P[labels == k]
        if len(pts):
            tot += float(((pts - c) ** 2).sum())
    return tot


def silhouette(P, labels, max_points=500, rng=None):
    """Subsampled silhouette score (mean over up to ``max_points`` points)."""
    rng = rng or np.random.default_rng(0)
    mask = labels >= 0
    Pv, lv = P[mask], labels[mask]
    uniq = np.unique(lv)
    if len(uniq) < 2 or len(Pv) < 3:
        return float("nan")
    if len(Pv) > max_points:
        sel = rng.choice(len(Pv), max_points, replace=False)
        Pv, lv = Pv[sel], lv[sel]
    scores = []
    for i in range(len(Pv)):
        same = lv == lv[i]
        same[i] = False
        if same.sum() == 0:
            scores.append(0.0)
            continue
        a = np.sqrt(((Pv[same] - Pv[i]) ** 2).sum(1)).mean()
        b = np.inf
        for c in uniq:
            if c == lv[i]:
                continue
            other = Pv[lv == c]
            if len(other) == 0:
                continue
            d = np.sqrt(((other - Pv[i]) ** 2).sum(1)).mean()
            b = min(b, d)
        scores.append((b - a) / max(a, b) if max(a, b) > 0 else 0.0)
    return float(np.mean(scores))


def davies_bouldin(P, labels, centroids=None):
    """Davies-Bouldin cluster-validity index (lower is better)."""
    uniq = np.unique(labels[labels >= 0])
    if len(uniq) < 2:
        return float("nan")
    cents, spreads = [], []
    for c in uniq:
        pts = P[labels == c]
        ctr = pts.mean(0)
        cents.append(ctr)
        spreads.append(np.sqrt(((pts - ctr) ** 2).sum(1)).mean())
    cents = np.array(cents)
    spreads = np.array(spreads)
    db = 0.0
    for i in range(len(uniq)):
        best = 0.0
        for j in range(len(uniq)):
            if i == j:
                continue
            d = np.sqrt(((cents[i] - cents[j]) ** 2).sum())
            if d > 0:
                best = max(best, (spreads[i] + spreads[j]) / d)
        db += best
    return float(db / len(uniq))


def cheap_metrics(P, labels, centroids=None):
    """Fast per-frame metrics: cluster count, noise, inertia and sizes."""
    lab = np.asarray(labels)
    uniq = np.unique(lab[lab >= 0])
    sizes = {int(c): int((lab == c).sum()) for c in uniq}
    return {
        "n_clusters": int(len(uniq)),
        "n_noise": int((lab < 0).sum()),
        "inertia": _inertia(P, lab, centroids),
        "sizes": sizes,
    }


def _finite_or_none(x):
    """Return ``x`` if it is a finite number, otherwise ``None`` (JSON-safe)."""
    try:
        return float(x) if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def full_metrics(P, labels, centroids=None, rng=None):
    """Cheap metrics plus silhouette and Davies-Bouldin scores (JSON-safe)."""
    m = cheap_metrics(P, labels, centroids)
    m["silhouette"] = _finite_or_none(silhouette(P, np.asarray(labels), rng=rng))
    m["davies_bouldin"] = _finite_or_none(
        davies_bouldin(P, np.asarray(labels), centroids))
    return m


def _inset(kind, title, subtitle="", **payload):
    """Build the algorithm-specific *detail view* payload for the UI inset.

    Every stepper attaches one of these to ``frame['extra']['inset']`` so the
    frontend can draw the small box next to the main scatter — the dendrogram
    for Hierarchical, the reachability plot for OPTICS, the objective curve for
    K-Means and so on — while the same frame animates the points.

    Args:
        kind (str): Renderer to use — ``'curve'``, ``'bars'``, ``'dendrogram'``
            or ``'grid'``.
        title (str): Bold heading of the inset box.
        subtitle (str): One-line explanation shown under the title.
        **payload: Renderer-specific data (see each stepper).

    Returns:
        dict: ``{'inset': {...}}``, ready to merge into a frame's ``extra``.
    """
    d = {"kind": kind, "title": title, "subtitle": subtitle}
    d.update(payload)
    return {"inset": d}


_SUPERSCRIPT = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def _n(v, p=3):
    """Format one number for a worked example (compact, never NaN/inf).

    Very large and very small magnitudes become ``5.17×10⁻²⁸`` rather than
    ``5.17e-28``: the exponent is written with unicode superscripts so it reads
    correctly both as plain text and inside a typeset equation.

    Args:
        v: Any value; non-numeric input is returned as-is.
        p (int): Decimal places before trailing zeros are stripped.

    Returns:
        str: The formatted number, or ``"—"`` when it is not finite.
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if not math.isfinite(f):
        return "—"
    if f != 0 and (abs(f) < 1e-3 or abs(f) >= 1e5):
        mant, exp = f"{f:.2e}".split("e")
        return f"{mant}×10{str(int(exp)).translate(_SUPERSCRIPT)}"
    s = f"{f:.{p}f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-") else "0"


def _eq(title, formula, lines, result=None, note=""):
    """Build the *worked example* payload shown in the equation box.

    The box states the equation the current step is actually evaluating, then
    substitutes this frame's real numbers into it, so a reader can follow the
    arithmetic rather than trusting the animation.

    Maths is written as LaTeX and typeset by the frontend. ``formula`` and each
    row's left-hand side are pure LaTeX; the substitution and value columns are
    mixed text where maths is delimited by ``$…$``, so prose and numbers can sit
    on the same line.

    Args:
        title (str): Name of the quantity, e.g. ``"Inertia"``.
        formula (str): The general equation as LaTeX, without ``$`` delimiters.
        lines (list): Rows of ``[lhs_latex, substitution, value]`` — the
            substitution column carries the actual numbers for this step.
        result (list | None): Optional ``[label, value]`` highlighted at the end.
        note (str): One-line reminder of what the number means, as plain prose.

    Returns:
        dict: ``{'equation': {...}}``, ready to merge into a frame's ``extra``.
    """
    return {"equation": {
        "title": title, "formula": formula,
        "lines": [[str(c) for c in row] for row in lines],
        "result": None if result is None else [str(c) for c in result],
        "note": note}}


def _p(key, label, typ, default, mn=None, mx=None, step=None, options=None,
       help="", applies=True, only_if=None):
    """Build one parameter-spec dict for the algorithm panel schema.

    Args:
        key (str): Parameter name passed to the stepper.
        label (str): Control label in the panel.
        typ (str): ``'int'``, ``'float'``, ``'choice'`` or ``'bool'``.
        default: Starting value.
        mn, mx, step: Numeric range for slider types.
        options (list | None): Allowed values for ``'choice'``.
        help (str): Hint shown under the control.
        applies (bool): False when this illustration cannot honour the
            parameter, so the panel greys it out instead of letting it look
            active while doing nothing.
        only_if (dict | None): ``{'key': other, 'not': [values]}`` — greys the
            control out while the other parameter holds one of those values.

    Returns:
        dict: One JSON-friendly parameter spec.
    """
    return {"key": key, "label": label, "type": typ, "default": default,
            "min": mn, "max": mx, "step": step, "options": options,
            "help": help, "applies": bool(applies), "only_if": only_if}


_METRICS = ["euclidean", "manhattan", "cosine", "l1", "l2"]

ALGORITHMS = {
    "K-Means": {
        "blurb": "Partition into k blobs by repeatedly reassigning points and "
                 "moving centroids to the mean.",
        "params": [
            _p("k", "Clusters (k)", "int", 4, 2, 100, 1, help="Number of clusters"),
            _p("max_iter", "Max iterations", "int", 60, 5, 500, 5),
            _p("n_init", "N init", "int", 10, 1, 50, 1,
               help="Restarts from different seedings; the tightest one wins. "
                    "The animation follows a single seeding so you can watch "
                    "it, but this value shapes the result."),
        ],
    },
    "MiniBatch K-Means": {
        "blurb": "K-Means that updates centroids from small random batches — "
                 "faster, slightly noisier.",
        "params": [
            _p("k", "Clusters (k)", "int", 4, 2, 100, 1),
            _p("batch_size", "Batch size", "int", 256, 32, 4096, 32),
            _p("max_iter", "Max iterations", "int", 80, 5, 500, 5),
            _p("n_init", "N init", "int", 3, 1, 20, 1,
               help="Restarts from different seedings; the tightest one wins. "
                    "The animation follows a single seeding, but this value "
                    "shapes the result."),
        ],
    },
    "Gaussian Mixture": {
        "blurb": "Fit k Gaussians via Expectation-Maximisation; points are "
                 "assigned by posterior probability.",
        "params": [
            _p("k", "Components (k)", "int", 4, 2, 100, 1),
            _p("max_iter", "Max iterations", "int", 60, 5, 500, 5),
            _p("covariance_type", "Covariance", "choice", "full",
               options=["full", "tied", "diag", "spherical"]),
        ],
    },
    "Hierarchical": {
        "blurb": "Agglomerative merging: start with singletons and fuse the "
                 "closest pair until k clusters remain.",
        "params": [
            _p("k", "Clusters (k)", "int", 4, 2, 100, 1),
            _p("linkage", "Linkage", "choice", "ward",
               options=["ward", "average", "complete", "single"]),
            _p("metric", "Metric", "choice", "euclidean", options=_METRICS,
               only_if={"key": "linkage", "not": ["ward"]},
               help="Ward is defined only for Euclidean distances, so the "
                    "metric applies to the other linkages."),
        ],
    },
    "DBSCAN": {
        "blurb": "Grow clusters from dense cores; points in sparse regions are "
                 "labelled noise. No k needed.",
        "params": [
            _p("eps", "Neighbourhood radius (eps)", "float", 0.15, 0.02, 2.0, 0.01),
            _p("min_samples", "Min samples", "int", 6, 2, 100, 1),
            _p("metric", "Metric", "choice", "euclidean", options=_METRICS),
        ],
    },
    "Mean Shift": {
        "blurb": "Every point climbs the density gradient; points that reach "
                 "the same peak form a cluster.",
        "params": [
            _p("bandwidth", "Bandwidth", "float", 0.25, 0.05, 2.0, 0.01),
            _p("max_iter", "Max iterations", "int", 40, 5, 200, 5),
            _p("min_bin_freq", "Min bin frequency", "int", 1, 1, 50, 1),
            _p("auto_bw", "Auto bandwidth", "bool", False),
        ],
    },
    "OPTICS": {
        "blurb": "Order points by reachability distance, then carve clusters "
                 "from the valleys. Handles varying density.",
        "params": [
            _p("min_samples", "Min samples", "int", 6, 2, 100, 1),
            _p("xi", "Xi (valley steepness)", "float", 0.05, 0.01, 0.3, 0.01),
            _p("metric", "Metric", "choice", "euclidean", options=_METRICS),
            _p("cluster_method", "Cluster method", "choice", "xi",
               options=["xi", "dbscan"]),
        ],
    },
    "Birch": {
        "blurb": "Stream points into a compact CF-tree of sub-clusters, then "
                 "merge those into k clusters.",
        "params": [
            _p("threshold", "Radius threshold", "float", 0.15, 0.02, 2.0, 0.01),
            _p("k", "Final clusters (k)", "int", 4, 2, 100, 1),
            _p("branching_factor", "Branching factor", "int", 50, 10, 200, 5,
               help="Largest number of sub-clusters a node of the CF-tree may "
                    "hold before it splits."),
        ],
    },
    "Spectral": {
        "blurb": "Cluster the eigenvectors of a neighbour graph — finds "
                 "non-convex shapes K-Means can't.",
        "params": [
            _p("k", "Clusters (k)", "int", 4, 2, 100, 1),
            _p("n_neighbors", "Neighbours", "int", 10, 3, 100, 1,
               only_if={"key": "affinity", "not": ["rbf"]},
               help="Size of the neighbourhood graph. The RBF affinity weights "
                    "every pair instead, so it ignores this."),
            _p("affinity", "Affinity", "choice", "rbf",
               options=["rbf", "nearest_neighbors", "cosine"]),
        ],
    },
    "HDBSCAN": {
        "blurb": "Hierarchical DBSCAN: condense a mutual-reachability tree and "
                 "keep the most persistent clusters. (Approximate.)",
        "params": [
            _p("min_cluster_size", "Min cluster size", "int", 15, 3, 200, 1),
            _p("min_samples", "Min samples", "int", 5, 1, 100, 1),
            _p("metric", "Metric", "choice", "euclidean",
               options=["euclidean", "manhattan", "cosine", "l2"]),
        ],
    },
    "SOM": {
        "blurb": "Self-Organising Map: a neuron grid unfolds onto the data, "
                 "then neurons are grouped into k clusters.",
        "params": [
            _p("k", "Clusters (k)", "int", 4, 2, 100, 1),
            _p("som_rows", "Grid rows", "int", 6, 3, 20, 1),
            _p("som_cols", "Grid cols", "int", 6, 3, 20, 1),
            _p("som_iter", "Training steps", "int", 400, 100, 3000, 100),
            _p("som_sigma", "Neighbourhood sigma", "float", 1.5, 0.4, 5.0, 0.1),
            _p("som_lr", "Learning rate", "float", 0.5, 0.05, 1.0, 0.05),
        ],
    },
}


def algorithm_schema():
    """JSON-friendly description of every algorithm + params (drives the UI)."""
    return {name: {"blurb": spec["blurb"], "params": spec["params"]}
            for name, spec in ALGORITHMS.items()}


