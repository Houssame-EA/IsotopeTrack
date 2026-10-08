"""Tests for fitting one, two or three trend lines in correlation plots."""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from results.multi_trend import describe, fit_trends


@pytest.fixture(scope="module")
def app():
    """A Qt application for the plot tests."""
    return QApplication.instance() or QApplication([])


def ratios(spec, seed=1, noise=0.08):
    """Log Fe and log Mn for populations of fixed Mn/Fe ratio: ``[(n, ratio), ...]``."""
    rng = np.random.default_rng(seed)
    xs, ys = [], []
    for n, ratio in spec:
        x = rng.lognormal(1, 1, n)
        xs.append(np.log10(x))
        ys.append(np.log10(x * ratio * rng.lognormal(0, noise, n)))
    return np.concatenate(xs), np.concatenate(ys)


@pytest.mark.parametrize("spec", [
    [(1000, 2.0)],
    [(700, 2.0), (300, 0.2)],
    [(500, 5.0), (300, 0.5), (200, 0.05)],
])
def test_the_right_number_of_lines_is_found(spec):
    """One, two and three ratio populations give one, two and three lines with their ratios."""
    fit = fit_trends(*ratios(spec))
    assert len(fit.lines) == len(spec) and fit.chosen_by == "data"
    expected = sorted((r for _n, r in spec), reverse=True)
    for line, ratio, (n, _r) in zip(fit.lines, expected, sorted(spec, key=lambda s: -s[1])):
        assert line.slope == pytest.approx(1.0, abs=0.03)
        assert 10 ** line.intercept == pytest.approx(ratio, rel=0.05)
        assert line.n == pytest.approx(n, abs=0.03 * n)
        assert line.r > 0.95


def test_no_extra_lines_for_one_cloud_or_noise():
    """Ratios too close to separate, and unrelated values, stay a single line."""
    assert len(fit_trends(*ratios([(500, 2.0), (500, 2.4)], noise=0.2)).lines) == 1
    rng = np.random.default_rng(3)
    assert len(fit_trends(rng.normal(size=800), rng.normal(size=800)).lines) == 1


def test_fixed_count_and_linear_axes():
    """A fixed count is honoured; on linear axes lines through the origin are separated."""
    assert len(fit_trends(*ratios([(700, 2.0), (300, 0.2)]), lines=3).lines) == 3
    rng = np.random.default_rng(5)
    x = rng.uniform(0, 10, 800)
    y = np.where(np.arange(800) % 2 == 0, 2 * x, 0.5 * x) + rng.normal(0, 0.3, 800)
    fit = fit_trends(x, y)
    assert [round(line.slope, 1) for line in fit.lines] == [2.0, 0.5]


def test_too_few_points_and_non_finite_values():
    """Fewer than ten finite points give no fit; NaNs are skipped and labelled -1."""
    assert fit_trends([1, 2, 3], [1, 2, 3]) is None
    x, y = ratios([(300, 2.0)])
    x[:5] = np.nan
    fit = fit_trends(x, y)
    assert (fit.labels[:5] == -1).all() and (fit.labels[5:] == 0).all()


def test_description_names_ratios_on_log_axes():
    """Slope-one lines on log-log axes read as ratios; others as power laws or equations."""
    fit = fit_trends(*ratios([(700, 2.0), (300, 0.2)]))
    assert describe(fit.lines[0], True, True, "Fe", "Mn").startswith("Mn/Fe ≈ 2")
    assert describe(fit.lines[0], False, False).startswith("y = ")


def _builder_table():
    """Three Mn/Fe populations as a Figure Builder table, over two samples."""
    from results.figure_builder.core.expressions import ParticleTable
    rng = np.random.default_rng(4)
    parts = []
    for ratio, n, sample in [(2.0, 600, "A"), (0.2, 400, "B"), (0.03, 200, "A")]:
        for _ in range(n):
            fe = rng.lognormal(1, 1)
            parts.append({"elements": {"56Fe": fe * 50, "55Mn": fe * ratio * rng.lognormal(0, 0.15) * 50},
                          "source_sample": sample})
    return ParticleTable.from_input({"type": "multiple_sample_data", "sample_names": ["A", "B"],
                                     "particle_data": parts}, "Counts")


def _render(table, **panel):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from results.figure_builder.core.engine import render
    from results.figure_builder.core.spec import default_spec, make_panel, normalise_spec
    spec = default_spec()
    spec["panels"] = [make_panel(kind="scatter", x="Fe", y="Mn", log_x=True, log_y=True,
                                 show_fit=True, rect=[0, 0, 1, 1], **panel)]
    fig = Figure()
    FigureCanvasAgg(fig)
    report = render(fig, normalise_spec(spec), table)
    assert not report.errors
    return report


def test_builder_scatter_draws_each_line(app):
    """The scatter reports three lines overall and splits them per sample."""
    table = _builder_table()
    stats = _render(table, fit_lines="auto", fit_color_points=True, show_r=True).stats
    assert stats[0].startswith("All particles: 3 lines chosen from the data")
    assert sum(1 for s in stats if s.strip().startswith("line ")) == 3
    stats = _render(table, fit_lines="auto", group_by="sample").stats
    assert any(s.startswith("A: 2 lines") for s in stats)
    assert any(s.startswith("B: 1 line") for s in stats)
    stats = _render(table, fit_lines="1").stats
    assert stats[0].startswith("All particles: slope =")


def test_canvas_correlation_plot_draws_each_line(app):
    """The correlation plot draws one line per trend, named with its r and ratio."""
    import pyqtgraph as pg
    from results.results_correlation import CorrelationPlotDisplayDialog, CorrelationPlotNode
    rng = np.random.default_rng(4)
    parts = []
    for ratio, n in [(2.0, 600), (0.2, 400)]:
        for _ in range(n):
            fe = rng.lognormal(3, 1)
            parts.append({"elements": {"56Fe": fe, "55Mn": fe * ratio * rng.lognormal(0, 0.15)},
                          "source_sample": "S"})
    node = CorrelationPlotNode()
    node.input_data = {"type": "sample_data", "sample_name": "S", "particle_data": parts,
                       "selected_isotopes": [{"label": "56Fe"}, {"label": "55Mn"}]}
    node.config.update({"x_element": "56Fe", "y_element": "55Mn", "log_x": True, "log_y": True,
                        "trend_lines": "auto"})
    dlg = CorrelationPlotDisplayDialog(node)
    plots = [pi for pi in dlg.plot_widget.ci.items if isinstance(pi, pg.PlotItem)]
    names = [label.text for pi in plots if pi.legend is not None for _s, label in pi.legend.items]
    assert len(names) == 2
    found = [float(n.split("ratio ")[1].split(" ")[0]) for n in names]
    assert found == pytest.approx([2.0, 0.2], rel=0.05)
    node.config["trend_lines"] = "1"
    dlg._refresh()
    plots = [pi for pi in dlg.plot_widget.ci.items if isinstance(pi, pg.PlotItem)]
    assert all(pi.legend is None or not pi.legend.items for pi in plots)
    dlg.close()
