"""Isotope ratios from counts, mass-bias references from co-detected counts, and the counting band."""

from __future__ import annotations

import types

import numpy as np
import pandas as pd
import pytest

from results.figure_builder.core.isotopes import (
    counting_envelope, counts_for_isotope_ratios, is_count_ratio, particle_sigma, same_element)

TRUE = 1.15
SENS = {"206Pb": 30.0, "207Pb": 30.0 / 1.093 * 0.9}


def particles(n=600, seed=2, sample="S", tl=None):
    """Pb particles in counts and in fg, each isotope with its own counts-per-fg slope."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        lam = rng.lognormal(np.log(250), 0.6)
        c = {"206Pb": float(rng.poisson(lam * TRUE)) + 1, "207Pb": float(rng.poisson(lam)) + 1}
        if tl is not None:
            t = rng.lognormal(np.log(150), 0.3)
            c["205Tl"], c["203Tl"] = t * tl, t
        out.append({"elements": c,
                    "element_mass_fg": {k: v / SENS.get(k, 10.0) for k, v in c.items()},
                    "source_sample": sample, "original_sample": sample})
    return out


def test_same_element_and_count_ratio_rules():
    """Isotopes of one element are recognised; only ratios read in counts count as count ratios."""
    assert same_element("206Pb", "207Pb") and not same_element("28Si", "24Mg")
    assert is_count_ratio("206Pb / 207Pb") and is_count_ratio("counts:206Pb / counts:207Pb")
    assert not is_count_ratio("mass:206Pb / mass:207Pb")
    assert is_count_ratio("(206Pb / 207Pb) * mb_ab12_206Pb207Pb")


def test_figure_in_mass_reads_isotope_ratios_in_counts_and_keeps_x():
    """In mass, 206Pb/207Pb is rewritten to counts; X and element ratios stay in mass."""
    from results.figure_builder.core.expressions import ParticleTable, evaluate
    table = ParticleTable.from_input({"type": "sample_data", "sample_name": "S",
                                      "particle_data": particles()}, "Element Mass (fg)")
    panel = {"x": "207Pb", "y": "206Pb / 207Pb", "value": "28Si / 24Mg"}
    out = counts_for_isotope_ratios(panel, table)
    assert out["y"] == "counts:206Pb / counts:207Pb"
    assert out["x"] == "207Pb" and out["value"] == "28Si / 24Mg"
    y = evaluate(out["y"], table)
    assert np.median(y) == pytest.approx(TRUE, rel=0.03)
    mass_ratio = evaluate("206Pb / 207Pb", table)
    assert np.median(mass_ratio) != pytest.approx(TRUE, rel=0.03)
    assert counts_for_isotope_ratios({"y": "mass:206Pb / mass:207Pb"}, table)["y"] == \
        "mass:206Pb / mass:207Pb"


def test_envelope_is_the_same_on_counts_and_on_mass_axes():
    """With X proportional to N, the band along mass equals the band along counts, point for point."""
    rng = np.random.default_rng(0)
    n = rng.lognormal(np.log(300), 0.8, 2000)
    sens = 25.0
    xs_c, lo_c, hi_c = counting_envelope(n, n, TRUE, 2.0)
    xs_m, lo_m, hi_m = counting_envelope(n / sens, n, TRUE, 2.0)
    assert np.allclose(xs_m * sens, xs_c, rtol=1e-6)
    assert np.allclose(hi_m, hi_c, rtol=0.02)
    assert np.allclose(lo_m, lo_c, rtol=0.02, atol=1e-3)
    assert np.allclose(particle_sigma([100.0], TRUE), np.sqrt(TRUE * (1 + TRUE) / 100.0))


def test_figure_builder_band_works_with_mass_on_x():
    """A Figure Builder scatter in mass keeps the band and finds about 95% inside ±2σ."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    from results.figure_builder.core.expressions import ParticleTable
    from results.figure_builder.core.spec import default_spec, make_panel, normalise_spec
    table = ParticleTable.from_input({"type": "sample_data", "sample_name": "S",
                                      "particle_data": particles(1500)}, "Element Mass (fg)")
    spec = default_spec()
    spec["panels"] = [make_panel(rect=[0, 0, 1, 1], kind="scatter", x="207Pb", y="206Pb / 207Pb",
                                 poisson_band=2.0)]
    fig = Figure()
    FigureCanvasAgg(fig)
    rep = render(fig, normalise_spec(spec), table)
    assert not rep.errors
    line = next(l for l in rep.stats if "counting-statistics band" in l and "inside" in l)
    share = float(line.split("; ")[1].split("%")[0])
    assert 90 <= share <= 99
    assert float(line.split("mean ratio ")[1].split(";")[0]) == pytest.approx(TRUE, rel=0.03)


def test_mass_bias_is_not_applied_to_a_mass_ratio():
    """A mass ratio is left uncorrected, with the reason in the notes."""
    from types import SimpleNamespace
    from results.figure_builder.core import massbias as mb
    from results.figure_builder.core.expressions import ParticleTable
    from results.figure_builder.core.spec import make_panel
    table = ParticleTable.from_input({"type": "sample_data", "sample_name": "S",
                                      "particle_data": particles()}, "Element Mass (fg)")
    report = SimpleNamespace(stats=[])
    p = make_panel(kind="scatter", x="207Pb", y="mass:206Pb / mass:207Pb", mb_method="exponential",
                   mb_source="manual", mb_ref="205Tl / 203Tl", mb_certified="2.3871",
                   mb_measured_mode="value", mb_measured="2.33")
    out = mb.prepare(p, table, report)
    assert out["y"] == "mass:206Pb / mass:207Pb"
    assert any("applies to a ratio of counts" in l for l in report.stats)


class _Stub:
    """Enough of the Isotopic Ratio dialog to run its sample preparation."""

    parent_window = None

    def __init__(self, config):
        from results import results_isotope as ri
        self.node = types.SimpleNamespace(config=config)
        cls = ri.IsotopicRatioDisplayDialog
        for name in ("_prepare_sample", "_correct_per_replicate", "_compute_replicate_ref_ratio",
                     "_ratio_from_time_series"):
            setattr(self, name, types.MethodType(getattr(cls, name), self))


def node_table(parts, dk):
    """The node's per-sample table, built as extract_plot_data builds it."""
    from results import results_isotope as ri
    from results.shared_plot_utils import build_element_matrix
    df = ri.with_counts(build_element_matrix(parts, dk), parts, dk)
    df["_source_sample"] = [p["source_sample"] for p in parts]
    df["_original_sample"] = [p["original_sample"] for p in parts]
    return df


def test_node_ratio_is_from_counts_in_mass_mode():
    """With mass on X, the node's ratio is the count ratio and X is the mass."""
    parts = particles()
    cfg = {"element1": "206Pb", "element2": "207Pb", "data_type_display": "Element Mass (fg)",
           "correction_method": "None"}
    res = _Stub(cfg)._prepare_sample(node_table(parts, "element_mass_fg"), cfg)
    x, ratios, _n, _c, corrected, mean_raw = res
    assert np.median(ratios) == pytest.approx(TRUE, rel=0.03)
    assert mean_raw == pytest.approx(np.mean([p["elements"]["206Pb"] / p["elements"]["207Pb"]
                                              for p in parts]))
    assert np.median(x) < 50
    assert np.allclose(res.band["counts"] / SENS["207Pb"], res.band["x"])


def test_node_per_replicate_reference_uses_co_detected_counts():
    """Two replicates with different Tl: each corrected with its own counts-based reference."""
    from results.figure_builder.core.isotopes import exponential_factor
    parts = particles(500, 1, "R1", tl=2.33) + particles(500, 2, "R2", tl=2.352)
    for p in parts:
        p["source_sample"] = "Pooled"
    cfg = {"element1": "206Pb", "element2": "207Pb", "data_type_display": "Element Mass (fg)",
           "correction_method": "Exponential Law (instrumental mass fractionation)",
           "ref_isotope_num": "205Tl", "ref_isotope_den": "203Tl", "ref_certified_ratio": 2.3871,
           "ref_measured_ratio": 2.3}
    res = _Stub(cfg)._prepare_sample(node_table(parts, "element_mass_fg"), cfg)
    f = res.band["factor"]
    k1 = exponential_factor("206Pb", "207Pb", "205Tl", "203Tl", 2.3871, 2.33)
    k2 = exponential_factor("206Pb", "207Pb", "205Tl", "203Tl", 2.3871, 2.352)
    assert np.allclose(np.unique(np.round(f, 8)), sorted([round(k1, 8), round(k2, 8)]))


def test_node_log_x_keeps_corrected_values_aligned():
    """With log X, points dropped for x <= 0 are dropped from the corrected values too."""
    parts = particles(300)
    df = node_table(parts, "elements")
    df.loc[df.index[:5], "207Pb"] = 0.0
    df.loc[df.index[:5], "_counts_207Pb"] = 0.0
    cfg = {"element1": "206Pb", "element2": "207Pb", "data_type_display": "Counts",
           "correction_method": "None", "log_x": True}
    x, ratios, _n, _c, corrected, _m = _Stub(cfg)._prepare_sample(df, cfg)
    assert len(x) == len(ratios) == len(corrected)
