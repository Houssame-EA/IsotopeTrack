"""Fixes found by opening every canvas figure in many settings.

Heatmap log scale and cell text, histogram settings in the chosen units,
readable log axes, pie labels that do not overlap, and crowded tick labels.
"""

import numpy as np
import pytest
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

import utils.unit as unit_mod
from utils.unit import ExportUnits


def test_heatmap_log_scale_reads_real_values():
    """The log colour scale spans the values themselves, and ignores empty cells."""
    from results.results_heatmap import _log_norm, _log_tick
    norm = _log_norm(np.array([[np.nan, 120.0], [800.0, 3000.0]]))
    assert norm.vmin == 120.0 and norm.vmax == 3000.0
    assert _log_norm(np.array([[np.nan, 0.0]])) is None
    assert _log_tick(200.0) == "200"
    assert _log_tick(0.05) == "0.05"
    assert _log_tick(2e5) == "$\\mathregular{2\\times10^{5}}$"
    assert _log_tick(1e5) == "$\\mathregular{10^{5}}$"
    assert _log_tick(3e-5) == "$\\mathregular{3\\times10^{-5}}$"


def test_heatmap_cell_numbers_fit_their_cells():
    """Long cell text with its range shrinks until every cell's text fits inside the cell."""
    from results.results_heatmap import _CellText, _CellTextGroup, _fmt_cell_number
    fig = Figure(figsize=(4, 3), dpi=100)
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot()
    ax.imshow(np.ones((3, 4)), aspect="auto")
    group = _CellTextGroup(ax, 18)
    for i in range(3):
        for j in range(4):
            group.add(ax.add_artist(_CellText(group, j, i, "416889\n(188853–519731)",
                                              ha="center", va="center")))
    canvas.draw()
    renderer = canvas.get_renderer()
    (x0, _), (x1, _) = ax.transData.transform([(0, 0), (1, 0)])
    assert all(t.get_window_extent(renderer).width <= abs(x1 - x0) for t in group.texts)
    assert len({t.get_fontsize() for t in group.texts}) == 1
    assert _fmt_cell_number(0.0042) == "0.0042"
    assert _fmt_cell_number(1500.4) == "1500"


def test_heatmap_cell_text_reads_on_its_colour():
    """Pale cells get black text and dark cells white, on a log scale too."""
    from matplotlib.colors import LogNorm
    from results.results_heatmap import _text_color_on
    fig = Figure()
    ax = fig.add_subplot()
    im = ax.imshow(np.array([[500.0, 30000.0]]), cmap="Greens", norm=LogNorm(500, 30000))
    assert _text_color_on(im, 600.0) == "black"
    assert _text_color_on(im, 30000.0) == "white"


def test_histogram_settings_follow_the_units():
    """A 20 fg bin width is 0.02 pg on a pg histogram; counts are left alone."""
    from results.results_bar_charts import shown_setting
    unit_mod.units.set(ExportUnits(mass_unit="pg"))
    cfg = {"data_type_display": "Element Mass (fg)", "bin_width": 20, "x_max": 1000}
    assert shown_setting(cfg, "bin_width", 20) == pytest.approx(0.02)
    assert shown_setting(cfg, "x_max", 1000) == pytest.approx(1.0)
    assert shown_setting({"data_type_display": "Counts", "bin_width": 20}, "bin_width", 20) == 20
    assert unit_mod.units.saved_for(0.02, "Element Mass (fg)") == pytest.approx(20.0)


def test_detection_limit_line_follows_the_units():
    """The histogram's detection limit line is drawn in the chosen unit."""
    import pyqtgraph as pg
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from results.shared_plot_utils import _add_det_limit_v
    unit_mod.units.set(ExportUnits(mass_unit="pg"))
    pi = pg.PlotItem()
    _add_det_limit_v(pi, {"show_det_limit": True, "det_limit_value": 500.0,
                          "data_type_display": "Element Mass (fg)"})
    lines = [i for i in pi.items if isinstance(i, pg.InfiniteLine)]
    assert lines and lines[0].value() == pytest.approx(0.5)


def test_log_axis_labels_are_thinned():
    """Between two powers of ten only 1, 2 and 5 keep a label."""
    from utils.pyqtgraph_patches import thin_log_labels
    values = np.log10([20, 30, 40, 50, 60, 70, 80, 90, 100])
    strings = [str(v) for v in range(9)]
    kept = [s for s in thin_log_labels(values, strings) if s]
    assert kept == ["0", "3", "8"]
    assert thin_log_labels(values[:3], strings[:3]) == strings[:3]


def test_log_axis_never_applies_an_si_factor():
    """A log axis over big values shows no (x1e+12) factor."""
    import pyqtgraph as pg
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from utils.pyqtgraph_patches import apply_pyqtgraph_patches
    apply_pyqtgraph_patches()
    axis = pg.AxisItem("bottom")
    axis.setLabel("Mass")
    axis.setLogMode(True)
    axis.setRange(10, 14)
    assert axis.autoSIPrefixScale == 1.0


def _pie_with_labels(sizes, texts):
    fig = Figure(figsize=(4, 4))
    FigureCanvasAgg(fig)
    ax = fig.add_subplot()
    wedges = ax.pie(sizes, startangle=90, counterclock=False)[0]
    anns = []
    for w, t in zip(wedges, texts):
        th = np.radians((w.theta1 + w.theta2) / 2)
        x, y = 1.15 * np.cos(th), 1.15 * np.sin(th)
        anns.append(ax.annotate(t, xy=(np.cos(th), np.sin(th)), xytext=(x, y),
                                ha="left" if x >= 0 else "right", va="center"))
    return fig, ax, anns


def test_pie_labels_do_not_overlap():
    """Small slices bunched together get labels that do not touch."""
    from results.shared_plot_utils import declutter_pie_labels
    fig, ax, anns = _pie_with_labels([60, 2, 2, 2, 2, 2, 30],
                                     [f"El{i}\n({i} P)\n{i}%" for i in range(7)])
    declutter_pie_labels(ax, anns)
    renderer = fig.canvas.get_renderer()
    boxes = [a.get_window_extent(renderer) for a in anns]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            assert not boxes[i].overlaps(boxes[j])


def test_crowded_tick_labels_are_shortened():
    """Lines too long for a category's width end in an ellipsis."""
    from results.results_box_plot import _fit_tick_labels
    labels = ["Mg\n(ASB-Chrysotile)"] * 18
    out = _fit_tick_labels(labels, 900, char_px=10)
    assert out[0].startswith("Mg\n(") and out[0].endswith("…")
    assert _fit_tick_labels(["Mg\n(A)"], 900) == ["Mg\n(A)"]
