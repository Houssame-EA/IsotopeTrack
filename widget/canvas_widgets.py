from PySide6.QtWidgets import (
    QDialog, QMenu, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QGraphicsObject, QLabel, QCheckBox,
    QFrame, QScrollArea, QSplitter, QGraphicsWidget,
    QGraphicsEllipseItem, QApplication, QDialogButtonBox, QLineEdit, QToolTip,
    QSizePolicy, QMessageBox
)
from PySide6.QtCore import (
    Qt, Signal, QPointF, QRectF, QMimeData, QPoint, QObject, QEvent, QRect,
    QTimer, QSize, QThread,
    QPropertyAnimation, QParallelAnimationGroup, QSequentialAnimationGroup,
    QPauseAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QDrag, QPixmap, QPainterPath, QCursor,
    QLinearGradient, QFont, QPainterPathStroker, QRadialGradient,QFontMetrics,
    QShortcut, QKeySequence, QIcon, QTransform, QCursor, QWheelEvent
)
import numpy as np
from collections import deque
from pathlib import Path

from results.results_pie_charts import (
    PieChartDisplayDialog, PieChartPlotNode,
    ElementCompositionDisplayDialog, ElementCompositionPlotNode,
)
from results.results_reader import (      
    integrate_insights_panel,
    make_insights_toggle_button,
)

from results.results_heatmap import HeatmapDisplayDialog, HeatmapPlotNode
from results.results_bar_charts import (
    ElementBarChartDisplayDialog, ElementBarChartPlotNode,
    HistogramPlotNode, HistogramDisplayDialog,
)
from results.results_correlation import CorrelationPlotDisplayDialog, CorrelationPlotNode
from results.results_isotope import IsotopicRatioDisplayDialog, IsotopicRatioPlotNode
from results.results_cluster import ClusteringDisplayDialog, ClusteringPlotNode
from results.results_triangle import TriangleDisplayDialog, TrianglePlotNode
from results.results_AI import AIAssistantNode
from results.results_box_plot import BoxPlotDisplayDialog, BoxPlotNode
from results.results_molar_ratio import MolarRatioDisplayDialog, MolarRatioPlotNode
from results.results_single_multiple import (
    SingleMultipleElementDisplayDialog, SingleMultipleElementPlotNode,
)
from results.results_matrix import (
    CorrelationMatrixDisplayDialog, CorrelationMatrixNode,
)
from results.results_concentration import (
    ConcentrationDisplayDialog, ConcentrationComparisonNode,
)
from results.results_network import (
    NetworkDisplayDialog, NetworkDiagramNode)
from results.results_dashboard import DashboardDisplayDialog, DashboardNode
from results.results_periodic import IsotopeChipSelector
from tools.particle_filter import (
    ParticleFilterNode, build_particle_filter_node_item)
from tools.particle_classifier_node import (
    ParticleClassifierNode, build_particle_classifier_node_item,
    is_allowed_upstream, is_allowed_downstream, EXCLUDED_DOWNSTREAM_TYPES,
    maybe_show_classifier_onboarding)

import qtawesome as qta

from tools.theme import theme as _app_theme
import logging
_itk_log = logging.getLogger("IsotopeTrack.widget.canvas_widgets")

# ── user-action logging ──────────────────────────────────────────────────────
def _ual():
    """Return the UserActionLogger, or None if logging isn't ready."""
    try:
        from tools.logging_utils import logging_manager
        return logging_manager.get_user_action_logger()
    except Exception:
        _itk_log.exception("Handled exception in _ual")
        return None

def _collect_main_windows():
    """
    Return every visible MainWindow in this process.

    Uses ``QApplication.topLevelWidgets`` so that windows opened via the
    Windows taskbar (which bypass the ``app.main_windows`` list) are also
    included.  Identifies MainWindow instances by the presence of
    ``window_number`` to avoid a circular import with mainwindow.py.

    Args:
        None

    Returns:
        list: Visible top-level widgets that are MainWindow instances,
            sorted by ``window_number``.
    """
    windows = [
        w for w in QApplication.topLevelWidgets()
        if hasattr(w, 'window_number') and w.isVisible()
    ]
    windows.sort(key=lambda w: getattr(w, 'window_number', 0))
    return windows


def _sample_concentration_meta(window, sample_name):
    """
    Build the per sample concentration metadata for a source window.

    Args:
        window (Any): The owning main window exposing the concentration helpers.
        sample_name (str): Sample identifier within that window.

    Returns:
        dict: Mapping with volume_ml, dilution_factor and te_available keys.
    """
    if window is None or not hasattr(window, 'effective_volume_ml'):
        return {'volume_ml': 0.0, 'dilution_factor': 1.0, 'te_available': False}
    try:
        return {
            'volume_ml': window.effective_volume_ml(sample_name),
            'dilution_factor': window.get_sample_dilution(sample_name),
            'te_available': window.has_transport_rate(),
        }
    except Exception:
        _itk_log.exception("Handled exception in _sample_concentration_meta")
        return {'volume_ml': 0.0, 'dilution_factor': 1.0, 'te_available': False}


def _combine_concentration_meta(metas):
    """
    Combine per member concentration metadata into a single entry.

    Volumes add together, the dilution factor is taken from the first member,
    and transport availability requires every member to provide it.

    Args:
        metas (list): List of per member metadata dicts.

    Returns:
        dict: Combined metadata with volume_ml, dilution_factor and te_available.
    """
    metas = [m for m in metas if m]
    if not metas:
        return {'volume_ml': 0.0, 'dilution_factor': 1.0, 'te_available': False}
    return {
        'volume_ml': sum(m.get('volume_ml', 0.0) for m in metas),
        'dilution_factor': metas[0].get('dilution_factor', 1.0),
        'te_available': all(m.get('te_available', False) for m in metas),
    }


class DS:

    BG_PRIMARY    = "#0F172A"
    BG_SECONDARY  = "#1E293B"
    BG_SURFACE    = "#1E293B"
    BG_ELEVATED   = "#334155"
    BG_INPUT      = "#0F172A"

    TEXT_PRIMARY   = "#F1F5F9"
    TEXT_SECONDARY = "#94A3B8"
    TEXT_MUTED     = "#64748B"
    TEXT_ON_ACCENT = "#FFFFFF"

    ACCENT         = "#3B82F6"
    ACCENT_HOVER   = "#60A5FA"
    ACCENT_ACTIVE  = "#2563EB"
    ACCENT_LIGHT   = "#1E3A5F"

    SUCCESS  = "#22C55E"
    SUCCESS_BG = "#052E16"
    WARNING  = "#F59E0B"
    WARNING_BG = "#422006"
    ERROR    = "#EF4444"
    ERROR_BG = "#450A0A"

    PURPLE   = "#A855F7"
    PINK     = "#EC4899"
    TEAL     = "#14B8A6"
    ORANGE   = "#F97316"
    INDIGO   = "#6366F1"
    CYAN     = "#06B6D4"

    BORDER         = "#334155"
    BORDER_SUBTLE  = "#1E293B"
    BORDER_FOCUS   = "#3B82F6"

    HDR_DATA     = ("#6366F1", "#4F46E5")
    HDR_VIZ      = ("#8B5CF6", "#7C3AED")
    HDR_AI       = ("#EC4899", "#DB2777")
    HDR_BATCH    = ("#14B8A6", "#0D9488")

    ICON_DIAMETER   = 75         
    NODE_W          = 130
    NODE_H          = 105
    NODE_RADIUS     = 12
    NODE_HEADER_H   = 36
    ANCHOR_R        = 8
    GRID_SIZE       = 24
    GRID_DOT_ALPHA  = 35

    FONT_FAMILY   = "Segoe UI"
    FONT_TITLE    = 12
    FONT_BODY     = 11
    FONT_SMALL    = 10
    FONT_TINY     = 9

    SHADOW_BLUR   = 20
    SHADOW_OFFSET = 4
    SHADOW_COLOR  = QColor(0, 0, 0, 90)

    ANIM_FAST = 120
    ANIM_NORMAL = 200
    ANIM_SLOW = 350

    @staticmethod
    def font(size=None, bold=False):
        f = QFont(DS.FONT_FAMILY, size or DS.FONT_BODY)
        if bold:
            f.setWeight(QFont.Weight.DemiBold)
        return f

    @staticmethod
    def pen(color, width=1.0):
        return QPen(QColor(color), width)

    @staticmethod
    def brush(color):
        return QBrush(QColor(color))

class WorkflowLink(QObject):
    state_changed = Signal(int)

    def __init__(self, source_node, source_channel, sink_node, sink_channel):
        super().__init__()
        self.source_node = source_node
        self.source_channel = source_channel
        self.sink_node = sink_node
        self.sink_channel = sink_channel
        self.enabled = True

    def get_data(self):
        if hasattr(self.source_node, 'get_output_data'):
            return self.source_node.get_output_data()
        return None


class WorkflowNode(QObject):
    position_changed = Signal(QPointF)
    configuration_changed = Signal()

    def __init__(self, title, node_type):
        super().__init__()
        self.title = title
        self.node_type = node_type
        self.position = QPointF(0, 0)
        self._has_input = False
        self._has_output = False
        self.input_channels = []
        self.output_channels = []

    def set_position(self, pos):
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        """
        Args:
            parent_window (Any): The parent window.
        """

class AnchorPointSignals(QObject):
    position_changed = Signal(QPointF)


class AnchorPoint(QGraphicsEllipseItem):

    def __init__(self, parent, channel_name, is_input=True):
        super().__init__(parent)
        self.channel_name = channel_name
        self.is_input = is_input
        self.radius = DS.ANCHOR_R

        self.signals = AnchorPointSignals()
        self.position_changed = self.signals.position_changed

        r = self.radius
        self.setRect(QRectF(-r, -r, r * 2, r * 2))

        self._base_color = QColor(DS.SUCCESS) if is_input else QColor(DS.ORANGE)
        self._apply_style(hover=False)

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges, True)
        self.setZValue(10)
        self.setCursor(QCursor(Qt.CrossCursor))

    def _apply_style(self, hover=False):
        c = self._base_color
        r = self.radius * (1.2 if hover else 1.0)
        grad = QRadialGradient(0, 0, r)
        grad.setColorAt(0, c.lighter(150 if hover else 120))
        grad.setColorAt(1, c)
        self.setBrush(QBrush(grad))
        border = c.darker(130)
        self.setPen(QPen(border, 2.0 if hover else 1.5))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            self.position_changed.emit(value)
        return super().itemChange(change, value)
    
    def shape(self):
        """Creates an invisible, larger hitbox for easier clicking and dragging."""
        path = QPainterPath()
        hitbox_radius = self.radius + 12
        path.addEllipse(QRectF(-hitbox_radius, -hitbox_radius, hitbox_radius * 2, hitbox_radius * 2))
        return path

    def hoverEnterEvent(self, event):
        self._apply_style(hover=True)
        self.setScale(1.3)
        label = "Input (Connect here)" if self.is_input else "Output (Drag to connect to multiple nodes)"
        QToolTip.showText(event.screenPos(), label)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._apply_style(hover=False)
        self.setScale(1.0)
        super().hoverLeaveEvent(event)

    def set_drag_target(self, state):
        """Highlight this input port while a connection is being dragged.

        state: 'none', 'candidate' (a valid drop target), or 'snap' (the wire
        is about to connect here).
        """
        c = self._base_color
        if state == 'snap':
            grad = QRadialGradient(0, 0, self.radius * 1.7)
            grad.setColorAt(0, c.lighter(185))
            grad.setColorAt(1, c)
            self.setBrush(QBrush(grad))
            self.setPen(QPen(c.lighter(160), 2.8))
            self.setScale(1.6)
        elif state == 'candidate':
            grad = QRadialGradient(0, 0, self.radius * 1.35)
            grad.setColorAt(0, c.lighter(165))
            grad.setColorAt(1, c)
            self.setBrush(QBrush(grad))
            self.setPen(QPen(c.lighter(140), 2.2))
            self.setScale(1.28)
        else:
            self._apply_style(hover=False)
            self.setScale(1.0)

class NodeItem(QGraphicsWidget):

    def __init__(self, workflow_node, parent=None):
        super().__init__(parent)
        self.workflow_node = workflow_node
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        self.width = DS.NODE_W
        self.height = DS.NODE_H
        self.icon_d = DS.ICON_DIAMETER
        self.setAcceptHoverEvents(True)

        self.is_hovered = False
        self.anchors = {}
        self._icon_cache = {}
        self._create_anchors()

        if hasattr(workflow_node, 'position_changed'):
            workflow_node.position_changed.connect(self.setPos)

    def paint_icon_node(self, painter, grad_colors, icon_name, label_text,
                        badge_text="", badge_color=None):
        """Paint a circular icon node with its label.

        When ``badge_text`` is given it is drawn as a small rounded pill on the
        upper-right of the circle (used to show how many figures a viz node has
        open).
        """
        painter.setRenderHint(QPainter.Antialiasing)

        d = self.icon_d
        cx = self.width / 2
        cy = d / 2 + 4
        r = d / 2

        for i in range(5):
            s = 6 - i
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 6 + i * 4))
            painter.drawEllipse(QPointF(cx + 1, cy + 2), r + s, r + s)

        if self.isSelected():
            painter.setPen(Qt.NoPen)
            glow = QRadialGradient(cx, cy, r + 10)
            glow.setColorAt(0.7, QColor(DS.ACCENT).lighter(120))
            glow.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(QPointF(cx, cy), r + 10, r + 10)
        elif self.is_hovered:
            painter.setPen(Qt.NoPen)
            glow = QRadialGradient(cx, cy, r + 7)
            gc = QColor(grad_colors[0])
            gc.setAlpha(80)
            glow.setColorAt(0.7, gc)
            glow.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(QPointF(cx, cy), r + 7, r + 7)

        # ── main circle with gradient ──────────────────────────────────────
        grad = QRadialGradient(cx - r * 0.3, cy - r * 0.3, d * 0.8)
        grad.setColorAt(0.0, QColor(grad_colors[0]).lighter(130))
        grad.setColorAt(0.5, QColor(grad_colors[0]))
        grad.setColorAt(1.0, QColor(grad_colors[1]).darker(120))
        painter.setBrush(QBrush(grad))

        if self.isSelected():
            painter.setPen(QPen(QColor(DS.ACCENT), 2.5))
        elif self.is_hovered:
            painter.setPen(QPen(QColor(grad_colors[0]).lighter(160), 2.0))
        else:
            painter.setPen(QPen(QColor(grad_colors[1]).darker(140), 1.5))

        painter.drawEllipse(QPointF(cx, cy), r, r)

        highlight = QPainterPath()
        hr = r * 0.85
        highlight.addEllipse(QPointF(cx, cy - r * 0.1), hr, hr * 0.7)
        clip_rect = QRectF(cx - r, cy - r, d, r * 0.8)
        clip_path = QPainterPath()
        clip_path.addRect(clip_rect)
        shine = highlight & clip_path
        painter.setPen(Qt.NoPen)
        shine_grad = QLinearGradient(cx, cy - r, cx, cy)
        shine_grad.setColorAt(0.0, QColor(255, 255, 255, 55))
        shine_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(shine_grad))
        painter.drawPath(shine)

        icon_size = int(d * 0.48)
        cache_key = f"{icon_name}_{icon_size}"
        if cache_key not in self._icon_cache:
            try:
                ico = qta.icon(icon_name, color='white')
                px = ico.pixmap(QSize(icon_size, icon_size))
                self._icon_cache[cache_key] = px
            except Exception:
                _itk_log.exception("Handled exception in paint_icon_node")
                self._icon_cache[cache_key] = None

        px = self._icon_cache.get(cache_key)
        if px and not px.isNull():
            ix = cx - icon_size / 2
            iy = cy - icon_size / 2
            painter.setOpacity(0.95)
            painter.drawPixmap(int(ix), int(iy), px)
            painter.setOpacity(1.0)

        label_y = cy + r + 8
        label_color = _app_theme.palette.text_primary
        painter.setPen(QPen(QColor(label_color)))
        painter.setFont(DS.font(DS.FONT_SMALL, bold=True))
        label_rect = QRectF(0, label_y, self.width, 20)
        painter.drawText(label_rect, Qt.AlignHCenter | Qt.AlignTop, label_text)

        if badge_text:
            bc = QColor(badge_color) if badge_color else QColor(DS.TEXT_MUTED)
            t = str(badge_text)
            f = QFont(DS.FONT_FAMILY)
            f.setPixelSize(11)
            f.setBold(True)
            tw = QFontMetrics(f).horizontalAdvance(t)
            bh = 18
            bw = max(bh, tw + 11)
            bx = cx + r * 0.62
            by = cy - r * 0.62
            rect = QRectF(bx - bw / 2, by - bh / 2, bw, bh)
            painter.setPen(QPen(QColor(_app_theme.palette.bg_primary), 2))
            painter.setBrush(bc)
            painter.drawRoundedRect(rect, bh / 2, bh / 2)
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(f)
            painter.drawText(rect, Qt.AlignCenter, t)

    def paint(self, painter, option, widget=None):
        self.paint_icon_node(
            painter, DS.HDR_DATA, "fa6s.cube",
            self.workflow_node.title,
        )

    # ── anchors ─────────────────────────────────────────────────────────────
    def _create_anchors(self):
        cy = self.icon_d / 2 + 4
        if hasattr(self.workflow_node, '_has_input') and self.workflow_node._has_input:
            a = AnchorPoint(self, "input", is_input=True)
            a.setPos(self.width / 2 - self.icon_d / 2 - 4, cy)
            self.anchors["input"] = a
        if hasattr(self.workflow_node, '_has_output') and self.workflow_node._has_output:
            a = AnchorPoint(self, "output", is_input=False)
            a.setPos(self.width / 2 + self.icon_d / 2 + 4, cy)
            self.anchors["output"] = a

    def get_anchor(self, channel_name):
        return self.anchors.get(channel_name)

    def boundingRect(self):
        m = 20
        return QRectF(-m, -m, self.width + 2 * m, self.height + 2 * m)

    def shape(self):
        p = QPainterPath()
        cx = self.width / 2
        cy = self.icon_d / 2 + 4
        r = self.icon_d / 2 + 6
        p.addEllipse(QPointF(cx, cy), r, r)
        p.addRect(QRectF(0, cy + self.icon_d / 2, self.width, 24))
        return p

    # ── interaction ─────────────────────────────────────────────────────────
    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not (event.modifiers() & Qt.ControlModifier):
                if self.scene() and not self.isSelected():
                    self.scene().clearSelection()
            self.setSelected(True)
        elif event.button() == Qt.RightButton:
            self.show_context_menu(event.screenPos())
        super().mousePressEvent(event)

    def show_context_menu(self, global_pos):
        menu = QMenu()
        menu.setStyleSheet(self._ctx_menu_style())
        dup = menu.addAction(qta.icon('fa6s.copy', color=DS.ACCENT), "  Duplicate")
        dup.triggered.connect(self.duplicate_node)
        menu.addSeparator()
        dele = menu.addAction(qta.icon('fa6s.trash-can', color=DS.ERROR), "  Delete")
        dele.triggered.connect(self.delete_node)
        menu.exec(global_pos)

    @staticmethod
    def _ctx_menu_style():
        p = _app_theme.palette
        return f"""
        QMenu {{
            background: {p.bg_secondary};
            border: 1px solid {p.border};
            border-radius: 8px;
            padding: 4px;
            color: {p.text_primary};
            font-family: '{DS.FONT_FAMILY}';
            font-size: 12px;
        }}
        QMenu::item {{
            padding: 8px 24px 8px 12px;
            border-radius: 6px;
        }}
        QMenu::item:selected {{
            background: {p.accent_soft};
            color: {p.text_primary};
        }}
        QMenu::separator {{
            height: 1px;
            background: {p.border};
            margin: 4px 8px;
        }}
        """

    def duplicate_node(self):
        if self.scene():
            self.scene().duplicate_node(self)

    def delete_node(self):
        if self.scene():
            self.scene().delete_node(self)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            if hasattr(self.workflow_node, 'set_position'):
                self.workflow_node.set_position(value)
        elif change == QGraphicsItem.ItemSelectedHasChanged:
            self.update()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        self.configure_node()
        super().mouseDoubleClickEvent(event)

    def configure_node(self):
        pass

class LinkCurveItem(QGraphicsWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setAcceptHoverEvents(True)

        self.__curve_path = QPainterPath()
        self.__pen = QPen(QColor(DS.ACCENT), 2.5)
        self.__pen.setCapStyle(Qt.RoundCap)
        self.hover = False

        self._dot_offset = 0.0
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._advance_dots)
        self._anim_timer.start(30)

    def _advance_dots(self):
        self._dot_offset += 0.008
        if self._dot_offset > 1.0:
            self._dot_offset -= 1.0
        if not self.__curve_path.isEmpty():
            self.update()

    def set_curve_path(self, path):
        if path != self.__curve_path:
            self.prepareGeometryChange()
            self.__curve_path = path
            self.update()

    def set_pen(self, pen):
        if pen != self.__pen:
            self.__pen = pen
            self.update()

    def boundingRect(self):
        if self.__curve_path.isEmpty():
            return QRectF()
        stroke = QPainterPathStroker()
        stroke.setWidth(max(self.__pen.widthF() + 12, 18))
        return stroke.createStroke(self.__curve_path).boundingRect()

    def paint(self, painter, option, widget=None):
        if self.__curve_path.isEmpty():
            return
        painter.setRenderHint(QPainter.Antialiasing)

        shadow = QPainterPath(self.__curve_path)
        shadow.translate(1.5, 2)
        painter.setPen(QPen(QColor(0, 0, 0, 40), self.__pen.widthF() + 2))
        painter.drawPath(shadow)

        if self.hover:
            grad = QLinearGradient(
                self.__curve_path.pointAtPercent(0),
                self.__curve_path.pointAtPercent(1))
            grad.setColorAt(0, QColor(DS.ACCENT))
            grad.setColorAt(1, QColor(DS.PURPLE))
            pen = QPen(QBrush(grad), 3.5)
        else:
            pen = QPen(self.__pen)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawPath(self.__curve_path)

        dot_color = QColor(DS.TEXT_PRIMARY) if not self.hover else QColor("#FFF")
        painter.setPen(Qt.NoPen)
        painter.setBrush(dot_color)
        for i in range(3):
            t = (self._dot_offset + i * 0.33) % 1.0
            pt = self.__curve_path.pointAtPercent(t)
            painter.drawEllipse(pt, 2.5, 2.5)

    def hoverEnterEvent(self, event):
        self.hover = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.hover = False
        self.update()
        super().hoverLeaveEvent(event)


class LinkItem(QGraphicsWidget):
    activated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptedMouseButtons(Qt.RightButton | Qt.LeftButton)
        self.setAcceptHoverEvents(True)
        self.setZValue(5)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)

        self.source_anchor = None
        self.sink_anchor = None
        self.workflow_link = None
        self.is_hovered = False
        self.curve_item = LinkCurveItem(self)
        self.__update_curve()

    def set_source_anchor(self, anchor):
        if self.source_anchor:
            try: self.source_anchor.position_changed.disconnect(self.__update_curve)
            except Exception:
                _itk_log.exception("Handled exception in set_source_anchor")
        self.source_anchor = anchor
        if anchor:
            anchor.position_changed.connect(self.__update_curve)
        self.__update_curve()

    def set_sink_anchor(self, anchor):
        if self.sink_anchor:
            try: self.sink_anchor.position_changed.disconnect(self.__update_curve)
            except Exception:
                _itk_log.exception("Handled exception in set_sink_anchor")
        self.sink_anchor = anchor
        if anchor:
            anchor.position_changed.connect(self.__update_curve)
        self.__update_curve()

    def set_workflow_link(self, link):
        self.workflow_link = link

    def __update_curve(self):
        if not self.source_anchor or not self.sink_anchor:
            return
        try:
            src = self.source_anchor.scenePos()
            snk = self.sink_anchor.scenePos()
            pad = 60
            x0 = min(src.x(), snk.x()) - pad
            y0 = min(src.y(), snk.y()) - pad
            x1 = max(src.x(), snk.x()) + pad
            y1 = max(src.y(), snk.y()) + pad
            self.setPos(x0, y0)
            self.resize(x1 - x0, y1 - y0)

            sl = QPointF(src.x() - x0, src.y() - y0)
            el = QPointF(snk.x() - x0, snk.y() - y0)

            dx = abs(el.x() - sl.x())
            offset = max(dx * 0.5, 50)

            path = QPainterPath()
            path.moveTo(sl)
            path.cubicTo(
                QPointF(sl.x() + offset, sl.y()),
                QPointF(el.x() - offset, el.y()),
                el)

            self.curve_item.set_curve_path(path)

            if self.isSelected():
                pen = QPen(QColor(DS.WARNING), 3.5)
            elif self.is_hovered:
                pen = QPen(QColor(DS.ACCENT_HOVER), 3.0)
            else:
                pen = QPen(QColor(DS.ACCENT), 2.5)
            pen.setCapStyle(Qt.RoundCap)
            self.curve_item.set_pen(pen)
        except Exception as e:
            _itk_log.exception("Handled exception in __update_curve")
            _itk_log.error(f"Link update error: {e}")

    def boundingRect(self):
        return self.curve_item.boundingRect()

    def shape(self):
        if self.curve_item and not self.curve_item._LinkCurveItem__curve_path.isEmpty():
            s = QPainterPathStroker()
            s.setWidth(18)
            return s.createStroke(self.curve_item._LinkCurveItem__curve_path)
        return QPainterPath()

    def mousePressEvent(self, event):

        scene = self.scene()
        if scene:
            items_under_cursor = scene.items(event.scenePos())
            if any(isinstance(i, AnchorPoint) for i in items_under_cursor):
                event.ignore()
                return

        if event.button() == Qt.LeftButton:
            self.setSelected(not self.isSelected())
        elif event.button() == Qt.RightButton:
            self._show_ctx(event.screenPos())
        else:
            super().mousePressEvent(event)

    def _show_ctx(self, pos):
        menu = QMenu()
        menu.setStyleSheet(NodeItem._ctx_menu_style())
        d = menu.addAction(qta.icon('fa6s.link-slash', color=DS.ERROR), "  Remove Connection")
        d.triggered.connect(self.delete_connection)
        menu.exec(pos)

    def delete_connection(self):
        if self.scene():
            self.scene().delete_link(self)

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.__update_curve()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.__update_curve()
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.__update_curve()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        self.activated.emit()
        super().mouseDoubleClickEvent(event)

def _dialog_base_style():
    """Dialog stylesheet synced to the current app theme. The canvas itself
    (nodes, links, grid) keeps the DS design system — those are intentionally
    always-dark like the canvas in Figma or Final Cut. But pop-up dialogs
    should match whichever theme the user has chosen.
    """
    from tools.theme import theme as _app_theme
    p = _app_theme.palette
    return f"""
    QDialog {{
        background: {p.bg_primary};
        color: {p.text_primary};
        font-family: '{DS.FONT_FAMILY}';
    }}
    QTabWidget::pane {{
        border: 1px solid {p.border};
        border-radius: 6px;
        background: {p.bg_secondary};
    }}
    QTabBar::tab {{
        background: {p.bg_tertiary};
        color: {p.text_secondary};
        padding: 8px 20px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 2px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {p.bg_secondary};
        color: {p.accent};
        border-bottom: 2px solid {p.accent};
    }}
    QLabel {{ color: {p.text_primary}; }}
    QPushButton {{
        background: {p.bg_tertiary};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 600;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background: {p.accent_soft};
        border-color: {p.accent};
    }}
    QTableWidget {{
        background: {p.bg_secondary};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 6px;
        gridline-color: {p.border_subtle};
        selection-background-color: {p.accent};
        selection-color: {p.text_inverse};
        alternate-background-color: {p.bg_tertiary};
    }}
    QHeaderView::section {{
        background: {p.bg_tertiary};
        color: {p.text_primary};
        padding: 10px;
        border: 1px solid {p.border_subtle};
        font-weight: 600;
    }}
    QCheckBox {{ color: {p.text_primary}; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px;
        border-radius: 4px;
        border: 2px solid {p.border};
        background: {p.bg_secondary};
    }}
    QCheckBox::indicator:checked {{
        background: {p.accent};
        border-color: {p.accent};
    }}
    QLineEdit {{
        background: {p.bg_secondary};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 6px;
        padding: 8px 12px;
    }}
    QLineEdit:focus {{ border: 2px solid {p.accent}; }}
    QDialogButtonBox QPushButton {{ min-width: 90px; }}
    """


def _canvas_chrome_style():
    """Stylesheet for the canvas dialog chrome (header, palette, statusbar).
    The canvas itself (nodes/links/grid) stays always-dark like Figma.
    """
    p = _app_theme.palette
    return f"""
    QDialog {{
        background: {p.bg_primary};
    }}
    QFrame#chromeHeader {{
        background: {p.bg_secondary};
        border-bottom: 1px solid {p.border};
    }}
    QFrame#chromePalette {{
        background: {p.bg_secondary};
        border-right: 1px solid {p.border};
    }}
    QFrame#chromeStatus {{
        background: {p.bg_secondary};
        border-top: 1px solid {p.border};
    }}
    QLabel {{
        color: {p.text_primary};
        background: transparent;
    }}
    QPushButton {{
        background: {p.bg_tertiary};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {p.accent_soft};
        border-color: {p.accent};
        color: {p.accent};
    }}
    QLineEdit {{
        background: {p.bg_tertiary};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 12px;
    }}
    QLineEdit:focus {{ border: 2px solid {p.accent}; }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{
        background: {p.bg_secondary}; width: 6px; border-radius: 3px;
    }}
    QScrollBar::handle:vertical {{
        background: {p.border}; border-radius: 3px; min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {p.text_muted}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QSplitter::handle {{ background: {p.border}; width: 1px; }}
    """


class SampleSelectorDialog(QDialog):
    """Simplified single-sample configurator: samples on left, isotope chips on right."""

    def __init__(self, parent, samples, current_selection=None,
                 current_isotopes=None, current_sum_replicates=False,
                 current_replicate_samples=None):
        super().__init__(parent)
        self.setWindowTitle("Single Sample Configuration")
        self.setModal(True)
        self.resize(900, 580)
        self.setMinimumSize(700, 480)
        self.setStyleSheet(_dialog_base_style())
        _app_theme.themeChanged.connect(lambda _: self.setStyleSheet(_dialog_base_style()))

        self.parent_window = parent
        self.samples = samples
        self.current_isotopes = current_isotopes or []
        self.current_replicate_samples = current_replicate_samples or []

        self.sample_config = {}
        for s in samples:
            included = False
            if current_sum_replicates and s in self.current_replicate_samples:
                included = True
            elif not current_sum_replicates and s == current_selection:
                included = True
            self.sample_config[s] = included

        self._build()

    # ── build ──────────────────────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        p = _app_theme.palette
        banner = QLabel(
            "Check one sample for individual analysis, or multiple to sum/combine them.")
        banner.setWordWrap(True)
        banner.setStyleSheet(
            f"padding:10px; background:{p.accent_soft}; border:1px solid {p.border_strong};"
            f" border-radius:6px; color:{p.text_primary}; font-size:11px;")
        root.addWidget(banner)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(6)

        lv.addWidget(self._make_section_label("Samples"))

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search samples…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._filter_samples)
        lv.addWidget(self._search)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._sample_container = QWidget()
        self._sample_layout = QVBoxLayout(self._sample_container)
        self._sample_layout.setContentsMargins(0, 0, 0, 0)
        self._sample_layout.setSpacing(2)
        self._scroll.setWidget(self._sample_container)
        lv.addWidget(self._scroll)

        btns = QHBoxLayout()
        for txt, slot in [("Select All", self._select_all), ("Clear", self._clear_all)]:
            b = QPushButton(txt)
            b.setFixedHeight(28)
            b.clicked.connect(slot)
            btns.addWidget(b)
        btns.addStretch()
        lv.addLayout(btns)

        splitter.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 0, 0, 0)
        rv.setSpacing(6)
        rv.addWidget(self._make_section_label("Isotopes"))

        self._chip_selector = IsotopeChipSelector()
        rv.addWidget(self._chip_selector)

        splitter.addWidget(right)
        splitter.setSizes([380, 480])
        root.addWidget(splitter, 1)

        self._preview = QLabel()
        self._preview.setWordWrap(True)
        self._preview.setStyleSheet(
            f"padding:10px; background:{p.accent_soft}; border:1px solid {p.border_strong};"
            f" border-radius:6px; color:{p.text_primary}; font-size:12px; font-weight:600;")
        root.addWidget(self._preview)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        self._checkboxes = {}
        self._build_sample_list(self.samples)
        self._load_isotopes()
        self._update_preview()

    def _make_section_label(self, text):
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"font-size:10px; font-weight:700; letter-spacing:1px;"
            f" color:{_app_theme.palette.text_muted}; padding-bottom:2px;")
        return lbl

    def _build_sample_list(self, samples):
        while self._sample_layout.count():
            child = self._sample_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._checkboxes = {}
        p = _app_theme.palette
        for s in samples:
            cb = QCheckBox(s)
            cb.setChecked(self.sample_config.get(s, False))
            cb.setStyleSheet(
                f"QCheckBox {{ padding:6px 8px; border-radius:5px; color:{p.text_primary}; }}"
                f"QCheckBox:hover {{ background:{p.bg_hover}; }}"
                f"QCheckBox::indicator {{ width:16px; height:16px; border-radius:3px; }}"
                f"QCheckBox::indicator:unchecked {{ border:2px solid {p.border};"
                f" background:{p.bg_secondary}; }}"
                f"QCheckBox::indicator:checked {{ border:2px solid {p.accent};"
                f" background:{p.accent}; }}"
            )
            cb.stateChanged.connect(lambda _, s=s: self._on_check(s))
            self._checkboxes[s] = cb
            self._sample_layout.addWidget(cb)
        self._sample_layout.addStretch()

    def _load_isotopes(self):
        if not (self.parent_window and hasattr(self.parent_window, 'selected_isotopes')):
            return
        pairs = []
        for el, isos in self.parent_window.selected_isotopes.items():
            for iso in isos:
                pairs.append((el, iso))
        if not pairs:
            return
        from results.results_periodic import CompactPeriodicTableWidget
        _tmp = CompactPeriodicTableWidget()
        elem_data = _tmp.get_elements()
        _tmp.deleteLater()
        self._chip_selector.set_available_isotopes(elem_data, pairs)
        if self.current_isotopes:
            self._chip_selector.set_selected(self.current_isotopes)

    def _on_check(self, sample):
        self.sample_config[sample] = self._checkboxes[sample].isChecked()
        self._update_preview()

    def _filter_samples(self, text):
        q = text.lower()
        for s, cb in self._checkboxes.items():
            cb.setVisible(q in s.lower())

    def _select_all(self):
        for s, cb in self._checkboxes.items():
            if cb.isVisible():
                cb.setChecked(True)

    def _clear_all(self):
        for cb in self._checkboxes.values():
            if cb.isVisible():
                cb.setChecked(False)

    def _update_preview(self):
        p = _app_theme.palette
        inc = [s for s, checked in self.sample_config.items() if checked]
        if not inc:
            txt = "No samples selected"
        elif len(inc) == 1:
            txt = f"Individual analysis of \"{inc[0]}\""
        else:
            txt = f"Summed analysis of {len(inc)} samples: {', '.join(inc)}"
        self._preview.setText(txt)
        self._preview.setStyleSheet(
            f"padding:10px; background:{p.accent_soft}; border:1px solid {p.border_strong};"
            f" border-radius:6px; color:{p.text_primary}; font-size:12px; font-weight:600;")

    def get_selection(self):
        selected = [s for s, c in self.sample_config.items() if c]
        raw_iso = self._chip_selector.get_selected()
        isotopes = []
        for sym, mass in raw_iso:
            key = f"{sym}-{mass:.4f}"
            lbl = self.parent_window.get_formatted_label(key) if self.parent_window else key
            isotopes.append({'symbol': sym, 'mass': mass, 'key': key, 'label': lbl})
        if not selected:
            return None, isotopes, False
        elif len(selected) == 1:
            return selected[0], isotopes, False
        else:
            return selected, isotopes, True
        
    
class MultipleSampleSelectorDialog(QDialog):
    """Simplified multi-sample configurator: sample list with inline group fields + isotope chips."""

    def __init__(self, parent, samples, current_selection=None,
                 current_isotopes=None, current_sample_config=None):
        super().__init__(parent)
        self.setWindowTitle("Multi-Sample Configuration")
        self.setModal(True)
        self.resize(1000, 600)
        self.setMinimumSize(800, 480)
        self.setStyleSheet(_dialog_base_style())
        _app_theme.themeChanged.connect(lambda _: self.setStyleSheet(_dialog_base_style()))

        self.parent_window = parent
        self.samples = samples
        self.current_isotopes = current_isotopes or []

        if current_sample_config:
            self.current_sample_config = current_sample_config.copy()
        else:
            self.current_sample_config = {}
            cs = current_selection or []
            for s in samples:
                self.current_sample_config[s] = {
                    'included': s in cs, 'sum_group': '', 'custom_name': s}

        self._build()

    # ── build ──────────────────────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        p = _app_theme.palette
        banner = QLabel(
            "Check samples to include. Assign the same Group name to combine samples "
            "— leave blank for individual analysis.")
        banner.setWordWrap(True)
        banner.setStyleSheet(
            f"padding:10px; background:{p.accent_soft}; border:1px solid {p.border_strong};"
            f" border-radius:6px; color:{p.text_primary}; font-size:11px;")
        root.addWidget(banner)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(6)

        lv.addWidget(self._make_section_label("Samples"))

        top_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search samples…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._filter_samples)
        top_row.addWidget(self._search, 1)

        self._group_input = QLineEdit()
        self._group_input.setPlaceholderText("Group name…")
        self._group_input.setFixedWidth(120)
        top_row.addWidget(self._group_input)

        apply_btn = QPushButton("Apply to Checked")
        apply_btn.setFixedHeight(32)
        apply_btn.clicked.connect(self._apply_group_to_checked)
        top_row.addWidget(apply_btn)
        lv.addLayout(top_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._sample_container = QWidget()
        self._sample_layout = QVBoxLayout(self._sample_container)
        self._sample_layout.setContentsMargins(0, 0, 0, 0)
        self._sample_layout.setSpacing(2)
        self._scroll.setWidget(self._sample_container)
        lv.addWidget(self._scroll)

        btns = QHBoxLayout()
        for txt, slot in [
            ("Select All", self._select_all),
            ("Clear All", self._clear_all),
            ("Clear Groups", self._clear_groups),
            ("Auto-Group", self._auto_group),
        ]:
            b = QPushButton(txt)
            b.setFixedHeight(28)
            b.clicked.connect(slot)
            btns.addWidget(b)
        btns.addStretch()
        lv.addLayout(btns)

        splitter.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 0, 0, 0)
        rv.setSpacing(6)
        rv.addWidget(self._make_section_label("Isotopes"))

        self._chip_selector = IsotopeChipSelector()
        rv.addWidget(self._chip_selector)

        splitter.addWidget(right)
        splitter.setSizes([540, 420])
        root.addWidget(splitter, 1)

        self._preview = QLabel()
        self._preview.setWordWrap(True)
        self._preview.setStyleSheet(
            f"padding:10px; background:{p.accent_soft}; border:1px solid {p.border_strong};"
            f" border-radius:6px; color:{p.text_primary}; font-size:12px; font-weight:600;")
        root.addWidget(self._preview)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        self._row_widgets = {}
        self._build_sample_list(self.samples)
        self._load_isotopes()
        self._update_preview()

    def _make_section_label(self, text):
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"font-size:10px; font-weight:700; letter-spacing:1px;"
            f" color:{_app_theme.palette.text_muted}; padding-bottom:2px;")
        return lbl

    def _build_sample_list(self, samples):
        while self._sample_layout.count():
            child = self._sample_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._row_widgets = {}
        p = _app_theme.palette
        for s in samples:
            cfg = self.current_sample_config.get(
                s, {'included': False, 'sum_group': '', 'custom_name': s})

            row_w = QWidget()
            row_w.setStyleSheet(
                f"QWidget {{ border-radius:5px; }}"
                f"QWidget:hover {{ background:{p.bg_hover}; }}")
            row = QHBoxLayout(row_w)
            row.setContentsMargins(4, 2, 4, 2)
            row.setSpacing(6)

            cb = QCheckBox()
            cb.setChecked(cfg.get('included', False))
            cb.setStyleSheet(
                f"QCheckBox::indicator {{ width:16px; height:16px; border-radius:3px; }}"
                f"QCheckBox::indicator:unchecked {{ border:2px solid {p.border};"
                f" background:{p.bg_secondary}; }}"
                f"QCheckBox::indicator:checked {{ border:2px solid {p.accent};"
                f" background:{p.accent}; }}"
            )
            row.addWidget(cb)

            name_lbl = QLabel(s)
            name_lbl.setStyleSheet(f"color:{p.text_primary}; background:transparent;")
            name_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            row.addWidget(name_lbl, 1)

            group_edit = QLineEdit()
            group_edit.setPlaceholderText("Group…")
            group_edit.setText(cfg.get('sum_group', ''))
            group_edit.setFixedWidth(100)
            group_edit.setFixedHeight(24)
            group_edit.setStyleSheet(
                f"QLineEdit {{ background:{p.bg_tertiary}; color:{p.text_primary};"
                f" border:1px solid {p.border}; border-radius:4px; padding:2px 6px;"
                f" font-size:11px; }}"
                f"QLineEdit:focus {{ border-color:{p.accent}; }}"
            )
            row.addWidget(group_edit)

            cb.stateChanged.connect(lambda _, s=s: self._on_change(s))
            group_edit.textChanged.connect(lambda _, s=s: self._on_change(s))

            self._row_widgets[s] = (row_w, cb, group_edit)
            self._sample_layout.addWidget(row_w)

        self._sample_layout.addStretch()

    def _load_isotopes(self):
        if not (self.parent_window and hasattr(self.parent_window, 'selected_isotopes')):
            return
        pairs = []
        for el, isos in self.parent_window.selected_isotopes.items():
            for iso in isos:
                pairs.append((el, iso))
        if not pairs:
            return
        from results.results_periodic import CompactPeriodicTableWidget
        _tmp = CompactPeriodicTableWidget()
        elem_data = _tmp.get_elements()
        _tmp.deleteLater()
        self._chip_selector.set_available_isotopes(elem_data, pairs)
        if self.current_isotopes:
            self._chip_selector.set_selected(self.current_isotopes)

    def _on_change(self, sample):
        row_w, cb, group_edit = self._row_widgets[sample]
        self.current_sample_config[sample] = {
            'included': cb.isChecked(),
            'sum_group': group_edit.text().strip(),
            'custom_name': sample,
        }
        self._update_preview()

    def _filter_samples(self, text):
        q = text.lower()
        for s, (row_w, cb, ge) in self._row_widgets.items():
            row_w.setVisible(q in s.lower())

    def _select_all(self):
        for s, (row_w, cb, ge) in self._row_widgets.items():
            if row_w.isVisible():
                cb.setChecked(True)

    def _clear_all(self):
        for row_w, cb, ge in self._row_widgets.values():
            if row_w.isVisible():
                cb.setChecked(False)

    def _clear_groups(self):
        for row_w, cb, ge in self._row_widgets.values():
            ge.clear()

    def _apply_group_to_checked(self):
        g = self._group_input.text().strip()
        if not g:
            return
        for s, (row_w, cb, ge) in self._row_widgets.items():
            if cb.isChecked() and row_w.isVisible():
                ge.setText(g)

    def _auto_group(self):
        """Detect sample groups by stripping common replicate suffixes and numeric endings.
        Handles patterns like:
          sample_1, sample_2         → "sample"
          ctrl_R1, ctrl_R2           → "ctrl"
          liver_rep1, liver_rep2     → "liver"
          2024_Au_A, 2024_Au_B       → "2024_Au"
          HgSe_1mg_r1, HgSe_1mg_r2  → "HgSe_1mg"
        """
        import re
        from collections import defaultdict

        def extract_root(name):
            patterns = [
                r'[_\-\s]?(?:replicate|replica|rep|r)[\s_\-]?\d+$',
                r'[_\-\s]?\d+[_\-\s]?(?:replicate|replica|rep|r)$',
                r'[_\-\s]?\d+$',
                r'[_\-\s][A-Za-z]$',
            ]
            root = name
            for pat in patterns:
                new = re.sub(pat, '', root, flags=re.IGNORECASE).strip('_- ')
                if new and new != root and len(new) >= 2:
                    root = new
                    break
            return root

        groups = defaultdict(list)
        for s in self.samples:
            root = extract_root(s)
            groups[root].append(s)

        for root, members in groups.items():
            if len(members) > 1:
                for s in members:
                    if s in self._row_widgets:
                        _, cb, ge = self._row_widgets[s]
                        ge.setText(root)
                        cb.setChecked(True)

    def _update_preview(self):
        p = _app_theme.palette
        for s, (row_w, cb, ge) in self._row_widgets.items():
            self.current_sample_config[s] = {
                'included': cb.isChecked(),
                'sum_group': ge.text().strip(),
                'custom_name': s,
            }
        inc = [s for s, c in self.current_sample_config.items() if c['included']]
        if not inc:
            txt = "No samples selected"
        else:
            indiv = [s for s in inc if not self.current_sample_config[s]['sum_group']]
            grps = {}
            for s in inc:
                g = self.current_sample_config[s]['sum_group']
                if g:
                    grps.setdefault(g, []).append(s)
            parts = [f"{len(indiv)} individual" if indiv else ""] + \
                    [f'group "{g}" ({len(ss)} samples)' for g, ss in grps.items()]
            parts = [x for x in parts if x]
            txt = f"Will process: {', '.join(parts)}"
        self._preview.setText(txt)
        self._preview.setStyleSheet(
            f"padding:10px; background:{p.accent_soft}; border:1px solid {p.border_strong};"
            f" border-radius:6px; color:{p.text_primary}; font-size:12px; font-weight:600;")

    def get_selection(self):
        for s, (row_w, cb, ge) in self._row_widgets.items():
            self.current_sample_config[s] = {
                'included': cb.isChecked(),
                'sum_group': ge.text().strip(),
                'custom_name': s,
            }
        sel = [s for s, c in self.current_sample_config.items() if c['included']]
        raw_iso = self._chip_selector.get_selected()
        isotopes = []
        for sym, mass in raw_iso:
            key = f"{sym}-{mass:.4f}"
            lbl = self.parent_window.get_formatted_label(key) if self.parent_window else key
            isotopes.append({'symbol': sym, 'mass': mass, 'key': key, 'label': lbl})
        return sel, isotopes, self.current_sample_config

class SampleSelectorNode(WorkflowNode):
    def __init__(self, parent_window=None):
        super().__init__("Single Sample", "sample_selector")
        self.parent_window = parent_window
        self._has_input = True
        self._has_output = True
        self.input_channels = ["input"]
        self.output_channels = ["output"]
        self.selected_sample = None
        self.selected_isotopes = []
        self.sum_replicates = False
        self.replicate_samples = []
        self.input_data = None
        self.batch_samples = None
        self.batch_particle_data = None
        self.batch_sample_data = None
        self.batch_available_isotopes = None
        self.batch_concentration_meta = None

    def process_data(self, input_data):
        self.input_data = input_data
        if input_data:
            dt = input_data.get('type', 'unknown')
            if dt == 'batch_sample_list':
                self.batch_samples = input_data.get('sample_names', [])
                self.batch_particle_data = input_data.get('particle_data', [])
                self.batch_sample_data = input_data.get('data', {})
                self.batch_available_isotopes = input_data.get('available_isotopes', {})
                self.batch_concentration_meta = input_data.get('concentration_meta', {})

    def get_output_data(self):
        if self.input_data and self.input_data.get('type') != 'batch_sample_list':
            return self.input_data
        if not self.selected_sample and not (self.sum_replicates and self.replicate_samples):
            return None
        particle_data = self._get_particles()
        if not particle_data:
            return None
        filtered = self._filter(particle_data)
        name = (f"Summed: {', '.join(self.replicate_samples)}"
                if self.sum_replicates and self.replicate_samples
                else self.selected_sample)
        all_dt = {}
        sd = self._sample_data()
        if sd:
            for k, v in sd.items():
                if isinstance(v, dict):
                    all_dt[k] = v
        members = (self.replicate_samples
                   if self.sum_replicates and self.replicate_samples
                   else [self.selected_sample])
        if self.batch_particle_data is not None:
            metas = [(self.batch_concentration_meta or {}).get(m) for m in members]
        else:
            metas = [_sample_concentration_meta(self.parent_window, m) for m in members]
        conc_meta = _combine_concentration_meta(metas)
        return {
            'type': 'sample_data', 'sample_name': name,
            'data_types': all_dt, 'data': sd,
            'particle_data': filtered, 'selected_isotopes': self.selected_isotopes,
            'total_particles': len(particle_data), 'filtered_particles': len(filtered),
            'sum_replicates': self.sum_replicates,
            'replicate_samples': self.replicate_samples,
            'concentration_meta': {name: conc_meta},
            'parent_window': self.parent_window,
        }

    def _get_particles(self):
        if self.batch_particle_data is not None:
            key = self.replicate_samples if (self.sum_replicates and self.replicate_samples) else [self.selected_sample]
            return [p for p in self.batch_particle_data if p.get('source_sample') in key]
        if not hasattr(self.parent_window, 'sample_particle_data'):
            return None
        if not self.sum_replicates or not self.replicate_samples:
            return self.parent_window.sample_particle_data.get(self.selected_sample, [])
        combined = []
        for s in self.replicate_samples:
            for p in self.parent_window.sample_particle_data.get(s, []):
                pc = p.copy()
                pc.setdefault('source_sample', s)
                pc.setdefault('original_sample', s)
                combined.append(pc)
        return combined

    def _filter(self, particles):
        if not self.selected_isotopes:
            return particles
        labels = [i['label'] for i in self.selected_isotopes]
        out = []
        for p in particles:
            if any(p.get('elements', {}).get(l, 0) > 0 for l in labels):
                fp = p.copy()
                for fld in ('elements', 'element_mass_fg', 'particle_mass_fg',
                            'element_moles_fmol', 'particle_moles_fmol',
                            'element_diameter_nm', 'particle_diameter_nm'):
                    if fld in p:
                        fp[fld] = {k: v for k, v in p[fld].items()
                                   if k in labels and (
                                       (fld == 'elements' and v > 0)
                                       or (fld != 'elements' and v > 0 and not np.isnan(v)))}
                out.append(fp)
        return out

    def _sample_data(self):
        if self.batch_sample_data:
            return self.batch_sample_data.get(self.selected_sample)
        if not self.parent_window or not self.selected_sample:
            return None
        if hasattr(self.parent_window, 'data_by_sample'):
            return self.parent_window.data_by_sample.get(self.selected_sample)
        return None

    def configure(self, parent_window):
        samples = (self.batch_samples if self.batch_samples
                   else list(getattr(parent_window, 'sample_to_folder_map', {}).keys()))
        dlg = SampleSelectorDialog(
            parent_window, samples, self.selected_sample,
            self.selected_isotopes, self.sum_replicates, self.replicate_samples)
        if dlg.exec() == QDialog.Accepted:
            sample, isotopes, sr = dlg.get_selection()
            if sample:
                if sr and isinstance(sample, list):
                    self.replicate_samples = sample
                    self.selected_sample = sample[0] if sample else None
                    self.sum_replicates = True
                else:
                    self.selected_sample = sample
                    self.replicate_samples = []
                    self.sum_replicates = False
                self.selected_isotopes = isotopes
                self.configuration_changed.emit()
                ual = _ual()
                if ual:
                    ual.log_action('SAMPLE_SELECT',
                                   f'Canvas node configured: {self.selected_sample}',
                                   {'node': 'SampleSelector',
                                    'sample': self.selected_sample,
                                    'sum_replicates': self.sum_replicates,
                                    'isotope_count': len(isotopes)})
                return True
        return False


class MultipleSampleSelectorNode(WorkflowNode):
    def __init__(self, parent_window=None):
        super().__init__("Multi-Sample", "multiple_sample_selector")
        self.parent_window = parent_window
        self._has_input = True
        self._has_output = True
        self.input_channels = ["input"]
        self.output_channels = ["output"]
        self.selected_samples = []
        self.sample_config = {}
        self.selected_isotopes = []
        self.sum_replicates = False
        self.input_data = None
        self.batch_samples = None
        self.batch_particle_data = None
        self.batch_sample_data = None
        self.batch_available_isotopes = None
        self.batch_concentration_meta = None

    def process_data(self, input_data):
        self.input_data = input_data
        if input_data:
            dt = input_data.get('type', 'unknown')
            if dt == 'batch_sample_list':
                self.batch_samples = input_data.get('sample_names', [])
                self.batch_particle_data = input_data.get('particle_data', [])
                self.batch_sample_data = input_data.get('data', {})
                self.batch_available_isotopes = input_data.get('available_isotopes', {})
                self.batch_concentration_meta = input_data.get('concentration_meta', {})

    def get_output_data(self):
        if self.input_data and self.input_data.get('type') != 'batch_sample_list':
            return self.input_data
        included = ([s for s, c in self.sample_config.items() if c.get('included')]
                    if self.sample_config else self.selected_samples)
        if not included:
            return None

        combined, total, names = [], 0, []
        if self.sample_config:
            indiv, groups = {}, {}
            for s in included:
                c = self.sample_config.get(s, {'sum_group': '', 'custom_name': s})
                g = c.get('sum_group', '')
                if not g:
                    indiv[s] = c
                    names.append(s)
                else:
                    groups.setdefault(g, []).append(s)
            for g in groups:
                names.append(g)
            for s in indiv:
                total += self._add_individual(s, s, combined)
            for g, ss in groups.items():
                total += self._add_group(g, ss, combined)
        else:
            names = list(included)
            for s in included:
                total += self._add_individual(s, s, combined)

        if not combined:
            return None

        csd, adt = {}, {}
        src = self.batch_sample_data or getattr(self.parent_window, 'data_by_sample', {})
        for s in included:
            sd = src.get(s)
            if sd:
                csd[s] = sd
                for dt, dv in sd.items():
                    if isinstance(dv, dict):
                        adt.setdefault(dt, {})
                        for el, val in dv.items():
                            adt[dt].setdefault(el, []).append(val)

        if self.batch_particle_data is not None:
            conc_src = lambda m: (self.batch_concentration_meta or {}).get(m)
        else:
            conc_src = lambda m: _sample_concentration_meta(self.parent_window, m)
        name_members = {}
        if self.sample_config:
            for s in included:
                c = self.sample_config.get(s, {'sum_group': '', 'custom_name': s})
                g = c.get('sum_group', '')
                name_members.setdefault(g or s, []).append(s)
        else:
            for s in included:
                name_members.setdefault(s, []).append(s)
        concentration_meta = {
            nm: _combine_concentration_meta([conc_src(m) for m in mem])
            for nm, mem in name_members.items()
        }

        return {
            'type': 'multiple_sample_data', 'sample_names': names,
            'original_sample_names': list(included),
            'sample_config': self.sample_config or None,
            'data_types': adt, 'data': csd, 'particle_data': combined,
            'selected_isotopes': self.selected_isotopes,
            'total_particles': total, 'filtered_particles': len(combined),
            'sum_replicates': self.sum_replicates,
            'concentration_meta': concentration_meta,
            'parent_window': self.parent_window,
        }

    def _add_individual(self, name, src, out):
        particles = self._raw_particles(src)
        n = len(particles)
        for p in self._filter(particles):
            p['source_sample'] = name
            p.setdefault('original_sample', src)
            out.append(p)
        return n

    def _add_group(self, gname, members, out):
        total = 0
        for s in members:
            particles = self._raw_particles(s)
            total += len(particles)
            for p in self._filter(particles):
                p['source_sample'] = gname
                p.setdefault('original_sample', s)
                p['sum_group'] = gname
                p['is_summed'] = True
                out.append(p)
        return total

    def _raw_particles(self, sample):
        if self.batch_particle_data is not None:
            return [p for p in self.batch_particle_data if p.get('source_sample') == sample]
        if hasattr(self.parent_window, 'sample_particle_data'):
            return list(self.parent_window.sample_particle_data.get(sample, []))
        return []

    def _filter(self, particles):
        if not self.selected_isotopes:
            return particles
        labels = [i['label'] for i in self.selected_isotopes]
        out = []
        for p in particles:
            if any(p.get('elements', {}).get(l, 0) > 0 for l in labels):
                fp = p.copy()
                for fld in ('elements', 'element_mass_fg', 'particle_mass_fg',
                            'element_moles_fmol', 'particle_moles_fmol',
                            'element_diameter_nm', 'particle_diameter_nm'):
                    if fld in p:
                        fp[fld] = {k: v for k, v in p[fld].items()
                                   if k in labels and (
                                       (fld == 'elements' and v > 0) or
                                       (fld != 'elements' and v > 0 and not np.isnan(v)))}
                out.append(fp)
        return out

    def configure(self, parent_window):
        samples = (self.batch_samples if self.batch_samples
                   else list(getattr(parent_window, 'sample_to_folder_map', {}).keys()))
        dlg = MultipleSampleSelectorDialog(
            parent_window, samples, self.selected_samples,
            self.selected_isotopes, self.sample_config)
        if dlg.exec() == QDialog.Accepted:
            sel, iso, cfg = dlg.get_selection()
            if sel:
                self.selected_samples = sel
                self.selected_isotopes = iso
                self.sample_config = cfg
                self.configuration_changed.emit()
                return True
        return False


class BatchSampleSelectorNode(WorkflowNode):
    def __init__(self, parent_window=None):
        super().__init__("Batch Windows", "batch_sample_selector")
        self.parent_window = parent_window
        self._has_output = True
        self.output_channels = ["output"]
        self.selected_windows = []
        self._saved_output_snapshot = None

    def get_output_data(self):
        """Combined dataset for the selected windows.

        Aggregates live data from the currently selected windows. When no live
        windows are linked (e.g. after reopening a single-window project that
        baked the batch results), the saved output snapshot is replayed instead.
        Returns None when there is neither live selection nor a snapshot.
        """
        if not self.selected_windows:
            snap = getattr(self, '_saved_output_snapshot', None)
            if snap:
                out = dict(snap)
                out['parent_window'] = self.parent_window
                return out
            return None
        names, particles, data, isos = [], [], {}, {}
        concentration_meta = {}
        for w in self.selected_windows:
            num = getattr(w, 'window_number', '?')
            fp = getattr(w, '_project_filepath', None)
            proj_name = Path(fp).stem if fp else "Unnamed"
            lbl = f"W{num} ({proj_name})"
            if hasattr(w, 'selected_isotopes'):
                for el, il in w.selected_isotopes.items():
                    isos.setdefault(el, set()).update(il)
            if hasattr(w, 'data_by_sample'):
                for sn, sd in w.data_by_sample.items():
                    dn = f"{sn} [{lbl}]"
                    names.append(dn)
                    data[dn] = sd
                    concentration_meta[dn] = _sample_concentration_meta(w, sn)
                    if hasattr(w, 'sample_particle_data'):
                        for p in w.sample_particle_data.get(sn, []):
                            pc = p.copy()
                            pc['source_sample'] = dn
                            pc['source_window'] = lbl
                            pc['original_sample'] = sn
                            particles.append(pc)
        return {
            'type': 'batch_sample_list', 'sample_names': names,
            'particle_data': particles, 'data': data,
            'available_isotopes': {k: list(v) for k, v in isos.items()},
            'concentration_meta': concentration_meta,
            'is_batch': True, 'source_windows': len(self.selected_windows),
            'parent_window': self.parent_window,
        }

    def configure(self, parent_window):
        """Open the window selector; selecting live windows rebuilds the batch.

        When a saved batch snapshot was loaded from a project, it is shown in the
        dialog and kept as-is unless the user selects live windows, in which case
        the batch switches back to live aggregation.
        """
        dlg = BatchSampleSelectorDialog(
            parent_window,
            previously_selected=self.selected_windows,
            saved_snapshot=self._saved_output_snapshot)
        if dlg.exec() == QDialog.Accepted:
            sel = dlg.get_selection()
            if sel:
                self.selected_windows = sel
                self._saved_output_snapshot = None
                self.configuration_changed.emit()
                return True
        return False


class BatchSampleSelectorDialog(QDialog):
    def __init__(self, parent_window, previously_selected=None, saved_snapshot=None):
        super().__init__(parent_window)
        self.setWindowTitle("Batch Window Selector")
        self.setModal(True)
        self.resize(900, 600)
        self.setStyleSheet(_dialog_base_style())
        _app_theme.themeChanged.connect(
            lambda _: self.setStyleSheet(_dialog_base_style())
        )

        self.parent_window = parent_window
        self.previously_selected = previously_selected or []
        self.saved_snapshot = saved_snapshot
        self.all_windows = _collect_main_windows()
        self.window_checkboxes = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        hdr = QLabel("Select Windows to Include")
        hdr.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DS.TEXT_PRIMARY};")
        layout.addWidget(hdr)

        if self.saved_snapshot:
            p = _app_theme.palette
            snap = self.saved_snapshot
            ns = len(snap.get('sample_names', []) or [])
            npart = len(snap.get('particle_data', []) or [])
            nwin = snap.get('source_windows', 0)
            banner = QLabel(
                f"✓  Saved batch results kept: {nwin} window(s) · {ns} samples "
                f"· {npart:,} particles, loaded from the saved project. They stay "
                f"connected as-is. Select windows below only if you want to rebuild "
                f"the batch from the currently open windows instead.")
            banner.setWordWrap(True)
            banner.setStyleSheet(
                f"padding:10px; background:{p.accent_soft}; border:1px solid {p.accent};"
                f" border-radius:6px; color:{p.text_primary}; font-weight:600;")
            layout.addWidget(banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        sw = QWidget()
        sl = QVBoxLayout(sw)
        sl.setSpacing(8)
        sl.setContentsMargins(12, 12, 12, 12)

        for w in self.all_windows:
            sc = len(getattr(w, 'data_by_sample', {}))
            pc = sum(len(p) for p in getattr(w, 'sample_particle_data', {}).values())
            num = getattr(w, 'window_number', '?')
            fp = getattr(w, '_project_filepath', None)
            proj_name = Path(fp).stem if fp else "Unnamed"
            label = f"Window {num} ({proj_name})  —  {sc} samples, {pc:,} particles"

            cb = QCheckBox(label)
            was_selected = w in self.previously_selected
            cb.setChecked(was_selected)
            cb.window_ref = w
            cb.stateChanged.connect(self._preview)
            sl.addWidget(cb)
            self.window_checkboxes.append(cb)

        sl.addStretch()
        scroll.setWidget(sw)
        layout.addWidget(scroll)

        self.preview_label = QLabel("No windows selected")
        self.preview_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview_label)
        self._preview()

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _preview(self):
        p = _app_theme.palette
        sel = [cb for cb in self.window_checkboxes if cb.isChecked()]
        if not sel and self.saved_snapshot:
            snap = self.saved_snapshot
            ns = len(snap.get('sample_names', []) or [])
            self.preview_label.setText(
                f"Keeping saved batch results · {snap.get('source_windows', 0)} "
                f"window(s) · {ns} samples")
            self.preview_label.setStyleSheet(
                f"padding:12px; background:{p.accent_soft}; border:1px solid {p.accent};"
                f" border-radius:6px; color:{p.text_primary}; font-weight:bold;")
        elif not sel:
            self.preview_label.setText("No windows selected")
            self.preview_label.setStyleSheet(
                f"padding:12px; background:{p.bg_tertiary}; border:1px solid {p.border};"
                f" border-radius:6px; color:{p.text_secondary}; font-weight:600;")
        else:
            ts = sum(len(getattr(cb.window_ref, 'data_by_sample', {})) for cb in sel)
            tp = sum(sum(len(p2) for p2 in getattr(cb.window_ref, 'sample_particle_data', {}).values()) for cb in sel)
            self.preview_label.setText(
                f"{len(sel)} window(s)  •  {ts} samples  •  {tp:,} particles")
            self.preview_label.setStyleSheet(
                f"padding:12px; background:{p.accent_soft}; border:1px solid {p.accent};"
                f" border-radius:6px; color:{p.text_primary}; font-weight:bold;")

    def get_selection(self):
        return [cb.window_ref for cb in self.window_checkboxes if cb.isChecked()]

class _CalculationWorker(QThread):
    """Runs a node's ``get_output_data()`` off the GUI thread.

    The Single- and Multi-Sample selector nodes filter and combine the raw
    particle data when their selection is confirmed (the OK button). On large
    datasets this can take a noticeable amount of time. Doing it here keeps the
    canvas responsive instead of freezing while the calculation runs.

    The ``finished_ok`` / ``failed`` signals are emitted from the worker thread
    but, because the receiving node lives on the GUI thread, Qt delivers them
    back on the GUI thread — so the slots are free to touch the scene/UI.
    """

    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, compute_fn, parent=None):
        super().__init__(parent)
        self._compute_fn = compute_fn

    def run(self):
        """Execute the calculation and report the result via a signal."""
        try:
            result = self._compute_fn()
        except Exception as exc:
            _itk_log.exception("Handled exception in run")
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(result)


class _StatusNodeMixin:
    """Adds status badge rendering to icon nodes."""

    def _status_text(self):
        return ""

    def _status_color(self):
        return DS.TEXT_SECONDARY

    def _is_calc_busy(self):
        """Return True while a background calculation is running.

        Returns:
            bool: Whether at least one worker thread is still active.
        """
        return bool(getattr(self, "_calc_workers", None))

    def _run_calculation_async(self):
        """Compute this node's output in a background thread, then push the
        result to every connected sink.

        Replaces the old synchronous loop (which called ``get_output_data()``
        directly on the GUI thread) so the canvas stays responsive while the
        calculation runs.
        """
        s = self.scene()
        if not s:
            return
        has_sink = any(lk.source_node == self.workflow_node
                       for lk in s.workflow_links)
        if not has_sink:
            return

        if not hasattr(self, "_calc_workers"):
            self._calc_workers = set()

        worker = _CalculationWorker(self.workflow_node.get_output_data)
        self._calc_workers.add(worker)
        worker.finished_ok.connect(self._on_calc_done)
        worker.failed.connect(self._on_calc_failed)
        worker.finished.connect(lambda w=worker: self._cleanup_worker(w))

        self.update()
        worker.start()

    def _on_calc_done(self, result):
        """Deliver the freshly computed output to every connected sink.

        Runs back on the GUI thread, so calling ``process_data`` here is safe.
        """
        s = self.scene()
        if s:
            for lk in s.workflow_links:
                if lk.source_node == self.workflow_node:
                    try:
                        if hasattr(lk.sink_node, "process_data"):
                            lk.sink_node.process_data(result)
                    except Exception as exc:
                        _itk_log.exception("Handled exception in _on_calc_done")
                        _itk_log.error(f"Data flow error: {exc}")
        self.update()

    def _on_calc_failed(self, message):
        """Handle a failed background calculation.

        Args:
            message (str): Error text from the worker thread.
        """
        _itk_log.error(f"Calculation error: {message}")
        self.update()

    def _cleanup_worker(self, worker):
        """Drop a finished worker so it can be garbage-collected."""
        workers = getattr(self, "_calc_workers", None)
        if workers is not None:
            workers.discard(worker)
        worker.deleteLater()
        self.update()


class SampleSelectorNodeItem(NodeItem, _StatusNodeMixin):
    """Single beaker icon."""
    def __init__(self, wf, pw=None):
        super().__init__(wf)
        self.parent_window = pw
        wf.configuration_changed.connect(self.update)
        wf.configuration_changed.connect(self._trigger)
        self.setAcceptHoverEvents(True)
        self._hovered = False

        self._tooltip_widget = ModernNodeTooltip()
        self._tooltip_widget.hide()

        self.hover_timer = QTimer()
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self._show_tooltip)
        self.hover_pos = None

    def paint(self, painter, option, widget=None):
        wf = self.workflow_node
        badge, bc = "", None
        if wf.selected_sample or (wf.sum_replicates and wf.replicate_samples):
            badge, bc = "✓", DS.SUCCESS
        elif wf.input_data:
            badge, bc = "⟳", DS.PURPLE
        else:
            badge, bc = "!", DS.ERROR

        if self._hovered:
            glow_color = QColor("#6366F1")
            for i in range(18, 0, -1):
                glow_color.setAlpha(int(120 * (1 - i / 18)))
                painter.setPen(QPen(glow_color, i * 1.2))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(self.boundingRect().center(), i * 2.2, i * 2.2)

        if self._is_calc_busy():
            badge, bc = "⏳", DS.WARNING

        self.paint_icon_node(
            painter, ("#6366F1", "#4338CA"),
            "fa6s.flask", "Sample",
            badge, bc,
        )

    def _trigger(self):
        """Run the node calculation in a background thread on (re)configure."""
        self._run_calculation_async()

    def configure_node(self):
        if self.parent_window:
            self.workflow_node.configure(self.parent_window)

    def _build_tooltip_lines(self):
        wf = self.workflow_node
        lines = ["Single Sample"]
        if wf.selected_sample:
            lines.append(f"Sample: {wf.selected_sample}")
            if wf.sum_replicates and wf.replicate_samples:
                lines.append(f"Replicates: {', '.join(wf.replicate_samples)}")
            if wf.selected_isotopes:
                lines.append(f"Isotopes: {', '.join(i['label'] if isinstance(i, dict) else str(i) for i in wf.selected_isotopes)}")


        else:
            lines.append("Status: Not configured")
        return lines

    def _show_tooltip(self):
        if not self.isUnderMouse() or self.hover_pos is None:
            return
        lines = self._build_tooltip_lines()
        self._tooltip_widget.set_content(lines, accent_color="#6366F1")
        pos = self.hover_pos
        tw = self._tooltip_widget
        x = pos.x() + 14
        y = pos.y() - tw.height() - 8
        screen = (QApplication.screenAt(pos) or QApplication.primaryScreen()).availableGeometry()
        if x + tw.width() > screen.right():
            x = pos.x() - tw.width() - 14
        if y < screen.top():
            y = pos.y() + 20
        tw.move(int(x), int(y))
        tw.show()
        tw.raise_()

    def hoverEnterEvent(self, event):
        super().hoverEnterEvent(event)
        self._hovered = True
        self.hover_pos = event.screenPos()
        self.hover_timer.start(400)
        self.update()

    def hoverMoveEvent(self, event):
        super().hoverMoveEvent(event)
        self.hover_pos = event.screenPos()
        if not self._tooltip_widget.isVisible():
            self.hover_timer.start(400)

    def hoverLeaveEvent(self, event):
        self.hover_timer.stop()
        self._tooltip_widget.hide()
        self._hovered = False
        super().hoverLeaveEvent(event)
        self.hover_pos = None
        self.update()


class ModernNodeTooltip(QWidget):
    """Custom floating tooltip with glow effect."""
    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._lines = []
        self._accent = QColor("#8B5CF6")

    def set_content(self, lines, accent_color=None):
        self._lines = lines
        if accent_color:
            self._accent = QColor(accent_color)
        self._recompute_size()
        self.update()

    def _recompute_size(self):
        fm = QFontMetrics(self._body_font())
        title_fm = QFontMetrics(self._title_font())
        max_w = 0
        for i, line in enumerate(self._lines):
            f = title_fm if i == 0 else fm
            max_w = max(max_w, QFontMetrics(f).horizontalAdvance(line))
        pad_x, pad_y = 18, 14
        line_h = fm.height()
        title_h = title_fm.height()
        total_h = pad_y * 2 + title_h + 6
        if len(self._lines) > 1:
            total_h += (len(self._lines) - 1) * (line_h + 4)
        self.setFixedSize(max_w + pad_x * 2, total_h + 6)

    def _title_font(self):
        f = QFont()
        f.setPixelSize(12)
        f.setWeight(QFont.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)
        return f

    def _body_font(self):
        f = QFont()
        f.setPixelSize(11)
        return f

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        glow_margin = 6
        rect = QRectF(glow_margin, glow_margin, w - glow_margin * 2, h - glow_margin * 2)

        accent = self._accent
        for i in range(glow_margin, 0, -1):
            glow = QColor(accent)
            glow.setAlpha(int(60 * (1 - i / glow_margin)))
            p.setPen(Qt.NoPen)
            p.setBrush(Qt.NoBrush)
            pen = QPen(glow, i * 1.5)
            p.setPen(pen)
            p.drawRoundedRect(rect.adjusted(-i, -i, i, i), 10 + i, 10 + i)

        bg = QColor(15, 10, 30, 230)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(rect, 10, 10)

        bar_grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
        bar_grad.setColorAt(0, QColor(accent.red(), accent.green(), accent.blue(), 200))
        bar_grad.setColorAt(1, QColor(accent.red(), accent.green(), accent.blue(), 0))
        p.setBrush(bar_grad)
        bar_rect = QRectF(rect.left(), rect.top(), rect.width(), 3)
        p.drawRect(bar_rect)

        border_color = QColor(accent)
        border_color.setAlpha(160)
        p.setPen(QPen(border_color, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect, 10, 10)

        pad_x, pad_y = 18, 14
        x = int(rect.left()) + pad_x
        y = int(rect.top()) + pad_y

        for i, line in enumerate(self._lines):
            if i == 0:
                p.setFont(self._title_font())
                p.setPen(QColor(accent))
                p.drawText(x, y + QFontMetrics(self._title_font()).ascent(), line)
                y += QFontMetrics(self._title_font()).height() + 2
                sep_color = QColor(accent)
                sep_color.setAlpha(60)
                p.setPen(QPen(sep_color, 1))
                p.drawLine(x, y + 2, int(rect.right()) - pad_x, y + 2)
                y += 8
            else:
                p.setFont(self._body_font())
                fm = QFontMetrics(self._body_font())
                if ": " in line:
                    label, val = line.split(": ", 1)
                    p.setPen(QColor(180, 170, 210))
                    p.drawText(x, y + fm.ascent(), label + ": ")
                    label_w = fm.horizontalAdvance(label + ": ")
                    p.setPen(QColor(230, 225, 255))
                    p.drawText(x + label_w, y + fm.ascent(), val)
                else:
                    p.setPen(QColor(200, 195, 230))
                    p.drawText(x, y + fm.ascent(), line)
                y += fm.height() + 4

        p.end()


class FigurePreviewPopup(QWidget):
    """Small framed thumbnail preview of a node's figure, shown on hover.

    Styled like the figure cards in the spread prototype: a compact white card
    with rounded corners, a soft drop shadow and the plot tucked inside.
    """

    _PAD = 13
    _INNER = 7
    _WIDTH = 190
    _RADIUS = 12

    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._pm = None
        self._accent = QColor("#38BDF8")

    def set_pixmap(self, pm, accent=None):
        """Set the preview thumbnail and resize the card to fit it."""
        if accent:
            self._accent = QColor(accent)
        if pm is not None and not pm.isNull():
            self._pm = pm.scaledToWidth(self._WIDTH, Qt.SmoothTransformation)
            card_w = self._pm.width() + self._INNER * 2
            card_h = self._pm.height() + self._INNER * 2
            self.setFixedSize(card_w + self._PAD * 2, card_h + self._PAD * 2)
        else:
            self._pm = None
        self.update()

    def paintEvent(self, event):
        """Paint a soft-shadowed white card with the figure thumbnail inside."""
        if self._pm is None or self._pm.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        pad = self._PAD
        card = QRectF(pad, pad, self.width() - pad * 2, self.height() - pad * 2)
        r = self._RADIUS

        p.setPen(Qt.NoPen)
        for i in range(10, 0, -1):
            p.setBrush(QColor(0, 0, 0, 7))
            p.drawRoundedRect(card.adjusted(-i, -i + 1, i, i + 3), r + i, r + i)

        p.setBrush(QColor(255, 255, 255))
        p.drawRoundedRect(card, r, r)

        inner = card.adjusted(self._INNER, self._INNER, -self._INNER, -self._INNER)
        clip = QPainterPath()
        clip.addRoundedRect(inner, 6, 6)
        p.save()
        p.setClipPath(clip)
        p.drawPixmap(inner.toRect(), self._pm)
        p.restore()

        p.setPen(QPen(QColor(226, 230, 238), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(card, r, r)
        p.end()


class _FanCardItem(QGraphicsObject):
    """One animated figure card in the hover fan (rotates/scales into place)."""

    selected = Signal(object)
    killed = Signal(object)

    def __init__(self, view, accent, pm):
        super().__init__()
        self.view = view
        self._accent = QColor(accent)
        self._pm = pm
        self.w = pm.width() + 12
        self.h = pm.height() + 12
        self.setOpacity(0.0)
        self.setScale(0.55)
        self.setZValue(1)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self._x_rect = QRectF(self.w / 2 - 24, -self.h / 2 + 6, 19, 19)
        self._seq = None
        self._hover_anim = None
        self._base_scale = 1.0
        self._base_z = 1

    def boundingRect(self):
        return QRectF(-self.w / 2 - 2, -self.h / 2 - 2, self.w + 4, self.h + 4)

    def paint(self, p, opt, widget=None):
        """Draw the white card, the clipped plot image, the accent border and
        the corner close (✕) button."""
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        rect = QRectF(-self.w / 2, -self.h / 2, self.w, self.h)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255))
        p.drawRoundedRect(rect, 10, 10)
        inner = rect.adjusted(6, 6, -6, -6)
        clip = QPainterPath()
        clip.addRoundedRect(inner, 6, 6)
        p.save()
        p.setClipPath(clip)
        p.drawPixmap(inner.toRect(), self._pm)
        p.restore()
        bc = QColor(self._accent)
        bc.setAlpha(170)
        p.setPen(QPen(bc, 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect, 10, 10)
        xr = self._x_rect
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 140))
        p.drawEllipse(xr)
        p.setPen(QPen(QColor(255, 255, 255), 1.6))
        p.drawLine(QPointF(xr.left() + 6, xr.top() + 6), QPointF(xr.right() - 6, xr.bottom() - 6))
        p.drawLine(QPointF(xr.right() - 6, xr.top() + 6), QPointF(xr.left() + 6, xr.bottom() - 6))

    def mousePressEvent(self, event):
        """Emit ``killed`` when the ✕ is clicked, otherwise ``selected``."""
        if self._x_rect.contains(event.pos()):
            self.killed.emit(self.view)
        else:
            self.selected.emit(self.view)
        event.accept()

    def hoverEnterEvent(self, event):
        self.setZValue(100)
        self._scale_to(self._base_scale * 1.14)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setZValue(self._base_z)
        self._scale_to(self._base_scale)
        super().hoverLeaveEvent(event)

    def _scale_to(self, scale):
        """Animate the card to ``scale`` (used for the hover pop)."""
        a = QPropertyAnimation(self, b"scale")
        a.setDuration(140)
        a.setEndValue(float(scale))
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim = a
        a.start()

    def animate_to(self, pos, rot, scale, opac, delay, dur=440):
        """Animate position, rotation, scale and opacity together (after an
        optional stagger ``delay``) to fan the card into place."""
        self._base_scale = float(scale)
        if self._seq:
            self._seq.stop()
        grp = QParallelAnimationGroup()
        for prop, end in ((b"pos", pos), (b"rotation", float(rot)),
                          (b"scale", float(scale)), (b"opacity", float(opac))):
            an = QPropertyAnimation(self, prop)
            an.setDuration(dur)
            an.setEndValue(end)
            an.setEasingCurve(QEasingCurve.Type.OutCubic)
            grp.addAnimation(an)
        if delay > 0:
            seq = QSequentialAnimationGroup()
            seq.addAnimation(QPauseAnimation(int(delay)))
            seq.addAnimation(grp)
            self._seq = seq
        else:
            self._seq = grp
        self._seq.start()


class FigureFanPopup(QWidget):
    """Hover fan of a node's open figures: spread, animated cards you pick/kill.

    Mirrors the spread prototype: cards emerge from a pivot near the node and
    fan out (rotation + scale + fade), staggered.
    """

    select_figure = Signal(object)
    close_figure = Signal(object)

    ANGLE = 110.0
    DISTANCE = 80.0
    STAGGER = 110

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._gview = QGraphicsView(self)
        self._gview.setFrameShape(QFrame.NoFrame)
        self._gview.setStyleSheet("background: transparent; border: none;")
        self._gview.setRenderHint(QPainter.Antialiasing)
        self._gview.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._gview.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._gview.setAttribute(Qt.WA_TranslucentBackground)
        self._gview.viewport().setAttribute(Qt.WA_TranslucentBackground)
        self._scene = QGraphicsScene(self)
        self._gview.setScene(self._scene)
        self._gview.viewport().installEventFilter(self)
        self._cards = []
        self.on_enter = None
        self.on_leave = None

    def eventFilter(self, obj, event):
        """Forward viewport enter/leave to the on_enter/on_leave callbacks."""
        if obj is self._gview.viewport():
            if event.type() == QEvent.Type.Enter and self.on_enter:
                self.on_enter()
            elif event.type() == QEvent.Type.Leave and self.on_leave:
                self.on_leave()
        return False

    def has_cards(self):
        """True if the fan currently holds any figure cards."""
        return bool(self._cards)

    def _placeholder_pixmap(self, w, idx, accent):
        """A neutral 'Figure N' card image for a restored figure with no thumbnail."""
        h = int(w * 0.72)
        pm = QPixmap(w, h)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(245, 247, 250))
        p.drawRoundedRect(0, 0, w, h, 8, 8)
        ac = QColor(accent)
        ac.setAlpha(70)
        p.setPen(QPen(ac, 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(1, 1, w - 2, h - 2, 8, 8)
        p.setPen(QColor(120, 130, 145))
        f = QFont(DS.FONT_FAMILY)
        f.setPixelSize(max(11, int(w * 0.1)))
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, f"Figure {idx}")
        p.end()
        return pm

    def set_views(self, views, accent, zoom=1.0):
        """Build one card per figure view and fan them out around a pivot.

        Cards are sized to the canvas zoom, laid out along an arc of ``ANGLE``
        degrees at radius ``DISTANCE`` and animated into place with a per-card
        ``STAGGER`` delay.
        """
        import math
        for c in self._cards:
            try:
                self._scene.removeItem(c)
            except Exception:
                pass
        self._cards = []
        z = max(0.65, min(1.6, zoom))
        thumb_w = int(150 * z)
        data = []
        for idx, v in enumerate(views, 1):
            pm = getattr(v, 'thumbnail', None)
            if pm is None or pm.isNull():
                spm = self._placeholder_pixmap(thumb_w, idx, accent)
            else:
                spm = pm.scaledToWidth(thumb_w, Qt.SmoothTransformation)
            data.append((v, spm))
        n = len(data)
        if n == 0:
            self.setFixedSize(1, 1)
            return
        cw = data[0][1].width() + 12
        ch = data[0][1].height() + 12
        R = self.DISTANCE * z
        half = math.radians(self.ANGLE / 2.0)
        span_w = 2.0 * (R * math.sin(half)) + cw + 40
        W = int(max(cw + 50, span_w))
        H = int(R + ch + 44)
        self.setFixedSize(W, H)
        self._gview.setGeometry(0, 0, W, H)
        self._scene.setSceneRect(0, 0, W, H)
        pivot = QPointF(W / 2.0, H - ch / 2.0 - 10)
        for i, (v, spm) in enumerate(data):
            card = _FanCardItem(v, accent, spm)
            card.selected.connect(self.select_figure)
            card.killed.connect(self.close_figure)
            self._scene.addItem(card)
            card.setPos(pivot)
            self._cards.append(card)
            t = 0.0 if n == 1 else (i - (n - 1) / 2.0) / (n - 1)
            ang = t * self.ANGLE
            rad = math.radians(ang)
            cx = pivot.x() + R * math.sin(rad)
            cy = pivot.y() - R * math.cos(rad)
            card.animate_to(QPointF(cx, cy), ang, 1.0, 1.0, delay=i * self.STAGGER)

    def enterEvent(self, event):
        if self.on_enter:
            self.on_enter()

    def leaveEvent(self, event):
        if self.on_leave:
            self.on_leave()


class StickyNoteItem(QGraphicsWidget):
    """A movable, editable sticky note with color, font-size and transparency support.
    Right-click empty canvas → Add Note. Double-click to edit."""
    MIN_W, MIN_H = 160, 80

    COLOR_PRESETS = [
        ("Yellow",  "#FFF8DC", "#3D3000", "#E6B800"),
        ("Blue",    "#DBEAFE", "#1E3A5F", "#3B82F6"),
        ("Green",   "#DCFCE7", "#052E16", "#22C55E"),
        ("Pink",    "#FCE7F3", "#4A0020", "#EC4899"),
        ("Purple",  "#EDE9FE", "#2E1065", "#A855F7"),
        ("Orange",  "#FFEDD5", "#431407", "#F97316"),
        ("White",   "#FFFFFF", "#334155", "#94A3B8"),
    ]

    def __init__(self, text="Double-click to edit…", parent=None):
        super().__init__(parent)
        self._text = text
        self._color_index = 0
        self._font_size = DS.FONT_SMALL
        self._transparent = False
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self._hovered = False
        self.resize(self.MIN_W, self.MIN_H)

    # ── helpers ────────────────────────────────────────────────────────────
    def _current_colors(self):
        """Return (bg_color, border_color, text_color) based on current settings."""
        _, light_bg, dark_bg, border_hex = self.COLOR_PRESETS[self._color_index]
        if self._transparent:
            bg = QColor(0, 0, 0, 0)
        else:
            bg = QColor(light_bg) if not _app_theme.is_dark else QColor(dark_bg)
        border = QColor(border_hex)
        if self.isSelected() or self._hovered:
            border = border.lighter(130)
        if self._transparent:
            txt = QColor(_app_theme.palette.text_primary)
        elif not _app_theme.is_dark:
            txt = QColor(bg).darker(180)
        else:
            txt = QColor(bg).lighter(220)
        return bg, border, txt

    def boundingRect(self):
        m = 6
        return QRectF(-m, -m, self.size().width() + 2*m, self.size().height() + 2*m)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.size().width(), self.size().height()
        body = QRectF(0, 0, w, h)
        bg, border_col, txt_col = self._current_colors()

        if not self._transparent:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 25))
            painter.drawRoundedRect(body.adjusted(3, 4, 3, 4), 6, 6)

        painter.setBrush(bg)
        pen_width = 2.0 if (self.isSelected() or self._hovered) else 1.5
        painter.setPen(QPen(border_col, pen_width))
        painter.drawRoundedRect(body, 6, 6)

        if not self._transparent:
            fold = 14
            fold_path = QPainterPath()
            fold_path.moveTo(w - fold, 0)
            fold_path.lineTo(w, fold)
            fold_path.lineTo(w - fold, fold)
            fold_path.closeSubpath()
            painter.setBrush(border_col.darker(115))
            painter.setPen(Qt.NoPen)
            painter.drawPath(fold_path)

        painter.setPen(txt_col)
        f = QFont(DS.FONT_FAMILY, self._font_size)
        painter.setFont(f)
        right_margin = -18 if not self._transparent else -8
        painter.drawText(body.adjusted(8, 8, right_margin, -6),
                         Qt.AlignTop | Qt.AlignLeft | Qt.TextWordWrap, self._text)

    def hoverEnterEvent(self, event):
        self._hovered = True; self.update(); super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False; self.update(); super().hoverLeaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        from PySide6.QtWidgets import QInputDialog
        parent_widget = None
        if self.scene() and self.scene().views():
            parent_widget = self.scene().views()[0]
        text, ok = QInputDialog.getMultiLineText(
            parent_widget, "Edit Note", "Note text:", self._text
        )
        if ok:
            self._text = text
            fm = QFontMetrics(QFont(DS.FONT_FAMILY, self._font_size))
            lines = max(2, text.count("\n") + 1 + sum(len(ln) // 18 for ln in text.split("\n")))
            self.resize(self.size().width(), max(self.MIN_H, 16 + lines * (fm.height() + 2)))
            self.update()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._show_context_menu(event.screenPos())
            return
        if event.button() == Qt.LeftButton:
            if self.scene() and not self.isSelected():
                self.scene().clearSelection()
            self.setSelected(True)
        super().mousePressEvent(event)

    def _show_context_menu(self, global_pos):
        menu = QMenu()
        menu.setStyleSheet(NodeItem._ctx_menu_style())

        # ── Color submenu ──────────────────────────────────────────────────
        color_menu = menu.addMenu(
            qta.icon('fa6s.palette', color=DS.ACCENT), "  Note Color")
        color_menu.setStyleSheet(NodeItem._ctx_menu_style())
        for i, (name, light_bg, dark_bg, border) in enumerate(self.COLOR_PRESETS):
            act = color_menu.addAction(name)
            preview = QColor(light_bg) if not _app_theme.is_dark else QColor(dark_bg)
            px = QPixmap(14, 14)
            px.fill(preview)
            act.setIcon(QIcon(px))
            if i == self._color_index:
                act.setText(f"✓  {name}")
            act.setData(i)
            act.triggered.connect(lambda checked=False, idx=i: self._set_color(idx))

        # ── Font size submenu ──────────────────────────────────────────────
        size_menu = menu.addMenu(
            qta.icon('fa6s.text-height', color=DS.ACCENT), "  Text Size")
        size_menu.setStyleSheet(NodeItem._ctx_menu_style())
        for size, label in [(8, "Tiny (8)"), (9, "Small (9)"), (10, "Normal (10)"),
                             (12, "Medium (12)"), (14, "Large (14)"), (16, "XL (16)")]:
            act = size_menu.addAction(f"✓  {label}" if size == self._font_size else f"   {label}")
            act.triggered.connect(lambda checked=False, s=size: self._set_font_size(s))

        menu.addSeparator()

        # ── Transparency toggle ────────────────────────────────────────────
        trans_icon = 'fa6s.eye-slash' if self._transparent else 'fa6s.eye'
        trans_label = "  Make Opaque" if self._transparent else "  Make Transparent"
        trans_act = menu.addAction(qta.icon(trans_icon, color=DS.CYAN), trans_label)
        trans_act.triggered.connect(self._toggle_transparent)

        menu.addSeparator()
        del_act = menu.addAction(qta.icon("fa6s.trash-can", color=DS.ERROR), "  Delete Note")
        del_act.triggered.connect(self._delete_self)
        menu.exec(global_pos)

    def _set_color(self, index):
        self._color_index = index
        self.update()

    def _set_font_size(self, size):
        self._font_size = size
        fm = QFontMetrics(QFont(DS.FONT_FAMILY, size))
        lines = max(2, self._text.count("\n") + 1 +
                    sum(len(ln) // 18 for ln in self._text.split("\n")))
        self.resize(self.size().width(), max(self.MIN_H, 16 + lines * (fm.height() + 2)))
        self.update()

    def _toggle_transparent(self):
        self._transparent = not self._transparent
        self.update()

    def _delete_self(self):
        if self.scene():
            self.scene().removeItem(self)

class MultipleSampleSelectorNodeItem(NodeItem, _StatusNodeMixin):
    def __init__(self, wf, pw=None):
        super().__init__(wf)
        self.parent_window = pw
        wf.configuration_changed.connect(self.update)
        wf.configuration_changed.connect(self._trigger)
        self.setAcceptHoverEvents(True)

        self._tooltip_widget = ModernNodeTooltip()
        self._tooltip_widget.hide()

        self.hover_timer = QTimer()
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self._show_tooltip)

        self.hover_pos = None

    def paint(self, painter, option, widget=None):
        wf = self.workflow_node
        badge, bc = "", None
        if wf.selected_samples:
            badge, bc = "✓", DS.SUCCESS
        elif wf.input_data:
            badge, bc = "⟳", DS.PURPLE
        else:
            badge, bc = "!", DS.ERROR
        if self._is_calc_busy():
            badge, bc = "⏳", DS.WARNING
        self.paint_icon_node(
            painter, ("#8B5CF6", "#6D28D9"),
            "fa6s.flask-vial", "Multi-Sample",
            badge, bc,
        )

    def _trigger(self):
        """Run the node calculation in a background thread on (re)configure."""
        self._run_calculation_async()

    def configure_node(self):
        if self.parent_window:
            self.workflow_node.configure(self.parent_window)

    def _build_tooltip_lines(self):
        wf = self.workflow_node
        lines = ["Multi-Sample"]
        if wf.selected_samples:
            lines.append(f"Total: {len(wf.selected_samples)} samples")
            if hasattr(wf, 'sample_config') and wf.sample_config:
                groups = set()
                for config in wf.sample_config.values():
                    if config.get('included', False):
                        group = config.get('sum_group', '').strip()
                        if group:
                            groups.add(group)
                if groups:
                    lines.append(f"Groups: {', '.join(sorted(groups))}")
            if wf.selected_isotopes:
                lines.append(f"Isotopes: {', '.join(i['label'] if isinstance(i, dict) else str(i) for i in wf.selected_isotopes)}")

        else:
            lines.append("Status: Not configured")
        return lines

    def _show_tooltip(self):
        if not self.isUnderMouse() or self.hover_pos is None:
            return
        lines = self._build_tooltip_lines()
        self._tooltip_widget.set_content(lines, accent_color="#8B5CF6")
        pos = self.hover_pos
        tw = self._tooltip_widget
        x = pos.x() + 14
        y = pos.y() - tw.height() - 8
        screen = (QApplication.screenAt(pos) or QApplication.primaryScreen()).availableGeometry()
        if x + tw.width() > screen.right():
            x = pos.x() - tw.width() - 14
        if y < screen.top():
            y = pos.y() + 20
        tw.move(int(x), int(y))
        tw.show()
        tw.raise_()

    def hoverEnterEvent(self, event):
        super().hoverEnterEvent(event)
        self.hover_pos = event.screenPos()
        self.hover_timer.start(400)

    def hoverMoveEvent(self, event):
        super().hoverMoveEvent(event)
        self.hover_pos = event.screenPos()
        if not self._tooltip_widget.isVisible():
            self.hover_timer.start(400)

    def hoverLeaveEvent(self, event):
        self.hover_timer.stop()
        self._tooltip_widget.hide()
        super().hoverLeaveEvent(event)
        self.hover_pos = None

class BatchSampleSelectorNodeItem(NodeItem, _StatusNodeMixin):
    """Globe / multi-window icon."""
    def __init__(self, wf, pw=None):
        super().__init__(wf)
        self.parent_window = pw
        wf.configuration_changed.connect(self.update)
        wf.configuration_changed.connect(self._trigger)

    def paint(self, painter, option, widget=None):
        wf = self.workflow_node
        badge, bc = "", None
        if wf.selected_windows or getattr(wf, '_saved_output_snapshot', None):
            badge, bc = "✓", DS.SUCCESS
        else:
            badge, bc = "!", DS.ERROR
        self.paint_icon_node(
            painter, ("#14B8A6", "#0F766E"),
            "fa6s.window-restore", "Batch",
            badge, bc,
        )

    def _trigger(self):
        s = self.scene()
        if s:
            for lk in s.workflow_links:
                if lk.source_node == self.workflow_node:
                    s._trigger_data_flow(lk)

    def configure_node(self):
        if self.parent_window:
            self.workflow_node.configure(self.parent_window)

def _make_viz_icon_node(grad_colors, icon_name, label, dialog_class, multi_figure=False):
    """Factory: creates a circular icon node for each visualization type."""

    class VizIconNodeItem(NodeItem):
        def __init__(self, wf, pw=None):
            super().__init__(wf)
            self.parent_window = pw
            wf.configuration_changed.connect(self.update)
            self.setAcceptHoverEvents(True)
            self._accent = grad_colors[0]
            self._preview_timer = QTimer()
            self._preview_timer.setSingleShot(True)
            self._preview_timer.timeout.connect(self._show_preview)
            self._watch_timer = QTimer()
            self._watch_timer.setInterval(120)
            self._watch_timer.timeout.connect(self._watch_cursor)
            self._preview_pos = None
            self._prime_attempted = False
            self._preview_popup = FigurePreviewPopup()
            self._preview_popup.hide()
            if multi_figure:
                self._fan = FigureFanPopup()
                self._fan.hide()
                self._fan.select_figure.connect(self._focus_figure)
                self._fan.close_figure.connect(self._close_figure)
                self._restore_saved_figures(wf)
            else:
                self._fan = None

        def _restore_saved_figures(self, wf):
            """Rebuild figures saved with the project (no windows opened yet)."""
            stashed = getattr(wf, '_restored_figure_configs', None)
            if not stashed:
                return
            wf._restored_figure_configs = None
            try:
                from results.shared_plot_utils import rebuild_node_figures
                rebuild_node_figures(wf, dialog_class, self.parent_window, stashed)
                self.update()
            except Exception:
                _itk_log.exception("Handled exception in _restore_saved_figures")

        def paint(self, painter, option, widget=None):
            if multi_figure:
                n = len(getattr(self.workflow_node, '_figures', []) or [])
                badge = str(n) if n else ""
                bc = QColor(grad_colors[0]) if n else None
                self.paint_icon_node(painter, grad_colors, icon_name, label, badge, bc)
            else:
                self.paint_icon_node(painter, grad_colors, icon_name, label)

        def configure_node(self):
            """Open the node's figure on double-click.

            For multi-figure nodes each call opens a new independent figure;
            closing one only hides it, so it stays selectable from the hover
            fan. Single-figure nodes reuse one persistent dialog.
            """
            ual = _ual()
            if ual:
                ual.log_action('DIALOG_OPEN', f'Opened viz node: {label}',
                            {'node_type': self.workflow_node.node_type,
                                'dialog': dialog_class.__name__})
            if multi_figure:
                from results.shared_plot_utils import open_node_figures
                self._active_dialog = open_node_figures(
                    self.workflow_node, dialog_class, self.parent_window,
                    always_new=True)
                self.update()
            else:
                from results.shared_plot_utils import show_persistent_figure
                self._active_dialog = show_persistent_figure(
                    self.workflow_node,
                    lambda: dialog_class(self.workflow_node, self.parent_window))

        def _figure_views(self):
            """Return all of this node's figure views (live or restored)."""
            return list(getattr(self.workflow_node, '_figures', []) or [])

        def _current_zoom(self):
            try:
                vs = self.scene().views()
                if vs:
                    return vs[0].transform().m11()
            except Exception:
                pass
            return 1.0

        def _screen_geo(self, pt):
            """Available geometry of the screen under ``pt``.

            Resolves the monitor the cursor/node is actually on so popups land
            on the correct display in a multi-monitor setup, falling back to the
            primary screen.
            """
            scr = None
            try:
                if pt is not None:
                    scr = QApplication.screenAt(pt)
            except Exception:
                scr = None
            if scr is None:
                scr = QApplication.primaryScreen()
            return scr.availableGeometry()

        def _show_preview(self):
            """Show the hover preview for this node.

            Multi-figure nodes with open figures fan them out; otherwise a
            single thumbnail is shown. This single path also serves a multi
            node before any figure exists, so a freshly-connected node previews
            automatically, priming the thumbnail off-screen when missing.
            """
            try:
                if not self.isUnderMouse() or self._preview_pos is None:
                    return
                if multi_figure and self._figure_views():
                    self._show_fan()
                    return
                pm = getattr(self.workflow_node, '_figure_thumbnail', None)
                if pm is None or pm.isNull():
                    if self._prime_thumbnail():
                        self._preview_timer.start(600)
                    return
                tw = self._preview_popup
                tw.set_pixmap(pm, self._accent)
                pos = self._preview_pos
                x = pos.x() + 18
                y = pos.y() - tw.height() - 10
                screen = self._screen_geo(pos)
                if x + tw.width() > screen.right():
                    x = pos.x() - tw.width() - 18
                if y < screen.top():
                    y = pos.y() + 22
                tw.move(int(x), int(y))
                tw.show()
                tw.raise_()
                self._start_watch()
            except Exception:
                _itk_log.exception("Handled exception in _show_preview")

        def _show_fan(self):
            """Position and show the hover fan above the node, on-screen-clamped."""
            views = self._figure_views()
            if not views:
                return
            fan = self._fan
            fan.set_views(views, self._accent, self._current_zoom())
            if not fan.has_cards():
                return
            pos = self._preview_pos
            x = pos.x() - fan.width() // 2
            y = pos.y() - fan.height() - 12
            screen = self._screen_geo(pos)
            x = max(screen.left() + 8, min(x, screen.right() - fan.width() - 8))
            if y < screen.top() + 8:
                y = pos.y() + 24
            fan.move(int(x), int(y))
            fan.show()
            fan.raise_()
            self._start_watch()

        def _focus_figure(self, view):
            """Bring the figure picked from the fan to the front."""
            try:
                from results.shared_plot_utils import focus_node_figure
                focus_node_figure(view)
                if self._fan is not None:
                    self._fan.raise_()
            except Exception:
                _itk_log.exception("Handled exception in _focus_figure")

        def _close_figure(self, view):
            """Kill the figure picked from the fan, then refresh or hide the fan."""
            try:
                from results.shared_plot_utils import close_node_figure
                close_node_figure(view)
                self.update()
                views = self._figure_views()
                if views:
                    self._fan.set_views(views, self._accent, self._current_zoom())
                else:
                    self._do_hide()
            except Exception:
                _itk_log.exception("Handled exception in _close_figure")

        def _prime_thumbnail(self):
            """Build the figure off-screen once (if it has data) so a preview
            exists before the user opens it. Returns True if a build started."""
            if self._prime_attempted:
                return False
            wf = self.workflow_node
            if getattr(wf, 'input_data', None) is None:
                return False
            self._prime_attempted = True
            try:
                from results.shared_plot_utils import prime_figure_thumbnail
                prime_figure_thumbnail(
                    wf, lambda: dialog_class(wf, self.parent_window))
                return True
            except Exception:
                _itk_log.exception("Handled exception in _prime_thumbnail")
                return False

        def _node_screen_rect(self):
            """This node's bounding box in global screen coordinates."""
            try:
                vs = self.scene().views()
                if not vs:
                    return None
                view = vs[0]
                r = view.mapFromScene(self.sceneBoundingRect()).boundingRect()
                tl = view.viewport().mapToGlobal(r.topLeft())
                return QRect(tl.x(), tl.y(), r.width(), r.height())
            except Exception:
                return None

        def _start_watch(self):
            if not self._watch_timer.isActive():
                self._watch_timer.start()

        def _watch_cursor(self):
            """Hide the popup once the cursor leaves the node and popup areas.

            Keeps the preview/fan open while the cursor is within a small margin
            of either the node or any visible popup, so the user can move onto
            the popup without it vanishing.
            """
            try:
                cur = QCursor.pos()
                m = 28
                over = False
                nr = self._node_screen_rect()
                if nr is not None and nr.adjusted(-m, -m, m, m).contains(cur):
                    over = True
                for popup in (self._fan, self._preview_popup):
                    if popup is not None and popup.isVisible():
                        if popup.geometry().adjusted(-m, -m, m, m).contains(cur):
                            over = True
                if not over:
                    self._do_hide()
            except Exception:
                _itk_log.exception("Handled exception in _watch_cursor")

        def _do_hide(self):
            try:
                self._watch_timer.stop()
                if self._fan is not None:
                    self._fan.hide()
                if self._preview_popup is not None:
                    self._preview_popup.hide()
            except Exception:
                _itk_log.exception("Handled exception in _do_hide")

        def _popup_visible(self):
            return ((self._fan is not None and self._fan.isVisible())
                    or (self._preview_popup is not None
                        and self._preview_popup.isVisible()))

        def hoverEnterEvent(self, event):
            super().hoverEnterEvent(event)
            self._preview_pos = event.screenPos()
            self._preview_timer.start(350)

        def hoverMoveEvent(self, event):
            super().hoverMoveEvent(event)
            self._preview_pos = event.screenPos()
            if not self._popup_visible():
                self._preview_timer.start(350)

        def hoverLeaveEvent(self, event):
            """Stop the open timer; the cursor-watch timer handles hiding."""
            self._preview_timer.stop()
            super().hoverLeaveEvent(event)

    VizIconNodeItem.__name__ = f"{label.replace(' ', '').replace('/', '')}IconNodeItem"
    return VizIconNodeItem

HistogramPlotNodeItem = _make_viz_icon_node(
    ("#F97316", "#C2410C"), "fa6s.chart-column", "Histogram",
    HistogramDisplayDialog, multi_figure=True)

ElementBarChartPlotNodeItem = _make_viz_icon_node(
    ("#EF4444", "#B91C1C"), "fa6s.chart-bar", "Bar Chart",
    ElementBarChartDisplayDialog, multi_figure=True)

BoxPlotNodeItem = _make_viz_icon_node(
    ("#8B5CF6", "#6D28D9"), "fa6s.chart-simple", "Box Plot",
    BoxPlotDisplayDialog, multi_figure=True)

CorrelationPlotNodeItem = _make_viz_icon_node(
    ("#EC4899", "#BE185D"), "fa6s.chart-line", "Correlation",
    CorrelationPlotDisplayDialog, multi_figure=True)

PieChartPlotNodeItem = _make_viz_icon_node(
    ("#14B8A6", "#0F766E"), "fa6s.chart-pie", "Pie Chart",
    PieChartDisplayDialog, multi_figure=True)

ElementCompositionPlotNodeItem = _make_viz_icon_node(
    ("#06B6D4", "#0E7490"), "fa6s.circle-half-stroke", "Composition",
    ElementCompositionDisplayDialog, multi_figure=True)

HeatmapPlotNodeItem = _make_viz_icon_node(
    ("#F59E0B", "#B45309"), "fa6s.fire", "Heatmap",
    HeatmapDisplayDialog, multi_figure=True)

MolarRatioPlotNodeItem = _make_viz_icon_node(
    ("#6366F1", "#4338CA"), "fa6s.divide", "Molar Ratio",
    MolarRatioDisplayDialog, multi_figure=True)

IsotopicRatioPlotNodeItem = _make_viz_icon_node(
    ("#A855F7", "#7E22CE"), "fa6s.atom", "Isotope Ratio",
    IsotopicRatioDisplayDialog, multi_figure=True)

TrianglePlotNodeItem = _make_viz_icon_node(
    ("#22C55E", "#15803D"), "fa6s.play", "Ternary",
    TriangleDisplayDialog, multi_figure=True)

SingleMultipleElementPlotNodeItem = _make_viz_icon_node(
    ("#3B82F6", "#1D4ED8"), "fa6s.layer-group", "Single/Multi",
    SingleMultipleElementDisplayDialog, multi_figure=True)

ClusteringPlotNodeItem = _make_viz_icon_node(
    ("#0EA5E9", "#0369A1"), "fa6s.circle-nodes", "Clustering",
    ClusteringDisplayDialog, multi_figure=True)

CorrelationMatrixNodeItem = _make_viz_icon_node(
    ("#F43F5E", "#BE123C"), "fa6s.table-cells", "Corr. Matrix",
    CorrelationMatrixDisplayDialog, multi_figure=True)

ConcentrationComparisonNodeItem = _make_viz_icon_node(
    ("#8B5CF6", "#6D28D9"), "fa6s.arrows-left-right", "Concentration",
    ConcentrationDisplayDialog, multi_figure=True)

NetworkDiagramNodeItem = _make_viz_icon_node(
    ("#14B8A6", "#0F766E"), "fa6s.diagram-project", "Network",
    NetworkDisplayDialog, multi_figure=True)

DashboardNodeItem = _make_viz_icon_node(
    ("#3B82F6", "#1D4ED8"), "fa6s.gauge-high", "Dashboard",
    DashboardDisplayDialog, multi_figure=True)


class AIAssistantNodeItem(NodeItem):
    """AI sparkle icon."""
    def __init__(self, wf, pw=None):
        super().__init__(wf)
        self.parent_window = pw
        wf.configuration_changed.connect(self.update)

    def paint(self, painter, option, widget=None):
        st = "✓" if self.workflow_node.input_data else ""
        sc = DS.SUCCESS if self.workflow_node.input_data else None
        self.paint_icon_node(
            painter, ("#EC4899", "#BE185D"),
            "fa6s.wand-magic-sparkles", "AI Assistant",
            st, sc,
        )

    def configure_node(self):
        if self.parent_window:
            self.workflow_node.configure(self.parent_window)

_PENDING_DRAG_NODE_TYPE = None


class DraggableNodeButton(QPushButton):

    def __init__(self, text, node_type, icon_name=None, color=None):
        super().__init__(text)
        self.node_type = node_type
        self._icon_name = icon_name
        self._color = color or DS.ACCENT
        self.setMinimumHeight(34)
        self.setCursor(QCursor(Qt.OpenHandCursor))
        self._refresh_style()
        _app_theme.themeChanged.connect(lambda _: self._refresh_style())

    def _refresh_style(self):
        p = _app_theme.palette
        if self._icon_name:
            self.setIcon(qta.icon(self._icon_name, color=self._color))
        self.setStyleSheet(f"""
            QPushButton {{
                background: {p.bg_tertiary};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 8px;
                padding: 7px 10px;
                text-align: left;
                font-size: 12px;
                font-weight: 500;
                font-family: '{DS.FONT_FAMILY}';
            }}
            QPushButton:hover {{
                background: {p.accent_soft};
                border-color: {p.accent};
                color: {p.accent};
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            ual = _ual()
            if ual:
                ual.log_action('CLICK',
                               f'Dragged node from palette: {self.text().strip()}',
                               {'node_type': self.node_type})
            self._drag = QDrag(self)
            self._mime = QMimeData()
            self._mime.setText(self.node_type)
            self._drag.setMimeData(self._mime)
            px = self.grab()
            self._drag.setPixmap(px)
            self._drag.setHotSpot(QPoint(px.width()//2, px.height()//2))
            global _PENDING_DRAG_NODE_TYPE
            _PENDING_DRAG_NODE_TYPE = self.node_type
            try:
                self._drag.exec_(Qt.CopyAction)
            finally:
                _PENDING_DRAG_NODE_TYPE = None
        super().mousePressEvent(event)

class _CollapsibleGroup(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self._expanded = True
        self._title = title
        self._btn = QPushButton(f"  ▾  {title}")
        self._btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn.clicked.connect(self.toggle)
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        vl.addWidget(self._btn)
        vl.addWidget(self._container)

        self._apply_theme()
        _app_theme.themeChanged.connect(lambda _: self._apply_theme())

    def _apply_theme(self):
        p = _app_theme.palette
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {p.text_secondary};
                border: none;
                text-align: left;
                font-weight: 700;
                font-size: 11px;
                padding: 6px 4px;
                font-family: '{DS.FONT_FAMILY}';
            }}
            QPushButton:hover {{ color: {p.accent}; }}
        """)

    def addWidget(self, w):
        self._layout.addWidget(w)

    def toggle(self):
        self._expanded = not self._expanded
        self._container.setVisible(self._expanded)
        arrow = "▾" if self._expanded else "▸"
        self._btn.setText(f"  {arrow}  {self._title}")


class NodePalette(QWidget):

    def __init__(self, parent_window=None):
        super().__init__()
        self.parent_window = parent_window
        self._all_buttons = []
        self._setup()

    def _setup(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._apply_palette_theme()
        _app_theme.themeChanged.connect(lambda _: self._apply_palette_theme())

        self.search = QLineEdit()
        self.search.setPlaceholderText("  🔍  Search nodes…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        root.addWidget(self.search)
        self._apply_palette_theme()  

        self._scroll_area = QScrollArea()
        scroll = self._scroll_area
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(10, 4, 10, 10)
        cl.setSpacing(4)

        # ── Data Processing ────────────────────────────────────────────────
        dg = _CollapsibleGroup("DATA PROCESSING")
        for txt, ntype, icon, color in [
            ("Single Sample",    "sample_selector",          'fa6s.flask',           DS.INDIGO),
            ("Multiple Sample",  "multiple_sample_selector", 'fa6s.flask-vial',          DS.PURPLE),
            ("Batch Windows",    "batch_sample_selector",    'fa6s.window-restore',  DS.TEAL),
            ("Particle Filter",  "particle_filter",          'fa6s.filter',          DS.TEAL),
            ("Particle Classifier", "particle_classifier",   'fa6s.tags',            DS.INDIGO),
        ]:
            b = DraggableNodeButton(txt, ntype, icon, color)
            dg.addWidget(b)
            self._all_buttons.append((b, txt))
        cl.addWidget(dg)

        # ── Visualization ──────────────────────────────────────────────────
        vg = _CollapsibleGroup("VISUALIZATION")
        for txt, ntype, icon, color in [
            ("Histogram",         "histogram_plot",                'fa6s.chart-column',       DS.ORANGE),
            ("Element Bar Chart", "element_bar_chart_plot",        'fa6s.chart-bar',          DS.ERROR),
            ("Box Plot",          "box_plot",                      'fa6s.chart-simple',       DS.PURPLE),
            ("Correlation",       "correlation_plot",              'fa6s.chart-line',         DS.PINK),
            ("Pie Chart",         "pie_chart_plot",                'fa6s.chart-pie',          DS.TEAL),
            ("Composition",       "element_composition_plot",      'fa6s.circle-half-stroke', DS.CYAN),
            ("Heatmap",           "heatmap_plot",                  'fa6s.fire',               DS.WARNING),
            ("Molar Ratio",       "molar_ratio_plot",              'fa6s.divide',             DS.INDIGO),
            ("Isotopic Ratio",    "isotopic_ratio_plot",           'fa6s.atom',               DS.PURPLE),
            ("Ternary Plot",      "triangle_plot",                 'fa6s.play',               DS.SUCCESS),
            ("Single / Multiple", "single_multiple_element_plot",  'fa6s.layer-group',        DS.ACCENT),
            ("Clustering",        "clustering_plot",               'fa6s.circle-nodes',       DS.CYAN),
            ("Corr. Matrix",      "correlation_matrix",            'fa6s.table-cells',        DS.PINK),
            ("Concentration",     "concentration_comparison",      'fa6s.arrows-left-right',  DS.PURPLE),
            ("Network",           "network_diagram",               'fa6s.diagram-project',    DS.TEAL),
            ("Dashboard",           "dashboard",                    'fa6s.gauge-high',        DS.ACCENT),
        ]:
            b = DraggableNodeButton(txt, ntype, icon, color)
            vg.addWidget(b)
            self._all_buttons.append((b, txt))
        cl.addWidget(vg)

        ag = _CollapsibleGroup("AI & ANALYTICS")
        b = DraggableNodeButton("AI Data Assistant", "ai_assistant",
                                'fa6s.wand-magic-sparkles', DS.PINK)
        ag.addWidget(b)
        self._all_buttons.append((b, "AI Data Assistant"))
        cl.addWidget(ag)

        cl.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

        self._hint_label = QLabel("Drag → Canvas  •  Del = delete  •  Ctrl+C = duplicate  •  Ctrl+Z = undo")
        hint = self._hint_label
        hint.setWordWrap(True)
        root.addWidget(hint)
        self._apply_palette_theme()

    def _apply_palette_theme(self):
        p = _app_theme.palette
        self.setStyleSheet(f"background: {p.bg_secondary};")
        if hasattr(self, 'search'):
            self.search.setStyleSheet(f"""
                QLineEdit {{
                    background: {p.bg_tertiary};
                    color: {p.text_primary};
                    border: 1px solid {p.border};
                    border-radius: 8px;
                    padding: 8px 12px;
                    margin: 10px 10px 6px 10px;
                    font-size: 12px;
                }}
                QLineEdit:focus {{ border: 2px solid {p.accent}; }}
            """)
        if hasattr(self, '_scroll_area'):
            self._scroll_area.setStyleSheet(f"""
                QScrollArea {{ border: none; background: transparent; }}
                QScrollBar:vertical {{
                    background: {p.bg_secondary}; width: 6px; border-radius: 3px;
                }}
                QScrollBar::handle:vertical {{
                    background: {p.border}; border-radius: 3px; min-height: 20px;
                }}
                QScrollBar::handle:vertical:hover {{ background: {p.text_muted}; }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            """)
        if hasattr(self, '_hint_label'):
            self._hint_label.setStyleSheet(
                f"color: {p.text_muted}; font-size: 10px;"
                f" padding: 8px 12px; background: {p.bg_primary};"
                f" border-top: 1px solid {p.border};"
            )
    def _filter(self, text):
        q = text.lower()
        for btn, name in self._all_buttons:
            btn.setVisible(q in name.lower())

class EnhancedCanvasScene(QGraphicsScene):

    node_selection_changed = Signal(int)

    def __init__(self, parent_window=None):
        super().__init__()
        self.parent_window = parent_window
        self.dragging_connection = False
        self.drag_start_anchor = None
        self.temp_link_item = None

        self.workflow_nodes = []
        self.workflow_links = []
        self.node_items = {}
        self.link_items = {}

        self._undo_stack = deque(maxlen=50)
        self._undoing = False

        self.setSceneRect(-2000, -2000, 4000, 4000)
        self.selectionChanged.connect(self._on_selection)

    def _on_selection(self):
        n = sum(1 for i in self.selectedItems() if isinstance(i, NodeItem))
        self.node_selection_changed.emit(n)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Z and (event.modifiers() & Qt.ControlModifier):
            self.undo()
        elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected_items()
        elif event.key() == Qt.Key_D and event.modifiers() == Qt.ControlModifier:
            self.duplicate_selected_nodes()
        elif event.key() == Qt.Key_A and event.modifiers() == Qt.ControlModifier:
            self.select_all_items()
        elif event.key() == Qt.Key_Escape:
            self.clearSelection()
        else:
            super().keyPressEvent(event)

    def undo(self):
        """Reverse the last tracked action (add/delete node or link)."""
        if not self._undo_stack:
            return
        self._undoing = True
        _peek_type = self._undo_stack[-1][0]
        ual = _ual()
        if ual:
            ual.log_action('CLICK', f'Canvas undo: {_peek_type}',
                           {'action': _peek_type,
                            'remaining_undo': len(self._undo_stack) - 1})
        try:
            action_type, data = self._undo_stack.pop()
            if action_type == 'add_node':
                ni = self.node_items.get(data['wf_node'])
                if ni:
                    self.delete_node(ni)
            elif action_type == 'delete_node':
                self.add_node(data['wf_node'], data['pos'])
            elif action_type == 'add_link':
                li = data.get('li')
                if li and li.scene():
                    self.delete_link(li)
            elif action_type == 'delete_link':
                self.add_link(data['src_node'], data['src_ch'],
                              data['snk_node'], data['snk_ch'])
        finally:
            self._undoing = False

    def delete_selected_items(self):
        nodes = [i for i in self.selectedItems() if isinstance(i, NodeItem)]
        links = [i for i in self.selectedItems() if isinstance(i, LinkItem)]
        notes = [i for i in self.selectedItems() if isinstance(i, StickyNoteItem)]
        for l in links:
            self.delete_link(l)
        for n in nodes:
            self.delete_node(n)
        for note in notes:
            self.removeItem(note)

    def delete_node(self, ni):
        if not isinstance(ni, NodeItem):
            return
        wn = ni.workflow_node
        if not self._undoing:
            self._undo_stack.append(('delete_node', {'wf_node': wn, 'pos': ni.pos()}))
            ual = _ual()
            if ual:
                ual.log_action('DATA_OP', f'Deleted node: {wn.title}',
                               {'node_type': wn.node_type,
                                'remaining_nodes': len(self.workflow_nodes) - 1})
        for lk in list(self.workflow_links):
            if lk.source_node == wn or lk.sink_node == wn:
                li = self.link_items.get(lk)
                if li:
                    self.delete_link(li)
        self.workflow_nodes.remove(wn) if wn in self.workflow_nodes else None
        self.node_items.pop(wn, None)
        self.removeItem(ni)

    def delete_link(self, li):
        if not isinstance(li, LinkItem):
            return
        wl = li.workflow_link
        if not self._undoing and wl:
            self._undo_stack.append(('delete_link', {
                'src_node': wl.source_node, 'src_ch': wl.source_channel,
                'snk_node': wl.sink_node,  'snk_ch': wl.sink_channel,
            }))
            ual = _ual()
            if ual:
                ual.log_action('DATA_OP',
                               f'Removed connection: {wl.source_node.title} → {wl.sink_node.title}',
                               {'source': wl.source_node.title,
                                'sink': wl.sink_node.title})
        if wl in self.workflow_links:
            self.workflow_links.remove(wl)
        self.link_items.pop(wl, None)
        self.removeItem(li)

    def duplicate_selected_nodes(self):
        sel = [i for i in self.selectedItems() if isinstance(i, NodeItem)]
        self.clearSelection()
        for ni in sel:
            d = self.duplicate_node(ni)
            if d:
                d.setSelected(True)

    def duplicate_node(self, ni):
        import copy
        wf = ni.workflow_node
        factory = _NODE_FACTORIES.get(wf.node_type)
        if not factory:
            return None
        new_wf = factory(self.parent_window)
        for attr in ('config', 'selected_sample', 'selected_isotopes',
                     'sum_replicates', 'replicate_samples',
                     'selected_samples', 'sample_config',
                     'sample_filters', 'selected_sources', 'merged_name',
                     'saved_cluster_state',
                     # Particle Classifier (tools/particle_classifier_node.py)
                     # -- same full state list carried by save/load in
                     # save_export/project_manager.py's config_attributes.
                     'definitions', 'groups', 'overlap_mode',
                     'unmatched_mode', 'unclassified_color',
                     'group_pooling_policies', '_has_unresolved_issues',
                     'confound_dismissals'):
            if hasattr(wf, attr):
                try:
                    setattr(new_wf, attr, copy.deepcopy(getattr(wf, attr)))
                except Exception:
                    _itk_log.exception("Handled exception in duplicate_node")
        pos = ni.pos() + QPointF(DS.NODE_W + 30, 20)
        _, item = self.add_node(new_wf, pos)
        ual = _ual()
        if ual:
            ual.log_action('CLICK', f'Duplicated node: {wf.title}',
                           {'node_type': wf.node_type,
                            'total_nodes': len(self.workflow_nodes)})
        return item

    def select_all_items(self):
        for i in self.items():
            if isinstance(i, (NodeItem, LinkItem)):
                i.setSelected(True)

    def add_node(self, wf_node, pos):
        wf_node.set_position(pos)
        self.workflow_nodes.append(wf_node)
        item_cls = _NODE_ITEM_MAP.get(wf_node.node_type, NodeItem)
        if item_cls in (NodeItem,):
            ni = item_cls(wf_node)
        else:
            ni = item_cls(wf_node, self.parent_window)
        ni.setPos(pos)
        self.addItem(ni)
        self.node_items[wf_node] = ni
        if not self._undoing:
            self._undo_stack.append(('add_node', {'wf_node': wf_node}))
            ual = _ual()
            if ual:
                ual.log_action('DATA_OP', f'Added node: {wf_node.title}',
                               {'node_type': wf_node.node_type,
                                'total_nodes': len(self.workflow_nodes)})
        return wf_node, ni

    def add_link(self, src_node, src_ch, snk_node, snk_ch):
        for lk in self.workflow_links:
            if (lk.source_node == src_node and lk.sink_node == snk_node
                    and lk.source_channel == src_ch and lk.sink_channel == snk_ch):
                return None
        refusal = validate_classifier_link(src_node, snk_node)
        if refusal:
            _itk_log.warning(
                "Blocked link %s -> %s: %s",
                getattr(src_node, 'title', src_node),
                getattr(snk_node, 'title', snk_node), refusal)
            QMessageBox.warning(
                self.views()[0] if self.views() else None,
                "Connection Not Allowed", refusal)
            return None
        wl = WorkflowLink(src_node, src_ch, snk_node, snk_ch)
        self.workflow_links.append(wl)
        li = LinkItem()
        li.set_workflow_link(wl)
        si = self.node_items.get(src_node)
        di = self.node_items.get(snk_node)
        if not si or not di:
            return None
        sa = si.get_anchor(src_ch)
        da = di.get_anchor(snk_ch)
        if sa and da:
            li.set_source_anchor(sa)
            li.set_sink_anchor(da)
            self.addItem(li)
            self.link_items[wl] = li
            if not self._undoing:
                self._undo_stack.append(('add_link', {'li': li}))
                ual = _ual()
                if ual:
                    ual.log_action('DATA_OP',
                                   f'Connected: {src_node.title} → {snk_node.title}',
                                   {'source': src_node.title,
                                    'source_type': src_node.node_type,
                                    'sink': snk_node.title,
                                    'sink_type': snk_node.node_type,
                                    'total_links': len(self.workflow_links)})
            QApplication.processEvents()
            self._trigger_data_flow(wl)
            return wl
        return None

    def _trigger_data_flow(self, wl):
        try:
            data = wl.get_data()
            if hasattr(wl.sink_node, 'process_data'):
                wl.sink_node.process_data(data)
        except Exception as e:
            _itk_log.exception("Handled exception in _trigger_data_flow")
            _itk_log.error(f"Data flow error: {e}")

    def contextMenuEvent(self, event):
        """Right-click on empty canvas space → canvas context menu."""
        items = self.items(event.scenePos())
        if any(isinstance(i, (NodeItem, LinkItem, StickyNoteItem)) for i in items):
            super().contextMenuEvent(event)
            return
        menu = QMenu()
        menu.setStyleSheet(NodeItem._ctx_menu_style())
        note_act = menu.addAction(
            qta.icon('fa6s.note-sticky', color=DS.WARNING), "  Add Note")
        menu.addSeparator()
        undo_act = menu.addAction(
            qta.icon('fa6s.rotate-left', color=DS.ACCENT), "  Undo  (Ctrl+Z)")
        undo_act.setEnabled(bool(self._undo_stack))
        result = menu.exec(event.screenPos())
        if result == note_act:
            note = StickyNoteItem()
            note.setPos(event.scenePos())
            self.addItem(note)
        elif result == undo_act:
            self.undo()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.scenePos(), self.views()[0].transform() if self.views() else QTransform())
            cur = item
            while cur and not isinstance(cur, AnchorPoint):
                cur = cur.parentItem()
            if isinstance(cur, AnchorPoint) and not cur.is_input:
                self._start_drag(cur, event.scenePos())
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging_connection and self.temp_link_item:
            pos = event.scenePos()
            near = self._nearest_candidate(pos, 70)
            if near is not None:
                if getattr(self, '_snap_anchor', None) is not near:
                    if getattr(self, '_snap_anchor', None) is not None:
                        self._snap_anchor.set_drag_target('candidate')
                    near.set_drag_target('snap')
                    self._snap_anchor = near
                if self.temp_link_item.sink_anchor:
                    self.temp_link_item.sink_anchor.setPos(near.scenePos())
            else:
                if getattr(self, '_snap_anchor', None) is not None:
                    self._snap_anchor.set_drag_target('candidate')
                    self._snap_anchor = None
                if self.temp_link_item.sink_anchor:
                    self.temp_link_item.sink_anchor.setPos(pos)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.dragging_connection:
            self._end_drag(event.scenePos())
        else:
            super().mouseReleaseEvent(event)

    def _nearest_candidate(self, pos, radius):
        """Closest highlighted input anchor to ``pos`` within ``radius``, or None."""
        best, bestd = None, float(radius) * float(radius)
        for a in getattr(self, '_candidate_anchors', []):
            try:
                ap = a.scenePos()
                dx, dy = ap.x() - pos.x(), ap.y() - pos.y()
                d = dx * dx + dy * dy
                if d < bestd:
                    bestd, best = d, a
            except Exception:
                pass
        return best

    def _start_drag(self, anchor, pos):
        """Begin a connection drag from ``anchor``.

        Every valid input anchor on other nodes is highlighted as a candidate
        drop target so the connection is easy to land.
        """
        self.dragging_connection = True
        self.drag_start_anchor = anchor
        self.temp_link_item = LinkItem()
        self.temp_link_item.set_source_anchor(anchor)
        self.temp_link_item.setZValue(100)
        ta = AnchorPoint(None, "temp", is_input=True)
        ta.setPos(pos)
        self.addItem(ta)
        self.temp_link_item.set_sink_anchor(ta)
        self.addItem(self.temp_link_item)
        src_node = anchor.parentItem()
        self._candidate_anchors = [
            it for it in self.items()
            if isinstance(it, AnchorPoint) and it.is_input
            and it.parentItem() is not None and it.parentItem() is not src_node]
        for a in self._candidate_anchors:
            a.set_drag_target('candidate')
        self._snap_anchor = None

    def _end_drag(self, pos):
        """Finish a connection drag.

        Connects to whatever the wire snapped to, or the nearest candidate port,
        so the user need not release exactly on the small anchor dot.
        """
        target = getattr(self, '_snap_anchor', None) or self._nearest_candidate(pos, 70)
        for a in getattr(self, '_candidate_anchors', []):
            try:
                a.set_drag_target('none')
            except Exception:
                pass
        self._candidate_anchors = []
        self._snap_anchor = None

        if self.temp_link_item:
            if self.temp_link_item.sink_anchor:
                self.removeItem(self.temp_link_item.sink_anchor)
            self.removeItem(self.temp_link_item)
            self.temp_link_item = None

        if target is None:
            for item in self.items(pos, Qt.IntersectsItemShape, Qt.DescendingOrder):
                if isinstance(item, AnchorPoint) and item.is_input and item != self.drag_start_anchor:
                    target = item
                    break

        if target and self.drag_start_anchor:
            sni = self.drag_start_anchor.parentItem()
            dni = target.parentItem()
            if sni and dni and sni != dni:
                swf = next((w for w, i in self.node_items.items() if i == sni), None)
                dwf = next((w for w, i in self.node_items.items() if i == dni), None)
                if swf and dwf:
                    self.add_link(swf, self.drag_start_anchor.channel_name,
                                  dwf, target.channel_name)

        self.dragging_connection = False
        self.drag_start_anchor = None

class EnhancedCanvasView(QGraphicsView):

    zoom_changed = Signal(float)

    def __init__(self, parent_window=None):
        super().__init__()
        self.parent_window = parent_window
        self.scene = EnhancedCanvasScene(parent_window)
        self.setScene(self.scene)

        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setAcceptDrops(True)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setFocusPolicy(Qt.StrongFocus)

        self._apply_view_theme()
        self._view_theme_handler = lambda _: self._safe_apply_view_theme()
        _app_theme.themeChanged.connect(self._view_theme_handler)
        self.destroyed.connect(self._view_disconnect_theme)

        self._zoom = 1.0
        self._panning = False
        self._pan_start = QPoint()
        self._setup_shortcuts()

    def _apply_view_theme(self):
        p = _app_theme.palette
        self.setStyleSheet(
            f"QGraphicsView {{ background: {p.bg_primary}; border: none; }}")
        self.viewport().update()

    def _safe_apply_view_theme(self):
        try:
            self._apply_view_theme()
        except RuntimeError:
            _itk_log.exception("Handled exception in _safe_apply_view_theme")

    def _view_disconnect_theme(self):
        try:
            _app_theme.themeChanged.disconnect(self._view_theme_handler)
        except Exception:
            _itk_log.exception("Handled exception in _view_disconnect_theme")

    def _setup_shortcuts(self):
        QShortcut(QKeySequence.Delete, self).activated.connect(
            self.scene.delete_selected_items)
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(
            self.scene.duplicate_selected_nodes)
        QShortcut(QKeySequence.SelectAll, self).activated.connect(
            self.scene.select_all_items)
        QShortcut(QKeySequence("Escape"), self).activated.connect(
            self.scene.clearSelection)
        QShortcut(QKeySequence.Undo, self).activated.connect(
            self.scene.undo)

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        new_zoom = self._zoom * factor
        if 0.15 < new_zoom < 5.0:
            self._zoom = new_zoom
            self.scale(factor, factor)
            self.zoom_changed.emit(self._zoom)

    def set_zoom(self, value):
        factor = value / self._zoom
        self._zoom = value
        self.scale(factor, factor)
        self.zoom_changed.emit(self._zoom)

    def fit_content(self):
        items_rect = self.scene.itemsBoundingRect().adjusted(-60, -60, 60, 60)
        if items_rect.isNull():
            return
        self.fitInView(items_rect, Qt.KeepAspectRatio)
        self._zoom = self.transform().m11()
        self.zoom_changed.emit(self._zoom)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            return
        super().mouseReleaseEvent(event)

    def drawBackground(self, painter, rect):
        p = _app_theme.palette
        painter.fillRect(rect, QColor(p.bg_primary))

        gs = DS.GRID_SIZE
        if _app_theme.is_dark:
            dot = QColor(255, 255, 255, DS.GRID_DOT_ALPHA)
        else:
            dot = QColor(0, 0, 0, 40)

        painter.setPen(QPen(dot, 1.5))
        left = int(rect.left()) - (int(rect.left()) % gs)
        top  = int(rect.top())  - (int(rect.top())  % gs)
        y = top
        while y < rect.bottom():
            x = left
            while x < rect.right():
                painter.drawPoint(x, y)
                x += gs
            y += gs

    def drawForeground(self, painter, rect):
        """Draw a centered hint while the canvas has no result blocks yet."""
        super().drawForeground(painter, rect)
        try:
            scene = self.scene
            if getattr(scene, 'workflow_nodes', None):
                return
            if any(isinstance(i, (NodeItem, StickyNoteItem)) for i in scene.items()):
                return
            p = _app_theme.palette
            center = self.mapToScene(self.viewport().rect().center())
            cx, cy = center.x(), center.y()
            painter.save()
            painter.setPen(QPen(QColor(p.text_secondary)))
            f = painter.font()
            f.setPointSize(15)
            f.setBold(True)
            painter.setFont(f)
            painter.drawText(
                QRectF(cx - 240, cy - 30, 480, 30),
                Qt.AlignCenter, "Drag a result block onto the canvas to begin")
            f.setPointSize(11)
            f.setBold(False)
            painter.setFont(f)
            painter.setPen(QPen(QColor(p.text_muted)))
            painter.drawText(
                QRectF(cx - 240, cy + 4, 480, 24),
                Qt.AlignCenter,
                "Choose a visualization from the panel on the left, then connect a sample")
            painter.restore()
        except Exception:
            _itk_log.debug("canvas empty hint skipped")

    def _drag_node_type(self, event):
        """Return the node type carried by a drag/drop event, or None.

        Reads it from the mime data when possible, and falls back to the
        module-level holder set by the palette. The mime-data access is
        guarded because PySide6 can hand back a wrapper of the wrong type
        here; letting that raise inside the event handler leaves Qt's drag
        state half-initialised ("drag leave received before drag enter").

        Returns:
            str | None: The dragged node type, or None if not a node drag.
        """
        md = event.mimeData()
        has_text = getattr(md, "hasText", None)
        if callable(has_text):
            try:
                if has_text():
                    text = md.text()
                    if text:
                        return text
            except (AttributeError, RuntimeError):
                _itk_log.exception("Handled exception in _drag_node_type")
        return _PENDING_DRAG_NODE_TYPE

    def dragEnterEvent(self, event):
        if self._drag_node_type(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._drag_node_type(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        ntype = self._drag_node_type(event)
        if not ntype:
            event.ignore()
            return
        sp = self.mapToScene(event.pos())
        gs = DS.GRID_SIZE
        snapped = QPointF(round(sp.x() / gs) * gs, round(sp.y() / gs) * gs)

        factory = _NODE_FACTORIES.get(ntype)
        if factory:
            wf = factory(self.parent_window)
            self.scene.add_node(wf, snapped)
            if ntype == "particle_classifier":
                # Fresh node just dragged in by the user (never fires for
                # project-load deserialization or node duplication, which
                # don't go through this drop handler) -- design §10.
                # Deferred to the next event-loop turn: this dropEvent runs
                # INSIDE the palette drag source's QDrag.exec_() nested loop
                # (mouse still grabbed by the drag), and opening a modal
                # there is the same "modal launched while another loop owns
                # the input grab" hazard that broke the color picker's
                # click handling earlier. Firing after the drop unwinds and
                # releases the grab avoids it.
                QTimer.singleShot(
                    0, lambda: maybe_show_classifier_onboarding(
                        self.parent_window))
            event.acceptProposedAction()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        self.scene.keyPressEvent(event)
        super().keyPressEvent(event)


ParticleFilterNodeItem = build_particle_filter_node_item()
ParticleClassifierNodeItem = build_particle_classifier_node_item()


_NODE_FACTORIES = {
    "sample_selector":              SampleSelectorNode,
    "multiple_sample_selector":     MultipleSampleSelectorNode,
    "batch_sample_selector":        BatchSampleSelectorNode,
    "particle_filter":              ParticleFilterNode,
    "particle_classifier":          ParticleClassifierNode,
    "histogram_plot":               HistogramPlotNode,
    "element_bar_chart_plot":       ElementBarChartPlotNode,
    "correlation_plot":             CorrelationPlotNode,
    "box_plot":                     BoxPlotNode,
    "molar_ratio_plot":             MolarRatioPlotNode,
    "pie_chart_plot":               PieChartPlotNode,
    "element_composition_plot":     ElementCompositionPlotNode,
    "heatmap_plot":                 HeatmapPlotNode,
    "isotopic_ratio_plot":          IsotopicRatioPlotNode,
    "triangle_plot":                TrianglePlotNode,
    "single_multiple_element_plot": SingleMultipleElementPlotNode,
    "clustering_plot":              ClusteringPlotNode,
    "ai_assistant":                 AIAssistantNode,
    "correlation_matrix":           CorrelationMatrixNode,
    "concentration_comparison":     ConcentrationComparisonNode,
    "network_diagram":              NetworkDiagramNode,
    "dashboard":                    DashboardNode,
}

_NODE_ITEM_MAP = {
    "sample_selector":              SampleSelectorNodeItem,
    "multiple_sample_selector":     MultipleSampleSelectorNodeItem,
    "batch_sample_selector":        BatchSampleSelectorNodeItem,
    "particle_filter":              ParticleFilterNodeItem,
    "particle_classifier":          ParticleClassifierNodeItem,
    "histogram_plot":               HistogramPlotNodeItem,
    "element_bar_chart_plot":       ElementBarChartPlotNodeItem,
    "correlation_plot":             CorrelationPlotNodeItem,
    "box_plot":                     BoxPlotNodeItem,
    "molar_ratio_plot":             MolarRatioPlotNodeItem,
    "pie_chart_plot":               PieChartPlotNodeItem,
    "element_composition_plot":     ElementCompositionPlotNodeItem,
    "heatmap_plot":                 HeatmapPlotNodeItem,
    "isotopic_ratio_plot":          IsotopicRatioPlotNodeItem,
    "triangle_plot":                TrianglePlotNodeItem,
    "single_multiple_element_plot": SingleMultipleElementPlotNodeItem,
    "clustering_plot":              ClusteringPlotNodeItem,
    "ai_assistant":                 AIAssistantNodeItem,
    "correlation_matrix":           CorrelationMatrixNodeItem,
    "concentration_comparison":     ConcentrationComparisonNodeItem,
    "network_diagram":              NetworkDiagramNodeItem,
    "dashboard":                    DashboardNodeItem,
}

#: Every Visualization-category node type (mirrors the palette's
#: "VISUALIZATION" group in NodePalette._setup — category membership has
#: no runtime field on the node classes themselves, so this list is the
#: source of truth for "is this a viz node" checks, e.g. classifier
#: downstream-connectivity validation).
_VIZ_NODE_TYPES = frozenset({
    "histogram_plot", "element_bar_chart_plot", "box_plot",
    "correlation_plot", "pie_chart_plot", "element_composition_plot",
    "heatmap_plot", "molar_ratio_plot", "isotopic_ratio_plot",
    "triangle_plot", "single_multiple_element_plot", "clustering_plot",
    "correlation_matrix", "concentration_comparison", "network_diagram",
    "dashboard",
})


def validate_classifier_link(src_node, snk_node):
    """Check a proposed link against Particle Classifier connectivity rules.

    Design §2: upstream limited to Particle Filter / Single Sample /
    Multiple Sample; downstream limited to Visualization-category nodes
    excluding Clustering, AI Data Assistant, and Dashboard. Only fires when
    one endpoint of the link actually is a Particle Classifier node — every
    other link pair in the app is unaffected.

    Args:
        src_node: The link's source ``WorkflowNode``.
        snk_node: The link's sink ``WorkflowNode``.

    Returns:
        str | None: A human-readable refusal reason, or None if the link
            is permitted (including when neither endpoint is a classifier).
    """
    if getattr(snk_node, 'node_type', None) == "particle_classifier":
        if not is_allowed_upstream(getattr(src_node, 'node_type', None)):
            return (
                "Particle Classifier can only accept input from a "
                "Particle Filter, Single Sample, or Multiple Sample node.")
    if getattr(src_node, 'node_type', None) == "particle_classifier":
        snk_type = getattr(snk_node, 'node_type', None)
        if not is_allowed_downstream(snk_type, _VIZ_NODE_TYPES):
            if snk_type in EXCLUDED_DOWNSTREAM_TYPES:
                return (
                    "Particle Classifier cannot connect to Clustering, "
                    "AI Data Assistant, or Dashboard nodes.")
            return (
                "Particle Classifier can only connect to Visualization "
                "nodes.")
    return None


class CanvasResultsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("IsotopeTrack — Workflow Builder")
        self.setMinimumSize(1300, 780)
        self._apply_chrome_theme()
        _app_theme.themeChanged.connect(lambda _: self._apply_chrome_theme())
        self._build()
        ual = _ual()
        if ual:
            ual.log_action('NEW_WINDOW', 'Opened Workflow Builder canvas',
                           {'dialog': 'CanvasResultsDialog'})

    def _apply_chrome_theme(self):
        self.setStyleSheet(_canvas_chrome_style())

    def _build(self):                          
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
    
        # ── header bar ─────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setObjectName("chromeHeader")
        hdr.setFixedHeight(52)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
    
        logo = QLabel("◆  Workflow Builder")
        logo.setStyleSheet(
            f"color: {_app_theme.palette.text_primary};"
            f" font-size: 16px; font-weight: 700;"
            f" font-family: '{DS.FONT_FAMILY}';"
        )
        hl.addWidget(logo)
        hl.addStretch()
    
        def _zoom_out():
            self.canvas.set_zoom(self.canvas._zoom / 1.2)
        def _zoom_in():
            self.canvas.set_zoom(self.canvas._zoom * 1.2)
        def _fit():
            self.canvas.fit_content()
    
        zm = QPushButton("−")
        zm.setFixedSize(30, 30)
        zm.setStyleSheet(self._tool_btn_style())
        zm.clicked.connect(_zoom_out)
        hl.addWidget(zm)
    
        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(50)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        hl.addWidget(self.zoom_label)
    
        zp = QPushButton("+")
        zp.setFixedSize(30, 30)
        zp.setStyleSheet(self._tool_btn_style())
        zp.clicked.connect(_zoom_in)
        hl.addWidget(zp)
    
        fit = QPushButton("Fit")
        fit.setFixedSize(40, 30)
        fit.setStyleSheet(self._tool_btn_style())
        fit.clicked.connect(_fit)
        hl.addWidget(fit)
    
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {DS.BORDER}; margin: 8px 12px;")
        hl.addWidget(sep)
    
  
        self._insights_btn = None  
    
        def _clear_and_log():
            self.clear_canvas()
    
        def _close_and_log():
            self.close()
    
        clr = QPushButton("Clear All")
        clr.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {DS.ERROR};
                border: 1px solid {DS.ERROR}; border-radius: 6px;
                padding: 5px 14px; font-weight: 600; font-size: 11px;
            }}
            QPushButton:hover {{ background: {DS.ERROR_BG}; }}
        """)
        clr.clicked.connect(_clear_and_log)
    
        back = QPushButton("✕  Close")
        back.setStyleSheet(f"""
            QPushButton {{
                background: {DS.ACCENT}; color: white;
                border: none; border-radius: 6px;
                padding: 6px 16px; font-weight: 600; font-size: 11px;
            }}
            QPushButton:hover {{ background: {DS.ACCENT_HOVER}; }}
        """)
        back.clicked.connect(_close_and_log)

        self._insights_placeholder = QPushButton("✦  Insights")
        self._insights_placeholder.setFixedHeight(30)
        self._insights_placeholder.setStyleSheet(self._tool_btn_style())
        hl.addWidget(self._insights_placeholder)  
    
        hl.addWidget(clr)
        hl.addWidget(back)
    
        root.addWidget(hdr)
    
        # ── body splitter ──────────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
    
        pf = QFrame()
        pf.setObjectName("chromePalette")
        pf.setFixedWidth(240)
        pl = QVBoxLayout(pf)
        pl.setContentsMargins(0, 0, 0, 0)
        self.palette = NodePalette(self.parent)
        pl.addWidget(self.palette)
    
        self.canvas = EnhancedCanvasView(self.parent)
        self.canvas.zoom_changed.connect(
            lambda z: self.zoom_label.setText(f"{int(z * 100)}%"))
    
        splitter.addWidget(pf)
        splitter.addWidget(self.canvas)
    
        self.insights_panel = integrate_insights_panel(self, splitter)
        splitter.setSizes([240, 860, 0])  
    
        real_btn = make_insights_toggle_button(self, splitter)
        hl.replaceWidget(self._insights_placeholder, real_btn)
        self._insights_placeholder.deleteLater()
        self._insights_btn = real_btn
        # ──────────────────────────────────────────────────────────────────
    
        root.addWidget(splitter)
    
        sb = QFrame()
        sb.setObjectName("chromeStatus")
        sb.setFixedHeight(28)
        sbl = QHBoxLayout(sb)
        sbl.setContentsMargins(12, 0, 12, 0)
    
        self.status_label = QLabel("Ready")
        sbl.addWidget(self.status_label)
        sbl.addStretch()
    
        self.sel_label = QLabel("")
        sbl.addWidget(self.sel_label)
    
        self.canvas.scene.node_selection_changed.connect(self._update_sel)
        root.addWidget(sb)
        

    def _update_sel(self, count):
        if count:
            self.sel_label.setText(f"{count} node{'s' if count > 1 else ''} selected")
        else:
            self.sel_label.setText("")

    @staticmethod
    def _tool_btn_style():
        p = _app_theme.palette
        return f"""
            QPushButton {{
                background: {p.bg_tertiary};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 6px;
                font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover {{
                background: {p.accent_soft};
                border-color: {p.accent};
            }}
        """

    def clear_canvas(self):
        self.canvas.scene.workflow_nodes.clear()
        self.canvas.scene.workflow_links.clear()
        self.canvas.scene.node_items.clear()
        self.canvas.scene.link_items.clear()
        self.canvas.scene.clear()
        self.status_label.setText("Canvas cleared")


def show_canvas_results(parent_window):
    dialog = CanvasResultsDialog(parent_window)
    dialog.exec_()