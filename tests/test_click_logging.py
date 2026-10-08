"""Clicks in the Workflow Builder header and the Insights panel reach the user-action log."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton

from tools.logging_utils import logging_manager


class _Recorder:
    """Stand-in user-action logger that keeps every entry."""

    def __init__(self):
        self.entries = []

    def log_action(self, action_type, description, context=None):
        """Keep the entry."""
        self.entries.append((action_type, description, dict(context or {})))

    def descriptions(self):
        """The logged descriptions, in order."""
        return [d for _t, d, _c in self.entries]


@pytest.fixture
def recorder(monkeypatch):
    """Send user actions to a recorder instead of the log files."""
    rec = _Recorder()
    monkeypatch.setattr(logging_manager, "get_user_action_logger", lambda: rec)
    return rec


@pytest.fixture
def dialog():
    """A Workflow Builder window with no data."""
    from PySide6.QtTest import QTest
    QApplication.instance() or QApplication([])
    from widget.canvas_widgets import CanvasResultsDialog
    owner = QMainWindow()
    dlg = CanvasResultsDialog(owner)
    dlg.resize(1400, 800)
    dlg.show()
    QApplication.processEvents()
    yield dlg, QTest
    dlg.done(0)
    dlg.deleteLater()
    owner.deleteLater()


def _button(dlg, text):
    """The visible header button whose label contains *text*."""
    return next(b for b in dlg.findChildren(QPushButton) if text in b.text() and b.isVisible())


def test_header_buttons_are_logged(dialog, recorder):
    """Clear All, Insights and Close each leave an entry."""
    dlg, QTest = dialog
    QTest.mouseClick(_button(dlg, "Clear All"), Qt.LeftButton)
    QTest.mouseClick(dlg._insights_btn, Qt.LeftButton)
    QApplication.processEvents()
    assert dlg.insights_panel.isVisible()
    QTest.mouseClick(dlg._insights_btn, Qt.LeftButton)
    QTest.mouseClick(_button(dlg, "Close"), Qt.LeftButton)
    said = recorder.descriptions()
    assert said[:2] == ["Cleared canvas", "Opened Insights"]
    assert "Closed Insights" in said and said[-1] == "Closed Workflow Builder"


def test_insights_controls_are_logged(dialog, recorder):
    """Refresh, the plot-type menu and the element menu each leave an entry."""
    dlg, QTest = dialog
    panel = dlg.insights_panel
    QTest.mouseClick(dlg._insights_btn, Qt.LeftButton)
    QApplication.processEvents()
    panel._refresh_btn.setEnabled(True)
    QTest.mouseClick(panel._refresh_btn, Qt.LeftButton)
    panel._types_menu.actions()[-1].trigger()
    panel._all_action.trigger()
    panel._focus_menu.actions()[0].trigger()
    said = recorder.descriptions()
    assert "Insights: searched again from scratch" in said
    assert any(d.startswith("Insights: showing ") and d != "Insights: showing All plot types"
               for d in said)
    assert "Insights: showing All plot types" in said
    assert "Insights: searching all elements" in said


def test_card_buttons_are_logged(recorder):
    """Adding a finding's plot, figure or clustering node leaves an entry naming it."""
    QApplication.instance() or QApplication([])
    from results.insights.engine import Suggestion
    from results.insights.panel import _Card
    s = Suggestion(title="56Fe vs 55Mn", reasoning="r", category="types", confidence=0.9,
                   node_type="correlation_plot", elements=("56Fe", "55Mn"), samples=("a",),
                   explain_key="particle_type")
    got = []
    card = _Card(s, on_add=got.append, on_figure=got.append, on_cluster=got.append)
    card._add_btn.click()
    card._figure_btn.click()
    card._cluster_btn.click()
    said = recorder.descriptions()
    assert said == ["Insights: added plot for '56Fe vs 55Mn'",
                    "Insights: added figure for '56Fe vs 55Mn'",
                    "Insights: explored '56Fe vs 55Mn' in Clustering"]
    assert got == [s, s, s]
