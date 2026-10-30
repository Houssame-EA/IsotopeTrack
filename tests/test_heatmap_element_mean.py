"""Ranking heatmap combinations by the mean of one element per particle."""

from __future__ import annotations

from results.results_heatmap import _element_mean, _element_total


def test_mean_ignores_the_number_of_particles():
    """20 particles of 0.2 fg Pb rank above 200 particles of 0.03 fg, unlike the total."""
    data = {
        "208Pb": {"particle_count": 200, "total_values": {"208Pb": [0.03] * 200}},
        "63Cu, 208Pb": {"particle_count": 20,
                        "total_values": {"208Pb": [0.2] * 20, "63Cu": [1.0] * 20}},
    }
    by_mean = sorted(data, key=lambda c: _element_mean(data[c], "Pb"), reverse=True)
    by_total = sorted(data, key=lambda c: _element_total(data[c], "Pb"), reverse=True)
    assert by_mean == ["63Cu, 208Pb", "208Pb"]
    assert by_total == ["208Pb", "63Cu, 208Pb"]
    assert abs(_element_mean(data["208Pb"], "Pb") - 0.03) < 1e-12


def test_mean_of_missing_element_and_non_detects():
    """No element gives zero; NaN and non-positive values are left out of the mean."""
    assert _element_mean({"total_values": {"63Cu": [1.0]}}, "Pb") == 0.0
    assert _element_mean({"total_values": {"208Pb": [1.0, 3.0, float("nan"), -2.0]}}, "Pb") == 2.0
