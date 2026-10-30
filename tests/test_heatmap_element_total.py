"""Ranking Heatmap node combinations by the total of one element."""

from __future__ import annotations

from results.results_heatmap import _element_total, _label_symbol


def test_symbol_of_labels():
    """Mass-first, mass-last and bare labels give the same symbol."""
    assert _label_symbol("208Pb") == "Pb"
    assert _label_symbol("Pb208") == "Pb"
    assert _label_symbol("Pb") == "Pb"


def test_total_ranks_the_heavier_combination_first():
    """2000 Pb particles holding 50 fg rank below 1500 PbCu particles holding 500 fg."""
    data = {
        "208Pb": {"particle_count": 2000, "total_values": {"208Pb": [0.025] * 2000}},
        "63Cu, 208Pb": {"particle_count": 1500,
                        "total_values": {"208Pb": [500 / 1500] * 1500, "63Cu": [1.0] * 1500}},
    }
    ranked = sorted(data, key=lambda c: _element_total(data[c], "Pb"), reverse=True)
    assert ranked == ["63Cu, 208Pb", "208Pb"]
    assert abs(_element_total(data["208Pb"], "Pb") - 50) < 1e-9
    assert abs(_element_total(data["63Cu, 208Pb"], "208Pb") - 500) < 1e-6


def test_missing_element_and_non_detects_add_nothing():
    """A combination without the element totals zero; NaN and negatives are ignored."""
    assert _element_total({"total_values": {"63Cu": [1.0]}}, "Pb") == 0.0
    assert _element_total({"total_values": {"208Pb": [1.0, float("nan"), -2.0]}}, "Pb") == 1.0
