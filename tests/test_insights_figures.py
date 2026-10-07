"""Tests for the explanations and explained figures behind each Insights finding.

Every explanation key a detector can emit must have an explanation and a
figure design, and every design must draw without errors on realistic data.
"""
from __future__ import annotations

import ast
import math
import pathlib
import random

import pytest
from PySide6.QtWidgets import QApplication

from results import ai_figures as af
from results.ai_figure_view import table_for
from results.insights import engine as rr
from results.insights import figures as F
from results.insights import panel as ip
from results.insights.explain import EXPLANATIONS, explanation_for

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def app():
    """Return the running QApplication, creating one if needed."""
    return QApplication.instance() or QApplication([])


def emitted_explain_keys() -> set[str]:
    """Every literal explain key written by a detector in the engine and discovery modules."""
    keys = set()
    for path in ("results/insights/engine.py", "results/insights/discovery.py"):
        tree = ast.parse((ROOT / path).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "explain_key":
                if isinstance(node.value, ast.Constant):
                    keys.add(node.value.value)
                elif isinstance(node.value, ast.JoinedStr):
                    keys.update({"cooccurrence_with", "cooccurrence_avoid"})
    return keys


def test_every_finding_has_an_explanation_and_a_figure():
    """No detector can emit a finding without both."""
    keys = emitted_explain_keys()
    assert {"interference", "isotope_groups", "replicate_flag", "time_rate"} <= keys
    for key in keys:
        assert key in EXPLANATIONS, key
        assert key in F.DESIGNS, key


def test_explanations_have_three_filled_paragraphs():
    """Each explanation says how it was found, how to read it, what to check."""
    for key, e in EXPLANATIONS.items():
        assert len(e.found) > 40 and e.meaning and e.check, key
    assert explanation_for("missing", "comparison") is EXPLANATIONS["comparison"]


def particles(seed=1, r67=1.18, sample=""):
    """Particles with Pb isotopes, Ce with a CeO+ shadow, Fe/Ti and all quantities."""
    rng = random.Random(seed)
    out = []
    for i in range(500):
        e = {}
        pb207 = math.exp(rng.gauss(4, 0.7))
        pb206 = pb207 * r67 * math.exp(rng.gauss(0, 0.03))
        if rng.random() < 0.7:
            e.update({"206Pb": pb206, "207Pb": pb207})
        if rng.random() < 0.5:
            ce = math.exp(rng.gauss(4, 0.9))
            e["140Ce"] = ce
            if ce * 0.02 > 1:
                e["156Gd"] = ce * 0.02
            e["139La"] = ce * 0.5
        if rng.random() < 0.6:
            fe = math.exp(rng.gauss(3, 0.7))
            e["56Fe"] = fe
            e["48Ti"] = fe * 0.5
        if not e:
            e["27Al"] = 2.0
        out.append({"elements": e,
                    "element_mass_fg": {k: v * 0.01 for k, v in e.items()},
                    "element_diameter_nm": {k: 20 * v ** (1 / 3) for k, v in e.items()},
                    "element_moles_fmol": {k: v * 0.001 for k, v in e.items()},
                    "start_time": i * 0.02, "end_time": i * 0.02 + 0.001,
                    "source_sample": sample})
    return out


@pytest.fixture(scope="module")
def stream():
    """Two samples as one canvas stream, and its particle table."""
    parts = particles(1, 1.18, "S1") + particles(2, 1.15, "S2")
    data = {"type": "multiple_sample_data", "sample_names": ["S1", "S2"],
            "particle_data": parts}
    return parts, table_for(data, "Counts")


ELEMENTS = {
    "interference": ("140Ce", "156Gd"), "isotope": ("206Pb", "207Pb"),
    "isotope_abundance": ("206Pb", "207Pb"), "isotope_two": ("206Pb", "207Pb"),
    "isotope_track": ("206Pb", "207Pb", "56Fe"), "isotope_groups": ("206Pb", "207Pb"),
    "comparison": ("56Fe",), "replicate_flag": ("56Fe", "48Ti"), "replicate_agree": ("56Fe",),
    "signature": ("140Ce",), "stoichiometry": ("56Fe", "48Ti"),
    "correlation": ("56Fe", "140Ce"), "cooccurrence_with": ("156Gd", "140Ce"),
    "cooccurrence_avoid": ("56Fe", "140Ce"), "rare": ("156Gd", "140Ce"), "quality": ("56Fe",),
    "distribution_two": ("56Fe",), "distribution_spread": ("56Fe",), "size": (),
    "time_rate": (), "time_signal": (), "composition": ("56Fe", "48Ti", "140Ce"),
    "network": ("56Fe", "48Ti", "140Ce", "139La"), "outlier": ("56Fe", "140Ce"),
}


@pytest.mark.parametrize("key", sorted(F.DESIGNS))
def test_every_design_draws(app, stream, key):
    """Each story draws without a panel error and ends with its legend."""
    from results.insights.discovery import _figure_spec
    parts, table = stream
    config = {}
    if key == "size":
        config = _figure_spec("Element Mass (fg)", kind="scatter", x="total",
                              y="mass:56Fe / total")
    elif key.startswith("time"):
        config = _figure_spec("Counts", kind="timeline", time_mode="signal", value="56Fe")
    s = rr.Suggestion("t", "r", key.split("_")[0], 0.5, "x", config=config,
                      elements=ELEMENTS[key], explain_key=key)
    ctx = F.context_from(parts, s.elements, {"56Fe": 2.0}, multi_sample=True)
    spec = F.figure_for(s, ctx)
    assert spec is not None
    plots, caption = spec["panels"][:-1], spec["panels"][-1]
    assert 2 <= len(plots) <= F.MAX_PANELS
    assert caption["kind"] == "text" and caption["caption"]
    assert caption["text"].count("(") >= len(plots)
    assert "(a) What Insights found" in caption["text"]
    assert spec["figure"]["panel_letters"]
    assert af.render_problems(spec, table) == []


def test_context_records_quantities_and_smallest_values():
    """The figure context sees counts, mass and size and the smallest detected values."""
    parts = particles(3, 1.18, "S")
    ctx = F.context_from(parts, ["56Fe"], {"56Fe": 2.5})
    assert {"counts", "mass", "d"} <= ctx.quantities
    smallest = min(p["element_mass_fg"]["56Fe"] for p in parts if "56Fe" in p["element_mass_fg"])
    assert ctx.smallest[("mass", "56Fe")] == pytest.approx(smallest)
    assert F._limit(ctx, "counts", "56Fe") == {"dl_value": "2.5",
                                              "dl_label": "Detection threshold"}
    assert F._limit(ctx, "mass", "56Fe")["dl_label"] == "Smallest detected"


def test_detection_thresholds_are_read_per_isotope_key():
    """Stored thresholds are matched to labels and averaged over time and samples."""
    class Window:
        selected_isotopes = {"Gd": [155.9221], "Pb": [206.9759]}
        element_thresholds = {"A": {"Gd-155.9221": {"threshold": [1.0, 2.0]}},
                              "B": {"Gd-155.9221": {"threshold": 2.5},
                                    "Pb-206.9759": {"threshold": 3.0}}}

        def get_formatted_label(self, key):
            """Label isotopes as mass number then symbol."""
            symbol, mass = key.split("-")
            return f"{round(float(mass))}{symbol}"

    out = ip.detection_thresholds(Window(), ["A", "B"], ["156Gd", "207Pb", "56Fe"])
    assert out == {"156Gd": pytest.approx(2.0), "207Pb": pytest.approx(3.0)}
    assert ip.detection_thresholds(object(), ["A"], ["156Gd"]) == {}


def test_card_shows_details_and_figure_action(app):
    """A card with numbers and an explanation offers details and the figure."""
    s = rr.Suggestion("156Gd looks like CeO⁺ from 140Ce", "r", "interference", 0.9,
                      "correlation_plot", elements=("140Ce", "156Gd"),
                      explain_key="interference", details=[("Particles with both", "481")])
    added = []
    card = ip._Card(s, on_add=lambda *_: None, on_figure=added.append)
    assert card._details is not None and card._details.isHidden()
    card._toggle_details()
    assert not card._details.isHidden()
    card._figure_btn.click()
    assert added == [s]


def test_story_panels_follow_the_explanation_order():
    """Captions run found, how it was found, how to read it, then checks."""
    s = rr.Suggestion("156Gd looks like CeO⁺ from 140Ce", "r", "interference", 0.9,
                      "correlation_plot", elements=("140Ce", "156Gd"), explain_key="interference",
                      details=[("Median suspect/parent", "2.0 %"), ("Likely species", "CeO⁺")])
    story = F._interference(s, F.FigureContext())
    starts = [caption.split(":")[0] for _panel, caption in story]
    assert starts == ["What Insights found", "How it was found", "How to read it", "Check"]
    assert "2.0 %" in story[1][1]


def test_story_layout_fits_six_panels_and_the_legend():
    """Six panels sit in three columns above a legend sized to its text."""
    rects, caption, width, height = F.story_layout(6, "x" * 400)
    assert len(rects) == 6 and width > 15
    assert caption[1] == pytest.approx(rects[-1][1] + rects[-1][3])
    assert caption[1] + caption[3] == pytest.approx(1.0)


def test_caption_panel_has_no_letter(app, stream):
    """The legend is not lettered, so the plots keep a to f."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    parts, table = stream
    s = rr.Suggestion("t", "r", "quality", 0.5, "x", elements=("56Fe",), explain_key="quality")
    spec = F.figure_for(s, F.context_from(parts, s.elements))
    fig = Figure()
    FigureCanvasAgg(fig)
    render(fig, spec, table)
    letters = sorted(t.get_text() for t in fig.texts
                     if getattr(t, "_fb_element", ("", ""))[1] == "letters")
    assert letters == [chr(ord("a") + i) for i in range(len(spec["panels"]) - 1)]


class _Scene:
    """Bare canvas scene for the panel."""

    workflow_nodes = []
    node_items = {}

    def selectedItems(self):
        """Return no selection."""
        return []


def _finished_panel(app, pool):
    """Run a panel to the end of its search over *pool*."""
    import time

    class Window:
        sample_particle_data = pool

    rr.invalidate_context_cache()
    panel = ip.SmartInsightsPanel(_Scene(), Window())
    panel._set_filter(None)
    panel.show()
    end = time.time() + 60
    while time.time() < end and not (panel._worker is None and panel._ran):
        app.processEvents()
        time.sleep(0.01)
    return panel


def test_filter_shows_exactly_the_picked_type(app):
    """Picking a plot type shows that type; picking all brings everything back."""
    pool = {"liver_1": particles(1, 1.18, ""), "liver_2": particles(2, 1.18, ""),
            "kidney_1": particles(3, 1.15, ""), "kidney_2": particles(4, 1.15, "")}
    panel = _finished_panel(app, pool)
    everything = len(panel._suggestions)
    types = {s.node_type for s in panel._suggestions}
    assert len(types) > 2
    for node_type in types:
        panel._type_actions[node_type].trigger()
        assert {s.node_type for s in panel._suggestions} == {node_type}
        assert panel.current_filter() == node_type
    panel._all_action.trigger()
    assert len(panel._suggestions) == everything
    assert all(a.isEnabled() == bool(len([s for s in panel._found if s.node_type == k]))
               for k, a in panel._type_actions.items())
    panel._teardown()


def test_new_findings_wait_while_the_pointer_is_over_the_list(app, monkeypatch):
    """Cards do not move under the pointer; new ones wait behind a bar."""
    pool = {"S1": particles(5, 1.18, ""), "S2": particles(6, 1.15, "")}
    panel = _finished_panel(app, pool)
    shown = dict(panel._cards)
    extra = rr.Suggestion("New finding", "r", "rare", 0.99, "heatmap_plot", elements=("56Fe",))
    monkeypatch.setattr(panel, "_pointer_over_list", lambda: True)
    panel._found.append(extra)
    panel._render(searching=True)
    assert panel._held and not panel._new_bar.isHidden()
    assert panel._cards == shown
    panel._release_held()
    assert not panel._held
    assert ip.card_key(extra) in panel._cards
    assert all(panel._cards[k] is card for k, card in shown.items() if k in panel._cards)
    panel._teardown()
