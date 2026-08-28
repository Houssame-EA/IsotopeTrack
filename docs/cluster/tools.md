# `tools.py`

Custom Cluster Test — exhaustive pipeline search against known components.

Standalone companion to ``dialog.py``.  It reads the same input data
and re-uses a few side-effect-free helpers when importable, but never modifies
the existing clustering behaviour.

You provide the components you prepared (for example ``Ag ; Ti ; Ce ; FeNiCo``)
and the tool sweeps a grid of complete pipelines — data type, scaling,
dimensionality reduction, algorithm and that algorithm's own hyper-parameters
(including the cluster count, left open) — scoring every result against the
ground truth derived from your component list, using external validity indices
(Adjusted Rand Index, AMI, V-measure, …) alongside the usual internal indices
(Silhouette, Calinski-Harabasz, …).

It answers two questions: which complete pipeline best reproduces your known
components, and which scoring metric to trust when no ground truth is available
(by correlating each internal metric against the external truth across the grid).

Ground truth is decided by each particle's elemental combination: a particle
belongs to a named component when the set of elements it contains is exactly the
set that component names, so ``107Ag``, ``197Au`` and ``107Ag+197Au`` are three
separate truth groups.  Everything else is the ``"other"`` group (unnamed
combinations, coincidences, outliers, background).  Nothing is excluded; a
pipeline that parks ``"other"`` particles in a noise label or its own cluster is
rewarded for it.

The engine (everything above the GUI guard) has no Qt dependency and is fully
usable and testable on its own.  The GUI is defined only when PySide6 imports.

---

## Constants

| Name | Value |
|------|-------|
| `EMBED_DIMS` | `_prep.EMBED_DIMS` |
| `KEEP_ALL` | `_prep.KEEP_ALL` |
| `DR_METRIC_OPTIONS` | `_prep.DR_METRIC_OPTIONS` |
| `DR_PARAM_SPECS` | `_prep.DR_PARAM_SPECS` |
| `EXTERNAL_METRICS` | `{'ARI': {'display': 'Adjusted Rand Index', 'func': lambda…` |
| `DEFAULT_EXTERNAL_METRICS` | `['ARI', 'AMI', 'V-measure']` |
| `PRIMARY_EXTERNAL_METRIC` | `'ARI'` |
| `OTHER_LABEL_NAME` | `'other'` |
| `DEFAULT_COMPOSITION_TOL` | `10.0` |
| `ALGO_PARAM_SPECS` | `{'K-Means': {'density': False, 'needs_k': True, 'params':…` |
| `ALGORITHMS` | `list(ALGO_PARAM_SPECS.keys())` |
| `DATA_TYPES` | `list(DATA_KEY_MAP.keys())` |
| `SCALINGS` | `['None', 'Robust Z-score', 'CLR', 'ILR']` |
| `DIM_REDUCTIONS` | `['None', 'PCA', 't-SNE'] + (['UMAP'] if _UMAP_OK else [])` |
| `DEFAULT_DATA_TYPES` | `['Counts']` |
| `DEFAULT_SCALINGS` | `['None']` |
| `DEFAULT_DIM_REDUCTIONS` | `['None']` |
| `DEFAULT_ALGORITHMS` | `['K-Means']` |
| `_TOL_RE` | `re.compile('\\s*[~±]\\s*([0-9]*\\.?[0-9]+)\\s*%?\\s*$')` |

## Classes

### `Preprocessor`

Builds and caches preprocessed matrices for the sweep.

Each ``(data_type, scaling, dim_reduction, params)`` matrix is computed once
and reused across every algorithm and cluster count, which is what keeps a large
grid tractable.  The kept-row set is fixed once from the count matrix so
ground-truth labels stay aligned across all data types.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, particle_data, elements, filter_zeros=True, tsne_random_state=4` | Initialise the cache and the fixed kept-row mask. |
| `n_rows` | `(self)` | Number of kept particles. |
| `raw_matrix` | `(self, data_type)` | Return the kept, unscaled matrix for ``data_type`` (cached). |
| `counts_matrix` | `(self)` | Return the kept count matrix used to build ground truth. |
| `_scaled` | `(self, data_type, scaling)` | Return the scaled matrix for one ``(data_type, scaling)`` (cached). |
| `matrix` | `(self, data_type, scaling, dim_reduction, params=None)` | Return the fully preprocessed matrix for one pipeline (cached). |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_v_measure` | `(truth, pred)` | V-measure (harmonic mean of homogeneity and completeness). |
| `_homogeneity` | `(truth, pred)` | Homogeneity score: each cluster contains a single truth class. |
| `_completeness` | `(truth, pred)` | Completeness score: each truth class falls into a single cluster. |
| `parse_components` | `(text)` | Parse a component string into ``[(name, [elements], spec), ...]``. |
| `_element_symbol` | `(label)` | Bare element symbol from a column or component token. |
| `resolve_components` | `(components, elements)` | Match parsed components to data columns and report what was dropped. |
| `build_ground_truth` | `(raw_matrix, elements, components, other_flags=None, presence_threshol` | Assign each particle to a named component or to ``"other"``. |
| `_row_for_particle` | `(p, data_type, elements)` | Build one matrix row for a particle in the requested representation. |
| `_freeze_params` | `(params)` | Return a hashable, order-independent key for a parameter dict. |
| `zero_row_count` | `(data)` | Count rows that are zero in every column. |
| `constant_row_count` | `(data)` | Count rows whose values are identical across every column. |
| `metric_undefined` | `(name, params, data)` | Return True when the chosen metric has no defined answer on ``data``. |
| `run_algorithm` | `(name, params, data, som_runner=None, capture=None)` | Fit one algorithm with explicit ``params`` and return integer labels. |
| `make_host_som_runner` | `(host_dialog)` | Build a SOM runner that does not disturb the host's SOM tab state. |
| `build_param_grid` | `(name, selections)` | Expand per-parameter value lists into concrete parameter dicts. |
| `build_dr_param_grid` | `(name, selections)` | Expand one reduction's per-parameter value lists into parameter dicts. |
| `normalize_dr_selections` | `(dim_reductions=None, dr_selections=None)` | Return ``{reduction: {param: [values]}}`` from either calling style. |
| `expand_pre_combos` | `(data_types, scalings, dr_map)` | Build the preprocessing axis as ``(data_type, scaling, reduction, params)``. |
| `_best_dr_suffix` | `(row)` | Return ``" [perplexity=50, ...]"`` for a result row, or an empty string. |
| `count_combinations` | `(pre_combos, algo_selections)` | Return the total number of fits a sweep would perform. |
| `_params_str` | `(algo, params)` | Return a compact human-readable parameter string for a result row. |
| `run_sweep` | `(particle_data, elements, components, *, data_types, scalings, dim_red` | Run the full pipeline grid and score every result against ground truth. |
| `rank_results` | `(results, metric=PRIMARY_EXTERNAL_METRIC)` | Return results sorted best-first by ``metric`` (NaNs last). |
| `_spearman` | `(a, b)` | Return the tie-corrected Spearman rank correlation of two sequences. |
| `borda_count_rank` | `(results, metrics, registry=None)` | Rank results by Borda count across *metrics* (internal or external). |
| `analyze_metric_trust` | `(results, internal_metrics, reference=PRIMARY_EXTERNAL_METRIC)` | Report how well each internal index tracks the ground-truth reference. |
| `summarize_sweep_failures` | `(failures, total=None)` | Summarise where a sweep produced no usable partition, per algorithm. |
| `compact_payload` | `(payload)` | Return a sweep payload trimmed for long-term storage. |
| `per_cluster_silhouette` | `(data, labels)` | Return the mean silhouette width of each individual cluster. |
