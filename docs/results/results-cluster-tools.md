# `results_cluster_tools.py`

Custom Cluster Test — exhaustive pipeline search against known components.

---

## Constants

| Name | Value |
|------|-------|
| `EXTERNAL_METRICS` | `{'ARI': {'display': 'Adjusted Rand Index', 'func': lambda…` |
| `DEFAULT_EXTERNAL_METRICS` | `['ARI', 'AMI', 'V-measure']` |
| `PRIMARY_EXTERNAL_METRIC` | `'ARI'` |
| `OTHER_LABEL_NAME` | `'other'` |
| `ALGO_PARAM_SPECS` | `{'K-Means': {'density': False, 'needs_k': True, 'params':…` |
| `ALGORITHMS` | `list(ALGO_PARAM_SPECS.keys())` |
| `DATA_TYPES` | `list(DATA_KEY_MAP.keys())` |
| `SCALINGS` | `['None', 'Robust Z-score', 'CLR', 'ILR']` |
| `DIM_REDUCTIONS` | `['None', 'PCA', 't-SNE']` |
| `DEFAULT_DATA_TYPES` | `['Counts']` |
| `DEFAULT_SCALINGS` | `['None']` |
| `DEFAULT_DIM_REDUCTIONS` | `['None']` |
| `DEFAULT_ALGORITHMS` | `['K-Means']` |

## Classes

### `Preprocessor`

Builds and caches preprocessed matrices for the sweep.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, particle_data, elements, filter_zeros=True, tsne_random_state=4` | Initialise the cache and the fixed kept-row mask. |
| `n_rows` | `(self)` | Number of kept particles. |
| `raw_matrix` | `(self, data_type)` | Return the kept, unscaled matrix for ``data_type`` (cached). |
| `counts_matrix` | `(self)` | Return the kept count matrix used to build ground truth. |
| `_scaled` | `(self, data_type, scaling)` | Return the scaled matrix for one ``(data_type, scaling)`` (cached). |
| `matrix` | `(self, data_type, scaling, dim_reduction)` | Return the fully preprocessed matrix for one pipeline (cached). |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_v_measure` | `(truth, pred)` | V-measure (harmonic mean of homogeneity and completeness). |
| `_homogeneity` | `(truth, pred)` | Homogeneity score: each cluster contains a single truth class. |
| `_completeness` | `(truth, pred)` | Completeness score: each truth class falls into a single cluster. |
| `multiplicative_replacement` | `(matrix, frac=0.65, threshold=None)` | Replace zeros in a non-negative composition matrix without distorting ratios. |
| `parse_components` | `(text)` | Parse a component string into ``[(name, [elements]), ...]``. |
| `build_ground_truth` | `(raw_matrix, elements, components, other_flags=None)` | Assign each particle to a named component or to ``"other"``. |
| `_row_for_particle` | `(p, data_type, elements)` | Build one matrix row for a particle in the requested representation. |
| `run_algorithm` | `(name, params, data, som_runner=None)` | Fit one algorithm with explicit ``params`` and return integer labels. |
| `make_host_som_runner` | `(host_dialog)` | Build a SOM runner that does not disturb the host's SOM tab state. |
| `build_param_grid` | `(name, selections)` | Expand per-parameter value lists into concrete parameter dicts. |
| `count_combinations` | `(pre_combos, algo_selections)` | Return the total number of fits a sweep would perform. |
| `_params_str` | `(algo, params)` | Return a compact human-readable parameter string for a result row. |
| `run_sweep` | `(particle_data, elements, components, *, data_types, scalings, dim_red` | Run the full pipeline grid and score every result against ground truth. |
| `rank_results` | `(results, metric=PRIMARY_EXTERNAL_METRIC)` | Return results sorted best-first by ``metric`` (NaNs last). |
| `_spearman` | `(a, b)` | Return the tie-corrected Spearman rank correlation of two sequences. |
| `borda_count_rank` | `(results, metrics, registry=None)` | Rank results by Borda count across *metrics* (internal or external). |
| `analyze_metric_trust` | `(results, internal_metrics, reference=PRIMARY_EXTERNAL_METRIC)` | Report how well each internal index tracks the ground-truth reference. |
| `analyze_metric_trust_stratified` | `(results, internal_metrics, reference=PRIMARY_EXTERNAL_METRIC, min_per` | Validate each internal index against ground truth within fixed preprocessing. |
| `summarize_sweep_failures` | `(failures, total=None)` | Summarise where a sweep produced no usable partition, per algorithm. |
| `per_cluster_silhouette` | `(data, labels)` | Return the mean silhouette width of each individual cluster. |
