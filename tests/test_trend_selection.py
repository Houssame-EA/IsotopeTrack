"""Trend lines fitted to points the user draws a loop around."""

from __future__ import annotations

import numpy as np
import pytest

from results import trend_selection as ts


@pytest.fixture
def app():
    """A QApplication for the widget tests."""
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _clouds(seed=4):
    """Fe and Mn masses on two ratios, 2 (600 particles) and 0.2 (400)."""
    rng = np.random.default_rng(seed)
    parts = []
    for ratio, n in [(2.0, 600), (0.2, 400)]:
        for _ in range(n):
            fe = rng.lognormal(3, 1)
            parts.append({"elements": {"56Fe": fe, "55Mn": fe * ratio * rng.lognormal(0, 0.15)},
                          "source_sample": "S"})
    return parts


UPPER_LOOP = [(-0.5, -0.55), (3.0, 2.95), (3.0, 3.65), (-0.5, 0.15)]
"""A loop around the ratio-2 cloud on log–log axes (y within x − 0.05 to x + 0.65)."""

LOWER_LOOP = [(-0.5, -1.55), (3.0, 1.95), (3.0, 2.65), (-0.5, -0.85)]
"""A loop around the ratio-0.2 cloud on log–log axes."""


def test_inside_and_fit():
    """Points inside a loop are found and fitted on their own."""
    x = np.array([0.0, 1.0, 2.0, 1.0, 5.0])
    y = np.array([0.1, 1.1, 2.1, 3.0, 5.0])
    sel = {"polygon": [[-1, -1], [3, 1.5], [3, 3], [-1, 0.6]]}
    mask, line = ts.fit_selection(sel, x, y)
    assert mask.tolist() == [True, True, True, False, False]
    assert line.slope == pytest.approx(1.0) and line.intercept == pytest.approx(0.1)
    assert line.n == 3 and line.r == pytest.approx(1.0)


def test_too_few_points_give_no_line():
    """A loop around fewer than three points draws no line."""
    mask, line = ts.fit_selection({"polygon": [[-1, -1], [0.5, -1], [0.5, 0.5]]},
                                  [0.0, 1.0, 2.0], [0.0, 1.0, 2.0])
    assert mask.sum() == 1 and line is None


def test_loops_only_apply_to_the_axes_they_were_drawn_on():
    """Changing an axis quantity or its log scaling hides a loop; going back shows it."""
    cfg = {"x_element": "56Fe", "y_element": "55Mn", "log_x": True, "log_y": True}
    cfg["trend_selections"] = [ts.new_selection(UPPER_LOOP, "", cfg)]
    assert len(ts.active_selections(cfg)) == 1
    assert ts.active_selections(dict(cfg, y_element="48Ti")) == []
    assert ts.active_selections(dict(cfg, log_y=False)) == []
    assert ts.active_selections(cfg, "other sample") == []


def test_legend_text_gives_ratio_or_slope():
    """On log–log axes a slope near one reads as a ratio; otherwise the slope is shown."""
    from results.multi_trend import TrendLine
    line = TrendLine(slope=1.02, intercept=np.log10(2), sigma=0.1, n=1234, r=0.981)
    assert ts.legend_text(1, line, True, True) == "selection 1: r = 0.981, ratio 2 (n = 1,234)"
    assert "slope 1.02" in ts.legend_text(2, line, False, False)


def _legend(dlg):
    """Legend texts of every panel in a correlation window."""
    import pyqtgraph as pg
    plots = [pi for pi in dlg.plot_widget.ci.items if isinstance(pi, pg.PlotItem)]
    return [label.text for pi in plots if pi.legend is not None for _s, label in pi.legend.items]


def _draw_loop(dlg, loop):
    """Drag the mouse around *loop* (plot coordinates) on the window's only panel."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    pi = dlg._primary_plot_item
    vb = pi.getViewBox()
    port = dlg.plot_widget.viewport()

    def at(x, y):
        """Widget position of a plot coordinate."""
        return dlg.plot_widget.mapFromScene(vb.mapViewToScene(QPointF(x, y)))

    path = []
    for (x0, y0), (x1, y1) in zip(loop, loop[1:] + loop[:1]):
        path += [(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t) for t in np.linspace(0, 1, 8)[:-1]]
    QTest.mousePress(port, Qt.LeftButton, Qt.NoModifier, at(*path[0]))
    for p in path[1:]:
        QTest.mouseMove(port, at(*p))
    QTest.mouseRelease(port, Qt.LeftButton, Qt.NoModifier, at(*path[-1]))


def test_correlation_window_fits_selected_points(app):
    """Two loops drawn on the plot give two lines with their own ratios; both can be removed."""
    from PySide6.QtWidgets import QApplication
    from results.results_correlation import CorrelationPlotDisplayDialog, CorrelationPlotNode
    node = CorrelationPlotNode()
    node.input_data = {"type": "sample_data", "sample_name": "S", "particle_data": _clouds(),
                       "selected_isotopes": [{"label": "56Fe"}, {"label": "55Mn"}]}
    node.config.update({"x_element": "56Fe", "y_element": "55Mn", "log_x": True, "log_y": True,
                        "auto_x": False, "x_min": -1, "x_max": 3.5,
                        "auto_y": False, "y_min": -2, "y_max": 4})
    dlg = CorrelationPlotDisplayDialog(node)
    dlg.resize(1000, 700)
    dlg.show()
    QApplication.processEvents()
    assert _legend(dlg) == []

    dlg.start_point_selection()
    _draw_loop(dlg, UPPER_LOOP)
    QApplication.processEvents()
    names = _legend(dlg)
    assert len(names) == 1 and names[0].startswith("selection 1:")
    assert float(names[0].split("ratio ")[1].split(" ")[0]) == pytest.approx(2.0, rel=0.05)
    assert "(n = 600)" in names[0]

    _draw_loop(dlg, LOWER_LOOP)
    QApplication.processEvents()
    names = _legend(dlg)
    assert len(names) == 2 and names[1].startswith("selection 2:")
    assert float(names[1].split("ratio ")[1].split(" ")[0]) == pytest.approx(0.2, rel=0.05)
    assert len(node.config["trend_selections"]) == 2

    dlg.stop_point_selection()
    assert not dlg._selecting and not dlg._select_hint.isVisible()

    node.config["y_element"] = "56Fe"
    dlg._refresh()
    assert _legend(dlg) == []
    node.config["y_element"] = "55Mn"
    dlg._refresh()
    assert len(_legend(dlg)) == 2

    dlg.remove_last_selection()
    assert [n.split(":")[0] for n in _legend(dlg)] == ["selection 1"]
    dlg.remove_all_selections()
    assert _legend(dlg) == [] and node.config["trend_selections"] == []
    dlg.close()


def test_drag_pans_again_after_selection_ends(app):
    """Outside selection mode the mouse is left to the plot, so nothing is stored."""
    from PySide6.QtWidgets import QApplication
    from results.results_correlation import CorrelationPlotDisplayDialog, CorrelationPlotNode
    node = CorrelationPlotNode()
    node.input_data = {"type": "sample_data", "sample_name": "S", "particle_data": _clouds(),
                       "selected_isotopes": [{"label": "56Fe"}, {"label": "55Mn"}]}
    node.config.update({"x_element": "56Fe", "y_element": "55Mn", "log_x": True, "log_y": True})
    dlg = CorrelationPlotDisplayDialog(node)
    dlg.resize(1000, 700)
    dlg.show()
    QApplication.processEvents()
    _draw_loop(dlg, UPPER_LOOP)
    assert not node.config.get("trend_selections")
    dlg.close()
