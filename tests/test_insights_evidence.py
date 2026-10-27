"""Measured legends, checks and the Figure Builder tools behind the explained figures."""

from __future__ import annotations

import math
import random
import zlib

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from results.figure_builder.core.expressions import ParticleTable
from results.insights import engine as rr
from results.insights import evidence as ev
from results.insights import figures as F
from tests.figure_checks import render_problems


@pytest.fixture(scope="module")
def app():
    """A Qt application for off-screen drawing."""
    return QApplication.instance() or QApplication([])


def lead_particles(seed: int, r76: float, name: str, n: int = 400) -> list[dict]:
    """Pb particles with Poisson-like counts, Fe in some of them, and arrival times."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        p206 = float(rng.lognormal(4.5, 0.6))
        e = {"206Pb": float(rng.poisson(p206)) or 1.0,
             "207Pb": float(rng.poisson(p206 * r76)) or 1.0,
             "208Pb": float(rng.poisson(p206 * 2.1)) or 1.0}
        if rng.random() < 0.5:
            e["56Fe"] = float(rng.lognormal(3, 0.5))
        out.append({"elements": e,
                    "element_mass_fg": {k: v * 0.01 for k, v in e.items()},
                    "element_moles_fmol": {k: v * 0.0001 for k, v in e.items()},
                    "start_time": i * 0.05, "end_time": i * 0.05 + 0.0005,
                    "source_sample": name})
    return out


@pytest.fixture(scope="module")
def pooled():
    """Two replicated materials, A and B, pooled the way a selector pools them."""
    pool = {}
    for g, r in (("A", 0.84), ("B", 0.88)):
        for k in range(3):
            name = f"{g}_{k + 1}"
            pool[name] = lead_particles(zlib.crc32(name.encode()) % 1000, r, name)
    units = [("A", ("A_1", "A_2", "A_3")), ("B", ("B_1", "B_2", "B_3"))]
    return pool, units, ev.table_from(units, pool)


def test_table_keeps_groups_and_replicates(pooled):
    """Pooled particles carry the group as sample and the replicate as original sample."""
    _pool, _units, table = pooled
    assert table.samples() == ["A", "B"]
    assert sorted(set(table.column("replicate").tolist())) == ["A_1", "A_2", "A_3", "B_1", "B_2", "B_3"]


def test_counting_noise_gives_excess_scatter_near_one(pooled):
    """Poisson counts scatter as counting statistics predict."""
    _pool, _units, table = pooled
    st = ev.ratio_spread(table, "207Pb", "206Pb", "206Pb >= 50", group=table.column("sample") == "A")
    assert 0.8 < st["excess"] < 1.3
    assert 0.9 < st["inside"] <= 1.0
    assert st["median"] == pytest.approx(0.84, rel=0.03)


def test_replicate_medians_and_test(pooled):
    """Three replicate medians per material, compared with a replicate-level test."""
    _pool, _units, table = pooled
    meds = ev.replicate_medians(table, "207Pb / 206Pb", "206Pb >= 50")
    assert [len(v) for v in meds.values()] == [3, 3]
    p, method = ev.replicate_test(meds, log=False)
    assert p < 0.01 and "replicate medians" in method
    assert ev.replicate_test({"A": [1.0], "B": [2.0, 2.1]})[0] is None


def test_size_classes_split_in_thirds(pooled):
    """Small, medium and large each hold about a third of the particles."""
    _pool, _units, table = pooled
    classes = ev.size_classes(table)
    assert [n for n, _m in classes] == ["small", "medium", "large"]
    sizes = [int(m.sum()) for _n, m in classes]
    assert max(sizes) - min(sizes) <= 0.05 * sum(sizes)


def test_coincidence_against_chance(pooled):
    """Sparse, short events make chance co-detection far rarer than the pairing seen."""
    _pool, _units, table = pooled
    c = ev.coincidence(table, "206Pb", "56Fe")
    assert c["observed"] > 100 and c["expected"] < 0.1 * c["observed"]


def test_exponential_law_factor():
    """The exponential law reproduces a certified reference ratio."""
    from results.figure_builder.core.isotopes import exponential_factor, split_factor
    k = exponential_factor("205Tl", "203Tl", "205Tl", "203Tl", 2.3871, 2.31)
    assert 2.31 * k == pytest.approx(2.3871)
    assert exponential_factor("207Pb", "206Pb", "205Tl", "203Tl", 1, 1) == pytest.approx(1.0)
    assert split_factor("(207Pb / 206Pb) * 1.0123") == ("207Pb / 206Pb", 1.0123)
    assert split_factor("207Pb / 206Pb") == ("207Pb / 206Pb", 1.0)


def test_isotope_sources_and_their_ratios():
    """Built-in sources give their ratios; a typed source line is read back."""
    from results.figure_builder.core import references as R
    R.set_user(None)
    r76 = R.source_ratio("Average crust (Stacey & Kramers 1975)", "207Pb", "206Pb")
    assert r76 == pytest.approx(15.628 / 18.700)
    name, comp = R.parse_isotope_source("Horne ore: 206Pb=17.0, 207Pb=15.4, 208Pb=36.9")
    assert name == "Horne ore" and comp["207Pb"] == 15.4
    with pytest.raises(ValueError):
        R.parse_isotope_source("no colon here")


def context(pooled, key, elements, bias=None):
    """A figure context over the pooled table."""
    pool, _units, table = pooled
    parts = [p for v in pool.values() for p in v]
    return F.context_from(parts, list(elements), {}, multi_sample=True, groups=2, table=table,
                          mass_bias=bias)


def test_isotope_figure_measures_and_checks(app, pooled):
    """The legend quotes measured numbers and closes with passed or failed checks."""
    s = rr.Suggestion("207Pb/206Pb", "r", "isotope", 0.8, "x", elements=("207Pb", "206Pb"),
                      explain_key="isotope_groups", facts={"ratio_cut": ("206Pb", 50.0)})
    ctx = context(pooled, "isotope_groups", s.elements)
    spec = F.figure_for(s, ctx)
    legend = spec["panels"][-1]["text"]
    assert "Measured" in legend and "Checks:" in legend
    assert "replicate medians" in legend and "excess scatter" in legend
    assert any(p.get("iso_refs") == "all" for p in spec["panels"])
    _pool, _units, table = pooled
    assert render_problems(spec, table) == []


def test_mass_bias_correction_reaches_the_ratio_panels(app, pooled):
    """With an exponential-law reference, ratio panels plot the corrected ratio."""
    bias = {"ref_num": "205Tl", "ref_den": "203Tl", "certified": 2.3871, "measured": 2.31}
    s = rr.Suggestion("207Pb/206Pb", "r", "isotope", 0.8, "x", elements=("207Pb", "206Pb"),
                      explain_key="isotope", facts={"ratio_cut": ("206Pb", 50.0)})
    spec = F.figure_for(s, context(pooled, "isotope", s.elements, bias))
    ratio_panels = [p for p in spec["panels"] if "206Pb" in str(p.get("value") or p.get("y"))]
    assert any(str(p.get("value") or p.get("y")).startswith("(207Pb / 206Pb) * ") for p in ratio_panels)
    assert "exponential law" in spec["panels"][-1]["text"]
    _pool, _units, table = pooled
    assert render_problems(spec, table) == []


def test_without_a_table_the_legend_has_no_checks(app, pooled):
    """No particle table, no measured numbers: the legend stays descriptive."""
    s = rr.Suggestion("Fe", "r", "comparison", 0.8, "x", elements=("56Fe",), explain_key="comparison")
    ctx = F.FigureContext(quantities={"counts", "mass"}, multi_sample=True, groups=2)
    legend = F.figure_for(s, ctx)["panels"][-1]["text"]
    assert "Checks:" not in legend and "Measured" not in legend


@pytest.mark.parametrize("key, elements", [
    ("comparison", ("56Fe",)), ("correlation", ("56Fe", "206Pb")),
    ("stoichiometry", ("207Pb", "206Pb")), ("cooccurrence_with", ("56Fe", "206Pb")),
    ("signature", ("56Fe",)), ("composition", ("56Fe", "206Pb", "207Pb")),
])
def test_stories_draw_with_their_checks(app, pooled, key, elements):
    """Each story draws from the pooled table, with legends placed under the plots."""
    s = rr.Suggestion("t", "r", key.split("_")[0], 0.8, "x", elements=elements, explain_key=key)
    spec = F.figure_for(s, context(pooled, key, elements))
    _pool, _units, table = pooled
    assert render_problems(spec, table) == []
    plots = [p for p in spec["panels"] if p["kind"] != "text"]
    assert all(p.get("legend_loc") in ("below", "ternary") for p in plots)
    assert all(p.get("marks_in_legend") for p in plots)


def test_legends_never_cover_the_plot(app, pooled):
    """Every legend of an explained figure sits outside its plot area."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    _pool, _units, table = pooled
    for key, elements in (("isotope_groups", ("207Pb", "206Pb")), ("comparison", ("56Fe",)),
                          ("correlation", ("56Fe", "206Pb"))):
        s = rr.Suggestion("t", "r", "isotope", 0.8, "x", elements=elements, explain_key=key,
                          facts={"ratio_cut": ("206Pb", 50.0)})
        spec = F.figure_for(s, context(pooled, key, elements))
        fig = Figure(figsize=(spec["figure"]["width"], spec["figure"]["height"]))
        FigureCanvasAgg(fig)
        report = render(fig, spec, table)
        renderer = fig.canvas.get_renderer()
        for pid, hd in report.artists.items():
            ax = hd.get("ax")
            leg = ax.get_legend() if ax is not None else None
            if leg is None or getattr(ax, "name", "") == "ternary":
                continue
            lb = leg.get_window_extent(renderer)
            ab = ax.get_window_extent(renderer)
            assert lb.y1 <= ab.y0 + 1 or lb.x0 >= ab.x1 - 1, (key, pid)


def test_replicate_medians_drawn_and_tested(app, pooled):
    """A box panel marks replicate medians and tests on them when asked."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    from results.figure_builder.core.spec import default_spec, make_panel, normalise_spec
    _pool, _units, table = pooled
    spec = default_spec()
    spec["panels"] = [make_panel(kind="box", value="207Pb / 206Pb", group_by="sample",
                                 filter="206Pb >= 50", rep_medians=True, test="welch",
                                 test_unit="replicates", rect=[0, 0, 1, 1])]
    spec = normalise_spec(spec)
    fig = Figure()
    FigureCanvasAgg(fig)
    report = render(fig, spec, table)
    assert not report.errors
    assert any("one value per replicate" in line for line in report.stats)
    ax = report.artists[spec["panels"][0]["id"]]["ax"]
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert "Replicate medians" in labels


def test_size_grouping_and_marks_in_legend(app, pooled):
    """Size thirds group a panel; the detection-limit line is named in the legend."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    from results.figure_builder.core.spec import default_spec, make_panel, normalise_spec
    _pool, _units, table = pooled
    spec = default_spec()
    spec["panels"] = [make_panel(kind="histogram", value="mass:56Fe", log_x=True, group_by="size",
                                 dl_value="0.2", dl_label="MDL", marks_in_legend=True,
                                 rect=[0, 0, 1, 1])]
    spec = normalise_spec(spec)
    fig = Figure()
    FigureCanvasAgg(fig)
    report = render(fig, spec, table)
    assert not report.errors
    ax = report.artists[spec["panels"][0]["id"]]["ax"]
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert any(t.startswith("Small") for t in labels) and any("MDL" in t for t in labels)
    assert not any(t.get_text().strip().startswith("MDL") for t in ax.texts)


def test_isotope_sources_drawn_on_a_three_isotope_plot(app, pooled):
    """Source points join the legend of a ratio-against-ratio plot."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    from results.figure_builder.core.spec import default_spec, make_panel, normalise_spec
    _pool, _units, table = pooled
    spec = default_spec()
    spec["panels"] = [make_panel(kind="scatter", x="207Pb / 206Pb", y="208Pb / 206Pb",
                                 iso_refs="all", rect=[0, 0, 1, 1])]
    spec = normalise_spec(spec)
    fig = Figure()
    FigureCanvasAgg(fig)
    report = render(fig, spec, table)
    assert not report.errors
    assert sum("Isotope source" in line for line in report.stats) == 2


def test_mass_bias_reference_read_from_an_isotopic_ratio_node():
    """The first exponential-law node with a complete reference is used; others are skipped."""
    from types import SimpleNamespace
    from results.insights.panel import EXPONENTIAL_LAW, mass_bias_reference
    off = SimpleNamespace(node_type="isotopic_ratio_plot", config={"correction_method": "None"})
    half = SimpleNamespace(node_type="isotopic_ratio_plot",
                           config={"correction_method": EXPONENTIAL_LAW, "ref_isotope_num": "205Tl",
                                   "ref_isotope_den": "", "ref_certified_ratio": 2.3871,
                                   "ref_measured_ratio": 2.31})
    full = SimpleNamespace(node_type="isotopic_ratio_plot",
                           config={"correction_method": EXPONENTIAL_LAW, "ref_isotope_num": "205Tl",
                                   "ref_isotope_den": "203Tl", "ref_certified_ratio": 2.3871,
                                   "ref_measured_ratio": 2.31})
    other = SimpleNamespace(node_type="histogram_plot", config={})
    assert mass_bias_reference(SimpleNamespace(workflow_nodes=[other, off, half])) is None
    ref = mass_bias_reference(SimpleNamespace(workflow_nodes=[off, half, full]))
    assert ref == {"ref_num": "205Tl", "ref_den": "203Tl", "certified": 2.3871, "measured": 2.31}
