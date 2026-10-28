"""Magnifying the Figure Builder preview, and the layout sketch's match suggestions."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QPixmap, QWheelEvent
from PySide6.QtWidgets import QApplication

from results.figure_builder.ui import sketch as SK
from tests.test_figure_builder import make_input


@pytest.fixture(scope="module")
def app():
    """A Qt application for the widgets."""
    return QApplication.instance() or QApplication([])


@pytest.fixture
def preview(app):
    """A preview showing a blank 800 × 600 figure in a 400 × 300 window."""
    from results.figure_builder.ui.dialog import PreviewLabel
    p = PreviewLabel()
    p.resize(400, 300)
    pm = QPixmap(800, 600)
    pm.fill(Qt.white)
    p.set_figure_pixmap(pm)
    return p


def test_zoom_keeps_the_point_under_the_pointer(preview):
    """Zooming around a point leaves that point of the figure under it."""
    anchor = QPointF(300, 75)
    before = preview._to_fraction(anchor)
    preview.set_zoom(3.0, anchor)
    after = preview._to_fraction(anchor)
    assert preview.zoom() == 3.0
    assert after[0] == pytest.approx(before[0], abs=1e-3)
    assert after[1] == pytest.approx(before[1], abs=1e-3)


def test_zoom_is_limited_and_fit_restores_the_whole_figure(preview):
    """Zoom stays between the whole figure and eight times; Fit goes back to the whole figure."""
    preview.set_zoom(50)
    assert preview.zoom() == preview.ZOOM_MAX
    preview.set_zoom(0.1)
    assert preview.zoom() == preview.ZOOM_MIN
    preview.zoom_in()
    preview.zoom_in()
    assert preview.zoom() == pytest.approx(preview.ZOOM_STEP ** 2)
    preview.pan_by(500, 500)
    preview.zoom_fit()
    assert preview.zoom() == 1.0
    x0, y0, w, h = preview._geometry()
    assert (x0, y0, w, h) == pytest.approx((0, 0, 400, 300))


def test_moving_around_stays_on_the_figure(preview):
    """Moving a magnified figure never shows past its edges."""
    preview.set_zoom(2.0)
    preview.pan_by(10_000, 10_000)
    x0, y0, w, h = preview._geometry()
    assert x0 == pytest.approx(0) and y0 == pytest.approx(0)
    preview.pan_by(-10_000, -10_000)
    x0, y0, w, h = preview._geometry()
    assert x0 + w == pytest.approx(400) and y0 + h == pytest.approx(300)


def wheel(widget, dy, pixel=False, mods=Qt.NoModifier):
    """Send a wheel event: a mouse wheel notch, or a trackpad swipe with *pixel*."""
    pos = QPointF(200, 150)
    event = QWheelEvent(pos, widget.mapToGlobal(pos), QPoint(0, dy) if pixel else QPoint(),
                        QPoint(0, 0) if pixel else QPoint(0, dy), Qt.NoButton, mods,
                        Qt.ScrollUpdate if pixel else Qt.NoScrollPhase, False)
    widget.wheelEvent(event)


def test_mouse_wheel_zooms_and_trackpad_swipe_moves(preview):
    """A mouse wheel zooms; a trackpad swipe moves; Cmd/Ctrl + swipe zooms."""
    wheel(preview, 120)
    assert preview.zoom() > 1.0
    zoom = preview.zoom()
    before = preview._geometry()
    wheel(preview, 40, pixel=True)
    assert preview.zoom() == zoom and preview._geometry()[1] != before[1]
    wheel(preview, 120, pixel=True, mods=Qt.ControlModifier)
    assert preview.zoom() > zoom
    wheel(preview, -2000)
    assert preview.zoom() < zoom


def test_window_zoom_buttons_and_sharper_render(app):
    """The + / − buttons drive the zoom, the label shows it, and the preview renders sharper."""
    from results.figure_builder import FigureBuilderDialog, FigureBuilderNode
    node = FigureBuilderNode()
    node.process_data(make_input())
    dlg = FigureBuilderDialog(node)
    dlg.resize(1200, 800)
    dlg.show()
    app.processEvents()
    fit_dpi = dlg._preview_dpi()
    assert not dlg.zoom_out_btn.isEnabled()
    dlg.zoom_in_btn.click()
    dlg.zoom_in_btn.click()
    assert dlg.preview.zoom() > 1.0 and dlg.zoom_label.text().endswith('%')
    assert dlg.zoom_out_btn.isEnabled()
    assert dlg._preview_dpi() > fit_dpi
    dlg._render()
    dlg.zoom_label.click()
    assert dlg.preview.zoom() == 1.0 and dlg.zoom_label.text() == 'Fit'
    dlg.close()


def panels(*rects):
    """Panels with the given rectangles and ids p0, p1, ..."""
    return [{'id': f'p{i}', 'rect': list(r)} for i, r in enumerate(rects)]


def test_nearly_equal_size_is_suggested_once():
    """A panel nearly the size of another gets one size suggestion, not width and height too."""
    found = SK.suggestions(panels([0, 0, 0.5, 0.5], [0.5, 0, 0.48, 0.47]), 'p1')
    texts = [d['text'] for d in found]
    assert texts[0] == 'Make b the same size as a?'
    assert not any('width' in t or 'height' in t for t in texts)
    assert found[0]['rect'] == [0.5, 0.0, 0.5, 0.5]


def test_edges_nearly_lined_up_are_suggested():
    """A top edge a little off another's is offered to line up."""
    found = SK.suggestions(panels([0, 0.10, 0.4, 0.4], [0.5, 0.13, 0.3, 0.6]), 'p1')
    top = next(d for d in found if 'top-aligned' in d['text'])
    assert top['rect'] == [0.5, 0.1, 0.3, 0.6]


def test_matching_far_or_inset_panels_is_not_suggested():
    """Equal, far apart or inset panels get no suggestion."""
    assert SK.suggestions(panels([0, 0, 0.5, 0.5], [0.5, 0, 0.5, 0.5]), 'p1') == []
    assert SK.suggestions(panels([0, 0, 0.5, 0.5], [0.6, 0.7, 0.2, 0.25]), 'p1') == []
    assert SK.suggestions(panels([0, 0, 1, 1], [0.6, 0.05, 0.35, 0.33]), 'p1') == []


def test_sketch_applies_only_when_asked(app):
    """The chip suggests; nothing moves until Apply, and ✕ hides the suggestion."""
    spec = {'figure': {'width': 8, 'height': 6}, 'panels': panels([0, 0, 0.5, 0.5], [0.5, 0, 0.48, 0.47])}
    sk = SK.LayoutSketch(spec)
    sk.resize(400, 300)
    changes = []
    sk.layout_changed.connect(lambda: changes.append(1))
    sk.select('p1')
    assert sk.current_suggestion() is not None
    assert spec['panels'][1]['rect'] == [0.5, 0, 0.48, 0.47] and not changes
    sk.dismiss_suggestion()
    assert sk.current_suggestion() is None or 'size' not in sk.current_suggestion()['text']
    sk._dismissed.clear()
    sk.refresh_suggestions()
    sk.apply_suggestion()
    assert spec['panels'][1]['rect'] == [0.5, 0.0, 0.5, 0.5] and changes
    assert sk.current_suggestion() is None


def test_match_menu_lists_every_other_panel(app):
    """The context menu can match any other panel exactly, whatever the distance."""
    spec = {'figure': {'width': 8, 'height': 6},
            'panels': panels([0, 0, 0.5, 0.5], [0.6, 0.7, 0.2, 0.25], [0, 0.6, 0.3, 0.3])}
    sk = SK.LayoutSketch(spec)
    sk.select('p1')
    from PySide6.QtWidgets import QMenu
    parent = QMenu()
    menu = sk._match_menu(parent, spec['panels'][1])
    subs = [a.menu() for a in menu.actions()]
    assert [m.title() for m in subs] == ['Panel a', 'Panel c']
    size = next(a for a in subs[0].actions() if a.text() == 'The same size as a')
    size.trigger()
    assert spec['panels'][1]['rect'] == [0.5, 0.5, 0.5, 0.5]
