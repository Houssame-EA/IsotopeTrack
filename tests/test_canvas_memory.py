"""A deleted canvas node gives its particle data back, and undo restores it with its data."""

from __future__ import annotations

import random

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QMainWindow

LABELS = ["56Fe", "48Ti", "27Al"]


def particles(n, name, seed):
    """Particles of one sample carrying a few elements."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        el = {lab: rng.lognormvariate(4, 1) for lab in LABELS if rng.random() < 0.7} or {"56Fe": 20.0}
        out.append({"elements": el, "element_mass_fg": {k: v / 50 for k, v in el.items()},
                    "start_time": i * 0.001, "source_sample": name})
    return out


@pytest.fixture
def canvas():
    """A canvas with a multi-sample selector over two loaded samples."""
    app = QApplication.instance() or QApplication([])
    from widget.canvas_widgets import CanvasResultsDialog, _NODE_FACTORIES
    owner = QMainWindow()
    owner.sample_particle_data = {"A": particles(300, "A", 1), "B": particles(300, "B", 2)}
    owner.selected_isotopes = {}
    dlg = CanvasResultsDialog(owner)
    sc = dlg.canvas.scene
    multi = _NODE_FACTORIES["multiple_sample_selector"](owner)
    multi.selected_samples = ["A", "B"]
    multi.selected_isotopes = [{"label": lab, "symbol": lab[2:], "mass": float(lab[:2]), "key": lab}
                               for lab in LABELS]
    sc.add_node(multi, QPointF(0, 0))
    app.processEvents()
    yield app, sc, multi, owner, _NODE_FACTORIES
    dlg.done(0)


def plot_on(sc, source, factories, owner, kind="histogram_plot", x=400):
    """Add a node of *kind* fed by *source*."""
    node = factories[kind](owner)
    sc.add_node(node, QPointF(x, 0))
    sc.add_link(source, "output", node, "input")
    return node


def test_deleted_node_lets_go_of_its_particles(canvas):
    """The undo history keeps the node, but no longer the data that reached it."""
    app, sc, multi, owner, factories = canvas
    plot = plot_on(sc, multi, factories, owner)
    app.processEvents()
    assert plot.input_data and plot.input_data.get("particle_data")
    sc.delete_node(sc.node_items[plot])
    app.processEvents()
    assert plot.input_data is None
    assert any(entry[0] == "delete_node" and entry[1]["wf_node"] is plot for entry in sc._undo_stack)


def test_undo_brings_the_node_back_with_its_data_and_links(canvas):
    """One undo restores the node, its link and the data flowing through it."""
    app, sc, multi, owner, factories = canvas
    plot = plot_on(sc, multi, factories, owner)
    app.processEvents()
    count = len(plot.input_data["particle_data"])
    sc.delete_node(sc.node_items[plot])
    sc.undo()
    app.processEvents()
    assert plot in sc.workflow_nodes and plot in sc.node_items
    assert any(lk.source_node is multi and lk.sink_node is plot for lk in sc.workflow_links)
    assert plot.input_data and len(plot.input_data["particle_data"]) == count


def test_undo_of_a_middle_node_feeds_what_it_fed_again(canvas):
    """A deleted node between a source and a plot comes back and passes the data on."""
    app, sc, multi, owner, factories = canvas
    temp = plot_on(sc, multi, factories, owner, kind="temp_pass_through", x=300)
    plot = plot_on(sc, temp, factories, owner, x=600)
    app.processEvents()
    count = len(plot.input_data["particle_data"])
    sc.delete_node(sc.node_items[temp])
    app.processEvents()
    assert not plot.input_data
    sc.undo()
    app.processEvents()
    assert plot.input_data and len(plot.input_data["particle_data"]) == count


def test_selector_fed_by_a_batch_drops_the_batch_when_deleted(canvas):
    """A selector's copy of the batch it was fed goes with it."""
    app, sc, multi, owner, factories = canvas
    from widget.canvas_widgets import EnhancedCanvasScene
    multi.batch_particle_data = [{"elements": {"56Fe": 1.0}}]
    multi.batch_samples = ["A"]
    EnhancedCanvasScene._release_node_data(multi)
    assert multi.batch_particle_data is None and multi.batch_samples is None
    assert multi.selected_samples == ["A", "B"]


def open_and_close(app, node, owner):
    """Open a node's figure window, let it draw, and close it as the user would."""
    dlg = node.configure(owner)
    for _ in range(20):
        app.processEvents()
    dlg.close()
    app.processEvents()
    return dlg


def flush(app):
    """Let pending timers fire and run pending deletions, as the event loop would."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtTest import QTest
    QTest.qWait(600)
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    app.processEvents()


@pytest.mark.parametrize("kind", ["histogram_plot", "box_plot"])
def test_deleted_nodes_do_not_pile_up_figure_windows(canvas, kind):
    """Open, close and delete a plot again and again: its windows are destroyed, not kept."""
    import gc
    import shiboken6
    app, sc, multi, owner, factories = canvas
    nodes = []
    for i in range(3):
        plot = plot_on(sc, multi, factories, owner, kind=kind, x=400 + 30 * i)
        app.processEvents()
        dlg = open_and_close(app, plot, owner)
        assert plot._figure_dialog is dlg and not dlg.isVisible()
        del dlg
        sc.delete_node(sc.node_items[plot])
        flush(app)
        nodes.append(plot)
    gc.collect()
    assert all(n._figure_dialog is None for n in nodes)
    windows = [o for o in gc.get_objects() if type(o).__name__.endswith("DisplayDialog")]
    assert not any(shiboken6.isValid(w) for w in windows)
    assert len(windows) <= 1


def test_closing_a_figure_window_keeps_it_for_reopening(canvas):
    """Closing (not deleting) a figure only hides it, so it reopens as left."""
    app, sc, multi, owner, factories = canvas
    plot = plot_on(sc, multi, factories, owner)
    app.processEvents()
    dlg = open_and_close(app, plot, owner)
    flush(app)
    assert plot._figure_dialog is dlg
    assert plot.configure(owner) is dlg


def test_undone_node_builds_a_new_figure_window(canvas):
    """After undo, opening the node draws a fresh window from the data sent to it again."""
    app, sc, multi, owner, factories = canvas
    plot = plot_on(sc, multi, factories, owner)
    app.processEvents()
    old = open_and_close(app, plot, owner)
    sc.delete_node(sc.node_items[plot])
    flush(app)
    sc.undo()
    app.processEvents()
    new = plot.configure(owner)
    app.processEvents()
    assert new is not None and new is not old and new.isVisible()
    new.close()


def test_plot_menus_without_a_parent_are_freed_with_the_window(canvas):
    """pyqtgraph's parentless "Plot Options" menus do not outlive the figure."""
    from PySide6.QtWidgets import QMenu
    app, sc, multi, owner, factories = canvas

    def option_menus():
        return [w for w in app.topLevelWidgets() if isinstance(w, QMenu) and w.title() == "Plot Options"]

    before = len(option_menus())
    plot = plot_on(sc, multi, factories, owner)
    app.processEvents()
    open_and_close(app, plot, owner)
    assert len(option_menus()) > before
    sc.delete_node(sc.node_items[plot])
    flush(app)
    assert len(option_menus()) == before


def test_thumbnail_refresh_is_disconnected_from_a_destroyed_window(canvas):
    """The node's signal no longer reaches a window that is gone."""
    app, sc, multi, owner, factories = canvas
    plot = plot_on(sc, multi, factories, owner)
    app.processEvents()
    dlg = open_and_close(app, plot, owner)
    node, _slot = dlg._thumb_refresh_slot
    assert node is plot
    import results.shared_plot_utils as spu
    sc.delete_node(sc.node_items[plot])
    flush(app)
    assert dlg._thumb_refresh_slot is None
    calls = []
    original = spu.capture_figure_thumbnail
    spu.capture_figure_thumbnail = lambda *a, **k: calls.append(a)
    try:
        plot.configuration_changed.emit()
        flush(app)
    finally:
        spu.capture_figure_thumbnail = original
    assert calls == []



def open_canvas_figure(app, sc, node):
    """Double-click a node on the canvas: opens one more figure from the hover fan."""
    sc.node_items[node].configure_node()
    for _ in range(20):
        app.processEvents()
    return node._figures[-1]


def test_deleting_a_figure_from_the_hover_fan_frees_its_window(canvas):
    """A figure removed from the fan is destroyed and no longer redraws or refreshes."""
    import shiboken6
    from results.shared_plot_utils import close_node_figure
    app, sc, multi, owner, factories = canvas
    plot = plot_on(sc, multi, factories, owner)
    app.processEvents()
    view = open_canvas_figure(app, sc, plot)
    dlg = view.dialog
    dlg.close()
    app.processEvents()
    assert shiboken6.isValid(dlg) and not dlg.isVisible()
    assert dlg._thumb_refresh_slot is not None
    close_node_figure(view)
    flush(app)
    assert not shiboken6.isValid(dlg)
    assert view not in plot._figures and view.dialog is None
    plot.configuration_changed.emit()
    flush(app)


def test_closing_a_canvas_figure_only_hides_it(canvas):
    """The window's close button keeps the figure in the fan for reopening."""
    import shiboken6
    app, sc, multi, owner, factories = canvas
    plot = plot_on(sc, multi, factories, owner)
    app.processEvents()
    view = open_canvas_figure(app, sc, plot)
    dlg = view.dialog
    dlg.close()
    flush(app)
    assert shiboken6.isValid(dlg) and not dlg.isVisible()
    assert view in plot._figures and view.dialog is dlg


def test_clearing_the_canvas_frees_nodes_and_their_windows(canvas):
    """Clear canvas (and project load) release every node's data, windows and undo history."""
    import shiboken6
    app, sc, multi, owner, factories = canvas
    plot = plot_on(sc, multi, factories, owner)
    app.processEvents()
    view = open_canvas_figure(app, sc, plot)
    dlg = view.dialog
    dlg.close()
    app.processEvents()
    assert plot.input_data and sc._undo_stack
    sc.clear_workflow()
    flush(app)
    assert not shiboken6.isValid(dlg)
    assert plot.input_data is None
    assert not sc._undo_stack and not sc.workflow_nodes and not sc.node_items
