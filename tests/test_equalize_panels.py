"""Side-by-side and grid panels get the same data area."""

from __future__ import annotations

import time

import numpy as np
import pytest


@pytest.fixture(scope="module")
def app():
    """The running QApplication, created if needed."""
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def settle(app):
    """Let the layout and the deferred pass run."""
    for _ in range(5):
        app.processEvents()
        time.sleep(0.02)


def grid(app, shape, sizes):
    """A layout of plots, the first of each row showing Y tick values and the others not."""
    import pyqtgraph as pg
    w = pg.GraphicsLayoutWidget()
    w.resize(1200, 600)
    w.show()
    rows, cols = shape
    plots = []
    for k, n in enumerate(sizes):
        r, c = divmod(k, cols)
        pi = w.addPlot(row=r, col=c)
        rng = np.random.default_rng(k)
        pi.plot(rng.lognormal(0, 1, n) * 10 ** k, rng.normal(0, 1, n) * 10 ** (3 * k), pen=None,
                symbol="o")
        pi.setTitle(f"Sample {k}")
        if c:
            pi.getAxis("left").setStyle(showValues=False)
        plots.append(pi)
    settle(app)
    return w, plots


def widths(plots):
    """Data-area width of each plot, in pixels."""
    return [round(p.getViewBox().sceneBoundingRect().width()) for p in plots]


def test_side_by_side_panels_get_equal_data_areas(app):
    """Two panels in a row, one with Y tick values and one without, end up the same width."""
    from results.shared_plot_utils import equalize_panels
    w, plots = grid(app, (1, 2), [50, 4000])
    equalize_panels(w)
    settle(app)
    a, b = widths(plots)
    assert abs(a - b) <= 1
    w.resize(900, 600)
    settle(app)
    a, b = widths(plots)
    assert abs(a - b) <= 1


def test_grid_panels_get_equal_widths_and_heights(app):
    """A 2 × 3 grid: every panel the same width and the same height."""
    from results.shared_plot_utils import equalize_panels
    w, plots = grid(app, (2, 3), [40, 900, 3000, 200, 10, 600])
    equalize_panels(w)
    settle(app)
    assert max(widths(plots)) - min(widths(plots)) <= 1
    heights = [round(p.getViewBox().sceneBoundingRect().height()) for p in plots]
    assert max(heights) - min(heights) <= 1


def test_single_plot_is_left_alone(app):
    """One panel: nothing to equalise and nothing changed."""
    import pyqtgraph as pg
    from results.shared_plot_utils import equalize_panels
    w = pg.GraphicsLayoutWidget()
    pi = w.addPlot()
    before = pi.preferredWidth()
    equalize_panels(w)
    assert pi.preferredWidth() == before


def test_linked_panels_share_a_range_covering_all_of_them(app):
    """Y-linked panels: with fit_y every panel's points are inside the shared range."""
    import pyqtgraph as pg
    from results.shared_plot_utils import equalize_panels
    w = pg.GraphicsLayoutWidget()
    w.resize(1000, 500)
    w.show()
    a = w.addPlot(row=0, col=0)
    b = w.addPlot(row=0, col=1)
    a.plot([1, 2, 3], [0.2, 5.0, 9.0], pen=None, symbol="o")
    b.plot([1, 2, 3], [0.1, 0.3, 0.5], pen=None, symbol="o")
    b.setYLink(a)
    settle(app)
    equalize_panels(w, fit_y=True)
    settle(app)
    lo, hi = a.getViewBox().viewRange()[1]
    assert lo <= 0.1 and hi >= 9.0
    assert b.getViewBox().viewRange()[1] == pytest.approx([lo, hi])


def test_typed_range_is_kept_without_fit_y(app):
    """Without fit_y a range the user typed stays as it is."""
    import pyqtgraph as pg
    from results.shared_plot_utils import equalize_panels
    w = pg.GraphicsLayoutWidget()
    w.show()
    a = w.addPlot(row=0, col=0)
    b = w.addPlot(row=0, col=1)
    a.plot([1, 2], [0, 100], pen=None, symbol="o")
    b.plot([1, 2], [0, 1], pen=None, symbol="o")
    b.setYLink(a)
    a.setYRange(10, 20, padding=0)
    settle(app)
    equalize_panels(w, fit_y=False)
    settle(app)
    assert a.getViewBox().viewRange()[1] == pytest.approx([10, 20])
