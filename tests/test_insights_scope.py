# -*- coding: utf-8 -*-
"""Tests for the Insights engine in ``results.results_reader``.

Covers:

* ``_build_matrix`` — sparse element matrix and detection masks
* ``resolve_scope`` — selected node, then canvas union, then all loaded samples
* ``build_context`` and ``gather_scope_data`` — context assembly and caching
* the category registry and each analyser, including the statistics behind them
* ``_isotope_entries`` — resolving element labels for the Add flow
* ``_AnalysisWorker`` — end-to-end runs and cooperative cancellation

Only pure logic is exercised; no widgets are instantiated. The worker is driven
by calling ``run()`` directly on the test thread rather than ``start()``, so
results arrive synchronously.

Several tests use planted data — an element deliberately made to track another,
or two samples drawn from different distributions — alongside pure noise, so
that both the finding and the *not* finding are checked.
"""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from results import results_reader as rr


# ──────────────────────────────────────────────────────────────────────────────
# Fakes mirroring the canvas objects the resolver reads
# ──────────────────────────────────────────────────────────────────────────────

class FakeNode:
    """Stand-in for a workflow node, carrying whatever attributes a test needs."""

    def __init__(self, node_type, **kw):
        """Create a node of *node_type* with arbitrary extra attributes.

        Args:
            node_type: Value for the node's ``node_type`` attribute.
            **kw: Additional attributes to set, such as ``selected_sample``.
        """
        self.node_type = node_type
        self.__dict__.update(kw)


class FakeItem:
    """Stand-in for a graphics item wrapping a workflow node."""

    def __init__(self, node):
        """Wrap *node* the way ``NodeItem`` does.

        Args:
            node: The workflow node this item represents.
        """
        self.workflow_node = node


class FakeScene:
    """Stand-in for the canvas scene, exposing only what the resolver reads."""

    def __init__(self, nodes=(), selected=()):
        """Create a scene holding *nodes*, of which *selected* are selected.

        Args:
            nodes: Workflow nodes present on the canvas.
            selected: Subset of nodes to report as selected.
        """
        self.workflow_nodes = list(nodes)
        self._selected = [FakeItem(n) for n in selected]

    def selectedItems(self):
        """Return the selected items, as ``QGraphicsScene`` would."""
        return self._selected


class FakeWindow:
    """Stand-in for the main window, holding the loaded particle pool."""

    def __init__(self, pool):
        """Expose *pool* as ``sample_particle_data``.

        Args:
            pool: Sample name to list of particle dicts.
        """
        self.sample_particle_data = pool


def make_particles(n, elements, seed=0):
    """Generate synthetic particles with random concentrations.

    Args:
        n: How many particles to create.
        elements: Element label to the probability that it is detected in any
            given particle.
        seed: Seed for reproducibility.

    Returns:
        A list of particle dicts, each with an ``elements`` mapping holding
        only the elements that were detected.
    """
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        out.append({
            "elements": {el: rng.uniform(0.1, 100.0)
                         for el, prob in elements.items() if rng.random() < prob}
        })
    return out


def lognormal_particles(n, element, mu, sigma=0.5, seed=0):
    """Generate particles carrying one element with a log-normal spread.

    Args:
        n: How many particles to create.
        element: Element label to populate.
        mu: Mean of the underlying normal distribution.
        sigma: Standard deviation of the underlying normal distribution.
        seed: Seed for reproducibility.

    Returns:
        A list of particle dicts.
    """
    rng = random.Random(seed)
    return [{"elements": {element: math.exp(rng.gauss(mu, sigma))}}
            for _ in range(n)]


def correlated_particles(n=1200, seed=7):
    """Generate particles where one element tracks another and a third does not.

    ``55Mn`` is a fixed fraction of ``56Fe`` plus noise, while ``90Zr`` varies
    independently. Any correlation analysis should find the first pair and
    reject the second.

    Args:
        n: How many particles to create.
        seed: Seed for reproducibility.

    Returns:
        A list of particle dicts.
    """
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        elements = {}
        iron = math.exp(rng.gauss(2.0, 0.8))
        elements["56Fe"] = iron
        if rng.random() < 0.85:
            elements["55Mn"] = iron * rng.uniform(0.28, 0.34)
        if rng.random() < 0.60:
            elements["90Zr"] = math.exp(rng.gauss(1.0, 0.9))
        if rng.random() < 0.40:
            elements["27Al"] = math.exp(rng.gauss(0.5, 0.7))
        out.append({"elements": elements})
    return out


@pytest.fixture
def pool():
    """Return three samples with overlapping but distinct element sets."""
    return {
        "S1": make_particles(400, {"56Fe": 0.9, "55Mn": 0.8, "27Al": 0.5, "48Ti": 0.3}, 1),
        "S2": make_particles(300, {"56Fe": 0.7, "55Mn": 0.6, "90Zr": 0.4}, 2),
        "S3": make_particles(200, {"56Fe": 0.5, "27Al": 0.9}, 3),
    }


@pytest.fixture
def win(pool):
    """Return a fake main window exposing the sample pool."""
    return FakeWindow(pool)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Isolate each test from contexts cached by its neighbours."""
    rr.invalidate_context_cache()
    yield
    rr.invalidate_context_cache()


@pytest.fixture
def nodes():
    """Return one node of each kind the resolver cares about."""
    return {
        "single": FakeNode("sample_selector", selected_sample="S1"),
        "multi": FakeNode("multiple_sample_selector", selected_samples=["S2", "S3"]),
        "plot": FakeNode("correlation_plot"),
    }


# ──────────────────────────────────────────────────────────────────────────────
# _build_matrix
# ──────────────────────────────────────────────────────────────────────────────

def _naive_matrix(particles):
    """Build the element matrix the obvious way, as a reference to check against.

    Args:
        particles: Particle dicts.

    Returns:
        Element label to concentration array, zero-filled at non-detects.
    """
    all_els = {}
    for p in particles:
        for el in p.get("elements", {}):
            all_els.setdefault(el, [])
    for p in particles:
        els = p.get("elements", {})
        for el in all_els:
            v = els.get(el, 0)
            all_els[el].append(float(v) if isinstance(v, (int, float)) and v > 0 else 0.0)
    return {el: np.asarray(v) for el, v in all_els.items()}


def test_matrix_matches_naive_reference(pool):
    """The sparse build agrees with the naive one on values, masks and shape."""
    particles = pool["S1"]
    matrix, mask = rr._build_matrix(particles)
    ref = _naive_matrix(particles)

    assert set(matrix) == set(ref)
    for el, expected in ref.items():
        assert np.allclose(matrix[el], expected)
        assert np.array_equal(mask[el], expected > 0)
        assert len(matrix[el]) == len(particles)


def test_matrix_is_empty_for_no_particles():
    """An empty particle list yields empty dicts rather than raising."""
    assert rr._build_matrix([]) == ({}, {})


def test_mask_separates_non_detect_from_zero():
    """A missing element reads as zero in the matrix but false in the mask."""
    particles = [
        {"elements": {"56Fe": 5.0}},
        {"elements": {}},
        {"elements": {"56Fe": 3.0}},
    ]
    matrix, mask = rr._build_matrix(particles)
    assert list(mask["56Fe"]) == [True, False, True]
    assert matrix["56Fe"][1] == 0.0


@pytest.mark.parametrize("bad", ["n/a", None, float("nan"), -1.0, 0, 0.0])
def test_matrix_rejects_non_positive_and_junk(bad):
    """Values that cannot be a concentration are dropped, whatever their type."""
    matrix, mask = rr._build_matrix([{"elements": {"56Fe": bad}}])
    assert matrix == {} and mask == {}


def test_matrix_accepts_int_values():
    """Integer concentrations survive the numeric fast path."""
    matrix, _ = rr._build_matrix([{"elements": {"56Fe": 7}}])
    assert matrix["56Fe"][0] == pytest.approx(7.0)


# ──────────────────────────────────────────────────────────────────────────────
# resolve_scope
# ──────────────────────────────────────────────────────────────────────────────

def test_selected_node_takes_priority(win, nodes):
    """A selected sample node scopes the analysis to just its sample."""
    scene = FakeScene(list(nodes.values()), selected=[nodes["single"]])
    scope = rr.resolve_scope(scene, win)
    assert scope.sample_names == ("S1",)
    assert scope.origin == "selection"
    assert scope.total_particles == 400
    assert not scope.is_multi


def test_selected_multi_node_scopes_to_its_samples(win, nodes):
    """A selected multi-sample node contributes every sample it includes."""
    scene = FakeScene(list(nodes.values()), selected=[nodes["multi"]])
    scope = rr.resolve_scope(scene, win)
    assert set(scope.sample_names) == {"S2", "S3"}
    assert scope.is_multi


def test_no_selection_falls_back_to_canvas_union(win, nodes):
    """With nothing selected, every sample node on the canvas counts."""
    scope = rr.resolve_scope(FakeScene(list(nodes.values())), win)
    assert set(scope.sample_names) == {"S1", "S2", "S3"}
    assert scope.origin == "canvas"


def test_no_sample_nodes_falls_back_to_all_loaded(win, nodes):
    """A canvas without sample nodes widens the scope to everything loaded."""
    scope = rr.resolve_scope(FakeScene([nodes["plot"]]), win)
    assert set(scope.sample_names) == {"S1", "S2", "S3"}
    assert scope.origin == "all"


def test_selecting_a_plot_node_does_not_scope_to_it(win, nodes):
    """Only sample nodes drive the scope; selecting a plot node is ignored."""
    scene = FakeScene([nodes["plot"]], selected=[nodes["plot"]])
    assert rr.resolve_scope(scene, win).origin == "all"


def test_empty_pool_gives_empty_scope():
    """With nothing loaded the scope is empty rather than undefined."""
    scope = rr.resolve_scope(FakeScene([]), FakeWindow({}))
    assert scope.sample_names == ()
    assert scope.total_particles == 0


def test_sample_without_data_is_dropped(win):
    """A node pointing at an unloaded sample contributes nothing."""
    ghost = FakeNode("sample_selector", selected_sample="NOT_LOADED")
    scene = FakeScene([ghost], selected=[ghost])
    assert rr.resolve_scope(scene, win).sample_names == ()


def test_replicate_samples_are_expanded(win):
    """Summed replicates bring in every member sample, not just the first."""
    node = FakeNode("sample_selector", selected_sample="S1",
                    sum_replicates=True, replicate_samples=["S1", "S2"])
    scene = FakeScene([node], selected=[node])
    assert set(rr.resolve_scope(scene, win).sample_names) == {"S1", "S2"}


def test_sample_config_include_flags_are_respected(win):
    """Samples excluded in a multi node's config stay out of the scope."""
    node = FakeNode(
        "multiple_sample_selector",
        selected_samples=["S1", "S2", "S3"],
        sample_config={"S1": {"included": True},
                       "S2": {"included": False},
                       "S3": {"included": True}},
    )
    scene = FakeScene([node], selected=[node])
    assert set(rr.resolve_scope(scene, win).sample_names) == {"S1", "S3"}


def test_scope_key_tracks_particle_count(win, pool, nodes):
    """Loading more particles changes the fingerprint, invalidating the cache."""
    scene = FakeScene([nodes["single"]])
    before = rr.resolve_scope(scene, win).key
    pool["S1"] = pool["S1"] + make_particles(10, {"56Fe": 1.0}, 9)
    assert rr.resolve_scope(scene, win).key != before


def test_batch_pool_wins_over_window_data(win):
    """A batch node's particles take precedence over the main window's."""
    batch = FakeNode(
        "sample_selector",
        batch_particle_data=[{"source_sample": "B1", "elements": {"56Fe": 1.0}}] * 20,
    )
    scope = rr.resolve_scope(FakeScene([batch]), win)
    assert scope.sample_names == ("B1",)


# ──────────────────────────────────────────────────────────────────────────────
# Element selection must never narrow the analysis
# ──────────────────────────────────────────────────────────────────────────────

def test_isotope_selection_is_ignored(win):
    """A node filtered to one isotope still yields insights over every element."""
    node = FakeNode("sample_selector", selected_sample="S1",
                    selected_isotopes=[{"label": "56Fe"}])
    scene = FakeScene([node], selected=[node])
    ctx = rr.build_context(scene, win)
    assert {"56Fe", "55Mn", "27Al", "48Ti"} <= set(ctx.matrix)


# ──────────────────────────────────────────────────────────────────────────────
# AnalysisContext
# ──────────────────────────────────────────────────────────────────────────────

def test_context_shape(win, pool, nodes):
    """Particle counts, sample index and detection counts all line up."""
    scene = FakeScene([nodes["single"], nodes["multi"]])
    ctx = rr.build_context(scene, win)

    assert ctx.n == sum(len(pool[s]) for s in ctx.sample_names)
    assert len(ctx.sample_idx) == ctx.n
    for i, name in enumerate(ctx.sample_names):
        assert int((ctx.sample_idx == i).sum()) == len(pool[name])
    for el, mask in ctx.det_mask.items():
        assert ctx.det_counts[el] == int(mask.sum())
        assert len(ctx.matrix[el]) == ctx.n


def test_context_is_cached_per_scope(win, nodes):
    """Rebuilding the same scope returns the cached context, not a copy."""
    scene = FakeScene([nodes["single"], nodes["multi"]])
    scope = rr.resolve_scope(scene, win)
    assert rr.build_context(scene, win, scope) is rr.build_context(scene, win, scope)


def test_different_scopes_do_not_share_a_cache_entry(win, nodes):
    """Narrowing the scope produces a distinct context."""
    scene = FakeScene([nodes["single"], nodes["multi"]])
    wide = rr.build_context(scene, win)
    narrow_scope = rr.resolve_scope(
        FakeScene([nodes["single"]], selected=[nodes["single"]]), win)
    assert rr.build_context(scene, win, narrow_scope) is not wide


def test_cache_can_be_invalidated(win, nodes):
    """Clearing the cache forces the next build to start from scratch."""
    scene = FakeScene([nodes["single"]])
    first = rr.build_context(scene, win)
    rr.invalidate_context_cache()
    assert rr.build_context(scene, win) is not first


def test_frequent_elements_filters_rare_ones(win, nodes):
    """Only elements clearing the detection floor are offered for testing."""
    ctx = rr.build_context(FakeScene([nodes["single"]], selected=[nodes["single"]]), win)
    frequent = ctx.frequent_elements()
    assert set(frequent) <= set(ctx.elements_by_abundance())
    floor = max(5, ctx.n * 0.04)
    assert all(ctx.det_counts[el] >= floor for el in frequent)


def test_particle_mask_for_is_a_union(win, nodes):
    """Scoping to several elements keeps particles carrying any one of them."""
    ctx = rr.build_context(FakeScene([nodes["single"]], selected=[nodes["single"]]), win)
    combined = ctx.particle_mask_for(["56Fe", "27Al"])
    expected = ctx.det_mask["56Fe"] | ctx.det_mask["27Al"]
    assert np.array_equal(combined, expected)


def test_particle_mask_for_unknown_element_is_empty(win, nodes):
    """An element that was never measured selects no particles."""
    ctx = rr.build_context(FakeScene([nodes["single"]], selected=[nodes["single"]]), win)
    assert not ctx.particle_mask_for(["999Xx"]).any()


# ──────────────────────────────────────────────────────────────────────────────
# _AnalysisWorker
# ──────────────────────────────────────────────────────────────────────────────

def _run_worker(scene, win, scope=None):
    """Run an analysis synchronously and capture what it emits.

    Args:
        scene: The scene to analyse.
        win: Fake main window holding the particle pool.
        scope: Scope to use. Resolved from the scene when omitted.

    Returns:
        A ``(worker, captured)`` pair, where *captured* holds one entry per
        ``results_ready`` emission.
    """
    scope = scope or rr.resolve_scope(scene, win)
    particles, idx = rr.gather_scope_data(scene, win, scope)
    worker = rr._AnalysisWorker(scope, particles, idx)
    captured = []
    worker.results_ready.connect(captured.append)
    worker.run()
    return worker, captured


def test_worker_emits_suggestions(win, nodes):
    """A normal run produces well-formed, renderable suggestions."""
    _, captured = _run_worker(FakeScene([nodes["single"], nodes["multi"]]), win)
    assert captured, "worker never emitted"
    suggestions = captured[-1]
    assert suggestions
    assert all(s.node_type for s in suggestions)
    assert all(0.0 <= s.confidence <= 1.0 for s in suggestions)
    assert all(s.category in rr._CAT_META for s in suggestions)


def test_worker_groups_multi_sample_without_source_sample_key():
    """Comparison insights come from sample_idx, not a per-particle key."""
    win = FakeWindow({"LOW": lognormal_particles(400, "56Fe", 1.0, seed=11),
                      "HIGH": lognormal_particles(400, "56Fe", 3.0, seed=12)})
    scene = FakeScene([])
    scope = rr.resolve_scope(scene, win)
    particles, _ = rr.gather_scope_data(scene, win, scope)
    assert not any("source_sample" in p for p in particles)

    _, captured = _run_worker(scene, win, scope)
    assert any(s.category == "comparison" for s in captured[-1])


def test_cancelled_worker_emits_nothing(win, nodes):
    """Cancelling before the run starts suppresses the result entirely."""
    scene = FakeScene([nodes["single"], nodes["multi"]])
    scope = rr.resolve_scope(scene, win)
    particles, idx = rr.gather_scope_data(scene, win, scope)
    worker = rr._AnalysisWorker(scope, particles, idx)
    captured = []
    worker.results_ready.connect(captured.append)
    worker.cancel()
    worker.run()
    assert captured == []


def test_worker_emits_empty_list_for_tiny_dataset():
    """Too few particles to analyse still emits, so the panel can react."""
    win = FakeWindow({"T": make_particles(3, {"56Fe": 1.0})})
    _, captured = _run_worker(FakeScene([]), win)
    assert captured[-1] == []


def test_worker_handles_empty_scope():
    """An empty scope emits an empty result rather than raising."""
    _, captured = _run_worker(FakeScene([]), FakeWindow({}))
    assert captured[-1] == []


# ──────────────────────────────────────────────────────────────────────────────
# Category registry
# ──────────────────────────────────────────────────────────────────────────────

def test_clustering_is_gone():
    """Clustering was removed, so it must not appear anywhere."""
    assert "clustering" not in rr.category_keys()
    assert "clustering" not in rr._CAT_META
    assert not hasattr(rr, "_bimodality_bc")


def test_registry_covers_every_advertised_category():
    """Every chip the panel can draw has an analyser behind it."""
    assert set(rr.category_keys()) == set(rr._CAT_META)
    for key in rr.category_keys():
        assert callable(rr._ANALYSERS[key].run)
        assert rr._ANALYSERS[key].label
        assert rr._ANALYSERS[key].icon


def _ctx_for(particles, name="S"):
    """Build a context over a single synthetic sample.

    Args:
        particles: Particle dicts to load.
        name: Sample name to file them under.

    Returns:
        The analysis context.
    """
    win = FakeWindow({name: particles})
    node = FakeNode("sample_selector", selected_sample=name)
    return rr.build_context(FakeScene([node], selected=[node]), win)


# ──────────────────────────────────────────────────────────────────────────────
# Correlation
# ──────────────────────────────────────────────────────────────────────────────

def test_correlation_finds_a_planted_pair():
    """A pair that genuinely tracks together is surfaced with its elements set."""
    ctx = _ctx_for(correlated_particles())
    cards = [s for s in rr._analyse_correlation(ctx)
             if s.node_type == "correlation_plot"]
    assert cards
    assert {"56Fe", "55Mn"} == set(cards[0].elements)
    assert cards[0].confidence > 0.8


def test_correlation_ignores_an_independent_element():
    """An element varying on its own is never paired with the planted ones."""
    ctx = _ctx_for(correlated_particles())
    cards = [s for s in rr._analyse_correlation(ctx)
             if s.node_type == "correlation_plot"]
    assert not any("90Zr" in s.elements for s in cards)


def test_correlation_reports_overlap_and_correction():
    """The card states what the statistic rests on, not just its value."""
    ctx = _ctx_for(correlated_particles())
    card = next(s for s in rr._analyse_correlation(ctx)
                if s.node_type == "correlation_plot")
    assert "particles carry both" in card.reasoning
    assert "q = " in card.reasoning


def test_correlation_suppresses_pure_noise():
    """With no real structure, multiplicity correction leaves nothing behind."""
    rng = random.Random(3)
    noise = [{"elements": {f"E{i}": math.exp(rng.gauss(0, 1))
                           for i in range(8) if rng.random() < 0.6}}
             for _ in range(800)]
    cards = [s for s in rr._analyse_correlation(_ctx_for(noise))
             if s.node_type == "correlation_plot"]
    assert cards == []


def test_correlation_matrix_offered_only_with_enough_elements():
    """The full matrix card needs four elements to be worth drawing."""
    rich = rr._analyse_correlation(_ctx_for(correlated_particles()))
    assert any(s.node_type == "correlation_matrix" for s in rich)

    thin = rr._analyse_correlation(
        _ctx_for(lognormal_particles(300, "56Fe", 1.0, seed=4)))
    assert not any(s.node_type == "correlation_matrix" for s in thin)


def test_correlation_matrix_card_is_unscoped():
    """The matrix needs every element, so it must not narrow the new node."""
    card = next(s for s in rr._analyse_correlation(_ctx_for(correlated_particles()))
                if s.node_type == "correlation_matrix")
    assert card.elements == ()


def test_correlate_pair_needs_enough_overlap():
    """Too few co-detected particles yields nothing rather than a wild estimate."""
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([1.0, 2.0, 3.0, 4.0])
    assert rr._correlate_pair(a, b) is None
    assert rr._correlate_pair(a, b, min_overlap=3) is not None


def test_correlate_pair_rejects_a_constant_column():
    """A column that never varies has no correlation to report."""
    a = np.arange(1, 60, dtype=float)
    b = np.full(59, 5.0)
    assert rr._correlate_pair(a, b) is None


def test_correlate_pair_counts_only_co_detections():
    """The overlap reflects particles carrying both elements, not either."""
    a = np.array([1.0] * 40 + [0.0] * 10)
    b = np.array([0.0] * 10 + [2.0] * 40)
    result = rr._correlate_pair(a * np.linspace(1, 2, 50),
                                b * np.linspace(1, 3, 50))
    assert result is not None
    assert result["overlap"] == 30


# ──────────────────────────────────────────────────────────────────────────────
# Benjamini-Hochberg
# ──────────────────────────────────────────────────────────────────────────────

def test_bh_flags_clearly_significant_tests():
    """Small p-values survive correction; large ones do not."""
    significant, _ = rr._benjamini_hochberg([0.0001, 0.002, 0.9, 0.8])
    assert list(significant) == [True, True, False, False]


def test_bh_rejects_everything_when_nothing_is_significant():
    """A family of weak results yields no discoveries."""
    significant, _ = rr._benjamini_hochberg([0.5, 0.6, 0.7])
    assert not significant.any()


def test_bh_is_stricter_than_a_raw_threshold():
    """A lone p-value under 0.05 fails once the family size is accounted for."""
    family = [0.04] + [0.4 + i * 0.02 for i in range(19)]
    significant, _ = rr._benjamini_hochberg(family)
    assert family[0] < 0.05
    assert not significant.any()


def test_bh_accepts_a_family_that_is_significant_together():
    """Many tests sharing a small p-value are jointly credible."""
    significant, _ = rr._benjamini_hochberg([0.04] * 20)
    assert significant.all()


def test_bh_adjusted_values_are_valid_probabilities():
    """Adjusted p-values stay in range and never fall below the raw ones."""
    raw = [0.001, 0.02, 0.3, 0.44, 0.9]
    _, adjusted = rr._benjamini_hochberg(raw)
    assert all(0.0 <= a <= 1.0 for a in adjusted)
    assert all(a >= r - 1e-12 for a, r in zip(adjusted, raw))


def test_bh_handles_an_empty_family():
    """No tests means no results, not an error."""
    significant, adjusted = rr._benjamini_hochberg([])
    assert significant.size == 0 and adjusted.size == 0


# ──────────────────────────────────────────────────────────────────────────────
# Remaining analysers
# ──────────────────────────────────────────────────────────────────────────────

def test_isotope_analyser_pairs_masses_of_one_element():
    """Two masses of the same element become a ratio suggestion."""
    rng = random.Random(5)
    particles = []
    for _ in range(400):
        base = math.exp(rng.gauss(1.0, 0.6))
        particles.append({"elements": {"206Pb": base, "208Pb": base * 2.4,
                                       "56Fe": math.exp(rng.gauss(1.0, 0.5))}})
    cards = rr._analyse_isotope(_ctx_for(particles))
    assert cards
    assert cards[0].node_type == "isotopic_ratio_plot"
    assert {"206Pb", "208Pb"} <= set(cards[0].elements)


def test_isotope_analyser_silent_without_isotope_pairs():
    """One mass per element offers no ratio to compute."""
    assert rr._analyse_isotope(_ctx_for(correlated_particles())) == []


def test_distribution_analyser_scopes_to_its_elements():
    """Box plot and histogram both name the elements they describe."""
    cards = rr._analyse_distribution(_ctx_for(correlated_particles()))
    assert {s.node_type for s in cards} == {"box_plot", "histogram_plot"}
    assert all(s.elements for s in cards)
    histogram = next(s for s in cards if s.node_type == "histogram_plot")
    assert len(histogram.elements) == 1


def test_composition_analyser_stays_unscoped():
    """Composition cards describe every element, so they narrow nothing."""
    cards = rr._analyse_composition(_ctx_for(correlated_particles()))
    assert {s.node_type for s in cards} == {"element_bar_chart_plot", "pie_chart_plot"}
    assert all(s.elements == () for s in cards)


def test_comparison_analyser_finds_a_real_difference():
    """Samples drawn from clearly different distributions are reported."""
    win = FakeWindow({"LOW": lognormal_particles(400, "56Fe", 1.0, seed=1),
                      "HIGH": lognormal_particles(400, "56Fe", 3.0, seed=2)})
    cards = rr._analyse_comparison(rr.build_context(FakeScene([]), win))
    assert cards
    assert cards[0].elements == ("56Fe",)
    assert "Kruskal-Wallis" in cards[0].reasoning


def test_comparison_analyser_stays_quiet_for_identical_samples():
    """Samples from the same distribution are not reported as differing."""
    win = FakeWindow({"A": lognormal_particles(400, "56Fe", 1.0, seed=1),
                      "B": lognormal_particles(400, "56Fe", 1.0, seed=2)})
    assert rr._analyse_comparison(rr.build_context(FakeScene([]), win)) == []


def test_comparison_analyser_needs_more_than_one_sample():
    """A single-sample scope has nothing to compare."""
    assert rr._analyse_comparison(_ctx_for(correlated_particles())) == []


def test_outlier_analyser_ignores_an_ordinary_heavy_tail():
    """A plain log-normal element is not flagged, despite its long tail."""
    particles = lognormal_particles(600, "56Fe", 1.0, sigma=1.0, seed=6)
    assert rr._analyse_outlier(_ctx_for(particles)) == []


def test_outlier_analyser_finds_a_detached_population():
    """A genuinely separate high-concentration group is flagged."""
    particles = lognormal_particles(600, "56Fe", 1.0, sigma=0.3, seed=6)
    particles += [{"elements": {"56Fe": 1e6}} for _ in range(30)]
    cards = rr._analyse_outlier(_ctx_for(particles))
    assert cards
    assert cards[0].category == "outlier"


# ──────────────────────────────────────────────────────────────────────────────
# analyse() dispatch
# ──────────────────────────────────────────────────────────────────────────────

def test_analyse_runs_only_the_requested_category():
    """Asking for one category runs that one and nothing else."""
    ctx = _ctx_for(correlated_particles())
    cards = rr.analyse(ctx, categories=["distribution"])
    assert cards
    assert {s.category for s in cards} == {"distribution"}


def test_analyse_runs_everything_by_default():
    """Omitting the category list scans the lot."""
    ctx = _ctx_for(correlated_particles())
    assert len(rr.analyse(ctx)) >= len(rr.analyse(ctx, categories=["correlation"]))


def test_analyse_ignores_an_unknown_category():
    """A stale category key is skipped rather than raising."""
    assert rr.analyse(_ctx_for(correlated_particles()), categories=["nope"]) == []


def test_analyse_honours_the_stop_callback():
    """A run told to stop returns nothing."""
    ctx = _ctx_for(correlated_particles())
    assert rr.analyse(ctx, should_stop=lambda: True) == []


def test_analyse_survives_a_failing_analyser(monkeypatch):
    """One broken category cannot take down the others."""
    def explode(ctx, progress=None):
        """Stand in for an analyser that fails at runtime."""
        raise RuntimeError("boom")

    broken = rr.InsightCategory("distribution", "Distribution", "▦", explode)
    monkeypatch.setitem(rr._ANALYSERS, "distribution", broken)
    cards = rr.analyse(_ctx_for(correlated_particles()))
    assert cards
    assert not any(s.category == "distribution" for s in cards)


def test_analyse_returns_nothing_for_a_tiny_context():
    """Below the minimum particle count, no category runs."""
    assert rr.analyse(_ctx_for(lognormal_particles(3, "56Fe", 1.0))) == []


def test_worker_runs_only_its_categories():
    """The worker passes its category filter through to the analysis."""
    win = FakeWindow({"S": correlated_particles()})
    scene = FakeScene([])
    scope = rr.resolve_scope(scene, win)
    particles, idx = rr.gather_scope_data(scene, win, scope)
    worker = rr._AnalysisWorker(scope, particles, idx, categories=["composition"])
    captured = []
    worker.results_ready.connect(captured.append)
    worker.run()
    assert captured[-1]
    assert {s.category for s in captured[-1]} == {"composition"}


# ──────────────────────────────────────────────────────────────────────────────
# Isotope record resolution for the Add flow
# ──────────────────────────────────────────────────────────────────────────────

class FakeIsotopeWindow(FakeWindow):
    """Fake main window that also exposes the app's measured isotope list."""

    def __init__(self, pool, isotopes):
        """Store the pool and the available isotopes.

        Args:
            pool: Sample name to particle dicts.
            isotopes: Element symbol to the masses measured for it.
        """
        super().__init__(pool)
        self.selected_isotopes = isotopes

    def get_formatted_label(self, key):
        """Format an isotope key the way the main window does.

        Args:
            key: Key of the form ``"Fe-55.9349"``.

        Returns:
            A label such as ``"56Fe"``.
        """
        symbol, mass = key.split("-")
        return f"{round(float(mass))}{symbol}"


@pytest.fixture
def iso_win():
    """Return a fake window measuring iron, manganese and zirconium."""
    return FakeIsotopeWindow(
        {"S1": correlated_particles()},
        {"Fe": [55.9349], "Mn": [54.9380], "Zr": [89.9047]},
    )


def test_isotope_entries_resolve_to_full_records(iso_win):
    """Labels become records carrying the symbol and mass the dialog needs."""
    entries = rr._isotope_entries(iso_win, FakeScene([]), ["56Fe", "55Mn"])
    assert [e["label"] for e in entries] == ["56Fe", "55Mn"]
    assert all({"symbol", "mass", "key", "label"} <= set(e) for e in entries)
    assert entries[0]["symbol"] == "Fe"


def test_isotope_entries_preserve_request_order(iso_win):
    """Records come back in the order the insight named them."""
    entries = rr._isotope_entries(iso_win, FakeScene([]), ["55Mn", "56Fe"])
    assert [e["label"] for e in entries] == ["55Mn", "56Fe"]


def test_isotope_entries_skip_unknown_labels(iso_win):
    """An element the app never measured is dropped rather than faked."""
    entries = rr._isotope_entries(iso_win, FakeScene([]), ["56Fe", "999Xx"])
    assert [e["label"] for e in entries] == ["56Fe"]


def test_isotope_entries_empty_without_an_isotope_list(win):
    """With nothing to resolve against, no records are invented."""
    assert rr._isotope_entries(win, FakeScene([]), ["56Fe"]) == []


def test_isotope_entries_prefer_a_batch_node(iso_win):
    """A batch node's isotope list takes precedence over the window's."""
    batch = FakeNode("batch_sample_selector",
                     batch_available_isotopes={"Zr": [89.9047]})
    entries = rr._isotope_entries(iso_win, FakeScene([batch]), ["56Fe", "90Zr"])
    assert [e["label"] for e in entries] == ["90Zr"]


def test_find_batch_node():
    """The batch node is located by type, and absence is reported as None."""
    batch = FakeNode("batch_sample_selector")
    assert rr._find_batch_node(FakeScene([batch])) is batch
    assert rr._find_batch_node(FakeScene([FakeNode("sample_selector")])) is None
