"""Tests for particle types in Insights and their Figure Builder grouping."""

from __future__ import annotations

import numpy as np
import pytest

from results.insights import discovery as disc
from results.insights import engine as rr
from results.figure_builder.core import types as T

from tests.test_insights_discovery import FakeScene, FakeWindow


@pytest.fixture(autouse=True)
def _clear_cache():
    """Isolate each test from cached contexts."""
    rr.invalidate_context_cache()
    yield
    rr.invalidate_context_cache()


TYPE_RECIPES = {
    "ilmenite": {"48Ti": 1.0, "56Fe": 1.1, "55Mn": 0.05},
    "clay": {"27Al": 1.0, "28Si": 1.2, "56Fe": 0.25},
    "monazite": {"140Ce": 1.0, "139La": 0.5, "146Nd": 0.35},
}
"""Mass make-up of three simulated particle types."""


def particles(n_each, seed, recipes=TYPE_RECIPES, noise=0.12, singles=200):
    """Simulated multi-element particles of fixed types plus single-element ones."""
    rng = np.random.default_rng(seed)
    out = []
    for recipe in recipes.values():
        for _ in range(n_each):
            size = rng.lognormal(0, 0.8)
            mass = {el: size * share * rng.lognormal(0, noise) for el, share in recipe.items()}
            out.append({"elements": {el: m * 100 for el, m in mass.items()},
                        "element_mass_fg": mass})
    for _ in range(singles):
        m = rng.lognormal(0, 0.8)
        out.append({"elements": {"56Fe": m * 100}, "element_mass_fg": {"56Fe": m}})
    return out


def context(pool):
    """Analysis context over *pool* (sample name to particles)."""
    rr.invalidate_context_cache()
    return rr.build_context(FakeScene(), FakeWindow(pool))


def replicated_pool():
    """Two materials in three replicates each; monazite only in the second."""
    pool = {}
    for r in (1, 2, 3):
        pool[f"soil_{r}"] = particles(150, r, {k: v for k, v in TYPE_RECIPES.items() if k != "monazite"})
        pool[f"ash_{r}"] = particles(150, 10 + r)
    return pool


def test_known_types_are_found_and_named():
    """Three simulated types come back as stable types named by their main elements."""
    found = disc.find_particle_types(context(replicated_pool()))
    assert found is not None
    names = {t["name"] for t in found["types"]}
    assert names == {"Si–Al–Fe", "Fe–Ti–Mn", "Ce–La–Nd"}
    assert found["use_mass"] and found["silhouette"] >= disc.TYPES_MIN_SILHOUETTE
    for t in found["types"]:
        assert t["jaccard"] >= disc.TYPES_MIN_JACCARD
        assert t["confirmed_in"]
    monazite = next(t for t in found["types"] if "Ce" in t["name"])
    assert monazite["confirmed_in"] == ["ash"]
    assert all(monazite["per_sample"][f"soil_{r}"][0] == 0 for r in (1, 2, 3))


def test_cards_and_their_figure_spec():
    """An overview card and one card per type, each with a PCA grouped by type."""
    cards = disc.analyse_particle_types(context(replicated_pool()))
    assert cards[0].explain_key == "types_overview"
    per_type = [c for c in cards if c.explain_key == "particle_type"]
    assert len(per_type) == len(cards) - 1 >= 3
    panel = per_type[0].config["panels"][0]
    assert panel["kind"] == "pca" and panel["group_by"] == "types"
    assert len(panel["types"]["types"]) == len(per_type)
    shares = dict(per_type[0].details)
    assert any(k.startswith("Share in") for k in shares)


def test_no_types_without_structure():
    """Elements scattered independently give no types."""
    rng = np.random.default_rng(4)
    parts = []
    for _ in range(1200):
        mass = {el: rng.lognormal(0, 1.2) for el in ("48Ti", "56Fe", "27Al", "28Si", "55Mn")
                if rng.random() < 0.7}
        if len(mass) < 2:
            continue
        parts.append({"elements": {k: v * 100 for k, v in mass.items()}, "element_mass_fg": mass})
    assert disc.find_particle_types(context({"S": parts})) is None


def test_too_few_particles_gives_nothing():
    """Below the particle minimum no search is made."""
    assert disc.find_particle_types(context({"S": particles(40, 1)})) is None


def test_type_seen_in_one_replicate_only_is_dropped():
    """A type must appear in two replicates of a group when replicates exist."""
    pool = {f"soil_{r}": particles(150, r, {k: v for k, v in TYPE_RECIPES.items() if k != "monazite"})
            for r in (1, 2, 3)}
    pool["soil_1"] += particles(150, 99, {"monazite": TYPE_RECIPES["monazite"]}, singles=0)
    found = disc.find_particle_types(context(pool))
    assert found is not None
    assert not any("Ce" in t["name"] for t in found["types"])


def test_assignment_is_the_same_particle_by_particle():
    """A particle gets the same type alone or among others; single-element ones get none."""
    found = disc.find_particle_types(context(replicated_pool()))
    definition = found["definition"]
    rows = particles(30, 77, singles=5)
    M = np.array([[p["element_mass_fg"].get(e, 0.0) for e in definition["elements"]] for p in rows])
    together = T.assign(M, definition)
    alone = np.array([T.assign(M[i:i + 1], definition)[0] for i in range(len(rows))])
    assert np.array_equal(together, alone)
    assert (together[-5:] == -1).all()
    assert (together[:90] >= 0).mean() > 0.9


def test_figure_builder_groups_by_type():
    """The PCA panel of a type card draws one group per type."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    from results.figure_builder.core.expressions import ParticleTable
    cards = disc.analyse_particle_types(context(replicated_pool()))
    pool = replicated_pool()
    parts = [dict(p, source_sample=s) for s, ps in pool.items() for p in ps]
    table = ParticleTable.from_input({"type": "multiple_sample_data", "sample_names": list(pool),
                                      "particle_data": parts}, "Element Mass (fg)")
    fig = Figure()
    FigureCanvasAgg(fig)
    report = render(fig, cards[0].config, table)
    assert not report.errors
    assert any(s.startswith("PCA") for s in report.stats)


def _typed_table(pool):
    """Particle table over *pool* in element mass."""
    from results.figure_builder.core.expressions import ParticleTable
    parts = [dict(p, source_sample=s) for s, ps in pool.items() for p in ps]
    return ParticleTable.from_input({"type": "multiple_sample_data", "sample_names": list(pool),
                                     "particle_data": parts}, "Element Mass (fg)"), parts


@pytest.mark.parametrize("which", [0, 1, 2, 3])
def test_type_stories_draw(which):
    """The overview and each type card build a lettered figure that draws without error."""
    from results import ai_figures as af
    from results.insights import figures as F
    pool = replicated_pool()
    cards = disc.analyse_particle_types(context(pool))
    card = cards[which]
    table, parts = _typed_table(pool)
    labels = list(cards[0].config["panels"][0]["types"]["elements"])
    ctx = F.context_from(parts, labels, {}, multi_sample=True, groups=2)
    spec = F.figure_for(card, ctx)
    assert spec is not None and spec["data_type"] == "Element Mass (fg)"
    assert 4 <= len(spec["panels"]) - 1 <= F.MAX_PANELS
    assert af.render_problems(spec, table) == []


def test_type_only_keeps_one_type():
    """A panel limited to one type counts only that type's particles."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    from results.figure_builder.core.spec import default_spec, make_panel, normalise_spec
    pool = replicated_pool()
    cards = disc.analyse_particle_types(context(pool))
    definition = cards[0].config["panels"][0]["types"]
    table, _parts = _typed_table(pool)
    which = T.table_types(table, definition)
    spec = default_spec()
    spec["data_type"] = "Element Mass (fg)"
    name = definition["types"][0]["name"]
    spec["panels"] = [make_panel(rect=[0, 0, 1, 1], kind="histogram", value="total", log_x=True,
                                 types=definition, type_only=name)]
    fig = Figure()
    FigureCanvasAgg(fig)
    report = render(fig, normalise_spec(spec), table)
    assert not report.errors
    assert report.counts[spec["panels"][0]["id"]] == int((which == 0).sum())


def test_type_cards_offer_clustering():
    """Only particle-type cards show the Clustering button, and it passes the card on."""
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from results.insights import panel as ip
    cards = disc.analyse_particle_types(context(replicated_pool()))
    seen = []
    card = ip._Card(cards[1], on_add=lambda *_: None, on_figure=lambda *_: None,
                    on_cluster=seen.append)
    card._cluster_btn.click()
    assert seen == [cards[1]]
    other = rr.Suggestion("t", "r", "comparison", 0.8, "box_plot", elements=("56Fe",))
    plain = ip._Card(other, on_add=lambda *_: None, on_figure=lambda *_: None, on_cluster=seen.append)
    assert not hasattr(plain, "_cluster_btn")


def test_switching_plot_type_replaces_the_cards_at_once():
    """Picking another plot type shows only its cards, before Qt deletes the old ones."""
    import time
    from PySide6.QtWidgets import QApplication
    from tests.test_insights_discovery import FakeScene, FakeWindow
    from results.insights import panel as ip
    app = QApplication.instance() or QApplication([])
    panel = ip.SmartInsightsPanel(FakeScene(), FakeWindow(replicated_pool()))
    panel.resize(380, 900)
    panel.show()
    panel.scan()
    start = time.time()
    while panel._worker is not None and time.time() - start < 120:
        app.processEvents()
        time.sleep(0.01)

    def visible_types():
        return {c._s.node_type for c in panel.findChildren(ip._Card) if c.isVisible()}

    assert len(visible_types()) > 2
    for key, action in panel._type_actions.items():
        if not action.isEnabled():
            continue
        action.trigger()
        assert visible_types() == {key}, key
    panel._all_action.trigger()
    assert len(visible_types()) > 2
    panel._teardown()
    panel.close()
