# `detail.py`

Detail views and worked examples, built from a finished clustering fit.

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

---

## Constants

| Name | Value |
|------|-------|
| `MAX_DENDRO_LEAVES` | `160` |
| `MAX_CURVE_POINTS` | `240` |
| `KDIST_BRUTE_MAX` | `2000` |
| `EDGE_LENGTH_LIMIT` | `4.0` |
| `BUILDERS` | `{'K-Means': _kmeans, 'MiniBatch K-Means': _kmeans, 'Gauss…` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_curve_series` | `(values, label, color='accent')` | Wrap a sequence of y-values in the shape the curve renderer expects. |
| `_sizes` | `(labels)` | Return the cluster ids present and their populations. |
| `_centroids` | `(X, labels, ids)` | Mean position of each cluster in ``X``. |
| `_wcss` | `(X, labels, ids)` | Within-cluster sum of squares, total and per cluster. |
| `_k_distance` | `(X, min_samples)` | Sorted distance to the k-th nearest neighbour of every point. |
| `_size_bars` | `(title, subtitle, labels, ylabel='particles')` | Build a bar inset of cluster populations. |
| `_kmeans` | `(ctx)` | Detail view for K-Means and MiniBatch K-Means. |
| `_gmm` | `(ctx)` | Detail view for the Gaussian mixture. |
| `_dbscan` | `(ctx)` | Detail view for DBSCAN. |
| `_hierarchical` | `(ctx)` | Detail view for agglomerative clustering. |
| `_linkage_from_estimator` | `(est)` | Rebuild scipy-style merges from a fitted AgglomerativeClustering. |
| `_linkage_from_data` | `(X, labels, linkage)` | Compute a bounded linkage when the estimator kept no merge heights. |
| `_meanshift` | `(ctx)` | Detail view for Mean Shift. |
| `_optics` | `(ctx)` | Detail view for OPTICS. |
| `_birch` | `(ctx)` | Detail view for Birch. |
| `_spectral` | `(ctx)` | Detail view for Spectral clustering. |
| `_spectrum` | `(est, X, want=12)` | Smallest eigenvalues of the normalised Laplacian of the affinity graph. |
| `_hdbscan` | `(ctx)` | Detail view for HDBSCAN. |
| `_som` | `(ctx)` | Detail view for the Self-Organising Map. |
| `_umatrix` | `(som, rows, cols)` | Mean distance from every neuron to its grid neighbours. |
| `som_overlay` | `(som, X, xy)` | Place the trained map's neurons in the scatter's display coordinates. |
| `build` | `(algo, params, X, labels, k, estimator=None, som=None)` | Describe a finished fit as a detail view and a worked example. |
