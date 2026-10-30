"""Fit equation on scatters, edge plots in another unit, and median and mode isotope-ratio lines."""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from results.figure_builder.charts.xy import line_equation
from results.figure_builder.core.expressions import ParticleTable


@pytest.fixture(scope="module")
def app():
    """A Qt application for off-screen drawing."""
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def table():
    """Fe and Cu particles carrying counts, mass, moles and diameter."""
    rng = np.random.default_rng(4)
    parts = []
    for _ in range(300):
        fe = float(rng.lognormal(3, 0.5))
        cu = fe * 0.5 * float(rng.lognormal(0, 0.1))
        e = {"56Fe": fe, "63Cu": cu}
        parts.append({"elements": e,
                      "element_mass_fg": {k: v * 0.02 for k, v in e.items()},
                      "element_moles_fmol": {k: v * 0.0003 for k, v in e.items()},
                      "element_diameter_nm": {k: 30 * v ** (1 / 3) for k, v in e.items()},
                      "source_sample": "S"})
    return ParticleTable.from_input({"type": "sample_data", "sample_name": "S",
                                     "particle_data": parts}, "Counts")


def render(table, **panel):
    """Draw one scatter panel; return the report, its handles and the figure."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render as draw
    from results.figure_builder.core.spec import default_spec, make_panel, normalise_spec
    spec = default_spec()
    spec["panels"] = [make_panel(kind="scatter", x="56Fe", y="63Cu", rect=[0, 0, 1, 1], **panel)]
    spec = normalise_spec(spec)
    fig = Figure(figsize=(6, 5))
    FigureCanvasAgg(fig)
    report = draw(fig, spec, table)
    assert not report.errors, report.errors
    return report, report.artists[spec["panels"][0]["id"]], fig


def test_equation_follows_the_axes():
    """Linear, log–log and one-log fits are written for the axes they are on."""
    assert line_equation(2.0, -0.5, False, False) == "y = 2x − 0.5"
    assert line_equation(1.02, np.log10(0.5), True, True) == "y = 0.5·x$^{1.02}$"
    assert line_equation(0.3, 1.0, False, True) == "log y = 0.3x + 1"
    assert line_equation(4.0, 2.0, True, False) == "y = 4·log x + 2"


def test_scatter_shows_the_equation_not_r(app, table):
    """The fit text on the plot is the line's equation; r stays in the statistics."""
    report, hd, _fig = render(table, show_fit=True, show_r=True, log_x=True, log_y=True)
    texts = [t.get_text() for t in hd["ax"].texts if getattr(t, "_fb_r", False)]
    assert texts and texts[0].startswith("y = ") and "x$^{" in texts[0]
    assert not any("R²" in t or "r = " in t for t in texts)
    assert any("Pearson r" in line for line in report.stats)


def test_edges_in_mass_use_their_own_scale(app, table):
    """Edges in fg show the particles' mass on their own labelled scale."""
    _report, hd, _fig = render(table, marginals="hist", marginals_unit="mass", log_x=True,
                               log_y=True)
    top, right, ax = hd["marg_top"], hd["marg_right"], hd["ax"]
    assert top.get_xlabel().endswith("mass (fg)") and right.get_ylabel().endswith("mass (fg)")
    lo, hi = top.get_xlim()
    assert hi < 100 and ax.get_xlim()[1] > hi
    assert top.get_shared_x_axes().get_siblings(top) == [top]


def test_edges_in_the_axes_quantity_stay_shared(app, table):
    """By default the edges share the scatter's axes, as before."""
    _report, hd, _fig = render(table, marginals="hist", log_x=True, log_y=True)
    assert hd["ax"] in hd["marg_top"].get_shared_x_axes().get_siblings(hd["marg_top"])


def test_edge_titles_use_the_isotope_style(app, table):
    """Automatic edge titles are written like the main axes' titles."""
    _report, hd, _fig = render(table, marginals="hist", marginals_unit="mass", log_x=True,
                               log_y=True)
    assert "$^{" in hd["marg_top"].get_xlabel()
    assert "$^{" in hd["marg_right"].get_ylabel()


def test_typed_edge_titles_replace_the_automatic_ones(app, table):
    """Typed titles name the edges, whatever quantity they show."""
    for unit in ("mass", "same"):
        _report, hd, _fig = render(table, marginals="kde", marginals_unit=unit,
                                   marg_top_label="Fe in fg", marg_right_label="Cu in fg")
        assert hd["marg_top"].get_xlabel() == "Fe in fg"
        assert hd["marg_right"].get_ylabel() == "Cu in fg"


def test_shared_edges_stay_untitled_by_default(app, table):
    """Edges sharing the axes' quantity get no title unless one is typed."""
    _report, hd, _fig = render(table, marginals="hist")
    assert hd["marg_top"].get_xlabel() == "" and hd["marg_right"].get_ylabel() == ""


def test_ratio_mode_is_the_density_peak():
    """The mode sits at the peak, apart from the mean and median of a skewed set."""
    from results.results_isotope import ratio_mode
    rng = np.random.default_rng(2)
    r = rng.lognormal(np.log(1.2), 0.4, 20000)
    mode = ratio_mode(r)
    assert mode == pytest.approx(1.2 * np.exp(-0.4 ** 2), rel=0.08)
    assert mode < np.median(r) < np.mean(r)
    assert ratio_mode(r, log=True) == pytest.approx(1.2, rel=0.05)
    two = np.r_[rng.normal(0.85, 0.01, 3000), rng.normal(0.95, 0.01, 1000)]
    assert ratio_mode(two) == pytest.approx(0.85, abs=0.01)
    assert ratio_mode([1.0, 2.0]) is None


def test_median_and_mode_lines_are_settings():
    """The node keeps median and mode lines off until switched on."""
    from results.results_isotope import IsotopicRatioPlotNode
    assert IsotopicRatioPlotNode.DEFAULT_CONFIG["show_median_line"] is False
    assert IsotopicRatioPlotNode.DEFAULT_CONFIG["show_mode_line"] is False
