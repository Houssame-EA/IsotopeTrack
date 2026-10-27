"""Numbered selector nodes, Insights searching one of them, and plots wired straight to it."""

from __future__ import annotations

import random

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QMainWindow

from results.insights import engine as rr


def particles(n, seed, shift=1.0):
    """Particles with Fe, Ti and Pb, Fe scaled by *shift*."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        fe = rng.lognormvariate(3, 0.5) * shift
        out.append({"elements": {"56Fe": fe, "48Ti": fe * 0.5, "208Pb": rng.lognormvariate(2, 0.4)},
                    "element_mass_fg": {"56Fe": fe * 0.01, "48Ti": fe * 0.005},
                    "start_time": i * 0.01, "end_time": i * 0.01 + 0.0005})
    return out


@pytest.fixture
def canvas():
    """A real canvas with a Multi-Sample node (two sum groups) and a Single Sample node."""
    app = QApplication.instance() or QApplication([])
    from widget.canvas_widgets import CanvasResultsDialog, _NODE_FACTORIES
    owner = QMainWindow()
    owner.sample_particle_data = {
        "A_1": particles(120, 1), "A_2": particles(120, 2),
        "B_1": particles(120, 3, 3.0), "B_2": particles(120, 4, 3.0), "C": particles(120, 5),
    }
    dlg = CanvasResultsDialog(owner)
    sc = dlg.canvas.scene
    multi = _NODE_FACTORIES["multiple_sample_selector"](owner)
    multi.selected_samples = ["A_1", "A_2", "B_1", "B_2"]
    multi.sample_config = {s: {"included": True, "sum_group": s[0], "custom_name": s}
                           for s in multi.selected_samples}
    multi.selected_isotopes = [{"label": "56Fe"}, {"label": "48Ti"}]
    single = _NODE_FACTORIES["sample_selector"](owner)
    single.selected_sample = "C"
    sc.add_node(multi, QPointF(300, 100))
    sc.add_node(single, QPointF(300, 400))
    app.processEvents()
    yield app, dlg, sc, multi, single, owner
    dlg.done(0)
    dlg.deleteLater()
    owner.deleteLater()


def test_selector_nodes_get_numbers_that_stay_put(canvas):
    """Numbers start at 1, survive removing a node, and fill the gap for the next one."""
    app, _dlg, sc, multi, single, owner = canvas
    from widget.canvas_widgets import _NODE_FACTORIES
    assert (multi.insights_number, single.insights_number) == (1, 2)
    third = _NODE_FACTORIES["sample_selector"](owner)
    sc.add_node(third, QPointF(300, 700))
    assert third.insights_number == 3
    sc.delete_node(sc.node_items[multi])
    assert (single.insights_number, third.insights_number) == (2, 3)
    fourth = _NODE_FACTORIES["multiple_sample_selector"](owner)
    sc.add_node(fourth, QPointF(300, 900))
    assert fourth.insights_number == 1
    plot = _NODE_FACTORIES["histogram_plot"](owner)
    sc.add_node(plot, QPointF(600, 100))
    assert not getattr(plot, "insights_number", 0)


def test_saved_numbers_are_kept_and_clashes_resolved(canvas):
    """A node arriving with a free number keeps it; one clashing with another gets a new one."""
    _app, _dlg, sc, _multi, _single, owner = canvas
    from widget.canvas_widgets import _NODE_FACTORIES
    kept = _NODE_FACTORIES["sample_selector"](owner)
    kept.insights_number = 7
    sc.add_node(kept, QPointF(0, 0))
    clash = _NODE_FACTORIES["sample_selector"](owner)
    clash.insights_number = 7
    sc.add_node(clash, QPointF(0, 200))
    assert kept.insights_number == 7 and clash.insights_number == 3


def test_number_is_saved_with_the_project():
    """The project file keeps each node's number."""
    import inspect
    from save_export import project_manager as pm
    source = inspect.getsource(pm)
    assert source.count("'insights_number'") == 2


def test_scope_follows_one_node_with_its_groups_and_elements(canvas):
    """Node 1 is searched as it sends data on: two sum groups, two elements."""
    _app, _dlg, sc, multi, single, owner = canvas
    scope = rr.resolve_scope(sc, owner, multi.insights_number)
    assert scope.origin == "node" and scope.node_number == 1
    assert scope.sample_names == ("A_1", "A_2", "B_1", "B_2")
    assert sorted(g.name for g in scope.groups) == ["A", "B"]
    assert scope.labels == ("56Fe", "48Ti")
    parts, _idx = rr.gather_scope_data(sc, owner, scope)
    assert parts and all(set(p["elements"]) <= {"56Fe", "48Ti"} for p in parts)
    assert "208Pb" in owner.sample_particle_data["A_1"][0]["elements"]
    other = rr.resolve_scope(sc, owner, single.insights_number)
    assert other.sample_names == ("C",) and other.labels == ()
    assert rr.resolve_scope(sc, owner, 99).origin == "canvas"


@pytest.fixture
def panel(canvas):
    """The Insights panel on that canvas, searching synchronously."""
    app, _dlg, sc, multi, single, owner = canvas
    from results.insights.panel import SmartInsightsPanel
    p = SmartInsightsPanel(sc, owner)
    p._poll.stop()
    yield p
    p._teardown()
    p.deleteLater()


def test_panel_searches_the_lowest_node_until_told_otherwise(canvas, panel):
    """Node 1 is searched first; picking 2 or all switches, and the button says which."""
    _app, _dlg, sc, multi, single, owner = canvas
    panel.scan(force=True)
    assert panel.current_node() == 1 and panel._scope.node_number == 1
    assert panel._node_btn.text().startswith("Node: 1")
    panel.set_node(2)
    assert panel._scope.sample_names == ("C",)
    panel.set_node(0)
    assert panel._scope.origin == "canvas"
    assert panel._node_btn.text().startswith("Node: all")


def test_add_connects_straight_to_the_node(canvas, panel):
    """A card's plot hangs off node 1 itself; no new selector is created."""
    _app, _dlg, sc, multi, single, owner = canvas
    panel.scan(force=True)
    before = len(sc.workflow_nodes)
    s = rr.Suggestion("Fe by group", "r", "comparison", 0.8, "box_plot", elements=("56Fe",))
    panel._add_suggestion(s)
    added = sc.workflow_nodes[before:]
    assert [n.node_type for n in added] == ["box_plot"]
    assert any(lk.source_node is multi and lk.sink_node is added[0] for lk in sc.workflow_links)
    assert panel._card_source(s).startswith("Node 1")


def test_replicate_findings_still_get_their_own_selector(canvas, panel):
    """A replicate check needs the replicates apart, so it keeps a selector of its own."""
    _app, _dlg, sc, multi, single, owner = canvas
    panel.scan(force=True)
    before = len(sc.workflow_nodes)
    s = rr.Suggestion("A replicates", "r", "replicate", 0.8, "box_plot", elements=("56Fe",),
                      samples=("A_1", "A_2"))
    panel._add_suggestion(s)
    kinds = [n.node_type for n in sc.workflow_nodes[before:]]
    assert "box_plot" in kinds and any(k.endswith("sample_selector") for k in kinds)
    assert "replicates apart" in panel._card_source(s)
