"""Draggable, resizable, collapsible panels that float over the plot.

A box is a plain child widget of the plot container, moved with ``move()`` and
sized with ``resize()`` rather than laid out — that is what "floating" means
here. Positions are clamped to the parent so a box can never be dragged fully
out of reach.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSizePolicy,
                               QToolButton, QVBoxLayout, QWidget)

from .state import THEME

_HEAD_H = 22
_GRIP = 14


def _c(spec):
    """Return a ``QColor`` from a palette string.

    ``THEME`` holds colour *strings*; ``QPen(str, width)`` is not a valid
    overload, so every colour must be wrapped before it reaches a pen or brush.

    Args:
        spec (str): A ``#RRGGBB`` colour.

    Returns:
        QColor: The colour, falling back to grey when unparseable.
    """
    col = QColor(spec)
    return col if col.isValid() else QColor('#888888')


class _Grip(QWidget):
    """Bottom-right resize handle."""

    def __init__(self, box):
        """Attach the grip to a box and give it the diagonal resize cursor.

        Args:
            box (FloatBox): The box this grip resizes.
        """
        super().__init__(box)
        self._box = box
        self.setFixedSize(_GRIP, _GRIP)
        self.setCursor(Qt.SizeFDiagCursor)
        self._from = None

    def mousePressEvent(self, ev):
        """Record the size and pointer position the drag starts from.

        Args:
            ev (QMouseEvent): The press event.
        """
        if ev.button() == Qt.LeftButton:
            self._from = (ev.globalPosition().toPoint(),
                          self._box.width(), self._box.height())
            ev.accept()

    def mouseMoveEvent(self, ev):
        """Resize the box to follow the pointer, honouring the minimum size.

        Args:
            ev (QMouseEvent): The move event.
        """
        if self._from is None:
            return
        start, w0, h0 = self._from
        d = ev.globalPosition().toPoint() - start
        self._box.resize(max(180, w0 + d.x()), max(90, h0 + d.y()))
        self._box.clamp()

    def mouseReleaseEvent(self, _ev):
        """End the resize drag.

        Args:
            _ev (QMouseEvent): Unused.
        """
        self._from = None

    def paintEvent(self, _ev):
        """Draw the three diagonal ridges of the grip.

        The painter is ended in a ``finally``: letting an exception escape
        ``paintEvent`` with it still active makes Qt segfault rather than
        raise.

        Args:
            _ev (QPaintEvent): Unused.
        """
        p = QPainter(self)
        try:
            p.setPen(QPen(_c(THEME.muted), 1))
            for off in (3, 7, 11):
                p.drawLine(_GRIP - off, _GRIP - 2, _GRIP - 2, _GRIP - off)
        finally:
            p.end()


class _Header(QFrame):
    """Drag strip carrying the title and the collapse caret."""

    def __init__(self, box, title):
        """Build the drag strip.

        Args:
            box (FloatBox): The box this header moves.
            title (str): Initial title text.
        """
        super().__init__(box)
        self._box = box
        self._from = None
        self.setFixedHeight(_HEAD_H)
        self.setCursor(Qt.OpenHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 4, 0)
        lay.setSpacing(6)
        self.title = QLabel(title)
        lay.addWidget(self.title, 1)

        self.caret = QToolButton()
        self.caret.setText('▾')
        self.caret.setAutoRaise(True)
        self.caret.setFixedSize(16, 16)
        self.caret.setToolTip('Collapse')
        self.caret.clicked.connect(box.toggle_collapsed)
        lay.addWidget(self.caret)

    def mousePressEvent(self, ev):
        """Begin a move drag and raise the box above its siblings.

        Args:
            ev (QMouseEvent): The press event.
        """
        if ev.button() == Qt.LeftButton:
            self._from = (ev.globalPosition().toPoint(), self._box.pos())
            self.setCursor(Qt.ClosedHandCursor)
            self._box.raise_()
            ev.accept()

    def mouseMoveEvent(self, ev):
        """Move the box to follow the pointer, then clamp it to the parent.

        Args:
            ev (QMouseEvent): The move event.
        """
        if self._from is None:
            return
        start, origin = self._from
        d = ev.globalPosition().toPoint() - start
        self._box.move(origin + d)
        self._box.clamp()

    def mouseReleaseEvent(self, _ev):
        """End the move drag and restore the open-hand cursor.

        Args:
            _ev (QMouseEvent): Unused.
        """
        self._from = None
        self.setCursor(Qt.OpenHandCursor)


class FloatBox(QFrame):
    """A titled panel that floats over the plot, movable and resizable.

    The box remembers the geometry it was first given so :meth:`reset` can
    restore it, which is what the settings dialog's 'Reset size & position'
    does.
    """

    collapsed_changed = Signal(bool)

    def __init__(self, title, content, parent=None, subtitle=False):
        """Wrap a widget in a floating, titled frame.

        Args:
            title (str): Header text.
            content (QWidget): Widget to host; it is reparented into the body.
            parent (QWidget | None): The container the box floats over.
            subtitle (bool): Add a subtitle line under the header.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._default = None
        self._collapsed = False
        self._expanded_h = 200

        lay = QVBoxLayout(self)
        lay.setContentsMargins(1, 1, 1, 1)
        lay.setSpacing(0)

        self.header = _Header(self, title)
        lay.addWidget(self.header)

        self.sub = QLabel('') if subtitle else None
        if self.sub is not None:
            self.sub.setContentsMargins(8, 0, 8, 2)
            self.sub.setWordWrap(True)
            lay.addWidget(self.sub)

        self.content = content
        content.setParent(self)
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(content, 1)

        self.grip = _Grip(self)
        self.apply_theme()

    def set_default_geometry(self, x, y, w, h):
        """Record and apply the geometry :meth:`reset` returns to.

        Args:
            x (int): Left edge within the parent.
            y (int): Top edge within the parent.
            w (int): Width.
            h (int): Height.
        """
        self._default = QRect(int(x), int(y), int(w), int(h))
        self.setGeometry(self._default)

    def reset(self):
        """Restore the default size and position, expanding if collapsed."""
        if self._default is not None:
            self.setGeometry(self._default)
            if self._collapsed:
                self.toggle_collapsed()
        self.clamp()

    def clamp(self):
        """Keep the box inside its parent, leaving the header reachable."""
        par = self.parentWidget()
        if par is None:
            return
        pw, ph = par.width(), par.height()
        w = min(self.width(), max(180, pw - 8))
        h = min(self.height(), max(_HEAD_H + 8, ph - 8))
        if (w, h) != (self.width(), self.height()):
            self.resize(w, h)
        x = min(max(4, self.x()), max(4, pw - w - 4))
        y = min(max(4, self.y()), max(4, ph - _HEAD_H - 4))
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)
        self.grip.move(w - _GRIP - 2, h - _GRIP - 2)

    def resizeEvent(self, ev):
        """Keep the grip pinned to the bottom-right corner.

        Args:
            ev (QResizeEvent): The resize event.
        """
        super().resizeEvent(ev)
        self.grip.move(self.width() - _GRIP - 2, self.height() - _GRIP - 2)
        self.grip.raise_()

    def toggle_collapsed(self):
        """Fold the body away, leaving only the header, or restore it."""
        self._collapsed = not self._collapsed
        self.content.setVisible(not self._collapsed)
        if self.sub is not None:
            self.sub.setVisible(not self._collapsed)
        self.grip.setVisible(not self._collapsed)
        self.header.caret.setText('▴' if self._collapsed else '▾')
        self.header.caret.setToolTip('Expand' if self._collapsed else 'Collapse')
        if self._collapsed:
            self._expanded_h = self.height()
            self.resize(self.width(), _HEAD_H + 4)
        else:
            self.resize(self.width(), self._expanded_h)
        self.collapsed_changed.emit(self._collapsed)

    @property
    def collapsed(self):
        """bool: True while the body is folded away."""
        return self._collapsed

    def set_title(self, text):
        """Set the header text.

        Args:
            text (str): New title.
        """
        self.header.title.setText(text)

    def set_subtitle(self, text):
        """Set the subtitle text, if this box was built with one.

        Args:
            text (str): New subtitle.
        """
        if self.sub is not None:
            self.sub.setText(text)

    def apply_theme(self):
        """Re-read the palette. Must be called on every dark/light switch."""
        self.setStyleSheet(
            'FloatBox{background:%s;border:1px solid %s;border-radius:8px;}'
            % (THEME.panel, THEME.stroke))
        self.header.setStyleSheet(
            '_Header{background:%s;border-top-left-radius:7px;'
            'border-top-right-radius:7px;border-bottom:1px solid %s;}'
            'QLabel{color:%s;font-weight:600;font-size:11px;}'
            'QToolButton{color:%s;border:none;}'
            % (THEME.chip, THEME.stroke, THEME.text, THEME.muted))
        if self.sub is not None:
            self.sub.setStyleSheet('color:%s;font-size:10px;' % THEME.muted)
        self.grip.update()
        fn = getattr(self.content, 'apply_theme', None)
        if callable(fn):
            try:
                fn()
            except Exception:
                pass
