# `live_engine.py`

Pure-NumPy clustering engine with per-iteration *steppers* for Cluster Lab.

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

---

## Constants

| Name | Value |
|------|-------|
| `SCALINGS` | `['None', 'CLR', 'Robust Z-score', 'Standardize']` |
| `_SUPERSCRIPT` | `str.maketrans('0123456789-', '⁰¹²³⁴⁵⁶⁷⁸⁹⁻')` |
| `FULL_LINKAGE_MAX` | `12000` |
| `_SCIPY_METRIC` | `{'manhattan': 'cityblock', 'l1': 'cityblock', 'l2': 'eucl…` |
| `_METRICS` | `['euclidean', 'manhattan', 'cosine', 'l1', 'l2']` |
| `ALGORITHMS` | `{'K-Means': {'fn': step_kmeans, 'true_iteration': True, '…` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_multiplicative_replacement` | `(X, frac=0.65)` | Replace zeros with a fraction of each column's smallest positive value. |
| `_clr` | `(X)` | Centred log-ratio transform of a composition matrix. |
| `_robust_z` | `(X)` | Median/MAD robust z-score standardisation. |
| `_standardize` | `(X)` | Mean/standard-deviation standardisation. |
| `_pca_2d` | `(X)` | Project to 2 components; returns (P, explained_variance_ratio[:2]). |
| `build_matrix` | `(input_data, elements, cfg)` | Turn ``input_data`` into (raw_matrix, sample_labels) for ``elements``. |
| `preprocess` | `(input_data, elements, cfg)` | Full pipeline: matrix -> filter -> scale -> PCA-2D display projection. |
| `_inertia` | `(P, labels, centroids)` | Total within-cluster squared distance to the centroids. |
| `silhouette` | `(P, labels, max_points=500, rng=None)` | Subsampled silhouette score (mean over up to ``max_points`` points). |
| `davies_bouldin` | `(P, labels, centroids=None)` | Davies-Bouldin cluster-validity index (lower is better). |
| `cheap_metrics` | `(P, labels, centroids=None)` | Fast per-frame metrics: cluster count, noise, inertia and sizes. |
| `calinski_harabasz` | `(P, labels)` | Calinski-Harabasz index (variance-ratio criterion; higher is better). |
| `_finite_or_none` | `(x)` | Return ``x`` if it is a finite number, otherwise ``None`` (JSON-safe). |
| `full_metrics` | `(P, labels, centroids=None, rng=None)` | Cheap metrics plus silhouette and Davies-Bouldin scores (JSON-safe). |
| `_pairwise` | `(A, B=None, metric='euclidean')` | Pairwise distances between two point sets under the chosen metric. |
| `_metric_label` | `(metric)` | Human name of a metric, for the notes and worked examples. |
| `_shape_covs` | `(covs, cov_type, d, Nk=None)` | Constrain fitted covariances to the requested family. |
| `_affinity_note` | `(affinity, nn)` | Narration for the graph-building step of spectral clustering. |
| `_kpp_init` | `(P, k, rng)` | k-means++ seeding. |
| `_inset` | `(kind, title, subtitle='', **payload)` | Build the algorithm-specific *detail view* payload for the UI inset. |
| `_n` | `(v, p=3)` | Format one number for a worked example (compact, never NaN/inf). |
| `_eq` | `(title, formula, lines, result=None, note='')` | Build the *worked example* payload shown in the equation box. |
| `_fr` | `(it, note, labels, centroids=None, positions=None, extra=None, converg` | Assemble a frame with cheap metrics attached. |
| `step_kmeans` | `(P, params, rng, minibatch=False)` | Stream Lloyd (or MiniBatch) K-Means iterations as frames. |
| `step_gmm` | `(P, params, rng)` | Stream Gaussian-mixture EM iterations as frames. |
| `step_dbscan` | `(P, params, rng)` | Stream DBSCAN density region-growing as frames. |
| `step_meanshift` | `(P, params, rng)` | Stream mean-shift density ascent as frames. |
| `_merge_modes` | `(pts, tol, min_bin_freq=1)` | Group collapsed points into modes by snapping to a coarse grid. |
| `step_hierarchical` | `(P, params, rng)` | Stream agglomerative merges as frames. |
| `full_hierarchical` | `(P, k, linkage='ward', metric='euclidean')` | Agglomerative partition of *every* point, not just the animated sample. |
| `_linkage_dist` | `(Q, ca, cb, cea, ceb, linkage, metric='euclidean')` | Linkage distance between two clusters under the chosen metric. |
| `_subsample` | `(P, max_points, rng)` | Return indices of a representative subset (all points if small enough). |
| `_nn_map` | `(P, idx)` | Index of the nearest representative (row of ``P[idx]``) for every point. |
| `_expand` | `(P, idx, lab_sub)` | Assign every point the label of its nearest representative. |
| `_sub_labels` | `(clusters, n, active=None)` | Contiguous 0..K-1 labels over the n representatives from a cluster dict. |
| `step_som` | `(P, params, rng)` | Stream self-organising-map training as frames. |
| `_kmeans_labels` | `(X, k, rng, iters=30)` | Quick K-Means labelling used to group SOM neurons. |
| `step_spectral` | `(P, params, rng)` | Stream spectral clustering (embedding then K-Means) as frames. |
| `step_birch` | `(P, params, rng)` | Stream Birch CF-tree insertion and the final merge as frames. |
| `step_optics` | `(P, params, rng)` | Stream OPTICS reachability ordering and cluster extraction as frames. |
| `step_hdbscan` | `(P, params, rng)` | Approximate HDBSCAN: mutual-reachability single-linkage + size cut. |
| `_p` | `(key, label, typ, default, mn=None, mx=None, step=None, options=None, ` | Build one parameter-spec dict for the algorithm panel schema. |
| `algorithm_schema` | `()` | JSON-friendly description of every algorithm + params (drives the UI). |
| `run` | `(algo, params, prep, seed=42)` | Yield frames for ``algo`` over preprocessed data ``prep``. |
