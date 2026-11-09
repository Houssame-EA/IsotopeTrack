"""Tests for how Insights checks each finding against replicates and chance coincidence."""

from __future__ import annotations

import math
import random

import pytest

from results.insights import engine as rr
from results.insights import robustness as rb


class FakeScene:
    """Stand-in for the canvas scene."""

    workflow_nodes = []

    def selectedItems(self):
        """Return no selection."""
        return []


class FakeWindow:
    """Stand-in for the main window, holding the loaded particle pool."""

    def __init__(self, pool):
        """Expose *pool* as ``sample_particle_data``."""
        self.sample_particle_data = pool


@pytest.fixture(autouse=True)
def _clear_cache():
    """Isolate each test from contexts cached by its neighbours."""
    rr.invalidate_context_cache()
    yield
    rr.invalidate_context_cache()


def context(pool):
    """Analysis context over *pool*, grouped into replicates by sample name."""
    rr.invalidate_context_cache()
    return rr.build_context(FakeScene(), FakeWindow(pool))


def material(seed, linked=True, ce_mu=4.0, n=600, gap=0.05):
    """Particles with Fe and Ti, linked or not, and Ce, timed *gap* seconds apart."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        e = {}
        if rng.random() < 0.6:
            fe = math.exp(rng.gauss(3.2, 0.8))
            e["56Fe"] = fe
            if rng.random() < 0.7:
                e["48Ti"] = (fe * 0.45 * math.exp(rng.gauss(0, 0.3)) if linked
                             else math.exp(rng.gauss(2.4, 0.8)))
        if rng.random() < 0.4:
            e["140Ce"] = math.exp(rng.gauss(ce_mu, 0.6))
        if not e:
            e["27Al"] = 3.0
        out.append({"elements": e, "start_time": i * gap, "end_time": i * gap + 0.001})
    return out


def finding(category, elements, samples, explain_key="", details=()):
    """A bare finding for the checks to measure."""
    return rr.Suggestion("t", "r", category, 0.8, "x", elements=tuple(elements),
                         samples=tuple(samples), explain_key=explain_key,
                         details=list(details))


def test_correlation_missing_in_one_replicate_is_flagged_and_ranked_down():
    """Fe vs Ti holds in r1 and r2 but not r3: 2 of 3, r3 named, score cut."""
    pool = {"Inf_r1": material(1), "Inf_r2": material(2), "Inf_r3": material(3, linked=False)}
    ctx = context(pool)
    s = finding("correlation", ("56Fe", "48Ti"), pool, details=[("False discovery", "q = 1e-20")])
    rb.attach(ctx, [s])
    ev = s.evidence
    assert [c.label for c in ev.replicates] == ["r1", "r2", "r3"]
    assert [c.ok for c in ev.replicates] == [True, True, False]
    assert ev.n_ok == 2 and ev.reproducible is False
    assert [c.label for c in ev.failed] == ["r3"]
    assert ev.effect.startswith("ρ +")
    assert ev.evidence == "q = 1e-20"
    assert s.confidence == pytest.approx(0.8 * (2 / 3) ** 2)


def test_correlation_seen_in_every_replicate_keeps_its_score():
    """A pattern in all three replicates passes and keeps its ranking score."""
    pool = {"Inf_r1": material(1), "Inf_r2": material(2), "Inf_r3": material(4)}
    ctx = context(pool)
    s = finding("correlation", ("56Fe", "48Ti"), pool)
    rb.attach(ctx, [s])
    assert s.evidence.reproducible is True
    assert s.confidence == pytest.approx(0.8)


def test_comparison_needs_a_clean_gap_between_replicates():
    """Ce higher in every Influent replicate than in every Effluent one."""
    pool = {"Inf_r1": material(1, ce_mu=4.6), "Inf_r2": material(2, ce_mu=4.5),
            "Inf_r3": material(3, ce_mu=4.7), "Eff_r1": material(4, ce_mu=3.4),
            "Eff_r2": material(5, ce_mu=3.5), "Eff_r3": material(6, ce_mu=3.3)}
    ctx = context(pool)
    s = finding("comparison", ("140Ce",), pool)
    ev = rb.assess(ctx, s)
    assert len(ev.replicates) == 6 and ev.reproducible is True
    assert ev.replicates[0].label == "Inf r1"
    assert ev.effect.endswith("×") and float(ev.effect[:-1]) > 2.5


def test_comparison_with_an_overlapping_replicate_fails_it():
    """One Effluent replicate as high as Influent breaks the gap for both sides."""
    pool = {"Inf_r1": material(1, ce_mu=4.6), "Inf_r2": material(2, ce_mu=4.5),
            "Eff_r1": material(4, ce_mu=3.4), "Eff_r2": material(5, ce_mu=4.6)}
    ctx = context(pool)
    ev = rb.assess(ctx, finding("comparison", ("140Ce",), pool))
    assert ev.reproducible is False
    assert any(not c.ok for c in ev.replicates)


def test_unreplicated_samples_get_effect_but_no_replicate_checks():
    """A single sample has nothing to repeat against."""
    pool = {"Solo": material(1)}
    ctx = context(pool)
    ev = rb.assess(ctx, finding("correlation", ("56Fe", "48Ti"), pool))
    assert ev.replicates == [] and ev.reproducible is None
    assert ev.effect
    assert rb.rank_weight(ev) == 1.0


def test_coincidence_compares_co_detections_with_chance():
    """Linked Fe–Ti sits far above chance; crowded independent elements sit near it."""
    pool = {"Inf_r1": material(1), "Inf_r2": material(2)}
    ctx = context(pool)
    ev = rb.assess(ctx, finding("correlation", ("56Fe", "48Ti"), pool))
    assert ev.coincidence_fold > rb.COINCIDENCE_MIN_FOLD

    rng = random.Random(9)
    crowded = []
    for i in range(3000):
        e = {}
        if rng.random() < 0.5:
            e["56Fe"] = 10.0
        if rng.random() < 0.5:
            e["48Ti"] = 10.0
        if not e:
            e["27Al"] = 1.0
        crowded.append({"elements": e, "start_time": i * 0.001, "end_time": i * 0.001 + 0.002})
    ctx = context({"Busy": crowded})
    ev = rb.assess(ctx, finding("cooccurrence", ("56Fe", "48Ti"), ("Busy",),
                                explain_key="cooccurrence_with"))
    assert ev.coincidence_fold < rb.COINCIDENCE_MIN_FOLD
    assert rb.rank_weight(ev) == pytest.approx(0.2)


def test_kinds_without_a_measure_are_left_alone():
    """Composition and replicate cards keep their score and get no evidence."""
    pool = {"Inf_r1": material(1), "Inf_r2": material(2)}
    ctx = context(pool)
    s = finding("composition", (), pool)
    rb.attach(ctx, [s])
    assert s.evidence is None and s.confidence == 0.8


def test_engine_attaches_evidence_to_detector_findings():
    """Findings that come out of a scan carry their evidence."""
    pool = {"Inf_r1": material(1), "Inf_r2": material(2), "Inf_r3": material(3, linked=False)}
    ctx = context(pool)
    found = rr.analyse(ctx, categories=["correlation"])
    pair = next(s for s in found if set(s.elements) == {"56Fe", "48Ti"})
    assert pair.evidence is not None and pair.evidence.n_ok == 2


def test_card_shows_the_strip_and_names_the_failing_replicate(qapp):
    """The card lists effect, evidence, replicates and coincidence, and says where it failed."""
    from PySide6.QtWidgets import QLabel
    from results.insights import panel as ip
    s = finding("correlation", ("56Fe", "48Ti"), ("a", "b", "c"))
    s.evidence = rb.Evidence(effect="ρ +0.61", evidence="q = 3e-9",
                             replicates=[rb.ReplicateCheck("r1", True, "ρ +0.9"),
                                         rb.ReplicateCheck("r2", False, "ρ +0.1")],
                             coincidence=(1765, 48.4))
    cells = ip.evidence_cells(s.evidence)
    assert [c[0] for c in cells] == ["Effect", "Evidence", "Reproducible", "Coincidence"]
    assert cells[2] == ("Reproducible", "1 of 2 replicates", False)
    assert cells[3] == ("Coincidence", "36× above chance", True)
    card = ip._Card(s, on_add=lambda _s: None)
    texts = [w.text() for w in card.findChildren(QLabel)]
    assert "Not seen in r2 (ρ +0.1)" in texts
    assert "✗ 1 of 2 replicates" in texts
    assert any("score" in t for t in texts)


@pytest.fixture
def qapp():
    """The running QApplication, created if needed."""
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
