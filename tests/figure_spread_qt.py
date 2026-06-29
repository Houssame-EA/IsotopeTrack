"""Throwaway prototype: hover a node and the figures SPREAD/FAN out (PySide6).

Run from the project root:   python tests/figure_spread_qt.py
Standalone (no app imports) so it's safe to delete afterwards.

  - dark node canvas (dotted grid, rounded nodes, wire)
  - hover the 'Histogram' node -> its figure previews emerge from it and fan
    out in an arc (animated position + rotation + scale + fade, staggered)
  - each card has an x to remove it; remaining cards re-fan
  - sliders tune spread distance / fan angle / stagger live
"""
import sys
from math import sin, cos, radians
from PySide6.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene, QGraphicsObject,
    QGraphicsPathItem, QWidget, QLabel, QSlider, QHBoxLayout, QVBoxLayout,
)
from PySide6.QtCore import (
    Qt, QRectF, QPointF, QTimer, Signal,
    QPropertyAnimation, QParallelAnimationGroup, QSequentialAnimationGroup,
    QPauseAnimation, QEasingCurve,
)
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath

CANVAS = "#0e1014"; GRID = "#1b1e26"; NODE = "#1b1f29"; NODE_BD = "#2b313d"
TXT = "#e7eaf0"; MUTED = "#99a2b2"; SKY = "#38bdf8"; GREEN = "#34d399"

FIGS = [
    {"t": "Ag - log",    "c": "#3b82f6", "h": [.18, .42, .68, .95, .8, .55, .3, .16]},
    {"t": "Au - linear", "c": "#f97316", "h": [.1, .3, .55, .8, .93, .7, .46, .2]},
    {"t": "Ag/Au - pM",  "c": "#10b981", "h": [.5, .82, .6, .92, .7, .86, .5, .3]},
    {"t": "Pd - counts", "c": "#7c6cf0", "h": [.3, .55, .78, .62, .9, .5, .32, .16]},
    {"t": "Pt - density","c": "#d99012", "h": [.2, .4, .62, .85, .7, .52, .4, .2]},
]


def bars(p, rect, color, heights):
    p.save()
    p.setPen(QPen(QColor("#eef1f5"), 1))
    for g in range(4):
        y = rect.top() + rect.height() * g / 3
        p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
    n = len(heights); gap = 3; bw = (rect.width() - gap * (n - 1)) / n
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color))
    for i, hh in enumerate(heights):
        bh = max(2, rect.height() * hh)
        x = rect.left() + i * (bw + gap); y = rect.bottom() - bh
        p.drawRoundedRect(QRectF(x, y, bw, bh), 1.5, 1.5)
    p.restore()


class FigureCard(QGraphicsObject):
    removed = Signal(object)

    def __init__(self, fig, canvas):
        super().__init__()
        self.fig = fig; self.canvas = canvas
        self.w, self.h = 128, 100
        self.setOpacity(0.0); self.setScale(0.5); self.setVisible(False)
        self.setZValue(6); self.setAcceptHoverEvents(True)
        self._xr = QRectF(-self.w / 2 + 6, -self.h / 2 + 6, 16, 16)
        self._seq = None

    def boundingRect(self):
        return QRectF(-self.w / 2 - 1, -self.h / 2 - 1, self.w + 2, self.h + 2)

    def paint(self, p, _o, _w):
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(-self.w / 2, -self.h / 2, self.w, self.h)
        p.setBrush(QColor("#ffffff")); p.setPen(QPen(QColor("#e7eaf0"), 1))
        p.drawRoundedRect(r, 11, 11)
        p.setPen(QColor("#1f2430")); f = QFont(); f.setPointSize(8); f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.drawText(QRectF(r.left() + 28, r.top() + 5, self.w - 36, 15),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.fig["t"])
        bars(p, QRectF(r.left() + 9, r.top() + 23, self.w - 18, self.h - 32), self.fig["c"], self.fig["h"])
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#f1f3f7")); p.drawRoundedRect(self._xr, 8, 8)
        p.setPen(QPen(QColor("#7a8494"), 1.4))
        xr = self._xr
        p.drawLine(QPointF(xr.left() + 5, xr.top() + 5), QPointF(xr.right() - 5, xr.bottom() - 5))
        p.drawLine(QPointF(xr.right() - 5, xr.top() + 5), QPointF(xr.left() + 5, xr.bottom() - 5))

    def mousePressEvent(self, e):
        if self._xr.contains(e.pos()):
            self.removed.emit(self); e.accept()
        else:
            e.accept()

    def hoverEnterEvent(self, _): self.canvas.cancel_collapse()
    def hoverLeaveEvent(self, _): self.canvas.schedule_collapse()

    def animate_to(self, pos, rot, scale, opac, delay, dur=440):
        if self._seq:
            self._seq.stop()
        grp = QParallelAnimationGroup()
        for prop, end in ((b"pos", pos), (b"rotation", float(rot)),
                          (b"scale", float(scale)), (b"opacity", float(opac))):
            a = QPropertyAnimation(self, prop); a.setDuration(dur)
            a.setEndValue(end); a.setEasingCurve(QEasingCurve.Type.OutCubic)
            grp.addAnimation(a)
        if delay > 0:
            seq = QSequentialAnimationGroup()
            seq.addAnimation(QPauseAnimation(delay)); seq.addAnimation(grp)
            self._seq = seq
        else:
            self._seq = grp
        self._seq.start()


class FigureNode(QGraphicsObject):
    def __init__(self, title, subtitle, accent, canvas, has_in=True, has_out=True, is_fig=False):
        super().__init__()
        self.title = title; self.subtitle = subtitle; self.accent = accent
        self.canvas = canvas; self.has_in = has_in; self.has_out = has_out; self.is_fig = is_fig
        self.w, self.h = 184, 86
        self.setZValue(2)
        if is_fig:
            self.setAcceptHoverEvents(True)

    def boundingRect(self):
        return QRectF(-4, -13, self.w + 18, self.h + 18)

    def port_scene(self, out=True):
        return self.mapToScene(QPointF(self.w if out else 0, self.h / 2))

    def top_center_scene(self):
        return self.mapToScene(QPointF(self.w / 2, 0))

    def paint(self, p, _o, _w):
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(QColor(NODE)); p.setPen(QPen(QColor(NODE_BD), 1.2))
        p.drawRoundedRect(QRectF(0, 0, self.w, self.h), 13, 13)
        p.setPen(QPen(QColor(NODE_BD), 1)); p.drawLine(QPointF(1, 41), QPointF(self.w - 1, 41))
        ac = QColor(self.accent)
        ic = QRectF(13, 8, 26, 26)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(ac.red(), ac.green(), ac.blue(), 40))
        p.drawRoundedRect(ic, 7, 7)
        p.setBrush(ac)
        for i, hh in enumerate((10, 16, 12)):
            p.drawRoundedRect(QRectF(ic.x() + 5 + i * 6, ic.bottom() - 5 - hh, 4, hh), 1, 1)
        p.setPen(QColor(TXT)); f = QFont(); f.setPointSize(11); f.setWeight(QFont.Weight.DemiBold); p.setFont(f)
        p.drawText(QRectF(47, 8, self.w - 55, 26),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.title)
        n = len(self.canvas.figs) if self.is_fig else 0
        sub = f"{n} figures open" if self.is_fig else self.subtitle
        p.setPen(QColor(MUTED)); f2 = QFont(); f2.setPointSize(9); p.setFont(f2)
        p.drawText(QRectF(14, 48, self.w - 28, 24),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), sub)
        p.setBrush(QColor("#21262f")); p.setPen(QPen(QColor("#444c5b"), 2))
        if self.has_in:
            p.drawEllipse(QPointF(0, self.h / 2), 6, 6)
        if self.has_out:
            p.drawEllipse(QPointF(self.w, self.h / 2), 6, 6)
        if self.is_fig and n and not self.canvas.spread_open:
            br = QRectF(self.w - 30, -11, 30, 22)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(SKY)); p.drawRoundedRect(br, 11, 11)
            p.setPen(QColor("#06222e")); fb = QFont(); fb.setPointSize(9); fb.setWeight(QFont.Weight.Bold)
            p.setFont(fb); p.drawText(br, int(Qt.AlignmentFlag.AlignCenter), str(n))

    def hoverEnterEvent(self, _):
        self.canvas.cancel_collapse(); self.canvas.spread()

    def hoverLeaveEvent(self, _):
        self.canvas.schedule_collapse()


class Canvas(QGraphicsView):
    def __init__(self):
        super().__init__()
        sc = QGraphicsScene(self); sc.setSceneRect(0, 0, 780, 540); self.setScene(sc)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.figs = list(FIGS)
        self.R = 150; self.A = 70; self.ST = 45
        self.spread_open = False

        self.src = FigureNode("Single Sample", "E1 - fw 6625 - r1", GREEN, self, has_in=False)
        self.src.setPos(60, 330); sc.addItem(self.src)
        self.fignode = FigureNode("Histogram", "", SKY, self, is_fig=True)
        self.fignode.setPos(360, 326); sc.addItem(self.fignode)

        path = QPainterPath(); a = self.src.port_scene(True); b = self.fignode.port_scene(False)
        path.moveTo(a); path.cubicTo(a.x() + 55, a.y(), b.x() - 55, b.y(), b.x(), b.y())
        wire = QGraphicsPathItem(path); wire.setZValue(0)
        pen = QPen(QColor("#3a4150"), 2.5); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        wire.setPen(pen); sc.addItem(wire)

        self.cards = []
        for fig in self.figs:
            c = FigureCard(fig, self); c.removed.connect(self.remove_card)
            sc.addItem(c); self.cards.append(c)
        self._place_collapsed()

        self._collapse = QTimer(self); self._collapse.setSingleShot(True)
        self._collapse.timeout.connect(self.collapse)

    def drawBackground(self, p, rect):
        p.fillRect(rect, QColor(CANVAS))
        step = 26; p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(GRID))
        x = int(rect.left()) - (int(rect.left()) % step)
        while x < rect.right():
            y = int(rect.top()) - (int(rect.top()) % step)
            while y < rect.bottom():
                p.drawEllipse(QPointF(x, y), 1.3, 1.3); y += step
            x += step

    def _pivot(self):
        return self.fignode.top_center_scene()

    def _spread_target(self, i, n):
        t = (i - (n - 1) / 2) / (n - 1) if n > 1 else 0.0
        ang = t * self.A; rad = radians(ang)
        piv = self._pivot()
        center = QPointF(piv.x() + self.R * sin(rad), piv.y() - self.R * cos(rad))
        return center, ang

    def _place_collapsed(self):
        piv = self._pivot()
        for c in self.cards:
            c.setPos(piv); c.setRotation(0); c.setScale(0.5); c.setOpacity(0.0); c.setVisible(False)

    def spread(self):
        if not self.cards:
            return
        self.spread_open = True; self.fignode.update()
        n = len(self.cards)
        for i, c in enumerate(self.cards):
            c.setVisible(True)
            center, ang = self._spread_target(i, n)
            c.animate_to(center, ang, 1.0, 1.0, delay=i * self.ST)

    def relayout(self):
        n = len(self.cards)
        for i, c in enumerate(self.cards):
            center, ang = self._spread_target(i, n)
            c.animate_to(center, ang, 1.0, 1.0, delay=0, dur=200)

    def collapse(self):
        self.spread_open = False
        piv = self._pivot(); n = len(self.cards)
        for i, c in enumerate(self.cards):
            c.animate_to(piv, 0, 0.5, 0.0, delay=(n - 1 - i) * self.ST)
        total = (n) * self.ST + 460
        QTimer.singleShot(total, self._hide_if_collapsed)
        self.fignode.update()

    def _hide_if_collapsed(self):
        if not self.spread_open:
            for c in self.cards:
                c.setVisible(False)

    def remove_card(self, card):
        card.animate_to(self._pivot(), 0, 0.4, 0.0, delay=0, dur=240)
        def finish():
            if card in self.cards:
                self.cards.remove(card)
            if card.fig in self.figs:
                self.figs.remove(card.fig)
            if card.scene():
                self.scene().removeItem(card)
            self.fignode.update()
            if self.spread_open and self.cards:
                self.relayout()
            elif not self.cards:
                self.spread_open = False; self.fignode.update()
        QTimer.singleShot(260, finish)

    def schedule_collapse(self): self._collapse.start(160)
    def cancel_collapse(self): self._collapse.stop()

    def set_R(self, v): self.R = v; self._relive()
    def set_A(self, v): self.A = v; self._relive()
    def set_ST(self, v): self.ST = v

    def _relive(self):
        if self.spread_open:
            self.relayout()


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Figure spread - hover fan (test)")
        self.resize(800, 640)
        self.setStyleSheet("QWidget{background:#0e1014;color:#e7eaf0;font-family:'Helvetica Neue','Segoe UI',Arial;}"
                           "QLabel{color:#99a2b2;font-size:12px;}")
        self.canvas = Canvas()
        root = QVBoxLayout(self); root.setContentsMargins(14, 12, 14, 14); root.setSpacing(10)
        root.addWidget(self._controls()); root.addWidget(self.canvas, 1)

    def _slider(self, lo, hi, val, fmt, cb):
        box = QVBoxLayout(); box.setSpacing(2)
        lab = QLabel(); s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi); s.setValue(val); s.setFixedWidth(150)
        lab.setText(fmt(val))
        s.valueChanged.connect(lambda v: (lab.setText(fmt(v)), cb(v)))
        box.addWidget(lab); box.addWidget(s)
        w = QWidget(); w.setLayout(box); return w

    def _controls(self):
        bar = QHBoxLayout(); bar.setSpacing(24)
        bar.addWidget(self._slider(80, 230, 150, lambda v: f"Spread distance  {v}", self.canvas.set_R))
        bar.addWidget(self._slider(0, 150, 70, lambda v: f"Fan angle  {v}°", self.canvas.set_A))
        bar.addWidget(self._slider(0, 110, 45, lambda v: f"Stagger  {v} ms", self.canvas.set_ST))
        bar.addStretch(1)
        host = QWidget(); host.setStyleSheet("background:#15181f;border:1px solid #232833;border-radius:12px;")
        host.setLayout(bar); bar.setContentsMargins(16, 10, 16, 10)
        return host


def main():
    app = QApplication(sys.argv)
    win = Window()          # keep a reference, or it gets garbage-collected and closes instantly
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
