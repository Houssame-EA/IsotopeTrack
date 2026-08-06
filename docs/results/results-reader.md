# `results_reader.py`

Smart Insights for the Workflow Builder canvas.

This module analyses the particle data behind the canvas and proposes plot
nodes worth adding, presented as cards in a dockable side panel.

The pipeline has four stages:

``resolve_scope``
    Decides *which samples* to analyse. Priority runs from the currently
    selected sample node, to the union of every sample node on the canvas, to
    every loaded sample. Element selection is deliberately never consulted, so
    insights can surface patterns in elements the user has not picked.

``gather_scope_data``
    Collects the raw particle dicts for that scope. Cheap enough for the GUI
    thread, which keeps the scene off the worker thread entirely.

``build_context_from``
    Turns those particles into an :class:`AnalysisContext` — the element
    matrix, detection masks and per-sample index that every analysis shares.
    Results are cached by scope fingerprint.

``_AnalysisWorker``
    Runs the statistical tests on a background thread and emits a list of
    :class:`Suggestion` objects for the panel to render.

Public entry points for the canvas dialog are :func:`integrate_insights_panel`
and :func:`make_insights_toggle_button`.

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
| `MIN_MODE_SEPARATION` | `0.3` |
| `MIN_MINOR_MODE_SHARE` | `0.1` |
| `MIN_VALLEY_DEPTH` | `0.4` |
| `MAX_BIMODALITY_CARDS` | `3` |
| `SIGNATURE_ABSENCE_RATIO` | `0.3` |
| `SIGNATURE_MIN_COMBO_GAP` | `0.12` |
| `_SAMPLE_NODE_TYPES` | `('sample_selector', 'multiple_sample_selector')` |
| `_NODE_SLOT_W` | `150` |
| `_NODE_SLOT_H` | `125` |
| `_SLOT_SPAN` | `6` |
| `_CTX_CACHE_MAX` | `3` |
| `_CTX_LOCK` | `threading.Lock()` |
| `_DEFAULT_CARD_LIMIT` | `1` |
| `_MULTI_SAMPLE_CATEGORIES` | `('comparison', 'signature')` |

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

| Method | Signature | Description |
|--------|-----------|-------------|
| `confidence_label` | `(self) → str` | Bucket the confidence score as ``"high"``, ``"medium"`` or ``"low"``. |

### `AnalysisScope`

Which samples the Insights engine should look at, and why.

Attributes:
    sample_names: The samples to analyse, in display order.
    origin: How the scope was arrived at. ``"selection"`` means it came
        from the sample node the user has selected, ``"canvas"`` from the
        union of every sample node present, and ``"all"`` from everything
        loaded because the canvas offered no sample nodes.
    counts: Particle count per entry in *sample_names*, index aligned.
    pool_ids: Identity of each sample's particle list, index aligned. Two
        different datasets can share a name and a particle count, so the
        counts alone are not enough to tell cached contexts apart.

| Method | Signature | Description |
|--------|-----------|-------------|
| `key` | `(self) → str` | Return the cache fingerprint for this scope. |
| `total_particles` | `(self) → int` | Return the number of particles across every sample in scope. |
| `is_multi` | `(self) → bool` | Return whether the scope spans more than one sample. |
| `origin_label` | `(self) → str` | Return a human-readable form of :attr:`origin` for the panel. |

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

| Method | Signature | Description |
|--------|-----------|-------------|
| `n` | `(self) → int` | Return the number of particles in the context. |
| `sample_names` | `(self) → list[str]` | Return the scope's sample names as a list. |
| `is_multi` | `(self) → bool` | Return whether the context spans more than one sample. |
| `elements_by_abundance` | `(self) → list[str]` | Rank every element by how many particles detected it. |
| `frequent_elements` | `(self, min_frac: float=0.04, min_abs: int=5) → list[str]` | Select the elements detected often enough to be worth testing. |
| `matrix_for` | `(self, data_key: str) → tuple[dict[str, np.ndarray], dict[str, np.ndar` | Return the matrix and detection mask for one measurement. |
| `available_data_keys` | `(self, sample_size: int=400) → list[str]` | List the measurements these particles actually carry. |
| `particle_mask_for` | `(self, elements) → np.ndarray` | Mark the particles carrying at least one of *elements*. |

### `InsightCategory`

One family of tests the user can run from the panel.

Attributes:
    key: Identifier, also the ``category`` on suggestions it produces.
    label: Text for the chip.
    icon: Glyph shown beside the label.
    run: Callable taking ``(ctx, progress)`` and returning suggestions.

### `_AnalysisWorker` *(extends `QThread`)*

Background thread that turns particle data into :class:`Suggestion` cards.

The worker is handed plain data rather than the scene, so it never touches
Qt objects owned by the GUI thread. It is single-use: construct one per
analysis and discard it when finished.

Signals:
    results_ready: Emitted once with the final list of suggestions. Named
        to avoid shadowing ``QThread.finished``, which the panel relies on
        to know when a cancelled thread has actually exited.
    progress: Emitted with a short status string as each stage begins.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, scope: AnalysisScope, particles: list[dict], sample_idx: np.nda` | Prepare an analysis run. |
| `cancel` | `(self) → None` | Ask the run to stop at the next stage boundary. |
| `_stop` | `(self) → bool` | Return whether :meth:`cancel` has been called. |
| `run` | `(self)` | Analyse the particles and emit the resulting suggestions. |

### `_Card` *(extends `QFrame`)*

One suggestion rendered as a card in the panel.

Shows the category tag, title, reasoning and a confidence bar, with an Add
button that hands the suggestion back to the panel. Colours come from the
active theme palette rather than per-category accents, so a list of cards
reads as one surface.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, s: Suggestion, on_add, parent=None)` | Build a card for one suggestion. |
| `_build` | `(self)` | Lay out and style the card's contents. |
| `_clicked` | `(self)` | Hand the suggestion to the panel and flash the card as feedback. |

### `SmartInsightsPanel` *(extends `QWidget`)*

Resizable pane holding the suggestion cards.

Embedded as the rightmost pane of the canvas splitter and hidden by default,
toggled by the button from :func:`make_insights_toggle_button`.

Analysis runs on a background worker and refreshes when the panel becomes
visible or when the user presses the re-analyse button. Because the scope
follows the canvas selection, selecting a different sample node updates the
header strip immediately, though it does not re-run the analysis on its own.

Use :func:`integrate_insights_panel` to construct and attach one rather than
instantiating this directly.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, scene, parent_window, parent=None)` | Build the panel and subscribe it to theme and selection changes. |
| `_build_ui` | `(self)` | Assemble the header, sample strip, card scroll area and footer. |
| `_apply_theme` | `(self)` | Restyle the panel chrome from the current theme palette. |
| `run_category` | `(self, key: str, force: bool=False)` | Scan one category of insights and show the result. |
| `refresh` | `(self)` | Rescan the active category, discarding anything remembered. |
| `_forget_results` | `(self)` | Drop remembered results and reset the chips to their idle labels. |
| `_sync_chips` | `(self, scope: AnalysisScope \| None=None)` | Update which chip reads as active and which are worth offering. |
| `_on_scene_selection` | `(self, *_)` | React to the canvas selection changing the scope. |
| `_stop_worker` | `(self)` | Cancel any in-flight analysis and stop listening to it. |
| `_update_sample_strip` | `(self, scope: AnalysisScope \| None=None)` | Show which samples will be analysed, and why those. |
| `_on_done` | `(self, suggestions: list[Suggestion], remember: bool=True)` | Render a finished scan and record its result on the chip. |
| `_rebuild_cards` | `(self)` | Replace the card list with one card per current suggestion. |
| `_empty_message` | `(self) → str` | Explain why a scan produced no cards. |
| `_idle_message` | `(self) → str` | Describe what a scan would cover, before any category is picked. |
| `_show_empty` | `(self)` | Display the empty-state message in place of the cards. |
| `_show_idle` | `(self)` | Display the idle prompt shown before anything has been scanned. |
| `_show_placeholder` | `(self, text: str)` | Put a centred muted message where the cards would go. |
| `_clear_cards` | `(self)` | Remove every card, leaving the trailing stretch in place. |
| `_add_suggestion` | `(self, s: Suggestion)` | Build the branch a suggestion describes and wire it into the canvas. |
| `_build_scoped_selector` | `(self, s: Suggestion, factories: dict)` | Create a sample selector holding the insight's elements only. |
| `_flash_status` | `(self, message: str, msec: int=2600)` | Show a transient message in the status line. |
| `showEvent` | `(self, event)` | Show what is in scope without analysing anything. |
| `_show_scope_only` | `(self)` | Refresh the scope display and prompt for a category. |
| `closeEvent` | `(self, event)` | Release resources if the panel is ever closed directly. |
| `_teardown` | `(self)` | Drop the theme subscription and stop any running analysis. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_safe_float` | `(v) → float \| None` | Coerce *v* to a positive float, or ``None`` if it is not usable. |
| `_build_matrix` | `(particles: list[dict], data_key: str='elements') → tuple[dict[str, np` | Build the element matrix in a single sparse pass. |
| `_correlate_pair` | `(a: np.ndarray, b: np.ndarray, min_overlap: int=MIN_CORR_OVERLAP) → di` | Correlate two element columns both parametrically and by rank. |
| `_benjamini_hochberg` | `(pvalues: list[float], q: float=FDR_Q) → tuple[np.ndarray, np.ndarray]` | Control the false discovery rate across a family of tests. |
| `_bimodality_coefficient` | `(values: np.ndarray) → float` | Score how two-humped a distribution looks, from skewness and kurtosis. |
| `_detect_bimodality` | `(values: np.ndarray) → dict \| None` | Look for two separated populations in one element's measurements. |
| `_isotope_symbol` | `(name: str) → str \| None` | Extract the element symbol from an isotope label. |
| `_group_isotopes` | `(elements: list[str]) → dict[str, list[str]]` | Group isotope labels by their shared element symbol. |
| `_find_source_node` | `(scene) → object \| None` | Find the node a newly added plot node should be wired to. |
| `_find_batch_node` | `(scene)` | Find the batch node feeding the canvas, if there is one. |
| `_occupied_rects` | `(scene) → list[tuple[float, float, float, float]]` | List the space every node on the canvas already takes up. |
| `_free_position` | `(scene, preferred)` | Find a spot for a new node that no existing node is sitting on. |
| `_isotope_entries` | `(parent_window, scene, labels) → list[dict]` | Resolve element labels into the isotope records a selector expects. |
| `_samples_of_node` | `(node) → list[str]` | List the samples a selector node refers to. |
| `_dedupe` | `(seq) → list[str]` | Drop duplicates and falsy entries while preserving order. |
| `_raw_pool` | `(scene, parent_window) → dict[str, list[dict]]` | Collect every loaded particle, grouped by sample, with all elements intact. |
| `resolve_scope` | `(scene, parent_window) → AnalysisScope` | Decide which samples to analyse. |
| `gather_scope_data` | `(scene, parent_window, scope: AnalysisScope) → tuple[list[dict], np.nd` | Collect the particle list for *scope*. |
| `build_context_from` | `(scope: AnalysisScope, particles: list[dict], sample_idx: np.ndarray) ` | Build an :class:`AnalysisContext`, reusing a cached one when possible. |
| `build_context` | `(scene, parent_window, scope: AnalysisScope \| None=None) → AnalysisCon` | Resolve, gather and build a context in one call. |
| `invalidate_context_cache` | `() → None` | Drop every cached context. |
| `_say` | `(progress, message: str) → None` | Report progress if the caller supplied a callback. |
| `_analyse_correlation` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Find element pairs that vary together. |
| `_analyse_isotope` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Find isotope pairs worth plotting as a ratio. |
| `_scan_bimodality` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Look for elements whose measurements fall into two separate populations. |
| `_analyse_distribution` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Describe the shape and spread of individual element distributions. |
| `_analyse_composition` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Summarise which element combinations particles actually contain. |
| `_analyse_comparison` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Find elements whose concentrations differ between samples. |
| `_analyse_signature` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Find what one sample contains that another does not. |
| `_signature_combination` | `(ctx: AnalysisContext, usable, sizes, names) → Suggestion \| None` | Find an element combination that belongs to one sample alone. |
| `_analyse_outlier` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Find elements with a detached population of unusually high particles. |
| `_analyse_joint_outlier` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Find particles that are extreme in more than one element at once. |
| `_analyse_anomaly` | `(ctx: AnalysisContext, progress=None) → list[Suggestion]` | Run every anomaly test the outlier category covers. |
| `category_keys` | `() → list[str]` | List the analysis categories in the order the panel shows them. |
| `_dedupe_suggestions` | `(suggestions: list[Suggestion]) → list[Suggestion]` | Rank suggestions and drop the ones that repeat each other. |
| `analyse` | `(ctx: AnalysisContext, categories=None, progress=None, should_stop=Non` | Run one or more categories of analysis over *ctx*. |
| `integrate_insights_panel` | `(canvas_dialog, splitter: QSplitter) → SmartInsightsPanel` | Append a :class:`SmartInsightsPanel` as the rightmost pane of *splitter*. |
| `make_insights_toggle_button` | `(canvas_dialog, splitter: QSplitter) → QPushButton` | Create the header button that shows and hides the insights panel. |
