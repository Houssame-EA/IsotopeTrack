"""Detail views and worked examples, built from a finished clustering fit.

The Cluster Lab used to run a second, hand-written NumPy implementation of every
algorithm purely so it could narrate the answer as it was built. That meant the
same clustering was computed twice, and the picture on screen came from the
teaching copy rather than the real one. This module replaces that: it takes the
*single* scikit-learn fit the rest of the app already performed and derives the
same two panels from it.

``build`` is the entry point. It returns the payload the frontend expects::

    {"inset": {...}, "equation": {...}}

``inset`` drives the small figure beside the scatter and is rendered by
:mod:`results.cluster.live_qt.insets`, which understands four kinds:

``curve``
    ``series`` of ``[x, y]`` points, optional ``hline`` marking a threshold.
``bars``
    ``values`` per bar with optional ``bar_clusters`` to colour them by cluster.
``dendrogram``
    ``merges`` in scipy's ``[a, b, height, size]`` form plus ``n_leaves``.
``grid``
    A ``rows`` x ``cols`` field of ``values``, used for the SOM's U-matrix.

``equation`` states the formula the algorithm optimises with this fit's actual
numbers substituted in.

Where scikit-learn keeps the interesting quantity on the fitted estimator — the
reachability ordering for OPTICS, the mixing weights for a Gaussian mixture, the
merge heights for agglomerative clustering — the estimator is read directly, so
the figure describes the fit that produced the labels rather than an
approximation of it. When no estimator is available the builders fall back to
quantities derivable from the labels and the data alone, so a detail view is
always produced.
"""

from __future__ import annotations

import logging

import numpy as np

try:
    from results.cluster.live_engine import _eq, _inset, _n
except Exception:
    from .live_engine import _eq, _inset, _n

_log = logging.getLogger("IsotopeTrack.results.cluster.detail")

MAX_DENDRO_LEAVES = 160

#: Points kept in a curve inset.
#:
#: The renderer walks the series in Python and issues one line segment per
#: point, so handing it one point per particle would cost tens of thousands of
#: draw calls on every repaint. A curve a couple of hundred points wide is
#: indistinguishable at inset size and costs nothing.
MAX_CURVE_POINTS = 240


def _curve_series(values, label, color="accent"):
    """Wrap a sequence of y-values in the shape the curve renderer expects.

    Long sequences are evenly subsampled to :data:`MAX_CURVE_POINTS`, keeping
    the first and last values so the ends of the curve stay exact.

    Args:
        values (array-like): The y-values, in x order.
        label (str): Legend text.
        color (str): Theme colour key.

    Returns:
        list[dict]: A single-series list for the ``series`` payload key.
    """
    v = np.asarray(values, float).ravel()
    if v.size > MAX_CURVE_POINTS:
        idx = np.unique(np.linspace(0, v.size - 1, MAX_CURVE_POINTS).astype(int))
        v = v[idx]
    return [{"y": [None if not np.isfinite(x) else float(x) for x in v],
             "label": label, "color": color}]


def _sizes(labels):
    """Return the cluster ids present and their populations.

    Args:
        labels (np.ndarray): Cluster id per point, -1 for noise.

    Returns:
        tuple: ``(ids, counts)`` with noise excluded from both.
    """
    labels = np.asarray(labels, int)
    ids = sorted({int(v) for v in labels if v >= 0})
    return ids, [int((labels == c).sum()) for c in ids]


def _centroids(X, labels, ids):
    """Mean position of each cluster in ``X``.

    Args:
        X (np.ndarray): Feature matrix.
        labels (np.ndarray): Cluster id per row.
        ids (list): Cluster ids to compute, in order.

    Returns:
        np.ndarray: One row per id.
    """
    X = np.asarray(X, float)
    return np.array([X[labels == c].mean(axis=0) if (labels == c).any()
                     else np.zeros(X.shape[1]) for c in ids])


def _wcss(X, labels, ids):
    """Within-cluster sum of squares, total and per cluster.

    Args:
        X (np.ndarray): Feature matrix.
        labels (np.ndarray): Cluster id per row.
        ids (list): Cluster ids to compute, in order.

    Returns:
        tuple: ``(total, per_cluster)``.
    """
    X = np.asarray(X, float)
    cents = _centroids(X, labels, ids)
    per = []
    for c, mu in zip(ids, cents):
        pts = X[labels == c]
        per.append(float(((pts - mu) ** 2).sum()) if pts.size else 0.0)
    return float(sum(per)), per


#: Points sampled when the k-distance curve has to fall back to brute force.
#:
#: Without a neighbour index the calculation is quadratic, which at tens of
#: thousands of particles means hundreds of millions of distances for a figure
#: a couple of hundred pixels wide. The shape of the curve is what matters, and
#: a sample of this size reproduces it.
KDIST_BRUTE_MAX = 2000

#: How far above the median a SOM grid edge may stretch before it is dropped.
#:
#: The map is trained in the fit space but drawn in the display projection, so
#: two neurons that are neighbours on the grid can own particles at opposite
#: ends of the plot. Drawing those edges spans the whole figure and buries the
#: map under crossing lines. The grid is kept where it is legible and the long
#: jumps are simply not drawn.
EDGE_LENGTH_LIMIT = 4.0


def _k_distance(X, min_samples):
    """Sorted distance to the k-th nearest neighbour of every point.

    This is the curve the elbow rule reads to pick a density radius, and it
    depends only on the data, so it describes DBSCAN and OPTICS equally well
    without needing anything from the fit.

    Uses scikit-learn's neighbour index, which answers this in roughly
    ``n log n``. Only if that import fails does it fall back to brute force, and
    then over a sample of at most :data:`KDIST_BRUTE_MAX` points.

    Args:
        X (np.ndarray): Feature matrix.
        min_samples (int): Neighbour rank to measure.

    Returns:
        np.ndarray: Ascending distances.
    """
    X = np.asarray(X, float)
    n = len(X)
    if n < 2:
        return np.zeros(n)
    k = max(1, min(int(min_samples), n - 1))
    try:
        from sklearn.neighbors import NearestNeighbors
        nn = NearestNeighbors(n_neighbors=k + 1).fit(X)
        d, _ = nn.kneighbors(X)
        out = d[:, k].copy()
        out.sort()
        return out
    except Exception:
        _log.exception("Handled exception building the neighbour index")

    if n > KDIST_BRUTE_MAX:
        idx = np.linspace(0, n - 1, KDIST_BRUTE_MAX).astype(int)
        X = X[np.unique(idx)]
        n = len(X)
        k = max(1, min(k, n - 1))
    step = max(1, int(2e6 // max(1, n)))
    out = np.empty(n)
    for i in range(0, n, step):
        chunk = X[i:i + step]
        d = np.sqrt(((chunk[:, None, :] - X[None, :, :]) ** 2).sum(-1))
        d.sort(axis=1)
        out[i:i + step] = d[:, k]
    out.sort()
    return out


def _size_bars(title, subtitle, labels, ylabel="particles"):
    """Build a bar inset of cluster populations.

    The fallback figure for any algorithm with nothing more specific to show.

    Args:
        title (str): Inset heading.
        subtitle (str): One-line explanation.
        labels (np.ndarray): Cluster id per point.
        ylabel (str): Axis label.

    Returns:
        dict: An ``inset`` payload.
    """
    ids, counts = _sizes(labels)
    return _inset("bars", title, subtitle, values=[float(c) for c in counts],
                  bar_clusters=ids, xlabel="cluster", ylabel=ylabel)


def _kmeans(ctx):
    """Detail view for K-Means and MiniBatch K-Means.

    Shows what each cluster contributes to the inertia the algorithm minimises,
    so a single wide bar marks the group that is costing the most.
    """
    X, labels = ctx["X"], ctx["labels"]
    ids, counts = _sizes(labels)
    total, per = _wcss(X, labels, ids)
    lines = [[r"n_k", "particles in each cluster",
              ", ".join(str(c) for c in counts) or "—"],
             [r"\sum_{x\in C_k}\|x-\mu_k\|^2", "worst cluster's contribution",
              _n(max(per) if per else 0, 4)],
             [r"J", f"summed over all {len(ids)} clusters", _n(total, 4)]]
    return {
        **_inset("bars", "Inertia by cluster",
                 "how much each group adds to the total the fit minimises",
                 values=[float(v) for v in per], bar_clusters=ids,
                 xlabel="cluster", ylabel="within-cluster sum of squares"),
        **_eq("Inertia (within-cluster sum of squares)",
              r"J=\sum_{k=1}^{K}\sum_{x\in C_k}\|x-\mu_k\|^2", lines,
              result=["J", _n(total, 4)],
              note="the fit chose the centroids that make this total as small "
                   "as it could; a tall bar is a cluster that is still spread out")}


def _gmm(ctx):
    """Detail view for the Gaussian mixture.

    Reads the fitted mixing weights when the estimator is available, since those
    are the parameters the model actually estimated, and falls back to the
    observed cluster proportions otherwise.
    """
    labels = ctx["labels"]
    est = ctx["estimator"]
    ids, counts = _sizes(labels)
    n = max(1, int(np.asarray(labels).size))
    weights = getattr(est, "weights_", None)
    if weights is not None and len(weights) == len(ids):
        vals = [float(w) for w in weights]
        sub = "fitted mixing weights — the share of the data each component claims"
        src = "estimated by the fit"
    else:
        vals = [c / n for c in counts]
        sub = "share of the particles assigned to each component"
        src = "counted from the assignments"
    ll = getattr(est, "lower_bound_", None)
    lines = [[r"\pi_k", src, ", ".join(_n(v, 3) for v in vals) or "—"],
             [r"\sum_k \pi_k", "the weights are a probability distribution",
              _n(sum(vals), 3)]]
    if ll is not None:
        lines.append([r"\log L", "mean log-likelihood the fit reached",
                      _n(float(ll), 4)])
    return {
        **_inset("bars", "Mixing weights", sub, values=vals, bar_clusters=ids,
                 xlabel="component", ylabel="weight"),
        **_eq("Gaussian mixture",
              r"p(x)=\sum_{k=1}^{K}\pi_k\,\mathcal{N}(x\mid\mu_k,\Sigma_k)",
              lines,
              result=(None if ll is None else [r"\log L", _n(float(ll), 4)]),
              note="each particle is assigned to the component that most likely "
                   "produced it, so a component can be narrow or broad")}


def _dbscan(ctx):
    """Detail view for DBSCAN.

    The k-distance curve with the chosen radius drawn across it: where the curve
    turns up, points stop having close neighbours and become noise.
    """
    X, labels, params = ctx["X"], ctx["labels"], ctx["params"]
    ms = int(params.get("min_samples", params.get("dbscan_min_samples", 5)) or 5)
    eps = float(params.get("eps", params.get("dbscan_eps", 0.0)) or 0.0)
    d = _k_distance(X, ms)
    labels = np.asarray(labels, int)
    noise = int((labels < 0).sum())
    ids, _ = _sizes(labels)
    below = int((d <= eps).sum()) if eps > 0 else 0
    lines = [[r"\varepsilon", "the radius you set", _n(eps, 4)],
             [r"\mathrm{minPts}", "neighbours needed to be a core point", str(ms)],
             [r"|\{d_k \le \varepsilon\}|",
              f"points whose {ms}-th neighbour is within the radius", str(below)],
             ["noise", "points in no dense region", str(noise)]]
    return {
        **_inset("curve", "k-distance curve",
                 f"distance to each point's {ms}-th nearest neighbour, sorted — "
                 f"the line is your radius",
                 series=_curve_series(d, f"{ms}-th neighbour distance"),
                 hline=({"y": float(eps), "label": "eps", "color": "bad"}
                        if eps > 0 else None),
                 xlabel="particles, sorted", ylabel=f"distance to {ms}-th neighbour"),
        **_eq("Density reachability",
              r"N_\varepsilon(x)=\{y : \|x-y\| \le \varepsilon\},\quad"
              r"|N_\varepsilon(x)| \ge \mathrm{minPts}", lines,
              result=["clusters found", str(len(ids))],
              note="the elbow of this curve is the usual choice of radius: below "
                   "it points have close neighbours, above it they do not")}


def _hierarchical(ctx):
    """Detail view for agglomerative clustering.

    Prefers the merge heights recorded by the fitted estimator, which are the
    real tree; recomputes a linkage over a bounded sample only when the
    estimator did not keep them.
    """
    X, labels, params = ctx["X"], ctx["labels"], ctx["params"]
    est = ctx["estimator"]
    k = int(ctx["k"])
    linkage = params.get("linkage", params.get("hier_linkage", "ward"))
    merges, n_leaves, leaf_labels = _linkage_from_estimator(est)
    if merges is None:
        merges, n_leaves, leaf_labels = _linkage_from_data(X, labels, linkage)
    if merges is None:
        return {**_size_bars("Cluster sizes",
                             "the dendrogram needs the merge heights, which this "
                             "fit did not keep", labels),
                **_eq("Linkage distance",
                      r"d(A,B)\ \text{between the two groups fused at each step}",
                      [["", "merge heights unavailable", "—"]])}
    heights = [float(m[2]) for m in merges]
    cut = heights[-k + 1] if 0 < k - 1 <= len(heights) else (
        heights[-1] if heights else 0.0)
    lines = [["linkage", "how the distance between two groups is measured",
              str(linkage)],
             [r"n", "leaves in the tree", str(n_leaves)],
             [r"d_{\max}", "height of the final merge",
              _n(max(heights) if heights else 0, 4)],
             [r"d_{\mathrm{cut}}", f"height the tree is cut at for k={k}",
              _n(cut, 4)]]
    return {
        **_inset("dendrogram", "Dendrogram",
                 f"{linkage} linkage — height is where two groups fuse; cutting "
                 f"at k={k} gives the colours",
                 merges=[[int(m[0]), int(m[1]), float(m[2]), int(m[3])]
                         for m in merges],
                 n_leaves=int(n_leaves), leaf_labels=leaf_labels,
                 cut=int(k), target=int(k), ylabel="linkage distance"),
        **_eq(f"Linkage distance ({linkage})",
              r"d(A,B)=\frac{n_A n_B}{n_A+n_B}\|c_A-c_B\|^2"
              if linkage == "ward" else r"d(A,B)\ \text{over all pairs }a\in A,b\in B",
              lines, result=["cut height", _n(cut, 4)],
              note="each bar is one fusion; cutting the tree straight across at "
                   "the height above leaves exactly the clusters you see")}


def _linkage_from_estimator(est):
    """Rebuild scipy-style merges from a fitted AgglomerativeClustering.

    A tree with one leaf per particle is unreadable and slow to draw, so only
    the top of it is kept: the last merges, with everything below each cut point
    collapsed into a single leaf carrying its majority cluster. That is the part
    of the dendrogram the cut at k actually passes through, and it comes from
    the fit itself rather than from a second linkage.

    Args:
        est: The fitted estimator, or None.

    Returns:
        tuple: ``(merges, n_leaves, leaf_labels)``, or ``(None, 0, [])``.
    """
    children = getattr(est, "children_", None)
    dists = getattr(est, "distances_", None)
    if children is None or dists is None:
        return None, 0, []
    children = np.asarray(children, int)
    dists = np.asarray(dists, float)
    if children.ndim != 2 or len(children) != len(dists) or not len(children):
        return None, 0, []
    n = int(children.shape[0]) + 1
    sizes = np.ones(2 * n - 1, int)
    for i, (a, b) in enumerate(children):
        sizes[n + i] = sizes[a] + sizes[b]

    labels = getattr(est, "labels_", None)
    labels = (np.asarray(labels, int) if labels is not None
              and len(labels) == n else np.zeros(n, int))

    keep = min(len(children), MAX_DENDRO_LEAVES - 1)
    first = len(children) - keep
    kept = set(range(n + first, n + len(children)))

    def _majority(node):
        """Most common cluster among the original leaves under ``node``."""
        stack, seen = [node], []
        while stack:
            cur = stack.pop()
            if cur < n:
                seen.append(int(labels[cur]))
            else:
                stack.extend(children[cur - n])
        if not seen:
            return 0
        vals, counts = np.unique(np.asarray(seen), return_counts=True)
        return int(vals[int(np.argmax(counts))])

    slot, leaf_labels = {}, []
    for node in sorted(
            {int(c) for i in range(first, len(children)) for c in children[i]}
            - kept):
        slot[node] = len(leaf_labels)
        leaf_labels.append(_majority(node))
    if len(leaf_labels) < 2:
        return None, 0, []

    merges = []
    for i in range(first, len(children)):
        a, b = (int(v) for v in children[i])
        slot[n + i] = len(leaf_labels) + len(merges)
        merges.append([slot[a], slot[b], float(dists[i]), int(sizes[n + i])])
    return merges, len(leaf_labels), leaf_labels


def _linkage_from_data(X, labels, linkage):
    """Compute a bounded linkage when the estimator kept no merge heights.

    Agglomerative clustering needs the condensed distance matrix, which grows
    with the square of the point count, so the tree is built over an evenly
    spaced sample and the leaves are coloured by their real cluster.

    Args:
        X (np.ndarray): Feature matrix.
        labels (np.ndarray): Cluster id per row.
        linkage (str): Linkage method name.

    Returns:
        tuple: ``(merges, n_leaves, leaf_labels)``, or ``(None, 0, [])``.
    """
    try:
        from scipy.cluster.hierarchy import linkage as sp_linkage
    except Exception:
        return None, 0, []
    X = np.asarray(X, float)
    labels = np.asarray(labels, int)
    n = len(X)
    if n < 3:
        return None, 0, []
    idx = (np.linspace(0, n - 1, MAX_DENDRO_LEAVES).astype(int)
           if n > MAX_DENDRO_LEAVES else np.arange(n))
    idx = np.unique(idx)
    try:
        method = linkage if linkage in ("ward", "single", "complete",
                                        "average") else "ward"
        Z = sp_linkage(X[idx], method=method)
    except Exception:
        _log.exception("Handled exception building the dendrogram linkage")
        return None, 0, []
    merges = [[int(a), int(b), float(h), int(s)] for a, b, h, s in Z]
    return merges, len(idx), [int(v) for v in labels[idx]]


def _meanshift(ctx):
    """Detail view for Mean Shift.

    Shows how far each mode sits from the overall centre of the data, which is
    what the bandwidth controls: a wide bandwidth pulls the modes together.
    """
    X, labels, params = ctx["X"], ctx["labels"], ctx["params"]
    est = ctx["estimator"]
    ids, counts = _sizes(labels)
    centres = getattr(est, "cluster_centers_", None)
    X = np.asarray(X, float)
    if centres is not None and len(centres) == len(ids):
        cents = np.asarray(centres, float)
        src = "fitted mode positions"
    else:
        cents = _centroids(X, np.asarray(labels, int), ids)
        src = "mean position of each group"
    origin = X.mean(axis=0) if X.size else np.zeros(cents.shape[1:])
    spread = [float(np.sqrt(((c - origin) ** 2).sum())) for c in cents]
    bw = float(params.get("bandwidth", params.get("meanshift_bandwidth", 0)) or 0)
    lines = [["bandwidth", "width of the window each point climbs in",
              _n(bw, 4) if bw > 0 else "estimated from the data"],
             ["modes", "peaks the points converged onto", str(len(ids))],
             [r"n_k", "particles that reached each peak",
              ", ".join(str(c) for c in counts) or "—"]]
    return {
        **_inset("bars", "Modes found",
                 f"{src}, as distance from the centre of the data",
                 values=spread, bar_clusters=ids, xlabel="mode",
                 ylabel="distance from centre"),
        **_eq("Mean shift",
              r"m(x)=\frac{\sum_i K\!\left(\frac{\|x-x_i\|}{h}\right)x_i}"
              r"{\sum_i K\!\left(\frac{\|x-x_i\|}{h}\right)}", lines,
              result=["clusters", str(len(ids))],
              note="every particle climbs the density gradient until it stops "
                   "moving; particles that stop in the same place are one cluster")}


def _optics(ctx):
    """Detail view for OPTICS.

    The reachability plot, read straight off the fitted estimator: valleys are
    clusters and the peaks between them are the boundaries the fit cut at.
    """
    X, labels, params = ctx["X"], ctx["labels"], ctx["params"]
    est = ctx["estimator"]
    reach = getattr(est, "reachability_", None)
    order = getattr(est, "ordering_", None)
    ids, _ = _sizes(labels)
    noise = int((np.asarray(labels, int) < 0).sum())
    ms = int(params.get("min_samples", params.get("optics_min_samples", 5)) or 5)
    if reach is not None and order is not None:
        r = np.asarray(reach, float)[np.asarray(order, int)]
        r = np.where(np.isfinite(r), r, 0.0)
        inset = _inset("curve", "Reachability plot",
                       "particles in the order OPTICS visited them — each valley "
                       "is a cluster, each peak a boundary",
                       series=_curve_series(r, "reachability"),
                       xlabel="processing order",
                       ylabel="reachability distance")
        peak = float(r.max()) if r.size else 0.0
        lines = [[r"\mathrm{minPts}", "neighbours needed for a core point", str(ms)],
                 [r"\max r", "tallest boundary between two valleys", _n(peak, 4)],
                 ["noise", "particles left in no valley", str(noise)]]
    else:
        d = _k_distance(X, ms)
        inset = _inset("curve", "k-distance curve",
                       "the fit kept no reachability ordering, so this shows the "
                       f"distance to each point's {ms}-th neighbour",
                       series=_curve_series(d, f"{ms}-th neighbour distance"),
                       xlabel="particles, sorted",
                       ylabel=f"distance to {ms}-th neighbour")
        lines = [[r"\mathrm{minPts}", "neighbours needed for a core point", str(ms)],
                 ["noise", "particles left in no valley", str(noise)]]
    return {**inset,
            **_eq("Reachability distance",
                  r"r(x)=\max\bigl(\mathrm{core}(x),\ \|x-y\|\bigr)", lines,
                  result=["clusters", str(len(ids))],
                  note="OPTICS orders the particles so that dense neighbourhoods "
                       "sit together; the clusters are then carved from the valleys")}


def _birch(ctx):
    """Detail view for Birch.

    Shows the sub-cluster summaries the tree kept before they were merged into
    the final clusters, which is what the radius threshold controls.
    """
    labels, params = ctx["labels"], ctx["params"]
    est = ctx["estimator"]
    centres = getattr(est, "subcluster_centers_", None)
    thr = float(params.get("threshold", params.get("birch_threshold", 0)) or 0)
    ids, counts = _sizes(labels)
    if centres is not None and len(centres):
        cents = np.asarray(centres, float)
        origin = cents.mean(axis=0)
        vals = [float(np.sqrt(((c - origin) ** 2).sum())) for c in cents]
        sub = (f"{len(cents)} CF leaves the tree kept, as distance from their "
               f"own centre")
        inset = _inset("bars", "CF leaves", sub, values=vals, xlabel="leaf",
                       ylabel="distance from centre")
        leaves = str(len(cents))
    else:
        inset = _size_bars("Cluster sizes",
                           "the fit kept no CF leaves, so this shows the final "
                           "groups", labels)
        leaves = "—"
    lines = [["threshold", "largest radius a sub-cluster may have", _n(thr, 4)],
             ["CF leaves", "summaries the tree held before the final merge", leaves],
             [r"n_k", "particles per final cluster",
              ", ".join(str(c) for c in counts) or "—"]]
    return {**inset,
            **_eq("Clustering feature",
                  r"\mathrm{CF}=(N,\ \vec{LS},\ SS),\quad"
                  r"R=\sqrt{\frac{SS}{N}-\left\|\frac{\vec{LS}}{N}\right\|^2}",
                  lines, result=["clusters", str(len(ids))],
                  note="each leaf stores only a count, a sum and a sum of squares, "
                       "which is why Birch can stream data it never holds at once")}


def _spectral(ctx):
    """Detail view for Spectral clustering.

    The eigenvalue spectrum of the affinity graph's Laplacian, where the gap
    after the k-th value is the evidence for choosing that many clusters.
    """
    X, labels = ctx["X"], ctx["labels"]
    est = ctx["estimator"]
    k = int(ctx["k"])
    ids, _ = _sizes(labels)
    vals = _spectrum(est, X)
    if vals is None:
        return {**_size_bars("Cluster sizes",
                             "the affinity graph was not kept, so this shows the "
                             "final groups", labels),
                **_eq("Graph Laplacian", r"L=D-W", [["", "spectrum unavailable", "—"]])}
    gaps = np.diff(vals)
    gap_at = int(np.argmax(gaps)) + 1 if gaps.size else 0
    lines = [[r"\lambda_i", "smallest eigenvalues of the Laplacian",
              ", ".join(_n(v, 3) for v in vals[:6])],
             [r"\lambda_{k+1}-\lambda_k", "largest gap in the spectrum",
              _n(float(gaps.max()) if gaps.size else 0, 4)],
             ["k", "clusters you asked for", str(k)]]
    return {
        **_inset("bars", "Laplacian spectrum",
                 "the gap after the k-th eigenvalue is how strongly the data "
                 "argues for that many clusters",
                 values=[float(v) for v in vals], highlight=gap_at,
                 xlabel="eigenvalue index", ylabel=r"λ"),
        **_eq("Graph Laplacian", r"L=D-W,\qquad L u_i=\lambda_i u_i", lines,
              result=["largest gap after", str(gap_at)],
              note="clustering happens on the eigenvectors, not the raw points, "
                   "which is how this finds shapes K-Means cannot")}


def _spectrum(est, X, want=12):
    """Smallest eigenvalues of the normalised Laplacian of the affinity graph.

    Args:
        est: Fitted estimator, consulted for ``affinity_matrix_``.
        X (np.ndarray): Feature matrix, used when the estimator kept nothing.
        want (int): How many eigenvalues to return.

    Returns:
        np.ndarray | None: Ascending eigenvalues, or None on failure.
    """
    W = getattr(est, "affinity_matrix_", None)
    try:
        if W is None:
            Xa = np.asarray(X, float)
            if len(Xa) > 800 or len(Xa) < 3:
                return None
            d2 = ((Xa[:, None, :] - Xa[None, :, :]) ** 2).sum(-1)
            scale = np.median(d2[d2 > 0]) if (d2 > 0).any() else 1.0
            W = np.exp(-d2 / max(scale, 1e-12))
        W = np.asarray(W, float)
        if W.ndim != 2 or W.shape[0] != W.shape[1] or W.shape[0] > 1500:
            return None
        deg = W.sum(axis=1)
        deg[deg <= 0] = 1.0
        dinv = 1.0 / np.sqrt(deg)
        L = np.eye(W.shape[0]) - (W * dinv[:, None]) * dinv[None, :]
        vals = np.linalg.eigvalsh((L + L.T) / 2.0)
        return np.sort(vals)[:want]
    except Exception:
        _log.exception("Handled exception computing the Laplacian spectrum")
        return None


def _hdbscan(ctx):
    """Detail view for HDBSCAN.

    Cluster persistence: how long each cluster survived as the density threshold
    was lowered, which is exactly the quantity HDBSCAN maximises when it decides
    which clusters to keep.
    """
    labels, params = ctx["labels"], ctx["params"]
    est = ctx["estimator"]
    ids, counts = _sizes(labels)
    noise = int((np.asarray(labels, int) < 0).sum())
    pers = getattr(est, "cluster_persistence_", None)
    mcs = int(params.get("min_cluster_size",
                         params.get("hdbscan_min_cluster_size", 5)) or 5)
    if pers is not None and len(pers) == len(ids):
        vals = [float(v) for v in pers]
        inset = _inset("bars", "Cluster persistence",
                       "how long each cluster survived as the density threshold "
                       "fell — tall bars are the clusters HDBSCAN trusted",
                       values=vals, bar_clusters=ids, xlabel="cluster",
                       ylabel="persistence")
        best = _n(max(vals) if vals else 0, 4)
    else:
        inset = _size_bars("Cluster sizes",
                           "the fit kept no persistence scores, so this shows the "
                           "final groups", labels)
        best = "—"
    lines = [["min cluster size", "smallest group allowed to be a cluster", str(mcs)],
             ["clusters kept", "groups that persisted", str(len(ids))],
             ["noise", "particles in no persistent cluster", str(noise)],
             ["strongest", "highest persistence score", best]]
    return {**inset,
            **_eq("Cluster stability",
                  r"S(C)=\sum_{x\in C}\left(\frac{1}{\lambda_x}-"
                  r"\frac{1}{\lambda_{\mathrm{birth}}}\right)", lines,
                  result=["clusters", str(len(ids))],
                  note="HDBSCAN keeps the clusters that stay intact longest as the "
                       "density threshold drops, so it picks the count itself")}


def _som(ctx):
    """Detail view for the Self-Organising Map.

    The U-matrix: each cell is one neuron of the trained grid, shaded by how far
    it sits from its neighbours, so cluster borders show up as ridges.
    """
    labels, params = ctx["labels"], ctx["params"]
    som = ctx.get("som")
    rows = int(params.get("som_rows", 6) or 6)
    cols = int(params.get("som_cols", 6) or 6)
    ids, counts = _sizes(labels)
    grid = _umatrix(som, rows, cols)
    if grid is None:
        return {**_size_bars("Cluster sizes",
                             "the trained map was not available, so this shows the "
                             "final groups", labels),
                **_eq("Self-organising map",
                      r"w_j \leftarrow w_j + \alpha\,h_{cj}\,(x-w_j)",
                      [["grid", "map size", f"{rows}x{cols}"],
                       ["clusters", "groups the neurons formed", str(len(ids))]])}
    flat = [float(v) for v in np.asarray(grid, float).ravel()]
    lines = [["grid", "neurons in the map", f"{rows}x{cols} = {rows * cols}"],
             [r"\max u", "tallest ridge between neighbouring neurons",
              _n(max(flat) if flat else 0, 4)],
             [r"n_k", "particles per cluster",
              ", ".join(str(c) for c in counts) or "—"]]
    return {
        **_inset("grid", "U-matrix",
                 "one cell per neuron, shaded by distance to its neighbours — "
                 "ridges are the borders between clusters",
                 rows=rows, cols=cols, values=flat),
        **_eq("Self-organising map",
              r"w_j \leftarrow w_j + \alpha(t)\,h_{cj}(t)\,\bigl(x-w_j\bigr)",
              lines, result=["clusters", str(len(ids))],
              note="neighbouring neurons hold similar particles, so the map lays "
                   "the data out on a grid you can read directly")}


def _umatrix(som, rows, cols):
    """Mean distance from every neuron to its grid neighbours.

    Prefers the map's own ``get_u_matrix``, which is what the SOM tab draws, so
    the two views of the same map agree.

    Args:
        som: The trained map.
        rows (int): Grid rows.
        cols (int): Grid columns.

    Returns:
        np.ndarray | None: A ``rows`` x ``cols`` field, or None.
    """
    if som is None:
        return None
    try:
        if hasattr(som, "get_u_matrix"):
            u = np.asarray(som.get_u_matrix(), float)
            if u.ndim == 2:
                return u
        w = som.get_weights() if hasattr(som, "get_weights") else getattr(
            som, "weights", None)
        if w is None:
            return None
        w = np.asarray(w, float)
        r = int(getattr(som, "rows", rows) or rows)
        c = int(getattr(som, "cols", cols) or cols)
        if w.ndim == 2 and w.shape[0] == r * c:
            w = w.reshape(r, c, -1)
        if w.ndim != 3:
            return None
        r, c = w.shape[0], w.shape[1]
        out = np.zeros((r, c))
        for i in range(r):
            for j in range(c):
                acc, n = 0.0, 0
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    a, b = i + di, j + dj
                    if 0 <= a < r and 0 <= b < c:
                        acc += float(np.sqrt(((w[i, j] - w[a, b]) ** 2).sum()))
                        n += 1
                out[i, j] = acc / max(n, 1)
        return out
    except Exception:
        _log.exception("Handled exception building the U-matrix")
        return None


def som_overlay(som, X, xy):
    """Place the trained map's neurons in the scatter's display coordinates.

    The map is trained in the fit space, which is not the space the scatter
    draws in, so a neuron cannot simply be plotted. Each neuron is put at the
    mean display position of the particles it won.

    Every neuron is drawn, including the ones that won nothing — an empty
    neuron is still part of the map, and dropping it tore holes in the grid and
    made a large map look far smaller than it is. Empty neurons take the average
    position of their placed grid neighbours, repeated until the grid is filled,
    so they sit where the map's own topology puts them.

    Args:
        som: The trained map, needing ``predict``, ``rows`` and ``cols``.
        X (np.ndarray): The matrix the map was trained on.
        xy (np.ndarray): Display coordinates, row-aligned with ``X``.

    Returns:
        dict | None: ``{'nodes': [[x, y], ...], 'edges': [[i, j], ...]}`` with
        one node per neuron, in row-major order.
    """
    if som is None or not hasattr(som, "predict"):
        return None
    try:
        X = np.asarray(X, float)
        xy = np.asarray(xy, float)
        if len(X) != len(xy) or len(X) == 0:
            return None
        bmu = np.asarray(som.predict(X), int).ravel()
        if len(bmu) != len(xy):
            return None
        rows = int(getattr(som, "rows", 0) or 0)
        cols = int(getattr(som, "cols", 0) or 0)
        if rows <= 0 or cols <= 0 or rows * cols < 2:
            return None
        dims = int(xy.shape[1]) if xy.ndim == 2 else 2

        pos = np.full((rows, cols, dims), np.nan)
        won = np.zeros((rows, cols), bool)
        for n in range(rows * cols):
            pts = xy[bmu == n]
            if pts.size:
                pos[n // cols, n % cols] = pts.mean(axis=0)
                won[n // cols, n % cols] = True
        if not won.any():
            return None

        for _ in range(rows + cols):
            holes = np.argwhere(~np.isfinite(pos[:, :, 0]))
            if not len(holes):
                break
            filled = pos.copy()
            for i, j in holes:
                near = [pos[a, b] for a, b in
                        ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1))
                        if 0 <= a < rows and 0 <= b < cols
                        and np.isfinite(pos[a, b, 0])]
                if near:
                    filled[i, j] = np.mean(near, axis=0)
            pos = filled
        flat = pos.reshape(-1, dims)
        centre = np.nanmean(flat[np.isfinite(flat[:, 0])], axis=0)
        pos[~np.isfinite(pos[:, :, 0])] = centre

        pairs = []
        for i in range(rows):
            for j in range(cols):
                if i + 1 < rows and won[i, j] and won[i + 1, j]:
                    pairs.append(((i, j), (i + 1, j)))
                if j + 1 < cols and won[i, j] and won[i, j + 1]:
                    pairs.append(((i, j), (i, j + 1)))
        lengths = np.array([float(np.sqrt(((pos[a] - pos[b]) ** 2).sum()))
                            for a, b in pairs]) if pairs else np.zeros(0)
        limit = (np.median(lengths) * EDGE_LENGTH_LIMIT
                 if lengths.size else np.inf)
        edges = [[a[0] * cols + a[1], b[0] * cols + b[1]]
                 for (a, b), d in zip(pairs, lengths) if d <= limit]

        return {"nodes": [[float(v) for v in p] for p in pos.reshape(-1, dims)],
                "edges": edges}
    except Exception:
        _log.exception("Handled exception placing the SOM neurons")
        return None


BUILDERS = {
    "K-Means": _kmeans,
    "MiniBatch K-Means": _kmeans,
    "Gaussian Mixture": _gmm,
    "DBSCAN": _dbscan,
    "Hierarchical": _hierarchical,
    "Mean Shift": _meanshift,
    "OPTICS": _optics,
    "Birch": _birch,
    "Spectral": _spectral,
    "HDBSCAN": _hdbscan,
    "SOM": _som,
}


def build(algo, params, X, labels, k, estimator=None, som=None):
    """Describe a finished fit as a detail view and a worked example.

    Never raises: a detail view is a reading aid, and failing to draw one must
    not cost the user their clustering. On failure an empty payload comes back
    and the boxes simply stay blank.

    Args:
        algo (str): Algorithm name, as used by :data:`BUILDERS`.
        params (dict): The parameters the fit ran with.
        X (np.ndarray): The matrix that was clustered.
        labels (array-like): Cluster id per row, -1 for noise.
        k (int): Cluster count requested.
        estimator: The fitted scikit-learn estimator, when one was kept.
        som: The trained self-organising map, for ``algo == 'SOM'``.

    Returns:
        dict: ``{'inset': {...}, 'equation': {...}}``, possibly empty.
    """
    fn = BUILDERS.get(algo)
    if fn is None:
        return {}
    try:
        labels = np.asarray(labels, int).ravel()
        X = np.asarray(X, float)
        if labels.size == 0 or X.size == 0:
            return {}
        return fn({"algo": algo, "params": dict(params or {}), "X": X,
                   "labels": labels, "k": int(k or 0),
                   "estimator": estimator, "som": som})
    except Exception:
        _log.exception("Handled exception building the %s detail view", algo)
        return {}
