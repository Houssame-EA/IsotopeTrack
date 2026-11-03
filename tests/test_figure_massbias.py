"""Tests for mass-bias correction of isotope ratios in Figure Builder panels."""

from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pytest

from results.figure_builder.core import massbias as mb
from results.figure_builder.core.expressions import ParticleTable, pretty
from results.figure_builder.core.isotopes import exponential_factor, split_factor
from results.figure_builder.core.spec import default_spec, make_panel, normalise_spec

TRUE = 1.15
CERT = 2.3871
TL = {"A": 2.3300, "B": 2.3520}


def stream(with_tl_particles=False, seed=1):
    """Two samples whose Pb ratio reads low by each sample's own Tl bias."""
    rng = np.random.default_rng(seed)
    parts = []
    for s, tl in TL.items():
        k = exponential_factor("206Pb", "207Pb", "205Tl", "203Tl", CERT, tl)
        for _ in range(800):
            lam = rng.lognormal(np.log(300), 0.6)
            e = {"206Pb": float(rng.poisson(lam * TRUE / k)) + 1, "207Pb": float(rng.poisson(lam)) + 1}
            if with_tl_particles:
                t = rng.lognormal(np.log(200), 0.4)
                e["205Tl"] = t * tl
                e["203Tl"] = t
            parts.append({"elements": e, "source_sample": s, "original_sample": s})
    return ParticleTable.from_input({"type": "multiple_sample_data", "sample_names": list(TL),
                                     "particle_data": parts}, "Counts")


def panel(**kw):
    """A ratio scatter with the exponential law, reference typed on the panel."""
    base = dict(kind="scatter", x="207Pb", y="206Pb / 207Pb", mb_method="exponential",
                mb_source="manual", mb_ref="205Tl / 203Tl", mb_certified=str(CERT),
                group_by="sample")
    base.update(kw)
    return make_panel(**base)


def ratio_of_sums(table, expr_panel, sample):
    """Corrected ratio of one sample from a prepared panel, as summed counts times the factor."""
    from results.figure_builder.core.expressions import evaluate
    y = evaluate(expr_panel["y"], table)
    m = table.column("sample") == sample
    return float(np.median(y[m]))


def test_one_typed_value_corrects_every_sample_alike():
    """With one measured value, every particle gets the same exponential-law factor."""
    table = stream()
    out = mb.prepare(panel(mb_measured_mode="value", mb_measured="2.33"), table)
    assert out["y"].startswith("(206Pb / 207Pb) * mb_")
    name = out["y"].split("* ")[1]
    k = exponential_factor("206Pb", "207Pb", "205Tl", "203Tl", CERT, 2.33)
    assert np.allclose(table.factors[name], k)


def test_ionic_reference_is_measured_in_each_sample():
    """Each sample's own Tl ratio brings both samples to the same corrected ratio."""
    table = stream()
    table.ionic_ratio = lambda s, a, b: TL[s] if (a, b) == ("205Tl", "203Tl") else None
    report = SimpleNamespace(stats=[])
    out = mb.prepare(panel(mb_measured_mode="ionic"), table, report)
    a, b = ratio_of_sums(table, out, "A"), ratio_of_sums(table, out, "B")
    assert a == pytest.approx(b, rel=0.01)
    assert any("A ×" in line and "B ×" in line for line in report.stats)


def test_particle_reference_uses_co_detected_summed_counts():
    """Measured from particles, the Tl ratio is the summed-count ratio of particles with both."""
    table = stream(with_tl_particles=True)
    ratios, notes = mb.measured_by_sample(panel(mb_measured_mode="particles"), table,
                                          {"ref_num": "205Tl", "ref_den": "203Tl",
                                           "certified": CERT, "measured": None})
    assert ratios["A"] == pytest.approx(TL["A"], rel=1e-9)
    assert ratios["B"] == pytest.approx(TL["B"], rel=1e-9)
    assert not notes


def test_missing_sample_reference_falls_back_to_the_typed_value_and_says_so():
    """A sample with no ionic Tl uses the typed value; the notes name it."""
    table = stream()
    table.ionic_ratio = lambda s, a, b: TL["A"] if s == "A" else None
    report = SimpleNamespace(stats=[])
    mb.prepare(panel(mb_measured_mode="ionic", mb_measured="2.34"), table, report)
    assert any("in B; the typed value 2.34 is used" in line for line in report.stats)


def test_incomplete_reference_leaves_the_panel_alone_with_a_reason():
    """No certified ratio: nothing is rewritten and the report says why."""
    table = stream()
    report = SimpleNamespace(stats=[])
    out = mb.prepare(panel(mb_certified="", mb_measured_mode="value", mb_measured="2.33"),
                     table, report)
    assert out["y"] == "206Pb / 207Pb"
    assert any("certified ratio" in line for line in report.stats)


def test_node_reference_is_read_from_the_canvas():
    """The Isotopic Ratio node's exponential-law settings are used when asked."""
    node = SimpleNamespace(node_type="isotopic_ratio_plot", config={
        "correction_method": mb.EXPONENTIAL_LAW, "ref_isotope_num": "205Tl",
        "ref_isotope_den": "203Tl", "ref_certified_ratio": CERT, "ref_measured_ratio": 2.33})
    table = stream()
    mb.attach(table, None, SimpleNamespace(workflow_nodes=[node]))
    out = mb.prepare(panel(mb_source="node", mb_ref="", mb_certified="",
                           mb_measured_mode="value"), table)
    name = out["y"].split("* ")[1]
    k = exponential_factor("206Pb", "207Pb", "205Tl", "203Tl", CERT, 2.33)
    assert np.allclose(table.factors[name], k)


def test_label_split_factor_and_band_follow_the_corrected_ratio():
    """The axis says corrected, split_factor finds the plain ratio, the band uses each group's factor."""
    table = stream()
    table.ionic_ratio = lambda s, a, b: TL[s]
    out = mb.prepare(panel(mb_measured_mode="ionic"), table)
    assert pretty(out["y"], table).endswith("(corrected)")
    assert split_factor(out["y"]) == ("206Pb / 207Pb", 1.0)
    m = table.column("sample") == "B"
    k_b = exponential_factor("206Pb", "207Pb", "205Tl", "203Tl", CERT, TL["B"])
    assert mb.group_factor(out, table, m) == pytest.approx(k_b)


def test_figure_draws_corrected_with_the_band_and_no_errors():
    """A full render: corrected ratio, counting band per sample, notes in the report."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    table = stream()
    table.ionic_ratio = lambda s, a, b: TL[s]
    spec = default_spec()
    spec["panels"] = [panel(mb_measured_mode="ionic", poisson_band=2.0, rect=[0, 0, 0.5, 1]),
                      panel(kind="histogram", value="206Pb / 207Pb", mb_measured_mode="ionic",
                            rect=[0.5, 0, 0.5, 1])]
    spec = normalise_spec(spec)
    fig = Figure()
    FigureCanvasAgg(fig)
    rep = render(fig, spec, table)
    assert not rep.errors
    means = [line for line in rep.stats if "mean ratio" in line]
    assert all("(measured " in line for line in means)
    vals = [float(line.split("mean ratio ")[1].split(" ")[0]) for line in means]
    assert len(vals) == 2 and vals[0] == pytest.approx(vals[1], rel=0.01)
    assert sum("Mass-bias correction, exponential law" in line for line in rep.stats) == 2
    assert spec["panels"][0]["y"] == "206Pb / 207Pb"


def test_uncorrected_panels_and_other_expressions_are_untouched():
    """No correction chosen, or a non-ratio expression: the panel comes back as it was."""
    table = stream()
    p = panel(mb_method="none")
    assert mb.prepare(p, table) is p
    out = mb.prepare(panel(y="206Pb + 207Pb", mb_measured_mode="value", mb_measured="2.33"), table)
    assert out["y"] == "206Pb + 207Pb"


def test_parse_pair():
    """Reference pairs are read with a slash or a colon."""
    assert mb.parse_pair("205Tl / 203Tl") == ("205Tl", "203Tl")
    assert mb.parse_pair("205Tl:203Tl") == ("205Tl", "203Tl")
    assert mb.parse_pair("205Tl") is None
