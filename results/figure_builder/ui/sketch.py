"""Layout sketch pad: the page where the user draws the figure's panels.

The user drags on empty paper to draw a panel rectangle (Shift-drag draws
on top of an existing panel, e.g. for an inset), drags a panel to move it,
drags its lower-right corner to resize it and presses Delete to remove it. Rectangles are stored as fractions of the page (origin
top-left), so the same layout scales to any final figure size.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import QMenu, QSizePolicy, QWidget

from results.figure_builder.core import engine as E

_SNAP = 1.0 / 48.0
_MIN = 0.06
_HANDLE = 10.0

KIND_GLYPHS = {
    'scatter': '⁘', 'line': '⟋', 'histogram': '▁▃▆', 'box': '⊟', 'violin': '◊', 'bar': '▌▌',
    'pie': '◔', 'density': '▦', 'ternary': '△', 'text': 'T', 'code': '</>',
    'corr_matrix': '▚', 'heatmap': '▦', 'cooccurrence': '◫', 'combinations': '☰',
    'composition': '▤', 'pairs': '⊞', 'strip': '⁞', 'ridgeline': '≋', 'hexbin': '⬢',
    'contour': '◎', 'radar': '✳', 'parallel': '⫴', 'ecdf': '⌐', 'qq': '⋰', 'upset': '⁝▌',
    'lollipop': '⊸', 'waffle': '▩', 'treemap': '▣', 'timeline': '⏱',
}


def _theme_colors():
    """Pick sketch colours from the application theme, with fallbacks."""
    try:
        from tools.theme import theme
        p = theme.palette
        return {
            'bg': p.bg_tertiary, 'paper': '#ffffff', 'grid': '#e6e9ef',
            'accent': p.accent, 'text': '#1f2937', 'muted': '#6b7280',
            'border': p.border_strong, 'danger': p.danger,
        }
    except Exception:
        return {'bg': '#eef1f5', 'paper': '#ffffff', 'grid': '#e6e9ef',
                'accent': '#2a78d6', 'text': '#1f2937', 'muted': '#6b7280',
                'border': '#9aa4b2', 'danger': '#d32f2f'}


def _snap(v: float) -> float:
    """Snap a page fraction to the sketch grid."""
    return round(v / _SNAP) * _SNAP


class LayoutSketch(QWidget):
    """Interactive page on which panels are drawn, moved and resized.

    Signals:
        selection_changed(str): id of the selected panel, '' for none.
        layout_changed(): a panel was added, moved, resized or removed.
        kind_requested(str, str): context-menu request to set a panel kind.
    """

    selection_changed = Signal(str)
    layout_changed = Signal()
    kind_requested = Signal(str, str)

    def __init__(self, spec: dict, parent=None):
        super().__init__(parent)
        self.spec = spec
        self.selected = ''
        self._mode = None
        self._press = QPointF()
        self._orig = None
        self._draft = None
        self._anchor = (0.0, 0.0)
        self.errors: dict = {}
        self.panel_factory = E.make_panel
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_spec(self, spec: dict):
        """Point the sketch at a (new) spec and repaint."""
        self.spec = spec
        ids = {p['id'] for p in spec.get('panels', [])}
        if self.selected not in ids:
            self.selected = ''
        self.update()

    def page_rect(self) -> QRectF:
        """The paper rectangle in widget pixels, keeping the figure aspect."""
        fig = self.spec.get('figure', {})
        aspect = float(fig.get('width', 8)) / max(0.1, float(fig.get('height', 6)))
        m = 14.0
        w, h = self.width() - 2 * m, self.height() - 2 * m
        if w / max(1.0, h) > aspect:
            pw, ph = h * aspect, h
        else:
            pw, ph = w, w / aspect
        return QRectF((self.width() - pw) / 2, (self.height() - ph) / 2, pw, ph)

    def _to_px(self, rect) -> QRectF:
        page = self.page_rect()
        x, y, w, h = rect
        return QRectF(page.x() + x * page.width(), page.y() + y * page.height(),
                      w * page.width(), h * page.height())

    def _to_frac(self, pt: QPointF) -> tuple[float, float]:
        page = self.page_rect()
        fx = (pt.x() - page.x()) / max(1.0, page.width())
        fy = (pt.y() - page.y()) / max(1.0, page.height())
        return min(1.0, max(0.0, fx)), min(1.0, max(0.0, fy))

    def _panel(self, pid: str):
        for p in self.spec.get('panels', []):
            if p['id'] == pid:
                return p
        return None

    def _hit(self, pt: QPointF):
        """Return ``(panel, part)`` under ``pt``; part is 'resize' or 'move'."""
        for p in reversed(self.spec.get('panels', [])):
            r = self._to_px(p['rect'])
            corner = QRectF(r.right() - _HANDLE, r.bottom() - _HANDLE, _HANDLE * 1.6, _HANDLE * 1.6)
            if corner.contains(pt):
                return p, 'resize'
            if r.contains(pt):
                return p, 'move'
        return None, None

    def select(self, pid: str):
        """Select a panel by id and notify listeners."""
        if pid != self.selected:
            self.selected = pid
            self.selection_changed.emit(pid)
        self.update()

    def paintEvent(self, _event):
        c = _theme_colors()
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        qp.fillRect(self.rect(), QColor(c['bg']))
        page = self.page_rect()
        qp.setPen(QPen(QColor(c['border']), 1))
        qp.setBrush(QColor(c['paper']))
        qp.drawRect(page)
        qp.setPen(QPen(QColor(c['grid']), 1))
        for i in range(1, 12):
            x = page.x() + page.width() * i / 12
            y = page.y() + page.height() * i / 12
            qp.drawPoint(QPointF(x, page.y() + 2))
            for j in range(1, 12):
                qp.drawPoint(QPointF(x, page.y() + page.height() * j / 12))
            qp.drawPoint(QPointF(page.x() + 2, y))
        letters = self.spec.get('figure', {}).get('letter_style', 'a')
        for i, p in enumerate(self.spec.get('panels', [])):
            r = self._to_px(p['rect']).adjusted(2, 2, -2, -2)
            sel = p['id'] == self.selected
            err = p['id'] in self.errors
            accent = QColor(c['accent'])
            fill = QColor(accent)
            fill.setAlpha(46 if sel else 22)
            edge = QColor(c['danger']) if err else (accent if sel else QColor(c['border']))
            qp.setBrush(QBrush(QColor('#ffffff')))
            qp.setPen(Qt.NoPen)
            qp.drawRoundedRect(r, 6, 6)
            qp.setBrush(QBrush(fill))
            qp.setPen(QPen(edge, 2.2 if sel else 1.2, Qt.SolidLine if sel else Qt.DashLine))
            qp.drawRoundedRect(r, 6, 6)
            f = QFont(self.font())
            f.setBold(True)
            f.setPointSizeF(max(8.0, min(16.0, r.height() / 5)))
            qp.setFont(f)
            qp.setPen(QColor(c['text']))
            glyph = KIND_GLYPHS.get(p.get('kind'), '?')
            qp.drawText(r, Qt.AlignCenter, glyph)
            f2 = QFont(self.font())
            f2.setPointSizeF(8.5)
            qp.setFont(f2)
            qp.setPen(QColor(c['muted']))
            name = E.PANEL_KINDS.get(p.get('kind'), p.get('kind', ''))
            if r.height() > 46:
                qp.drawText(r.adjusted(4, 0, -4, -4), Qt.AlignHCenter | Qt.AlignBottom, name)
            f3 = QFont(self.font())
            f3.setBold(True)
            qp.setFont(f3)
            qp.setPen(QColor(c['text']))
            qp.drawText(r.adjusted(6, 4, 0, 0), Qt.AlignLeft | Qt.AlignTop,
                        E.panel_letter(i, letters))
            if sel:
                h = QRectF(r.right() - _HANDLE + 2, r.bottom() - _HANDLE + 2, _HANDLE, _HANDLE)
                qp.setBrush(accent)
                qp.setPen(Qt.NoPen)
                qp.drawRect(h)
        if self._draft is not None:
            pen = QPen(QColor(c['accent']), 1.6, Qt.DashLine)
            qp.setPen(pen)
            fill = QColor(c['accent'])
            fill.setAlpha(30)
            qp.setBrush(fill)
            qp.drawRoundedRect(self._to_px(self._draft), 6, 6)
        if not self.spec.get('panels'):
            qp.setPen(QColor(c['muted']))
            qp.drawText(page, Qt.AlignCenter, 'Drag on the page to draw a panel')
        qp.end()

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return super().mousePressEvent(ev)
        self.setFocus()
        pt = ev.position()
        panel, part = self._hit(pt)
        self._press = pt
        if ev.modifiers() & Qt.ShiftModifier:
            panel = None
        if panel is None:
            if self.page_rect().contains(pt):
                self._mode = 'draw'
                fx, fy = self._to_frac(pt)
                self._anchor = (_snap(fx), _snap(fy))
                self._draft = [self._anchor[0], self._anchor[1], 0.0, 0.0]
                self.select('')
            return
        self.select(panel['id'])
        self._mode = part
        self._orig = list(panel['rect'])

    def mouseMoveEvent(self, ev):
        pt = ev.position()
        if self._mode is None:
            _, part = self._hit(pt)
            self.setCursor(Qt.SizeFDiagCursor if part == 'resize'
                           else Qt.OpenHandCursor if part == 'move' else Qt.CrossCursor)
            return
        page = self.page_rect()
        dx = (pt.x() - self._press.x()) / max(1.0, page.width())
        dy = (pt.y() - self._press.y()) / max(1.0, page.height())
        if self._mode == 'draw':
            x0, y0 = self._anchor
            fx, fy = self._to_frac(pt)
            fx, fy = _snap(fx), _snap(fy)
            self._draft = [min(x0, fx), min(y0, fy), abs(fx - x0), abs(fy - y0)]
            self.update()
            return
        panel = self._panel(self.selected)
        if panel is None:
            return
        x, y, w, h = self._orig
        if self._mode == 'move':
            nx = min(1.0 - w, max(0.0, _snap(x + dx)))
            ny = min(1.0 - h, max(0.0, _snap(y + dy)))
            panel['rect'] = [nx, ny, w, h]
        else:
            nw = min(1.0 - x, max(_MIN, _snap(w + dx)))
            nh = min(1.0 - y, max(_MIN, _snap(h + dy)))
            panel['rect'] = [x, y, nw, nh]
        self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return super().mouseReleaseEvent(ev)
        mode, self._mode = self._mode, None
        if mode == 'draw':
            d, self._draft = self._draft, None
            if d and d[2] >= _MIN and d[3] >= _MIN:
                panel = self.panel_factory(rect=[round(v, 4) for v in d])
                self.spec.setdefault('panels', []).append(panel)
                self.select(panel['id'])
                self.layout_changed.emit()
            self.update()
            return
        if mode in ('move', 'resize'):
            panel = self._panel(self.selected)
            if panel is not None and panel['rect'] != self._orig:
                self.layout_changed.emit()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.selected:
            self.delete_selected()
            return
        arrows = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}
        panel = self._panel(self.selected)
        if ev.key() in arrows and panel is not None:
            dx, dy = arrows[ev.key()]
            x, y, w, h = panel['rect']
            if ev.modifiers() & Qt.ShiftModifier:
                w = min(1.0 - x, max(_MIN, w + dx * _SNAP))
                h = min(1.0 - y, max(_MIN, h + dy * _SNAP))
            else:
                x = min(1.0 - w, max(0.0, x + dx * _SNAP))
                y = min(1.0 - h, max(0.0, y + dy * _SNAP))
            panel['rect'] = [round(x, 4), round(y, 4), round(w, 4), round(h, 4)]
            self.update()
            self.layout_changed.emit()
            return
        super().keyPressEvent(ev)

    def duplicate_selected(self):
        """Duplicate the selected panel, slightly offset."""
        panel = self._panel(self.selected)
        if panel is not None:
            self._duplicate(panel)

    def delete_selected(self):
        """Remove the selected panel."""
        panels = self.spec.get('panels', [])
        self.spec['panels'] = [p for p in panels if p['id'] != self.selected]
        self.select('')
        self.layout_changed.emit()

    def _duplicate(self, panel):
        import copy
        dup = copy.deepcopy(panel)
        dup['id'] = E.new_panel_id()
        x, y, w, h = dup['rect']
        dup['rect'] = [min(1 - w, x + 0.04), min(1 - h, y + 0.04), w, h]
        self.spec['panels'].append(dup)
        self.select(dup['id'])
        self.layout_changed.emit()

    def _restack(self, panel, front: bool):
        panels = [p for p in self.spec['panels'] if p['id'] != panel['id']]
        self.spec['panels'] = panels + [panel] if front else [panel] + panels
        self.layout_changed.emit()
        self.update()

    def contextMenuEvent(self, ev):
        panel, _ = self._hit(QPointF(ev.pos()))
        if panel is None:
            return
        self.select(panel['id'])
        menu = QMenu(self)
        kinds = menu.addMenu('Chart type')
        for key, label in E.PANEL_KINDS.items():
            act = QAction(label, kinds)
            act.setCheckable(True)
            act.setChecked(panel.get('kind') == key)
            act.triggered.connect(lambda _=False, k=key, pid=panel['id']: self.kind_requested.emit(pid, k))
            kinds.addAction(act)
        menu.addSeparator()
        menu.addAction('Duplicate', lambda: self._duplicate(panel))
        menu.addAction('Bring to front', lambda: self._restack(panel, True))
        menu.addAction('Send to back', lambda: self._restack(panel, False))
        menu.addSeparator()
        menu.addAction('Delete', self.delete_selected)
        menu.exec(ev.globalPos())
