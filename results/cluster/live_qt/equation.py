"""The worked-example box, typeset with LaTeX.

Expressions are rendered by matplotlib's mathtext, which is already a
dependency, ships its own fonts and needs no network. mathtext returns a
greyscale coverage mask, so glyphs are tinted to the theme's text colour
rather than baked in — a dark/light switch costs a re-tint, not a re-parse.

Rendering is cached on ``(latex, size, colour, ratio)``, so a repeated
expression or a repaint after a resize costs a dictionary lookup.
"""

from __future__ import annotations

import logging
from html import escape

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from .state import THEME

_log = logging.getLogger("IsotopeTrack.results.cluster.live_qt.equation")

_CACHE = {}
_PARSER = None


def _parser():
    """Return the shared mathtext parser, or None when matplotlib is absent.

    Imported lazily so opening the application does not pay for matplotlib in
    a session that never shows a worked example.

    Returns:
        matplotlib.mathtext.MathTextParser | None: The parser, or None.
    """
    global _PARSER
    if _PARSER is None:
        try:
            from matplotlib.mathtext import MathTextParser
            _PARSER = MathTextParser('agg')
        except Exception:
            _log.exception("mathtext unavailable; equations fall back to text")
            _PARSER = False
    return _PARSER or None


def render_math(latex, size, color, ratio=2.0):
    """Typeset a LaTeX fragment into a tinted pixmap.

    Args:
        latex (str): LaTeX source without surrounding ``$``.
        size (float): Font size in logical pixels.
        color (str): Glyph colour as ``#RRGGBB``.
        ratio (float): Device pixel ratio to render at.

    Returns:
        QPixmap | None: The typeset fragment, or None when it could not be
        parsed, in which case the caller shows the source as plain text.
    """
    src = str(latex or '').strip()
    if not src:
        return None
    key = (src, round(size, 2), color, ratio)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit

    parser = _parser()
    if parser is None:
        return None
    try:
        from matplotlib.font_manager import FontProperties
        prop = FontProperties(size=size)
        parse = parser.parse('$%s$' % src, dpi=72 * ratio, prop=prop)
        mask = np.asarray(parse.image)
    except Exception:
        _log.debug("mathtext could not parse %r", src)
        return None

    h, w = mask.shape
    rgb = QColor(color)
    if not rgb.isValid():
        rgb = QColor('#000000')
    argb = np.empty((h, w, 4), dtype=np.uint8)
    argb[..., 0] = rgb.blue()
    argb[..., 1] = rgb.green()
    argb[..., 2] = rgb.red()
    argb[..., 3] = mask
    img = QImage(argb.tobytes(), w, h, 4 * w, QImage.Format_ARGB32)
    pm = QPixmap.fromImage(img.copy())
    pm.setDevicePixelRatio(ratio)
    _CACHE[key] = pm
    return pm


def clear_cache():
    """Drop every cached pixmap, so a theme change re-tints the glyphs."""
    _CACHE.clear()


def _strip_latex(src):
    """Return a readable plain-text fallback for an expression.

    Used when matplotlib is unavailable or an expression fails to parse, so a
    worked example degrades to something legible rather than vanishing.

    Args:
        src (str): LaTeX source.

    Returns:
        str: The source with the most common markup removed.
    """
    import re
    s = str(src or '')
    s = re.sub(r'\\(left|right|,|;|!|quad|qquad)', '', s)
    s = re.sub(r'\\[a-zA-Z]+', lambda m: m.group(0)[1:], s)
    return s.replace('{', '').replace('}', '').replace('$', '')


class MathLabel(QLabel):
    """A label showing one typeset expression, scaled down to fit its width.

    Shrinking the pixmap rather than clipping it means a box dragged small
    stays readable.
    """

    def __init__(self, parent=None):
        """Create an empty math label.

        Args:
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self._pm = None
        self._last_w = -1
        self._rescaling = False
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

    def set_math(self, latex, size, color):
        """Typeset an expression and show it, falling back to plain text.

        Args:
            latex (str): LaTeX source without surrounding ``$``.
            size (float): Font size in logical pixels.
            color (str): Glyph colour as ``#RRGGBB``.
        """
        pm = render_math(latex, size, color, self.devicePixelRatioF() or 2.0)
        self._pm = pm
        self._last_w = -1
        if pm is None:
            self.setText(_strip_latex(latex))
            self.setFixedHeight(int(size * 1.6))
            return
        self.setText('')
        self._rescale()

    def _rescale(self):
        """Scale the pixmap down when it is wider than the available width.

        Guarded against re-entry. ``setFixedHeight`` resizes the widget, which
        delivers another resize event, which would call back into here — an
        unbounded recursion that overflows the stack and crashes the process
        rather than raising. The flag plus the width check in
        :meth:`resizeEvent` break the cycle.
        """
        pm = self._pm
        if pm is None or self._rescaling:
            return
        self._rescaling = True
        try:
            ratio = pm.devicePixelRatio() or 1.0
            avail = max(20, self.width())
            native = pm.width() / ratio
            if native > avail:
                scaled = pm.scaledToWidth(int(avail * ratio),
                                          Qt.SmoothTransformation)
                scaled.setDevicePixelRatio(ratio)
                shown = scaled
            else:
                shown = pm
            super().setPixmap(shown)
            want = int(shown.height() / (shown.devicePixelRatio() or 1.0)) + 2
            if want != self.height():
                self.setFixedHeight(want)
        finally:
            self._rescaling = False

    def resizeEvent(self, ev):
        """Re-fit the pixmap when the label width changes.

        Height changes are ignored on purpose: this widget *sets* its own
        height, so reacting to a height change would chase its own tail.

        Args:
            ev (QResizeEvent): The resize event.
        """
        super().resizeEvent(ev)
        w = ev.size().width()
        if w == self._last_w or self._rescaling:
            return
        self._last_w = w
        self._rescale()


class MixedRow(QWidget):
    """A line of prose with inline ``$…$`` maths spans.

    The engine writes substitution rows as mixed text, e.g.
    ``nearest of $4$ centroids``. Each span is laid out side by side: prose as
    a plain label, maths as a :class:`MathLabel`, so the ``$`` delimiters never
    reach the screen.
    """

    def __init__(self, src, size, color, align_right=False, bold=False,
                 parent=None):
        """Build the row from a mixed string.

        Args:
            src (str): Text with optional ``$…$`` maths spans.
            size (float): Font size in logical pixels.
            color (str): Text and glyph colour as ``#RRGGBB``.
            align_right (bool): Push the content to the right.
            bold (bool): Draw the prose parts bold.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        if align_right:
            lay.addStretch(1)
        for i, part in enumerate(str(src or '').split('$')):
            if not part:
                continue
            if i % 2:
                m = MathLabel()
                m.set_math(part, size, color)
                m.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
                lay.addWidget(m)
            else:
                l = QLabel(escape(part))
                l.setWordWrap(False)
                if bold:
                    l.setStyleSheet('font-weight:600;')
                lay.addWidget(l)
        if not align_right:
            lay.addStretch(1)


class EquationBox(QWidget):
    """The worked example: formula, substituted rows, result and note.

    The body is rebuilt only when the content actually changes, because
    re-typesetting on every redraw is measurable. The whole body sits
    in a scroll area, so shrinking the floating box scrolls rather than clips.
    """

    title_changed = Signal(str, str)
    availability_changed = Signal(bool)

    def __init__(self, S, parent=None):
        """Build the scrollable worked-example body.

        Args:
            S (LiveState): The view state, for ``eq_on`` and the font size.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.S = S
        self._key = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        outer.addWidget(self.scroll)

        self.body = QWidget()
        self.scroll.setWidget(self.body)
        self.grid = QGridLayout(self.body)
        self.grid.setContentsMargins(9, 6, 9, 9)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(4)
        self.grid.setColumnStretch(1, 1)

        self.apply_theme()

    def apply_theme(self):
        """Re-tint the glyphs and restyle the text for the active palette."""
        clear_cache()
        self.setStyleSheet(
            'QWidget{background:transparent;color:%(text)s;}'
            'QLabel#eqSub{color:%(muted)s;font-size:11px;}'
            'QLabel#eqNote{color:%(muted)s;font-size:10px;}'
            'QScrollBar:vertical{background:transparent;width:8px;margin:0;}'
            'QScrollBar::handle:vertical{background:%(stroke2)s;'
            'border-radius:4px;min-height:24px;}'
            'QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{'
            'height:0;}'
            % {'text': THEME.text, 'muted': THEME.muted,
               'stroke2': THEME.stroke2})
        self._key = None

    def invalidate(self):
        """Force the body to be re-typeset on the next frame.

        The cache key includes the colour and font size, but the pixmap cache
        is keyed separately, so both are cleared when the appearance changes.
        """
        clear_cache()
        self._key = None

    def _clear(self):
        """Remove every widget from the body grid."""
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _math(self, latex, size=None):
        """Build a typeset label for an expression.

        Args:
            latex (str): LaTeX source.
            size (float | None): Font size, defaulting to the appearance size.

        Returns:
            MathLabel: The typeset label.
        """
        lbl = MathLabel()
        lbl.set_math(latex, size or (self.S.ui.font_size * 0.82), THEME.text)
        return lbl

    def _text(self, s, name=None):
        """Build a wrapped plain-text label.

        Args:
            s (str): Text to show.
            name (str | None): Object name, for the stylesheet.

        Returns:
            QLabel: The label.
        """
        lbl = QLabel(escape(str(s or '')))
        lbl.setWordWrap(True)
        if name:
            lbl.setObjectName(name)
        return lbl

    def set_frame(self, frame):
        """Render the equation carried by a frame, or report it has none.

        Args:
            frame (dict | None): The frame currently on screen.
        """
        d = ((frame or {}).get('extra') or {}).get('equation')
        available = bool(d) and self.S.eq_on
        self.availability_changed.emit(available)
        if not available:
            return
        self.title_changed.emit(d.get('title') or 'Worked example', '')

        key = repr([d.get('title'), d.get('formula'), d.get('lines'),
                    d.get('result'), d.get('note'), THEME.text,
                    self.S.ui.font_size])
        if key == self._key:
            return
        self._key = key

        self._clear()
        row = 0
        if d.get('formula'):
            f = self._math(d['formula'], self.S.ui.font_size * 0.95)
            self.grid.addWidget(f, row, 0, 1, 3)
            row += 1

        size = self.S.ui.font_size * 0.82
        for line in (d.get('lines') or []):
            lhs = line[0] if len(line) > 0 else ''
            sub = line[1] if len(line) > 1 else ''
            val = line[2] if len(line) > 2 else ''
            self.grid.addWidget(self._math(lhs), row, 0)
            s = MixedRow(sub, size, THEME.muted)
            s.setObjectName('eqSub')
            self.grid.addWidget(s, row, 1)
            self.grid.addWidget(
                MixedRow(val, size, THEME.text, align_right=True), row, 2)
            row += 1

        result = d.get('result')
        if result:
            self.grid.addWidget(MixedRow(result[0], size, THEME.text),
                                row, 0, 1, 2)
            self.grid.addWidget(
                MixedRow(result[1], size, THEME.text, align_right=True,
                         bold=True), row, 2)
            row += 1

        if d.get('note'):
            self.grid.addWidget(self._text(d['note'], 'eqNote'), row, 0, 1, 3)
            row += 1

        self.grid.setRowStretch(row, 1)
