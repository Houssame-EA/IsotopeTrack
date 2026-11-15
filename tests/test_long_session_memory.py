"""Memory that used to grow over a long session: plot redraws, the log buffer, sample data."""

from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMenu


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
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    app.processEvents()


def test_redrawing_a_plot_layout_does_not_keep_old_plots(app):
    """Each redraw frees the plots it replaced, with their menus."""
    import pyqtgraph as pg
    import shiboken6
    from results.shared_plot_utils import clear_plot_layout
    glw = pg.GraphicsLayoutWidget()
    replaced = []
    for _ in range(5):
        replaced += [i.ctrlMenu for i in glw.scene().items() if isinstance(i, pg.PlotItem)]
        clear_plot_layout(glw)
        glw.addPlot()
        glw.addPlot(row=1, col=0)
        flush(app)
    assert len(replaced) == 8
    assert not any(shiboken6.isValid(m) for m in replaced)
    items = [i for i in glw.scene().items() if isinstance(i, pg.PlotItem)]
    assert len(items) == 2 and all(i.ctrlMenu is not None for i in items)


def test_clearing_a_plot_layout_keeps_items_outside_it(app):
    """A crosshair added straight to the view is left alone."""
    import pyqtgraph as pg
    from results.shared_plot_utils import clear_plot_layout
    glw = pg.GraphicsLayoutWidget()
    glw.addPlot()
    line = pg.InfiniteLine()
    glw.scene().addItem(line)
    clear_plot_layout(glw)
    assert line.scene() is glw.scene()


def test_log_buffer_before_the_log_window_is_bounded():
    """Log records kept for the log window stop at what the window can show."""
    from tools import logging_utils as lu
    buffer = lu.EnhancedLoggingManager._pre_window_buffer
    handler = lu._BufferHandler(buffer)
    record = logging.LogRecord("t", logging.DEBUG, __file__, 1, "message", None, None)
    for _ in range(lu._MAX_GUI_ENTRIES + 100):
        handler.emit(record)
    assert len(buffer) == lu._MAX_GUI_ENTRIES
    buffer.clear()


@pytest.fixture
def mw(app, monkeypatch):
    """A main window whose confirmation boxes answer Yes and whose notices stay silent."""
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    from mainwindow import MainWindow
    w = MainWindow()
    w.unsaved_changes = False
    yield w
    w.unsaved_changes = False
    w.close()


def test_reset_lets_go_of_isobaric_backups_and_detections(mw):
    """Removing all samples, or loading a project, drops what belonged to the old samples."""
    mw._isobaric_raw_backup = {"S1": {"56Fe": [1.0] * 1000}}
    mw.multi_element_particles = [{"elements": {"56Fe": 1.0}}]
    mw.saturation_filtered_peaks = {"S1": {}}
    mw.detection_states = {"S1": {}}
    mw.reset_data_structures()
    assert mw._isobaric_raw_backup == {}
    assert mw.multi_element_particles == []
    assert mw.saturation_filtered_peaks == {}
    assert mw.detection_states == {}


def test_removing_a_sample_drops_its_isobaric_backup(mw):
    """A removed sample's raw-channel backup and settings go with it."""
    mw.sample_to_folder_map = {"S1": "/a", "S2": "/b"}
    mw._isobaric_raw_backup = {"S1": {"56Fe": [1.0]}, "S2": {"56Fe": [2.0]}}
    mw.sample_dilutions = {"S1": 10.0, "S2": 5.0}
    mw.remove_sample("S1")
    assert "S1" not in mw._isobaric_raw_backup and "S2" in mw._isobaric_raw_backup
    assert "S1" not in mw.sample_dilutions


def test_figure_builder_insert_menu_does_not_pile_up_submenus(app):
    """Refilling the expression insert menu replaces its submenus instead of adding more."""
    import sys
    sys.path.insert(0, "tests")
    from test_figure_builder import make_input
    from results.figure_builder import FigureBuilderNode
    from results.figure_builder.ui.editor import PanelEditor
    node = FigureBuilderNode()
    node.process_data(make_input(n=200))
    editor = PanelEditor()
    table = node.build_table()

    def submenus():
        return editor.insert_menu.findChildren(QMenu)

    editor.set_table(table)
    flush(app)
    first = len(submenus())
    assert first > 0
    for _ in range(5):
        editor.set_table(table)
        flush(app)
    assert len(submenus()) == first


def test_clearing_the_canvas_empties_the_insights_caches(app):
    """Insights stops holding the particles of a canvas that was cleared."""
    from results.insights import engine
    from widget.canvas_widgets import EnhancedCanvasScene
    batch = [{"elements": {"56Fe": 1.0}, "source_sample": "A"}]
    engine._split_batch(batch)
    engine._CTX_CACHE["old"] = object()
    EnhancedCanvasScene().clear_workflow()
    assert engine._BATCH_SPLITS == {} and engine._CTX_CACHE == {}
