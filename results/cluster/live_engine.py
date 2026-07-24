"""Pure-NumPy clustering engine with per-iteration *steppers* for Cluster Lab.

Every algorithm is exposed as a generator that ``yield``s **frames** describing
the state of the computation at each step, so the frontend can animate *how the
answer is built*, not just show the final labelling.

Frame schema (all fields JSON-serialisable)::

    {
        "iter":      int,                 # 0-based step index
        "note":      str,                 # human narration of this step
        "labels":    [int, ...],          # cluster id per point, -1 = noise
        "centroids": [[x, y], ...] | None,# moving cluster centres (view coords)
        "positions": [[x, y], ...] | None,# override point positions (mean-shift/SOM)
        "extra":     {...},               # algo-specific overlay data
        "metrics":   {...},               # cheap live metrics
        "converged": bool,
    }

Every stepper also fills ``extra['inset']`` — the payload for the small
*detail view* box the frontend draws beside the scatter, so you watch the
algorithm's own figure build up in step with the points::

    {"kind": "curve"|"bars"|"dendrogram"|"grid", "title": str,
     "subtitle": str, ...renderer-specific data...}

K-Means/MiniBatch show the inertia curve, GMM the log-likelihood and mixing
weights, DBSCAN the k-distance curve against eps, Mean Shift the collapsing
mode count, Hierarchical and HDBSCAN a live dendrogram / condensed tree,
OPTICS the reachability plot, Spectral the Laplacian spectrum and eigengap,
Birch its CF-leaf sizes, and SOM the U-matrix of the neuron grid.

Alongside it, ``extra['equation']`` carries the *worked example* — the equation
the current step is evaluating, with this frame's actual numbers substituted
into it::

    {"title": str, "formula": str,
     "lines": [[left, substitution, value], ...],
     "result": [label, value] | None, "note": str}

Design choices
--------------
* **Everything runs in a fixed 2-D display projection** (PCA of the
  preprocessed matrix). Clustering the points you can see is the whole point of
  a teaching tool — the moving centroids live in the same coordinates as the
  dots. The README explains how to cluster in full space for production.
* **No scikit-learn dependency.** Keeps the demo light and lets the steppers
  expose their own iterations. The real app already has sklearn; the README
  shows how to wrap ``_run_algo`` for production while keeping this streaming
  layer for the animated algorithms.

Depends only on NumPy.
"""

from __future__ import annotations

import math

import numpy as np


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


def calinski_harabasz(P, labels):
    """Calinski-Harabasz index (variance-ratio criterion; higher is better)."""
    lab = np.asarray(labels)
    uniq = np.unique(lab[lab >= 0])
    k, n = len(uniq), len(P)
    if k < 2 or n <= k:
        return float("nan")
    overall = P.mean(0)
    bg = wg = 0.0
    for c in uniq:
        pts = P[lab == c]
        ctr = pts.mean(0)
        bg += len(pts) * ((ctr - overall) ** 2).sum()
        wg += ((pts - ctr) ** 2).sum()
    if wg <= 0:
        return float("nan")
    return float((bg / (k - 1)) / (wg / (n - k)))


def evaluate_k(P, algo, params, k_min=2, k_max=10, seed=42):
    """Sweep k for ``algo`` and yield validity scores per k (for the score test).

    For each k the algorithm is run to completion on ``P`` and scored with
    silhouette, Calinski-Harabasz and Davies-Bouldin (all JSON-safe: NaN→None).
    Only meaningful for algorithms that take a ``k`` parameter.

    Yields:
        dict: ``{"k", "silhouette", "calinski", "davies_bouldin",
        "n_clusters", "done", "total"}``.
    """
    spec = ALGORITHMS.get(algo)
    if spec is None or not any(p["key"] == "k" for p in spec["params"]):
        return
    P = np.asarray(P, dtype=np.float64)
    ks = list(range(int(k_min), int(k_max) + 1))
    for i, k in enumerate(ks):
        rng = np.random.default_rng(seed)
        p = dict(params)
        p["k"] = k
        last = None
        for fr in spec["fn"](P, p, rng):
            last = fr
        labels = np.asarray(last["labels"]) if last else np.zeros(len(P), int)
        yield {
            "k": int(k),
            "silhouette": _finite_or_none(silhouette(P, labels, rng=rng)),
            "calinski": _finite_or_none(calinski_harabasz(P, labels)),
            "davies_bouldin": _finite_or_none(davies_bouldin(P, labels)),
            "n_clusters": int(len(np.unique(labels[labels >= 0]))),
            "done": i + 1, "total": len(ks),
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


def _pairwise(A, B=None, metric="euclidean"):
    """Pairwise distances between two point sets under the chosen metric.

    Args:
        A (ndarray): ``(n, d)`` points.
        B (ndarray | None): ``(m, d)`` points; defaults to ``A``.
        metric (str): ``'euclidean'``/``'l2'``, ``'manhattan'``/``'l1'`` or
            ``'cosine'``. Anything unrecognised falls back to Euclidean.

    Returns:
        ndarray: ``(n, m)`` distance matrix.
    """
    A = np.asarray(A, float)
    B = A if B is None else np.asarray(B, float)
    m = str(metric or "euclidean").lower()
    if m in ("manhattan", "l1", "cityblock"):
        return np.abs(A[:, None, :] - B[None, :, :]).sum(2)
    if m == "cosine":
        na = np.linalg.norm(A, axis=1, keepdims=True)
        nb = np.linalg.norm(B, axis=1, keepdims=True)
        na[na == 0] = 1e-12
        nb[nb == 0] = 1e-12
        cos = (A / na) @ (B / nb).T
        return np.clip(1.0 - cos, 0.0, 2.0)
    return np.sqrt(((A[:, None, :] - B[None, :, :]) ** 2).sum(2))


def _metric_label(metric):
    """Human name of a metric, for the notes and worked examples."""
    return {"l1": "manhattan", "cityblock": "manhattan",
            "l2": "euclidean"}.get(str(metric or "").lower(),
                                   str(metric or "euclidean").lower())


def _shape_covs(covs, cov_type, d, Nk=None):
    """Constrain fitted covariances to the requested family.

    Mirrors scikit-learn's ``covariance_type``: ``full`` leaves each component
    free, ``diag`` drops the off-diagonal terms, ``spherical`` replaces each
    with a single variance, and ``tied`` shares one covariance across all
    components.

    Args:
        covs (ndarray): ``(k, d, d)`` unconstrained covariances.
        cov_type (str): ``'full'``, ``'tied'``, ``'diag'`` or ``'spherical'``.
        d (int): Data dimensionality.
        Nk (ndarray | None): Per-component weights used when tying.

    Returns:
        ndarray: ``(k, d, d)`` covariances of the requested family.
    """
    covs = np.asarray(covs, float)
    eye = np.eye(d)
    if cov_type == "diag":
        return np.array([np.diag(np.diag(c)) + 1e-6 * eye for c in covs])
    if cov_type == "spherical":
        return np.array([(np.trace(c) / d) * eye + 1e-6 * eye for c in covs])
    if cov_type == "tied":
        w = np.ones(len(covs)) if Nk is None else np.asarray(Nk, float)
        shared = (covs * w[:, None, None]).sum(0) / max(w.sum(), 1e-12)
        return np.array([shared + 1e-6 * eye for _ in covs])
    return covs


def _affinity_note(affinity, nn):
    """Narration for the graph-building step of spectral clustering."""
    if affinity == "rbf":
        return ("Build a fully connected RBF affinity graph "
                "(gaussian weights on every pair)")
    if affinity == "cosine":
        return f"Build a {nn}-nearest-neighbour graph on cosine distances"
    return f"Build a {nn}-nearest-neighbour affinity graph"


def _kpp_init(P, k, rng):
    """k-means++ seeding."""
    n = len(P)
    idx = [int(rng.integers(n))]
    d2 = ((P - P[idx[0]]) ** 2).sum(1)
    for _ in range(1, k):
        probs = d2 / d2.sum() if d2.sum() > 0 else np.full(n, 1 / n)
        j = int(rng.choice(n, p=probs))
        idx.append(j)
        d2 = np.minimum(d2, ((P - P[j]) ** 2).sum(1))
    return P[idx].copy()


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


def _fr(it, note, labels, centroids=None, positions=None, extra=None,
        converged=False, P=None):
    """Assemble a frame with cheap metrics attached.

    Non-finite coordinates (e.g. an empty cluster's centroid) are replaced with
    0 so the frame is always valid JSON for the page.
    """
    lab = np.asarray(labels)
    cents = None if centroids is None else np.nan_to_num(
        np.asarray(centroids, float), nan=0.0, posinf=0.0, neginf=0.0)
    pos = None if positions is None else np.nan_to_num(
        np.asarray(positions, float), nan=0.0, posinf=0.0, neginf=0.0)
    frame = {
        "iter": int(it),
        "note": note,
        "labels": lab.astype(int).tolist(),
        "centroids": None if cents is None else cents.tolist(),
        "positions": None if pos is None else pos.tolist(),
        "extra": extra or {},
        "converged": bool(converged),
    }
    if P is not None:
        frame["metrics"] = cheap_metrics(P, lab, cents)
    return frame


def step_kmeans(P, params, rng, minibatch=False):
    """Stream Lloyd (or MiniBatch) K-Means iterations as frames."""
    k = int(params.get("k", 4))
    max_iter = int(params.get("max_iter", 60))
    batch = int(params.get("batch_size", 256))
    C = _kpp_init(P, k, rng)
    labels = np.zeros(len(P), dtype=int)
    hist, shifts = [], []

    probe = int(rng.integers(len(P)))

    def _ins(note=""):
        """Detail-view + worked-example payload for the current K-Means state."""
        x = P[probe]
        c = int(labels[probe]) if len(labels) else 0
        mu = C[min(c, len(C) - 1)]
        terms = " + ".join(f"({_n(x[j])}-{_n(mu[j])})^2" for j in range(len(x)))
        d2 = float(((x - mu) ** 2).sum())
        return {
            **_inset("curve", "Inertia", note or "within-cluster sum of "
                     "squares — every update must push it down",
                     series=[
                         {"y": list(hist), "label": "inertia",
                          "color": "accent"},
                         {"y": list(shifts), "label": "max centroid shift",
                          "color": "warn", "axis": "right"},
                     ], xlabel="update"),
            **_eq("Assignment & inertia",
                  r"c(i)=\arg\min_k \|x_i-\mu_k\|^2 \qquad "
                  r"J=\sum_i \|x_i-\mu_{c(i)}\|^2",
                  [[rf"\|x_{{{probe}}}-\mu_{{{c}}}\|^2", f"${terms}$", _n(d2, 4)],
                   [rf"c({probe})", f"nearest of ${len(C)}$ centroids", str(c)],
                   [r"J", f"summed over all ${len(P)}$ points",
                    _n(hist[-1] if hist else 0, 2)]],
                  result=["J", _n(hist[-1] if hist else 0, 2)],
                  note=f"point {probe} sits {_n(math.sqrt(d2), 3)} from its "
                       f"centroid; J adds that squared distance for every point")}
    hist.append(_inertia(P, labels, C))
    shifts.append(0.0)
    yield _fr(0, f"Seeded {k} centroids with k-means++", labels, C,
              extra=_ins("k-means++ picks spread-out seeds"), P=P)
    for it in range(1, max_iter + 1):
        D = ((P[:, None, :] - C[None, :, :]) ** 2).sum(2)
        labels = D.argmin(1)
        hist.append(_inertia(P, labels, C))
        shifts.append(shifts[-1])
        yield _fr(it, f"Iteration {it}: assign each point to its nearest centroid",
                  labels, C, extra=_ins("assignment step — inertia drops"), P=P)
        newC = C.copy()
        if minibatch:
            sel = rng.choice(len(P), min(batch, len(P)), replace=False)
            for kk in range(k):
                m = sel[labels[sel] == kk]
                if len(m):
                    newC[kk] += 0.5 * (P[m].mean(0) - newC[kk])
        else:
            for kk in range(k):
                m = labels == kk
                if m.any():
                    newC[kk] = P[m].mean(0)
        shift = float(np.sqrt(((newC - C) ** 2).sum(1)).max())
        C = newC
        hist.append(_inertia(P, labels, C))
        shifts.append(shift)
        yield _fr(it, f"Iteration {it}: move centroids to the mean of their points "
                  f"(max shift {shift:.3f})", labels, C,
                  extra=_ins("update step — centroids move to the mean"), P=P)
        if shift < 1e-4 and not minibatch:
            yield _fr(it, "Converged — centroids stopped moving", labels, C,
                      extra=_ins("flat curve = converged"), converged=True, P=P)
            return
    yield _fr(max_iter, "Reached iteration limit", labels, C,
              extra=_ins(), converged=True, P=P)


def step_gmm(P, params, rng):
    """Stream Gaussian-mixture EM iterations as frames."""
    k = int(params.get("k", 4))
    max_iter = int(params.get("max_iter", 60))
    cov_type = str(params.get("covariance_type", "full")).lower()
    n, d = P.shape
    means = _kpp_init(P, k, rng)
    covs = np.array([np.cov(P.T) + 1e-3 * np.eye(d) for _ in range(k)])
    covs = _shape_covs(covs, cov_type, d)
    weights = np.full(k, 1 / k)
    labels = np.zeros(n, dtype=int)
    ll_hist, w_hist = [], []

    probe = int(rng.integers(n))
    resp = [None]

    def _ins(note=""):
        """Detail-view + worked-example payload for the current EM state."""
        r = resp[0]
        if r is None:
            lines = [[r"r_{ij}", "waiting for the first E-step", "—"]]
            res = None
        else:
            num = r" + ".join(
                rf"{_n(weights[j], 3)}\cdot{_n(r[j] / max(weights[j], 1e-12), 3)}"
                for j in range(min(k, 3)))
            top = int(np.argmax(r))
            lines = [[rf"\pi_j\,\mathcal{{N}}(x_{{{probe}}}\mid\mu_j,\Sigma_j)",
                      "$" + num + (r" + \ldots" if k > 3 else "") + "$", ""],
                     [rf"r_{{{probe},{top}}}",
                      f"that term over the sum of all ${k}$ components",
                      _n(r[top], 4)],
                     [rf"\arg\max_j r_{{{probe},j}}",
                      "hard label used to colour the point", str(top)]]
            res = [f"r[{probe},{top}]", _n(r[top], 4)]
        return {
            **_inset("curve", "Log-likelihood",
                     note or f"{cov_type} covariances; EM can only increase "
                             f"the likelihood — the plateau is the fit",
                     series=[{"y": list(ll_hist), "label": "log-likelihood",
                              "color": "accent"}],
                     bars=[{"values": list(w_hist[-1]) if w_hist else [],
                            "label": "mixing weights π", "by_cluster": True}],
                     xlabel="EM step"),
            **_eq("Responsibility (E-step)",
                  r"r_{ij}=\frac{\pi_j\,\mathcal{N}(x_i\mid\mu_j,\Sigma_j)}"
                  r"{\sum_l \pi_l\,\mathcal{N}(x_i\mid\mu_l,\Sigma_l)}",
                  lines, result=res,
                  note="a soft membership in [0,1]; the M-step then refits each "
                       "component weighted by these numbers")}
    yield _fr(0, f"Initialised {k} Gaussian components ({cov_type} covariance)",
              labels, means,
              extra=_ins("k components, equal weights to start"), P=P)

    def _pdf(x, mu, cov):
        """Multivariate-normal density of each row under one component."""
        inv = np.linalg.inv(cov)
        det = max(np.linalg.det(cov), 1e-12)
        diff = x - mu
        expo = -0.5 * np.einsum("ni,ij,nj->n", diff, inv, diff)
        return np.exp(expo) / np.sqrt((2 * np.pi) ** d * det)

    prev_ll = -np.inf
    for it in range(1, max_iter + 1):
        R = np.stack([weights[j] * _pdf(P, means[j], covs[j]) for j in range(k)], 1)
        ll = np.log(R.sum(1) + 1e-300).sum()
        R = R / (R.sum(1, keepdims=True) + 1e-300)
        labels = R.argmax(1)
        ll_hist.append(_finite_or_none(ll))
        w_hist.append([float(x) for x in weights])
        resp[0] = [float(v) for v in R[probe]]
        yield _fr(it, f"E-step {it}: soft-assign points by posterior probability",
                  labels, means,
                  extra=_ins("E-step: responsibilities recomputed"), P=P)
        Nk = R.sum(0) + 1e-12
        means = (R.T @ P) / Nk[:, None]
        for j in range(k):
            diff = P - means[j]
            covs[j] = (R[:, j, None] * diff).T @ diff / Nk[j] + 1e-3 * np.eye(d)
        covs = _shape_covs(covs, cov_type, d, Nk)
        weights = Nk / n
        w_hist.append([float(x) for x in weights])
        yield _fr(it, f"M-step {it}: update component means, covariances, weights",
                  labels, means,
                  extra=_ins("M-step: means, covariances and weights refitted"),
                  P=P)
        if abs(ll - prev_ll) < 1e-4:
            yield _fr(it, "Converged — log-likelihood stabilised", labels, means,
                      extra=_ins("plateau reached — EM has converged"),
                      converged=True, P=P)
            return
        prev_ll = ll
    yield _fr(max_iter, "Reached iteration limit", labels, means,
              extra=_ins(), converged=True, P=P)


def step_dbscan(P, params, rng):
    """Stream DBSCAN density region-growing as frames.

    Runs on a bounded representative sample for O(n^2) safety, then labels every
    point by its nearest sample point so the whole dataset is coloured.
    """
    eps = float(params.get("eps", 0.15))
    min_samples = int(params.get("min_samples", 6))
    metric = _metric_label(params.get("metric", "euclidean"))
    idx = _subsample(P, 2000, rng)
    Q = P[idx]
    m = len(Q)
    nn = _nn_map(P, idx)
    D = _pairwise(Q, Q, metric)
    neigh = [np.where(D[i] <= eps)[0] for i in range(m)]
    is_core = np.array([len(neigh[i]) >= min_samples for i in range(m)])
    lab = np.full(m, -1, dtype=int)
    kd = np.sort(np.sort(D, axis=1)[:, min(min_samples, m - 1)])

    probe = int(rng.integers(m))

    def _ins(note=""):
        """Detail-view + worked-example payload for the current DBSCAN state."""
        sizes = [int((lab == c).sum()) for c in range(max(lab.max() + 1, 0))]
        cnt = int(len(neigh[probe]))
        kind = ("core" if is_core[probe]
                else ("border" if lab[probe] >= 0 else "noise"))
        return {
            **_inset(
                "curve", f"{min_samples}-distance curve",
                note or f"eps={eps:g} on {metric} distances: points above the "
                        f"line are too sparse to be cores — the elbow is the "
                        f"natural eps",
                series=[{"y": [float(x) for x in kd],
                         "label": f"distance to {min_samples}th neighbour",
                         "color": "accent"}],
                hline={"y": float(eps), "label": f"eps = {eps:g}", "color": "bad"},
                bars=[{"values": sizes, "label": "cluster sizes (sample)",
                       "by_cluster": True}],
                xlabel="points sorted by density"),
            **_eq("Core-point test",
                  r"N_\varepsilon(x)=\{\,y : d(x,y)\le\varepsilon\,\} \qquad "
                  r"x \in \mathrm{core} \iff |N_\varepsilon(x)|\ge \mathrm{minPts}",
                  [[rf"|N_\varepsilon(x_{{{probe}}})|",
                    f"neighbours within ${_n(eps)}$ of point ${probe}$", str(cnt)],
                   [r"|N_\varepsilon| \ge \mathrm{minPts}",
                    f"${cnt} \\ge {min_samples}$",
                    "yes" if cnt >= min_samples else "no"],
                   [rf"d_{{{min_samples}}}(x_{{{probe}}})",
                    f"distance to its ${min_samples}$th neighbour",
                    _n(float(np.sort(D[probe])[min(min_samples, m - 1)]))]],
                  result=[f"x[{probe}]", kind],
                  note="only core points start and extend clusters; the rest "
                       "join as borders or stay noise")}
    yield _fr(0, f"Found {int(is_core.sum())} core points (≥{min_samples} "
              f"neighbours within {eps}, {metric} distance)", lab[nn],
              extra=_ins(f"{int(is_core.sum())}/{m} sample points are cores"), P=P)
    cid = 0
    for i in range(m):
        if lab[i] != -1 or not is_core[i]:
            continue
        lab[i] = cid
        queue = list(neigh[i])
        qi = 0
        while qi < len(queue):
            j = queue[qi]; qi += 1
            if lab[j] == -1:
                lab[j] = cid
                if is_core[j]:
                    queue.extend(neigh[j].tolist())
            if qi % max(1, len(queue) // 6 + 1) == 0:
                yield _fr(cid, f"Expanding cluster {cid} "
                          f"({int((lab == cid).sum())} sample points)",
                          lab[nn], extra=_ins("region growing from core points"),
                          P=P)
        cid += 1
    yield _fr(cid, f"Done — {cid} clusters, {int((lab < 0).sum())} noise (sample)",
              lab[nn], extra=_ins(f"{int((lab < 0).sum())} points stayed noise"),
              converged=True, P=P)


def step_meanshift(P, params, rng):
    """Stream mean-shift density ascent as frames.

    The mode search runs on a bounded sample; every point is coloured by its
    nearest current mode so the full dataset is labelled at each step.
    """
    max_iter = int(params.get("max_iter", 40))
    min_bin_freq = max(int(params.get("min_bin_freq", 1)), 1)
    idx = _subsample(P, 1500, rng)
    Q = P[idx]
    if params.get("auto_bw"):
        sample = Q[rng.choice(len(Q), min(len(Q), 400), replace=False)]
        dd = _pairwise(sample, sample, "euclidean")
        bw = float(np.median(dd[dd > 0])) * 0.3 if (dd > 0).any() else 0.25
        bw = max(bw, 1e-3)
    else:
        bw = float(params.get("bandwidth", 0.25))
    pts = Q.copy()
    labels = np.zeros(len(P), dtype=int)
    nmodes, shifts = [], []

    probe = int(rng.integers(len(Q)))
    walk = [None]

    def _ins(note=""):
        """Detail-view + worked-example payload for the current Mean Shift state."""
        w = walk[0]
        if w is None:
            lines = [["m(x)", "waiting for the first shift", "—"]]
            res = None
        else:
            old, new, wsum, wmax = w
            lines = [[rf"K\!\left(\|x_{{{probe}}}-x_j\|/h\right)",
                      f"gaussian kernel, $h={_n(bw)}$; largest weight",
                      _n(wmax, 4)],
                     [r"m(x)",
                      f"weighted mean of ${len(Q)}$ sample points",
                      "(" + ", ".join(_n(v) for v in new) + ")"],
                     [r"\|m(x)-x\|", "how far this walker just moved",
                      _n(float(np.sqrt(((new - old) ** 2).sum())), 4)]]
            res = ["sum of kernel weights", _n(wsum, 3)]
        return {
            **_inset("curve", "Modes & drift",
                     note or f"bandwidth {bw:g}: walkers merge onto density "
                             f"peaks, so the mode count collapses",
                     series=[{"y": list(nmodes), "label": "modes found",
                              "color": "accent"},
                             {"y": list(shifts), "label": "max shift",
                              "color": "warn", "axis": "right"}],
                     xlabel="shift step"),
            **_eq("Mean-shift step",
                  r"m(x)=\frac{\sum_j K\!\left(\|x-x_j\|/h\right)x_j}"
                  r"{\sum_j K\!\left(\|x-x_j\|/h\right)}",
                  lines, result=res,
                  note="each walker moves to the kernel-weighted mean of its "
                       "neighbourhood — uphill in density, every step")}
    yield _fr(0, f"Points climb the density gradient (bandwidth {_n(bw)}"
              f"{', chosen automatically' if params.get('auto_bw') else ''})",
              labels,
              extra=_ins("every sample point starts as its own walker"), P=P)
    modes = Q[:1]
    for it in range(1, max_iter + 1):
        d2 = ((pts[:, None, :] - Q[None, :, :]) ** 2).sum(2)
        W = np.exp(-d2 / (2 * bw ** 2))
        newpts = (W @ Q) / W.sum(1, keepdims=True)
        shift = np.sqrt(((newpts - pts) ** 2).sum(1)).max()
        walk[0] = (pts[probe].copy(), newpts[probe].copy(),
                   float(W[probe].sum()), float(W[probe].max()))
        pts = newpts
        modes, _ = _merge_modes(pts, bw * 0.5, min_bin_freq)
        labels = ((P[:, None, :] - modes[None, :, :]) ** 2).sum(2).argmin(1)
        conv = shift < 1e-3
        nmodes.append(int(len(modes)))
        shifts.append(float(shift))
        if it % 2 == 0 or conv:
            yield _fr(it, f"Shift {it}: {len(modes)} modes "
                      f"(max move {shift:.3f})", labels, centroids=modes,
                      extra=_ins("walkers still climbing" if not conv
                                 else "drift ≈ 0 — peaks reached"),
                      converged=conv, P=P)
        if conv:
            return
    labels = ((P[:, None, :] - modes[None, :, :]) ** 2).sum(2).argmin(1)
    yield _fr(max_iter, f"Stopped at {len(modes)} modes", labels,
              centroids=modes, extra=_ins(), converged=True, P=P)


def _merge_modes(pts, tol, min_bin_freq=1):
    """Group collapsed points into modes by snapping to a coarse grid.

    Args:
        pts (ndarray): Current walker positions.
        tol (float): Grid spacing used to decide which walkers have met.
        min_bin_freq (int): Discard modes supported by fewer walkers than this,
            mirroring scikit-learn's seed-binning parameter. At least one mode
            is always kept.

    Returns:
        tuple: ``(modes, labels)`` — the mode positions and each walker's mode.
    """
    if tol <= 0:
        tol = 1e-3
    keys = np.round(pts / tol).astype(np.int64)
    uniq, labels = np.unique(keys, axis=0, return_inverse=True)
    counts = np.bincount(labels, minlength=len(uniq))
    keep = np.where(counts >= max(int(min_bin_freq), 1))[0]
    if not len(keep):
        keep = np.array([int(np.argmax(counts))])
    modes = np.array([pts[labels == m].mean(0) for m in keep])
    remap = ((pts[:, None, :] - modes[None, :, :]) ** 2).sum(2).argmin(1)
    return modes, remap.astype(int)


def step_hierarchical(P, params, rng):
    """Stream agglomerative merges as frames."""
    k = int(params.get("k", 4))
    linkage = params.get("linkage", "ward")
    metric = "euclidean" if linkage == "ward" else _metric_label(
        params.get("metric", "euclidean"))
    idx = _subsample(P, 170, rng)
    Q = P[idx]
    n = len(Q)
    clusters = {i: [i] for i in range(n)}
    centroids = {i: Q[i].copy() for i in range(n)}
    merges = []

    FORMULAS = {
        "ward":     r"d(A,B)=\frac{n_A\,n_B}{n_A+n_B}\,\|c_A-c_B\|^2",
        "single":   r"d(A,B)=\min_{a\in A,\;b\in B}\|a-b\|",
        "complete": r"d(A,B)=\max_{a\in A,\;b\in B}\|a-b\|",
        "average":  r"d(A,B)=\frac{1}{n_A n_B}"
                    r"\sum_{a\in A}\sum_{b\in B}\|a-b\|",
    }
    last = [None]

    def _ins(active, note=""):
        """Detail-view + worked-example payload for the current merge state."""
        if last[0] is None:
            lines = [["d(A,B)", "waiting for the first merge", "—"]]
            res = None
        else:
            na, nb, dist, size = last[0]
            if linkage == "ward":
                sub = (rf"$\frac{{{na}\cdot{nb}}}{{{na + nb}}}"
                       rf"\,\|c_A-c_B\|^2 = {_n(na * nb / (na + nb), 3)}"
                       rf"\,\|c_A-c_B\|^2$")
            else:
                sub = (f"{linkage} distance over "
                       f"${na}\\times{nb}={na * nb}$ point pairs")
            lines = [[r"|A|,\;|B|", "sizes of the two groups just fused",
                      f"{na}, {nb}"],
                     [r"d(A,B)", sub, _n(dist, 4)],
                     [r"k_{\mathrm{now}}",
                      f"${n}$ leaves minus ${len(merges)}$ merges",
                      str(len(active))]]
            res = ["merge height", _n(dist, 4)]
        return {
            **_inset(
                "dendrogram", "Dendrogram",
                note or f"{linkage} linkage on {metric} distances — height is "
                        f"where two groups fuse; cutting at k={k} gives the "
                        f"colours",
                merges=[list(m) for m in merges], n_leaves=n,
                leaf_labels=[int(x) for x in _sub_labels(clusters, n, active)],
                leaf_order=[int(i) for i in idx],
                cut=len(active), target=k, ylabel="linkage distance"),
            **_eq(f"Linkage distance ({linkage}, {metric})",
                  FORMULAS.get(linkage, FORMULAS["ward"]), lines, result=res,
                  note="the smallest d(A,B) over all remaining pairs is the "
                       "merge that happens next, and its value is the bar height")}
    yield _fr(0, f"Start with {n} representative singletons; merge the closest "
              f"pair each step ({linkage} linkage, {metric} distance)", _expand(P, idx, _sub_labels(clusters, n)),
              extra=_ins(list(range(n)), "every point is its own leaf"), P=P)
    step = 0
    active = list(range(n))
    while len(active) > 1:
        best, bpair = np.inf, None
        for ai in range(len(active)):
            for bi in range(ai + 1, len(active)):
                a, b = active[ai], active[bi]
                d = _linkage_dist(Q, clusters[a], clusters[b], centroids[a],
                                  centroids[b], linkage, metric)
                if d < best:
                    best, bpair = d, (a, b)
        a, b = bpair
        new = max(clusters) + 1
        clusters[new] = clusters[a] + clusters[b]
        centroids[new] = Q[clusters[new]].mean(0)
        merges.append([int(a), int(b), float(best), len(clusters[new])])
        last[0] = (len(clusters[a]), len(clusters[b]), float(best),
                   len(clusters[new]))
        active.remove(a); active.remove(b); active.append(new)
        del clusters[a]; del clusters[b]
        step += 1
        if len(active) <= 12 or step % 6 == 0:
            yield _fr(step, f"Merge → {len(active)} clusters remain "
                      f"(link dist {best:.3f})",
                      _expand(P, idx, _sub_labels(clusters, n, active)),
                      extra=_ins(active, f"last fusion at height {best:.3f}"),
                      P=P)
        if len(active) == k:
            lab = _expand(P, idx, _sub_labels(clusters, n, active))
            yield _fr(step, f"Reached target of {k} clusters", lab,
                      extra=_ins(active, f"tree cut at k={k}"),
                      converged=True, P=P)
            return
    yield _fr(step, "Merged to a single cluster",
              _expand(P, idx, _sub_labels(clusters, n, active)),
              extra=_ins(active, "everything fused into one root"),
              converged=True, P=P)


def _linkage_dist(Q, ca, cb, cea, ceb, linkage, metric="euclidean"):
    """Linkage distance between two clusters under the chosen metric.

    Ward is defined only for squared Euclidean distances between centroids, so
    it ignores ``metric`` — the same restriction the main clustering dialog
    enforces by disabling the metric picker when Ward is selected.

    Args:
        Q (ndarray): The representative points.
        ca (list[int]): Member indices of the first cluster.
        cb (list[int]): Member indices of the second cluster.
        cea (ndarray): Centroid of the first cluster.
        ceb (ndarray): Centroid of the second cluster.
        linkage (str): ``'ward'``, ``'single'``, ``'complete'`` or ``'average'``.
        metric (str): Point-to-point distance for the non-Ward linkages.

    Returns:
        float: The distance at which these two clusters would fuse.
    """
    if linkage == "ward":
        na, nb = len(ca), len(cb)
        return (na * nb / (na + nb)) * ((cea - ceb) ** 2).sum()
    D = _pairwise(Q[ca], Q[cb], metric)
    if linkage == "single":
        return D.min()
    if linkage == "complete":
        return D.max()
    return D.mean()


def _subsample(P, max_points, rng):
    """Return indices of a representative subset (all points if small enough)."""
    if len(P) <= max_points:
        return np.arange(len(P))
    return np.sort(rng.choice(len(P), max_points, replace=False))


def _nn_map(P, idx):
    """Index of the nearest representative (row of ``P[idx]``) for every point."""
    Q = P[idx]
    return ((P[:, None, :] - Q[None, :, :]) ** 2).sum(2).argmin(1)


def _expand(P, idx, lab_sub):
    """Assign every point the label of its nearest representative."""
    return np.asarray(lab_sub)[_nn_map(P, idx)]


def _sub_labels(clusters, n, active=None):
    """Contiguous 0..K-1 labels over the n representatives from a cluster dict."""
    lab = np.zeros(n, dtype=int)
    keys = active if active is not None else list(clusters.keys())
    for cl, cid in enumerate(keys):
        for m in clusters[cid]:
            lab[m] = cl
    return lab


def step_som(P, params, rng):
    """Stream self-organising-map training as frames."""
    rows = int(params.get("som_rows", 6))
    cols = int(params.get("som_cols", 6))
    k = int(params.get("k", 4))
    n_iter = int(params.get("som_iter", 400))
    sigma0 = float(params.get("som_sigma", 1.5))
    lr0 = float(params.get("som_lr", 0.5))
    n_neurons = rows * cols
    W = P[rng.choice(len(P), n_neurons, replace=False)].copy()
    grid = np.array([[r, c] for r in range(rows) for c in range(cols)], float)
    labels = np.zeros(len(P), dtype=int)

    def _edges():
        """Return the neuron-grid adjacency edges."""
        e = []
        for r in range(rows):
            for c in range(cols):
                i = r * cols + c
                if c + 1 < cols:
                    e.append([i, i + 1])
                if r + 1 < rows:
                    e.append([i, i + cols])
        return e
    edges = _edges()

    def _umatrix():
        """Mean data-space distance from each neuron to its grid neighbours."""
        u = np.zeros(n_neurons)
        cnt = np.zeros(n_neurons)
        for a, b in edges:
            d = float(np.sqrt(((W[a] - W[b]) ** 2).sum()))
            u[a] += d
            u[b] += d
            cnt[a] += 1
            cnt[b] += 1
        cnt[cnt == 0] = 1
        return [float(x) for x in (u / cnt)]

    upd = [None]

    def _ins(neuron_lab=None, hits=None, note=""):
        """Detail-view + worked-example payload for the current SOM state."""
        if upd[0] is None:
            lines = [["w_i ← …", "waiting for the first training sample", "—"]]
            res = None
        else:
            bmu, lr, sigma, gd, hb, move = upd[0]
            lines = [[r"b", "neuron closest to the drawn sample $x$",
                      f"#{bmu} (row {bmu // cols}, col {bmu % cols})"],
                     [r"h(i,b)",
                      rf"$\exp\!\left(-\frac{{{_n(gd)}}}"
                      rf"{{2\cdot{_n(sigma)}^2}}\right)$ "
                      f"for a neighbour one cell away", _n(hb, 4)],
                     [r"\alpha\,h\,(x-w_i)",
                      rf"$\alpha={_n(lr, 3)}$, so that neighbour moves",
                      _n(move, 4)]]
            res = ["learning rate now", _n(lr, 3)]
        return {"som_nodes": W.tolist(), "som_edges": edges,
                **_inset("grid", "U-matrix",
                         note or "each cell is a neuron in map space; dark "
                                 "ridges are gaps between clusters",
                         rows=rows, cols=cols, values=_umatrix(),
                         cell_labels=(None if neuron_lab is None
                                      else [int(x) for x in neuron_lab]),
                         hits=(None if hits is None
                               else [int(x) for x in hits])),
                **_eq("Neuron update",
                      r"w_i \leftarrow w_i+\alpha(t)\,h(i,b)\,(x-w_i)"
                      r"\qquad h(i,b)=\exp\!\left("
                      r"-\frac{\|g_i-g_b\|^2}{2\sigma(t)^2}\right)",
                      lines, result=res,
                      note="the winner moves most, its grid neighbours follow — "
                           "that pull is what keeps the map continuous")}
    yield _fr(0, f"Drape a {rows}×{cols} neuron grid over the data",
              labels, extra=_ins(note="grid starts random — no structure yet"),
              P=P)
    snap = max(n_iter // 30, 1)
    neuron_lab, hits = None, None
    for it in range(1, n_iter + 1):
        x = P[rng.integers(len(P))]
        bmu = np.argmin(((W - x) ** 2).sum(1))
        lr = lr0 * (1 - it / n_iter)
        sigma = max(sigma0 * (1 - it / n_iter), 0.4)
        gd = ((grid - grid[bmu]) ** 2).sum(1)
        h = np.exp(-gd / (2 * sigma ** 2))
        nb = int(np.argsort(gd)[1]) if n_neurons > 1 else int(bmu)
        upd[0] = (int(bmu), float(lr), float(sigma), float(gd[nb]),
                  float(h[nb]),
                  float(lr * h[nb] * np.sqrt(((x - W[nb]) ** 2).sum())))
        W += lr * h[:, None] * (x - W)
        if it % snap == 0 or it == n_iter:
            neuron_lab = _kmeans_labels(W, k, rng)
            bmus = np.argmin(((P[:, None, :] - W[None, :, :]) ** 2).sum(2), 1)
            labels = neuron_lab[bmus]
            hits = np.bincount(bmus, minlength=n_neurons)
            yield _fr(it, f"Training {it}/{n_iter}: grid unfolds onto the data "
                      f"(lr {lr:.2f})", labels,
                      extra=_ins(neuron_lab, hits,
                                 "ridges sharpen as the grid unfolds"), P=P)
    yield _fr(n_iter, f"SOM trained; neurons grouped into {k} clusters",
              labels, extra=_ins(neuron_lab, hits,
                                 f"neurons grouped into {k} clusters"),
              converged=True, P=P)


def _kmeans_labels(X, k, rng, iters=30):
    """Quick K-Means labelling used to group SOM neurons."""
    k = min(k, len(X))
    C = _kpp_init(X, k, rng)
    lab = np.zeros(len(X), dtype=int)
    for _ in range(iters):
        lab = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2).argmin(1)
        for kk in range(k):
            if (lab == kk).any():
                C[kk] = X[lab == kk].mean(0)
    return lab


def step_spectral(P, params, rng):
    """Stream spectral clustering (embedding then K-Means) as frames."""
    k = int(params.get("k", 4))
    nn = int(params.get("n_neighbors", 10))
    affinity = str(params.get("affinity", "rbf")).lower()
    idx = _subsample(P, 400, rng)
    Q = P[idx]
    n = len(Q)
    D = _pairwise(Q, Q, "cosine" if affinity == "cosine" else "euclidean")
    spectrum = []

    def _ins(note=""):
        """Detail-view + worked-example payload for the current spectral state."""
        vals_ok = [v for v in spectrum if v is not None]
        if len(vals_ok) > k:
            gap = vals_ok[k] - vals_ok[k - 1]
            lines = [[rf"\lambda_{{{k}}}",
                      f"the ${k}$th smallest eigenvalue of $L$",
                      _n(vals_ok[k - 1], 4)],
                     [rf"\lambda_{{{k + 1}}}", "the next one up",
                      _n(vals_ok[k], 4)],
                     [rf"\mathrm{{gap}}_{{{k}}}",
                      f"${_n(vals_ok[k], 4)}-{_n(vals_ok[k - 1], 4)}$",
                      _n(gap, 4)]]
            res = [f"eigengap at k = {k}", _n(gap, 4)]
        else:
            lines = [[r"\lambda", "waiting for the eigendecomposition", "—"]]
            res = None
        return {
            **_inset(
                "bars", "Laplacian spectrum",
                note or "the first big jump (eigengap) is how many clusters the "
                        "graph really contains",
                values=list(spectrum), highlight=k - 1,
                vline={"x": k - 0.5, "label": f"cut at k={k}", "color": "bad"},
                xlabel="eigenvalue index", ylabel="λ"),
            **_eq("Normalised Laplacian & eigengap",
                  r"L=I-D^{-1/2}AD^{-1/2} \qquad "
                  r"\mathrm{gap}_k=\lambda_{k+1}-\lambda_k",
                  lines, result=res,
                  note="a large gap after k means the graph splits cleanly into "
                       "k pieces — that is the k worth choosing")}
    yield _fr(0, _affinity_note(affinity, nn), np.zeros(len(P), dtype=int),
              extra=_ins("graph built — spectrum comes next"), P=P)
    if affinity == "rbf":
        scale = np.median(D[D > 0]) if (D > 0).any() else 1.0
        A = np.exp(-(D ** 2) / (2 * max(scale, 1e-12) ** 2))
        np.fill_diagonal(A, 0.0)
    else:
        A = np.zeros((n, n))
        for i in range(n):
            order = np.argsort(D[i])[1:nn + 1]
            A[i, order] = 1
        A = np.maximum(A, A.T)
    deg = A.sum(1)
    deg[deg == 0] = 1
    L = np.eye(n) - (A / np.sqrt(deg)[:, None]) / np.sqrt(deg)[None, :]
    vals, vecs = np.linalg.eigh(L)
    spectrum = [_finite_or_none(v) for v in vals[:max(k + 6, 12)]]
    yield _fr(1, "Compute the graph Laplacian and its lowest eigenvectors",
              np.zeros(len(P), dtype=int),
              extra=_ins("λ₁≈0 always; count the near-zero ones"), P=P)
    emb = vecs[:, :k]
    emb = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-12)
    C = _kpp_init(emb, k, rng)
    lab_sub = np.zeros(n, dtype=int)
    for it in range(1, 25):
        lab_sub = ((emb[:, None, :] - C[None, :, :]) ** 2).sum(2).argmin(1)
        yield _fr(1 + it, f"Cluster points in spectral space (step {it})",
                  _expand(P, idx, lab_sub),
                  extra=_ins("K-Means now runs on the first k eigenvectors"),
                  P=P)
        newC = C.copy()
        for kk in range(k):
            if (lab_sub == kk).any():
                newC[kk] = emb[lab_sub == kk].mean(0)
        if np.sqrt(((newC - C) ** 2).sum(1)).max() < 1e-5:
            C = newC
            break
        C = newC
    yield _fr(30, f"Spectral clustering complete ({k} clusters)",
              _expand(P, idx, lab_sub), extra=_ins(), converged=True, P=P)


def step_birch(P, params, rng):
    """Stream Birch CF-tree insertion and the final merge as frames."""
    thr = float(params.get("threshold", 0.15))
    k = int(params.get("k", 4))
    subs, sub_n = [], []
    labels = np.full(len(P), -1, dtype=int)
    order = rng.permutation(len(P))
    growth = []

    absorb = [None]

    def _ins(note=""):
        """Detail-view + worked-example payload for the current CF-tree state."""
        top = sorted(sub_n, reverse=True)[:40]
        if absorb[0] is None:
            lines = [[r"\|x-c_j\|", "waiting for the first point", "—"]]
            res = None
        else:
            dist, j, cnt, joined = absorb[0]
            lines = [[r"j=\arg\min_j \|x-c_j\|",
                      f"closest of ${len(subs)}$ leaf centroids", f"#{j}"],
                     [r"\|x-c_j\| \le T",
                      f"${_n(dist, 4)} \\le {_n(thr)}$",
                      "yes" if joined else "no"],
                     [r"c_j \leftarrow \frac{n_j c_j + x}{n_j+1}",
                      f"$n_j={cnt} \\to {cnt + 1}$" if joined else
                      "threshold exceeded, so a new leaf opens",
                      f"{len(subs)} leaves"]]
            res = ["CF leaves", str(len(subs))]
        return {
            **_inset(
                "bars", "CF-tree leaves",
                note or f"each bar is one sub-cluster summary (radius ≤ {thr:g}); "
                        f"a new point either joins one or opens a new leaf",
                values=[int(x) for x in top],
                series=[{"y": list(growth), "label": "leaves", "color": "warn"}],
                xlabel="sub-cluster (largest first)", ylabel="points"),
            **_eq("CF absorption test",
                  r"j=\arg\min_j \|x-c_j\| \qquad "
                  r"\|x-c_j\|\le T \;\Rightarrow\; "
                  r"c_j \leftarrow \frac{n_j c_j + x}{n_j+1}",
                  lines, result=res,
                  note="one pass, one point at a time — the tree only ever "
                       "keeps these running summaries, never the raw points")}
    yield _fr(0, f"Stream points into a CF-tree (radius threshold {thr})", labels,
              extra=_ins("tree is empty — points arrive one at a time"), P=P)
    snap = max(len(P) // 25, 1)
    for step, i in enumerate(order, 1):
        if not subs:
            subs.append(P[i].copy()); sub_n.append(1)
            absorb[0] = (0.0, 0, 0, False)
        else:
            d = np.sqrt(((np.array(subs) - P[i]) ** 2).sum(1))
            j = int(d.argmin())
            absorb[0] = (float(d[j]), j, int(sub_n[j]), bool(d[j] <= thr))
            if d[j] <= thr:
                subs[j] = (subs[j] * sub_n[j] + P[i]) / (sub_n[j] + 1)
                sub_n[j] += 1
            else:
                subs.append(P[i].copy()); sub_n.append(1)
        if step % snap == 0:
            cents = np.array(subs)
            lab = ((P[:, None, :] - cents[None, :, :]) ** 2).sum(2).argmin(1)
            growth.append(int(len(subs)))
            yield _fr(step, f"{len(subs)} sub-clusters after {step} points",
                      lab, centroids=cents,
                      extra=_ins(f"{step} points absorbed so far"), P=P)
    cents = np.array(subs)
    sub_lab = _kmeans_labels(cents, min(k, len(cents)), rng)
    nearest = ((P[:, None, :] - cents[None, :, :]) ** 2).sum(2).argmin(1)
    labels = sub_lab[nearest]
    final_cents = np.array([P[labels == c].mean(0)
                            for c in range(sub_lab.max() + 1)
                            if (labels == c).any()])
    yield _fr(len(P), f"Merge sub-clusters into {len(final_cents)} final clusters",
              labels, centroids=final_cents,
              extra=_ins(f"{len(subs)} leaves condensed into "
                         f"{len(final_cents)} clusters"),
              converged=True, P=P)


def step_optics(P, params, rng):
    """Stream OPTICS reachability ordering and cluster extraction as frames."""
    min_samples = int(params.get("min_samples", 6))
    xi = float(params.get("xi", 0.05))
    metric = _metric_label(params.get("metric", "euclidean"))
    cluster_method = str(params.get("cluster_method", "xi")).lower()
    idx = _subsample(P, 350, rng)
    Q = P[idx]
    n = len(Q)
    D = _pairwise(Q, Q, metric)
    core_d = np.sort(D, axis=1)[:, min(min_samples, n - 1)]
    reach = np.full(n, np.inf)
    processed = np.zeros(n, bool)
    order = []
    r, lab_sub, thr = np.zeros(0), np.full(n, -1, dtype=int), 0.0
    cursor = [0]

    def _ins(note=""):
        """Detail-view + worked-example payload for the current OPTICS state."""
        pos = min(cursor[0], len(r) - 1) if len(r) else -1
        if pos >= 0:
            o = int(order[pos]) if len(order) == n else pos
            lines = [[rf"\mathrm{{core}}_{{{min_samples}}}(o)",
                      f"distance from point ${o}$ to its "
                      f"${min_samples}$th neighbour",
                      _n(float(core_d[o]), 4)],
                     [r"\mathrm{reach}(p)",
                      "the larger of the two, and the bar drawn here",
                      _n(float(r[pos]), 4)],
                     [r"\xi\;\mathrm{cut}",
                      f"below ${_n(float(thr), 4)}$ we are inside a valley",
                      "in" if r[pos] <= thr else "out"]]
            res = ["reachability", _n(float(r[pos]), 4)]
        else:
            lines = [[r"\mathrm{reach}(p)", "walking the order…", "—"]]
            res = None
        return {
            **_inset(
                "bars", "Reachability plot",
                note or (f"valleys are clusters, spikes are the gaps between "
                         f"them — cut here by the "
                         f"{'flat dbscan threshold' if cluster_method == 'dbscan' else 'xi steepness rule'}"
                         f" on {metric} distances"),
                values=[_finite_or_none(v) for v in r],
                bar_clusters=[int(lab_sub[i]) for i in order] if len(order) == n
                else None,
                hline={"y": float(thr), "label": "xi cut", "color": "bad"},
                cursor=cursor[0], xlabel="reachability order", ylabel="distance"),
            **_eq("Reachability distance",
                  r"\mathrm{reach}_k(p \mid o)="
                  r"\max\{\,\mathrm{core}_k(o),\; d(o,p)\,\}",
                  lines, result=res,
                  note="dense points get small reachability, so clusters appear "
                       "as valleys in this ordering regardless of their density")}
    yield _fr(0, "Order points by reachability distance (density-connected walk)",
              np.full(len(P), -1, dtype=int),
              extra=_ins("walking the density-connected order…"), P=P)
    for _ in range(n):
        unproc = np.where(~processed)[0]
        cur = unproc[np.argmin(reach[unproc])] if order else unproc[0]
        processed[cur] = True
        order.append(cur)
        upd = ~processed
        nd = np.maximum(core_d[cur], D[cur])
        improve = upd & (nd < reach)
        reach[improve] = nd[improve]
    order = np.array(order)
    r = reach[order]
    r[np.isinf(r)] = np.nanmax(r[~np.isinf(r)]) * 1.1 if np.isfinite(r).any() else 1.0
    lab_sub = np.full(n, -1, dtype=int)
    cid, i = 0, 0
    thr = (float(np.median(core_d)) if cluster_method == "dbscan"
           else float(np.percentile(r, 100 * (1 - xi * 6))))
    started = False
    for pos in range(n):
        if r[pos] <= thr:
            if not started:
                cid += 0 if not started and pos == 0 else 1
                started = True
            lab_sub[order[pos]] = cid
        else:
            started = False
        if pos % max(1, n // 20) == 0:
            cursor[0] = int(pos)
            yield _fr(pos, f"Walking reachability order ({pos}/{n})",
                      _expand(P, idx, lab_sub),
                      extra=_ins("scanning left to right for valleys"), P=P)
    cursor[0] = n
    yield _fr(n, f"Extracted {len(np.unique(lab_sub[lab_sub >= 0]))} clusters "
              f"from reachability valleys", _expand(P, idx, lab_sub),
              extra=_ins("each valley below the cut became a cluster"),
              converged=True, P=P)


def step_hdbscan(P, params, rng):
    """Approximate HDBSCAN: mutual-reachability single-linkage + size cut."""
    min_cluster = int(params.get("min_cluster_size", 15))
    metric = _metric_label(params.get("metric", "euclidean"))
    min_samples = int(params.get("min_samples", 5))
    idx = _subsample(P, 150, rng)
    Q = P[idx]
    n = len(Q)
    D = _pairwise(Q, Q, metric)
    kk = min(max(min_samples, 1), n - 1)
    core = np.sort(D, axis=1)[:, kk]
    mr = np.maximum(np.maximum(core[:, None], core[None, :]), D)
    clusters = {i: [i] for i in range(n)}
    active = list(range(n))
    merges = []

    last = [None]

    def _ins(note=""):
        """Detail-view + worked-example payload for the current HDBSCAN state."""
        lab = np.full(n, -1, dtype=int)
        big_now = [c for c in active if len(clusters[c]) >= min_cluster]
        for ci, c in enumerate(big_now):
            lab[clusters[c]] = ci
        if last[0] is None:
            lines = [[r"d_{\mathrm{mreach}}(a,b)",
                      "waiting for the first fusion", "—"]]
            res = None
        else:
            dist, na, nb, ca, cb = last[0]
            lines = [[rf"\mathrm{{core}}_{{{min_cluster}}}(a),\;"
                      rf"\mathrm{{core}}_{{{min_cluster}}}(b)",
                      "density-adjusted radii of the two closest points",
                      f"{_n(ca, 4)}, {_n(cb, 4)}"],
                     [r"d_{\mathrm{mreach}}(a,b)",
                      rf"$\max\{{{_n(ca, 4)},\;{_n(cb, 4)},\;d(a,b)\}}$",
                      _n(dist, 4)],
                     [r"|A\cup B| \ge m_{\min}",
                      f"${na + nb} \\ge {min_cluster}$",
                      "survives" if na + nb >= min_cluster else "still a twig"]]
            res = ["fusion height", _n(dist, 4)]
        return {
            **_inset(
                "dendrogram", "Condensed tree",
                note or f"branches holding ≥{min_cluster} points survive as "
                        f"clusters; thin twigs fall out as noise",
                merges=[list(m) for m in merges], n_leaves=n,
                leaf_labels=[int(x) for x in lab], cut=len(active),
                min_size=min_cluster, ylabel="mutual reachability"),
            **_eq("Mutual reachability",
                  r"d_{\mathrm{mreach}}(a,b)=\max\{\,\mathrm{core}_k(a),"
                  r"\;\mathrm{core}_k(b),\;d(a,b)\,\}",
                  lines, result=res,
                  note="inflating distances in sparse regions is what lets one "
                       "tree hold clusters of very different densities")}
    yield _fr(0, f"Build mutual-reachability graph on {metric} distances "
              f"(min_cluster_size {min_cluster}, min_samples {min_samples})",
              np.full(len(P), -1, dtype=int),
              extra=_ins("distances inflated by local density"), P=P)
    step = 0
    while len(active) > 1:
        best, bpair = np.inf, None
        for ai in range(len(active)):
            for bi in range(ai + 1, len(active)):
                a, b = active[ai], active[bi]
                d = mr[np.ix_(clusters[a], clusters[b])].min()
                if d < best:
                    best, bpair = d, (a, b)
        a, b = bpair
        sub = mr[np.ix_(clusters[a], clusters[b])]
        pi, pj = np.unravel_index(int(np.argmin(sub)), sub.shape)
        pa, pb = clusters[a][int(pi)], clusters[b][int(pj)]
        na, nb = len(clusters[a]), len(clusters[b])
        last[0] = (float(best), na, nb, float(core[pa]), float(core[pb]))
        new = max(clusters) + 1
        clusters[new] = clusters[a] + clusters[b]
        active.remove(a); active.remove(b); active.append(new)
        del clusters[a]; del clusters[b]
        merges.append([int(a), int(b), float(best), int(len(clusters[new]))])
        step += 1
        big = [c for c in active if len(clusters[c]) >= min_cluster]
        if len(big) >= 2 and (step % 8 == 0):
            lab_sub = np.full(n, -1, dtype=int)
            for ci, c in enumerate(big):
                lab_sub[clusters[c]] = ci
            yield _fr(step, f"Condensing tree — {len(big)} persistent clusters",
                      _expand(P, idx, lab_sub),
                      extra=_ins(f"{len(big)} branches are still big enough"),
                      P=P)
        if len(active) <= 6:
            break
    big = [c for c in active if len(clusters[c]) >= min_cluster]
    lab_sub = np.full(n, -1, dtype=int)
    for ci, c in enumerate(big):
        lab_sub[clusters[c]] = ci
    yield _fr(step, f"Selected {len(big)} clusters; rest is noise",
              _expand(P, idx, lab_sub),
              extra=_ins(f"kept {len(big)} persistent clusters"),
              converged=True, P=P)


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
        "fn": step_kmeans, "true_iteration": True,
        "blurb": "Partition into k blobs by repeatedly reassigning points and "
                 "moving centroids to the mean.",
        "params": [
            _p("k", "Clusters (k)", "int", 4, 2, 100, 1, help="Number of clusters"),
            _p("max_iter", "Max iterations", "int", 60, 5, 500, 5),
            _p("n_init", "N init", "int", 10, 1, 50, 1, applies=False,
               help="This view animates a single seeding so you can follow it; "
                    "② Cluster runs all n_init restarts and keeps the best."),
        ],
    },
    "MiniBatch K-Means": {
        "fn": lambda P, pr, rng: step_kmeans(P, pr, rng, minibatch=True),
        "true_iteration": True,
        "blurb": "K-Means that updates centroids from small random batches — "
                 "faster, slightly noisier.",
        "params": [
            _p("k", "Clusters (k)", "int", 4, 2, 100, 1),
            _p("batch_size", "Batch size", "int", 256, 32, 4096, 32),
            _p("max_iter", "Max iterations", "int", 80, 5, 500, 5),
            _p("n_init", "N init", "int", 3, 1, 20, 1, applies=False,
               help="This view animates a single seeding; ② Cluster runs all "
                    "n_init restarts and keeps the best."),
        ],
    },
    "Gaussian Mixture": {
        "fn": step_gmm, "true_iteration": True,
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
        "fn": step_hierarchical, "true_iteration": True,
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
        "fn": step_dbscan, "true_iteration": True,
        "blurb": "Grow clusters from dense cores; points in sparse regions are "
                 "labelled noise. No k needed.",
        "params": [
            _p("eps", "Neighbourhood radius (eps)", "float", 0.15, 0.02, 2.0, 0.01),
            _p("min_samples", "Min samples", "int", 6, 2, 100, 1),
            _p("metric", "Metric", "choice", "euclidean", options=_METRICS),
        ],
    },
    "Mean Shift": {
        "fn": step_meanshift, "true_iteration": True,
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
        "fn": step_optics, "true_iteration": True,
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
        "fn": step_birch, "true_iteration": True,
        "blurb": "Stream points into a compact CF-tree of sub-clusters, then "
                 "merge those into k clusters.",
        "params": [
            _p("threshold", "Radius threshold", "float", 0.15, 0.02, 2.0, 0.01),
            _p("k", "Final clusters (k)", "int", 4, 2, 100, 1),
            _p("branching_factor", "Branching factor", "int", 50, 10, 200, 5,
               applies=False,
               help="This view keeps one flat list of CF leaves so the "
                    "absorption step stays visible; ② Cluster builds the real "
                    "multi-level tree this bounds."),
        ],
    },
    "Spectral": {
        "fn": step_spectral, "true_iteration": True,
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
        "fn": step_hdbscan, "true_iteration": True,
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
        "fn": step_som, "true_iteration": True,
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
    out = {}
    for name, spec in ALGORITHMS.items():
        out[name] = {
            "blurb": spec["blurb"],
            "true_iteration": spec["true_iteration"],
            "params": spec["params"],
        }
    return out


def run(algo, params, prep, seed=42):
    """Yield frames for ``algo`` over preprocessed data ``prep``.

    A final frame carries ``metrics_full`` (silhouette / Davies-Bouldin).
    """
    rng = np.random.default_rng(seed)
    P = np.asarray(prep["xy"], dtype=np.float64)
    spec = ALGORITHMS.get(algo)
    if spec is None:
        return
    last = None
    for frame in spec["fn"](P, params, rng):
        last = frame
        yield frame
    if last is not None:
        cents = None if last.get("centroids") is None else np.asarray(last["centroids"])
        fm = full_metrics(P, np.asarray(last["labels"]), cents, rng=rng)
        yield {"iter": last["iter"], "note": "Final validity metrics computed",
               "labels": last["labels"], "centroids": last.get("centroids"),
               "positions": last.get("positions"), "extra": last.get("extra", {}),
               "metrics": last.get("metrics", {}), "metrics_full": fm,
               "converged": True, "final": True}
