"""The main cluster figure: points, centroids, axes, biplot and SOM overlay.

Two things are worth knowing before reading the drawing code.

*Point batching.* Points are grouped by ``(colour, dim state, shape)`` and each
group becomes one ``ScatterPlotItem`` with a single brush, which pyqtgraph
renders by caching one symbol pixmap and blitting it per point. Handing
pyqtgraph a per-point brush list instead collapses that optimisation and is
markedly slower.

*Text in device space.* The ``ViewBox`` owns the pan and zoom transform, so
anything drawn in data coordinates follows the view. That is right for lines
but wrong for text: a glyph would scale with the zoom and mirror on the
inverted y-axis. Tick labels, axis captions and biplot labels are therefore
painted with an identity transform, positioned through ``mapViewToDevice``.
"""

from __future__ import annotations

import math

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QToolTip

from .state import (DIM_ALPHA, FOCUS_MAX_ZOOM, ROT_EL_LIMIT, ROT_SENSITIVITY,
                    THEME, TWEEN_MS, cluster_tag, element_color,
                    element_label_text, marker_symbol, pale_color,
                    parse_element_label)
from .viewmath import (data_bounds2, data_bounds3, ease, fmt_tick, nice_ticks,
                       now_ms, rotate3)

_UNBOUNDED = QRectF(-1e12, -1e12, 2e12, 2e12)

#: Bit shift applied to the 256-step overlay ramp before grouping points for
#: drawing. Every distinct colour costs its own ``ScatterPlotItem`` and its own
#: ``setData`` call on every repaint, so drawing all 256 steps made colour-by-
#: element roughly thirty times heavier than colouring by cluster. Shifting by
#: three collapses the ramp to 32 draw bands, which is far more gradation than
#: is distinguishable in a scatter plot and leaves the legend's continuous
#: gradient untouched.
OVERLAY_SHIFT = 3

#: Offset to the centre of a draw band, so a band takes the colour of its middle
#: ramp step rather than its lower edge.
OVERLAY_MID = 1 << (OVERLAY_SHIFT - 1)

#: Roughly how many ticks each 3-D axis carries. The arms span the measured
#: range of their own channel, so this is a target for
#: :func:`~results.cluster.live_qt.viewmath.nice_ticks` to round against rather
#: than an exact count.
AXIS_TICK_TARGET = 5

#: How far past the end of a 3-D axis, in device pixels, its channel name is
#: written. The final tick label already occupies the arm's end, so a name drawn
#: there lands on top of it.
AXIS_NAME_GAP = 17.0


def _qcolor(spec, alpha=1.0):
    """Return a ``QColor`` from a palette string with an alpha multiplier.

    Args:
        spec (str): A ``#RRGGBB`` colour.
        alpha (float): Opacity in [0, 1].

    Returns:
        QColor: The colour, falling back to grey when unparseable.
    """
    c = QColor(spec)
    if not c.isValid():
        c = QColor('#888888')
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def rebuild_overlay(S):
    """Recompute the colour-by-element overlay, storing it on the state.

    Answers the same question the PCA biplot answers — where do the particles
    rich in this element sit — but by colouring the points, so it stays valid
    on t-SNE and UMAP where no element has a direction to point along.

    Composition data is heavily skewed, so the ramp spans the 2nd to 98th
    percentile of the *detected* values: one saturated particle would otherwise
    flatten every other point to the bottom of the scale. Particles where the
    element was not detected are flagged separately and drawn in the noise
    colour, since zero is a different statement from "a little".

    The result is stored as byte ramp indices so the draw loop does no
    arithmetic per point per frame.

    Args:
        S (LiveState): The view state, updated in place.
    """
    S.overlay = None
    key, d = S.ui.overlay_el, S.data
    if not key or not d or d.get('raw') is None or not d.get('elements'):
        return
    els = list(d['elements'])
    if key not in els:
        return
    j = els.index(key)

    raw = np.asarray(d['raw'], dtype=float)
    vals = np.nan_to_num(raw[:, j], nan=0.0, posinf=0.0, neginf=0.0)
    seen = vals[vals > 0]
    if seen.size == 0:
        return
    lo, hi = float(np.quantile(seen, 0.02)), float(np.quantile(seen, 0.98))
    if not (hi > lo):
        lo, hi = float(seen.min()), float(seen.max())
    if not (hi > lo):
        hi = lo + 1.0

    has = (vals > 0)
    idx = np.zeros(len(vals), dtype=np.uint8)
    idx[has] = np.round(
        np.clip((vals[has] - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
    S.overlay = {'key': key, 'col': j, 'lo': lo, 'hi': hi, 'idx': idx,
                 'has': has, 'vals': vals,
                 'detected': int(seen.size), 'total': int(len(vals))}


def axis_name(S, i):
    """Return the human label for a display axis.

    Args:
        S (LiveState): The view state.
        i (int): Axis index, 0 = x, 1 = y, 2 = z.

    Returns:
        str: For example ``'PC1 (63%)'``, ``'t-SNE 2'``, or an element name.
    """
    d = S.data or {}
    labels = d.get('axis_labels')
    if labels and i < len(labels) and labels[i]:
        return labels[i]
    p = d.get('projection') or 'PCA'
    if p == 'PCA':
        vr = d.get('var_ratio') or []
        v = vr[i] if i < len(vr) else None
        pct = '' if v is None or v != v else ' (%d%%)' % round(v * 100)
        return 'PC%d%s' % (i + 1, pct)
    return '%s %d' % (p, i + 1)


def axes_are_elements(S):
    """Report whether the axes are raw element channels.

    Args:
        S (LiveState): The view state.

    Returns:
        bool: True when no reduction is applied and axis labels exist.
    """
    d = S.data or {}
    return d.get('projection') == 'None' and bool(d.get('axis_labels'))


def _styled_font(painter, size, style, family=''):
    """Return a font at ``size`` pixels carrying the appearance settings.

    Args:
        painter (QPainter): Painter whose current font is the base.
        size (int): Pixel size.
        style (str): ``'normal'``, ``'bold'``, ``'italic'`` or both.
        family (str): Typeface name; empty keeps the system font. An
            unavailable family falls back to the system font automatically.

    Returns:
        QFont: The styled font.
    """
    f = QFont(painter.font())
    if family:
        f.setFamily(family)
    f.setPixelSize(max(6, int(round(size))))
    f.setBold('bold' in (style or ''))
    f.setItalic('italic' in (style or ''))
    return f


def draw_element_label(painter, key, x, y, size, align, mode, color,
                       style='normal', family=''):
    """Paint an element label, raising the mass in Atomic Notation mode.

    Rich text is not available when painting directly, so the mass digits are
    drawn smaller and lifted rather than marked up.

    Args:
        painter (QPainter): Active painter, in device coordinates.
        key (str): Element key.
        x (float): Anchor x in device pixels.
        y (float): Baseline y in device pixels.
        size (float): Base font size in pixels.
        align (str): ``'left'``, ``'right'`` or ``'center'``.
        mode (str): The element label style.
        color (str): Text colour as ``#RRGGBB``.
        style (str): Weight and slant, from the Appearance tab.
        family (str): Typeface name, from the Appearance tab.
    """
    sym, mass = parse_element_label(key)
    painter.setPen(QPen(_qcolor(color)))
    size = max(6, int(round(size)))
    f = _styled_font(painter, size, style, family)
    if mode != 'Atomic Notation' or not mass:
        text = element_label_text(key, mode)
        painter.setFont(f)
        w = painter.fontMetrics().horizontalAdvance(text)
        sx = x - w if align == 'right' else (x - w / 2 if align == 'center' else x)
        painter.drawText(QPointF(sx, y), text)
        return

    small = max(6, int(round(size * 0.68)))
    f.setPixelSize(small)
    painter.setFont(f)
    mw = painter.fontMetrics().horizontalAdvance(mass)
    f.setPixelSize(size)
    painter.setFont(f)
    sw = painter.fontMetrics().horizontalAdvance(sym)

    sx = x
    if align == 'right':
        sx = x - (mw + sw)
    elif align == 'center':
        sx = x - (mw + sw) / 2
    f.setPixelSize(small)
    painter.setFont(f)
    painter.drawText(QPointF(sx, y - size * 0.34), mass)
    f.setPixelSize(size)
    painter.setFont(f)
    painter.drawText(QPointF(sx + mw, y), sym)


class OriginAxes(pg.GraphicsObject):
    """Axes drawn as lines through the data origin, with ticks and captions.

    The graduations come from the *visible* range, so zooming changes the
    numbers rather than leaving an identical-looking frame.
    """

    def __init__(self, S):
        """Bind the axes to the view state and place them behind the points.

        Args:
            S (LiveState): The view state, for fonts and axis naming.
        """
        super().__init__()
        self.S = S
        self.setZValue(-5)

    def boundingRect(self):
        """Return a fixed, effectively unbounded rect.

        Returning the live view rect instead looks natural but is a trap: Qt
        caches an item's bounding rect and only re-reads it after
        ``prepareGeometryChange``, so a rect that silently tracks the ViewBox
        goes stale on every pan and forces the scene index to rebuild. A
        constant rect keeps the index stable; the item clips itself in paint.

        Returns:
            QRectF: A rect large enough to cover any view.
        """
        return _UNBOUNDED

    def _focus_mask(self):
        """Return a row selector for the focused cluster, or None.

        Returns:
            numpy.ndarray | None: Boolean mask over the embedding's rows when a
            cluster holds the focus and its labels line up with the data, else
            None.
        """
        S = self.S
        if S.focus is None:
            return None
        frame = S.current_frame()
        labels = frame.get('labels') if frame else None
        xy = (S.data or {}).get('xy')
        if labels is None or xy is None:
            return None
        labels = np.asarray(labels)
        if len(labels) != len(xy):
            return None
        return labels == S.focus

    def _paint3(self, painter, vb):
        """Draw the three data axes in 3-D, spanning the real data ranges.

        Each arm runs the full extent of its own channel, from the low corner
        of the cloud's bounding box to that channel's maximum, and its ticks
        are placed at round values inside that range. The whole thing lives in
        data coordinates, so the view box's zoom and pan carry it along with
        the particles: the axes grow as the reader zooms in, and a tick always
        sits beside the points whose value it states.

        The earlier version drew arms of a fixed screen length from the cloud's
        centre and derived tick values from that length, so the numbers bore no
        relation to the channel's actual range — an aluminium axis reaching 107
        counts was labelled to 16. Spanning the measured range instead is what
        makes the scale correct.

        Focusing a cluster narrows the range to that cluster's own points, so
        the ticks refine to its scale instead of staying at the whole cloud's.
        A cluster occupying a tenth of the spread is unreadable against ticks
        chosen for the other nine.

        Both passes clip to the view. :meth:`boundingRect` deliberately claims
        an unbounded rect to keep the scene index stable, which leaves the item
        responsible for staying inside the plot itself. Arms of a fixed screen
        length always did; arms that span the data do not once the reader zooms
        in, and without a clip they painted over the surrounding panels and left
        fragments of tick marks behind.

        Args:
            painter (QPainter): Active painter.
            vb (pg.ViewBox): The view box, for device mapping.
        """
        S = self.S
        bounds = data_bounds3(S, self._focus_mask())
        if bounds is None:
            return
        lo, hi = bounds
        if not (np.isfinite(lo).all() and np.isfinite(hi).all()):
            return
        if not np.any(hi - lo > 0):
            return

        ends = np.repeat(lo[None, :], 3, axis=0)
        for i in range(3):
            ends[i, i] = hi[i]
        pts = rotate3(S, np.vstack([lo[None, :], ends]))
        origin, arms = pts[0], pts[1:]

        painter.save()
        painter.setClipRect(vb.viewRect())
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(_qcolor(THEME.text), 0))
        for arm in arms:
            painter.drawLine(QPointF(origin[0], origin[1]),
                             QPointF(arm[0], arm[1]))
        painter.restore()

        marks, meta = [], []
        for i in range(3):
            values, step = nice_ticks(lo[i], hi[i], AXIS_TICK_TARGET)
            for value in values:
                point = lo.copy()
                point[i] = value
                marks.append(point)
                meta.append((i, value, step))
        if not marks:
            return
        marks = rotate3(S, np.asarray(marks))

        view = vb.viewRect()
        corner_a = vb.mapViewToDevice(QPointF(view.left(), view.top()))
        corner_b = vb.mapViewToDevice(QPointF(view.right(), view.bottom()))
        device_rect = QRectF(
            min(corner_a.x(), corner_b.x()), min(corner_a.y(), corner_b.y()),
            abs(corner_b.x() - corner_a.x()), abs(corner_b.y() - corner_a.y()))

        painter.save()
        painter.resetTransform()
        painter.setClipRect(device_rect)
        painter.setPen(QPen(_qcolor(THEME.text), 1))
        size = max(7, int(round(S.ui.font_size * 0.62)))
        painter.setFont(_styled_font(painter, size, S.ui.font_style, S.ui.font))
        metrics = painter.fontMetrics()
        device_origin = vb.mapViewToDevice(QPointF(origin[0], origin[1]))
        tick_px = max(3.0, 0.014 * min(abs(vb.width()), abs(vb.height())))

        normals, alongs = [], []
        for arm in arms:
            device_end = vb.mapViewToDevice(QPointF(arm[0], arm[1]))
            dx = device_end.x() - device_origin.x()
            dy = device_end.y() - device_origin.y()
            length = math.hypot(dx, dy) or 1.0
            normals.append((-dy / length * tick_px, dx / length * tick_px))
            alongs.append((dx / length, dy / length))

        for (axis, value, step), mark in zip(meta, marks):
            nx, ny = normals[axis]
            q = vb.mapViewToDevice(QPointF(mark[0], mark[1]))
            painter.drawLine(QPointF(q.x() - nx, q.y() - ny),
                             QPointF(q.x() + nx, q.y() + ny))
            label = fmt_tick(value, step)
            painter.drawText(
                QPointF(q.x() + nx * 2.1 - metrics.horizontalAdvance(label) / 2.0,
                        q.y() + ny * 2.1 + metrics.ascent() / 2.0), label)

        cap = max(8, int(round(S.ui.font_size * 0.85)))
        painter.setFont(_styled_font(painter, cap, S.ui.font_style, S.ui.font))
        metrics = painter.fontMetrics()
        for i, arm in enumerate(arms):
            device_end = vb.mapViewToDevice(QPointF(arm[0], arm[1]))
            nx, ny = normals[i]
            ux, uy = alongs[i]
            tip_x = device_end.x() + ux * AXIS_NAME_GAP + nx * 1.4
            tip_y = device_end.y() + uy * AXIS_NAME_GAP + ny * 1.4
            name = axis_name(S, i)
            if axes_are_elements(S):
                draw_element_label(painter, name, tip_x, tip_y, cap, 'center',
                                   S.ui.label_mode, THEME.text, S.ui.font_style,
                                   S.ui.font)
            else:
                painter.drawText(
                    QPointF(tip_x - metrics.horizontalAdvance(name) / 2.0,
                            tip_y), name)
        painter.restore()

    def paint(self, painter, *_):
        """Draw the axis cross, ticks and captions.

        Lines are drawn in data coordinates so they follow the view; all text
        is drawn in device pixels for the reasons given in the module
        docstring.

        Args:
            painter (QPainter): Active painter.
        """
        vb = self.getViewBox()
        if vb is None or not self.S.data or self.S.data.get('empty'):
            return
        S = self.S
        if S.cur_dims() == 3:
            self._paint3(painter, vb)
            return
        vr = vb.viewRect()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(_qcolor(THEME.text), 0))

        ox = min(max(0.0, vr.left()), vr.right())
        oy = min(max(0.0, vr.top()), vr.bottom())
        painter.drawLine(QPointF(vr.left(), oy), QPointF(vr.right(), oy))
        painter.drawLine(QPointF(ox, vr.top()), QPointF(ox, vr.bottom()))

        xs, xstep = nice_ticks(vr.left(), vr.right(), 8)
        ys, ystep = nice_ticks(vr.top(), vr.bottom(), 6)

        painter.save()
        painter.resetTransform()
        painter.setPen(QPen(_qcolor(THEME.text), 1))

        size = max(7, int(round(S.ui.font_size * 0.68)))
        f = _styled_font(painter, size, S.ui.font_style, S.ui.font)
        painter.setFont(f)
        fm = painter.fontMetrics()

        origin = vb.mapViewToDevice(QPointF(ox, oy))
        d_ox, d_oy = origin.x(), origin.y()

        for v in xs:
            if v == 0:
                continue
            p = vb.mapViewToDevice(QPointF(v, oy))
            painter.drawLine(QPointF(p.x(), d_oy - 3), QPointF(p.x(), d_oy + 3))
            label = fmt_tick(v, xstep)
            painter.drawText(
                QPointF(p.x() - fm.horizontalAdvance(label) / 2.0,
                        d_oy + 5 + fm.ascent()), label)

        for v in ys:
            if v == 0:
                continue
            p = vb.mapViewToDevice(QPointF(ox, v))
            painter.drawLine(QPointF(d_ox - 3, p.y()), QPointF(d_ox + 3, p.y()))
            painter.drawText(QPointF(d_ox + 6, p.y() + fm.ascent() / 2.0 - 1),
                             fmt_tick(v, ystep))

        cap = max(8, int(round(S.ui.font_size * 0.85)))
        f = _styled_font(painter, cap, S.ui.font_style, S.ui.font)
        painter.setFont(f)
        fm = painter.fontMetrics()
        mode = S.ui.label_mode
        tl = vb.mapViewToDevice(QPointF(vr.left(), vr.top()))
        br = vb.mapViewToDevice(QPointF(vr.right(), vr.bottom()))
        right = max(tl.x(), br.x())
        top = min(tl.y(), br.y())

        if axes_are_elements(S):
            draw_element_label(painter, axis_name(S, 0), right - 8, d_oy - 5,
                               cap, 'right', mode, THEME.text, S.ui.font_style,
                               S.ui.font)
            draw_element_label(painter, axis_name(S, 1), d_ox + 6,
                               top + 8 + cap, cap, 'left', mode, THEME.text,
                               S.ui.font_style, S.ui.font)
        else:
            t0 = axis_name(S, 0)
            painter.drawText(
                QPointF(right - 8 - fm.horizontalAdvance(t0), d_oy - 5), t0)
            painter.drawText(QPointF(d_ox + 6, top + 8 + cap), axis_name(S, 1))
        painter.restore()


def biplot_vectors(S):
    """Return the element loading arrows for the current PCA view.

    An element's loading says how strongly it pushes along each plotted
    component, so the arrow points the way particles rich in it lie. Only the
    longest ``S.ui.biplot_n`` are returned — every element at once is
    unreadable, and the short arrows carry least information.

    Args:
        S (LiveState): The view state.

    Returns:
        list[dict]: ``{'key', 'vec', 'len'}`` longest first, empty when the
        view is not a PCA of the element columns or the arrows are off.
    """
    d = S.data or {}
    if not S.ui.biplot_on or d.get('projection') != 'PCA':
        return []
    L, els = d.get('loadings'), d.get('elements')
    if L is None or not els or len(L) != len(els):
        return []
    dims = S.cur_dims()
    raw = []
    for j, key in enumerate(els):
        v = L[j]
        if v is None:
            continue
        raw.append((key, [v[0] or 0, v[1] or 0,
                          (v[2] or 0) if dims == 3 and len(v) > 2 else 0]))
    if not raw:
        return []

    spun = rotate3(S, [vec for _, vec in raw], center=False)
    out = []
    for (key, vec), r in zip(raw, spun):
        ln = math.hypot(*vec)
        if not (ln > 1e-9):
            continue
        out.append({'key': key, 'vec': [r[0], r[1], r[2]], 'len': ln})
    out.sort(key=lambda o: -o['len'])
    return out[:max(1, S.ui.biplot_n)]


class BiplotArrows(pg.GraphicsObject):
    """One labelled arrow per element, radiating from the cloud's centre.

    PCA is mean-centred, so the data origin *is* the centre of the cloud and
    every arrow starts there. All arrows share one scale factor chosen so the
    longest reaches a fixed fraction of the visible cloud — lengths stay
    comparable while the group always fits on screen at any zoom.
    """

    def __init__(self, S):
        """Bind the arrows to the view state and place them above the points.

        Args:
            S (LiveState): The view state, for the loadings and arrow count.
        """
        super().__init__()
        self.S = S
        self.setZValue(6)

    def boundingRect(self):
        """Return a fixed, effectively unbounded rect.

        Returns:
            QRectF: A rect large enough to cover any view.
        """
        return _UNBOUNDED

    def paint(self, painter, *_):
        """Draw one labelled arrow per element, longest first.

        Args:
            painter (QPainter): Active painter.
        """
        S = self.S
        vecs = biplot_vectors(S)
        if not vecs:
            return
        b = data_bounds2((S.data or {}).get('xy'))
        if not b:
            return
        span = max(b[2] - b[0], b[3] - b[1])
        if not (span > 0):
            return
        vb = self.getViewBox()
        if vb is None:
            return

        k = (span * 0.42) / vecs[0]['len']
        px, py = vb.viewPixelSize()
        head = max(5.0, S.ui.font_size * 0.42)
        els = (S.data or {}).get('elements') or []
        painter.setRenderHint(QPainter.Antialiasing, True)

        for v in vecs:
            ex, ey = v['vec'][0] * k, v['vec'][1] * k
            dx, dy = ex / px, -ey / py
            ln = math.hypot(dx, dy)
            if ln < 2:
                continue
            uxv, uyv = dx / ln, dy / ln
            col = element_color(v['key'], els)
            pale = pale_color(col, 0.52)

            painter.setPen(QPen(_qcolor(pale), 1.6 * px))
            painter.drawLine(QPointF(0, 0), QPointF(ex, ey))

            tipx, tipy = ex, ey
            bx, by = uxv * head * px, -uyv * head * py
            nx, ny = -uyv * head * 0.42 * px, -uxv * head * 0.42 * py
            poly = QPolygonF([QPointF(tipx, tipy),
                              QPointF(tipx - bx - nx, tipy - by - ny),
                              QPointF(tipx - bx + nx, tipy - by + ny)])
            painter.setBrush(_qcolor(pale))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(poly)

            lx = tipx + uxv * head * 1.5 * px
            ly = tipy - uyv * head * 1.5 * py
            painter.save()
            painter.resetTransform()
            dev = vb.mapViewToDevice(QPointF(lx, ly))
            align = 'right' if uxv < -0.15 else ('left' if uxv > 0.15 else 'center')
            draw_element_label(painter, v['key'], dev.x(), dev.y(),
                               max(7, int(round(S.ui.font_size * 0.78))), align,
                               S.ui.label_mode, col, S.ui.font_style, S.ui.font)
            painter.restore()


class Centroids(pg.GraphicsObject):
    """Cluster centroids as ringed markers: halo, solid core, contrast ring.

    Drawn as one item rather than a scatter because each centroid is three
    concentric strokes in two colours, and there are only ever a handful.
    """

    def __init__(self, S):
        """Bind the centroids to the view state and place them above the points.

        Args:
            S (LiveState): The view state, for colours and centroid size.
        """
        super().__init__()
        self.S = S
        self.cen = None
        self.setZValue(10)

    def set_centroids(self, cen):
        """Adopt a new centroid array and repaint.

        Args:
            cen (array-like | None): One row per cluster, or None to clear.
        """
        self.cen = None if cen is None else np.asarray(cen, dtype=float)
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self):
        """Return a fixed, effectively unbounded rect.

        Returns:
            QRectF: A rect large enough to cover any view.
        """
        return _UNBOUNDED

    def paint(self, painter, *_):
        """Draw each centroid as a halo, a solid core and a contrast ring.

        Dimmed centroids paint first so the focused cluster ends up on top.

        Args:
            painter (QPainter): Active painter.
        """
        S, cen = self.S, self.cen
        vb = self.getViewBox()
        if cen is None or len(cen) == 0 or vb is None:
            return
        px, py = vb.viewPixelSize()
        painter.setRenderHint(QPainter.Antialiasing, True)

        order = [k for k in range(len(cen)) if k not in S.hidden]
        order.sort(key=lambda k: 1 if S.is_dimmed(k) else 0)

        R = max(2.0, S.ui.cent_size)
        halo, ring = R * 1.69, R * 1.38
        for k in order:
            x, y = float(cen[k][0]), float(cen[k][1])
            col = S.cluster_color(k)
            a = DIM_ALPHA if S.is_dimmed(k) else 1.0

            painter.setPen(Qt.NoPen)
            painter.setBrush(_qcolor(col, 0.22 * a))
            painter.drawEllipse(QPointF(x, y), halo * px, halo * py)

            painter.setBrush(_qcolor(col, a))
            painter.setPen(QPen(_qcolor(THEME.bg, a), max(1.5, R * 0.38) * px))
            painter.drawEllipse(QPointF(x, y), R * px, R * py)

            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(_qcolor(THEME.text, 0.8 * a), 1.5 * px))
            painter.drawEllipse(QPointF(x, y), ring * px, ring * py)


class SomOverlay(pg.GraphicsObject):
    """The self-organising-map neuron grid drawn over the particles."""

    def __init__(self, S):
        """Bind the overlay to the view state.

        Args:
            S (LiveState): The view state.
        """
        super().__init__()
        self.S = S
        self.nodes = None
        self.edges = None
        self.setZValue(5)

    def set_grid(self, nodes, edges):
        """Adopt a new neuron grid and repaint.

        Args:
            nodes (array-like | None): Neuron positions in data space.
            edges (list[tuple[int, int]] | None): Index pairs joining neurons.
        """
        self.nodes = None if nodes is None else np.asarray(nodes, dtype=float)
        self.edges = edges or []
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self):
        """Return a fixed, effectively unbounded rect.

        Returns:
            QRectF: A rect large enough to cover any view.
        """
        return _UNBOUNDED

    def paint(self, painter, *_):
        """Draw the neuron grid: edges first, then the neurons.

        Args:
            painter (QPainter): Active painter.
        """
        vb = self.getViewBox()
        if self.nodes is None or len(self.nodes) == 0 or vb is None:
            return
        px, py = vb.viewPixelSize()
        painter.setRenderHint(QPainter.Antialiasing, True)
        N = self.nodes

        painter.setPen(QPen(_qcolor(THEME.text, 0.28), 1.2 * px))
        for a, b in (self.edges or []):
            if a < len(N) and b < len(N):
                painter.drawLine(QPointF(N[a][0], N[a][1]),
                                 QPointF(N[b][0], N[b][1]))
        painter.setPen(Qt.NoPen)
        painter.setBrush(_qcolor(THEME.text))
        for p in N:
            painter.drawEllipse(QPointF(p[0], p[1]), 3.2 * px, 3.2 * py)


def sphere_rect(S, xy):
    """Frame the 3-D cloud by its bounding sphere.

    Framing the rotated bounding box instead would make the view breathe as
    the cloud spins, and could swing points outside the pane. The radius to
    the furthest point is rotation-invariant, so a square built from it holds
    the whole cloud at every angle.

    Args:
        S (LiveState): The view state.
        xy (array-like): The embedding, ``(n, 2+)``.

    Returns:
        QRectF | None: The square to frame, or None without usable data.
    """
    P = np.asarray(xy, dtype=float)
    if P.ndim != 2 or P.size == 0:
        return None
    if P.shape[1] < 3:
        P = np.column_stack([P[:, :2], np.zeros(len(P))])
    c = P[:, :3].mean(axis=0)
    r = float(np.linalg.norm(P[:, :3] - c, axis=1).max())
    if not (r > 0):
        r = 1e-6
    return QRectF(c[0] - r, c[1] - r, 2 * r, 2 * r)


def focus_rect(S, c):
    """Return the data-space rect to frame when focusing a cluster.

    Applies an 18% margin, a floor of 2% of the cloud's larger span so a
    collapsed cluster cannot divide by zero, and a clamp so the result is never
    more than :data:`~results.cluster.live_qt.state.FOCUS_MAX_ZOOM` times
    tighter than the fitted view.

    Args:
        S (LiveState): The view state.
        c (int | None): Cluster id, or None for the whole cloud.

    Returns:
        QRectF | None: The rect to frame, or None when it cannot be computed.
    """
    xy = (S.data or {}).get('xy')
    if xy is None or len(xy) == 0:
        return None
    if c is None and S.cur_dims() == 3:
        return sphere_rect(S, xy)
    b = data_bounds2(rotate3(S, xy)[:, :2])
    if b is None:
        return None
    if c is None:
        return QRectF(b[0], b[1], b[2] - b[0], b[3] - b[1])

    fr = S.current_frame()
    labels = fr.get('labels') if fr else None
    if labels is None:
        return None
    P = rotate3(
        S, fr.get('positions') if fr.get('positions') is not None else xy)[:, :2]
    m = np.asarray(labels) == c
    if not m.any() or len(m) != len(P):
        return None

    sel = P[m]
    x0, y0 = float(sel[:, 0].min()), float(sel[:, 1].min())
    x1, y1 = float(sel[:, 0].max()), float(sel[:, 1].max())
    min_span = max(b[2] - b[0], b[3] - b[1]) * 0.02 or 1e-6
    if x1 - x0 < min_span:
        mid = (x0 + x1) / 2
        x0, x1 = mid - min_span / 2, mid + min_span / 2
    if y1 - y0 < min_span:
        mid = (y0 + y1) / 2
        y0, y1 = mid - min_span / 2, mid + min_span / 2
    mx, my = (x1 - x0) * 0.18, (y1 - y0) * 0.18
    x0, x1, y0, y1 = x0 - mx, x1 + mx, y0 - my, y1 + my

    full_w, full_h = (b[2] - b[0]) or 1e-9, (b[3] - b[1]) or 1e-9
    min_w, min_h = full_w / FOCUS_MAX_ZOOM, full_h / FOCUS_MAX_ZOOM
    if (x1 - x0) < min_w:
        mid = (x0 + x1) / 2
        x0, x1 = mid - min_w / 2, mid + min_w / 2
    if (y1 - y0) < min_h:
        mid = (y0 + y1) / 2
        y0, y1 = mid - min_h / 2, mid + min_h / 2
    return QRectF(x0, y0, x1 - x0, y1 - y0)


class _RotateViewBox(pg.ViewBox):
    """A view box whose left-drag spins the cloud when the view is 3-D.

    Panning a 3-D view has no meaning while the camera looks at a fixed
    centre, so the gesture is reused for rotation. Everything else — wheel
    zoom, right-drag, the auto-range button — keeps the inherited behaviour.
    """

    def __init__(self, S, on_rotate, parent=None):
        """Bind the box to the view state and the redraw callback.

        Args:
            S (LiveState): The view state, for ``rot`` and the current dims.
            on_rotate (callable): Called after each rotation change.
            parent (QGraphicsItem | None): Parent item.
        """
        super().__init__(parent)
        self.S = S
        self._on_rotate = on_rotate
        self._anchor = None

    def mouseDragEvent(self, ev, axis=None):
        """Rotate on left-drag in 3-D, otherwise pan as usual.

        Args:
            ev (MouseDragEvent): The drag event.
            axis (int | None): Axis the drag is constrained to, if any.
        """
        if axis is not None or self.S.cur_dims() != 3 \
                or ev.button() != Qt.MouseButton.LeftButton:
            super().mouseDragEvent(ev, axis=axis)
            return
        ev.accept()
        if ev.isStart() or self._anchor is None:
            self._anchor = (self.S.rot['az'], self.S.rot['el'])
        d = ev.pos() - ev.buttonDownPos()
        az0, el0 = self._anchor
        self.S.rot['az'] = az0 + d.x() * ROT_SENSITIVITY
        self.S.rot['el'] = max(-ROT_EL_LIMIT,
                               min(ROT_EL_LIMIT,
                                   el0 + d.y() * ROT_SENSITIVITY))
        if ev.isFinish():
            self._anchor = None
        self._on_rotate()


class ClusterScatter(pg.PlotWidget):
    """The 2-D particle figure.

    Emits :attr:`hovered` with the particle index under the cursor, or -1 when
    none, which the parent uses to drive the tooltip and the hover ring.
    """

    hovered = Signal(int)
    rotated = Signal()

    def __init__(self, S, parent=None):
        """Build the figure and its permanent items.

        Args:
            S (LiveState): The view state to draw from.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent, background=THEME.bg,
                         viewBox=_RotateViewBox(
                             S, lambda: self._on_rotate_drag()))
        self.S = S
        self.setMenuEnabled(False)
        self.setAntialiasing(False)
        self.hideAxis('bottom')
        self.hideAxis('left')

        self.scene().setItemIndexMethod(self.scene().ItemIndexMethod.NoIndex)
        self.setViewportUpdateMode(
            self.ViewportUpdateMode.FullViewportUpdate)

        vb = self.getPlotItem().getViewBox()
        vb.setAspectLocked(True)
        vb.setMouseEnabled(x=True, y=True)

        self._groups = {}
        self.axes = OriginAxes(S)
        self.biplot = BiplotArrows(S)
        self.som = SomOverlay(S)
        self.centroids = Centroids(S)
        self.hover_ring = pg.ScatterPlotItem(
            pxMode=True, symbol='o', brush=None,
            pen=pg.mkPen(THEME.text, width=2))
        self.hover_ring.setZValue(20)

        for item in (self.axes, self.som, self.biplot,
                     self.centroids, self.hover_ring):
            self.addItem(item)

        self._pos = None
        self._labels = None
        self._zoom_from = None
        self._zoom_to = None
        self._zoom_t0 = 0.0
        self._zoom_timer = QTimer(self)
        self._zoom_timer.timeout.connect(self._step_zoom)
        self.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def _on_rotate_drag(self):
        """Abandon any gliding zoom and republish the spun frame.

        A focus animation retargets the range every tick, so letting it run
        during a drag would fight the rotation for control of the view.
        """
        self._zoom_timer.stop()
        self._zoom_from = self._zoom_to = None
        self.rotated.emit()

    def _item(self, key, shape):
        """Fetch or create the scatter item for one group.

        Args:
            key (tuple): ``(colour, dim, shape)`` identifying the group.
            shape (str): The marker shape.

        Returns:
            pg.ScatterPlotItem: The item for that group.
        """
        it = self._groups.get(key)
        if it is None:
            it = pg.ScatterPlotItem(pxMode=True, symbol=marker_symbol(shape),
                                    pen=None, useCache=True)
            self.addItem(it)
            self._groups[key] = it
        return it

    def set_frame(self, pos, labels, centroids=None, som=None):
        """Draw one frame.

        Points are grouped by ``(colour, dim state, shape)`` and each group
        gets one ``setData`` call with one brush. Dimmed groups take a lower Z
        so the focused cluster paints over them.

        Args:
            pos (array-like): Point coordinates in data space.
            labels (array-like): Cluster id per point.
            centroids (array-like | None): One row per cluster.
            som (dict | None): ``{'nodes', 'edges'}`` for the SOM overlay.
        """
        S = self.S
        R = rotate3(S, pos)
        P, depth = R[:, :2], R[:, 2]
        L = np.asarray(labels)
        self._pos, self._labels = P, L
        r = S.point_radius()

        hidden_c = np.isin(L, list(S.hidden)) if S.hidden else np.zeros(len(L), bool)
        if S.sample_hidden:
            samples = np.asarray((S.data or {}).get('samples'))
            hidden_s = np.isin(samples, list(S.sample_hidden))
        else:
            hidden_s = np.zeros(len(L), bool)
        visible = ~(hidden_c | hidden_s)

        groups = {}
        ov = S.overlay
        samples = np.asarray((S.data or {}).get('samples')) \
            if S.is_multi_sample() else None

        for c in np.unique(L):
            c = int(c)
            base = np.flatnonzero(visible & (L == c))
            if base.size == 0:
                continue
            dim = S.is_dimmed(c)
            if ov is None:
                colour_keys = [(S.cluster_color(c), base)]
            else:
                sub = []
                det = base[ov['has'][base]]
                und = base[~ov['has'][base]]
                if und.size:
                    sub.append((THEME.noise, und))
                if det.size:
                    bands = ov['idx'][det] >> OVERLAY_SHIFT
                    for band in np.unique(bands):
                        sel = det[bands == band]
                        sub.append((S.ramp_color(
                            (int(band) << OVERLAY_SHIFT) + OVERLAY_MID), sel))
                colour_keys = sub

            for colour, idxs in colour_keys:
                if samples is None:
                    parts = [('circle', idxs, False)]
                else:
                    parts = [(S.shape_for(name),
                              idxs[samples[idxs] == name],
                              S.is_sample_dimmed(name))
                             for name in np.unique(samples[idxs])]
                for shape, sel, sdim in parts:
                    if sel.size == 0:
                        continue
                    groups.setdefault((colour, bool(dim or sdim), shape),
                                      []).append(sel)

        seen = set()
        three = S.cur_dims() == 3
        for (colour, dim, shape), chunks in groups.items():
            idxs = np.concatenate(chunks)
            if three:
                idxs = idxs[np.argsort(depth[idxs], kind='stable')]
            it = self._item((colour, dim, shape), shape)
            faint = 0.45 if colour == THEME.noise else 0.88
            alpha = faint * (DIM_ALPHA if dim else 1.0)
            it.setData(x=P[idxs, 0], y=P[idxs, 1],
                       brush=pg.mkBrush(_qcolor(colour, alpha)), size=r * 2)
            it.setZValue(0 if dim else 1)
            seen.add((colour, dim, shape))

        for key, it in self._groups.items():
            if key not in seen:
                it.setData(x=[], y=[])

        self.centroids.set_centroids(
            None if centroids is None else rotate3(S, centroids)[:, :2])
        if som and som.get('nodes') is not None:
            self.som.set_grid(rotate3(S, som['nodes'])[:, :2],
                              som.get('edges'))
        else:
            self.som.set_grid(None, None)
        self.axes.update()
        self.biplot.update()

    def fit(self, animate=False):
        """Frame the whole point cloud.

        Args:
            animate (bool): Glide to the new framing instead of jumping.
        """
        rect = focus_rect(self.S, None)
        if rect is not None:
            self._set_range(rect, 0.06, animate)

    def focus(self, c, animate=True):
        """Frame one cluster, or the whole cloud.

        Args:
            c (int | None): Cluster id, or None for everything.
            animate (bool): Glide to the new framing instead of jumping.
        """
        rect = focus_rect(self.S, c)
        if rect is not None:
            self._set_range(rect, 0.0 if c is not None else 0.06, animate)

    def _set_range(self, rect, padding, animate):
        """Move the view to a rect, optionally gliding there.

        Snapping straight to a focused cluster loses the sense of where it sat
        in the cloud. Easing over :data:`~results.cluster.live_qt.state.TWEEN_MS`
        keeps that context, which is what makes the zoom readable rather than
        disorienting.

        Args:
            rect (QRectF): Target rect in data coordinates.
            padding (float): Fractional margin passed to the ViewBox.
            animate (bool): Glide instead of jumping.
        """
        vb = self.getPlotItem().getViewBox()
        target = QRectF(rect)
        if padding:
            dx, dy = target.width() * padding, target.height() * padding
            target.adjust(-dx, -dy, dx, dy)
        if not animate:
            self._zoom_timer.stop()
            vb.setRange(target, padding=0.0)
            return
        cur = vb.viewRect()
        self._zoom_from = QRectF(cur)
        self._zoom_to = target
        self._zoom_t0 = now_ms()
        if not self._zoom_timer.isActive():
            self._zoom_timer.start(16)

    def _step_zoom(self):
        """Advance the view glide by one frame, stopping when it arrives."""
        if self._zoom_to is None:
            self._zoom_timer.stop()
            return
        k = min(1.0, (now_ms() - self._zoom_t0) / TWEEN_MS)
        e = ease(k)
        a, b = self._zoom_from, self._zoom_to

        def mix(x, y):
            """Interpolate one edge at the eased fraction.

            Args:
                x (float): Start value.
                y (float): End value.

            Returns:
                float: The interpolated value.
            """
            return x + (y - x) * e

        self.getPlotItem().getViewBox().setRange(
            QRectF(mix(a.left(), b.left()), mix(a.top(), b.top()),
                   mix(a.width(), b.width()), mix(a.height(), b.height())),
            padding=0.0)
        if k >= 1.0:
            self._zoom_timer.stop()
            self._zoom_to = None

    def _on_mouse_moved(self, scene_pos):
        """Find the particle nearest the cursor within twelve device pixels.

        Args:
            scene_pos (QPointF): Cursor position in scene coordinates.
        """
        if self._pos is None or not self.getPlotItem().sceneBoundingRect().contains(scene_pos):
            self._set_hover(-1)
            return
        vb = self.getPlotItem().getViewBox()
        pt = vb.mapSceneToView(scene_pos)
        px, py = vb.viewPixelSize()
        dx = (self._pos[:, 0] - pt.x()) / px
        dy = (self._pos[:, 1] - pt.y()) / py
        d2 = dx * dx + dy * dy
        i = int(np.argmin(d2))
        self._set_hover(i if d2[i] < 144 else -1)

    def _set_hover(self, i):
        """Move the hover ring to a particle and announce the change.

        Args:
            i (int): Particle index, or -1 when the cursor is over nothing.
        """
        if i == self.S.hover_idx:
            return
        self.S.hover_idx = i
        if i < 0 or self._pos is None:
            self.hover_ring.setData(x=[], y=[])
            QToolTip.hideText()
        else:
            r = self.S.point_radius()
            self.hover_ring.setData(x=[self._pos[i, 0]], y=[self._pos[i, 1]],
                                    size=(r + 3) * 2)
        self.hovered.emit(i)

    def hover_html(self, i):
        """Build the tooltip markup for one particle.

        Args:
            i (int): Particle index.

        Returns:
            str: Rich text naming the cluster, the sample and the top five
            detected elements, or '' when the particle cannot be described.
        """
        S = self.S
        d = S.data or {}
        raw, els = d.get('raw'), d.get('elements') or []
        if raw is None or i >= len(raw):
            return ''
        from .state import element_label_html
        row = np.asarray(raw[i], dtype=float)
        pairs = sorted(((els[j], row[j]) for j in range(len(els)) if row[j] > 0),
                       key=lambda p: -p[1])[:5]
        fr = S.current_frame()
        cl = int(fr['labels'][i]) if fr and fr.get('labels') is not None else -1
        out = ['<b>%s</b> <span style="color:%s">&#9679;</span>'
               % (cluster_tag(cl), S.cluster_color(cl))]
        if S.is_multi_sample():
            out.append('<br>Sample: <b>%s</b>' % S.sample_of(i))
        for key, val in pairs:
            out.append('<br>%s: <b>%g</b>'
                       % (element_label_html(key, S.ui.label_mode), val))
        return ''.join(out)

    def apply_theme(self):
        """Repaint after a palette change."""
        self.setBackground(THEME.bg)
        self.hover_ring.setPen(pg.mkPen(THEME.text, width=2))
        self.axes.update()
        self.biplot.update()
        self.centroids.update()
        self.som.update()
