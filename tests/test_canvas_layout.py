# -*- coding: utf-8 -*-
"""Tests for the automatic canvas layout: Arrange, its undo, and where Insights puts new branches."""
import itertools

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QMainWindow

from widget import canvas_layout as L

W, H = 130.0, 105.0


def _boxes(pos, size):
    """``(left, top, right, bottom)`` of each placed node."""
    return {n: (x, y, x + size[n][0], y + size[n][1]) for n, (x, y) in pos.items()}


def _clear(a, b):
    """Whether two boxes do not overlap."""
    return a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]


def _fan(n_branches):
    """A batch node with *n_branches* selector-to-plot branches and one unconnected node."""
    nodes = ['batch', 'lone']
    edges = []
    for i in range(n_branches):
        nodes += [f's{i}', f'p{i}']
        edges += [('batch', f's{i}'), (f's{i}', f'p{i}')]
    return nodes, edges, {n: (W, H) for n in nodes}


def test_arrange_puts_nodes_in_columns_by_data_flow():
    """Every node sits one column right of its parent, with nothing overlapping."""
    nodes, edges, size = _fan(5)
    pos = L.arrange(nodes, edges, size, {n: (i * 13.0, i * 7.0) for i, n in enumerate(nodes)})
    for a, b in edges:
        assert pos[b][0] > pos[a][0] + W
    assert len({pos[f's{i}'][0] for i in range(5)}) == 1
    boxes = _boxes(pos, size)
    for a, b in itertools.combinations(nodes, 2):
        assert _clear(boxes[a], boxes[b]), (a, b)


def test_arrange_centres_a_parent_on_its_branches():
    """The batch node sits level with the middle of its branches; a branch's plot is level with its selector."""
    nodes, edges, size = _fan(5)
    pos = L.arrange(nodes, edges, size)
    tops = [pos[f's{i}'][1] for i in range(5)]
    middle = (min(tops) + max(tops) + H) / 2
    assert pos['batch'][1] + H / 2 == pytest.approx(middle)
    for i in range(5):
        assert pos[f'p{i}'][1] == pytest.approx(pos[f's{i}'][1])


def test_arrange_keeps_the_users_order_and_stacks_loose_groups():
    """Branches keep their top-to-bottom order and an unconnected node goes below the graph."""
    nodes, edges, size = _fan(3)
    current = {n: (0.0, 0.0) for n in nodes}
    current.update({'s0': (200.0, 300.0), 's1': (200.0, 0.0), 's2': (200.0, 150.0), 'lone': (0.0, 900.0)})
    pos = L.arrange(nodes, edges, size, current, aspect=None)
    assert pos['s1'][1] < pos['s2'][1] < pos['s0'][1]
    assert pos['lone'][1] > max(y for n, (x, y) in pos.items() if n != 'lone') + H
    packed = L.arrange(nodes, edges, size, current)
    assert packed['s1'][1] < packed['s2'][1] < packed['s0'][1]
    boxes = _boxes(packed, size)
    assert all(_clear(boxes['lone'], boxes[n]) for n in nodes if n != 'lone')


def test_arrange_survives_a_cycle_and_an_empty_canvas():
    """A stray loop does not stop the layout; no nodes gives no positions."""
    pos = L.arrange(['a', 'b', 'c'], [('a', 'b'), ('b', 'c'), ('c', 'a')], {n: (W, H) for n in 'abc'})
    assert set(pos) == {'a', 'b', 'c'}
    assert L.arrange([], [], {}) == {}


def test_branch_slot_stacks_branches_under_each_other():
    """Each new branch goes one row lower in the column next to its source, without overlaps."""
    source = (0.0, 0.0, W, H)
    boxes = [source]
    rows = []
    for _ in range(6):
        slots = L.branch_slot(source, [W, W], H, boxes, max_height=float('inf'))
        assert slots[0][0] == pytest.approx(W + L.COLUMN_GAP)
        assert slots[1][0] == pytest.approx(2 * W + 2 * L.COLUMN_GAP)
        for x, y in slots:
            box = (x, y, x + W, y + H)
            assert all(_clear(box, b) for b in boxes)
            boxes.append(box)
        rows.append(slots[0][1])
    assert rows == sorted(rows) and len(set(rows)) == 6


def test_branch_slot_starts_a_new_column_when_limited():
    """With a height limit, a full column moves the next branch further right."""
    source = (0.0, 0.0, W, H)
    boxes = [source]
    xs = set()
    for _ in range(4):
        slots = L.branch_slot(source, [W, W], H, boxes, max_height=2 * (H + L.ROW_GAP))
        xs.add(slots[0][0])
        boxes += [(x, y, x + W, y + H) for x, y in slots]
    assert len(xs) == 2


@pytest.fixture
def canvas():
    """A real Workflow Builder canvas with a batch node and three messy branches."""
    app = QApplication.instance() or QApplication([])
    from widget.canvas_widgets import CanvasResultsDialog, _NODE_FACTORIES
    owner = QMainWindow()
    dlg = CanvasResultsDialog(owner)
    sc = dlg.canvas.scene
    batch = _NODE_FACTORIES['batch_sample_selector'](owner)
    sc.add_node(batch, QPointF(40, 200))
    branches = []
    for i, kind in enumerate(['histogram_plot', 'box_plot', 'molar_ratio_plot']):
        sel = _NODE_FACTORIES['sample_selector'](owner)
        plot = _NODE_FACTORIES[kind](owner)
        sc.add_node(sel, QPointF(300 + 290 * i, 200))
        sc.add_node(plot, QPointF(450 + 290 * i, 200 + 37 * i))
        sc.add_link(batch, 'output', sel, 'input')
        sc.add_link(sel, 'output', plot, 'input')
        branches.append((sel, plot))
    app.processEvents()
    yield dlg, sc, batch, branches, owner
    dlg.done(0)
    dlg.deleteLater()
    owner.deleteLater()


def _where(sc):
    """Position of every node item."""
    return {wn: (it.pos().x(), it.pos().y()) for wn, it in sc.node_items.items()}


def test_arrange_button_tidies_and_ctrl_z_puts_it_back(canvas):
    """Arrange moves the nodes into columns, records one undo step, and undo restores every position."""
    dlg, sc, batch, branches, _ = canvas
    before = _where(sc)
    assert sc.arrange_nodes(animate=False) > 0
    after = _where(sc)
    sels = [after[s] for s, _ in branches]
    assert len({x for x, _ in sels}) == 1
    assert all(after[p][1] == pytest.approx(after[s][1]) for s, p in branches)
    assert sc._undo_stack[-1][0] == 'move_nodes'
    assert sc.arrange_nodes(animate=False) == 0
    sc.undo()
    sc._arrange_anim.setCurrentTime(sc._arrange_anim.duration())
    restored = _where(sc)
    assert all(restored[wn] == pytest.approx(before[wn]) for wn in before)
    assert dlg._arrange_btn.toolTip().startswith('Tidy the canvas')


def test_insights_branch_goes_under_the_last_one(canvas):
    """A branch added the Insights way lands in the selector column, below the existing branches."""
    import results.insights.panel as ip
    from widget.canvas_widgets import _NODE_FACTORIES
    dlg, sc, batch, branches, owner = canvas
    sc.arrange_nodes(animate=False)
    sel = _NODE_FACTORIES['sample_selector'](owner)
    plot = _NODE_FACTORIES['histogram_plot'](owner)
    sc.add_node(sel, QPointF(-1900, -1900))
    sc.add_node(plot, QPointF(-1900, -1900))
    sc.add_link(batch, 'output', sel, 'input')
    sc.add_link(sel, 'output', plot, 'input')
    ip._place_branch(sc, [sel, plot], batch)
    now = _where(sc)
    column = now[branches[0][0]][0]
    assert now[sel][0] == pytest.approx(column)
    assert now[sel][1] > max(now[s][1] for s, _ in branches)
    assert now[plot][1] == pytest.approx(now[sel][1]) and now[plot][0] > now[sel][0]
    assert sc.node_items[sel].isSelected() and sc.node_items[plot].isSelected()
    boxes = {wn: sc.node_box(it) for wn, it in sc.node_items.items()}
    for a, b in itertools.combinations(boxes, 2):
        assert _clear(boxes[a], boxes[b])


def test_far_away_nodes_stay_reachable(canvas):
    """A node placed beyond the old 2000-unit edge grows the scrollable area to include it."""
    from widget.canvas_widgets import _NODE_FACTORIES
    dlg, sc, batch, branches, owner = canvas
    far = _NODE_FACTORIES['histogram_plot'](owner)
    sc.add_node(far, QPointF(400, 5200))
    note_x = 6100.0
    sc.node_items[branches[0][1]].setPos(QPointF(note_x, 300))
    sc.fit_scene_rect()
    rect = sc.sceneRect()
    for box in (sc.node_box(sc.node_items[far]), sc.node_box(sc.node_items[branches[0][1]])):
        assert rect.left() <= box[0] and rect.right() >= box[2]
        assert rect.top() <= box[1] and rect.bottom() >= box[3]
    sc.delete_node(sc.node_items[far])
    sc.node_items[branches[0][1]].setPos(QPointF(450, 200))
    sc.fit_scene_rect()
    shrunk = sc.sceneRect()
    assert shrunk.bottom() == pytest.approx(sc.BASE_RECT.bottom())
    assert shrunk.right() < note_x


def _wheel(view, dy, pixel=False, mods=None):
    """Send one wheel event: a trackpad swipe when *pixel*, else a mouse-wheel notch."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QWheelEvent
    pos = QPointF(view.viewport().width() / 2, view.viewport().height() / 2)
    ev = QWheelEvent(pos, view.viewport().mapToGlobal(pos.toPoint()),
                     QPoint(0, dy) if pixel else QPoint(0, 0), QPoint(0, dy),
                     Qt.NoButton, mods or Qt.NoModifier,
                     Qt.ScrollUpdate if pixel else Qt.NoScrollPhase, False)
    view.wheelEvent(ev)


def test_trackpad_swipe_moves_and_wheel_or_cmd_scroll_zooms(canvas):
    """A swipe scrolls the canvas without zooming; a mouse wheel and Cmd/Ctrl + swipe zoom."""
    from PySide6.QtCore import Qt
    dlg, sc, batch, branches, owner = canvas
    view = dlg.canvas
    dlg.resize(900, 600)
    dlg.show()
    QApplication.processEvents()
    sc.setSceneRect(-4000, -4000, 8000, 8000)
    sc.BASE_RECT = sc.sceneRect()
    zoom = view._zoom
    before = view.verticalScrollBar().value()
    _wheel(view, -120, pixel=True)
    assert view._zoom == zoom
    assert view.verticalScrollBar().value() != before
    _wheel(view, 120)
    assert view._zoom > zoom
    zoom = view._zoom
    _wheel(view, -120, pixel=True, mods=Qt.ControlModifier)
    assert view._zoom < zoom


def test_zoom_is_clamped_and_never_stuck(canvas):
    """Zoom stays within its limits, and from the smallest zoom it can always zoom back in."""
    dlg, sc, batch, branches, owner = canvas
    view = dlg.canvas
    view.set_zoom(0.01)
    assert view._zoom == pytest.approx(view.MIN_ZOOM)
    _wheel(view, 120)
    assert view._zoom > view.MIN_ZOOM
    view.set_zoom(50)
    assert view._zoom == pytest.approx(view.MAX_ZOOM)


def _groups(n, size_per=4):
    """*n* unconnected groups, each four samples feeding a filter that feeds two plots."""
    nodes, edges = [], []
    for g in range(n):
        f = f'f{g}'
        nodes.append(f)
        for i in range(size_per):
            nodes.append(f'g{g}s{i}')
            edges.append((f'g{g}s{i}', f))
        for p in ('heat', 'clus'):
            nodes.append(f'g{g}{p}')
            edges.append((f, f'g{g}{p}'))
    return nodes, edges, {n: (W, H) for n in nodes}


def test_many_groups_are_packed_into_columns_shaped_like_the_view():
    """Twelve groups fill several columns, not one tall line, and nothing overlaps."""
    nodes, edges, size = _groups(12)
    pos = L.arrange(nodes, edges, size, aspect=1.6)
    boxes = _boxes(pos, size)
    width = max(b[2] for b in boxes.values()) - min(b[0] for b in boxes.values())
    height = max(b[3] for b in boxes.values()) - min(b[1] for b in boxes.values())
    filters = {pos[f'f{g}'][0] for g in range(12)}
    assert len(filters) >= 3
    assert 0.8 < width / height < 3.2
    for a, b in itertools.combinations(nodes, 2):
        assert _clear(boxes[a], boxes[b]), (a, b)
    tall = L.arrange(nodes, edges, size, aspect=None)
    assert len({tall[f'f{g}'][0] for g in range(12)}) == 1


def test_arrange_twice_changes_nothing():
    """A packed layout is stable: arranging it again moves no node."""
    nodes, edges, size = _groups(9)
    first = L.arrange(nodes, edges, size, aspect=1.6)
    second = L.arrange(nodes, edges, size, current=first, aspect=1.6)
    assert all(second[n] == pytest.approx(first[n]) for n in nodes)


def test_a_node_fed_by_many_samples_sits_in_their_middle():
    """A filter fed by seven samples is level with the middle of them, and its plots stay beside it."""
    nodes, edges, size = _groups(1, size_per=7)
    pos = L.arrange(nodes, edges, size)
    tops = [pos[f'g0s{i}'][1] for i in range(7)]
    middle = (min(tops) + max(tops) + H) / 2
    assert pos['f0'][1] + H / 2 == pytest.approx(middle, abs=H / 2)
    assert min(tops) == pytest.approx(min(y for x, y in pos.values()))
