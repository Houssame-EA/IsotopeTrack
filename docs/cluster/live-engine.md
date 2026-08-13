# `live_engine.py`

Preprocessing, metrics and the parameter schema behind the Cluster Lab tab.

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

---

## Constants

| Name | Value |
|------|-------|
| `SCALINGS` | `['None', 'CLR', 'Robust Z-score', 'Standardize']` |
| `_SUPERSCRIPT` | `str.maketrans('0123456789-', '⁰¹²³⁴⁵⁶⁷⁸⁹⁻')` |
| `_METRICS` | `['euclidean', 'manhattan', 'cosine', 'l1', 'l2']` |
| `ALGORITHMS` | `{'K-Means': {'blurb': 'Partition into k blobs by repeated…` |

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
| `_finite_or_none` | `(x)` | Return ``x`` if it is a finite number, otherwise ``None`` (JSON-safe). |
| `full_metrics` | `(P, labels, centroids=None, rng=None)` | Cheap metrics plus silhouette and Davies-Bouldin scores (JSON-safe). |
| `_inset` | `(kind, title, subtitle='', **payload)` | Build the algorithm-specific *detail view* payload for the UI inset. |
| `_n` | `(v, p=3)` | Format one number for a worked example (compact, never NaN/inf). |
| `_eq` | `(title, formula, lines, result=None, note='')` | Build the *worked example* payload shown in the equation box. |
| `_p` | `(key, label, typ, default, mn=None, mx=None, step=None, options=None, ` | Build one parameter-spec dict for the algorithm panel schema. |
| `algorithm_schema` | `()` | JSON-friendly description of every algorithm + params (drives the UI). |
