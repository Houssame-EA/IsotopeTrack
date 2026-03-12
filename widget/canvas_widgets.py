from PySide6.QtWidgets import (
    QDialog, QMenu, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QGraphicsProxyWidget, QLabel, QTableWidget,
    QComboBox, QListWidget, QListWidgetItem, QCheckBox,
    QFrame, QScrollArea, QSplitter, QGroupBox, QTableWidgetItem,
    QGraphicsWidget, QGraphicsEllipseItem, QApplication, QMainWindow,
    QDialogButtonBox, QFormLayout, QSpinBox, QDoubleSpinBox, QTabWidget,
    QLineEdit, QAbstractItemView, QTextEdit, QToolTip, QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect, QSlider, QToolButton, QSizePolicy, QHeaderView,
    QMessageBox, QInputDialog, QGraphicsRectItem
)
from PySide6.QtCore import (
    Qt, Signal, QPointF, QRectF, QMimeData, QPoint, QObject,
    QPropertyAnimation, QEasingCurve, QTimer, QSize, QTimeLine
)
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QDrag, QPixmap, QPainterPath,
    QLinearGradient, QFont, QPainterPathStroker, QRadialGradient,QFontMetrics,
    QShortcut, QKeySequence, QIcon, QTransform, QCursor, QFontDatabase,
    QWheelEvent, QConicalGradient
)
import math
import numpy as np

from results.results_pie_charts import (
    PieChartDisplayDialog, PieChartPlotNode,
    ElementCompositionDisplayDialog, ElementCompositionPlotNode,
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
from results.results_AI import AIAssistantNode, AIChatDialog
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

import qtawesome as qta

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
    NODE_W          = 130         # total bounding width (for label)
    NODE_H          = 105         # total bounding height (circle + label)
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
        pass

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
        hitbox_radius = self.radius + 7
        path.addEllipse(QRectF(-hitbox_radius, -hitbox_radius, hitbox_radius * 2, hitbox_radius * 2))
        return path

    def hoverEnterEvent(self, event):
        self._apply_style(hover=True)
        self.setScale(1.3)
        # FIX: Tooltip clarify multi-connection support
        label = "Input (Connect here)" if self.is_input else "Output (Drag to connect to multiple nodes)"
        QToolTip.showText(event.screenPos(), label)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._apply_style(hover=False)
        self.setScale(1.0)
        super().hoverLeaveEvent(event)

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
        painter.setRenderHint(QPainter.Antialiasing)

        d = self.icon_d
        cx = self.width / 2          # center x
        cy = d / 2 + 4               # center y (a bit of top padding)
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
                self._icon_cache[cache_key] = None

        px = self._icon_cache.get(cache_key)
        if px and not px.isNull():
            ix = cx - icon_size / 2
            iy = cy - icon_size / 2
            painter.setOpacity(0.95)
            painter.drawPixmap(int(ix), int(iy), px)
            painter.setOpacity(1.0)

        label_y = cy + r + 8
        painter.setPen(QPen(QColor(DS.TEXT_PRIMARY)))
        painter.setFont(DS.font(DS.FONT_SMALL, bold=True))
        label_rect = QRectF(0, label_y, self.width, 20)
        painter.drawText(label_rect, Qt.AlignHCenter | Qt.AlignTop, label_text)

        if badge_text:
            bc = QColor(badge_color) if badge_color else QColor(DS.TEXT_MUTED)
            dot_x = cx + r * 0.6
            dot_y = cy + r * 0.6
            painter.setPen(QPen(QColor(DS.BG_PRIMARY), 2))
            painter.setBrush(bc)
            painter.drawEllipse(QPointF(dot_x, dot_y), 6, 6)

    def paint(self, painter, option, widget=None):
        self.paint_icon_node(
            painter, DS.HDR_DATA, "fa6s.cube",
            self.workflow_node.title,
        )

    # ── anchors ─────────────────────────────────────────────────────────────
    def _create_anchors(self):
        cy = self.icon_d / 2 + 4   # same vertical center as circle
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
                if self.scene():
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
        return f"""
        QMenu {{
            background: {DS.BG_SECONDARY};
            border: 1px solid {DS.BORDER};
            border-radius: 8px;
            padding: 4px;
            color: {DS.TEXT_PRIMARY};
            font-family: '{DS.FONT_FAMILY}';
            font-size: 12px;
        }}
        QMenu::item {{
            padding: 8px 24px 8px 12px;
            border-radius: 6px;
        }}
        QMenu::item:selected {{
            background: {DS.ACCENT_LIGHT};
        }}
        QMenu::separator {{
            height: 1px;
            background: {DS.BORDER};
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
            except: pass
        self.source_anchor = anchor
        if anchor:
            anchor.position_changed.connect(self.__update_curve)
        self.__update_curve()

    def set_sink_anchor(self, anchor):
        if self.sink_anchor:
            try: self.sink_anchor.position_changed.disconnect(self.__update_curve)
            except: pass
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
            print(f"Link update error: {e}")

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
    return f"""
    QDialog {{
        background: {DS.BG_PRIMARY};
        color: {DS.TEXT_PRIMARY};
        font-family: '{DS.FONT_FAMILY}';
    }}
    QTabWidget::pane {{
        border: 1px solid {DS.BORDER};
        border-radius: 6px;
        background: {DS.BG_SECONDARY};
    }}
    QTabBar::tab {{
        background: {DS.BG_SURFACE};
        color: {DS.TEXT_SECONDARY};
        padding: 8px 20px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 2px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {DS.BG_SECONDARY};
        color: {DS.ACCENT};
        border-bottom: 2px solid {DS.ACCENT};
    }}
    QLabel {{ color: {DS.TEXT_PRIMARY}; }}
    QPushButton {{
        background: {DS.BG_ELEVATED};
        color: {DS.TEXT_PRIMARY};
        border: 1px solid {DS.BORDER};
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 600;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background: {DS.ACCENT_LIGHT};
        border-color: {DS.ACCENT};
    }}
    QTableWidget {{
        background: {DS.BG_PRIMARY};
        color: {DS.TEXT_PRIMARY};
        border: 1px solid {DS.BORDER};
        border-radius: 6px;
        gridline-color: {DS.BORDER_SUBTLE};
        selection-background-color: {DS.ACCENT_LIGHT};
    }}
    QHeaderView::section {{
        background: {DS.BG_SURFACE};
        color: {DS.TEXT_SECONDARY};
        padding: 10px;
        border: 1px solid {DS.BORDER_SUBTLE};
        font-weight: 600;
    }}
    QCheckBox {{ color: {DS.TEXT_PRIMARY}; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px;
        border-radius: 4px;
        border: 2px solid {DS.BORDER};
        background: {DS.BG_PRIMARY};
    }}
    QCheckBox::indicator:checked {{
        background: {DS.ACCENT};
        border-color: {DS.ACCENT};
    }}
    QLineEdit {{
        background: {DS.BG_INPUT};
        color: {DS.TEXT_PRIMARY};
        border: 1px solid {DS.BORDER};
        border-radius: 6px;
        padding: 8px 12px;
    }}
    QLineEdit:focus {{ border: 2px solid {DS.ACCENT}; }}
    QDialogButtonBox QPushButton {{ min-width: 90px; }}
    """

# ═══════════════════════════════════════════════════════════════════════════════
#  SAMPLE SELECTOR DIALOGS
# ═══════════════════════════════════════════════════════════════════════════════

class SampleSelectorDialog(QDialog):
    def __init__(self, parent, samples, current_selection=None,
                 current_isotopes=None, current_sum_replicates=False,
                 current_replicate_samples=None):
        super().__init__(parent)
        self.setWindowTitle("Single Sample Configuration")
        self.setModal(True)
        self.resize(1000, 700)
        self.setMinimumSize(800, 600)
        self.setStyleSheet(_dialog_base_style())

        self.parent_window = parent
        self.samples = samples
        self.current_isotopes = current_isotopes or []
        self.current_replicate_samples = current_replicate_samples or []

        self.sample_config = {}
        for sample in samples:
            included = False
            if current_sum_replicates and sample in self.current_replicate_samples:
                included = True
            elif not current_sum_replicates and sample == current_selection:
                included = True
            self.sample_config[sample] = {'included': included}

        layout = QVBoxLayout(self)
        tab_widget = QTabWidget()
        tab_widget.addTab(self.create_sample_config_tab(), "Sample Selection")
        tab_widget.addTab(self.create_isotope_tab(), "Isotope Selection")
        layout.addWidget(tab_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.update_preview()

    def create_sample_config_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        hdr = QLabel("Configure Sample Selection")
        hdr.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {DS.TEXT_PRIMARY};")
        layout.addWidget(hdr)

        info = QLabel(
            "Check samples to include  •  Select one for individual analysis "
            "or multiple to sum them together."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"""
            padding: 10px; background: {DS.ACCENT_LIGHT};
            border: 1px solid {DS.ACCENT}; border-radius: 6px;
            color: {DS.ACCENT_HOVER}; font-size: 11px;
        """)
        layout.addWidget(info)

        self.sample_table = QTableWidget()
        self.sample_table.setColumnCount(2)
        self.sample_table.setHorizontalHeaderLabels(["Include", "Sample Name"])
        self.sample_table.setRowCount(len(self.samples))
        self.sample_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sample_table.setSelectionMode(QTableWidget.MultiSelection)

        for row, sample in enumerate(self.samples):
            cb = QCheckBox()
            cb.setChecked(self.sample_config.get(sample, {}).get('included', False))
            cb.stateChanged.connect(self.on_table_changed)
            self.sample_table.setCellWidget(row, 0, cb)
            item = QTableWidgetItem(sample)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.sample_table.setItem(row, 1, item)

        h = self.sample_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Fixed)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        self.sample_table.setColumnWidth(0, 70)
        layout.addWidget(self.sample_table)

        btns = QHBoxLayout()
        for txt, slot, color in [
            ("Select All", self.select_all_samples, DS.ACCENT),
            ("Clear All", self.clear_all_samples, DS.ERROR),
            ("Check Selected Rows", self.check_selected_rows, DS.SUCCESS),
        ]:
            b = QPushButton(txt)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {color}; color: white;
                    border: none; border-radius: 6px;
                    padding: 8px 14px; font-weight: 600;
                }}
                QPushButton:hover {{ background: {QColor(color).lighter(120).name()}; }}
            """)
            b.clicked.connect(slot)
            btns.addWidget(b)
        btns.addStretch()
        layout.addLayout(btns)

        self.preview_label = QLabel()
        self.preview_label.setStyleSheet(f"""
            background: {DS.ACCENT_LIGHT}; border: 1px solid {DS.ACCENT};
            border-radius: 6px; padding: 12px; color: {DS.ACCENT_HOVER};
            font-weight: 500; font-size: 12px;
        """)
        layout.addWidget(self.preview_label)
        return widget

    def create_isotope_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.addWidget(QLabel("Select Isotopes to Include"))

        from results.results_periodic import CompactPeriodicTableWidget
        self.periodic_table = CompactPeriodicTableWidget(self)
        self.periodic_table.setMaximumSize(850, 350)
        if self.parent_window and hasattr(self.parent_window, 'selected_isotopes'):
            pairs = []
            for el, isos in self.parent_window.selected_isotopes.items():
                for iso in isos:
                    pairs.append((el, iso))
            if pairs:
                self.periodic_table.update_available_masses(pairs)
        self.set_periodic_table_selections()
        layout.addWidget(self.periodic_table)

        ctrls = QHBoxLayout()
        sa = QPushButton("Select All Available")
        sa.clicked.connect(self.select_all_isotopes)
        ctrls.addWidget(sa)
        cl = QPushButton("Clear Selection")
        cl.clicked.connect(self.clear_isotope_selection)
        ctrls.addWidget(cl)
        ctrls.addStretch()
        layout.addLayout(ctrls)
        return widget

    def on_table_changed(self):
        self.update_sample_config_from_table()
        self.update_preview()

    def update_sample_config_from_table(self):
        for row in range(self.sample_table.rowCount()):
            sample = self.samples[row]
            cb = self.sample_table.cellWidget(row, 0)
            self.sample_config[sample] = {'included': cb.isChecked()}

    def update_preview(self):
        self.update_sample_config_from_table()
        inc = [s for s, c in self.sample_config.items() if c['included']]
        if not inc:
            self.preview_label.setText("No samples selected")
        elif len(inc) == 1:
            self.preview_label.setText(f"Individual analysis of '{inc[0]}'")
        else:
            self.preview_label.setText(
                f"Combined analysis of {len(inc)} samples: {', '.join(inc)}")

    def select_all_samples(self):
        for r in range(self.sample_table.rowCount()):
            self.sample_table.cellWidget(r, 0).setChecked(True)

    def clear_all_samples(self):
        for r in range(self.sample_table.rowCount()):
            self.sample_table.cellWidget(r, 0).setChecked(False)

    def check_selected_rows(self):
        rows = {it.row() for it in self.sample_table.selectedItems()}
        if not rows:
            QMessageBox.information(self, "Info", "Select rows first.")
            return
        for r in rows:
            self.sample_table.cellWidget(r, 0).setChecked(True)

    def set_periodic_table_selections(self):
        if not self.current_isotopes:
            return
        by_sym = {}
        for it in self.current_isotopes:
            by_sym.setdefault(it['symbol'], []).append(it['mass'])
        for sym, masses in by_sym.items():
            if sym in self.periodic_table.buttons:
                btn = self.periodic_table.buttons[sym]
                if btn.isotope_display:
                    if not isinstance(btn.isotope_display.selected_isotopes, set):
                        btn.isotope_display.selected_isotopes = set(btn.isotope_display.selected_isotopes or [])
                    for m in masses:
                        btn.isotope_display.selected_isotopes.add((sym, m))
                    if hasattr(btn.isotope_display, 'update'):
                        btn.isotope_display.update()

    def select_all_isotopes(self):
        if self.parent_window and hasattr(self.parent_window, 'selected_isotopes'):
            for el, isos in self.parent_window.selected_isotopes.items():
                if el in self.periodic_table.buttons:
                    btn = self.periodic_table.buttons[el]
                    if btn.isotope_display:
                        for iso in isos:
                            btn.isotope_display.select_preferred_isotope(iso)

    def clear_isotope_selection(self):
        self.periodic_table.clear_all_selections()

    def get_selection(self):
        self.update_sample_config_from_table()
        selected = [s for s, c in self.sample_config.items() if c['included']]
        isotopes = []
        if hasattr(self, 'periodic_table'):
            for sym, btn in self.periodic_table.buttons.items():
                if btn.isotope_display and btn.isotope_display.selected_isotopes:
                    for s, m in btn.isotope_display.selected_isotopes:
                        key = f"{s}-{m:.4f}"
                        lbl = self.parent_window.get_formatted_label(key)
                        isotopes.append({'symbol': s, 'mass': m, 'key': key, 'label': lbl})
        if len(selected) == 0:
            return None, isotopes, False
        elif len(selected) == 1:
            return selected[0], isotopes, False
        else:
            return selected, isotopes, True
        
    


class MultipleSampleSelectorDialog(QDialog):
    def __init__(self, parent, samples, current_selection=None,
                 current_isotopes=None, current_sample_config=None):
        super().__init__(parent)
        self.setWindowTitle("Multi-Sample Configuration")
        self.setModal(True)
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(_dialog_base_style())

        self.parent_window = parent
        self.samples = samples
        self.current_isotopes = current_isotopes or []
        self.clipboard_group_name = ""

        if current_sample_config:
            self.current_sample_config = current_sample_config.copy()
        else:
            self.current_sample_config = {}
            cs = current_selection or []
            for s in samples:
                self.current_sample_config[s] = {
                    'included': s in cs, 'sum_group': '', 'custom_name': s}

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self.create_sample_config_tab(), "Sample Configuration")
        tabs.addTab(self.create_isotope_tab(), "Isotope Selection")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.update_preview()

    def create_sample_config_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        hdr = QLabel("Configure Sample Processing")
        hdr.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {DS.TEXT_PRIMARY};")
        layout.addWidget(hdr)

        info = QLabel(
            "Check Include to use a sample  •  Same Sum Group name = combined  •  "
            "Empty group = individual")
        info.setWordWrap(True)
        info.setStyleSheet(f"""
            padding: 10px; background: {DS.ACCENT_LIGHT};
            border: 1px solid {DS.ACCENT}; border-radius: 6px;
            color: {DS.ACCENT_HOVER}; font-size: 11px;
        """)
        layout.addWidget(info)

        self.sample_table = QTableWidget()
        self.sample_table.setColumnCount(4)
        self.sample_table.setHorizontalHeaderLabels(
            ["Include", "Sample Name", "Sum Group", "Display Name"])
        self.sample_table.setRowCount(len(self.samples))
        self.sample_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sample_table.setSelectionMode(QTableWidget.MultiSelection)

        for row, sample in enumerate(self.samples):
            cfg = self.current_sample_config.get(
                sample, {'included': False, 'sum_group': '', 'custom_name': sample})
            cb = QCheckBox()
            cb.setChecked(cfg.get('included', False))
            cb.stateChanged.connect(self.on_table_changed)
            self.sample_table.setCellWidget(row, 0, cb)
            si = QTableWidgetItem(sample)
            si.setFlags(si.flags() & ~Qt.ItemIsEditable)
            self.sample_table.setItem(row, 1, si)
            self.sample_table.setItem(row, 2, QTableWidgetItem(cfg.get('sum_group', '')))
            self.sample_table.setItem(row, 3, QTableWidgetItem(cfg.get('custom_name', sample)))

        self.sample_table.itemChanged.connect(self.on_table_changed)
        h = self.sample_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Fixed)
        for c in (1, 2, 3):
            h.setSectionResizeMode(c, QHeaderView.Stretch)
        self.sample_table.setColumnWidth(0, 70)
        layout.addWidget(self.sample_table)

        row1 = QHBoxLayout()
        actions = [
            ("Select All", self.select_all_samples, DS.ACCENT),
            ("Clear All", self.clear_all_samples, DS.ERROR),
            ("Group Selected", self.group_selected_samples, DS.SUCCESS),
            ("Clear Groups", self.clear_all_groups, DS.WARNING),
            ("Copy Group", self.copy_group_name, DS.PURPLE),
            ("Paste to Selected", self.paste_group_name, DS.PINK),
        ]
        for txt, slot, c in actions:
            b = QPushButton(txt)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {c}; color: white; border: none;
                    border-radius: 6px; padding: 7px 12px; font-weight: 600; font-size: 11px;
                }}
                QPushButton:hover {{ background: {QColor(c).lighter(120).name()}; }}
            """)
            b.clicked.connect(slot)
            row1.addWidget(b)
        row1.addStretch()
        layout.addLayout(row1)

        qg = QHBoxLayout()
        qg.addWidget(QLabel("Quick Group:"))
        self.bulk_group_input = QLineEdit()
        self.bulk_group_input.setPlaceholderText("Enter group name…")
        qg.addWidget(self.bulk_group_input)
        ab = QPushButton("Apply to Selected")
        ab.setStyleSheet(f"""
            QPushButton {{ background: {DS.TEAL}; color: white; border: none;
                            border-radius: 6px; padding: 7px 12px; font-weight: 600; }}
            QPushButton:hover {{ background: {QColor(DS.TEAL).lighter(120).name()}; }}
        """)
        ab.clicked.connect(self.apply_bulk_group)
        qg.addWidget(ab)
        layout.addLayout(qg)

        self.clipboard_status = QLabel("Clipboard: empty")
        self.clipboard_status.setStyleSheet(
            f"color: {DS.TEXT_MUTED}; font-size: 10px; font-style: italic; padding: 4px;")
        layout.addWidget(self.clipboard_status)

        self.preview_label = QLabel()
        self.preview_label.setStyleSheet(f"""
            background: {DS.ACCENT_LIGHT}; border: 1px solid {DS.ACCENT};
            border-radius: 6px; padding: 12px; color: {DS.ACCENT_HOVER};
            font-weight: 500; font-size: 12px;
        """)
        layout.addWidget(self.preview_label)
        return widget

    def create_isotope_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.addWidget(QLabel("Select Isotopes to Include"))

        from results.results_periodic import CompactPeriodicTableWidget
        self.periodic_table = CompactPeriodicTableWidget(self)
        self.periodic_table.setMaximumSize(850, 350)
        if self.parent_window and hasattr(self.parent_window, 'selected_isotopes'):
            pairs = []
            for el, isos in self.parent_window.selected_isotopes.items():
                for iso in isos:
                    pairs.append((el, iso))
            if pairs:
                self.periodic_table.update_available_masses(pairs)
        self.set_periodic_table_selections()
        layout.addWidget(self.periodic_table)

        ctrls = QHBoxLayout()
        sa = QPushButton("Select All Available")
        sa.clicked.connect(self.select_all_isotopes)
        ctrls.addWidget(sa)
        cl = QPushButton("Clear Selection")
        cl.clicked.connect(self.clear_isotope_selection)
        ctrls.addWidget(cl)
        ctrls.addStretch()
        layout.addLayout(ctrls)
        return widget

    def on_table_changed(self):
        self.update_sample_config_from_table()
        self.update_preview()

    def update_sample_config_from_table(self):
        for row in range(self.sample_table.rowCount()):
            s = self.samples[row]
            cb = self.sample_table.cellWidget(row, 0)
            sg = self.sample_table.item(row, 2)
            dn = self.sample_table.item(row, 3)
            self.current_sample_config[s] = {
                'included': cb.isChecked(),
                'sum_group': sg.text().strip() if sg else "",
                'custom_name': (dn.text().strip() if dn and dn.text().strip() else s),
            }

    def update_preview(self):
        self.update_sample_config_from_table()
        inc = [s for s, c in self.current_sample_config.items() if c['included']]
        if not inc:
            self.preview_label.setText("No samples selected")
            return
        indiv, groups = [], {}
        for s in inc:
            g = self.current_sample_config[s]['sum_group']
            if not g:
                indiv.append(self.current_sample_config[s]['custom_name'])
            else:
                groups.setdefault(g, []).append(s)
        parts = [f"• {n} (individual)" for n in indiv]
        parts += [f"• {g} (sum of: {', '.join(ss)})" for g, ss in groups.items()]
        self.preview_label.setText(
            f"Will process {len(parts)} data source(s):\n" + "\n".join(parts))

    def get_selected_rows(self):
        return sorted({it.row() for it in self.sample_table.selectedItems()})

    def select_all_samples(self):
        for r in range(self.sample_table.rowCount()):
            self.sample_table.cellWidget(r, 0).setChecked(True)

    def clear_all_samples(self):
        for r in range(self.sample_table.rowCount()):
            self.sample_table.cellWidget(r, 0).setChecked(False)

    def group_selected_samples(self):
        rows = self.get_selected_rows()
        if len(rows) < 2:
            QMessageBox.information(self, "Info", "Select at least 2 rows to group.")
            return
        name, ok = QInputDialog.getText(self, "Group Name", "Name for sum group:")
        if ok and name.strip():
            for r in rows:
                self.sample_table.item(r, 2).setText(name.strip())
                self.sample_table.cellWidget(r, 0).setChecked(True)

    def clear_all_groups(self):
        for r in range(self.sample_table.rowCount()):
            self.sample_table.item(r, 2).setText("")

    def copy_group_name(self):
        rows = self.get_selected_rows()
        if not rows:
            QMessageBox.information(self, "Info", "Select a row first.")
            return
        gi = self.sample_table.item(rows[0], 2)
        g = gi.text().strip() if gi else ""
        if not g:
            QMessageBox.information(self, "Info", "No group name to copy.")
            return
        self.clipboard_group_name = g
        self.clipboard_status.setText(f"Clipboard: '{g}'")

    def paste_group_name(self):
        if not self.clipboard_group_name:
            QMessageBox.information(self, "Info", "Clipboard is empty.")
            return
        rows = self.get_selected_rows()
        if not rows:
            QMessageBox.information(self, "Info", "Select target rows.")
            return
        for r in rows:
            self.sample_table.item(r, 2).setText(self.clipboard_group_name)

    def apply_bulk_group(self):
        g = self.bulk_group_input.text().strip()
        if not g:
            QMessageBox.information(self, "Info", "Enter a group name.")
            return
        rows = self.get_selected_rows()
        if not rows:
            QMessageBox.information(self, "Info", "Select target rows.")
            return
        for r in rows:
            self.sample_table.item(r, 2).setText(g)
        self.bulk_group_input.clear()

    def set_periodic_table_selections(self):
        if not self.current_isotopes:
            return
        by_sym = {}
        for it in self.current_isotopes:
            by_sym.setdefault(it['symbol'], []).append(it['mass'])
        for sym, masses in by_sym.items():
            if sym in self.periodic_table.buttons:
                btn = self.periodic_table.buttons[sym]
                if btn.isotope_display:
                    if not isinstance(btn.isotope_display.selected_isotopes, set):
                        btn.isotope_display.selected_isotopes = set(btn.isotope_display.selected_isotopes or [])
                    for m in masses:
                        btn.isotope_display.selected_isotopes.add((sym, m))
                    if hasattr(btn.isotope_display, 'update'):
                        btn.isotope_display.update()

    def select_all_isotopes(self):
        if self.parent_window and hasattr(self.parent_window, 'selected_isotopes'):
            for el, isos in self.parent_window.selected_isotopes.items():
                if el in self.periodic_table.buttons:
                    btn = self.periodic_table.buttons[el]
                    if btn.isotope_display:
                        for iso in isos:
                            btn.isotope_display.select_preferred_isotope(iso)

    def clear_isotope_selection(self):
        self.periodic_table.clear_all_selections()

    def get_selection(self):
        self.update_sample_config_from_table()
        sel = [s for s, c in self.current_sample_config.items() if c['included']]
        isotopes = []
        if hasattr(self, 'periodic_table'):
            for sym, btn in self.periodic_table.buttons.items():
                if btn.isotope_display and btn.isotope_display.selected_isotopes:
                    for s, m in btn.isotope_display.selected_isotopes:
                        key = f"{s}-{m:.4f}"
                        lbl = self.parent_window.get_formatted_label(key)
                        isotopes.append({'symbol': s, 'mass': m, 'key': key, 'label': lbl})
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

    def process_data(self, input_data):
        self.input_data = input_data
        if input_data:
            dt = input_data.get('type', 'unknown')
            if dt == 'batch_sample_list':
                self.batch_samples = input_data.get('sample_names', [])
                self.batch_particle_data = input_data.get('particle_data', [])
                self.batch_sample_data = input_data.get('data', {})
                self.batch_available_isotopes = input_data.get('available_isotopes', {})

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
        return {
            'type': 'sample_data', 'sample_name': name,
            'data_types': all_dt, 'data': sd,
            'particle_data': filtered, 'selected_isotopes': self.selected_isotopes,
            'total_particles': len(particle_data), 'filtered_particles': len(filtered),
            'sum_replicates': self.sum_replicates,
            'replicate_samples': self.replicate_samples,
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

    def process_data(self, input_data):
        self.input_data = input_data
        if input_data:
            dt = input_data.get('type', 'unknown')
            if dt == 'batch_sample_list':
                self.batch_samples = input_data.get('sample_names', [])
                self.batch_particle_data = input_data.get('particle_data', [])
                self.batch_sample_data = input_data.get('data', {})
                self.batch_available_isotopes = input_data.get('available_isotopes', {})

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

        return {
            'type': 'multiple_sample_data', 'sample_names': names,
            'original_sample_names': list(included),
            'sample_config': self.sample_config or None,
            'data_types': adt, 'data': csd, 'particle_data': combined,
            'selected_isotopes': self.selected_isotopes,
            'total_particles': total, 'filtered_particles': len(combined),
            'sum_replicates': self.sum_replicates,
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

    def get_output_data(self):
        if not self.selected_windows:
            return None
        names, particles, data, isos = [], [], {}, {}
        for wi, w in enumerate(self.selected_windows):
            lbl = f"W{wi+1}"
            if hasattr(w, 'selected_isotopes'):
                for el, il in w.selected_isotopes.items():
                    isos.setdefault(el, set()).update(il)
            if hasattr(w, 'data_by_sample'):
                for sn, sd in w.data_by_sample.items():
                    dn = f"{sn} [{lbl}]"
                    names.append(dn)
                    data[dn] = sd
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
            'is_batch': True, 'source_windows': len(self.selected_windows),
            'parent_window': self.parent_window,
        }

    def configure(self, parent_window):
        dlg = BatchSampleSelectorDialog(parent_window)
        if dlg.exec() == QDialog.Accepted:
            sel = dlg.get_selection()
            if sel:
                self.selected_windows = sel
                self.configuration_changed.emit()
                return True
        return False


class BatchSampleSelectorDialog(QDialog):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.setWindowTitle("Batch Window Selector")
        self.setModal(True)
        self.resize(900, 600)
        self.setStyleSheet(_dialog_base_style())
        
        self.parent_window = parent_window
        app = QApplication.instance()
        self.all_windows = [w for w in getattr(app, 'main_windows', []) if w.isVisible()]
        self.window_checkboxes = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        hdr = QLabel("Select Windows to Include")
        hdr.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DS.TEXT_PRIMARY};")
        layout.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {DS.BG_SECONDARY};
                border: 1px solid {DS.BORDER};
                border-radius: 8px;
            }}
            QScrollBar:vertical {{
                background: {DS.BG_PRIMARY};
                width: 10px;
                margin: 0px 0px 0px 0px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {DS.BG_ELEVATED};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {DS.ACCENT};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        sw = QWidget()
        sw.setStyleSheet(f"background: {DS.BG_SECONDARY};")
        
        sl = QVBoxLayout(sw)
        sl.setSpacing(8)
        sl.setContentsMargins(12, 12, 12, 12)

        for i, w in enumerate(self.all_windows):
            sc = len(getattr(w, 'data_by_sample', {}))
            pc = sum(len(p) for p in getattr(w, 'sample_particle_data', {}).values())
            cs = getattr(w, 'current_sample', '?')
            
            cb = QCheckBox(f"Window {i+1}: {cs}  ({sc} samples, {pc:,} particles)")
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {DS.TEXT_PRIMARY};
                    font-size: 13px;
                    padding: 8px;
                    border-radius: 4px;
                }}
                QCheckBox:hover {{
                    background: {DS.BG_ELEVATED};
                }}
                QCheckBox::indicator {{
                    width: 18px; height: 18px;
                    border-radius: 4px;
                    border: 2px solid {DS.BORDER};
                    background: {DS.BG_INPUT};
                }}
                QCheckBox::indicator:checked {{
                    background: {DS.ACCENT};
                    border-color: {DS.ACCENT};
                }}
            """)
            cb.window_ref = w
            cb.stateChanged.connect(self._preview)
            sl.addWidget(cb)
            self.window_checkboxes.append(cb)

        sl.addStretch()
        scroll.setWidget(sw)
        layout.addWidget(scroll)

        self.preview_label = QLabel("No windows selected")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet(f"""
            padding: 12px; 
            background: {DS.BG_ELEVATED};
            border: 1px solid {DS.BORDER}; 
            border-radius: 6px;
            color: {DS.TEXT_SECONDARY}; 
            font-weight: 600;
        """)
        layout.addWidget(self.preview_label)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.setStyleSheet(f"""
            QPushButton {{
                background: {DS.BG_ELEVATED};
                color: {DS.TEXT_PRIMARY};
                border: 1px solid {DS.BORDER};
                border-radius: 6px;
                padding: 8px 24px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {DS.ACCENT_LIGHT};
                border-color: {DS.ACCENT};
            }}
        """)
        
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _preview(self):
        sel = [cb for cb in self.window_checkboxes if cb.isChecked()]
        if not sel:
            self.preview_label.setText("No windows selected")
            self.preview_label.setStyleSheet(f"""
                padding: 12px; background: {DS.BG_ELEVATED};
                border: 1px solid {DS.BORDER}; border-radius: 6px;
                color: {DS.TEXT_SECONDARY};
            """)
        else:
            ts = sum(len(getattr(cb.window_ref, 'data_by_sample', {})) for cb in sel)
            tp = sum(sum(len(p) for p in getattr(cb.window_ref, 'sample_particle_data', {}).values()) for cb in sel)
            
            self.preview_label.setText(
                f"{len(sel)} window(s)  •  {ts} samples  •  {tp:,} particles")
            self.preview_label.setStyleSheet(f"""
                padding: 12px; background: {DS.ACCENT_LIGHT};
                border: 1px solid {DS.ACCENT}; border-radius: 6px;
                color: {DS.TEXT_ON_ACCENT}; font-weight: bold;
            """)

    def get_selection(self):
        return [cb.window_ref for cb in self.window_checkboxes if cb.isChecked()]

class _StatusNodeMixin:
    """Adds status badge rendering to icon nodes."""

    def _status_text(self):
        return ""

    def _status_color(self):
        return DS.TEXT_SECONDARY


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

        self.paint_icon_node(
            painter, ("#6366F1", "#4338CA"),
            "fa6s.flask", "Sample",
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
        screen = QApplication.primaryScreen().availableGeometry()
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
        total_h = pad_y * 2 + title_h + 6  # title + separator gap
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

        # — Top accent bar —
        bar_grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
        bar_grad.setColorAt(0, QColor(accent.red(), accent.green(), accent.blue(), 200))
        bar_grad.setColorAt(1, QColor(accent.red(), accent.green(), accent.blue(), 0))
        p.setBrush(bar_grad)
        bar_rect = QRectF(rect.left(), rect.top(), rect.width(), 3)
        p.drawRect(bar_rect)

        # — Border —
        border_color = QColor(accent)
        border_color.setAlpha(160)
        p.setPen(QPen(border_color, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect, 10, 10)

        # — Text —
        pad_x, pad_y = 18, 14
        x = int(rect.left()) + pad_x
        y = int(rect.top()) + pad_y

        for i, line in enumerate(self._lines):
            if i == 0:
                # Title row
                p.setFont(self._title_font())
                p.setPen(QColor(accent))
                p.drawText(x, y + QFontMetrics(self._title_font()).ascent(), line)
                y += QFontMetrics(self._title_font()).height() + 2
                # Separator line
                sep_color = QColor(accent)
                sep_color.setAlpha(60)
                p.setPen(QPen(sep_color, 1))
                p.drawLine(x, y + 2, int(rect.right()) - pad_x, y + 2)
                y += 8
            else:
                p.setFont(self._body_font())
                fm = QFontMetrics(self._body_font())
                # Dim the label, highlight the value
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


class MultipleSampleSelectorNodeItem(NodeItem, _StatusNodeMixin):
    """Multiple beakers icon."""
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
        self.paint_icon_node(
            painter, ("#8B5CF6", "#6D28D9"),
            "fa6s.flask-vial", "Multi-Sample",
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
        # Position slightly above/right of cursor
        pos = self.hover_pos
        tw = self._tooltip_widget
        x = pos.x() + 14
        y = pos.y() - tw.height() - 8
        # Keep on screen
        screen = QApplication.primaryScreen().availableGeometry()
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
        if wf.selected_windows:
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

def _make_viz_icon_node(grad_colors, icon_name, label, dialog_class):
    """Factory: creates a circular icon node for each visualization type."""

    class VizIconNodeItem(NodeItem):
        def __init__(self, wf, pw=None):
            super().__init__(wf)
            self.parent_window = pw
            wf.configuration_changed.connect(self.update)

        def paint(self, painter, option, widget=None):
            self.paint_icon_node(painter, grad_colors, icon_name, label)

        def configure_node(self):
            dlg = dialog_class(self.workflow_node, self.parent_window)
            dlg.show()

    VizIconNodeItem.__name__ = f"{label.replace(' ', '').replace('/', '')}IconNodeItem"
    return VizIconNodeItem

HistogramPlotNodeItem = _make_viz_icon_node(
    ("#F97316", "#C2410C"), "fa6s.chart-column", "Histogram",
    HistogramDisplayDialog)

ElementBarChartPlotNodeItem = _make_viz_icon_node(
    ("#EF4444", "#B91C1C"), "fa6s.chart-bar", "Bar Chart",
    ElementBarChartDisplayDialog)

BoxPlotNodeItem = _make_viz_icon_node(
    ("#8B5CF6", "#6D28D9"), "fa6s.chart-simple", "Box Plot",
    BoxPlotDisplayDialog)

CorrelationPlotNodeItem = _make_viz_icon_node(
    ("#EC4899", "#BE185D"), "fa6s.chart-line", "Correlation",
    CorrelationPlotDisplayDialog)

PieChartPlotNodeItem = _make_viz_icon_node(
    ("#14B8A6", "#0F766E"), "fa6s.chart-pie", "Pie Chart",
    PieChartDisplayDialog)

ElementCompositionPlotNodeItem = _make_viz_icon_node(
    ("#06B6D4", "#0E7490"), "fa6s.circle-half-stroke", "Composition",
    ElementCompositionDisplayDialog)

HeatmapPlotNodeItem = _make_viz_icon_node(
    ("#F59E0B", "#B45309"), "fa6s.fire", "Heatmap",
    HeatmapDisplayDialog)

MolarRatioPlotNodeItem = _make_viz_icon_node(
    ("#6366F1", "#4338CA"), "fa6s.divide", "Molar Ratio",
    MolarRatioDisplayDialog)

IsotopicRatioPlotNodeItem = _make_viz_icon_node(
    ("#A855F7", "#7E22CE"), "fa6s.atom", "Isotope Ratio",
    IsotopicRatioDisplayDialog)

TrianglePlotNodeItem = _make_viz_icon_node(
    ("#22C55E", "#15803D"), "fa6s.play", "Ternary",
    TriangleDisplayDialog)

SingleMultipleElementPlotNodeItem = _make_viz_icon_node(
    ("#3B82F6", "#1D4ED8"), "fa6s.layer-group", "Single/Multi",
    SingleMultipleElementDisplayDialog)

ClusteringPlotNodeItem = _make_viz_icon_node(
    ("#0EA5E9", "#0369A1"), "fa6s.circle-nodes", "Clustering",
    ClusteringDisplayDialog)

CorrelationMatrixNodeItem = _make_viz_icon_node(
    ("#F43F5E", "#BE123C"), "fa6s.table-cells", "Corr. Matrix",
    CorrelationMatrixDisplayDialog)

ConcentrationComparisonNodeItem = _make_viz_icon_node(
    ("#8B5CF6", "#6D28D9"), "fa6s.arrows-left-right", "Concentration",
    ConcentrationDisplayDialog)

NetworkDiagramNodeItem = _make_viz_icon_node(
    ("#14B8A6", "#0F766E"), "fa6s.diagram-project", "Network",
    NetworkDisplayDialog)


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

class DraggableNodeButton(QPushButton):

    def __init__(self, text, node_type, icon_name=None, color=None):
        super().__init__(text)
        self.node_type = node_type
        self.setMinimumHeight(34)
        self.setCursor(QCursor(Qt.OpenHandCursor))
        c = color or DS.ACCENT
        if icon_name:
            self.setIcon(qta.icon(icon_name, color=c))
        self.setStyleSheet(f"""
            QPushButton {{
                background: {DS.BG_SURFACE};
                color: {DS.TEXT_PRIMARY};
                border: 1px solid {DS.BORDER};
                border-radius: 8px;
                padding: 7px 10px;
                text-align: left;
                font-size: 12px;
                font-weight: 500;
                font-family: '{DS.FONT_FAMILY}';
            }}
            QPushButton:hover {{
                background: {DS.ACCENT_LIGHT};
                border-color: {DS.ACCENT};
                color: {DS.ACCENT_HOVER};
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(self.node_type)
            drag.setMimeData(mime)
            px = self.grab()
            drag.setPixmap(px)
            drag.setHotSpot(QPoint(px.width()//2, px.height()//2))
            drag.exec_(Qt.CopyAction)
        super().mousePressEvent(event)

class _CollapsibleGroup(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self._expanded = True
        self._btn = QPushButton(f"  ▾  {title}")
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {DS.TEXT_SECONDARY};
                border: none;
                text-align: left;
                font-weight: 700;
                font-size: 11px;
                padding: 6px 4px;
                font-family: '{DS.FONT_FAMILY}';
            }}
            QPushButton:hover {{ color: {DS.ACCENT_HOVER}; }}
        """)
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
        self._title = title

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
        self.setStyleSheet(f"background: {DS.BG_SECONDARY};")

        self.search = QLineEdit()
        self.search.setPlaceholderText("  🔍  Search nodes…")
        self.search.setClearButtonEnabled(True)
        self.search.setStyleSheet(f"""
            QLineEdit {{
                background: {DS.BG_INPUT};
                color: {DS.TEXT_PRIMARY};
                border: 1px solid {DS.BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                margin: 10px 10px 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{ border: 2px solid {DS.ACCENT}; }}
        """)
        self.search.textChanged.connect(self._filter)
        root.addWidget(self.search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                background: {DS.BG_SECONDARY}; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {DS.BORDER}; border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {DS.TEXT_MUTED}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

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
        ]:
            b = DraggableNodeButton(txt, ntype, icon, color)
            vg.addWidget(b)
            self._all_buttons.append((b, txt))
        cl.addWidget(vg)

        # ── AI ─────────────────────────────────────────────────────────────
        ag = _CollapsibleGroup("AI & ANALYTICS")
        b = DraggableNodeButton("AI Data Assistant", "ai_assistant",
                                'fa6s.wand-magic-sparkles', DS.PINK)
        ag.addWidget(b)
        self._all_buttons.append((b, "AI Data Assistant"))
        cl.addWidget(ag)

        cl.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

        hint = QLabel("Drag → Canvas  •  Del = delete  •  Ctrl+C = duplicate")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"""
            color: {DS.TEXT_MUTED}; font-size: 10px;
            padding: 8px 12px; background: {DS.BG_PRIMARY};
            border-top: 1px solid {DS.BORDER};
        """)
        root.addWidget(hint)

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

        self.setSceneRect(-2000, -2000, 4000, 4000)
        self.selectionChanged.connect(self._on_selection)

    def _on_selection(self):
        n = sum(1 for i in self.selectedItems() if isinstance(i, NodeItem))
        self.node_selection_changed.emit(n)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected_items()
        elif event.key() == Qt.Key_D and event.modifiers() == Qt.ControlModifier:
            self.duplicate_selected_nodes()
        elif event.key() == Qt.Key_A and event.modifiers() == Qt.ControlModifier:
            self.select_all_items()
        elif event.key() == Qt.Key_Escape:
            self.clearSelection()
        else:
            super().keyPressEvent(event)

    def delete_selected_items(self):
        nodes = [i for i in self.selectedItems() if isinstance(i, NodeItem)]
        links = [i for i in self.selectedItems() if isinstance(i, LinkItem)]
        for l in links:
            self.delete_link(l)
        for n in nodes:
            self.delete_node(n)

    def delete_node(self, ni):
        if not isinstance(ni, NodeItem):
            return
        wn = ni.workflow_node
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
                     'selected_samples', 'sample_config'):
            if hasattr(wf, attr):
                try:
                    setattr(new_wf, attr, copy.deepcopy(getattr(wf, attr)))
                except:
                    pass
        pos = ni.pos() + QPointF(DS.NODE_W + 30, 20)
        _, item = self.add_node(new_wf, pos)
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
        return wf_node, ni

    def add_link(self, src_node, src_ch, snk_node, snk_ch):
        for lk in self.workflow_links:
            if (lk.source_node == src_node and lk.sink_node == snk_node
                    and lk.source_channel == src_ch and lk.sink_channel == snk_ch):
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
            print(f"Data flow error: {e}")

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
            if self.temp_link_item.sink_anchor:
                self.temp_link_item.sink_anchor.setPos(event.scenePos())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.dragging_connection:
            self._end_drag(event.scenePos())
        else:
            super().mouseReleaseEvent(event)

    def _start_drag(self, anchor, pos):
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

    def _end_drag(self, pos):
        if self.temp_link_item:
            if self.temp_link_item.sink_anchor:
                self.removeItem(self.temp_link_item.sink_anchor)
            self.removeItem(self.temp_link_item)
            self.temp_link_item = None

        target = None
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

        self.setStyleSheet(f"""
            QGraphicsView {{
                background: {DS.BG_PRIMARY};
                border: none;
            }}
        """)

        self._zoom = 1.0
        self._panning = False
        self._pan_start = QPoint()
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence.Delete, self).activated.connect(
            self.scene.delete_selected_items)
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(
            self.scene.duplicate_selected_nodes)
        QShortcut(QKeySequence.SelectAll, self).activated.connect(
            self.scene.select_all_items)
        QShortcut(QKeySequence("Escape"), self).activated.connect(
            self.scene.clearSelection)

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
        painter.fillRect(rect, QColor(DS.BG_PRIMARY))

        gs = DS.GRID_SIZE
        dot = QColor(255, 255, 255, DS.GRID_DOT_ALPHA)
        painter.setPen(QPen(dot, 1.5))

        left = int(rect.left()) - (int(rect.left()) % gs)
        top = int(rect.top()) - (int(rect.top()) % gs)
        y = top
        while y < rect.bottom():
            x = left
            while x < rect.right():
                painter.drawPoint(x, y)
                x += gs
            y += gs

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not event.mimeData().hasText():
            event.ignore()
            return
        ntype = event.mimeData().text()
        sp = self.mapToScene(event.pos())
        gs = DS.GRID_SIZE
        snapped = QPointF(round(sp.x() / gs) * gs, round(sp.y() / gs) * gs)

        factory = _NODE_FACTORIES.get(ntype)
        if factory:
            wf = factory(self.parent_window)
            self.scene.add_node(wf, snapped)
            event.acceptProposedAction()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        self.scene.keyPressEvent(event)
        super().keyPressEvent(event)


_NODE_FACTORIES = {
    "sample_selector":              SampleSelectorNode,
    "multiple_sample_selector":     MultipleSampleSelectorNode,
    "batch_sample_selector":        BatchSampleSelectorNode,
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
}

_NODE_ITEM_MAP = {
    "sample_selector":              SampleSelectorNodeItem,
    "multiple_sample_selector":     MultipleSampleSelectorNodeItem,
    "batch_sample_selector":        BatchSampleSelectorNodeItem,
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
}


class CanvasResultsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("IsotopeTrack — Workflow Builder")
        self.setMinimumSize(1300, 780)
        self.setStyleSheet(f"""
            QDialog {{ background: {DS.BG_PRIMARY}; }}
            QSplitter::handle {{ background: {DS.BORDER}; width: 1px; }}
        """)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header bar ─────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"""
            QFrame {{
                background: {DS.BG_SECONDARY};
                border-bottom: 1px solid {DS.BORDER};
            }}
        """)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)

        logo = QLabel("◆  Workflow Builder")
        logo.setStyleSheet(f"""
            color: {DS.TEXT_PRIMARY};
            font-size: 16px; font-weight: 700;
            font-family: '{DS.FONT_FAMILY}';
        """)
        hl.addWidget(logo)
        hl.addStretch()

        zm = QPushButton("−")
        zm.setFixedSize(30, 30)
        zm.setStyleSheet(self._tool_btn_style())
        zm.clicked.connect(lambda: self.canvas.set_zoom(self.canvas._zoom / 1.2))
        hl.addWidget(zm)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(50)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setStyleSheet(
            f"color: {DS.TEXT_SECONDARY}; font-size: 12px; font-weight: 600;")
        hl.addWidget(self.zoom_label)

        zp = QPushButton("+")
        zp.setFixedSize(30, 30)
        zp.setStyleSheet(self._tool_btn_style())
        zp.clicked.connect(lambda: self.canvas.set_zoom(self.canvas._zoom * 1.2))
        hl.addWidget(zp)

        fit = QPushButton("Fit")
        fit.setFixedSize(40, 30)
        fit.setStyleSheet(self._tool_btn_style())
        fit.clicked.connect(lambda: self.canvas.fit_content())
        hl.addWidget(fit)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {DS.BORDER}; margin: 8px 12px;")
        hl.addWidget(sep)

        clr = QPushButton("Clear All")
        clr.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {DS.ERROR};
                border: 1px solid {DS.ERROR}; border-radius: 6px;
                padding: 5px 14px; font-weight: 600; font-size: 11px;
            }}
            QPushButton:hover {{ background: {DS.ERROR_BG}; }}
        """)
        clr.clicked.connect(self.clear_canvas)
        hl.addWidget(clr)

        back = QPushButton("✕  Close")
        back.setStyleSheet(f"""
            QPushButton {{
                background: {DS.ACCENT}; color: white;
                border: none; border-radius: 6px;
                padding: 6px 16px; font-weight: 600; font-size: 11px;
            }}
            QPushButton:hover {{ background: {DS.ACCENT_HOVER}; }}
        """)
        back.clicked.connect(self.close)
        hl.addWidget(back)

        root.addWidget(hdr)

        # ── body splitter ──────────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        pf = QFrame()
        pf.setFixedWidth(240)
        pf.setStyleSheet(
            f"background: {DS.BG_SECONDARY}; border-right: 1px solid {DS.BORDER};")
        pl = QVBoxLayout(pf)
        pl.setContentsMargins(0, 0, 0, 0)
        self.palette = NodePalette(self.parent)
        pl.addWidget(self.palette)

        self.canvas = EnhancedCanvasView(self.parent)
        self.canvas.zoom_changed.connect(
            lambda z: self.zoom_label.setText(f"{int(z * 100)}%"))

        splitter.addWidget(pf)
        splitter.addWidget(self.canvas)
        splitter.setSizes([240, 1060])
        root.addWidget(splitter)

        sb = QFrame()
        sb.setFixedHeight(28)
        sb.setStyleSheet(f"""
            QFrame {{
                background: {DS.BG_SECONDARY};
                border-top: 1px solid {DS.BORDER};
            }}
        """)
        sbl = QHBoxLayout(sb)
        sbl.setContentsMargins(12, 0, 12, 0)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(
            f"color: {DS.TEXT_MUTED}; font-size: 11px;")
        sbl.addWidget(self.status_label)
        sbl.addStretch()

        self.sel_label = QLabel("")
        self.sel_label.setStyleSheet(
            f"color: {DS.TEXT_MUTED}; font-size: 11px;")
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
        return f"""
            QPushButton {{
                background: {DS.BG_ELEVATED};
                color: {DS.TEXT_PRIMARY};
                border: 1px solid {DS.BORDER};
                border-radius: 6px;
                font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover {{
                background: {DS.ACCENT_LIGHT};
                border-color: {DS.ACCENT};
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