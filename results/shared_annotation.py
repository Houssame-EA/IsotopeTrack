"""
shared_annotations.py — Figure annotation system for IsotopeTrack.

PowerPoint-style overlay for any PyQtGraph plot: click-to-select, drag-to-move,
resize handles, inspector panel, undo/redo. Designed to plug into any plot node
via a small integration (see `integrate_with_plot_widget` and `AnnotationManager`).

The annotation state lives in cfg['annotations'] (a list of plain dicts), so it
serializes with the workflow and can be rendered to either PyQtGraph (interactive)
or Matplotlib (publication export, future work).

Annotation schema (MVP — 5 types):
    Common fields:
        'id':    str       — unique identifier (e.g. 'ann_3f9a2b')
        'type':  str       — 'text' | 'vline' | 'hline' | 'vband' | 'rect'
        'color': str       — hex, e.g. '#A32D2D'
        'width': int       — line/border width in px
        'alpha': float     — 0..1 fill opacity (where applicable)

    Type-specific fields:
        text:  'x', 'y', 'text', 'font_size', 'box'(bool),
               'arrow_to': [x, y] | None
        vline: 'x', 'label', 'style'('solid'|'dash'|'dot')
        hline: 'y', 'label', 'style'
        vband: 'x1', 'x2', 'label'
        rect:  'x1', 'y1', 'x2', 'y2', 'label', 'filled'(bool)

Usage in a display dialog:

    from results.shared_annotations import (
        AnnotationManager, AnnotationToolbar, AnnotationInspector,
        draw_annotations,
    )

    # In _build_ui:
    self.ann_mgr = AnnotationManager(self.node.config, parent=self)
    self.ann_toolbar = AnnotationToolbar(self.ann_mgr, parent=self)
    self.ann_inspector = AnnotationInspector(self.ann_mgr, parent=self)
    # ... add toolbar to top, inspector to right-side of layout

    # In _refresh, after drawing the plot:
    self.ann_mgr.attach_plot(plot_item)  # rebuilds annotation items on the plot
"""

from __future__ import annotations

import copy
import uuid
from typing import Optional, Callable

import numpy as np

from PySide6.QtCore import Qt, QObject, Signal, QPointF, QRectF
from PySide6.QtGui import (
    QColor, QPen, QBrush, QPainterPath, QFont, QKeySequence, QShortcut,
    QCursor, QPainter, QTransform,
)
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QLabel, QLineEdit,
    QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QPushButton, QColorDialog,
    QFrame, QToolButton, QToolBar, QListWidget, QListWidgetItem, QScrollArea,
    QGroupBox, QSizePolicy, QMenu, QGraphicsItem,
)

import pyqtgraph as pg


# ──────────────────────────────────────────────────────────────────────
# Constants & defaults
# ──────────────────────────────────────────────────────────────────────

ANNOTATION_TYPES = ['text', 'vline', 'hline', 'vband', 'rect']

LINE_STYLES = {
    'solid': Qt.SolidLine,
    'dash':  Qt.DashLine,
    'dot':   Qt.DotLine,
}

DEFAULT_COLOR = '#A32D2D'
SELECTION_COLOR = '#378ADD'
HANDLE_SIZE_PX = 8

QUICK_COLORS = [
    '#A32D2D', '#185FA5', '#0F6E56', '#BA7517',
    '#444441', '#993556', '#534AB7', '#3B6D11',
]


def _new_id() -> str:
    """
    Returns:
        str: Result of the operation.
    """
    return f"ann_{uuid.uuid4().hex[:8]}"


def _default_data(ann_type: str, x: float = 0.0, y: float = 0.0) -> dict:
    """Return a default data dict for a new annotation of the given type.
    Args:
        ann_type (str): The ann type.
        x (float): Input array or value.
        y (float): Input array or value.
    Returns:
        dict: Result of the operation.
    """
    base = {
        'id':    _new_id(),
        'type':  ann_type,
        'color': DEFAULT_COLOR,
        'width': 2,
        'alpha': 0.25,
    }
    if ann_type == 'text':
        base.update({
            'x': x, 'y': y, 'text': 'Label',
            'font_size': 11, 'box': True, 'arrow_to': None,
        })
    elif ann_type == 'vline':
        base.update({'x': x, 'label': '', 'style': 'dash'})
    elif ann_type == 'hline':
        base.update({'y': y, 'label': '', 'style': 'dash'})
    elif ann_type == 'vband':
        base.update({'x1': x - 0.1, 'x2': x + 0.1, 'label': ''})
    elif ann_type == 'rect':
        base.update({
            'x1': x - 0.2, 'y1': y - 0.2, 'x2': x + 0.2, 'y2': y + 0.2,
            'label': '', 'filled': False,
        })
    else:
        raise ValueError(f"Unknown annotation type: {ann_type}")
    return base


# ──────────────────────────────────────────────────────────────────────
# Undo stack
# ──────────────────────────────────────────────────────────────────────

class _Command:
    def apply(self): ...
    def revert(self): ...


class AddCommand(_Command):
    def __init__(self, mgr, data):
        """
        Args:
            mgr (Any): The mgr.
            data (Any): Input data.
        """
        self.mgr = mgr
        self.data = copy.deepcopy(data)

    def apply(self):
        self.mgr._raw_add(self.data)

    def revert(self):
        self.mgr._raw_remove(self.data['id'])


class RemoveCommand(_Command):
    def __init__(self, mgr, data, index):
        """
        Args:
            mgr (Any): The mgr.
            data (Any): Input data.
            index (Any): Row or item index.
        """
        self.mgr = mgr
        self.data = copy.deepcopy(data)
        self.index = index

    def apply(self):
        self.mgr._raw_remove(self.data['id'])

    def revert(self):
        self.mgr._raw_insert(self.index, self.data)


class ModifyCommand(_Command):
    def __init__(self, mgr, ann_id, before, after):
        """
        Args:
            mgr (Any): The mgr.
            ann_id (Any): The ann id.
            before (Any): The before.
            after (Any): The after.
        """
        self.mgr = mgr
        self.ann_id = ann_id
        self.before = copy.deepcopy(before)
        self.after = copy.deepcopy(after)

    def apply(self):
        self.mgr._raw_update(self.ann_id, self.after)

    def revert(self):
        self.mgr._raw_update(self.ann_id, self.before)


class UndoStack(QObject):
    changed = Signal()

    def __init__(self, limit: int = 100):
        """
        Args:
            limit (int): The limit.
        """
        super().__init__()
        self._undo: list[_Command] = []
        self._redo: list[_Command] = []
        self._limit = limit

    def push(self, cmd: _Command):
        """
        Args:
            cmd (_Command): The cmd.
        """
        cmd.apply()
        self._undo.append(cmd)
        if len(self._undo) > self._limit:
            self._undo.pop(0)
        self._redo.clear()
        self.changed.emit()

    def undo(self):
        if not self._undo:
            return
        cmd = self._undo.pop()
        cmd.revert()
        self._redo.append(cmd)
        self.changed.emit()

    def redo(self):
        if not self._redo:
            return
        cmd = self._redo.pop()
        cmd.apply()
        self._undo.append(cmd)
        self.changed.emit()

    def can_undo(self) -> bool: return bool(self._undo)
    def can_redo(self) -> bool: return bool(self._redo)


# ──────────────────────────────────────────────────────────────────────
# Per-type graphics wrappers
# ──────────────────────────────────────────────────────────────────────

class _DraggableText(pg.TextItem):
    """TextItem with built-in drag-to-move + arrow line to an optional target."""

    sigPositionChangeFinished = Signal(object)
    sigClicked = Signal(object)

    def __init__(self, html: str = "", color='#000000', anchor=(0, 0)):
        """
        Args:
            html (str): The html.
            color (Any): Colour value.
            anchor (Any): The anchor.
        """
        super().__init__(html=html, color=color, anchor=anchor)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setAcceptHoverEvents(True)
        self._dragging = False
        self._drag_offset = None

    def hoverEnterEvent(self, ev):
        """
        Args:
            ev (Any): The ev.
        """
        self.setCursor(QCursor(Qt.SizeAllCursor))
        super().hoverEnterEvent(ev)

    def hoverLeaveEvent(self, ev):
        """
        Args:
            ev (Any): The ev.
        """
        self.unsetCursor()
        super().hoverLeaveEvent(ev)

    def mousePressEvent(self, ev):
        """
        Args:
            ev (Any): The ev.
        """
        if ev.button() == Qt.LeftButton:
            self.sigClicked.emit(self)
            self._dragging = True
            self._drag_offset = ev.pos()
            ev.accept()
        else:
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        """
        Args:
            ev (Any): The ev.
        """
        if self._dragging:
            delta = ev.pos() - self._drag_offset
            new_pos = self.pos() + delta
            self.setPos(new_pos)
            ev.accept()
        else:
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        """
        Args:
            ev (Any): The ev.
        """
        if self._dragging and ev.button() == Qt.LeftButton:
            self._dragging = False
            self.sigPositionChangeFinished.emit(self)
            ev.accept()
        else:
            super().mouseReleaseEvent(ev)


class BaseAnnotation(QObject):
    """Base wrapper. Subclasses implement _build_item, _sync_from_data, _hookup."""
    TYPE = "base"

    sig_clicked = Signal(str)
    sig_drag_finished = Signal(str, dict)

    def __init__(self, data: dict):
        """
        Args:
            data (dict): Input data.
        """
        super().__init__()
        self.data = data
        self.item = None
        self.extras: list = []
        self._plot_item = None
        self._selected = False

    # ── public lifecycle ────────────────────────────

    def attach(self, plot_item):
        """Create and add item(s) to the plot.
        Args:
            plot_item (Any): The plot item.
        """
        self._plot_item = plot_item
        self._build_item(plot_item)
        self._sync_from_data()
        self._hookup()

    def detach(self):
        """Remove all items from the plot."""
        if self._plot_item is None:
            return
        for it in [self.item] + self.extras:
            if it is not None:
                try:
                    self._plot_item.removeItem(it)
                except Exception:
                    pass
        self.item = None
        self.extras.clear()
        self._plot_item = None

    def refresh(self):
        """Reapply data → visual."""
        if self.item is not None:
            self._sync_from_data()

    def set_selected(self, selected: bool):
        """
        Args:
            selected (bool): The selected.
        """
        self._selected = selected
        if self.item is not None:
            self._apply_selection_style()

    # ── subclass API ────────────────────────────────

    def _build_item(self, plot_item):
        """
        Args:
            plot_item (Any): The plot item.
        """
        raise NotImplementedError

    def _sync_from_data(self):
        raise NotImplementedError

    def _hookup(self):
        """Wire pyqtgraph signals to sig_clicked / sig_drag_finished."""
        pass

    def _apply_selection_style(self):
        """Visual change when selected vs. unselected."""
        pass

    # ── helpers ─────────────────────────────────────

    def _color(self) -> QColor:
        """
        Returns:
            QColor: Result of the operation.
        """
        return QColor(self.data.get('color', DEFAULT_COLOR))

    def _pen(self) -> QPen:
        """
        Returns:
            QPen: Result of the operation.
        """
        w = int(self.data.get('width', 2))
        return QPen(self._color(), w,
                    LINE_STYLES.get(self.data.get('style', 'solid'), Qt.SolidLine))


# ──────────────────────────────────────────────────────────────────────
# Text annotation
# ──────────────────────────────────────────────────────────────────────

class TextAnnotation(BaseAnnotation):
    TYPE = 'text'

    def __init__(self, data):
        """
        Args:
            data (Any): Input data.
        """
        super().__init__(data)
        self._arrow = None

    def _build_item(self, plot_item):
        """
        Args:
            plot_item (Any): The plot item.
        """
        self.item = _DraggableText(html="", anchor=(0, 0.5))
        plot_item.addItem(self.item, ignoreBounds=True)
        self._arrow = pg.PlotDataItem(pen=pg.mkPen(self._color(), width=1.5))
        plot_item.addItem(self._arrow, ignoreBounds=True)
        self.extras = [self._arrow]

    def _sync_from_data(self):
        d = self.data
        color = d.get('color', '#000000')
        text = d.get('text', '')
        font_size = int(d.get('font_size', 11))
        boxed = bool(d.get('box', True))

        bg = 'rgba(255,255,255,0.9)' if boxed else 'transparent'
        border = f"border: 1.5px solid {color};" if boxed else ""
        padding = "padding: 3px 6px;" if boxed else ""
        html = (f'<span style="background:{bg}; {border} {padding} '
                f'color:{color}; font-size:{font_size}pt; '
                f'border-radius: 3px;">{text}</span>')
        self.item.setHtml(html)
        self.item.setPos(float(d['x']), float(d['y']))

        target = d.get('arrow_to')
        if target is not None and len(target) == 2:
            try:
                tx, ty = float(target[0]), float(target[1])
                self._arrow.setData([float(d['x']), tx], [float(d['y']), ty])
                self._arrow.setPen(pg.mkPen(color, width=1.5))
                self._arrow.setVisible(True)
            except (TypeError, ValueError):
                self._arrow.setVisible(False)
        else:
            self._arrow.setVisible(False)

    def _hookup(self):
        self.item.sigClicked.connect(lambda _: self.sig_clicked.emit(self.data['id']))
        self.item.sigPositionChangeFinished.connect(self._on_drag_done)

    def _on_drag_done(self, _):
        """
        Args:
            _ (Any): The  .
        """
        pos = self.item.pos()
        new = copy.deepcopy(self.data)
        new['x'] = float(pos.x())
        new['y'] = float(pos.y())
        self.sig_drag_finished.emit(self.data['id'], new)

    def _apply_selection_style(self):
        d = self.data
        color = d.get('color', '#000000')
        text = d.get('text', '')
        font_size = int(d.get('font_size', 11))
        boxed = bool(d.get('box', True))
        bg = 'rgba(230,241,251,0.95)' if self._selected else (
             'rgba(255,255,255,0.9)' if boxed else 'transparent')
        border_color = SELECTION_COLOR if self._selected else color
        border_w = 2 if self._selected else 1.5
        border = f"border: {border_w}px solid {border_color};" if (boxed or self._selected) else ""
        padding = "padding: 3px 6px;" if (boxed or self._selected) else ""
        html = (f'<span style="background:{bg}; {border} {padding} '
                f'color:{color}; font-size:{font_size}pt; '
                f'border-radius: 3px;">{text}</span>')
        self.item.setHtml(html)


# ──────────────────────────────────────────────────────────────────────
# Infinite line annotations
# ──────────────────────────────────────────────────────────────────────

class _LineAnnotation(BaseAnnotation):
    """Shared logic for vertical & horizontal lines."""
    ANGLE = 90
    POS_KEY = 'x'

    def _build_item(self, plot_item):
        """
        Args:
            plot_item (Any): The plot item.
        """
        self.item = pg.InfiniteLine(
            angle=self.ANGLE, movable=True, pen=self._pen(),
        )
        plot_item.addItem(self.item, ignoreBounds=True)
        self._label_item = pg.TextItem(
            "", color=self.data.get('color', DEFAULT_COLOR), anchor=(0.5, 1))
        plot_item.addItem(self._label_item, ignoreBounds=True)
        self.extras = [self._label_item]

    def _sync_from_data(self):
        d = self.data
        pos = float(d[self.POS_KEY])
        self.item.setValue(pos)
        self.item.setPen(self._pen())

        label = d.get('label', '')
        if label:
            self._label_item.setText(label, color=d.get('color', DEFAULT_COLOR))
            if self.ANGLE == 90:
                self._label_item.setPos(pos, 0)
            else:
                self._label_item.setPos(0, pos)
            self._label_item.setVisible(True)
        else:
            self._label_item.setVisible(False)

    def _hookup(self):
        self.item.sigPositionChangeFinished.connect(self._on_drag_done)
        self.item.sigClicked.connect(lambda _: self.sig_clicked.emit(self.data['id']))

    def _on_drag_done(self, _):
        """
        Args:
            _ (Any): The  .
        """
        new = copy.deepcopy(self.data)
        new[self.POS_KEY] = float(self.item.value())
        self.sig_drag_finished.emit(self.data['id'], new)

    def _apply_selection_style(self):
        if self._selected:
            w = int(self.data.get('width', 2))
            style = LINE_STYLES.get(self.data.get('style', 'solid'), Qt.SolidLine)
            self.item.setPen(QPen(QColor(SELECTION_COLOR), w, style))
        else:
            self.item.setPen(self._pen())


class VLineAnnotation(_LineAnnotation):
    TYPE = 'vline'
    ANGLE = 90
    POS_KEY = 'x'


class HLineAnnotation(_LineAnnotation):
    TYPE = 'hline'
    ANGLE = 0
    POS_KEY = 'y'


# ──────────────────────────────────────────────────────────────────────
# Shaded vertical band
# ──────────────────────────────────────────────────────────────────────

class VBandAnnotation(BaseAnnotation):
    TYPE = 'vband'

    def _build_item(self, plot_item):
        """
        Args:
            plot_item (Any): The plot item.
        """
        c = self._color()
        alpha = int(255 * float(self.data.get('alpha', 0.25)))
        brush = QBrush(QColor(c.red(), c.green(), c.blue(), alpha))
        self.item = pg.LinearRegionItem(
            orientation='vertical', movable=True, brush=brush,
            pen=pg.mkPen(c, width=1),
        )
        plot_item.addItem(self.item, ignoreBounds=True)
        self._label_item = pg.TextItem("", color=self.data.get('color', DEFAULT_COLOR),
                                        anchor=(0.5, 1))
        plot_item.addItem(self._label_item, ignoreBounds=True)
        self.extras = [self._label_item]

    def _sync_from_data(self):
        d = self.data
        x1, x2 = float(d['x1']), float(d['x2'])
        self.item.setRegion([x1, x2])
        c = self._color()
        alpha = int(255 * float(d.get('alpha', 0.25)))
        self.item.setBrush(QBrush(QColor(c.red(), c.green(), c.blue(), alpha)))
        edge_pen = pg.mkPen(c, width=max(1, int(d.get('width', 2)) - 1))
        try:
            for line in self.item.lines:
                line.setPen(edge_pen)
        except Exception:
            pass

        label = d.get('label', '')
        if label:
            self._label_item.setText(label, color=d.get('color', DEFAULT_COLOR))
            self._label_item.setPos((x1 + x2) / 2, 0)
            self._label_item.setVisible(True)
        else:
            self._label_item.setVisible(False)

    def _hookup(self):
        self.item.sigRegionChangeFinished.connect(self._on_drag_done)

    def _on_drag_done(self, _):
        """
        Args:
            _ (Any): The  .
        """
        new = copy.deepcopy(self.data)
        r = self.item.getRegion()
        new['x1'] = float(min(r))
        new['x2'] = float(max(r))
        self.sig_drag_finished.emit(self.data['id'], new)


# ──────────────────────────────────────────────────────────────────────
# Rectangle
# ──────────────────────────────────────────────────────────────────────

class RectAnnotation(BaseAnnotation):
    TYPE = 'rect'

    def __init__(self, data):
        """
        Args:
            data (Any): Input data.
        """
        super().__init__(data)
        self._corner_handles = []

    def _build_item(self, plot_item):
        """
        Args:
            plot_item (Any): The plot item.
        """
        self.item = pg.PlotDataItem(pen=self._pen())
        plot_item.addItem(self.item, ignoreBounds=True)

        self._fill_item = pg.PlotDataItem(pen=pg.mkPen(None))
        plot_item.addItem(self._fill_item, ignoreBounds=True)

        self._label_item = pg.TextItem(
            "", color=self.data.get('color', DEFAULT_COLOR), anchor=(0, 1))
        plot_item.addItem(self._label_item, ignoreBounds=True)

        self._handle_items = []
        self._handle_corners = []
        self.extras = [self._fill_item, self._label_item]

    def _sync_from_data(self):
        d = self.data
        x1, y1 = float(d['x1']), float(d['y1'])
        x2, y2 = float(d['x2']), float(d['y2'])
        xlo, xhi = min(x1, x2), max(x1, x2)
        ylo, yhi = min(y1, y2), max(y1, y2)

        xs = [xlo, xhi, xhi, xlo, xlo]
        ys = [ylo, ylo, yhi, yhi, ylo]
        self.item.setData(xs, ys)
        self.item.setPen(self._pen())

        if d.get('filled', False):
            c = self._color()
            alpha = int(255 * float(d.get('alpha', 0.25)))
            self._fill_item.setData(xs, ys)
            self._fill_item.setFillLevel(ylo)
            self._fill_item.setFillBrush(
                pg.mkBrush(c.red(), c.green(), c.blue(), alpha))
            self._fill_item.setVisible(True)
        else:
            self._fill_item.setVisible(False)

        label = d.get('label', '')
        if label:
            self._label_item.setText(label, color=d.get('color', DEFAULT_COLOR))
            self._label_item.setPos(xlo, yhi)
            self._label_item.setVisible(True)
        else:
            self._label_item.setVisible(False)

        if self._handle_items:
            corners = {
                'tl': (xlo, yhi), 'tr': (xhi, yhi),
                'bl': (xlo, ylo), 'br': (xhi, ylo),
            }
            for (h, which) in zip(self._handle_items, self._handle_corners):
                cx, cy = corners[which]
                try:
                    h.setPos(cx, cy)
                except Exception:
                    pass

    def _hookup(self):
        try:
            self.item.sigClicked.connect(
                lambda *a: self.sig_clicked.emit(self.data['id']))
        except Exception:
            pass
        try:
            self._fill_item.sigClicked.connect(
                lambda *a: self.sig_clicked.emit(self.data['id']))
        except Exception:
            pass

    def _apply_selection_style(self):
        self.item.setPen(self._pen())
        if self._selected:
            self._ensure_handles()
        else:
            self._remove_handles()

    # ── corner handles for resize ─────────────────

    def _ensure_handles(self):
        """Create the four corner-drag handles if they don't already exist."""
        if self._handle_items or self._plot_item is None:
            return
        d = self.data
        x1, y1 = float(d['x1']), float(d['y1'])
        x2, y2 = float(d['x2']), float(d['y2'])
        xlo, xhi = min(x1, x2), max(x1, x2)
        ylo, yhi = min(y1, y2), max(y1, y2)
        spec = [('tl', xlo, yhi), ('tr', xhi, yhi),
                ('bl', xlo, ylo), ('br', xhi, ylo)]
        for which, cx, cy in spec:
            try:
                h = pg.TargetItem(pos=(cx, cy), size=10,
                                   pen=pg.mkPen(SELECTION_COLOR, width=1.5),
                                   brush=pg.mkBrush('w'),
                                   movable=True)
                h.sigPositionChangeFinished.connect(
                    lambda _h=h, w=which: self._on_handle_done(w, _h))
                self._plot_item.addItem(h, ignoreBounds=True)
                self._handle_items.append(h)
                self._handle_corners.append(which)
            except Exception:
                pass

    def _remove_handles(self):
        for h in self._handle_items:
            try:
                self._plot_item.removeItem(h)
            except Exception:
                pass
        self._handle_items = []
        self._handle_corners = []

    def _on_handle_done(self, which: str, handle):
        """
        Args:
            which (str): The which.
            handle (Any): The handle.
        """
        new = copy.deepcopy(self.data)
        try:
            pos = handle.pos()
            hx, hy = float(pos.x()), float(pos.y())
        except Exception:
            return
        x1, y1 = float(new['x1']), float(new['y1'])
        x2, y2 = float(new['x2']), float(new['y2'])
        xlo, xhi = min(x1, x2), max(x1, x2)
        ylo, yhi = min(y1, y2), max(y1, y2)
        if which == 'tl':
            xlo, yhi = hx, hy
        elif which == 'tr':
            xhi, yhi = hx, hy
        elif which == 'bl':
            xlo, ylo = hx, hy
        elif which == 'br':
            xhi, ylo = hx, hy
        new['x1'], new['x2'] = xlo, xhi
        new['y1'], new['y2'] = ylo, yhi
        self.sig_drag_finished.emit(self.data['id'], new)

    def detach(self):
        self._remove_handles()
        super().detach()


# ──────────────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────────────

_ANNOTATION_CLASSES = {
    'text':  TextAnnotation,
    'vline': VLineAnnotation,
    'hline': HLineAnnotation,
    'vband': VBandAnnotation,
    'rect':  RectAnnotation,
}


def make_annotation(data: dict) -> BaseAnnotation:
    """
    Args:
        data (dict): Input data.
    Returns:
        BaseAnnotation: Result of the operation.
    """
    cls = _ANNOTATION_CLASSES.get(data.get('type'))
    if cls is None:
        raise ValueError(f"Unknown annotation type: {data.get('type')}")
    return cls(data)


# ──────────────────────────────────────────────────────────────────────
# AnnotationManager — the coordinator
# ──────────────────────────────────────────────────────────────────────

class _SceneMouseEventFilter(QObject):
    """
    Event filter installed on the pyqtgraph plot scene.

    Purpose: consume mouse press / release / move events at the scene level
    so they never bubble to the parent dialog or the OS window manager.
    Without this, macOS treats an unaccepted scene-level mouse release
    (produced after dragging an annotation to a new position) as a click
    outside the focused dialog, which raises the main application window
    above the dialog.

    We don't filter events that would block interaction — pyqtgraph items
    still receive their own mousePressEvent / mouseMoveEvent / mouseReleaseEvent
    via the scene's normal event dispatch. The filter only accepts the event
    *after* dispatch, preventing onward propagation.
    """

    _MOUSE_EVENT_TYPES = None

    def __init__(self, manager):
        """
        Args:
            manager (Any): The manager.
        """
        super().__init__()
        self._manager = manager

    def eventFilter(self, obj, event):
        """
        Args:
            obj (Any): The obj.
            event (Any): Qt event object.
        Returns:
            bool: Result of the operation.
        """
        if _SceneMouseEventFilter._MOUSE_EVENT_TYPES is None:
            from PySide6.QtCore import QEvent
            _SceneMouseEventFilter._MOUSE_EVENT_TYPES = {
                QEvent.Type.GraphicsSceneMousePress,
                QEvent.Type.GraphicsSceneMouseRelease,
                QEvent.Type.GraphicsSceneMouseMove,
                QEvent.Type.GraphicsSceneMouseDoubleClick,
            }
        try:
            if event.type() in _SceneMouseEventFilter._MOUSE_EVENT_TYPES:
                event.setAccepted(True)
        except Exception:
            pass
        return False


class AnnotationManager(QObject):
    """
    Owns cfg['annotations'], the list of live annotation wrappers, the selection
    state, and the undo stack. Exposes methods for toolbar/inspector to call.

    Flow:
      - Plot dialog calls attach_plot(plot_item) after every _refresh to rebuild items.
      - Toolbar calls begin_insert(type) to enter insert mode; next click on the
        plot scene creates an annotation at the clicked (data) coordinates.
      - Inspector calls update_selected(new_data) to modify the selected annotation.
      - Manager emits sig_selection_changed when selection changes.
    """

    sig_annotations_changed = Signal()
    sig_selection_changed = Signal(object)

    def __init__(self, cfg: dict, parent=None):
        """
        Args:
            cfg (dict): The cfg.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.cfg = cfg
        self.cfg.setdefault('annotations', [])
        self._wrappers: dict[str, BaseAnnotation] = {}
        self._selected_id: Optional[str] = None
        self._plot_item = None
        self._connected_scene = None
        self._insert_type: Optional[str] = None
        self._scene_filter = None

        self.undo_stack = UndoStack()
        self.undo_stack.changed.connect(self._on_undo_changed)

    # ── plot attachment ─────────────────────────────

    def attach_plot(self, plot_item):
        """Called after every plot refresh. Rebuilds all annotation items.
        Args:
            plot_item (Any): The plot item.
        """
        self._detach_all()
        self._plot_item = plot_item
        for d in self.cfg.get('annotations', []):
            self._build_wrapper(d)
        try:
            scene = plot_item.scene()
            if scene is not None:
                if self._connected_scene is scene:
                    try:
                        scene.sigMouseClicked.disconnect(self._on_scene_clicked)
                    except (RuntimeError, TypeError):
                        pass
                    if self._scene_filter is not None:
                        try:
                            scene.removeEventFilter(self._scene_filter)
                        except (RuntimeError, TypeError):
                            pass
                scene.sigMouseClicked.connect(self._on_scene_clicked)

                self._scene_filter = _SceneMouseEventFilter(self)
                scene.installEventFilter(self._scene_filter)

                self._connected_scene = scene
        except Exception:
            pass
        if self._selected_id and self._selected_id in self._wrappers:
            self._wrappers[self._selected_id].set_selected(True)

    def _detach_all(self):
        for w in self._wrappers.values():
            w.detach()
        self._wrappers.clear()

    def _build_wrapper(self, data):
        """
        Args:
            data (Any): Input data.
        """
        try:
            w = make_annotation(data)
            w.sig_clicked.connect(self._on_item_clicked)
            w.sig_drag_finished.connect(self._on_item_drag_done)
            w.attach(self._plot_item)
            self._wrappers[data['id']] = w
        except Exception as e:
            print(f"[annotations] failed to build {data.get('type')}: {e}")

    # ── insert mode ─────────────────────────────────

    def begin_insert(self, ann_type: str):
        """
        Args:
            ann_type (str): The ann type.
        """
        if ann_type not in ANNOTATION_TYPES:
            return
        self._insert_type = ann_type

    def cancel_insert(self):
        self._insert_type = None

    def is_inserting(self) -> bool:
        """
        Returns:
            bool: Result of the operation.
        """
        return self._insert_type is not None

    def _on_scene_clicked(self, ev):
        """Scene-level click: either places a new annotation (insert mode),
        selects the annotation under the click, or clears selection on empty.
        Args:
            ev (Any): The ev.
        """
        if self._plot_item is None:
            return
        if ev.button() != Qt.LeftButton:
            return

        scene_pos = ev.scenePos()
        scene = self._plot_item.scene()
        if scene is None:
            return

        owned = {}
        for ann_id, w in self._wrappers.items():
            if w.item is not None:
                owned[w.item] = ann_id
            for ex in w.extras:
                if ex is not None:
                    owned[ex] = ann_id

        hit_id = None
        for hit in scene.items(scene_pos):
            node = hit
            while node is not None:
                if node in owned:
                    hit_id = owned[node]
                    break
                node = node.parentItem()
            if hit_id is not None:
                break

        if self._insert_type is not None:
            try:
                vb = self._plot_item.getViewBox()
                data_pt = vb.mapSceneToView(scene_pos)
                self.add_new(self._insert_type, float(data_pt.x()), float(data_pt.y()))
            except Exception as e:
                print(f"[annotations] insert failed: {e}")
            finally:
                self._insert_type = None
            try:
                ev.accept()
            except Exception:
                pass
            return

        if hit_id is not None:
            self.select(hit_id)
        else:
            self.select(None)

        try:
            ev.accept()
        except Exception:
            pass

    # ── CRUD + undo ─────────────────────────────────

    def add_new(self, ann_type: str, x: float, y: float):
        """
        Args:
            ann_type (str): The ann type.
            x (float): Input array or value.
            y (float): Input array or value.
        """
        data = _default_data(ann_type, x, y)
        self.undo_stack.push(AddCommand(self, data))
        self.select(data['id'])

    def remove_selected(self):
        if self._selected_id is None:
            return
        annotations = self.cfg.get('annotations', [])
        for i, d in enumerate(annotations):
            if d['id'] == self._selected_id:
                self.undo_stack.push(RemoveCommand(self, d, i))
                self.select(None)
                return

    def update_selected(self, new_data: dict):
        """
        Args:
            new_data (dict): The new data.
        """
        if self._selected_id is None:
            return
        before = None
        for d in self.cfg.get('annotations', []):
            if d['id'] == self._selected_id:
                before = d
                break
        if before is None:
            return
        self.undo_stack.push(ModifyCommand(
            self, self._selected_id, before, new_data))

    def select(self, ann_id: Optional[str]):
        """
        Args:
            ann_id (Optional[str]): The ann id.
        """
        if ann_id == self._selected_id:
            return
        if self._selected_id and self._selected_id in self._wrappers:
            self._wrappers[self._selected_id].set_selected(False)
        self._selected_id = ann_id
        if ann_id and ann_id in self._wrappers:
            self._wrappers[ann_id].set_selected(True)
        self.sig_selection_changed.emit(self.get_selected_data())

    def get_selected_data(self) -> Optional[dict]:
        """
        Returns:
            Optional[dict]: Result of the operation.
        """
        if self._selected_id is None:
            return None
        for d in self.cfg.get('annotations', []):
            if d['id'] == self._selected_id:
                return d
        return None

    def get_all_data(self) -> list:
        """
        Returns:
            list: Result of the operation.
        """
        return list(self.cfg.get('annotations', []))


    def _raw_add(self, data):
        """
        Args:
            data (Any): Input data.
        """
        self.cfg.setdefault('annotations', []).append(copy.deepcopy(data))
        if self._plot_item is not None:
            self._build_wrapper(self.cfg['annotations'][-1])
        self.sig_annotations_changed.emit()

    def _raw_insert(self, index, data):
        """
        Args:
            index (Any): Row or item index.
            data (Any): Input data.
        """
        self.cfg.setdefault('annotations', []).insert(index, copy.deepcopy(data))
        if self._plot_item is not None:
            self._build_wrapper(self.cfg['annotations'][index])
        self.sig_annotations_changed.emit()

    def _raw_remove(self, ann_id):
        """
        Args:
            ann_id (Any): The ann id.
        """
        lst = self.cfg.get('annotations', [])
        for i, d in enumerate(lst):
            if d['id'] == ann_id:
                lst.pop(i)
                break
        if ann_id in self._wrappers:
            self._wrappers[ann_id].detach()
            del self._wrappers[ann_id]
        if self._selected_id == ann_id:
            self._selected_id = None
            self.sig_selection_changed.emit(None)
        self.sig_annotations_changed.emit()

    def _raw_update(self, ann_id, new_data):
        """
        Args:
            ann_id (Any): The ann id.
            new_data (Any): The new data.
        """
        lst = self.cfg.get('annotations', [])
        for i, d in enumerate(lst):
            if d['id'] == ann_id:
                lst[i] = copy.deepcopy(new_data)
                if ann_id in self._wrappers:
                    self._wrappers[ann_id].data = lst[i]
                    self._wrappers[ann_id].refresh()
                break
        if self._selected_id == ann_id:
            self.sig_selection_changed.emit(new_data)
        self.sig_annotations_changed.emit()

    # ── signal handlers ─────────────────────────────

    def _on_item_clicked(self, ann_id: str):
        """
        Args:
            ann_id (str): The ann id.
        """
        self.select(ann_id)

    def _on_item_drag_done(self, ann_id: str, new_data: dict):
        """
        Args:
            ann_id (str): The ann id.
            new_data (dict): The new data.
        """
        for d in self.cfg.get('annotations', []):
            if d['id'] == ann_id:
                before = d
                break
        else:
            return
        if before == new_data:
            return
        self.undo_stack.push(ModifyCommand(self, ann_id, before, new_data))

    def _on_undo_changed(self):
        if self._selected_id:
            self.sig_selection_changed.emit(self.get_selected_data())


# ──────────────────────────────────────────────────────────────────────
# Ambient UI — context menu, floating inspector, shelf button
# ──────────────────────────────────────────────────────────────────────

SwatchColors = [
    '#A32D2D',
    '#185FA5',
    '#0F6E56',
    '#BA7517',
    '#534AB7',
    '#444441',
]


def build_annotate_submenu(parent_menu,
                           mgr: 'AnnotationManager',
                           data_x: float,
                           data_y: float,
                           smart_actions=None,
                           title_prefix: str = "Annotate here") -> None:
    """
    Insert annotation items at the top of `parent_menu`, with coordinates
    pre-filled from (data_x, data_y). Lays out inline (no submenu cascade)
    so the menu is fast to scan and robust against Qt-side menu lifetime
    issues.

    Args:
        parent_menu:    an existing QMenu to prepend into
        mgr:            AnnotationManager for this plot
        data_x, data_y: click coordinates in plot data space
        smart_actions:  optional list of (label:str, callback:callable) for
                        plot-type-specific data-aware actions
        title_prefix:   header text before the coord pair
    Returns:
        None
    """
    coord_txt = f"({data_x:.3g}, {data_y:.3g})"

    header = parent_menu.addAction(f"✦  {title_prefix}   {coord_txt}")
    header.setEnabled(False)
    f = header.font(); f.setBold(True); header.setFont(f)

    a = parent_menu.addAction("   Text label")
    a.triggered.connect(lambda _=False, x=data_x, y=data_y:
                         mgr.add_new('text', x, y))

    a = parent_menu.addAction(f"   Vertical line at x = {data_x:.3g}")
    a.triggered.connect(lambda _=False, x=data_x, y=data_y:
                         mgr.add_new('vline', x, y))

    a = parent_menu.addAction(f"   Horizontal line at y = {data_y:.3g}")
    a.triggered.connect(lambda _=False, x=data_x, y=data_y:
                         mgr.add_new('hline', x, y))

    a = parent_menu.addAction("   Shaded band (centered here)")
    a.triggered.connect(lambda _=False, x=data_x, y=data_y:
                         mgr.add_new('vband', x, y))

    a = parent_menu.addAction("   Rectangle / box")
    a.triggered.connect(lambda _=False, x=data_x, y=data_y:
                         mgr.add_new('rect', x, y))

    if smart_actions:
        parent_menu.addSeparator()
        hdr = parent_menu.addAction("✦  Data-aware actions")
        hdr.setEnabled(False)
        f = hdr.font(); f.setItalic(True); hdr.setFont(f)
        for label, cb in smart_actions:
            act = parent_menu.addAction(f"   {label}")
            act.triggered.connect(cb)

    parent_menu.addSeparator()


# ──────────────────────────────────────────────────────────────────────
# FloatingInspector
# ──────────────────────────────────────────────────────────────────────

def _anchor_for(data: dict, viewbox) -> tuple[float, float]:
    """Return (data_x, data_y) near which the floating inspector should sit.
    Args:
        data (dict): Input data.
        viewbox (Any): The viewbox.
    Returns:
        tuple[float, float]: Result of the operation.
    """
    t = data.get('type')
    try:
        xr, yr = viewbox.viewRange()
    except Exception:
        xr, yr = (0, 1), (0, 1)
    if t == 'text':
        return float(data.get('x', 0)), float(data.get('y', 0))
    if t == 'vline':
        return float(data.get('x', 0)), yr[0] + 0.85 * (yr[1] - yr[0])
    if t == 'hline':
        return xr[0] + 0.2 * (xr[1] - xr[0]), float(data.get('y', 0))
    if t == 'vband':
        x1, x2 = float(data.get('x1', 0)), float(data.get('x2', 0))
        return (x1 + x2) / 2, yr[0] + 0.85 * (yr[1] - yr[0])
    if t == 'rect':
        x1, x2 = float(data.get('x1', 0)), float(data.get('x2', 0))
        y1, y2 = float(data.get('y1', 0)), float(data.get('y2', 0))
        return (x1 + x2) / 2, max(y1, y2)
    return 0.0, 0.0


class _ColorSwatch(QToolButton):
    """A round, clickable color dot. Emits sig_picked(hex_str)."""
    sig_picked = Signal(str)

    def __init__(self, hex_color: str, selected: bool = False, size: int = 20,
                 parent=None):
        """
        Args:
            hex_color (str): The hex color.
            selected (bool): The selected.
            size (int): Size value.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self._hex = hex_color
        self._size = size
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self._set_selected(selected)
        self.clicked.connect(lambda: self.sig_picked.emit(self._hex))

    def _set_selected(self, sel: bool):
        """
        Args:
            sel (bool): The sel.
        """
        border = "2px solid #222" if sel else "1px solid rgba(0,0,0,0.25)"
        self.setStyleSheet(
            f"QToolButton {{ "
            f"  background-color: {self._hex}; "
            f"  border: {border}; "
            f"  border-radius: {self._size // 2}px; "
            f"}} "
            f"QToolButton:hover {{ "
            f"  border: 2px solid rgba(0,0,0,0.55); "
            f"}}"
        )

    def set_selected(self, sel: bool):
        """
        Args:
            sel (bool): The sel.
        """
        self._set_selected(sel)


class _CustomColorButton(QToolButton):
    """The '+' button that opens a QColorDialog. Emits sig_picked(hex)."""
    sig_picked = Signal(str)

    def __init__(self, size: int = 20, parent=None):
        """
        Args:
            size (int): Size value.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.setText("+")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"QToolButton {{ "
            f"  background: white; "
            f"  border: 1px dashed rgba(0,0,0,0.35); "
            f"  border-radius: {size // 2}px; "
            f"  color: rgba(0,0,0,0.55); "
            f"  font-size: 13px; font-weight: bold; "
            f"}} "
            f"QToolButton:hover {{ border-color: #222; color: #222; }}"
        )
        self.clicked.connect(self._pick)

    def _pick(self):
        c = QColorDialog.getColor()
        if c.isValid():
            self.sig_picked.emit(c.name())


class FloatingInspector(QFrame):
    """
    Small popover shown next to the currently selected annotation.

    Parented to a *persistent* container (not the plot widget, which gets
    recreated on every refresh). Uses a getter to find the current plot
    widget / viewbox for positioning.

    Lifecycle:
        fi = FloatingInspector(mgr, parent=plot_container)
        fi.set_plot_accessor(lambda: (self.pw, self.primary_plot_item))
        # after every _refresh() in the host dialog:
        fi.attach(current_plot_item)
    """

    FIXED_WIDTH = 252
    OFFSET_X = 14
    OFFSET_Y = 14

    def __init__(self, mgr: 'AnnotationManager', parent: QWidget):
        """
        Args:
            mgr ('AnnotationManager'): The mgr.
            parent (QWidget): Parent widget or object.
        """
        super().__init__(parent)
        self.mgr = mgr
        self._plot_accessor: Callable = lambda: (None, None)
        self._plot_item = None
        self._viewbox = None
        self._editors: dict = {}
        self._swatches: list[_ColorSwatch] = []

        self.setObjectName("FloatingInspector")
        self.setFrameShape(QFrame.NoFrame)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            #FloatingInspector {
                background-color: rgba(255,255,255,0.985);
                border: 1px solid rgba(0,0,0,0.12);
                border-radius: 10px;
            }
            QLabel { color: #333; font-size: 11px; }
            QLabel[role="type"] {
                color: #888; font-size: 9px; font-weight: bold;
                letter-spacing: 1px;
            }
            QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
                font-size: 12px; padding: 3px 6px; min-height: 22px;
                border: 1px solid rgba(0,0,0,0.15);
                border-radius: 4px;
                background: white;
            }
            QLineEdit:focus, QDoubleSpinBox:focus,
            QSpinBox:focus, QComboBox:focus {
                border: 1px solid #378ADD;
            }
            QPushButton#delete_btn {
                color: #A32D2D; background: transparent; border: none;
                font-size: 11px; padding: 2px 4px;
            }
            QPushButton#delete_btn:hover { text-decoration: underline; }
            QCheckBox { font-size: 11px; color: #555; }
        """)
        self.setFixedWidth(self.FIXED_WIDTH)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)
        self._form: Optional[QWidget] = None

        self.mgr.sig_selection_changed.connect(self._on_selection_changed)

        self.hide()

    # ── public accessor wiring ──────────────────────

    def set_plot_accessor(self, fn: Callable):
        """fn() → (plot_widget, plot_item).  Both may be None.
        Args:
            fn (Callable): The fn.
        """
        self._plot_accessor = fn

    def attach(self, plot_item):
        """Called after each host-dialog _refresh to rebind positioning signals.
        Args:
            plot_item (Any): The plot item.
        """
        if self._viewbox is not None:
            try:
                self._viewbox.sigRangeChanged.disconnect(self._reposition)
            except (RuntimeError, TypeError):
                pass
            self._viewbox = None
        self._plot_item = plot_item
        if plot_item is not None:
            vb = plot_item.getViewBox()
            if vb is not None:
                vb.sigRangeChanged.connect(self._reposition)
                self._viewbox = vb
        sel = self.mgr.get_selected_data()
        if sel is not None:
            self._build_for(sel)
            self._resize_to_content()
            self._reposition()
            self.show()
            self.raise_()
        else:
            self.hide()

    # ── selection handling ──────────────────────────

    def _on_selection_changed(self, data):
        """
        Args:
            data (Any): Input data.
        """
        if data is None:
            self.hide()
            return
        self._build_for(data)
        self._resize_to_content()
        self._reposition()
        self.show()
        self.raise_()

    def _resize_to_content(self):
        """Force the inspector to shrink/grow to its form's sizeHint.

        Order matters: for widgets that live outside a parent layout (we are
        absolutely positioned over the plot), Qt will happily keep stale
        size hints. We walk: form.show → form.updateGeometry → outer
        invalidate+activate → self.updateGeometry → resize to hint.
        """
        if self._form is not None:
            self._form.show()
            self._form.updateGeometry()
        self._outer.invalidate()
        self._outer.activate()
        self.updateGeometry()
        hint = self.sizeHint()
        self.resize(self.FIXED_WIDTH, max(hint.height(), 40))

    # ── positioning ─────────────────────────────────

    def _reposition(self):
        if not self.isVisible() and self.mgr.get_selected_data() is None:
            return
        data = self.mgr.get_selected_data()
        if data is None:
            return
        pw, pi = self._plot_accessor()
        if pw is None or pi is None:
            return
        vb = pi.getViewBox()
        if vb is None:
            return

        x, y = _anchor_for(data, vb)
        try:
            scene_pt = vb.mapViewToScene(QPointF(x, y))
            widget_pt = pw.mapFromScene(scene_pt)
        except Exception:
            return

        gap_x = 24 if data.get('type') in ('vline', 'vband') else self.OFFSET_X
        gap_y = 24 if data.get('type') == 'hline' else self.OFFSET_Y

        anchor_widget_x = pw.x() + widget_pt.x()
        anchor_widget_y = pw.y() + widget_pt.y()

        local_x = anchor_widget_x + gap_x
        local_y = anchor_widget_y + gap_y

        parent = self.parentWidget()
        if parent is not None:
            margin = 6
            max_x = parent.width() - self.width() - margin
            max_y = parent.height() - self.height() - margin

            if local_x > max_x:
                local_x = anchor_widget_x - gap_x - self.width()
            local_x = max(margin, min(local_x, max(margin, max_x)))

            if local_y > max_y:
                local_y = anchor_widget_y - gap_y - self.height()
            local_y = max(margin, min(local_y, max(margin, max_y)))

        self.move(int(local_x), int(local_y))

    # ── form construction ───────────────────────────

    def _clear_form(self):
        if self._form is not None:
            self._outer.removeWidget(self._form)
            self._form.setParent(None)
            self._form.deleteLater()
            self._form = None
        self._editors.clear()
        self._swatches.clear()

    def _build_for(self, data: dict):
        """
        Args:
            data (dict): Input data.
        """
        self._clear_form()
        self._form = QWidget(self)
        form_lay = QVBoxLayout(self._form)
        form_lay.setContentsMargins(12, 10, 12, 10)
        form_lay.setSpacing(6)

        t = data.get('type')

        title = QLabel(self._title_for(data))
        title.setProperty("role", "type")
        form_lay.addWidget(title)

        if t == 'text':
            self._add_text_editor(form_lay, data, key='text',
                                   placeholder="Label…")
            self._add_arrow_fields(form_lay, data)
        elif t == 'vline':
            self._add_text_editor(form_lay, data, key='label',
                                   placeholder="Line label (optional)…")
            self._add_style_row(form_lay, data)
        elif t == 'hline':
            self._add_text_editor(form_lay, data, key='label',
                                   placeholder="Line label (optional)…")
            self._add_style_row(form_lay, data)
        elif t == 'vband':
            self._add_text_editor(form_lay, data, key='label',
                                   placeholder="Band label (optional)…")
            self._add_opacity_row(form_lay, data)
        elif t == 'rect':
            self._add_text_editor(form_lay, data, key='label',
                                   placeholder="Box label (optional)…")
            self._add_border_width_row(form_lay, data)

        form_lay.addWidget(self._build_color_row(data))

        del_row = QHBoxLayout()
        del_row.setContentsMargins(0, 2, 0, 0)
        del_row.addStretch(1)
        db = QPushButton("Delete")
        db.setObjectName("delete_btn")
        db.setCursor(Qt.PointingHandCursor)
        db.clicked.connect(self.mgr.remove_selected)
        del_row.addWidget(db)
        form_lay.addLayout(del_row)

        self._outer.addWidget(self._form)

    def _title_for(self, data: dict) -> str:
        """
        Args:
            data (dict): Input data.
        Returns:
            str: Result of the operation.
        """
        t = data.get('type')
        if t == 'text':
            return f"TEXT  ·  ({data.get('x', 0):.3g}, {data.get('y', 0):.3g})"
        if t == 'vline':
            return f"VERTICAL LINE  ·  x = {data.get('x', 0):.3g}"
        if t == 'hline':
            return f"HORIZONTAL LINE  ·  y = {data.get('y', 0):.3g}"
        if t == 'vband':
            return (f"SHADED BAND  ·  {data.get('x1', 0):.3g} → "
                    f"{data.get('x2', 0):.3g}")
        if t == 'rect':
            return "RECTANGLE"
        return str(t).upper()

    # ── field builders (compact) ────────────────────

    def _add_text_editor(self, layout, data, key: str, placeholder: str = ""):
        """
        Args:
            layout (Any): Target layout.
            data (Any): Input data.
            key (str): Dictionary or storage key.
            placeholder (str): The placeholder.
        """
        ed = QLineEdit(str(data.get(key, '')))
        ed.setPlaceholderText(placeholder)
        ed.editingFinished.connect(self._commit)
        self._editors[key] = (ed, 'text')
        layout.addWidget(ed)

    def _add_style_row(self, layout, data):
        """
        Args:
            layout (Any): Target layout.
            data (Any): Input data.
        """
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(QLabel("Style:"))
        cb = QComboBox()
        cb.addItems(['solid', 'dash', 'dot'])
        cur = data.get('style', 'dash')
        if cur in ['solid', 'dash', 'dot']:
            cb.setCurrentText(cur)
        cb.currentTextChanged.connect(lambda _: self._commit())
        self._editors['style'] = (cb, 'choice')
        row.addWidget(cb, 1)

        row.addWidget(QLabel("Width:"))
        sp = QSpinBox()
        sp.setRange(1, 10)
        sp.setValue(int(data.get('width', 2)))
        sp.setFixedWidth(52)
        sp.editingFinished.connect(self._commit)
        self._editors['width'] = (sp, 'int')
        row.addWidget(sp)

        layout.addLayout(row)

    def _add_opacity_row(self, layout, data):
        """
        Args:
            layout (Any): Target layout.
            data (Any): Input data.
        """
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(QLabel("Opacity:"))
        sp = QSpinBox()
        sp.setRange(0, 100)
        sp.setValue(int(float(data.get('alpha', 0.25)) * 100))
        sp.setSuffix(" %")
        sp.editingFinished.connect(self._commit)
        self._editors['alpha'] = (sp, 'alpha')
        row.addWidget(sp, 1)
        layout.addLayout(row)

    def _add_border_width_row(self, layout, data):
        """
        Args:
            layout (Any): Target layout.
            data (Any): Input data.
        """
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(QLabel("Border:"))
        sp = QSpinBox()
        sp.setRange(1, 10)
        sp.setValue(int(data.get('width', 2)))
        sp.editingFinished.connect(self._commit)
        self._editors['width'] = (sp, 'int')
        row.addWidget(sp, 1)
        layout.addLayout(row)

    def _add_arrow_fields(self, layout, data):
        """
        Args:
            layout (Any): Target layout.
            data (Any): Input data.
        """
        target = data.get('arrow_to')
        has_arrow = (target is not None and
                      isinstance(target, (list, tuple)) and len(target) == 2)

        wrapper = QWidget()
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(4)

        enable = QCheckBox("↘  point with an arrow")
        enable.setChecked(has_arrow)
        wl.addWidget(enable)

        xy_row = QHBoxLayout()
        xy_row.setSpacing(6)
        xy_row.addWidget(QLabel("→ x"))
        tx = QDoubleSpinBox()
        tx.setRange(-1e9, 1e9); tx.setDecimals(4); tx.setFixedWidth(70)
        if has_arrow:
            tx.setValue(float(target[0]))
        xy_row.addWidget(tx)
        xy_row.addWidget(QLabel("y"))
        ty = QDoubleSpinBox()
        ty.setRange(-1e9, 1e9); ty.setDecimals(4); ty.setFixedWidth(70)
        if has_arrow:
            ty.setValue(float(target[1]))
        xy_row.addWidget(ty)
        xy_row.addStretch(1)
        wl.addLayout(xy_row)

        tx.setEnabled(has_arrow); ty.setEnabled(has_arrow)

        def update_enabled():
            en = enable.isChecked()
            tx.setEnabled(en); ty.setEnabled(en)

        enable.stateChanged.connect(lambda _: (update_enabled(), self._commit()))
        tx.editingFinished.connect(self._commit)
        ty.editingFinished.connect(self._commit)
        self._editors['arrow_to'] = ((enable, tx, ty), 'arrow')

        layout.addWidget(wrapper)

    def _build_color_row(self, data) -> QWidget:
        """
        Args:
            data (Any): Input data.
        Returns:
            QWidget: Result of the operation.
        """
        current = data.get('color', DEFAULT_COLOR)
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(5)

        for hx in SwatchColors:
            sw = _ColorSwatch(hx, selected=(hx.lower() == current.lower()))
            sw.sig_picked.connect(self._on_swatch_picked)
            self._swatches.append(sw)
            row.addWidget(sw)

        custom = _CustomColorButton()
        custom.sig_picked.connect(self._on_swatch_picked)
        row.addWidget(custom)
        row.addStretch(1)
        return row_widget

    def _on_swatch_picked(self, hx: str):
        """
        Args:
            hx (str): The hx.
        """
        for sw in self._swatches:
            sw.set_selected(sw._hex.lower() == hx.lower())
        cur = self.mgr.get_selected_data()
        if cur is None:
            return
        new = copy.deepcopy(cur)
        new['color'] = hx
        self.mgr.update_selected(new)

    # ── commit from editors ─────────────────────────

    def _commit(self):
        cur = self.mgr.get_selected_data()
        if cur is None:
            return
        new = copy.deepcopy(cur)
        for key, (widget, kind) in self._editors.items():
            if kind == 'text':
                new[key] = widget.text()
            elif kind == 'int':
                new[key] = int(widget.value())
            elif kind == 'float':
                new[key] = float(widget.value())
            elif kind == 'bool':
                new[key] = bool(widget.isChecked())
            elif kind == 'choice':
                new[key] = widget.currentText()
            elif kind == 'alpha':
                new[key] = float(widget.value()) / 100.0
            elif kind == 'arrow':
                enable_w, tx_w, ty_w = widget
                if enable_w.isChecked():
                    new['arrow_to'] = [float(tx_w.value()), float(ty_w.value())]
                else:
                    new['arrow_to'] = None
        if new != cur:
            self.mgr.update_selected(new)


# ──────────────────────────────────────────────────────────────────────
# AnnotationShelfButton
# ──────────────────────────────────────────────────────────────────────

class AnnotationShelfButton(QPushButton):
    """
    A small pill showing "≡ N annotations". Clicking opens a popup menu
    with each annotation (select, toggle visible, delete) and a "clear all".
    """

    def __init__(self, mgr: 'AnnotationManager', parent=None):
        """
        Args:
            mgr ('AnnotationManager'): The mgr.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.mgr = mgr
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet("""
            QPushButton {
                background: rgba(0,0,0,0.04);
                border: 1px solid rgba(0,0,0,0.12);
                border-radius: 12px;
                padding: 3px 11px;
                color: #555;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(0,0,0,0.08);
                color: #222;
            }
        """)
        self.clicked.connect(self._show_menu)
        self.mgr.sig_annotations_changed.connect(self._refresh)
        self._refresh()

    def _refresh(self):
        n = len(self.mgr.get_all_data())
        self.setText(f"≡  {n} annotation{'' if n == 1 else 's'}")
        self.setVisible(True)

    def _summarize(self, d: dict) -> str:
        """
        Args:
            d (dict): The d.
        Returns:
            str: Result of the operation.
        """
        t = d.get('type')
        if t == 'text':
            tx = d.get('text', '')
            return f"T · {tx[:22] + '…' if len(tx) > 22 else tx}" if tx else "T · (empty)"
        if t == 'vline':
            lab = d.get('label', '')
            return f"│ · x = {d.get('x', 0):.3g}" + (f"  ({lab})" if lab else "")
        if t == 'hline':
            lab = d.get('label', '')
            return f"— · y = {d.get('y', 0):.3g}" + (f"  ({lab})" if lab else "")
        if t == 'vband':
            return f"▥ · [{d.get('x1', 0):.3g}, {d.get('x2', 0):.3g}]"
        if t == 'rect':
            return f"▭ · box"
        return str(t)

    def _show_menu(self):
        menu = QMenu(self)
        data_list = self.mgr.get_all_data()

        if not data_list:
            a =  menu.addAction("No annotations yet — right-click the plot")
            a.setEnabled(False)
        else:
            for d in data_list:
                label = self._summarize(d)
                act = menu.addAction(label)
                ann_id = d['id']
                act.triggered.connect(
                    lambda _=False, aid=ann_id: self.mgr.select(aid))
            menu.addSeparator()
            clear_act = menu.addAction("Clear all annotations")
            clear_act.triggered.connect(self._clear_all)

        pt = self.mapToGlobal(self.rect().topLeft())
        menu.exec(pt)

    def _clear_all(self):
        data_list = list(self.mgr.get_all_data())
        for d in reversed(data_list):
            self.mgr.select(d['id'])
            self.mgr.remove_selected()
        self.mgr.select(None)


# ──────────────────────────────────────────────────────────────────────
# Keyboard shortcuts helper
# ──────────────────────────────────────────────────────────────────────

def install_annotation_shortcuts(widget: QWidget, mgr: AnnotationManager):
    """Install Del / Ctrl+Z / Ctrl+Shift+Z / Esc shortcuts on a dialog.
    Args:
        widget (QWidget): Target widget.
        mgr (AnnotationManager): The mgr.
    Returns:
        object: Result of the operation.
    """
    def _sc(seq: str, slot):
        """
        Args:
            seq (str): The seq.
            slot (Any): The slot.
        Returns:
            object: Result of the operation.
        """
        s = QShortcut(QKeySequence(seq), widget)
        s.activated.connect(slot)
        return s

    _sc("Delete",       mgr.remove_selected)
    _sc("Backspace",    mgr.remove_selected)
    _sc("Ctrl+Z",       mgr.undo_stack.undo)
    _sc("Ctrl+Shift+Z", mgr.undo_stack.redo)
    _sc("Ctrl+Y",       mgr.undo_stack.redo)
    _sc("Escape",       lambda: (mgr.cancel_insert(), mgr.select(None)))