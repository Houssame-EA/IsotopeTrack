"""Closed dialogs are freed, and theme changes no longer reach dialogs that are gone."""

from __future__ import annotations

import pytest
import shiboken6
from PySide6.QtCore import SIGNAL, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QMenu, QVBoxLayout


THEME_CHANGED = SIGNAL("themeChanged(QString)")


@pytest.fixture
def app():
    """The application, with any pending deletions run before and after the test."""
    application = QApplication.instance() or QApplication([])
    flush(application)
    yield application
    flush(application)


def flush(app):
    """Run pending deletions, as the event loop would once a handler returns."""
    from PySide6.QtTest import QTest
    QTest.qWait(50)
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    app.processEvents()


def plot_dialog(parent):
    """A dialog holding a pyqtgraph plot, like the mass spectrum popup."""
    import pyqtgraph as pg
    dlg = QDialog(parent)
    QVBoxLayout(dlg).addWidget(pg.PlotWidget())
    return dlg


def option_menus(app):
    """pyqtgraph's parentless "Plot Options" menus that are still alive."""
    return [w for w in app.topLevelWidgets() if isinstance(w, QMenu) and w.title() == "Plot Options"]


def test_release_window_frees_a_plot_dialog_and_its_menus(app):
    """A modal plot dialog released after exec() is destroyed with its plot menus."""
    from results.shared_plot_utils import release_window
    owner = QMainWindow()
    before = len(option_menus(app))
    dlg = plot_dialog(owner)
    assert len(option_menus(app)) > before
    release_window(dlg)
    flush(app)
    assert not shiboken6.isValid(dlg)
    assert len(option_menus(app)) == before
    assert owner.findChildren(QDialog) == []


def test_release_window_ignores_a_dialog_already_gone(app):
    """Releasing twice, or after Qt freed it, does nothing."""
    from results.shared_plot_utils import release_window
    owner = QMainWindow()
    dlg = QDialog(owner)
    release_window(dlg)
    flush(app)
    release_window(dlg)
    release_window(None)


def test_dialog_still_usable_until_the_handler_returns(app):
    """Values can be read from a released dialog for the rest of the handler."""
    from results.shared_plot_utils import release_window
    owner = QMainWindow()
    dlg = QDialog(owner)
    dlg.setWindowTitle("kept")
    release_window(dlg)
    app.processEvents()
    assert dlg.windowTitle() == "kept"


def test_delete_on_close_frees_a_window_when_closed(app):
    """A non-modal window is destroyed, plot menus included, once the user closes it."""
    from results.shared_plot_utils import delete_on_close
    owner = QMainWindow()
    before = len(option_menus(app))
    dlg = plot_dialog(owner)
    delete_on_close(dlg)
    dlg.show()
    app.processEvents()
    dlg.close()
    flush(app)
    assert not shiboken6.isValid(dlg)
    assert len(option_menus(app)) == before


def theme_receivers_left_by(app, make):
    """Theme connections a widget leaves behind once it is deleted."""
    from tools.theme import theme
    before = theme.receivers(THEME_CHANGED)
    widget = make()
    assert theme.receivers(THEME_CHANGED) > before
    widget.deleteLater()
    flush(app)
    return theme.receivers(THEME_CHANGED) - before


@pytest.mark.parametrize("kind", ["sample_selector", "multiple_sample_selector",
                                  "chip_selector", "periodic_table",
                                  "editor_dialog", "figure_builder_style"])
def test_theme_hooks_end_with_their_widget(app, kind):
    """A deleted widget no longer stays on the app-wide theme signal."""
    import widget.canvas_widgets as cw
    from results.figure_builder.ui import look
    from results.results_periodic import CompactPeriodicTableWidget, IsotopeChipSelector
    from widget.custom_plot_widget import _install_theme_subscription
    owner = QMainWindow()

    def styled(install):
        dlg = QDialog(owner)
        install(dlg)
        return dlg

    make = {
        "sample_selector": lambda: cw.SampleSelectorDialog(owner, ["A"], "A", [], False, {}),
        "multiple_sample_selector": lambda: cw.MultipleSampleSelectorDialog(owner, ["A"], ["A"], [], {}),
        "chip_selector": lambda: IsotopeChipSelector(owner),
        "periodic_table": lambda: CompactPeriodicTableWidget(owner),
        "editor_dialog": lambda: styled(_install_theme_subscription),
        "figure_builder_style": lambda: styled(look.style),
    }[kind]
    assert theme_receivers_left_by(app, make) == 0


def test_theme_switch_after_dialogs_are_gone(app):
    """Switching theme once those dialogs are freed raises nothing."""
    import widget.canvas_widgets as cw
    from tools.theme import theme
    owner = QMainWindow()
    dlg = cw.SampleSelectorDialog(owner, ["A"], "A", [], False, {})
    dlg.deleteLater()
    flush(app)
    theme.themeChanged.emit("dark" if theme.is_dark else "light")
