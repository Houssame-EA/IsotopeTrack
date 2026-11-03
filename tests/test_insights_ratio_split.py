"""Tests for ratios that split by a third element, and the figure pieces that show them."""

from __future__ import annotations

import numpy as np
import pytest

from results.insights import discovery as disc
from results.insights import engine as rr
from results.insights import figures as F
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


def powder(seed, al_ratio=1.95, plain_ratio=4.36, n=1500, al_share=0.2):
    """Talc-like particles: Si/Mg near 4.4 without Al, lower with Al, Poisson counts."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        mg_true = rng.lognormal(np.log(220), 0.7)
        has_al = rng.random() < al_share
        r = rng.lognormal(np.log(al_ratio if has_al else plain_ratio), 0.08)
        e = {"24Mg": float(max(rng.poisson(mg_true), 1)),
             "28Si": float(max(rng.poisson(mg_true * r), 1))}
        if has_al:
            e["27Al"] = float(max(rng.poisson(mg_true * 0.4), 3))
        if rng.random() < 0.3:
            e["56Fe"] = float(rng.poisson(50) + 1)
        out.append({"elements": e, "start_time": i * 0.02, "end_time": i * 0.02 + 0.001})
    return out


def context(pool):
    """Analysis context over *pool*."""
    rr.invalidate_context_cache()
    return rr.build_context(FakeScene(), FakeWindow(pool))


def test_si_mg_split_by_al_is_found():
    """Si/Mg takes two values sorted by Al, and the card names all three elements."""
    ctx = context({"Powder": powder(1)})
    found = disc.analyse_ratio_split(ctx)
    card = next(s for s in found if s.elements == ("28Si", "24Mg", "27Al"))
    assert card.category == "ratio_split" and card.node_type == "figure_builder"
    w, wo = card.facts["medians"]
    assert w == pytest.approx(1.95, rel=0.1) and wo == pytest.approx(4.36, rel=0.1)
    panel = card.config["panels"][0]
    assert panel["show_missing"] and panel["poisson_band"] == 2.0
    assert panel["color_by"] == "log10(27Al)" and panel["y"] == "28Si / 24Mg"


def test_one_phase_gives_no_split():
    """The same ratio with and without Al is not a finding."""
    ctx = context({"Powder": powder(2, al_ratio=4.36)})
    assert not [s for s in disc.analyse_ratio_split(ctx) if "27Al" in s.elements]


def test_split_is_checked_in_each_replicate():
    """Both replicates show the split, so the card holds in 2 of 2."""
    pool = {"Powder_1": powder(3), "Powder_2": powder(4)}
    ctx = context(pool)
    found = rr.analyse(ctx, categories=["ratio_split"])
    card = next(s for s in found if s.elements == ("28Si", "24Mg", "27Al"))
    assert card.evidence is not None
    assert card.evidence.n_ok == 2 and card.evidence.reproducible is True


def test_explained_figure_draws_and_reports_checks():
    """The five-panel story draws without errors and its legend carries the checks."""
    from tests.figure_checks import render_problems, table_for
    pool = {"Powder_1": powder(5), "Powder_2": powder(6)}
    parts = []
    for name, ps in pool.items():
        for p in ps:
            q = dict(p)
            q["source_sample"] = "Powder"
            q["original_sample"] = name
            parts.append(q)
    table = table_for({"type": "multiple_sample_data", "sample_names": ["Powder"],
                       "particle_data": parts}, "Counts")
    s = rr.Suggestion("28Si/24Mg splits by 27Al", "r", "ratio_split", 0.8, "figure_builder",
                      elements=("28Si", "24Mg", "27Al"), explain_key="ratio_split")
    ctx = F.context_from(parts, s.elements, {}, table=table)
    spec = F.figure_for(s, ctx)
    assert spec is not None and len(spec["panels"]) == 6
    legend = spec["panels"][-1]["text"]
    assert "Checks:" in legend and "✓ the two populations' ratios differ" in legend
    assert render_problems(spec, table) == []


def test_scatter_keeps_particles_without_a_colour_value_in_grey():
    """With show_missing, particles lacking the colour element are drawn, not dropped."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    from tests.figure_checks import table_for
    parts = powder(7, n=400)
    table = table_for({"type": "sample_data", "sample_name": "P", "particle_data": parts},
                      "Counts")
    spec = disc._figure_spec("Counts", **disc.ratio_split_panel("28Si", "24Mg", "27Al"))
    counts = []
    for show in (False, True):
        spec["panels"][0]["show_missing"] = show
        fig = Figure()
        FigureCanvasAgg(fig)
        rep = render(fig, spec, table)
        assert not rep.errors
        counts.append(rep.counts[spec["panels"][0]["id"]])
    with_al = sum("27Al" in p["elements"] for p in parts)
    assert counts[0] == with_al and counts[1] == len(parts)


def test_short_last_row_is_centred():
    """Five panels: three on top, the last two centred beneath them."""
    rects, _cap, _w, _h = F.story_layout(5, "legend")
    assert [round(r[0], 3) for r in rects] == [0.0, 0.333, 0.667, 0.167, 0.5]
    rects, _cap, _w, _h = F.story_layout(6, "legend")
    assert [round(r[0], 3) for r in rects[3:]] == [0.0, 0.333, 0.667]
    rects, _cap, _w, _h = F.story_layout(4, "legend")
    assert [round(r[0], 3) for r in rects] == [0.0, 0.5, 0.0, 0.5]
