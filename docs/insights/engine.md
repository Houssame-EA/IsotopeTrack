# `engine.py`

The Insights engine: what to search, and the detectors that search it.

The pipeline has four stages:

``resolve_scope``
    Collects every loaded sample and works out its replicate groups (see
    :mod:`results.insights.replicates`). Canvas selection and element choices
    are never consulted, so a finding can surface anywhere.

``gather_scope_data``
    Collects the raw particle dicts for that scope. Cheap enough for the GUI
    thread, which keeps the scene off the worker thread entirely.

``build_context_from``
    Turns those particles into an :class:`AnalysisContext`: the element
    matrix, detection masks and per-sample index every detector shares.
    Results are cached by scope fingerprint.

``_AnalysisWorker``
    Runs the detectors on a background thread, per replicate group where a
    detector looks inside one material, and emits :class:`Suggestion` objects.

The panel that shows the suggestions lives in :mod:`results.insights.panel`;
the extra detectors in :mod:`results.insights.discovery`.

---

## Constants

| Name | Value |
|------|-------|
| `_FONT` | `'Segoe UI'` |
| `MIN_CORR_OVERLAP` | `25` |
| `FDR_Q` | `0.05` |
| `MIN_ABS_CORRELATION` | `0.5` |
| `MAX_CORRELATION_CARDS` | `4` |
| `BIMODALITY_SCAN_ORDER` | `('element_diameter_nm', 'particle_diameter_nm', 'element_…` |
| `MIN_BIMODALITY_PARTICLES` | `60` |
| `BIMODALITY_KDE_SAMPLE` | `4000` |
| `MIN_MODE_SEPARATION` | `0.3` |
| `MIN_MINOR_MODE_SHARE` | `0.1` |
| `MIN_VALLEY_DEPTH` | `0.4` |
| `MAX_BIMODALITY_CARDS` | `3` |
| `SIGNATURE_ABSENCE_RATIO` | `0.3` |
| `SIGNATURE_MIN_COMBO_GAP` | `0.12` |
| `_SAMPLE_NODE_TYPES` | `('sample_selector', 'multiple_sample_selector')` |
| `_CTX_CACHE_MAX` | `3` |
| `_CTX_LOCK` | `threading.Lock()` |
| `MIN_GROUP_FOLD` | `1.5` |
| `_REGISTRY` | `(('interference', _disc.analyse_interference, 'within', {…` |
| `_DEFAULT_CARD_LIMIT` | `1` |
| `FOCUSED_CARD_LIMIT` | `12` |
| `_MULTI_SAMPLE_CATEGORIES` | `('comparison', 'signature')` |
| `MIN_WITHIN_GROUP_PARTICLES` | `20` |

## Classes

### `Suggestion`

One proposed plot node, rendered as a card in the panel.

Attributes:
    title: Short headline shown on the card, e.g. ``"56Fe vs 55Mn"``.
    reasoning: Sentence explaining why this was surfaced, including the
        statistics behind it.
    category: Key into :data:`_CAT_META`, controlling the card's icon and
        label.
    confidence: Ranking weight in ``0.0`` to ``1.0``. This is a heuristic
        priority score used for sorting and deduplication, not a
        statistical confidence level.
    node_type: Key into ``widget.canvas_widgets._NODE_FACTORIES``, naming
        the node to create when the card's Add button is pressed.
    config: Pre-set configuration merged into the new node, such as the
        elements to plot on each axis.
    elements: The elements this insight is actually about. Adding the card
        builds a sample selector narrowed to these, so the new branch
        carries only the relevant data. Left empty for insights that need
        the full element set to mean anything, such as the composition
        breakdown or the full correlation matrix.
    samples: The samples where the finding holds. Adding the card builds a
        selector over these samples only. Empty means every sample in scope.
    sample_groups: Sample to replicate group label for *samples*. A label
        makes the new selector pool that sample with the rest of its group;
        an empty label keeps it separate, as replicate checks need.
    explain_key: Which explanation in :mod:`results.insights.explain`
        describes this finding; the category when empty.
    details: ``(label, value)`` pairs with the numbers behind the finding,
        shown in the card's details section.

| Method | Signature | Description |
|--------|-----------|-------------|
| `confidence_label` | `(self) → str` | Bucket the confidence score as ``"high"``, ``"medium"`` or ``"low"``. |

### `AnalysisScope`

Which samples the Insights engine looks at, and how they group.

Insights always searches every loaded sample and every element, whatever
is selected on the canvas, so that a finding can surface anywhere. Each
card then narrows the node it builds to the samples and elements the
finding is about.

Attributes:
    sample_names: The samples to analyse, in load order.
    origin: Where the samples came from. ``"all"`` for the loaded pool;
        ``"batch"`` when a batch node supplies them.
    counts: Particle count per entry in *sample_names*, index aligned.
    pool_ids: Identity of each sample's particle list, index aligned. Two
        different datasets can share a name and a particle count, so the
        counts alone are not enough to tell cached contexts apart.
    groups: Replicate groups covering *sample_names*, see
        :mod:`results.insights.replicates`.

| Method | Signature | Description |
|--------|-----------|-------------|
| `key` | `(self) → str` | Return the cache fingerprint for this scope. |
| `total_particles` | `(self) → int` | Return the number of particles across every sample in scope. |
| `is_multi` | `(self) → bool` | Return whether the scope spans more than one sample. |
| `has_several_groups` | `(self) → bool` | Return whether there is more than one group to compare. |
| `origin_label` | `(self) → str` | Return a human-readable form of :attr:`origin` for the panel. |
| `grouping_label` | `(self) → str` | Return a short description of the replicate grouping. |
| `group_of` | `(self, sample: str) → ReplicateGroup \| None` | Return the replicate group holding *sample*, if any. |

### `AnalysisContext`

Precomputed data shared by every analysis run against one scope.

Building this is the expensive part of the panel, so it happens once per
scope and is reused across insight categories.

Attributes:
    scope: The scope this context was built for.
    particles: The particle dicts in scope, concatenated sample by sample.
    matrix: Element label to concentration array, zero-filled at
        non-detects. Every array is ``n`` long.
    det_mask: Element label to boolean detection array, distinguishing a
        non-detect from a measured zero.
    det_counts: Element label to the number of particles detecting it.
    sample_idx: For each particle, the index of its sample within
        ``scope.sample_names``. This is what lets between-sample analyses
        group particles that carry no ``source_sample`` key of their own.
    unit_matrices: Matrices for measurements other than raw counts, built
        on first use and keyed by data key. Scanning sizes costs nothing
        until something actually asks for them.
    cache: Scratch space detectors use to share derived arrays, such as
        the number of elements per particle.
    label: Which part of the scope this context covers: empty for the
        whole scope, or a replicate group's name for a group subset.

| Method | Signature | Description |
|--------|-----------|-------------|
| `n` | `(self) → int` | Return the number of particles in the context. |
| `sample_names` | `(self) → list[str]` | Return the scope's sample names as a list. |
| `is_multi` | `(self) → bool` | Return whether the context spans more than one sample. |
| `elements_by_abundance` | `(self) → list[str]` | Rank every element by how many particles detected it. |
| `frequent_elements` | `(self, min_frac: float=0.04, min_abs: int=5) → list[str]` | Select the elements detected often enough to be worth testing. |
| `matrix_for` | `(self, data_key: str) → tuple[dict[str, np.ndarray], dict[str, np.ndar` | Return the matrix and detection mask for one measurement. |
| `available_data_keys` | `(self, sample_size: int=400) → list[str]` | List the measurements these particles actually carry. |
| `subset` | `(self, mask: np.ndarray, label: str='') → 'AnalysisContext'` | Return a context over the particles where *mask* is true. |
| `group_mask` | `(self, group: ReplicateGroup) → np.ndarray` | Mark the particles belonging to the samples of *group*. |
| `particle_mask_for` | `(self, elements) → np.ndarray` | Mark the particles carrying at least one of *elements*. |

### `InsightCategory`

One detector in the discovery engine.

Attributes:
    key: Identifier, and the default ``category`` of its suggestions.
    label: Human-readable name.
    icon: Glyph shown on cards of this kind.
    run: Callable taking ``(ctx, progress)`` and returning suggestions.
    kind: ``"within"`` for detectors that look inside one material and are
        run once per replicate group; ``"across"`` for detectors that
        compare samples or groups and see the whole scope.
    node_types: Plot nodes the detector can propose. Ticking a node type
        in the panel runs every detector that can feed it.

### `_AnalysisWorker` *(extends `QThread`)*

Background thread that turns particle data into :class:`Suggestion` cards.

The worker is handed plain data rather than the scene, so it never touches
Qt objects owned by the GUI thread. It is single-use: construct one per
analysis and discard it when finished.

Signals:
    results_ready: Emitted once with the final list of suggestions. Named
        to avoid shadowing ``QThread.finished``, which the panel relies on
        to know when a cancelled thread has actually exited.
    partial: Emitted after each detector with its suggestions and its
        key, so the panel can show findings as soon as they exist.
    progress: Emitted with a short status string as each stage begins.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, scope: AnalysisScope, particles: list[dict], sample_idx: np.nda` | Prepare an analysis run. |
| `cancel` | `(self) → None` | Ask the run to stop at the next stage boundary. |
| `_stop` | `(self) → bool` | Return whether :meth:`cancel` has been called. |
| `run` | `(self)` | Analyse the particles and emit the resulting suggestions. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_safe_float` | `(v) → float \| None` | Coerce *v* to a positive float, or ``None`` if it is not usable. |
| `_build_matrix` | `(particles: list[dict], data_key: str='elements') → tuple[dict[str, np` | Build the element matrix in a single sparse pass. |
| `_correlate_pair` | `(a: np.ndarray, b: np.ndarray, min_overlap: int=MIN_CORR_OVERLAP) → di` | Correlate two element columns both parametrically and by rank. |
| `_fmt_q` | `(q: float) → str` | Write a corrected p-value for a card, without printing a bare zero. |
| `correlated_pairs` | `(ctx, elements) → list[tuple[str, str, dict]]` | Correlate every pair of *elements*, reusing results already computed. |
| `_proportionality` | `(a: np.ndarray, b: np.ndarray) → float \| None` | Measure how close two elements are to a fixed ratio. |
| `_benjamini_hochberg` | `(pvalues: list[float], q: float=FDR_Q) → tuple[np.ndarray, np.ndarray]` | Control the false discovery rate across a family of tests. |
| `_bimodality_coefficient` | `(values: np.ndarray) → float` | Score how two-humped a distribution looks, from skewness and kurtosis. |
| `_detect_bimodality` | `(values: np.ndarray, min_separation: float=MIN_MODE_SEPARATION) → dict` | Look for two separated populations in one element's measurements. |
| `_isotope_symbol` | `(name: str) → str \| None` | Extract the element symbol from an isotope label. |
| `_group_isotopes` | `(elements: list[str]) → dict[str, list[str]]` | Group isotope labels by their shared element symbol. |
| `_find_batch_node` | `(scene)` | Find the batch node feeding the canvas, if there is one. |
| `_samples_of_node` | `(node) → list[str]` | List the samples a selector node refers to. |
| `_dedupe` | `(seq) → list[str]` | Drop duplicates and falsy entries while preserving order. |
| `_raw_pool` | `(scene, parent_window) → dict[str, list[dict]]` | Collect every loaded particle, grouped by sample, with all elements intact. |
| `resolve_scope` | `(scene, parent_window) → AnalysisScope` | Collect every loaded sample and work out its replicate groups. |
| `gather_scope_data` | `(scene, parent_window, scope: AnalysisScope) → tuple[list[dict], np.nd` | Collect the particle list for *scope*. |
| `build_context_from` | `(scope: AnalysisScope, particles: list[dict], sample_idx: np.ndarray) ` | Build an :class:`AnalysisContext`, reusing a cached one when possible. |
| `build_context` | `(scene, parent_window, scope: AnalysisScope \| None=None) → AnalysisCon` | Resolve, gather and build a context in one call. |
| `invalidate_context_cache` | `() → None` | Drop every cached context. |
| `_say` | `(progress, message: str) → None` | Report progress if the caller supplied a callback. |
| `_analyse_correlation` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Find element pairs that vary together. |
| `_analyse_isotope` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Examine isotope ratios within one material. |
| `_scan_bimodality` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Look for elements whose measurements fall into two separate populations. |
| `_analyse_distribution` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Describe the shape and spread of individual element distributions. |
| `_analyse_composition` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Summarise which element combinations particles actually contain. |
| `_comparison_groups` | `(ctx: AnalysisContext) → list[tuple[ReplicateGroup, list[int]]]` | List the replicate groups available for a between-group comparison. |
| `_group_selection` | `(groups) → dict` | Samples and selector grouping for a card about some replicate groups. |
| `_analyse_comparison` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Find elements whose signal differs between replicate groups. |
| `_group_rates` | `(ctx: AnalysisContext, mask: np.ndarray, indices: list[int]) → tuple[f` | Summarise how often *mask* is true across one group's replicates. |
| `_analyse_signature` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Find what one group of samples contains that another does not. |
| `_signature_combination` | `(ctx: AnalysisContext, groups) → Suggestion \| None` | Find an element combination that belongs to one group alone. |
| `_analyse_outlier` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Find elements with a detached population of unusually high particles. |
| `_analyse_joint_outlier` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Find particles that are extreme in more than one element at once. |
| `_analyse_anomaly` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Run every anomaly test the outlier category covers. |
| `category_keys` | `() → list[str]` | List the detectors in the order they run. |
| `node_type_keys` | `() → list[str]` | List the plot nodes Insights can propose, in panel order. |
| `analysers_for` | `(node_types) → list[str]` | Return the detectors needed to fill the given node types. |
| `_dedupe_suggestions` | `(suggestions: list[Suggestion], per_type_limit: int \| None=None) → lis` | Rank suggestions and drop the ones that repeat each other. |
| `_within_units` | `(ctx: AnalysisContext) → list[tuple[AnalysisContext, ReplicateGroup \| ` | Split the scope into the per-group contexts within-group detectors search. |
| `_run_detector` | `(ctx: AnalysisContext, analyser: InsightCategory, progress=None, shoul` | Run one detector the way its kind requires. |
| `analyse` | `(ctx: AnalysisContext, categories=None, progress=None, should_stop=Non` | Run detectors over *ctx* and collect their suggestions. |
| `context_for_stream` | `(data: dict \| None) → AnalysisContext \| None` | Build an analysis context from a canvas data stream. |
| `findings_for_stream` | `(data: dict \| None, limit: int=12, should_stop=None) → list[Suggestion` | Run every Insights detector over a canvas data stream. |
