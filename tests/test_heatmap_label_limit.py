"""Shortening Heatmap node row labels to the largest elements."""

from __future__ import annotations

from results.results_heatmap import _label_elements


def test_the_smallest_elements_are_left_out():
    """With a limit of 4, Pb (least signal) is dropped and the mass order is kept."""
    values = {"52Cr": [2.0], "63Cu": [3.0], "80Se": [1.5], "107Ag": [4.0], "208Pb": [0.1]}
    label, cut = _label_elements("52Cr, 63Cu, 80Se, 107Ag, 208Pb", values, 4)
    assert label == "52Cr, 63Cu, 80Se, 107Ag"
    assert cut


def test_short_combinations_and_no_limit_are_unchanged():
    """A label within the limit, or a limit of 0, is returned as it is."""
    values = {"63Cu": [1.0], "107Ag": [2.0]}
    assert _label_elements("63Cu, 107Ag", values, 4) == ("63Cu, 107Ag", False)
    assert _label_elements("63Cu, 107Ag", values, 0) == ("63Cu, 107Ag", False)
