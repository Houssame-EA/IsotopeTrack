"""The detail view: the algorithm's own figure, in four flavours.

Which one appears depends on the algorithm: an objective curve for K-Means and
GMM, a reachability plot for OPTICS, a dendrogram for Hierarchical, the
U-matrix for SOM. The engine says which via ``frame.extra.inset.kind``.

These are hand-painted with ``QPainter`` rather than built from a plotting
library. They are small, densely styled, redrawn only when a frame arrives,
and every detail — the L-shaped axis, min/max-only y labels, the dashed
threshold lines, the cursor rule — is specific enough that bending a general
plotting widget into shape would take more code than the painting does.
"""

from __future__ import annotations

import logging

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from .state import THEME

_log = logging.getLogger("IsotopeTrack.results.cluster.live_qt.insets")


def _c(spec, alpha=1.0):
    """Return a ``QColor`` from a palette string with an alpha multiplier.

    Args:
        spec (str): A ``#RRGGBB`` colour; falls back to grey when unparseable.
        alpha (float): Opacity in [0, 1].

    Returns:
        QColor: The colour, ready for a pen or brush.
    """
    col = QColor(spec)
    if not col.isValid():
        col = QColor('#888888')
    col.setAlphaF(max(0.0, min(1.0, alpha)))
    return col


def theme_color(name):
    """Resolve a palette keyword to a colour.

    Args:
        name (str): A key such as ``'accent'``, ``'warn'`` or ``'bad'``.

    Returns:
        str: A ``#RRGGBB`` colour, falling back to the accent colour.
    """
    return THEME.get(name) or THEME.accent


def _fmt_y(v):
    """Format a y-axis bound compactly.

    Args:
        v (float): The value.

    Returns:
        str: A short decimal or exponential string.
    """
    if abs(v) >= 1000 or (v != 0 and abs(v) < 0.01):
        from .viewmath import exp_str
        return exp_str(v)
    return '%g' % (round(v * 100) / 100)


def uniform_label(leaves, leaf_labels):
    """Return the cluster id shared by every leaf under a node.

    Args:
        leaves (list[int]): Leaf indices below the node.
        leaf_labels (list | None): Cluster id per leaf.

    Returns:
        int | None: The shared cluster id, or None when they differ.
    """
    if not leaf_labels or not leaves:
        return None
    c = leaf_labels[leaves[0]]
    for l in leaves:
        if leaf_labels[l] != c:
            return None
    return c


def build_dendro(d):
    """Build leaf positions and heights from a scipy-style merge list.

    The traversal is iterative; a deep merge tree would overflow a recursive
    one.

    Args:
        d (dict): The detail payload, with ``n_leaves`` and ``merges``.

    Returns:
        tuple: ``(n, kids, x, hgt, leaves, slots)`` — leaf count, child map,
        x position per node, height per merge, leaves below each node, and the
        number of leaf slots.
    """
    n = int(d.get('n_leaves') or 0)
    merges = d.get('merges') or []
    kids = {n + i: (m[0], m[1]) for i, m in enumerate(merges)}
    consumed = set()
    for a, b in kids.values():
        consumed.add(a)
        consumed.add(b)
    roots = [i for i in range(n + len(merges))
             if i not in consumed and (i < n or i in kids)]

    x, leaves, slot = {}, {}, 0
    for r0 in roots:
        stack = [(r0, False)]
        while stack:
            node, done = stack.pop()
            if node not in kids:
                x[node] = slot
                slot += 1
                leaves[node] = [node]
                continue
            if not done:
                stack.append((node, True))
                a, b = kids[node]
                stack.append((b, False))
                stack.append((a, False))
            else:
                a, b = kids[node]
                x[node] = (x[a] + x[b]) / 2
                leaves[node] = leaves[a] + leaves[b]
    hgt = {n + i: m[2] for i, m in enumerate(merges)}
    return n, kids, x, hgt, leaves, max(slot, 1)


class InsetCanvas(QWidget):
    """Paints whichever detail figure the current frame carries."""

    def __init__(self, S, parent=None):
        """Bind the canvas to the view state.

        Args:
            S (LiveState): The view state, for fonts and cluster colours.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.S = S
        self.data = None
        self.setMinimumSize(180, 110)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _font(self, p, size):
        """Return the detail-view font at ``size`` pixels.

        Args:
            p (QPainter): Painter whose current font is the base.
            size (float): Pixel size before the minimum is applied.

        Returns:
            QFont: The font carrying the family, weight and slant.
        """
        f = QFont(p.font())
        if self.S.ui.font:
            f.setFamily(self.S.ui.font)
        f.setPixelSize(max(7, int(round(size))))
        f.setBold('bold' in (self.S.ui.font_style or ''))
        f.setItalic('italic' in (self.S.ui.font_style or ''))
        return f

    def set_data(self, d):
        """Adopt a new detail payload and repaint.

        Args:
            d (dict | None): The frame's ``extra.inset`` payload.
        """
        self.data = d
        self.update()

    def _axes(self, p, w, h, xlabel=None, ylabel=None):
        """Draw the L-shaped axis box and return the plot rect.

        Args:
            p (QPainter): Active painter.
            w (float): Canvas width.
            h (float): Canvas height.
            xlabel (str | None): Label for the x axis.
            ylabel (str | None): Label for the y axis.

        Returns:
            QRectF: The area available for the plot itself.
        """
        fs = self.S.ui.font_size
        L = max(28.0, fs * 2.5)
        R = 10.0
        T = max(10.0, fs * 0.8)
        B = max(22.0, fs * 1.8) if (xlabel or ylabel) else max(14.0, fs * 1.2)
        r = QRectF(L, T, max(10.0, w - L - R), max(10.0, h - T - B))

        p.setPen(QPen(_c(THEME.text), 1))
        p.drawLine(QPointF(r.left(), r.top()), QPointF(r.left(), r.bottom()))
        p.drawLine(QPointF(r.left(), r.bottom()), QPointF(r.right(), r.bottom()))

        f = self._font(p, fs * 0.72)
        p.setFont(f)
        if xlabel:
            fm = p.fontMetrics()
            p.drawText(QPointF(r.right() - fm.horizontalAdvance(xlabel),
                               r.bottom() + 6 + fm.ascent()), xlabel)
        if ylabel:
            p.drawText(QPointF(2, 1 + p.fontMetrics().ascent()), ylabel)
        return r

    def _y_ticks(self, p, r, lo, hi):
        """Draw min and max labels on the y axis.

        Args:
            p (QPainter): Active painter.
            r (QRectF): The plot rect.
            lo (float): Lower bound.
            hi (float): Upper bound.
        """
        p.setPen(QPen(_c(THEME.text)))
        fm = p.fontMetrics()
        for val, y in ((hi, r.top() + 4), (lo, r.bottom() - 4)):
            t = _fmt_y(val)
            p.drawText(QPointF(r.left() - 4 - fm.horizontalAdvance(t),
                               y + fm.ascent() / 2 - 1), t)

    def paintEvent(self, _ev):
        """Paint whichever figure the payload names.

        A malformed payload draws a placeholder rather than taking the view
        down mid-run. The painter is ended in a ``finally`` so an escaping
        exception cannot leave it active and crash Qt.

        Args:
            _ev (QPaintEvent): Unused.
        """
        d = self.data
        if not d:
            return
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setFont(self._font(p, self.S.ui.font_size * 0.72))
            w, h = float(self.width()), float(self.height())
            if w < 40 or h < 30:
                return
            kind = d.get('kind')
            try:
                if kind == 'curve':
                    self._curve(p, d, w, h)
                elif kind == 'bars':
                    self._bars(p, d, w, h)
                elif kind == 'dendrogram':
                    self._dendro(p, d, w, h)
                elif kind == 'grid':
                    self._grid(p, d, w, h)
            except Exception:
                _log.exception("inset paint failed (kind=%s)", kind)
                p.setPen(QPen(_c(THEME.text)))
                p.drawText(QPointF(8, 16), 'detail view unavailable')
        finally:
            p.end()

    def _curve(self, p, d, w, h):
        """Draw a line chart with optional right axis, threshold and bar strip.

        Used for the K-Means and GMM objective curves.

        Args:
            p (QPainter): Active painter.
            d (dict): The detail payload.
            w (float): Canvas width.
            h (float): Canvas height.
        """
        series = [s for s in (d.get('series') or []) if s.get('y')]
        bars = [b for b in (d.get('bars') or []) if b.get('values')]
        bar_h = 30.0 if bars else 0.0
        r = self._axes(p, w, h - bar_h, d.get('xlabel'), d.get('ylabel'))

        if not series:
            p.setPen(QPen(_c(THEME.text)))
            fm = p.fontMetrics()
            p.drawText(QPointF(r.center().x() - fm.horizontalAdvance('collecting…') / 2,
                               r.center().y()), 'collecting…')

        left = [s for s in series if s.get('axis') != 'right']
        right = [s for s in series if s.get('axis') == 'right']

        def rng(lst):
            """Return the finite range of a list of series, widened if flat.

            Args:
                lst (list[dict]): Series to scan.

            Returns:
                tuple[float, float]: Lower and upper bound.
            """
            vals = [v for s in lst for v in s.get('y', [])
                    if v is not None and np.isfinite(v)]
            if not vals:
                return 0.0, 1.0
            lo, hi = min(vals), max(vals)
            return (lo, lo + 1.0) if hi - lo < 1e-12 else (lo, hi)

        lo, hi = rng(left if left else series)
        hline = d.get('hline') or {}
        if hline.get('y') is not None:
            lo, hi = min(lo, hline['y']), max(hi, hline['y'])
        rlo, rhi = rng(right) if right else (0.0, 1.0)
        nmax = max([len(s['y']) for s in series] + [2])

        def px(i):
            """Return the screen x for sample index ``i``.

            Args:
                i (int): Sample index.

            Returns:
                float: Screen x.
            """
            return r.left() if nmax < 2 else r.left() + (i / (nmax - 1)) * r.width()

        def py(v, use_r=False):
            """Return the screen y for a value.

            Args:
                v (float): The value.
                use_r (bool): Scale against the right axis instead of the left.

            Returns:
                float: Screen y.
            """
            a, b = (rlo, rhi) if use_r else (lo, hi)
            return r.bottom() - ((v - a) / ((b - a) or 1)) * r.height()

        if hline.get('y') is not None:
            col = theme_color(hline.get('color') or 'bad')
            pen = QPen(_c(col, 0.85), 1.2)
            pen.setDashPattern([4, 3])
            p.setPen(pen)
            y = py(hline['y'])
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            if hline.get('label'):
                p.setPen(QPen(_c(col)))
                fm = p.fontMetrics()
                p.drawText(QPointF(r.right() - 2 - fm.horizontalAdvance(hline['label']),
                                   y - 2), hline['label'])

        for s in series:
            use_r = s.get('axis') == 'right'
            col = theme_color(s.get('color') or 'accent')
            pen = QPen(_c(col, 0.7 if use_r else 1.0), 1.1 if use_r else 1.8)
            if use_r:
                pen.setDashPattern([3, 2])
            p.setPen(pen)
            prev = None
            for i, v in enumerate(s['y']):
                if v is None or not np.isfinite(v):
                    prev = None
                    continue
                cur = QPointF(px(i), py(v, use_r))
                if prev is not None:
                    p.drawLine(prev, cur)
                prev = cur
            last = len(s['y']) - 1
            lv = s['y'][last] if last >= 0 else None
            if lv is not None and np.isfinite(lv):
                p.setPen(Qt.NoPen)
                p.setBrush(_c(col))
                p.drawEllipse(QPointF(px(last), py(lv, use_r)), 2.6, 2.6)

        self._y_ticks(p, r, lo, hi)

        ly = r.top() + 2
        lh = max(10.0, self.S.ui.font_size * 0.82)
        for s in series:
            p.setPen(QPen(_c(theme_color(s.get('color') or 'accent'))))
            p.drawText(QPointF(r.left() + 5, ly + p.fontMetrics().ascent()),
                       '— ' + (s.get('label') or ''))
            ly += lh

        if bars:
            self._bar_strip(p, bars[0], r.left(), h - bar_h + 4,
                            r.width(), bar_h - 10)

    def _bar_strip(self, p, bar, x, y, w, h):
        """Draw the small bar strip that sits under a curve.

        Args:
            p (QPainter): Active painter.
            bar (dict): The bar payload.
            x (float): Left edge.
            y (float): Top edge.
            w (float): Width.
            h (float): Height.
        """
        vals = bar.get('values') or []
        if not vals:
            return
        mx = max([abs(v or 0) for v in vals] + [1e-9])
        bw = max(1.5, w / len(vals) - 2)
        p.setPen(Qt.NoPen)
        for i, v in enumerate(vals):
            bh = max(1.0, (abs(v or 0) / mx) * h)
            col = self.S.cluster_color(i) if bar.get('by_cluster') \
                else theme_color('accent')
            p.setBrush(_c(col, 0.85))
            p.drawRect(QRectF(x + i * (w / len(vals)), y + h - bh, bw, bh))
        p.setPen(QPen(_c(THEME.text)))
        p.drawText(QPointF(x, y + h + 9), bar.get('label') or '')

    def _bars(self, p, d, w, h):
        """Draw a bar chart with optional threshold, cursor and overlay line.

        Used for the OPTICS reachability plot, eigen spectra and CF-leaf sizes.

        Args:
            p (QPainter): Active painter.
            d (dict): The detail payload.
            w (float): Canvas width.
            h (float): Canvas height.
        """
        vals = [None if (v is None or not np.isfinite(v)) else v
                for v in (d.get('values') or [])]
        r = self._axes(p, w, h, d.get('xlabel'), d.get('ylabel'))
        if not vals:
            p.setPen(QPen(_c(THEME.text)))
            fm = p.fontMetrics()
            p.drawText(QPointF(r.center().x() - fm.horizontalAdvance('collecting…') / 2,
                               r.center().y()), 'collecting…')
            return

        hi, lo = max([v for v in vals if v is not None] or [1]), 0.0
        hline = d.get('hline') or {}
        if hline.get('y') is not None:
            hi = max(hi, hline['y'])
        if not np.isfinite(hi) or hi <= 0:
            hi = 1.0

        step = r.width() / len(vals)
        bw = max(1.0, step - (1 if step > 4 else 0))
        cursor = d.get('cursor')
        highlight = d.get('highlight')
        bar_clusters = d.get('bar_clusters')
        p.setPen(Qt.NoPen)
        for i, v in enumerate(vals):
            if v is None:
                continue
            bh = max(0.5, (v / hi) * r.height())
            cl = bar_clusters[i] if bar_clusters and i < len(bar_clusters) else None
            if cl is not None:
                col = self.S.cluster_color(cl)
            elif highlight is not None and i <= highlight:
                col = theme_color('accent')
            else:
                col = THEME.noise
            a = 0.25 if (cursor is not None and i > cursor) else 0.9
            p.setBrush(_c(col, a))
            p.drawRect(QRectF(r.left() + i * step, r.bottom() - bh, bw, bh))

        if hline.get('y') is not None:
            y = r.bottom() - (hline['y'] / hi) * r.height()
            col = theme_color(hline.get('color') or 'bad')
            pen = QPen(_c(col), 1.2)
            pen.setDashPattern([4, 3])
            p.setPen(pen)
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            if hline.get('label'):
                p.setPen(QPen(_c(col)))
                fm = p.fontMetrics()
                p.drawText(QPointF(r.right() - 2 - fm.horizontalAdvance(hline['label']),
                                   y - 2), hline['label'])

        vline = d.get('vline') or {}
        if vline.get('x') is not None:
            x = r.left() + (vline['x'] / len(vals)) * r.width()
            col = theme_color(vline.get('color') or 'bad')
            pen = QPen(_c(col), 1.2)
            pen.setDashPattern([4, 3])
            p.setPen(pen)
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            if vline.get('label'):
                p.setPen(QPen(_c(col)))
                p.drawText(QPointF(x, r.top() + p.fontMetrics().ascent()),
                           ' ' + vline['label'])

        if cursor is not None and cursor < len(vals):
            x = r.left() + (cursor / len(vals)) * r.width()
            p.setPen(QPen(_c(THEME.text, 0.5), 1))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))

        line = (d.get('series') or [None])[0]
        if line and line.get('y') and len(line['y']) > 1:
            mx = max(line['y']) or 1
            pen = QPen(_c(theme_color(line.get('color') or 'warn'), 0.8), 1.3)
            pen.setDashPattern([3, 2])
            p.setPen(pen)
            prev = None
            for i, v in enumerate(line['y']):
                cur = QPointF(r.left() + (i / (len(line['y']) - 1)) * r.width(),
                              r.bottom() - (v / mx) * r.height())
                if prev is not None:
                    p.drawLine(prev, cur)
                prev = cur

        self._y_ticks(p, r, lo, hi)

    def _dendro(self, p, d, w, h):
        """Draw the merge tree, colouring branches by cluster membership.

        Used for Hierarchical and HDBSCAN.

        Args:
            p (QPainter): Active painter.
            d (dict): The detail payload.
            w (float): Canvas width.
            h (float): Canvas height.
        """
        r = self._axes(p, w, h, 'leaves', d.get('ylabel') or 'distance')
        n, kids, x, hgt, leaves, slots = build_dendro(d)
        if not n:
            return
        hmax = max(list(hgt.values()) or [0]) or 1

        def X(i):
            """Return the screen x for leaf slot ``i``.

            Args:
                i (float): Slot position.

            Returns:
                float: Screen x.
            """
            return r.left() + ((i + 0.5) / slots) * r.width()

        def Y(v):
            """Return the screen y for a merge height.

            Args:
                v (float): Merge height.

            Returns:
                float: Screen y.
            """
            return r.bottom() - (v / hmax) * r.height() * 0.94

        ll = d.get('leaf_labels')

        def col_of(node):
            """Return the colour for a node.

            Args:
                node (int): Node id.

            Returns:
                str: The cluster colour when every leaf below agrees,
                otherwise the noise colour.
            """
            c = uniform_label(leaves.get(node) or [], ll)
            return THEME.noise if (c is None or c < 0) else self.S.cluster_color(c)

        for node, (a, b) in kids.items():
            ya = Y(hgt[a]) if a in kids else Y(0)
            yb = Y(hgt[b]) if b in kids else Y(0)
            yt = Y(hgt[node])
            xa, xb = X(x[a]), X(x[b])
            col = col_of(node)
            p.setPen(QPen(_c(col, 0.45 if col == THEME.noise else 0.95), 1.2))
            p.drawLine(QPointF(xa, ya), QPointF(xa, yt))
            p.drawLine(QPointF(xa, yt), QPointF(xb, yt))
            p.drawLine(QPointF(xb, yt), QPointF(xb, yb))

        p.setPen(Qt.NoPen)
        for i in range(n):
            if i not in x:
                continue
            c = ll[i] if (ll and i < len(ll) and ll[i] is not None) else -1
            p.setBrush(_c(THEME.noise if c < 0 else self.S.cluster_color(c),
                          0.5 if c < 0 else 0.95))
            p.drawRect(QRectF(X(x[i]) - 1, r.bottom() - 2.5, 2, 2.5))

        if d.get('cut') is not None:
            heights = sorted(hgt.values(), reverse=True)
            idx = (d.get('target') if d.get('target') is not None else d['cut']) - 1
            if 0 <= idx < len(heights):
                nxt = heights[idx + 1] if idx + 1 < len(heights) else 0
                y = Y((heights[idx] + nxt) / 2)
                col = theme_color('bad')
                pen = QPen(_c(col, 0.9), 1.1)
                pen.setDashPattern([4, 3])
                p.setPen(pen)
                p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
                p.setPen(QPen(_c(col)))
                p.drawText(QPointF(r.left(), y - 1),
                           ' cut · %s groups' % d['cut'])

        self._y_ticks(p, r, 0, hmax)

    def _grid(self, p, d, w, h):
        """Draw the SOM U-matrix as a heatmap in map space.

        Light cells are similar neighbours, dark cells are cluster boundaries.

        Args:
            p (QPainter): Active painter.
            d (dict): The detail payload.
            w (float): Canvas width.
            h (float): Canvas height.
        """
        rows, cols = int(d.get('rows') or 1), int(d.get('cols') or 1)
        vals = d.get('values') or []
        pad = 10.0
        avail_w, avail_h = w - 2 * pad, h - 2 * pad - 12
        cs = max(4.0, min(avail_w / cols, avail_h / rows))
        x0 = (w - cs * cols) / 2
        y0 = pad + (avail_h - cs * rows) / 2

        finite = [v for v in vals if v is not None and np.isfinite(v)]
        lo, hi = (min(finite), max(finite)) if finite else (0.0, 1.0)
        if hi - lo < 1e-12:
            hi = lo + 1

        cell_labels = d.get('cell_labels')
        for ri in range(rows):
            for ci in range(cols):
                i = ri * cols + ci
                v = vals[i] if i < len(vals) else None
                t = 0.0 if (v is None or not np.isfinite(v)) else (v - lo) / (hi - lo)
                x, y = x0 + ci * cs, y0 + ri * cs
                p.setPen(Qt.NoPen)
                p.setBrush(_c(THEME.text, 0.08 + 0.72 * t))
                p.drawRect(QRectF(x, y, cs - 1, cs - 1))
                cl = cell_labels[i] if (cell_labels and i < len(cell_labels)) else None
                if cl is not None:
                    p.setBrush(_c(self.S.cluster_color(cl), 0.95))
                    p.drawEllipse(QPointF(x + cs / 2, y + cs / 2),
                                  max(1.4, cs * 0.16), max(1.4, cs * 0.16))
        p.setPen(QPen(_c(THEME.text)))
        p.drawText(QPointF(pad, h - 3),
                   'light = similar neighbours · dark = cluster boundary')


class InsetBox(QWidget):
    """Container around :class:`InsetCanvas`.

    The title and subtitle are emitted rather than drawn: the box lives inside
    a floating panel whose header shows them and provides the drag handle.
    """

    title_changed = Signal(str, str)
    availability_changed = Signal(bool)

    def __init__(self, S, parent=None):
        """Build the container around a fresh canvas.

        Args:
            S (LiveState): The view state.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.S = S
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 8)
        lay.setSpacing(0)
        self.canvas = InsetCanvas(S)
        lay.addWidget(self.canvas, 1)
        self.apply_theme()

    def apply_theme(self):
        """Re-read the palette on a dark/light switch."""
        self.setStyleSheet('background:transparent;')
        self.canvas.update()

    def set_frame(self, frame):
        """Show the detail payload of a frame, or report it has none.

        Args:
            frame (dict | None): The frame currently on screen.
        """
        d = ((frame or {}).get('extra') or {}).get('inset')
        available = bool(d) and self.S.inset_on
        self.availability_changed.emit(available)
        if not available:
            return
        self.title_changed.emit(d.get('title') or 'Detail',
                                d.get('subtitle') or '')
        self.canvas.set_data(d)
