"""The canvas correlation figure: fitted line and r box, colour bar and saturation check.

The fitted line, r and n are written in a box pinned to the top-left corner
of the plot, like the Figure Builder's legend; the colour scale is pinned to
the top-right corner; saturation is judged on counts whatever is plotted.
"""

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

import utils.unit as unit_mod
from utils.unit import ExportUnits
from results import results_correlation as rc
from results.shared_plot_utils import apply_saturation_filter


@pytest.fixture(scope="module")
def qapp():
    """The Qt application."""
    return QApplication.instance() or QApplication([])


def test_equation_reads_like_the_figure_builder():
    """Both log axes give a power law; a linear fit reads y = ax + b."""
    assert rc.line_equation_html(0.4, 5.124, True, True) == "y = 1.33×10<sup>5</sup>·x<sup>0.4</sup>"
    assert rc.line_equation_html(2.0, -1.5, False, False) == "y = 2x − 1.5"
    assert rc.line_equation_html(2.0, 0.5, False, True) == "log y = 2x + 0.5"


def test_stats_line_follows_the_toggles():
    """The equation follows the trend line toggle and r the correlation toggle."""
    x = np.array([1.0, 2.0, 3.0, 4.0])
    y = np.array([2.0, 4.1, 5.9, 8.0])
    both = rc._stats_line(x, y, {})
    assert both.startswith("y = ") and "r = 1.000" in both and "n = 4" in both
    only_r = rc._stats_line(x, y, {"show_trendline": False})
    assert only_r.startswith("r = ")
    assert rc._stats_line(x, y, {"show_trendline": False, "show_correlation": False}) == ""


def test_saturation_is_judged_on_counts_not_on_mass():
    """A 50 000 fg particle of 2 000 counts is not saturated; one of 20 000 counts is."""
    mass = pd.DataFrame({"Fe": [50000.0, 300.0], "Si": [10.0, 20.0]})
    mass.attrs["counts"] = pd.DataFrame({"Fe": [2000.0, 20000.0], "Si": [5.0, 9.0]})
    kept = apply_saturation_filter(mass, {"filter_saturated": True, "saturation_threshold": 10000})
    assert kept["Fe"].tolist() == [50000.0]


def test_plot_data_carries_the_counts():
    """Mass tables built for the figure keep the particles' counts alongside."""
    particles = [{"elements": {"24Mg": 10.0}, "element_mass_fg": {"24Mg": 5e5}}]
    df = rc._matrix_with_counts(particles, "element_mass_fg")
    assert df.attrs["counts"]["24Mg"].tolist() == [10.0]


def test_box_and_colour_bar_are_pinned_to_the_plot(qapp):
    """Big masses in ag are all drawn, with the box and colour bar in the plot's corners."""
    unit_mod.units.set(ExportUnits(mass_unit="ag"))
    rng = np.random.default_rng(1)
    parts = [{"source_sample": "S", "elements": {"24Mg": 50.0, "28Si": 40.0, "27Al": 30.0},
              "element_mass_fg": {"24Mg": float(m), "28Si": float(m) * 0.8, "27Al": float(a)}}
             for m, a in zip(rng.lognormal(8, 0.4, 60), rng.lognormal(7, 0.4, 60))]
    node = rc.CorrelationPlotNode()
    node.config.update({"x_element": "24Mg", "y_element": "28Si", "color_element": "27Al",
                        "data_type_display": "Element Mass (fg)", "log_x": True, "log_y": True})
    node.process_data({"type": "sample_data", "particle_data": parts})
    dlg = rc.CorrelationPlotDisplayDialog(node)
    dlg._refresh()
    pi = dlg.plot_widget.getItem(0, 0)
    children = pi.vb.childItems()
    boxes = [c for c in children if isinstance(c, rc.pg.TextItem)]
    assert boxes and "n = 60" in boxes[0].toHtml()
    assert any(type(c).__name__ == "InsetColorBarItem" for c in children)
    assert "(ag)" in pi.getAxis("bottom").labelText
    assert not pi.getAxis("bottom").autoSIPrefix
    dlg.close()
