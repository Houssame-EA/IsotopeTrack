"""Cluster legend, sample legend, overlay colour bar and the colour picker.

The panel scrolls. A dataset with many clusters or many samples produces more
rows than a floating box can show, and the box is user-resizable, so the
content is wrapped in a ``QScrollArea`` that adds a vertical scrollbar only
when the rows do not fit.

Rows are reused across frames rather than rebuilt, because the legend is
refreshed on every computation frame and recreating a few hundred widgets that
often is wasteful.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QColorDialog, QDialog, QFrame,
                               QGraphicsOpacityEffect, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from .state import (DIM_ALPHA, MARKER_UNITS, PICKER_EXTRA, THEME, cluster_tag,
                    element_label_html, element_token_html)


def _glyph_pixmap(shape, color, px=13, dpr=2.0):
    """Render one marker shape into a small pixmap.

    Used for the sample legend glyphs and the shape dropdowns in the settings
    dialog.

    Args:
        shape (str): A key from :data:`~results.cluster.live_qt.state.SHAPES`.
        color (str): Fill colour; falls back to the theme's text colour.
        px (int): Logical size of the square pixmap.
        dpr (float): Device pixel ratio, so the glyph stays sharp on a
            high-density display.

    Returns:
        QPixmap: The rendered glyph on a transparent background.
    """
    pm = QPixmap(int(px * dpr), int(px * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    try:
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setBrush(QColor(color or THEME.text))
        p.setPen(Qt.NoPen)
        r = px * 0.30
        cx = cy = px / 2.0
        if shape == 'circle' or shape not in MARKER_UNITS:
            p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        else:
            path = QPainterPath()
            pts = MARKER_UNITS[shape]
            path.moveTo(cx + pts[0][0] * r, cy + pts[0][1] * r)
            for x, y in pts[1:]:
                path.lineTo(cx + x * r, cy + y * r)
            path.closeSubpath()
            p.drawPath(path)
    finally:
        p.end()
    return pm


def cluster_top_elements(S, labels, c):
    """Return the elements dominating a cluster's mean composition.

    Applies the same limits as the ② Cluster legends: elements contributing
    less than ``S.ui.min_pct`` are dropped, the top ``S.ui.max_iso`` are kept,
    and any remainder is reported as a ``'+N…'`` token.

    Args:
        S (LiveState): The view state, for the display limits.
        labels (numpy.ndarray): Per-particle cluster ids for the current frame.
        c (int): Cluster id to summarise.

    Returns:
        list[str]: Element keys in descending abundance, plus any overflow
        token. Empty when the cluster holds no signal.
    """
    d = S.data or {}
    els = d.get('elements')
    R = S.raw_matrix()
    if R is None or not els:
        return []
    m = np.asarray(labels) == c
    if not m.any() or len(m) != len(R):
        return []
    sums = R[m].sum(0)
    total = float(sums.sum())
    if not (total > 0):
        return []
    pct = sums / total * 100.0
    ranked = [(els[j], pct[j]) for j in range(len(els)) if pct[j] >= S.ui.min_pct]
    ranked.sort(key=lambda p: -p[1])
    keep = [p[0] for p in ranked[:S.ui.max_iso]]
    if len(ranked) > S.ui.max_iso:
        keep.append('+%d…' % (len(ranked) - S.ui.max_iso))
    return keep


def fmt_overlay_value(v):
    """Format an overlay scale bound compactly for the colour bar.

    Args:
        v (float): A value from the raw data matrix.

    Returns:
        str: A short decimal or exponential string, or ``'–'`` when not finite.
    """
    if not np.isfinite(v):
        return '–'
    a = abs(v)
    if a >= 1e5 or (0 < a < 1e-2):
        from .viewmath import exp_str
        return exp_str(v)
    return '%g' % (round(v * 100) / 100)


class ColorPicker(QDialog):
    """Swatch grid, hex field and a route to the system colour dialog."""

    def __init__(self, current, palette, parent=None):
        """Build the picker for a cluster currently showing ``current``.

        Args:
            current (str): The cluster's present colour as ``#RRGGBB``.
            palette (list[str]): The active cluster palette, offered first.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle('Cluster colour')
        self.setWindowFlags(Qt.Popup)
        self.chosen = None
        self._reset = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(4)
        seen, col, row = set(), 0, 0
        cur = str(current or '').lower()
        for hexv in list(palette) + PICKER_EXTRA:
            key = str(hexv).lower()
            if key in seen:
                continue
            seen.add(key)
            b = QPushButton()
            b.setFixedSize(20, 20)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(hexv)
            border = THEME.text if key == cur else THEME.stroke
            b.setStyleSheet('background:%s;border:%dpx solid %s;border-radius:4px;'
                            % (hexv, 2 if key == cur else 1, border))
            b.clicked.connect(lambda _=False, h=hexv: self._pick(h))
            grid.addWidget(b, row, col)
            col += 1
            if col >= 8:
                col, row = 0, row + 1
        lay.addLayout(grid)

        roww = QHBoxLayout()
        roww.setSpacing(6)
        self.hex = QLineEdit(current)
        self.hex.setMaxLength(7)
        self.hex.setFixedWidth(80)
        self.hex.textChanged.connect(self._on_hex)
        roww.addWidget(self.hex)

        more = QPushButton('Custom…')
        more.setToolTip('Open the system colour picker')
        more.clicked.connect(self._custom)
        roww.addWidget(more)

        rst = QPushButton('Default')
        rst.setToolTip('Use the palette colour for this cluster')
        rst.clicked.connect(self._default)
        roww.addWidget(rst)
        lay.addLayout(roww)

    def _pick(self, hexv):
        """Accept the dialog with the swatch the user clicked.

        Args:
            hexv (str): The chosen colour as ``#RRGGBB``.
        """
        self.chosen = hexv
        self.accept()

    def _on_hex(self, text):
        """Adopt a hand-typed colour once it parses as a full hex triplet.

        Args:
            text (str): Current contents of the hex field.
        """
        t = text.strip()
        if QColor(t).isValid() and len(t) == 7 and t.startswith('#'):
            self.chosen = t

    def _custom(self):
        """Hand off to the system colour dialog and accept its result."""
        c = QColorDialog.getColor(QColor(self.hex.text()), self, 'Cluster colour')
        if c.isValid():
            self.chosen = c.name()
            self.accept()

    def _default(self):
        """Accept the dialog asking to revert to the palette colour."""
        self.chosen = None
        self._reset = True
        self.accept()

    @property
    def reverted(self):
        """bool: True when the user chose 'Default' rather than a colour."""
        return self._reset



#: Cluster rows the legend will render.
#:
#: Density-based algorithms can return over a thousand clusters on a real
#: dataset. Each row is a widget whose label needs a scan of the composition
#: matrix, so the legend was costing more than everything else in the redraw
#: put together — and a thousand-row legend is unreadable anyway. The largest
#: clusters are listed and the rest are reported as a count.
MAX_LEGEND_ROWS = 60


class _Row(QFrame):
    """Shared behaviour for a legend row: click, alt-click and dim styling.

    Clicking the leading icon is a distinct action from clicking the row, so
    the press position is compared against the icon width rather than relying
    on child widgets swallowing the event.
    """

    clicked = Signal()
    alt_clicked = Signal()
    icon_clicked = Signal()

    def __init__(self):
        """Set the hand cursor and prepare the icon hit region."""
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self._icon_w = 0

    def mouseReleaseEvent(self, ev):
        """Route a left click to the icon, the alt action, or the row.

        Args:
            ev (QMouseEvent): The release event.
        """
        if ev.button() != Qt.LeftButton:
            return
        if ev.position().x() <= self._icon_w:
            self.icon_clicked.emit()
        elif ev.modifiers() & Qt.AltModifier:
            self.alt_clicked.emit()
        else:
            self.clicked.emit()

    def set_state(self, off, on, dim):
        """Apply the hidden, focused and dimmed appearances.

        Args:
            off (bool): The cluster or sample is hidden entirely.
            on (bool): It currently holds the focus.
            dim (bool): Something else holds the focus, so this fades back.
        """
        opacity = 0.35 if off else (DIM_ALPHA + 0.35 if dim else 1.0)
        bg = THEME.chip if on else 'transparent'
        self.setStyleSheet('QFrame{background:%s;border-radius:5px;}' % bg)
        for lbl in self.findChildren(QLabel):
            eff = lbl.graphicsEffect()
            if eff is None:
                eff = QGraphicsOpacityEffect(lbl)
                lbl.setGraphicsEffect(eff)
            eff.setOpacity(opacity)


class ClusterRow(_Row):
    """Swatch, dominant-element name and particle count for one cluster."""

    def __init__(self, cid):
        """Build the row for one cluster.

        Args:
            cid (int): Cluster id, negative for noise.
        """
        super().__init__()
        self.cid = cid
        self._icon_w = 22
        lay = QHBoxLayout(self)
        lay.setContentsMargins(5, 2, 6, 2)
        lay.setSpacing(7)

        self.sw = QLabel()
        self.sw.setFixedSize(12, 12)
        self.sw.setToolTip('Click to recolour')
        lay.addWidget(self.sw)

        self.nm = QLabel()
        self.nm.setTextFormat(Qt.RichText)
        lay.addWidget(self.nm, 1)

        self.ct = QLabel()
        self.ct.setObjectName('legendCount')
        lay.addWidget(self.ct)

        self._col = None

    def set_color(self, col):
        """Repaint the swatch, skipping the work when nothing changed.

        Args:
            col (str): The cluster's colour as ``#RRGGBB``.
        """
        if col == self._col:
            return
        self._col = col
        self.sw.setStyleSheet(
            'background:%s;border:1px solid %s;border-radius:3px;'
            % (col, THEME.stroke))


class SampleRow(_Row):
    """Marker glyph, sample name and particle count for one sample."""

    def __init__(self, name):
        """Build the row for one sample.

        Args:
            name (str): Sample name as it appears in the particle data.
        """
        super().__init__()
        self.name = name
        self._icon_w = 22
        lay = QHBoxLayout(self)
        lay.setContentsMargins(5, 2, 6, 2)
        lay.setSpacing(7)

        self.gl = QLabel()
        self.gl.setFixedSize(13, 13)
        self.gl.setToolTip('Click to change this sample’s marker shape')
        lay.addWidget(self.gl)

        self.nm = QLabel(name)
        lay.addWidget(self.nm, 1)

        self.ct = QLabel()
        self.ct.setObjectName('legendCount')
        lay.addWidget(self.ct)

        self._shape = None

    def set_shape(self, shape):
        """Repaint the glyph, skipping the work when nothing changed.

        Args:
            shape (str): A key from
                :data:`~results.cluster.live_qt.state.SHAPES`.
        """
        if shape == self._shape:
            return
        self._shape = shape
        self.gl.setPixmap(_glyph_pixmap(shape, THEME.text))


class ColorBar(QWidget):
    """The overlay ramp drawn as a gradient strip.

    Used in the legend and again under the colormap dropdown in the control
    panel.
    """

    def __init__(self, S):
        """Bind the strip to the state that owns the active ramp.

        Args:
            S (LiveState): The view state, queried for ``ramp_color``.
        """
        super().__init__()
        self.S = S
        self.setFixedHeight(10)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, _ev):
        """Paint one pixel column per ramp step across the widget width.

        Args:
            _ev (QPaintEvent): Unused.
        """
        p = QPainter(self)
        try:
            w, h = self.width(), self.height()
            for x in range(w):
                p.fillRect(x, 0, 1, h, QColor(
                    self.S.ramp_color(round(x / max(1, w - 1) * 255))))
        finally:
            p.end()


class LegendPanel(QWidget):
    """The legend: clusters, samples and the overlay scale, in a scroll area.

    Emits intent rather than mutating the state directly, so the parent keeps
    one place where focus and visibility change.
    """

    focus_cluster = Signal(int)
    toggle_cluster = Signal(int)
    recolor_cluster = Signal(int)
    focus_sample = Signal(str)
    toggle_sample = Signal(str)
    cycle_sample_shape = Signal(str)

    def __init__(self, S, parent=None):
        """Build the scrollable legend.

        Args:
            S (LiveState): The view state to read clusters and samples from.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.S = S
        self._crows = {}
        self._overflow_n = 0
        self._srows = {}
        self._top_labels = None
        self._top_cache = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        outer.addWidget(self.scroll)

        body = QWidget()
        self.scroll.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(9, 6, 9, 9)
        lay.setSpacing(5)

        self.h_clusters = QLabel('Clusters')
        self.h_clusters.setObjectName('legendHead')
        lay.addWidget(self.h_clusters)
        self.cbox = QVBoxLayout()
        self.cbox.setSpacing(1)
        lay.addLayout(self.cbox)

        self.samp_head = QLabel('Samples')
        self.samp_head.setObjectName('legendHead')
        lay.addWidget(self.samp_head)
        self.sbox = QVBoxLayout()
        self.sbox.setSpacing(1)
        lay.addLayout(self.sbox)

        self.ov_head = QLabel('Element')
        self.ov_head.setTextFormat(Qt.RichText)
        self.ov_head.setObjectName('legendHead')
        lay.addWidget(self.ov_head)
        self.ov_bar = ColorBar(S)
        lay.addWidget(self.ov_bar)

        scale = QHBoxLayout()
        self.ov_lo = QLabel()
        self.ov_hi = QLabel()
        for l in (self.ov_lo, self.ov_hi):
            l.setObjectName('ovScale')
        scale.addWidget(self.ov_lo)
        scale.addStretch(1)
        scale.addWidget(self.ov_hi)
        lay.addLayout(scale)

        self.ov_note = QLabel()
        self.ov_note.setObjectName('ovScale')
        lay.addWidget(self.ov_note)

        lay.addStretch(1)
        self.apply_theme()

    def invalidate(self):
        """Drop the cached cluster names and glyphs.

        The names embed the element label style and the composition limits, and
        the glyphs embed the text colour, so an appearance change has to clear
        both or the rows keep showing the previous formatting.
        """
        self._top_labels = None
        self._top_cache = {}
        for row in self._crows.values():
            row._col = None
        for row in self._srows.values():
            row._shape = None

    def rebuild(self, labels):
        """Refresh both legends and the overlay bar for the frame on screen.

        Args:
            labels (numpy.ndarray | None): Per-particle cluster ids, or None to
                leave the cluster rows alone and refresh only the rest.
        """
        self._rebuild_clusters(labels)
        self._rebuild_samples(labels)
        self._rebuild_overlay()

    def _cluster_name(self, L, labels, c):
        """Return a cluster's display name, caching the composition scan.

        :func:`cluster_top_elements` sums the raw matrix over every particle in
        the cluster, far too expensive to repeat per repaint. The cache is
        keyed on the identity of the labels array, so the scan runs once per
        frame rather than once per redraw.

        Args:
            L (numpy.ndarray): Per-particle cluster ids as an array.
            labels: The labels object as handed in, used as the cache key.
            c (int): Cluster id.

        Returns:
            str: Markup such as ``'C1 · Fe·Si'``.
        """
        if labels is not self._top_labels:
            self._top_labels = labels
            self._top_cache = {}
        cached = self._top_cache.get(c)
        if cached is not None:
            return cached
        top = [] if c < 0 else cluster_top_elements(self.S, L, c)
        name = cluster_tag(c)
        if top:
            name += ' · ' + '·'.join(
                element_token_html(t, self.S.ui.label_mode) for t in top)
        self._top_cache[c] = name
        return name

    def _rebuild_clusters(self, labels):
        """Rebuild or update one row per cluster present in the frame.

        Rows are recreated only when the set of cluster ids changes; otherwise
        they are updated in place.

        Args:
            labels (numpy.ndarray | None): Per-particle cluster ids.
        """
        S = self.S
        if labels is None:
            return
        L = np.asarray(labels)
        ids, counts = np.unique(L, return_counts=True)
        pairs = list(zip(ids.tolist(), counts.tolist()))
        pairs.sort(key=lambda p: (1, 0, 0) if p[0] < 0 else (0, -p[1], p[0]))
        hidden_n = max(0, len(pairs) - MAX_LEGEND_ROWS)
        if hidden_n:
            pairs = pairs[:MAX_LEGEND_ROWS]
        keys = [p[0] for p in pairs]

        if hidden_n != self._overflow_n:
            self._overflow_n = hidden_n
            self._crows = {}
        if set(keys) != set(self._crows):
            while self.cbox.count():
                w = self.cbox.takeAt(0).widget()
                if w:
                    w.deleteLater()
            self._crows = {}
            for c in keys:
                row = ClusterRow(c)
                row.clicked.connect(lambda cid=c: self.focus_cluster.emit(cid))
                row.alt_clicked.connect(lambda cid=c: self.toggle_cluster.emit(cid))
                row.icon_clicked.connect(lambda cid=c: self.recolor_cluster.emit(cid))
                self._crows[c] = row
                self.cbox.addWidget(row)
            if hidden_n:
                more = QLabel('+%s smaller clusters not listed' % f'{hidden_n:,}')
                more.setObjectName('legendMore')
                more.setStyleSheet('color:%s;font-size:10px;padding:2px 6px;'
                                   % THEME.muted)
                more.setWordWrap(True)
                self.cbox.addWidget(more)

        for c, n in pairs:
            row = self._crows.get(c)
            if row is None:
                continue
            row.set_color(S.cluster_color(c))
            row.set_state(c in S.hidden, S.focus == c, S.is_dimmed(c))
            row.setToolTip('Click to zoom back out' if S.focus == c
                           else 'Click to zoom to this cluster '
                                '(⌥-click to hide it)')
            name = self._cluster_name(L, labels, c)
            if row.nm.text() != name:
                row.nm.setText(name)
            row.ct.setText(str(n))

    def _rebuild_samples(self, labels):
        """Rebuild or update one row per sample, hiding the block if single.

        Counts exclude particles whose cluster is hidden, so the numbers track
        the visible scatter.

        Args:
            labels (numpy.ndarray | None): Per-particle cluster ids.
        """
        S = self.S
        multi = S.is_multi_sample()
        self.samp_head.setVisible(multi)
        for i in range(self.sbox.count()):
            w = self.sbox.itemAt(i).widget()
            if w:
                w.setVisible(multi)
        if not multi:
            return

        names = S.sample_names()
        src = (S.data or {}).get('samples')
        counts = {n: 0 for n in names}
        if src is not None:
            arr = np.asarray(src)
            keep = np.ones(len(arr), bool)
            if labels is not None and S.hidden:
                keep = ~np.isin(np.asarray(labels), list(S.hidden))
            for n in names:
                counts[n] = int(((arr == n) & keep).sum())

        if set(names) != set(self._srows):
            while self.sbox.count():
                w = self.sbox.takeAt(0).widget()
                if w:
                    w.deleteLater()
            self._srows = {}
            for n in names:
                row = SampleRow(n)
                row.clicked.connect(lambda nm=n: self.focus_sample.emit(nm))
                row.alt_clicked.connect(lambda nm=n: self.toggle_sample.emit(nm))
                row.icon_clicked.connect(
                    lambda nm=n: self.cycle_sample_shape.emit(nm))
                self._srows[n] = row
                self.sbox.addWidget(row)

        for n in names:
            row = self._srows.get(n)
            if row is None:
                continue
            row.set_shape(S.shape_for(n))
            row.set_state(n in S.sample_hidden, S.sample_focus == n,
                          S.is_sample_dimmed(n))
            row.setToolTip('Click to show every sample again'
                           if S.sample_focus == n
                           else 'Click to show only this sample '
                                '(⌥-click to hide it)')
            row.ct.setText(str(counts.get(n, 0)))

    def _rebuild_overlay(self):
        """Refresh the overlay colour bar, or hide it when no element is set.

        The bar reports the percentile bounds actually in use rather than the
        data minimum and maximum, so the scale on screen matches the scale the
        points were coloured with.
        """
        S = self.S
        ov = S.overlay
        show = ov is not None
        for w in (self.ov_head, self.ov_bar, self.ov_lo, self.ov_hi, self.ov_note):
            w.setVisible(show)
        if not show:
            return
        self.ov_head.setText(element_label_html(ov['key'], S.ui.label_mode))
        self.ov_lo.setText(fmt_overlay_value(ov['lo']))
        self.ov_hi.setText(fmt_overlay_value(ov['hi']))
        self.ov_note.setText('%d not detected' % (ov['total'] - ov['detected']))
        self.ov_bar.update()

    def apply_theme(self):
        """Restyle for the active palette.

        The frame comes from the enclosing floating box, so the panel itself
        stays transparent. Swatches and glyphs are cached by value, so their
        caches are cleared to force a repaint in the new colours.
        """
        self.setStyleSheet(
            'QWidget{background:transparent;color:%(text)s;}'
            'QLabel#legendHead{color:%(muted)s;font-size:10px;font-weight:600;'
            'letter-spacing:.06em;}'
            'QLabel#ovScale{color:%(muted)s;font-size:10px;}'
            'QLabel#legendCount{color:%(muted)s;font-size:11px;}'
            'QScrollBar:vertical{background:transparent;width:8px;margin:0;}'
            'QScrollBar::handle:vertical{background:%(stroke2)s;'
            'border-radius:4px;min-height:24px;}'
            'QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{'
            'height:0;}'
            % {'text': THEME.text, 'muted': THEME.muted,
               'stroke2': THEME.stroke2})
        for row in self._srows.values():
            row._shape = None
            row.set_shape(self.S.shape_for(row.name))
        for row in self._crows.values():
            row._col = None
            row.set_color(self.S.cluster_color(row.cid))
        self._top_labels = None
        self.ov_bar.update()
