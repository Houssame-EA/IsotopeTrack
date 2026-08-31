# `prep.py`

Shared preprocessing rules for every clustering entry point.

Keeps the ② Cluster tab, the ④ How it works view, the live panel and the sweep
tool agreeing on how the scaled matrix is reduced before clustering.

Every reduction parameter the app exposes is declared once here, in
:data:`DR_PARAM_SPECS`, and applied once here, in :func:`apply_reduction`. That
matters more than it looks: before this module owned them, the sweep, the
clustering matrix and the live projection each built their own t-SNE with their
own hard-coded perplexity, so a pipeline the sweep ranked first could not be
reproduced by the tab the user then clicked into.

scikit-learn and umap are imported lazily inside the functions that need them,
so importing this module stays cheap for callers that only want
:func:`reduction_components`.

---

## Constants

| Name | Value |
|------|-------|
| `EMBED_DIMS` | `3` |
| `KEEP_ALL` | `'all'` |
| `DR_METRIC_OPTIONS` | `['euclidean', 'manhattan', 'cosine', 'chebyshev', 'correl…` |
| `DR_PARAM_SPECS` | `{'None': {'params': {}}, 'PCA': {'params': {'n_components…` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `dr_defaults` | `(dim_reduction)` | Return ``{param: default}`` for one reduction. |
| `dr_params_str` | `(dim_reduction, params)` | Return a compact human-readable parameter string for a reduction. |
| `non_default_dr_params` | `(dim_reduction, params)` | Return only the parameters that differ from the reduction's defaults. |
| `reduction_components` | `(dim_reduction, n_features)` | Number of components to keep for ``dim_reduction`` by default. |
| `supported_kwargs` | `(cls, kwargs)` | Drop keyword arguments the estimator does not accept. |
| `n_components_value` | `(raw, dim_reduction, n_features, n_samples)` | Resolve an ``n_components`` selection to what the estimator should get. |
| `learning_rate_value` | `(raw)` | Resolve a t-SNE learning rate, which may be the string ``'auto'``. |
| `reduction_kwargs` | `(dim_reduction, params, n_samples, n_features, n_components=None, defa` | Build the estimator keyword arguments for one reduction. |
| `apply_reduction` | `(dim_reduction, m, params=None, default_random_state=42)` | Reduce ``m`` with ``dim_reduction`` under ``params``. |
