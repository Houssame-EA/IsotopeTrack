from PySide6.QtWidgets import (QDialog, QMenu,QVBoxLayout, QHBoxLayout, QWidget, 
                              QPushButton, QGraphicsView, QGraphicsScene, 
                              QGraphicsItem, QGraphicsProxyWidget, QLabel, QTableWidget,
                              QComboBox, QListWidget, QListWidgetItem, QCheckBox,
                              QFrame, QScrollArea, QSplitter, QGroupBox, QTableWidgetItem, 
                              QGraphicsWidget, QGraphicsEllipseItem, QApplication, QMainWindow,
                              QDialogButtonBox, QFormLayout, QSpinBox, QDoubleSpinBox, QTabWidget, QLineEdit, QAbstractItemView, QTextEdit)
from PySide6.QtCore import Qt, Signal, QPointF, QRectF, QMimeData, QPoint, QObject
from PySide6.QtGui import (QPainter, QPen, QBrush, QColor, QDrag, QPixmap, QPainterPath, 
                          QLinearGradient, QFont, QPainterPathStroker, QRadialGradient, QShortcut, QKeySequence)
import math
import numpy as np
from results.results_pie_charts import PieChartDisplayDialog, PieChartPlotNode, ElementCompositionDisplayDialog, ElementCompositionPlotNode
from results.results_heatmap import HeatmapDisplayDialog, HeatmapPlotNode
from results.results_bar_charts import ElementBarChartDisplayDialog, ElementBarChartPlotNode,HistogramPlotNode, HistogramDisplayDialog
from results.results_correlation import CorrelationPlotDisplayDialog, CorrelationPlotNode
from results.results_isotope import IsotopicRatioDisplayDialog, IsotopicRatioPlotNode
from results.results_cluster import ClusteringDisplayDialog, ClusteringPlotNode
from results.results_triangle import TriangleDisplayDialog, TrianglePlotNode
from results.results_AI import AIAssistantNode, EnhancedLocalChatDialog as AIAssistantChatDialog
from results.results_box_plot import BoxPlotDisplayDialog, BoxPlotNode
from results.results_molar_ratio import MolarRatioDisplayDialog, MolarRatioPlotNode
from results.results_single_multiple import (SingleMultipleElementDisplayDialog, SingleMultipleElementPlotNode)

import qtawesome as qta




class NodeItem(QGraphicsWidget):
    
    def __init__(self, workflow_node, parent=None):
        """
        Initialize enhanced visual representation of a workflow node with modern styling.
        
        Args:
            workflow_node: The workflow node data model this item represents
            parent: Optional parent QGraphicsItem
        """
        super().__init__(parent)
        self.workflow_node = workflow_node
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        self.width = 180
        self.height = 120
        self.corner_radius = 8
        self.setAcceptHoverEvents(True)
        
        self.is_hovered = False
        
        self.anchors = {}
        self._create_anchors()
        
        if hasattr(workflow_node, 'position_changed'):
            workflow_node.position_changed.connect(self.setPos)
        
    def paint_base_node(self, painter, header_r1, header_g1, header_b1, header_r2, header_g2, header_b2, icon_draw_func, title_text):
        """
        Base painting method to reduce code duplication with fixed signature.
    
        """
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = QRectF(0, 0, self.width, self.height)
        
        shadow_offset = 3
        shadow_rect = rect.translated(shadow_offset, shadow_offset)
        shadow_gradient = QRadialGradient(rect.center(), max(self.width, self.height) / 2)
        shadow_gradient.setColorAt(0, QColor(0, 0, 0, 20))
        shadow_gradient.setColorAt(1, QColor(0, 0, 0, 5))
        painter.setBrush(QBrush(shadow_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(shadow_rect, self.corner_radius, self.corner_radius)
        
        body_gradient = QLinearGradient(0, 0, 0, self.height)
        
        if self.isSelected():
            body_gradient.setColorAt(0, QColor(239, 246, 255))
            body_gradient.setColorAt(1, QColor(219, 234, 254))
            painter.setPen(QPen(QColor(59, 130, 246), 3))
        elif self.is_hovered:
            body_gradient.setColorAt(0, QColor(249, 250, 251))
            body_gradient.setColorAt(1, QColor(243, 244, 246))
            painter.setPen(QPen(QColor(156, 163, 175), 2))
        else:
            body_gradient.setColorAt(0, QColor(255, 255, 255))
            body_gradient.setColorAt(1, QColor(248, 250, 252))
            painter.setPen(QPen(QColor(229, 231, 235), 1))
        
        painter.setBrush(QBrush(body_gradient))
        painter.drawRoundedRect(rect, self.corner_radius, self.corner_radius)
        
        header_height = 32
        header_rect = QRectF(0, 0, self.width, header_height)
        
        header_gradient = QLinearGradient(0, 0, 0, header_height)
        header_gradient.setColorAt(0, QColor(header_r1, header_g1, header_b1))
        header_gradient.setColorAt(1, QColor(header_r2, header_g2, header_b2))
        
        painter.setBrush(QBrush(header_gradient))
        painter.setPen(Qt.NoPen)
        
        header_path = QPainterPath()
        header_path.addRoundedRect(header_rect, self.corner_radius, self.corner_radius)
        bottom_rect = QRectF(0, header_height - self.corner_radius, self.width, self.corner_radius)
        header_path.addRect(bottom_rect)
        painter.fillPath(header_path, QBrush(header_gradient))
        
        icon_rect = QRectF(8, 6, 20, 20)
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(Qt.NoBrush)
        icon_draw_func(painter, icon_rect)
        
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        title_rect = QRectF(32, 6, self.width - 64, 20)
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, title_text)
        
        self.draw_config_button(painter)
    
    def draw_config_button(self, painter):
        """
        Draw the common configuration button in the node header.
        
        Args:
            painter: QPainter object for drawing
        """
        config_rect = QRectF(self.width - 28, 6, 20, 20)
        config_gradient = QRadialGradient(config_rect.center(), 10)
        config_gradient.setColorAt(0, QColor(255, 255, 255, 200))
        config_gradient.setColorAt(1, QColor(255, 255, 255, 100))
        painter.setBrush(QBrush(config_gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 150), 1))
        painter.drawEllipse(config_rect)
        
        painter.setPen(QPen(QColor(100, 100, 100), 1.5))
        painter.setBrush(Qt.NoBrush)
        center = config_rect.center()
        inner_radius = 3
        outer_radius = 7
        
        for i in range(8):
            angle = i * 45 * math.pi / 180
            inner_x = center.x() + inner_radius * math.cos(angle)
            inner_y = center.y() + inner_radius * math.sin(angle)
            outer_x = center.x() + outer_radius * math.cos(angle)
            outer_y = center.y() + outer_radius * math.sin(angle)
            painter.drawLine(QPointF(inner_x, inner_y), QPointF(outer_x, outer_y))
        
        painter.drawEllipse(center, 2, 2)
    
    def paint(self, painter, option, widget=None):
        """
        Default paint for base NodeItem.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        def draw_default_icon(painter, icon_rect):
            painter.drawRoundedRect(icon_rect, 2, 2)
            painter.drawLine(icon_rect.left() + 4, icon_rect.top() + 6, 
                           icon_rect.right() - 4, icon_rect.top() + 6)
            painter.drawLine(icon_rect.left() + 4, icon_rect.top() + 10, 
                           icon_rect.right() - 4, icon_rect.top() + 10)
            painter.drawLine(icon_rect.left() + 4, icon_rect.top() + 14, 
                           icon_rect.right() - 4, icon_rect.top() + 14)
        
        self.paint_base_node(painter, 99, 102, 241, 79, 70, 229, draw_default_icon, self.workflow_node.title)
        
    
    def _create_anchors(self):
        """
        Create input and output anchor points for node connections.
        """
        if hasattr(self.workflow_node, '_has_input') and self.workflow_node._has_input:
            input_anchor = AnchorPoint(self, "input", is_input=True)
            input_anchor.setPos(-8, self.height / 2)
            self.anchors["input"] = input_anchor
        
        if hasattr(self.workflow_node, '_has_output') and self.workflow_node._has_output:
            output_anchor = AnchorPoint(self, "output", is_input=False)
            output_anchor.setPos(self.width + 8, self.height / 2)
            self.anchors["output"] = output_anchor
    
    def get_anchor(self, channel_name):
        """
        Get an anchor point by its channel name.
        
        Args:
            channel_name: Name of the channel to retrieve
            
        Returns:
            AnchorPoint: The requested anchor point or None if not found
        """
        return self.anchors.get(channel_name)
    
    def boundingRect(self):
        """
        Get the bounding rectangle including anchor points.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return QRectF(-16, -8, self.width + 32, self.height + 16)
    
    def shape(self):
        """
        Define the shape for precise collision detection - entire box is clickable.
        
        Returns:
            QPainterPath: Shape path for collision detection
        """
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width, self.height), self.corner_radius, self.corner_radius)
        return path
    
    def hoverEnterEvent(self, event):
        """
        Handle mouse hover enter event.
        
        Args:
            event: QGraphicsSceneHoverEvent
        """
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """
        Handle mouse hover leave event.
        
        Args:
            event: QGraphicsSceneHoverEvent
        """
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """
        Handle mouse press for selection and dragging.
        
        Args:
            event: QGraphicsSceneMouseEvent
        """
        if event.button() == Qt.LeftButton:
            self.setSelected(True)
            if self.scene():
                self.scene().clearSelection()
                self.setSelected(True)
        elif event.button() == Qt.RightButton:
            self.show_context_menu(event.screenPos())
        super().mousePressEvent(event)
    
    def show_context_menu(self, global_pos):
        """
        Show context menu with ONLY duplicate and delete options.
        
        Args:
            global_pos: Global screen position for menu placement
        """
        menu = QMenu()
        
        duplicate_action = menu.addAction("📋 Duplicate")
        duplicate_action.triggered.connect(self.duplicate_node)
        
        delete_action = menu.addAction("🗑️ Delete")
        delete_action.triggered.connect(self.delete_node)
        
        menu.exec(global_pos)
    
    def duplicate_node(self):
        """
        Duplicate this node.
        """
        if self.scene():
            self.scene().duplicate_node(self)
    
    def delete_node(self):
        """
        Delete this node.
        """
        if self.scene():
            self.scene().delete_node(self)
    
    def itemChange(self, change, value):
        """
        Handle item changes including position and selection.
        
        Args:
            change: Type of change occurring
            value: New value for the change
            
        Returns:
            Result of parent itemChange call
        """
        if change == QGraphicsItem.ItemPositionHasChanged:
            if hasattr(self.workflow_node, 'set_position'):
                self.workflow_node.set_position(value)
        elif change == QGraphicsItem.ItemSelectedHasChanged:
            self.update()
        return super().itemChange(change, value)
    
    def mouseDoubleClickEvent(self, event):
        """
        Open configuration dialog on double-click.
        
        Args:
            event: QGraphicsSceneMouseEvent
        """
        self.configure_node()
        super().mouseDoubleClickEvent(event)
        
    def configure_node(self):
        """
        Override in subclasses to show configuration dialog.
        """
        pass


class WorkflowLink(QObject):
    
    state_changed = Signal(int)
    
    def __init__(self, source_node, source_channel, sink_node, sink_channel):
        """
        Initialize data model for a connection between two nodes.
        
        Args:
            source_node: Source workflow node
            source_channel: Output channel name on source
            sink_node: Destination workflow node
            sink_channel: Input channel name on sink
        """
        super().__init__()
        self.source_node = source_node
        self.source_channel = source_channel
        self.sink_node = sink_node
        self.sink_channel = sink_channel
        self.enabled = True
        
    def get_data(self):
        """
        Get data from source node.
        
        Returns:
            Data from source node's output or None
        """
        if hasattr(self.source_node, 'get_output_data'):
            return self.source_node.get_output_data()
        return None

class WorkflowNode(QObject):
    
    position_changed = Signal(QPointF)
    configuration_changed = Signal()
    
    def __init__(self, title, node_type):
        """
        Initialize data model for a workflow node.
        
        Args:
            title: Display title for the node
            node_type: Type identifier string for the node
        """
        super().__init__()
        self.title = title
        self.node_type = node_type
        self.position = QPointF(0, 0)
        self._has_input = False
        self._has_output = False
        self.input_channels = []
        self.output_channels = []
        
    def set_position(self, pos):
        """
        Set the position of the node.
        
        Args:
            pos: New position as QPointF
        """
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)
            
    def configure(self, parent_window):
        """
        Override in subclasses to show configuration dialog.
        
        Args:
            parent_window: Parent window for dialog
        """
        pass


class AnchorPointSignals(QObject):
    
    position_changed = Signal(QPointF)

class AnchorPoint(QGraphicsEllipseItem):
    
    def __init__(self, parent, channel_name, is_input=True):
        """
        Initialize connection anchor point with enhanced visuals.
        
        Args:
            parent: Parent node item
            channel_name: Name of this channel
            is_input: True for input anchor, False for output
        """
        super().__init__(parent)
        self.channel_name = channel_name
        self.is_input = is_input
        self.radius = 10
        
        self.signals = AnchorPointSignals()
        self.position_changed = self.signals.position_changed
        
        rect = QRectF(-self.radius, -self.radius, self.radius * 2, self.radius * 2)
        self.setRect(rect)
        
        if is_input:
            gradient = QRadialGradient(0, 0, self.radius)
            gradient.setColorAt(0, QColor(74, 222, 128))
            gradient.setColorAt(1, QColor(34, 197, 94))
            self.setBrush(QBrush(gradient))
            self.setPen(QPen(QColor(22, 163, 74), 2))   
        else:
            gradient = QRadialGradient(0, 0, self.radius)
            gradient.setColorAt(0, QColor(248, 113, 113))
            gradient.setColorAt(1, QColor(239, 68, 68))
            self.setBrush(QBrush(gradient))
            self.setPen(QPen(QColor(220, 38, 38), 2))   
            
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges, True)
        self.setZValue(10)
        
    def itemChange(self, change, value):
        """
        Handle item changes and emit position updates.
        
        Args:
            change: Type of change occurring
            value: New value for the change
            
        Returns:
            Result of parent itemChange call
        """
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            self.position_changed.emit(value)
        return super().itemChange(change, value)
    
    def hoverEnterEvent(self, event):
        """
        Enhanced hover effect with glow.
        
        Args:
            event: QGraphicsSceneHoverEvent
        """
        if self.is_input:
            gradient = QRadialGradient(0, 0, self.radius * 1.2)
            gradient.setColorAt(0, QColor(134, 239, 172))
            gradient.setColorAt(1, QColor(34, 197, 94))
            self.setBrush(QBrush(gradient))
        else:
            gradient = QRadialGradient(0, 0, self.radius * 6)
            gradient.setColorAt(0, QColor(252, 165, 165))
            gradient.setColorAt(1, QColor(239, 68, 68))
            self.setBrush(QBrush(gradient))
        
        self.setScale(1.4)
        self.setPen(QPen(self.pen().color(), 3))
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """
        Reset to normal appearance when hover ends.
        
        Args:
            event: QGraphicsSceneHoverEvent
        """
        if self.is_input:
            gradient = QRadialGradient(0, 0, self.radius)
            gradient.setColorAt(0, QColor(74, 222, 128))
            gradient.setColorAt(1, QColor(34, 197, 94))
            self.setBrush(QBrush(gradient))
            self.setPen(QPen(QColor(22, 163, 74), 2))
        else:
            gradient = QRadialGradient(0, 0, self.radius)
            gradient.setColorAt(0, QColor(248, 113, 113))
            gradient.setColorAt(1, QColor(239, 68, 68))
            self.setBrush(QBrush(gradient))
            self.setPen(QPen(QColor(220, 38, 38), 2))
        
        self.setScale(1.0)
        super().hoverLeaveEvent(event)

class LinkCurveItem(QGraphicsWidget):
    
    def __init__(self, parent=None):
        """
        Initialize enhanced curve drawing component with better visuals.
        
        Args:
            parent: Optional parent QGraphicsItem
        """
        super().__init__(parent)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setAcceptHoverEvents(True)
        
        self.__curve_path = QPainterPath()
        self.__pen = QPen(QBrush(QColor("#3B82F6")), 3.0)  
        self.__hover_pen = QPen(QBrush(QColor("#1D4ED8")), 4.0)  
        self.hover = False
        
        self.__shadow_pen = QPen(QBrush(QColor(0, 0, 0, 60)), 5.0)
        
    def set_curve_path(self, path):
        """
        Set the curve path for this link.
        
        Args:
            path: QPainterPath defining the curve
        """
        if path != self.__curve_path:
            self.prepareGeometryChange()
            self.__curve_path = path
            self.update()
    
    def set_pen(self, pen):
        """
        Set the pen used to draw the curve.
        
        Args:
            pen: QPen to use for drawing
        """
        if pen != self.__pen:
            self.__pen = pen
            self.update()
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the curve.
        
        Returns:
            QRectF: Bounding rectangle including stroke width
        """
        if self.__curve_path.isEmpty():
            return QRectF()
        
        stroke = QPainterPathStroker()
        stroke.setWidth(max(self.__pen.widthF() + 8, 15))  
        stroke_path = stroke.createStroke(self.__curve_path)
        return stroke_path.boundingRect()
    
    def paint(self, painter, option, widget=None):
        """
        Paint the curve with shadow and optional gradient.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        if self.__curve_path.isEmpty():
            return
            
        painter.setRenderHint(QPainter.Antialiasing)
        
        shadow_path = QPainterPath(self.__curve_path)
        shadow_path.translate(2, 2)
        painter.setPen(self.__shadow_pen)
        painter.drawPath(shadow_path)
        
        if self.hover:
            gradient = QLinearGradient(self.__curve_path.pointAtPercent(0), 
                                     self.__curve_path.pointAtPercent(1))
            gradient.setColorAt(0, QColor("#3B82F6"))
            gradient.setColorAt(1, QColor("#8B5CF6"))
            pen = QPen(QBrush(gradient), 4.0)
            painter.setPen(pen)
        else:
            painter.setPen(self.__pen)
        
        painter.drawPath(self.__curve_path)
    
    def hoverEnterEvent(self, event):
        """
        Handle hover enter event.
        
        Args:
            event: QGraphicsSceneHoverEvent
        """
        self.hover = True
        self.update()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """
        Handle hover leave event.
        
        Args:
            event: QGraphicsSceneHoverEvent
        """
        self.hover = False
        self.update()
        super().hoverLeaveEvent(event)

class LinkItem(QGraphicsWidget):
    
    activated = Signal()
    
    def __init__(self, parent=None):
        """
        Initialize enhanced visual representation of a connection with selection support.
        
        Args:
            parent: Optional parent QGraphicsItem
        """
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
        """
        Set the source anchor for this link.
        
        Args:
            anchor: AnchorPoint to connect from
        """
        if self.source_anchor:
            try:
                self.source_anchor.position_changed.disconnect(self.__update_curve)
            except:
                pass
        
        self.source_anchor = anchor
        if anchor:
            anchor.position_changed.connect(self.__update_curve)
        self.__update_curve()
    
    def set_sink_anchor(self, anchor):
        """
        Set the sink anchor for this link.
        
        Args:
            anchor: AnchorPoint to connect to
        """
        if self.sink_anchor:
            try:
                self.sink_anchor.position_changed.disconnect(self.__update_curve)
            except:
                pass
            
        self.sink_anchor = anchor
        if anchor:
            anchor.position_changed.connect(self.__update_curve)
        self.__update_curve()
    
    def set_workflow_link(self, link):
        """
        Set the workflow link data model.
        
        Args:
            link: WorkflowLink data model
        """
        self.workflow_link = link
    
    def __update_curve(self):
        """
        Update curve with proper coordinate mapping and selection highlighting.
        """
        if not self.source_anchor or not self.sink_anchor:
            return
        
        try:
            source_scene_pos = self.source_anchor.scenePos()
            sink_scene_pos = self.sink_anchor.scenePos()
            
            min_x = min(source_scene_pos.x(), sink_scene_pos.x()) - 50
            min_y = min(source_scene_pos.y(), sink_scene_pos.y()) - 50
            max_x = max(source_scene_pos.x(), sink_scene_pos.x()) + 50
            max_y = max(source_scene_pos.y(), sink_scene_pos.y()) + 50
            
            self.setPos(min_x, min_y)
            self.resize(max_x - min_x, max_y - min_y)
            
            source_local = QPointF(source_scene_pos.x() - min_x, source_scene_pos.y() - min_y)
            sink_local = QPointF(sink_scene_pos.x() - min_x, sink_scene_pos.y() - min_y)
            
            path = QPainterPath()
            
            dx = sink_local.x() - source_local.x()
            dy = sink_local.y() - source_local.y()
            
            control_offset_x = max(abs(dx) * 0.5, 40)
            control_offset_y = abs(dy) * 0.1
            
            control1 = QPointF(source_local.x() + control_offset_x, source_local.y() + control_offset_y)
            control2 = QPointF(sink_local.x() - control_offset_x, sink_local.y() - control_offset_y)
            
            path.moveTo(source_local)
            path.cubicTo(control1, control2, sink_local)
            
            self.curve_item.set_curve_path(path)
            
            if self.isSelected():
                pen = QPen(QBrush(QColor("#FF6B35")), 5.0)
                self.curve_item.set_pen(pen)
            elif self.is_hovered:
                pen = QPen(QBrush(QColor("#1D4ED8")), 4.0)
                self.curve_item.set_pen(pen)
            else:
                pen = QPen(QBrush(QColor("#3B82F6")), 3.0)
                self.curve_item.set_pen(pen)
            
        except Exception as e:
            print(f"Error updating curve: {str(e)}")
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the link.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return self.curve_item.boundingRect()
    
    def shape(self):
        """
        Define a wider shape for easier selection.
        
        Returns:
            QPainterPath: Shape path with wider selection area
        """
        if self.curve_item and not self.curve_item._LinkCurveItem__curve_path.isEmpty():
            stroke = QPainterPathStroker()
            stroke.setWidth(15)
            return stroke.createStroke(self.curve_item._LinkCurveItem__curve_path)
        return QPainterPath()
    
    def mousePressEvent(self, event):
        """
        Handle mouse press for selection.
        
        Args:
            event: QGraphicsSceneMouseEvent
        """
        if event.button() == Qt.LeftButton:
            self.setSelected(not self.isSelected())
            if self.isSelected() and self.scene():
                for item in self.scene().selectedItems():
                    if item != self and isinstance(item, (LinkItem, NodeItem)):
                        item.setSelected(False)
        elif event.button() == Qt.RightButton:
            self.show_context_menu(event.screenPos())
        super().mousePressEvent(event)
    
    def show_context_menu(self, global_pos):
        """
        Show context menu for link operations.
        
        Args:
            global_pos: Global screen position for menu
        """
        menu = QMenu()
        
        delete_action = menu.addAction("🗑️ Delete Connection")
        delete_action.triggered.connect(self.delete_connection)
        
        menu.exec(global_pos)
    
    def delete_connection(self):
        """
        Delete this connection.
        """
        if self.scene():
            self.scene().delete_link(self)
    
    def hoverEnterEvent(self, event):
        """
        Handle hover enter event.
        
        Args:
            event: QGraphicsSceneHoverEvent
        """
        self.is_hovered = True
        self.__update_curve()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """
        Handle hover leave event.
        
        Args:
            event: QGraphicsSceneHoverEvent
        """
        self.is_hovered = False
        self.__update_curve()
        super().hoverLeaveEvent(event)
    
    def itemChange(self, change, value):
        """
        Update appearance when selection changes.
        
        Args:
            change: Type of change occurring
            value: New value for the change
            
        Returns:
            Result of parent itemChange call
        """
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.__update_curve()
        return super().itemChange(change, value)
    
    def mouseDoubleClickEvent(self, event):
        """
        Handle double-click event.
        
        Args:
            event: QGraphicsSceneMouseEvent
        """
        self.activated.emit()
        super().mouseDoubleClickEvent(event)
        
class SampleSelectorDialog(QDialog):
    
    def __init__(self, parent, samples, current_selection=None, current_isotopes=None, current_sum_replicates=False, current_replicate_samples=None):
        """
        Initialize enhanced single sample dialog with table interface for better sample selection.
        
        Args:
            parent: Parent window
            samples: List of available sample names
            current_selection: Currently selected sample name
            current_isotopes: List of currently selected isotope dictionaries
            current_sum_replicates: Boolean indicating if replicate summing is enabled
            current_replicate_samples: List of sample names to sum together
        """
        super().__init__(parent)
        self.setWindowTitle("Single Sample Configuration")
        self.setModal(True)
        self.resize(1000, 700)
        self.setMinimumSize(800, 600) 
        
        self.parent_window = parent
        self.samples = samples
        self.current_isotopes = current_isotopes or []
        self.current_replicate_samples = current_replicate_samples or []
        
        self.sample_config = {}
        for sample in samples:
            if current_sum_replicates and sample in self.current_replicate_samples:
                self.sample_config[sample] = {'included': True}
            elif not current_sum_replicates and sample == current_selection:
                self.sample_config[sample] = {'included': True}
            else:
                self.sample_config[sample] = {'included': False}
        
        layout = QVBoxLayout(self)
        
        tab_widget = QTabWidget()
        
        sample_tab = self.create_sample_config_tab()
        tab_widget.addTab(sample_tab, "Sample Selection")
        
        isotope_tab = self.create_isotope_tab()
        tab_widget.addTab(isotope_tab, "Isotope Selection")
        
        layout.addWidget(tab_widget)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.update_preview()
    
    def create_sample_config_tab(self):
        """
        Create the sample configuration tab with table.
        
        Returns:
            QWidget: Configured sample configuration tab
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        header = QLabel("Configure Sample Selection")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)
        
        instructions = QLabel("""
        • Check samples you want to include in the analysis
        • Select one sample for individual analysis, or multiple samples to sum them together
        • Use the buttons below for quick selection operations
        """)
        instructions.setWordWrap(True)
        instructions.setStyleSheet("""
            QLabel {
                color: #6B7280;
                font-size: 11px;
                padding: 8px;
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 4px;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(instructions)
        
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        
        self.sample_table = QTableWidget()
        self.sample_table.setColumnCount(2)
        self.sample_table.setHorizontalHeaderLabels(["Include", "Sample Name"])
        self.sample_table.setRowCount(len(self.samples))
        
        self.sample_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sample_table.setSelectionMode(QTableWidget.MultiSelection)
        
        self.sample_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: white;
                gridline-color: #E5E7EB;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #F3F4F6;
            }
            QTableWidget::item:selected {
                background-color: #EBF4FF;
                color: #1D4ED8;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                padding: 12px;
                border: 1px solid #E5E7EB;
                font-weight: 600;
                color: #374151;
            }
        """)
        
        for row, sample in enumerate(self.samples):
            config = self.sample_config.get(sample, {'included': False})
            
            include_checkbox = QCheckBox()
            include_checkbox.setChecked(config.get('included', False))
            include_checkbox.stateChanged.connect(self.on_table_changed)
            self.sample_table.setCellWidget(row, 0, include_checkbox)
            
            sample_item = QTableWidgetItem(sample)
            sample_item.setFlags(sample_item.flags() & ~Qt.ItemIsEditable)
            sample_item.setBackground(QColor("#F9FAFB"))
            self.sample_table.setItem(row, 1, sample_item)
        
        header = self.sample_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.sample_table.setColumnWidth(0, 80)
        
        layout.addWidget(self.sample_table)
        
        button_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_samples)
        select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        button_layout.addWidget(select_all_btn)
        
        clear_all_btn = QPushButton("Clear All")
        clear_all_btn.clicked.connect(self.clear_all_samples)
        clear_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #DC2626;
            }
        """)
        button_layout.addWidget(clear_all_btn)
        
        select_table_rows_btn = QPushButton("Check Selected Rows")
        select_table_rows_btn.clicked.connect(self.check_selected_rows)
        select_table_rows_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        button_layout.addWidget(select_table_rows_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.preview_label = QLabel()
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #F0F9FF;
                border: 1px solid #0EA5E9;
                border-radius: 4px;
                padding: 12px;
                color: #0C4A6E;
                font-weight: 500;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.preview_label)
        
        return widget
    
    def create_isotope_tab(self):
        """
        Create the isotope selection tab.
        
        Returns:
            QWidget: Configured isotope selection tab
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        isotope_header = QLabel("Select Isotopes to Include")
        isotope_header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(isotope_header)
        
        from results.results_periodic import CompactPeriodicTableWidget
        self.periodic_table = CompactPeriodicTableWidget(self)
        self.periodic_table.setMaximumSize(850, 350)
        
        if self.parent_window and hasattr(self.parent_window, 'selected_isotopes'):
            available_element_masses = []
            for element, isotopes in self.parent_window.selected_isotopes.items():
                for isotope in isotopes:
                    available_element_masses.append((element, isotope))
            
            if available_element_masses:
                self.periodic_table.update_available_masses(available_element_masses)
                
        self.set_periodic_table_selections()
        
        layout.addWidget(self.periodic_table)
        
        controls = QHBoxLayout()
        select_all_isotopes_btn = QPushButton("Select All Available")
        select_all_isotopes_btn.clicked.connect(self.select_all_isotopes)
        controls.addWidget(select_all_isotopes_btn)
        
        clear_isotopes_btn = QPushButton("Clear Selection")
        clear_isotopes_btn.clicked.connect(self.clear_isotope_selection)
        controls.addWidget(clear_isotopes_btn)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        return widget
    
    def on_table_changed(self):
        """
        Handle table changes.
        """
        self.update_sample_config_from_table()
        self.update_preview()
    
    def update_sample_config_from_table(self):
        """
        Update internal config from table state.
        """
        for row in range(self.sample_table.rowCount()):
            sample = self.samples[row]
            
            include_checkbox = self.sample_table.cellWidget(row, 0)
            included = include_checkbox.isChecked()
            
            self.sample_config[sample] = {'included': included}
    
    def update_preview(self):
        """
        Update the preview of what will be processed.
        """
        self.update_sample_config_from_table()
        
        included_samples = [s for s, config in self.sample_config.items() if config['included']]
        
        if not included_samples:
            self.preview_label.setText("Preview: No samples selected")
            return
        
        if len(included_samples) == 1:
            preview_text = f"Preview: Individual analysis of '{included_samples[0]}'"
        else:
            preview_text = f"Preview: Combined analysis of {len(included_samples)} samples:\n"
            preview_text += f"• Samples will be summed: {', '.join(included_samples)}"
        
        self.preview_label.setText(preview_text)
    
    def select_all_samples(self):
        """
        Select all samples.
        """
        for row in range(self.sample_table.rowCount()):
            checkbox = self.sample_table.cellWidget(row, 0)
            checkbox.setChecked(True)
    
    def clear_all_samples(self):
        """
        Clear all sample selections.
        """
        for row in range(self.sample_table.rowCount()):
            checkbox = self.sample_table.cellWidget(row, 0)
            checkbox.setChecked(False)
    
    def check_selected_rows(self):
        """
        Check the include checkbox for all selected table rows.
        """
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Check Rows", "Please select rows in the table first.")
            return
        
        for row in selected_rows:
            checkbox = self.sample_table.cellWidget(row, 0)
            checkbox.setChecked(True)
    
    def get_selected_rows(self):
        """
        Get list of selected row indices.
        
        Returns:
            list: Sorted list of selected row indices
        """
        selected_rows = set()
        for item in self.sample_table.selectedItems():
            selected_rows.add(item.row())
        return sorted(list(selected_rows))
    
    def set_periodic_table_selections(self):
        """
        Set current isotope selections on periodic table.
        """
        if not self.current_isotopes:
            return
            
        selected_isotopes = {}
        for item in self.current_isotopes:
            symbol = item['symbol']
            mass = item['mass']
            
            if symbol not in selected_isotopes:
                selected_isotopes[symbol] = []
            selected_isotopes[symbol].append(mass)
        
        for symbol, masses in selected_isotopes.items():
            if symbol in self.periodic_table.buttons:
                button = self.periodic_table.buttons[symbol]
                if button.isotope_display:
                    for mass in masses:
                        button.isotope_display.select_preferred_isotope(mass)
        
    def select_all_isotopes(self):
        """
        Select all available isotopes.
        """
        if self.parent_window and hasattr(self.parent_window, 'selected_isotopes'):
            for element, isotopes in self.parent_window.selected_isotopes.items():
                if element in self.periodic_table.buttons:
                    button = self.periodic_table.buttons[element]
                    if button.isotope_display:
                        for isotope in isotopes:
                            button.isotope_display.select_preferred_isotope(isotope)
    
    def clear_isotope_selection(self):
        """
        Clear all isotope selections.
        """
        self.periodic_table.clear_all_selections()
    
    def get_selection(self):
        """
        Get selection in the expected format.
        
        Returns:
            tuple: (selected_sample(s), selected_isotopes, sum_replicates_flag)
                   Single sample string if one selected
                   List of samples if multiple selected
                   None if no selection
        """
        self.update_sample_config_from_table()
        
        selected_samples = [sample for sample, config in self.sample_config.items() if config['included']]
        
        selected_isotopes = []
        if hasattr(self, 'periodic_table'):
            for symbol, button in self.periodic_table.buttons.items():
                if button.isotope_display and button.isotope_display.selected_isotopes:
                    for sym, mass in button.isotope_display.selected_isotopes:
                        element_key = f"{sym}-{mass:.4f}"
                        display_label = self.parent_window.get_formatted_label(element_key)
                        selected_isotopes.append({
                            'symbol': sym,
                            'mass': mass,
                            'key': element_key,
                            'label': display_label
                        })
        
        if len(selected_samples) == 0:
            return None, selected_isotopes, False
        elif len(selected_samples) == 1:
            return selected_samples[0], selected_isotopes, False
        else:
            return selected_samples, selected_isotopes, True
    

class MultipleSampleSelectorDialog(QDialog):
    
    def __init__(self, parent, samples, current_selection=None, current_isotopes=None, current_sample_config=None):
        """
        Initialize enhanced dialog with table for granular sample summing control with bulk operations.
        
        Args:
            parent: Parent window
            samples: List of available sample names
            current_selection: List of currently selected sample names
            current_isotopes: List of currently selected isotope dictionaries
            current_sample_config: Dictionary mapping samples to their configuration
        """
        super().__init__(parent)
        self.setWindowTitle("Multi-Sample Configuration with Summing Control")
        self.setModal(True)
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)
        
        self.parent_window = parent
        self.samples = samples
        self.current_isotopes = current_isotopes or []
        
        self.clipboard_group_name = ""
        
        if current_sample_config:
            self.current_sample_config = current_sample_config.copy()
        else:
            self.current_sample_config = {}
            current_selection = current_selection or []
            
            for sample in samples:
                self.current_sample_config[sample] = {
                    'included': sample in current_selection,
                    'sum_group': '',
                    'custom_name': sample
                }
        
        layout = QVBoxLayout(self)
        
        tab_widget = QTabWidget()
        
        sample_tab = self.create_sample_config_tab()
        tab_widget.addTab(sample_tab, "Sample Configuration")
        
        isotope_tab = self.create_isotope_tab()
        tab_widget.addTab(isotope_tab, "Isotope Selection")
        
        layout.addWidget(tab_widget)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.update_preview()
    
    def create_sample_config_tab(self):
        """
        Create the sample configuration tab with table and enhanced bulk operations.
        
        Returns:
            QWidget: Configured sample configuration tab
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        header = QLabel("Configure Sample Processing")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)
        
        instructions = QLabel("""
        • Check 'Include' to use a sample in the analysis
        • Enter the same 'Sum Group' name for samples you want to combine
        • Leave 'Sum Group' empty to keep samples separate
        • 'Display Name' will be shown in results (auto-generated for sum groups)
        • Use bulk operations below for faster setup
        """)
        instructions.setWordWrap(True)
        instructions.setStyleSheet("""
            QLabel {
                color: #6B7280;
                font-size: 11px;
                padding: 8px;
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 4px;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(instructions)
        
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        
        self.sample_table = QTableWidget()
        self.sample_table.setColumnCount(4)
        self.sample_table.setHorizontalHeaderLabels(["Include", "Sample Name", "Sum Group", "Display Name"])
        self.sample_table.setRowCount(len(self.samples))
        
        self.sample_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sample_table.setSelectionMode(QTableWidget.MultiSelection)
        
        self.sample_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: white;
                gridline-color: #E5E7EB;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #F3F4F6;
            }
            QTableWidget::item:selected {
                background-color: #EBF4FF;
                color: #1D4ED8;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                padding: 10px;
                border: 1px solid #E5E7EB;
                font-weight: 600;
                color: #374151;
            }
        """)
        
        for row, sample in enumerate(self.samples):
            config = self.current_sample_config.get(sample, {
                'included': False,
                'sum_group': '',
                'custom_name': sample
            })
            
            include_checkbox = QCheckBox()
            include_checkbox.setChecked(config.get('included', False))
            include_checkbox.stateChanged.connect(self.on_table_changed)
            self.sample_table.setCellWidget(row, 0, include_checkbox)
            
            sample_item = QTableWidgetItem(sample)
            sample_item.setFlags(sample_item.flags() & ~Qt.ItemIsEditable)
            sample_item.setBackground(QColor("#F9FAFB"))
            self.sample_table.setItem(row, 1, sample_item)
            
            sum_group_item = QTableWidgetItem(config.get('sum_group', ''))
            self.sample_table.setItem(row, 2, sum_group_item)
            
            display_name_item = QTableWidgetItem(config.get('custom_name', sample))
            self.sample_table.setItem(row, 3, display_name_item)
        
        self.sample_table.itemChanged.connect(self.on_table_changed)
        
        header = self.sample_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.sample_table.setColumnWidth(0, 80)
        
        layout.addWidget(self.sample_table)
        
        button_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_samples)
        select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        button_layout.addWidget(select_all_btn)
        
        clear_all_btn = QPushButton("Clear All")
        clear_all_btn.clicked.connect(self.clear_all_samples)
        clear_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #DC2626;
            }
        """)
        button_layout.addWidget(clear_all_btn)
        
        group_selected_btn = QPushButton("Group Selected")
        group_selected_btn.clicked.connect(self.group_selected_samples)
        group_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        button_layout.addWidget(group_selected_btn)
        
        clear_groups_btn = QPushButton("Clear Groups")
        clear_groups_btn.clicked.connect(self.clear_all_groups)
        clear_groups_btn.setStyleSheet("""
            QPushButton {
                background-color: #F59E0B;
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #D97706;
            }
        """)
        button_layout.addWidget(clear_groups_btn)
        
        copy_group_btn = QPushButton("Copy Group")
        copy_group_btn.clicked.connect(self.copy_group_name)
        copy_group_btn.setStyleSheet("""
            QPushButton {
                background-color: #8B5CF6;
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #7C3AED;
            }
        """)
        button_layout.addWidget(copy_group_btn)
        
        paste_group_btn = QPushButton("Paste to Selected")
        paste_group_btn.clicked.connect(self.paste_group_name)
        paste_group_btn.setStyleSheet("""
            QPushButton {
                background-color: #EC4899;
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #DB2777;
            }
        """)
        button_layout.addWidget(paste_group_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        bulk_layout = QHBoxLayout()
        
        bulk_layout.addWidget(QLabel("Quick Group:"))
        
        self.bulk_group_input = QLineEdit()
        self.bulk_group_input.setPlaceholderText("Enter group name and press Apply to Selected")
        self.bulk_group_input.setStyleSheet("""
            QLineEdit {
                padding: 6px 12px;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 2px solid #3B82F6;
            }
        """)
        bulk_layout.addWidget(self.bulk_group_input)
        
        apply_bulk_btn = QPushButton("Apply to Selected")
        apply_bulk_btn.clicked.connect(self.apply_bulk_group)
        apply_bulk_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        bulk_layout.addWidget(apply_bulk_btn)
        
        layout.addLayout(bulk_layout)
        
        self.clipboard_status = QLabel("Clipboard: Empty")
        self.clipboard_status.setStyleSheet("""
            QLabel {
                color: #6B7280;
                font-size: 10px;
                font-style: italic;
                padding: 4px;
            }
        """)
        layout.addWidget(self.clipboard_status)
        
        self.preview_label = QLabel()
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #F0F9FF;
                border: 1px solid #0EA5E9;
                border-radius: 4px;
                padding: 10px;
                color: #0C4A6E;
                font-weight: 500;
            }
        """)
        layout.addWidget(self.preview_label)
        
        return widget
    
    def copy_group_name(self):
        """
        Copy the group name from the first selected row.
        """
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Copy Group", "Please select at least one row to copy the group name from.")
            return
        
        first_row = selected_rows[0]
        sum_group_item = self.sample_table.item(first_row, 2)
        group_name = sum_group_item.text().strip() if sum_group_item else ""
        
        if not group_name:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Copy Group", "The selected sample has no group name to copy.")
            return
        
        self.clipboard_group_name = group_name
        self.clipboard_status.setText(f"Clipboard: '{group_name}'")
        print(f"📋 Copied group name: '{group_name}'")
    
    def paste_group_name(self):
        """
        Paste the copied group name to all selected rows.
        """
        if not self.clipboard_group_name:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Paste Group", "Clipboard is empty. Copy a group name first.")
            return
        
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Paste Group", "Please select rows to paste the group name to.")
            return
        
        for row in selected_rows:
            sum_group_item = self.sample_table.item(row, 2)
            sum_group_item.setText(self.clipboard_group_name)
        
        print(f"Pasted group name '{self.clipboard_group_name}' to {len(selected_rows)} samples")
    
    def apply_bulk_group(self):
        """
        Apply the group name from the input field to selected samples.
        """
        group_name = self.bulk_group_input.text().strip()
        if not group_name:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Bulk Group", "Please enter a group name.")
            return
        
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Bulk Group", "Please select rows to apply the group name to.")
            return
        
        for row in selected_rows:
            sum_group_item = self.sample_table.item(row, 2)
            sum_group_item.setText(group_name)
        
        self.bulk_group_input.clear()
        print(f"Applied group name '{group_name}' to {len(selected_rows)} samples")
    
    def get_selected_rows(self):
        """
        Get list of selected row indices.
        
        Returns:
            list: Sorted list of selected row indices
        """
        selected_rows = set()
        for item in self.sample_table.selectedItems():
            selected_rows.add(item.row())
        return sorted(list(selected_rows))
    
    def create_isotope_tab(self):
        """
        Create the isotope selection tab.
        
        Returns:
            QWidget: Configured isotope selection tab
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        isotope_header = QLabel("Select Isotopes to Include")
        isotope_header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(isotope_header)
        
        from results.results_periodic import CompactPeriodicTableWidget
        self.periodic_table = CompactPeriodicTableWidget(self)
        self.periodic_table.setMaximumSize(850, 350)
        
        if self.parent_window and hasattr(self.parent_window, 'selected_isotopes'):
            available_element_masses = []
            for element, isotopes in self.parent_window.selected_isotopes.items():
                for isotope in isotopes:
                    available_element_masses.append((element, isotope))
            
            if available_element_masses:
                self.periodic_table.update_available_masses(available_element_masses)
        
        self.set_periodic_table_selections()
        layout.addWidget(self.periodic_table)
        
        controls = QHBoxLayout()
        select_all_isotopes_btn = QPushButton("Select All Available")
        select_all_isotopes_btn.clicked.connect(self.select_all_isotopes)
        controls.addWidget(select_all_isotopes_btn)
        
        clear_isotopes_btn = QPushButton("Clear Selection")
        clear_isotopes_btn.clicked.connect(self.clear_isotope_selection)
        controls.addWidget(clear_isotopes_btn)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        return widget
    
    def on_table_changed(self):
        """
        Handle table changes.
        """
        self.update_sample_config_from_table()
        self.update_preview()
    
    def update_sample_config_from_table(self):
        """
        Update internal config from table state.
        """
        for row in range(self.sample_table.rowCount()):
            sample = self.samples[row]
            
            include_checkbox = self.sample_table.cellWidget(row, 0)
            included = include_checkbox.isChecked()
            
            sum_group_item = self.sample_table.item(row, 2)
            sum_group = sum_group_item.text().strip() if sum_group_item else ""
            
            display_name_item = self.sample_table.item(row, 3)
            display_name = display_name_item.text().strip() if display_name_item else sample
            
            self.current_sample_config[sample] = {
                'included': included,
                'sum_group': sum_group,
                'custom_name': display_name if display_name else sample
            }
    
    def update_preview(self):
        """
        Update the preview of what will be processed.
        """
        self.update_sample_config_from_table()
        
        included_samples = [s for s, config in self.current_sample_config.items() if config['included']]
        
        if not included_samples:
            self.preview_label.setText("Preview: No samples selected")
            return
        
        individual_samples = []
        sum_groups = {}
        
        for sample in included_samples:
            config = self.current_sample_config[sample]
            sum_group = config['sum_group']
            
            if not sum_group:
                individual_samples.append(config['custom_name'])
            else:
                if sum_group not in sum_groups:
                    sum_groups[sum_group] = []
                sum_groups[sum_group].append(sample)
        
        preview_parts = []
        
        for sample_name in individual_samples:
            preview_parts.append(f"• {sample_name} (individual)")
        
        for group_name, group_samples in sum_groups.items():
            preview_parts.append(f"• {group_name} (sum of: {', '.join(group_samples)})")
        
        if preview_parts:
            preview_text = f"Preview: Will process {len(preview_parts)} data source(s):\n" + "\n".join(preview_parts)
        else:
            preview_text = "Preview: No samples configured"
        
        self.preview_label.setText(preview_text)
    
    def select_all_samples(self):
        """
        Select all samples.
        """
        for row in range(self.sample_table.rowCount()):
            checkbox = self.sample_table.cellWidget(row, 0)
            checkbox.setChecked(True)
    
    def clear_all_samples(self):
        """
        Clear all sample selections.
        """
        for row in range(self.sample_table.rowCount()):
            checkbox = self.sample_table.cellWidget(row, 0)
            checkbox.setChecked(False)
    
    def group_selected_samples(self):
        """
        Group selected samples together.
        """
        from PySide6.QtWidgets import QInputDialog
        
        selected_rows = self.get_selected_rows()
        
        if len(selected_rows) < 2:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Group Samples", "Please select at least 2 rows in the table to group together.")
            return
        
        group_name, ok = QInputDialog.getText(
            self, "Group Name", 
            "Enter a name for this sum group:",
            text=f"Group_{len(set(self.sample_table.item(row, 2).text() for row in selected_rows if self.sample_table.item(row, 2).text())) + 1}"
        )
        
        if ok and group_name.strip():
            for row in selected_rows:
                sum_group_item = self.sample_table.item(row, 2)
                sum_group_item.setText(group_name.strip())
                checkbox = self.sample_table.cellWidget(row, 0)
                checkbox.setChecked(True)
    
    def clear_all_groups(self):
        """
        Clear all sum groups.
        """
        for row in range(self.sample_table.rowCount()):
            sum_group_item = self.sample_table.item(row, 2)
            sum_group_item.setText("")
    
    def set_periodic_table_selections(self):
        """
        Set current isotope selections on periodic table.
        """
        if not self.current_isotopes:
            return
            
        selected_isotopes = {}
        for item in self.current_isotopes:
            symbol = item['symbol']
            mass = item['mass']
            
            if symbol not in selected_isotopes:
                selected_isotopes[symbol] = []
            selected_isotopes[symbol].append(mass)
        
        for symbol, masses in selected_isotopes.items():
            if symbol in self.periodic_table.buttons:
                button = self.periodic_table.buttons[symbol]
                if button.isotope_display:
                    for mass in masses:
                        button.isotope_display.select_preferred_isotope(mass)
    
    def select_all_isotopes(self):
        """
        Select all available isotopes.
        """
        if self.parent_window and hasattr(self.parent_window, 'selected_isotopes'):
            for element, isotopes in self.parent_window.selected_isotopes.items():
                if element in self.periodic_table.buttons:
                    button = self.periodic_table.buttons[element]
                    if button.isotope_display:
                        for isotope in isotopes:
                            button.isotope_display.select_preferred_isotope(isotope)
    
    def clear_isotope_selection(self):
        """
        Clear all isotope selections.
        """
        self.periodic_table.clear_all_selections()
    
    def get_selection(self):
        """
        Get the final configuration.
        
        Returns:
            tuple: (selected_samples, selected_isotopes, sample_config)
        """
        self.update_sample_config_from_table()
        
        selected_samples = [sample for sample, config in self.current_sample_config.items() if config['included']]
        
        selected_isotopes = []
        if hasattr(self, 'periodic_table'):
            for symbol, button in self.periodic_table.buttons.items():
                if button.isotope_display and button.isotope_display.selected_isotopes:
                    for sym, mass in button.isotope_display.selected_isotopes:
                        element_key = f"{sym}-{mass:.4f}"
                        display_label = self.parent_window.get_formatted_label(element_key)
                        selected_isotopes.append({
                            'symbol': sym,
                            'mass': mass,
                            'key': element_key,
                            'label': display_label
                        })
        
        return selected_samples, selected_isotopes, self.current_sample_config

class MultipleSampleSelectorNode(WorkflowNode):
    
    def __init__(self, parent_window=None):
        """
        Args:
            parent_window: MainWindow instance or None
        
        Returns:
            None
        """
        super().__init__("Multiple Sample Selector", "multiple_sample_selector")
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
        """
        Args:
            input_data: dict with data from upstream node, or None
        
        Returns:
            None
        """
        self.input_data = input_data
        
        if input_data:
            data_type = input_data.get('type', 'unknown')
            
            if data_type == 'batch_sample_list':
                self.batch_samples = input_data.get('sample_names', [])
                self.batch_particle_data = input_data.get('particle_data', [])
                self.batch_sample_data = input_data.get('data', {})
                self.batch_available_isotopes = input_data.get('available_isotopes', {})
                print(f"Multiple Sample received batch with {len(self.batch_samples)} samples")
            else:
                sample_count = len(input_data.get('sample_names', []))
                print(f"Multiple sample received {data_type} data with {sample_count} samples")
        
    def get_output_data(self):
        """
        Args:
            None
        
        Returns:
            dict: Data dictionary with type 'multiple_sample_data', or None
        """
        if self.input_data and self.input_data.get('type') != 'batch_sample_list':
            return self.input_data
            
        if not self.sample_config:
            included_samples = self.selected_samples
        else:
            included_samples = [sample for sample, config in self.sample_config.items() if config.get('included', False)]
        
        if not included_samples:
            print("No samples selected in multiple sample selector")
            return None
        
        combined_particle_data = []
        total_original_particles = 0
        final_sample_names = []
        
        if self.sample_config:
            individual_samples = {}
            sum_groups = {}
            
            for sample in included_samples:
                config = self.sample_config.get(sample, {'sum_group': '', 'custom_name': sample})
                sum_group = config.get('sum_group', '')
                
                if not sum_group:
                    individual_samples[sample] = config
                    final_sample_names.append(sample)
                else:
                    if sum_group not in sum_groups:
                        sum_groups[sum_group] = []
                    sum_groups[sum_group].append(sample)
            
            for group_name in sum_groups.keys():
                final_sample_names.append(group_name)
            
            for sample, config in individual_samples.items():
                particles_added = self._process_individual_sample(sample, sample, combined_particle_data)
                total_original_particles += particles_added
            
            for group_name, group_samples in sum_groups.items():
                particles_added = self._process_sum_group(group_name, group_samples, combined_particle_data)
                total_original_particles += particles_added
        else:
            final_sample_names = included_samples
            for sample in included_samples:
                particles_added = self._process_individual_sample(sample, sample, combined_particle_data)
                total_original_particles += particles_added
        
        if not combined_particle_data:
            print("No particle data after filtering")
            return None
        
        combined_sample_data = {}
        all_data_types = {}
        
        if self.batch_sample_data:
            for sample in included_samples:
                if sample in self.batch_sample_data:
                    sample_data = self.batch_sample_data[sample]
                    combined_sample_data[sample] = sample_data
                    
                    for data_type, data_values in sample_data.items():
                        if isinstance(data_values, dict):
                            if data_type not in all_data_types:
                                all_data_types[data_type] = {}
                            
                            for element, value in data_values.items():
                                if element not in all_data_types[data_type]:
                                    all_data_types[data_type][element] = []
                                all_data_types[data_type][element].append(value)
        else:
            for sample in included_samples:
                if hasattr(self.parent_window, 'data_by_sample'):
                    sample_data = self.parent_window.data_by_sample.get(sample)
                    if sample_data:
                        combined_sample_data[sample] = sample_data
                        
                        for data_type, data_values in sample_data.items():
                            if isinstance(data_values, dict):
                                if data_type not in all_data_types:
                                    all_data_types[data_type] = {}
                                
                                for element, value in data_values.items():
                                    if element not in all_data_types[data_type]:
                                        all_data_types[data_type][element] = []
                                    all_data_types[data_type][element].append(value)
        
        data = {
            'type': 'multiple_sample_data',
            'sample_names': final_sample_names,
            'original_sample_names': included_samples,
            'sample_config': self.sample_config if self.sample_config else None,
            'data_types': all_data_types,
            'data': combined_sample_data,
            'particle_data': combined_particle_data,
            'selected_isotopes': self.selected_isotopes,
            'total_particles': total_original_particles,
            'filtered_particles': len(combined_particle_data),
            'sum_replicates': self.sum_replicates,
            'parent_window': self.parent_window
        }
        
        print(f"Multiple Sample Selector: {len(final_sample_names)} final samples ({final_sample_names}), "
              f"ALL data types ({list(all_data_types.keys())}), {len(self.selected_isotopes)} isotopes, "
              f"{len(combined_particle_data)}/{total_original_particles} particles")
        
        return data
    
    def _process_individual_sample(self, sample_name, source_sample_name, combined_particle_data):
        """
        Args:
            sample_name: str, sample name to process
            source_sample_name: str, display name for particle source
            combined_particle_data: list to append particles to
        
        Returns:
            int: Original particle count
        """
        original_count = 0
        
        if self.batch_particle_data is not None:
            particle_data = [p for p in self.batch_particle_data if p.get('source_sample') == sample_name]
            original_count = len(particle_data)
            
            filtered_particles = self.apply_isotope_filter(particle_data)
            
            for particle in filtered_particles:
                particle['source_sample'] = source_sample_name
                if 'original_sample' not in particle:
                    particle['original_sample'] = sample_name
            
            combined_particle_data.extend(filtered_particles)
        elif (hasattr(self.parent_window, 'sample_particle_data') and 
            sample_name in self.parent_window.sample_particle_data):
            
            particle_data = self.parent_window.sample_particle_data[sample_name]
            original_count = len(particle_data)
            
            filtered_particles = self.apply_isotope_filter(particle_data)
            
            for particle in filtered_particles:
                particle['source_sample'] = source_sample_name
                particle['original_sample'] = sample_name
            
            combined_particle_data.extend(filtered_particles)
        
        return original_count
    
    def _process_sum_group(self, group_name, group_samples, combined_particle_data):
        """
        Args:
            group_name: str, name for the summed group
            group_samples: list of str, sample names in group
            combined_particle_data: list to append particles to
        
        Returns:
            int: Total original particle count
        """
        total_original_particles = 0
        group_particles = []
        
        for sample in group_samples:
            if self.batch_particle_data is not None:
                particle_data = [p for p in self.batch_particle_data if p.get('source_sample') == sample]
                total_original_particles += len(particle_data)
                
                filtered_particles = self.apply_isotope_filter(particle_data)
                
                for particle in filtered_particles:
                    particle['source_sample'] = group_name
                    if 'original_sample' not in particle:
                        particle['original_sample'] = sample
                    particle['sum_group'] = group_name
                    particle['is_summed'] = True
                
                group_particles.extend(filtered_particles)
            elif (hasattr(self.parent_window, 'sample_particle_data') and 
                sample in self.parent_window.sample_particle_data):
                
                particle_data = self.parent_window.sample_particle_data[sample]
                total_original_particles += len(particle_data)
                
                filtered_particles = self.apply_isotope_filter(particle_data)
                
                for particle in filtered_particles:
                    particle['source_sample'] = group_name
                    particle['original_sample'] = sample
                    particle['sum_group'] = group_name
                    particle['is_summed'] = True
                
                group_particles.extend(filtered_particles)
        
        combined_particle_data.extend(group_particles)
        print(f"Processed sum group '{group_name}': {len(group_particles)} particles from {len(group_samples)} samples")
        return total_original_particles
    
    def apply_isotope_filter(self, particle_data):
        """
        Args:
            particle_data: list of particle dictionaries
        
        Returns:
            list: Filtered particle list
        """
        if not self.selected_isotopes:
            return particle_data
        
        selected_labels = [iso['label'] for iso in self.selected_isotopes]
        
        filtered_particles = []
        for particle in particle_data:
            has_selected_elements = False
            for element_name, count in particle.get('elements', {}).items():
                if element_name in selected_labels and count > 0:
                    has_selected_elements = True
                    break
            
            if has_selected_elements:
                filtered_particle = particle.copy()
                
                data_fields = [
                    'elements',
                    'element_mass_fg', 
                    'particle_mass_fg',
                    'element_moles_fmol',
                    'particle_moles_fmol', 
                    'element_diameter_nm',
                    'particle_diameter_nm'
                ]
                
                for field in data_fields:
                    if field in particle:
                        filtered_field = {}
                        for element_name, value in particle[field].items():
                            if element_name in selected_labels:
                                if field == 'elements' and value > 0:
                                    filtered_field[element_name] = value
                                elif field != 'elements' and value > 0 and not np.isnan(value):
                                    filtered_field[element_name] = value
                        
                        filtered_particle[field] = filtered_field
                
                filtered_particles.append(filtered_particle)
        
        return filtered_particles
    
    def configure(self, parent_window):
        """
        Args:
            parent_window: MainWindow instance
        
        Returns:
            bool: True if configuration accepted, False otherwise
        """
        if self.batch_samples:
            samples = self.batch_samples
            print(f"Using {len(samples)} samples from batch input")
        else:
            samples = list(parent_window.sample_to_folder_map.keys()) if hasattr(parent_window, 'sample_to_folder_map') else []
        
        dialog = MultipleSampleSelectorDialog(
            parent_window,
            samples,
            self.selected_samples,
            self.selected_isotopes,
            self.sample_config
        )
        
        if dialog.exec() == QDialog.Accepted:
            selected_samples, selected_isotopes, sample_config = dialog.get_selection()
            
            if selected_samples:
                self.selected_samples = selected_samples
                self.selected_isotopes = selected_isotopes
                self.sample_config = sample_config
                
                self.configuration_changed.emit()
                return True
        return False

class MultipleSampleSelectorNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Args:
            workflow_node: MultipleSampleSelectorNode instance
            parent_window: MainWindow instance or None
        
        Returns:
            None
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        
        self.status_label = QLabel("Not configured")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #6B7280;
                padding: 4px 6px;
                background-color: rgba(249, 250, 251, 200);
                border-radius: 4px;
                border: 1px solid #E5E7EB;
            }
        """)
        self.status_label.setAlignment(Qt.AlignCenter)
        
        self.status_proxy = QGraphicsProxyWidget(self)
        self.status_proxy.setWidget(self.status_label)
        self.status_proxy.setPos(8, 40)
        self.status_proxy.resize(self.width - 16, 50)
        
        workflow_node.configuration_changed.connect(self.update_status)
        workflow_node.configuration_changed.connect(self.trigger_data_flow)
        self.update_status()
    
    def update_status(self):
        """
        Args:
            None
        
        Returns:
            None
        """
        if self.workflow_node.input_data:
            batch_samples = len(self.workflow_node.input_data.get('sample_names', []))
            self.status_label.setText(f"Batch Input\n{batch_samples} samples")
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #7C3AED;
                    padding: 4px 6px;
                    background-color: rgba(237, 233, 254, 200);
                    border-radius: 4px;
                    border: 1px solid #A78BFA;
                }
            """)
            return
            
        if not self.workflow_node.selected_samples:
            self.status_label.setText("⚙️ Not configured\n(Double-click to setup)")
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #DC2626;
                    padding: 4px 6px;
                    background-color: rgba(254, 242, 242, 200);
                    border-radius: 4px;
                    border: 1px solid #EF4444;
                }
            """)
            return
        
        sample_count = len(self.workflow_node.selected_samples)
        isotope_count = len(self.workflow_node.selected_isotopes)
        
        if isotope_count == 0:
            isotope_text = "All isotopes"
        else:
            isotope_text = f"{isotope_count} isotopes"
        
        if self.workflow_node.sample_config:
            individual_count = 0
            sum_groups = set()
            
            for sample in self.workflow_node.selected_samples:
                config = self.workflow_node.sample_config.get(sample, {})
                sum_group = config.get('sum_group', '')
                
                if not sum_group:
                    individual_count += 1
                else:
                    sum_groups.add(sum_group)
            
            total_sources = individual_count + len(sum_groups)
            
            status_parts = []
            status_parts.append(f"✓ {total_sources} data source(s)")
            
            if individual_count > 0 and len(sum_groups) > 0:
                status_parts.append(f"({individual_count} individual, {len(sum_groups)} summed)")
            elif len(sum_groups) > 0:
                status_parts.append(f"({len(sum_groups)} summed groups)")
            
            status_parts.append(isotope_text)
            status_text = "\n".join(status_parts)
        else:
            if sample_count == 1:
                status_text = f"✓ 1 sample\n{isotope_text}"
            else:
                status_text = f"✓ {sample_count} samples\n{isotope_text}"
        
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #059669;
                padding: 4px 6px;
                background-color: rgba(236, 253, 245, 200);
                border-radius: 4px;
                border: 1px solid #10B981;
            }
        """)
    
    def trigger_data_flow(self):
        """
        Args:
            None
        
        Returns:
            None
        """
        scene = self.scene()
        if scene:
            for link in scene.workflow_links:
                if link.source_node == self.workflow_node:
                    print(f"Triggering data flow for multiple samples: {self.workflow_node.selected_samples}")
                    scene._trigger_data_flow(link)
            
            for node in scene.workflow_nodes:
                if hasattr(node, 'update_plot'):
                    node.update_plot()
    
    def configure_node(self):
        """
        Args:
            None
        
        Returns:
            None
        """
        if self.parent_window:
            self.workflow_node.configure(self.parent_window)
    
    def paint(self, painter, option, widget=None):
        """
        Args:
            painter: QPainter instance
            option: QStyleOptionGraphicsItem
            widget: QWidget or None
        
        Returns:
            None
        """
        def draw_enhanced_multi_sample_icon(painter, icon_rect):
            for i in range(3):
                offset = i * 2
                db_rect = QRectF(icon_rect.left() + offset, icon_rect.top() + offset, 
                               icon_rect.width() - offset * 2, icon_rect.height() - offset * 2)
                painter.drawRoundedRect(db_rect, 2, 2)
                
                if i == 2:
                    painter.drawLine(db_rect.left() + 2, db_rect.top() + 4, 
                                   db_rect.right() - 2, db_rect.top() + 4)
                    painter.drawLine(db_rect.left() + 2, db_rect.top() + 7, 
                                   db_rect.right() - 2, db_rect.top() + 7)
            
            sigma_x = icon_rect.right() - 6
            sigma_y = icon_rect.bottom() - 8
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            font = QFont("Arial", 14, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(QPointF(sigma_x, sigma_y), "Σ")
        
        self.paint_base_node(painter, 147, 51, 234, 126, 34, 206, draw_enhanced_multi_sample_icon, "Multi-Sample+")       
class SampleSelectorNode(WorkflowNode):
    
    def __init__(self, parent_window=None):
        """
        Args:
            parent_window: MainWindow instance or None
        
        Returns:
            None
        """
        super().__init__("Single sample", "sample_selector")
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
        """
        Args:
            input_data: dict with data from upstream node, or None
        
        Returns:
            None
        """
        self.input_data = input_data
        
        if input_data:
            data_type = input_data.get('type', 'unknown')
            
            if data_type == 'batch_sample_list':
                self.batch_samples = input_data.get('sample_names', [])
                self.batch_particle_data = input_data.get('particle_data', [])
                self.batch_sample_data = input_data.get('data', {})
                self.batch_available_isotopes = input_data.get('available_isotopes', {})
                print(f"Single Sample received batch with {len(self.batch_samples)} samples")
            else:
                sample_count = len(input_data.get('sample_names', []))
                print(f"Single sample received {data_type} data with {sample_count} samples")
        
    def get_output_data(self):
        """
        Args:
            None
        
        Returns:
            dict: Data dictionary with particle data, or None
        """
        if self.input_data and self.input_data.get('type') != 'batch_sample_list':
            return self.input_data
            
        if not self.selected_sample and not (self.sum_replicates and self.replicate_samples):
            return None
        
        particle_data = self.get_particle_data_with_replicates()
            
        if not particle_data:
            return None
        
        filtered_particles = self.apply_isotope_filter(particle_data)
        
        if self.sum_replicates and self.replicate_samples:
            display_name = f"Summed: {', '.join(self.replicate_samples)}"
        else:
            display_name = self.selected_sample
        
        all_data_types = {}
        sample_data = self.get_sample_data()
        
        if sample_data:
            for data_type, data_values in sample_data.items():
                if isinstance(data_values, dict):
                    all_data_types[data_type] = data_values
        
        data = {
            'type': 'sample_data',
            'sample_name': display_name,
            'data_types': all_data_types, 
            'data': sample_data, 
            'particle_data': filtered_particles,
            'selected_isotopes': self.selected_isotopes,
            'total_particles': len(particle_data),
            'filtered_particles': len(filtered_particles),
            'sum_replicates': self.sum_replicates,
            'replicate_samples': self.replicate_samples,
            'parent_window': self.parent_window
        }
        
        print(f"Single Sample: {display_name}, ALL data types ({list(all_data_types.keys())}), "
            f"{len(self.selected_isotopes)} isotopes, {len(filtered_particles)}/{len(particle_data)} particles, "
            f"sum_replicates: {self.sum_replicates}")
            
        return data
    
    def get_particle_data_with_replicates(self):
        """
        Args:
            None
        
        Returns:
            list: Particle data list, or None
        """
        if self.batch_particle_data is not None:
            if not self.sum_replicates or not self.replicate_samples:
                return [p for p in self.batch_particle_data if p.get('source_sample') == self.selected_sample]
            else:
                return [p for p in self.batch_particle_data if p.get('source_sample') in self.replicate_samples]
        
        if not hasattr(self.parent_window, 'sample_particle_data'):
            return None
        
        if not self.sum_replicates or not self.replicate_samples:
            return self.parent_window.sample_particle_data.get(self.selected_sample, [])
        
        print(f"Summing {len(self.replicate_samples)} manually selected samples: {self.replicate_samples}")
        
        combined_particles = []
        for sample_name in self.replicate_samples:
            sample_data = self.parent_window.sample_particle_data.get(sample_name, [])
            combined_particles.extend(sample_data)
        
        return combined_particles
            
    def apply_isotope_filter(self, particle_data):
        """
        Args:
            particle_data: list of particle dictionaries
        
        Returns:
            list: Filtered particle list
        """
        if not self.selected_isotopes:
            return particle_data
        
        selected_labels = [iso['label'] for iso in self.selected_isotopes]
        
        filtered_particles = []
        for particle in particle_data:
            has_selected_elements = False
            for element_name, count in particle.get('elements', {}).items():
                if element_name in selected_labels and count > 0:
                    has_selected_elements = True
                    break
            
            if has_selected_elements:
                filtered_particle = particle.copy()
                
                data_fields = [
                    'elements',
                    'element_mass_fg', 
                    'particle_mass_fg',
                    'element_moles_fmol',
                    'particle_moles_fmol', 
                    'element_diameter_nm',
                    'particle_diameter_nm'
                ]
                
                for field in data_fields:
                    if field in particle:
                        filtered_field = {}
                        for element_name, value in particle[field].items():
                            if element_name in selected_labels:
                                if field == 'elements' and value > 0:
                                    filtered_field[element_name] = value
                                elif field != 'elements' and value > 0 and not np.isnan(value):
                                    filtered_field[element_name] = value
                        
                        filtered_particle[field] = filtered_field
                
                filtered_particles.append(filtered_particle)
        
        return filtered_particles
    
    def configure(self, parent_window):
        """
        Args:
            parent_window: MainWindow instance
        
        Returns:
            bool: True if configuration accepted, False otherwise
        """
        if self.batch_samples:
            samples = self.batch_samples
            print(f"Using {len(samples)} samples from batch input")
        else:
            samples = list(parent_window.sample_to_folder_map.keys()) if hasattr(parent_window, 'sample_to_folder_map') else []
        
        dialog = SampleSelectorDialog(
            parent_window, 
            samples, 
            self.selected_sample, 
            self.selected_isotopes,
            self.sum_replicates,
            self.replicate_samples
        )
        
        if dialog.exec() == QDialog.Accepted:
            sample, selected_isotopes, sum_replicates = dialog.get_selection()
            if sample:
                if sum_replicates and isinstance(sample, list):
                    self.replicate_samples = sample
                    self.selected_sample = sample[0] if sample else None
                    self.sum_replicates = True
                else:
                    self.selected_sample = sample
                    self.replicate_samples = []
                    self.sum_replicates = False
                
                self.selected_isotopes = selected_isotopes
                
                self.configuration_changed.emit()
                return True
        return False
        
    def get_sample_data(self):
        """
        Args:
            None
        
        Returns:
            dict: Sample data dictionary, or None
        """
        if self.batch_sample_data:
            return self.batch_sample_data.get(self.selected_sample)
        
        if not self.parent_window or not self.selected_sample:
            return None
        if hasattr(self.parent_window, 'data_by_sample'):
            return self.parent_window.data_by_sample.get(self.selected_sample)
        return None


class SampleSelectorNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Args:
            workflow_node: SampleSelectorNode instance
            parent_window: MainWindow instance or None
        
        Returns:
            None
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        
        self.status_label = QLabel("Not configured")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #6B7280;
                padding: 4px 6px;
                background-color: rgba(249, 250, 251, 200);
                border-radius: 4px;
                border: 1px solid #E5E7EB;
            }
        """)
        self.status_label.setAlignment(Qt.AlignCenter)
        
        self.status_proxy = QGraphicsProxyWidget(self)
        self.status_proxy.setWidget(self.status_label)
        self.status_proxy.setPos(8, 40)
        self.status_proxy.resize(self.width - 16, 60)
        
        workflow_node.configuration_changed.connect(self.update_status)
        workflow_node.configuration_changed.connect(self.trigger_data_flow)
        self.update_status()
    
    def update_status(self):
        """
        Args:
            None
        
        Returns:
            None
        """
        if self.workflow_node.input_data:
            batch_samples = len(self.workflow_node.input_data.get('sample_names', []))
            self.status_label.setText(f"Batch Input\n{batch_samples} samples")
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #7C3AED;
                    padding: 4px 6px;
                    background-color: rgba(237, 233, 254, 200);
                    border-radius: 4px;
                    border: 1px solid #A78BFA;
                }
            """)
            return
            
        if self.workflow_node.selected_sample or (self.workflow_node.sum_replicates and self.workflow_node.replicate_samples):
            isotope_count = len(self.workflow_node.selected_isotopes)
            
            if isotope_count == 0:
                isotope_text = "All isotopes"
            else:
                isotope_text = f"{isotope_count} isotopes"
            
            sample_data = self.workflow_node.get_sample_data()
            data_types = []
            if sample_data:
                data_types = [key for key in sample_data.keys() if isinstance(sample_data[key], dict)]
            
            data_type_text = f"All types ({len(data_types)})" if data_types else "All types"
            
            if self.workflow_node.sum_replicates and self.workflow_node.replicate_samples:
                sample_count = len(self.workflow_node.replicate_samples)
                sample_text = f"{sample_count} samples summed"
                status_text = f"✓ {sample_text}\n{isotope_text}\n{data_type_text}"
            else:
                sample_name = self.workflow_node.selected_sample
                if len(sample_name) > 15:
                    sample_name = sample_name[:12] + "..."
                
                status_text = f"✓ {sample_name}\n{isotope_text}\n{data_type_text}"
            
            self.status_label.setText(status_text)
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #059669;
                    padding: 4px 6px;
                    background-color: rgba(236, 253, 245, 200);
                    border-radius: 4px;
                    border: 1px solid #10B981;
                }
            """)
        else:
            self.status_label.setText("⚙️ Not configured\n(Double-click to setup)")
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #DC2626;
                    padding: 4px 6px;
                    background-color: rgba(254, 242, 242, 200);
                    border-radius: 4px;
                    border: 1px solid #EF4444;
                }
            """)
    
    def trigger_data_flow(self):
        """
        Args:
            None
        
        Returns:
            None
        """
        scene = self.scene()
        if scene:
            for link in scene.workflow_links:
                if link.source_node == self.workflow_node:
                    if self.workflow_node.sum_replicates and self.workflow_node.replicate_samples:
                        print(f"Triggering data flow for summed samples: {self.workflow_node.replicate_samples}")
                    else:
                        print(f"Triggering data flow for sample change: {self.workflow_node.selected_sample}")
                    scene._trigger_data_flow(link)
            
            for node in scene.workflow_nodes:
                if hasattr(node, 'update_plot'):
                    node.update_plot()
        
    def configure_node(self):
        """
        Args:
            None
        
        Returns:
            None
        """
        if self.parent_window:
            self.workflow_node.configure(self.parent_window)
            
    def paint(self, painter, option, widget=None):
        """
        Args:
            painter: QPainter instance
            option: QStyleOptionGraphicsItem
            widget: QWidget or None
        
        Returns:
            None
        """
        def draw_sample_icon(painter, icon_rect):
            if self.workflow_node.sum_replicates and self.workflow_node.replicate_samples:
                for i in range(min(3, len(self.workflow_node.replicate_samples))):
                    offset = i * 2
                    db_rect = QRectF(icon_rect.left() + offset, icon_rect.top() + offset, 
                                   icon_rect.width() - offset * 2, icon_rect.height() - offset * 2)
                    painter.drawRoundedRect(db_rect, 2, 2)
                    
                    if i == min(2, len(self.workflow_node.replicate_samples) - 1):
                        painter.drawLine(db_rect.left() + 2, db_rect.top() + 4, 
                                       db_rect.right() - 2, db_rect.top() + 4)
                        painter.drawLine(db_rect.left() + 2, db_rect.top() + 7, 
                                       db_rect.right() - 2, db_rect.top() + 7)
                
                plus_x = icon_rect.right() - 6
                plus_y = icon_rect.top() + 3
                painter.drawLine(plus_x - 2, plus_y, plus_x + 2, plus_y)
                painter.drawLine(plus_x, plus_y - 2, plus_x, plus_y + 2)
            else:
                painter.drawRoundedRect(icon_rect, 2, 2)
                painter.drawLine(icon_rect.left() + 4, icon_rect.top() + 6, 
                               icon_rect.right() - 4, icon_rect.top() + 6)
                painter.drawLine(icon_rect.left() + 4, icon_rect.top() + 10, 
                               icon_rect.right() - 4, icon_rect.top() + 10)
                painter.drawLine(icon_rect.left() + 4, icon_rect.top() + 14, 
                               icon_rect.right() - 4, icon_rect.top() + 14)
        
        self.paint_base_node(painter, 99, 102, 241, 79, 70, 229, draw_sample_icon, self.workflow_node.title)


class BatchSampleSelectorDialog(QDialog):
    
    def __init__(self, parent_window):
        """
        Args:
            parent_window: MainWindow instance
        
        Returns:
            None
        """
        super().__init__(parent_window)
        self.setWindowTitle("🌐 Batch Window Selector")
        self.setModal(True)
        self.resize(900, 600)
        self.setMinimumSize(700, 500)
        
        self.parent_window = parent_window
        self.all_windows = self.get_all_windows()
        self.selected_windows = []
        
        self.setup_ui()
    
    def get_all_windows(self):
        """
        Args:
            None
        
        Returns:
            list: List of visible MainWindow instances
        """
        app = QApplication.instance()
        if not hasattr(app, 'main_windows'):
            return []
        return [w for w in app.main_windows if w.isVisible()]
    
    def setup_ui(self):
        """
        Args:
            None
        
        Returns:
            None
        """
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        header = QLabel("Select Windows to Include")
        header.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px;
                background: #ecf0f1;
                border-radius: 5px;
            }
        """)
        layout.addWidget(header)
        
        instructions = QLabel(
            "✓ Check windows to include all their samples\n"
            "• all samples and isotopes from selected windows will be available\n"
        )
        instructions.setStyleSheet("""
            QLabel {
                padding: 10px;
                background: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 5px;
                font-size: 12px;
            }
        """)
        layout.addWidget(instructions)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 5px;
                background: white;
            }
        """)
        
        scroll_content = QWidget()
        self.windows_layout = QVBoxLayout(scroll_content)
        self.windows_layout.setSpacing(10)
        
        self.window_checkboxes = []
        
        for i, window in enumerate(self.all_windows):
            window_checkbox = self.create_window_checkbox(window, i + 1)
            self.windows_layout.addWidget(window_checkbox)
            self.window_checkboxes.append(window_checkbox)
        
        self.windows_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        self.preview_label = QLabel("No windows selected")
        self.preview_label.setStyleSheet("""
            QLabel {
                padding: 10px;
                background: #e3f2fd;
                border: 2px solid #2196F3;
                border-radius: 5px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.preview_label)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def create_window_checkbox(self, window, window_num):
        """
        Args:
            window: MainWindow instance
            window_num: int, window number for display
        
        Returns:
            QCheckBox: Configured checkbox for window selection
        """
        sample_count = len(getattr(window, 'data_by_sample', {}))
        particle_count = sum(len(particles) for particles in getattr(window, 'sample_particle_data', {}).values())
        current_sample = getattr(window, 'current_sample', 'No sample')
        
        checkbox = QCheckBox(
            f"Window {window_num}: {current_sample}\n"
            f"  • {sample_count} samples, {particle_count:,} particles"
        )
        checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 13px;
                padding: 10px;
                background: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 5px;
            }
            QCheckBox:hover {
                background: #e9ecef;
                border-color: #3498db;
            }
            QCheckBox:checked {
                background: #d4edda;
                border-color: #28a745;
            }
        """)
        checkbox.window_ref = window
        checkbox.stateChanged.connect(self.update_preview)
        
        return checkbox
    
    def update_preview(self):
        """
        Args:
            None
        
        Returns:
            None
        """
        selected = [cb for cb in self.window_checkboxes if cb.isChecked()]
        
        if not selected:
            self.preview_label.setText("No windows selected")
            self.preview_label.setStyleSheet("""
                QLabel {
                    padding: 10px;
                    background: #fee;
                    border: 2px solid #f44;
                    border-radius: 5px;
                    font-weight: bold;
                }
            """)
        else:
            total_samples = sum(len(getattr(cb.window_ref, 'data_by_sample', {})) for cb in selected)
            total_particles = sum(
                sum(len(particles) for particles in getattr(cb.window_ref, 'sample_particle_data', {}).values())
                for cb in selected
            )
            
            self.preview_label.setText(
                f"Selected: {len(selected)} window(s)\n"
                f"Total: {total_samples} samples, {total_particles:,} particles\n"
            )
            self.preview_label.setStyleSheet("""
                QLabel {
                    padding: 10px;
                    background: #d4edda;
                    border: 2px solid #28a745;
                    border-radius: 5px;
                    font-weight: bold;
                }
            """)
    
    def get_selection(self):
        """
        Args:
            None
        
        Returns:
            list: List of selected MainWindow instances
        """
        selected_windows = [cb.window_ref for cb in self.window_checkboxes if cb.isChecked()]
        return selected_windows


class BatchSampleSelectorNode(WorkflowNode):
    
    def __init__(self, parent_window=None):
        """
        Args:
            parent_window: MainWindow instance or None
        
        Returns:
            None
        """
        super().__init__("Batch Selector", "batch_sample_selector")
        self.parent_window = parent_window
        self._has_output = True
        self.output_channels = ["output"]
        
        self.selected_windows = []
        
    def get_output_data(self):
        """
        Args:
            None
        
        Returns:
            dict: Data dictionary with type 'batch_sample_list', or None
        """
        if not self.selected_windows:
            return None
        
        all_sample_names = []
        all_particle_data = []
        all_sample_data = {}
        all_available_isotopes = {}
        
        for window_idx, window in enumerate(self.selected_windows):
            window_label = f"W{window_idx + 1}"
            
            if hasattr(window, 'selected_isotopes'):
                for element, isotopes in window.selected_isotopes.items():
                    if element not in all_available_isotopes:
                        all_available_isotopes[element] = set()
                    all_available_isotopes[element].update(isotopes)
            
            if hasattr(window, 'data_by_sample'):
                for sample_name, sample_data in window.data_by_sample.items():
                    display_name = f"{sample_name} [{window_label}]"
                    all_sample_names.append(display_name)
                    
                    all_sample_data[display_name] = sample_data
                    
                    if hasattr(window, 'sample_particle_data'):
                        particles = window.sample_particle_data.get(sample_name, [])
                        
                        for particle in particles:
                            particle_copy = particle.copy()
                            particle_copy['source_sample'] = display_name
                            particle_copy['source_window'] = window_label
                            particle_copy['original_sample'] = sample_name
                            all_particle_data.append(particle_copy)
        
        available_isotopes_dict = {k: list(v) for k, v in all_available_isotopes.items()}
        
        return {
            'type': 'batch_sample_list',
            'sample_names': all_sample_names,
            'particle_data': all_particle_data,
            'data': all_sample_data,
            'available_isotopes': available_isotopes_dict,
            'is_batch': True,
            'source_windows': len(self.selected_windows),
            'parent_window': self.parent_window
        }
    
    def configure(self, parent_window):
        """
        Args:
            parent_window: MainWindow instance
        
        Returns:
            bool: True if configuration accepted, False otherwise
        """
        dialog = BatchSampleSelectorDialog(parent_window)
        
        if dialog.exec() == QDialog.Accepted:
            selected_windows = dialog.get_selection()
            
            if selected_windows:
                self.selected_windows = selected_windows
                self.configuration_changed.emit()
                return True
        
        return False


class BatchSampleSelectorNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Args:
            workflow_node: BatchSampleSelectorNode instance
            parent_window: MainWindow instance or None
        
        Returns:
            None
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        self.width = 180
        self.height = 120
        
        self.status_label = QLabel("Not configured")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #6B7280;
                padding: 4px 6px;
                background-color: rgba(249, 250, 251, 200);
                border-radius: 4px;
                border: 1px solid #E5E7EB;
            }
        """)
        self.status_label.setAlignment(Qt.AlignCenter)
        
        self.status_proxy = QGraphicsProxyWidget(self)
        self.status_proxy.setWidget(self.status_label)
        self.status_proxy.setPos(8, 40)
        self.status_proxy.resize(self.width - 16, 60)
        
        workflow_node.configuration_changed.connect(self.update_status)
        workflow_node.configuration_changed.connect(self.trigger_data_flow)
        self.update_status()
    
    def update_status(self):
        """
        Args:
            None
        
        Returns:
            None
        """
        if not self.workflow_node.selected_windows:
            self.status_label.setText("⚙️ Not configured\n(Double-click to setup)")
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #DC2626;
                    padding: 4px 6px;
                    background-color: rgba(254, 242, 242, 200);
                    border-radius: 4px;
                    border: 1px solid #EF4444;
                }
            """)
        else:
            window_count = len(self.workflow_node.selected_windows)
            total_samples = sum(
                len(getattr(w, 'data_by_sample', {}))
                for w in self.workflow_node.selected_windows
            )
            
            self.status_label.setText(
                f"{window_count} window(s)\n"
                f"{total_samples} samples\n"
                f"All isotopes"
            )
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    color: #059669;
                    padding: 4px 6px;
                    background-color: rgba(236, 253, 245, 200);
                    border-radius: 4px;
                    border: 1px solid #10B981;
                }
            """)
    
    def trigger_data_flow(self):
        """
        Args:
            None
        
        Returns:
            None
        """
        scene = self.scene()
        if scene:
            for link in scene.workflow_links:
                if link.source_node == self.workflow_node:
                    print(f"🔄 Triggering data flow for batch windows: {len(self.workflow_node.selected_windows)} windows")
                    scene._trigger_data_flow(link)
            
            for node in scene.workflow_nodes:
                if hasattr(node, 'update_plot'):
                    node.update_plot()
    
    def paint(self, painter, option, widget=None):
        """
        Args:
            painter: QPainter instance
            option: QStyleOptionGraphicsItem
            widget: QWidget or None
        
        Returns:
            None
        """
        def draw_windows_icon(painter, icon_rect):
            for i in range(2):
                offset = i * 3
                window_rect = QRectF(
                    icon_rect.left() + offset,
                    icon_rect.top() + offset,
                    icon_rect.width() - offset * 2,
                    icon_rect.height() - offset * 2
                )
                painter.drawRoundedRect(window_rect, 2, 2)
                
                title_bar = QRectF(
                    window_rect.left(),
                    window_rect.top(),
                    window_rect.width(),
                    4
                )
                painter.fillRect(title_bar, QColor(255, 255, 255, 100))
        
        self.paint_base_node(painter, 99, 102, 241, 79, 70, 229,
                           draw_windows_icon, "Batch Windows")
    
    def configure_node(self):
        """
        Args:
            None
        
        Returns:
            None
        """
        if self.parent_window:
            self.workflow_node.configure(self.parent_window)



class DraggableNodeButton(QPushButton):
    
    def __init__(self, text, node_type):
        """
        Initialize enhanced draggable button with improved styling.
        
        Args:
            text: Button text to display
            node_type: Node type identifier for drag operation
        """
        super().__init__(text)
        self.node_type = node_type
        self.setMinimumHeight(35)
        self.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #374151;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 8px 10px;
                text-align: left;
                font-size: 11px;
                font-family: 'Segoe UI';
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
                border-color: #3B82F6;
                color: #3B82F6;
            }
            QPushButton:pressed {
                background-color: #E5E7EB;
            }
        """)
    
    def mousePressEvent(self, event):
        """
        Handle mouse press event to initiate drag.
        
        Args:
            event: QMouseEvent
        """
        if event.button() == Qt.LeftButton:
            self.start_drag()
        super().mousePressEvent(event)
    
    def start_drag(self):
        """
        Start drag operation with node type data.
        """
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.node_type)
        
        pixmap = self.grab()
        drag.setMimeData(mime_data)
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width()//2, pixmap.height()//2))
        
        drag.exec_(Qt.CopyAction)


class NodePalette(QWidget):
    
    def __init__(self, parent_window=None):
        """
        Initialize node palette with data processing and visualization components.
        
        Args:
            parent_window: Parent window reference
        """
        super().__init__()
        self.parent_window = parent_window
        self.setup_ui()
    
    def _get_group_style(self):
        """
        Return modern styling for QGroupBox widgets.
        
        Returns:
            str: CSS stylesheet for group boxes
        """
        return """
            QGroupBox {
                border: 1px solid #E5E7EB;
                border-radius: 10px;
                margin-top: 16px;
                padding-top: 16px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #FAFBFC);
                font-weight: 600;
                font-size: 12px;
                color: #374151;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 3px 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667EEA, stop:1 #764BA2);
                color: white;
                font-weight: 700;
                font-size: 11px;
                border-radius: 5px;
                left: 12px;
                top: 6px;
            }
        """
    
    def _get_button_style(self):
        """
        Return enhanced button styling.
        
        Returns:
            str: CSS stylesheet for buttons
        """
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F8FAFC);
                border: 1px solid #E2E8F0;
                border-radius: 7px;
                padding: 8px 12px;
                text-align: left;
                font-size: 12px;
                font-weight: 500;
                color: #1F2937;
                min-height: 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #F1F5F9, stop:1 #E2E8F0);
                border: 1px solid #CBD5E1;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #E2E8F0, stop:1 #CBD5E1);
                border: 1px solid #94A3B8;
            }
        """
    
    def setup_ui(self):
        """
        Set up the user interface for the node palette.
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #F8FAFC, stop:1 #F1F5F9);
            }
        """)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #F1F5F9, stop:1 #E2E8F0);
                width: 7px;
                border-radius: 3px;
                margin: 1px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #94A3B8, stop:1 #64748B);
                border-radius: 3px;
                min-height: 18px;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #64748B, stop:1 #475569);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        title = QLabel("Analysis Components")
        title.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667EEA, stop:1 #764BA2);
                color: white;
                font-size: 14px;
                font-weight: 700;
                font-family: 'Segoe UI', Arial, sans-serif;
                padding: 12px 16px;
                border-radius: 10px;
                margin-bottom: 6px;
            }
        """)
        layout.addWidget(title)
        
        data_group = QGroupBox("Data Processing")
        data_group.setStyleSheet(self._get_group_style())
        data_layout = QVBoxLayout(data_group)
        data_layout.setSpacing(6)
        data_layout.setContentsMargins(10, 20, 10, 10)
        
        sample_btn = DraggableNodeButton("Single Sample", "sample_selector")
        sample_btn.setIcon(qta.icon('fa6s.file', color="#667EEA"))
        sample_btn.setStyleSheet(self._get_button_style())
        data_layout.addWidget(sample_btn)
        
        multiple_sample_btn = DraggableNodeButton("Multiple Sample Selector", "multiple_sample_selector")
        multiple_sample_btn.setIcon(qta.icon('fa6s.copy', color="#764BA2"))
        multiple_sample_btn.setStyleSheet(self._get_button_style())
        data_layout.addWidget(multiple_sample_btn)
        
        batch_sample_btn = DraggableNodeButton("Batch Sample Selector", "batch_sample_selector")
        batch_sample_btn.setIcon(qta.icon('fa6s.globe', color="#667EEA"))
        batch_sample_btn.setToolTip("Select samples from ALL open windows")
        batch_sample_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667EEA, stop:1 #764BA2);
                color: white;
                font-weight: bold;
                border: 2px solid #5A67D8;
                padding: 8px 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5A67D8, stop:1 #6B46C1);
            }
        """)
        data_layout.addWidget(batch_sample_btn)
        
        layout.addWidget(data_group)
        
        plots_group = QGroupBox("Visualization")
        plots_group.setStyleSheet(self._get_group_style())
        plots_layout = QVBoxLayout(plots_group)
        plots_layout.setSpacing(6)
        plots_layout.setContentsMargins(10, 20, 10, 10)
        
        viz_colors = ["#667EEA", "#764BA2", "#F093FB", "#F5576C", "#4FACFE", 
                     "#EB470C", "#43E97B", "#072C0B", "#38F9D7", "#0739DE"]
        
        viz_buttons = [
            ("Histogram Plot", "histogram_plot", 'fa6s.chart-column'),
            ("Element Bar Chart", "element_bar_chart_plot", 'fa6s.chart-bar'),
            ("Box Plot", "box_plot", 'fa6s.chart-simple'),
            ("Correlation Plot", "correlation_plot", 'fa6s.chart-line'),
            ("Pie Chart Plot", "pie_chart_plot", 'fa6s.chart-pie'),
            ("Element Composition", "element_composition_plot", 'fa6s.burger'),
            ("Heatmap Plot", "heatmap_plot", 'fa6s.fire-flame-curved'),
            ("Molar Ratio Plot", "molar_ratio_plot", 'fa6s.divide'),
            ("Isotopic Ratio", "isotopic_ratio_plot", 'fa6s.percent'),
            ("Ternary Plot", "triangle_plot", 'fa6s.circle-nodes'),
            ("Single & multiple Elements", "single_multiple_element_plot", 'fa6s.newspaper'),
            ("Clustering Analysis", "clustering_plot", 'fa6s.network-wired'),
            ("AI Data Assistant", "ai_assistant", 'fa6s.hexagon-nodes')
        ]
        
        for i, (text, node_type, icon) in enumerate(viz_buttons):
            btn = DraggableNodeButton(text, node_type)
            btn.setIcon(qta.icon(icon, color=viz_colors[i % len(viz_colors)]))
            btn.setStyleSheet(self._get_button_style())
            plots_layout.addWidget(btn)
        
        layout.addWidget(plots_group)
        
        instructions = QLabel("Drag to canvas\nConnect nodes\nDouble-click to configure\nBuild data processing workflows!")
        instructions.setWordWrap(True)
        instructions.setStyleSheet("""
            QLabel {
                color: #64748B;
                font-size: 11px;
                font-weight: 500;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F8FAFC);
                padding: 10px;
                border-radius: 8px;
                border: 1px solid #E2E8F0;
                line-height: 1.3;
            }
        """)
        layout.addWidget(instructions)
        
        layout.addStretch()
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        

class EnhancedCanvasScene(QGraphicsScene):
    
    def __init__(self, parent_window=None):
        """
        Initialize enhanced scene with automatic data flow.
        
        Args:
            parent_window: Parent window reference
        """
        super().__init__()
        self.parent_window = parent_window
        
        self.dragging_connection = False
        self.drag_start_anchor = None
        self.temp_link_item = None
        
        self.workflow_nodes = []
        self.workflow_links = []
        self.node_items = {}
        self.link_items = {}
        
        self.setSceneRect(-1000, -1000, 2000, 2000)
        
        self.setFocusOnTouch(True)
    
    def keyPressEvent(self, event):
        """
        Handle keyboard shortcuts.
        
        Args:
            event: QKeyEvent
        """
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
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
        """
        Delete all selected items (nodes and links).
        """
        selected_items = self.selectedItems()
        
        if not selected_items:
            print("No items selected for deletion")
            return
        
        selected_nodes = [item for item in selected_items if isinstance(item, NodeItem)]
        selected_links = [item for item in selected_items if isinstance(item, LinkItem)]
        
        for link_item in selected_links:
            self.delete_link(link_item)
        
        for node_item in selected_nodes:
            self.delete_node(node_item)
        
        print(f"✅ Deleted {len(selected_nodes)} nodes and {len(selected_links)} connections")
    
    def delete_node(self, node_item):
        """
        Delete a specific node and all its connections.
        
        Args:
            node_item: NodeItem to delete
        """
        if not isinstance(node_item, NodeItem):
            return
            
        workflow_node = node_item.workflow_node
        
        links_to_delete = []
        for link in self.workflow_links:
            if link.source_node == workflow_node or link.sink_node == workflow_node:
                links_to_delete.append(link)
        
        for link in links_to_delete:
            link_item = self.link_items.get(link)
            if link_item:
                self.delete_link(link_item)
        
        if workflow_node in self.workflow_nodes:
            self.workflow_nodes.remove(workflow_node)
        
        if workflow_node in self.node_items:
            del self.node_items[workflow_node]
        
        self.removeItem(node_item)
        
        print(f"🗑️ Deleted node: {workflow_node.title}")
    
    def delete_link(self, link_item):
        """
        Delete a specific connection.
        
        Args:
            link_item: LinkItem to delete
        """
        if not isinstance(link_item, LinkItem):
            return
            
        workflow_link = link_item.workflow_link
        
        if workflow_link in self.workflow_links:
            self.workflow_links.remove(workflow_link)
        
        if workflow_link in self.link_items:
            del self.link_items[workflow_link]
        
        self.removeItem(link_item)
        
        print(f"🗑️ Deleted connection: {workflow_link.source_node.title} -> {workflow_link.sink_node.title}")
    
    def duplicate_selected_nodes(self):
        """
        Duplicate all selected nodes.
        """
        selected_nodes = [item for item in self.selectedItems() if isinstance(item, NodeItem)]
        
        if not selected_nodes:
            print("No nodes selected for duplication")
            return
        
        self.clearSelection()
        
        for node_item in selected_nodes:
            duplicated_node_item = self.duplicate_node(node_item)
            if duplicated_node_item:
                duplicated_node_item.setSelected(True)
        
        print(f"📋 Duplicated {len(selected_nodes)} nodes")
    
    def duplicate_node(self, node_item):
        """
        Duplicate a specific node.
        
        Args:
            node_item: NodeItem to duplicate
            
        Returns:
            NodeItem: Duplicated node item or None
        """
        if not isinstance(node_item, NodeItem):
            return None
            
        original_workflow_node = node_item.workflow_node
        
        new_workflow_node = None
        import copy
        if original_workflow_node.node_type == "sample_selector":
            new_workflow_node = SampleSelectorNode(self.parent_window)
            new_workflow_node.selected_sample = original_workflow_node.selected_sample
            new_workflow_node.selected_isotopes = copy.deepcopy(original_workflow_node.selected_isotopes)
            new_workflow_node.sum_replicates = original_workflow_node.sum_replicates
            new_workflow_node.replicate_samples = copy.deepcopy(original_workflow_node.replicate_samples)
            
        elif original_workflow_node.node_type == "multiple_sample_selector":
            new_workflow_node = MultipleSampleSelectorNode(self.parent_window)
            new_workflow_node.selected_samples = copy.deepcopy(original_workflow_node.selected_samples)
            new_workflow_node.selected_isotopes = copy.deepcopy(original_workflow_node.selected_isotopes)
            new_workflow_node.sample_config = copy.deepcopy(original_workflow_node.sample_config)
            new_workflow_node.sum_replicates = original_workflow_node.sum_replicates
            
        elif original_workflow_node.node_type == "histogram_plot":
            new_workflow_node = HistogramPlotNode(self.parent_window)
            new_workflow_node.config = copy.deepcopy(original_workflow_node.config)
            
        elif original_workflow_node.node_type == "box_plot":
            new_workflow_node = BoxPlotNode(self.parent_window)
            new_workflow_node.config = copy.deepcopy(original_workflow_node.config)

        elif original_workflow_node.node_type == "molar_ratio_plot":
            new_workflow_node = MolarRatioPlotNode(self.parent_window)
            new_workflow_node.config = copy.deepcopy(original_workflow_node.config)
            
        elif original_workflow_node.node_type == "element_bar_chart_plot": 
            new_workflow_node = ElementBarChartPlotNode(self.parent_window)
            new_workflow_node.config = copy.deepcopy(original_workflow_node.config)
            
        elif original_workflow_node.node_type == "correlation_plot": 
            new_workflow_node = CorrelationPlotNode(self.parent_window)
            new_workflow_node.config = copy.deepcopy(original_workflow_node.config)

        elif original_workflow_node.node_type == "pie_chart_plot": 
            new_workflow_node = PieChartPlotNode(self.parent_window)
            new_workflow_node.config = copy.deepcopy(original_workflow_node.config)
            
        elif original_workflow_node.node_type == "element_composition_plot":  
            new_workflow_node = ElementCompositionPlotNode(self.parent_window)
            new_workflow_node.config = copy.deepcopy(original_workflow_node.config)
            
        elif original_workflow_node.node_type == "heatmap_plot":
            new_workflow_node = HeatmapPlotNode(self.parent_window)
            new_workflow_node.config = copy.deepcopy(original_workflow_node.config)

        elif original_workflow_node.node_type == "isotopic_ratio_plot":
            new_workflow_node = IsotopicRatioPlotNode(self.parent_window)
            new_workflow_node.config = copy.deepcopy(original_workflow_node.config)
            
        elif original_workflow_node.node_type == "triangle_plot":
            new_workflow_node = TrianglePlotNode(self.parent_window)
            new_workflow_node.config = copy.deepcopy(original_workflow_node.config)
            
        elif original_workflow_node.node_type == "single_multiple_element_plot":
            new_workflow_node = SingleMultipleElementPlotNode(self.parent_window)
            new_workflow_node.config = copy.deepcopy(original_workflow_node.config)
            
        elif original_workflow_node.node_type == "clustering_plot":
            new_workflow_node = ClusteringPlotNode(self.parent_window)
            new_workflow_node.config = copy.deepcopy(original_workflow_node.config)
            
        elif original_workflow_node.node_type == "ai_assistant":
            new_workflow_node = AIAssistantNode(self.parent_window)
            new_workflow_node.config = copy.deepcopy(original_workflow_node.config)
                
                
        if not new_workflow_node:
            print(f"❌ Cannot duplicate node type: {original_workflow_node.node_type}")
            return None
        
        original_pos = node_item.pos()
        new_pos = QPointF(original_pos.x() + 170, original_pos.y() + 120)
        
        _, new_node_item = self.add_node(new_workflow_node, new_pos)
        
        print(f"📋 Duplicated {original_workflow_node.title}")
        return new_node_item
        
    def select_all_items(self):
        """
        Select all items in the scene.
        """
        for item in self.items():
            if isinstance(item, (NodeItem, LinkItem)):
                item.setSelected(True)
        print("✅ Selected all items")
    
    def add_node(self, workflow_node, pos):
        """
        Args:
            workflow_node: WorkflowNode instance
            pos: QPointF position
            
        Returns:
            tuple: (workflow_node, node_item)
        """
        workflow_node.set_position(pos)
        self.workflow_nodes.append(workflow_node)
        
        if workflow_node.node_type == "sample_selector":
            node_item = SampleSelectorNodeItem(workflow_node, self.parent_window)
        elif workflow_node.node_type == "multiple_sample_selector":
            node_item = MultipleSampleSelectorNodeItem(workflow_node, self.parent_window)
        elif workflow_node.node_type == "batch_sample_selector":
            node_item = BatchSampleSelectorNodeItem(workflow_node, self.parent_window)
        elif workflow_node.node_type == "histogram_plot":
            node_item = HistogramPlotNodeItem(workflow_node, self.parent_window)
        elif workflow_node.node_type == "element_bar_chart_plot":
            node_item = ElementBarChartPlotNodeItem(workflow_node, self.parent_window)
        elif workflow_node.node_type == "correlation_plot":  
            node_item = CorrelationPlotNodeItem(workflow_node, self.parent_window)
        elif workflow_node.node_type == "box_plot":  
            node_item = BoxPlotNodeItem(workflow_node, self.parent_window)
        elif workflow_node.node_type == "molar_ratio_plot":  
            node_item = MolarRatioPlotNodeItem(workflow_node, self.parent_window)
        elif workflow_node.node_type == "pie_chart_plot":  
            node_item = PieChartPlotNodeItem(workflow_node, self.parent_window)
        elif workflow_node.node_type == "element_composition_plot":  
            node_item = ElementCompositionPlotNodeItem(workflow_node, self.parent_window)
        elif workflow_node.node_type == "heatmap_plot":
            node_item = HeatmapPlotNodeItem(workflow_node, self.parent_window)
        elif workflow_node.node_type == "isotopic_ratio_plot":
            node_item = IsotopicRatioPlotNodeItem(workflow_node, self.parent_window)
        elif workflow_node.node_type == "triangle_plot":
            node_item = TrianglePlotNodeItem(workflow_node, self.parent_window)
        elif workflow_node.node_type == "single_multiple_element_plot":
            node_item = SingleMultipleElementPlotNodeItem(workflow_node, self.parent_window)
        elif workflow_node.node_type == "clustering_plot":
            node_item = ClusteringPlotNodeItem(workflow_node, self.parent_window)    
        elif workflow_node.node_type == "ai_assistant":
            node_item = AIAssistantNodeItem(workflow_node, self.parent_window)
        else:
            node_item = NodeItem(workflow_node)
        
        node_item.setPos(pos)
        self.addItem(node_item)
        self.node_items[workflow_node] = node_item
        
        return workflow_node, node_item
        
    def add_link(self, source_node, source_channel, sink_node, sink_channel):
        """
        Add a connection between nodes with immediate data flow.
        
        Args:
            source_node: Source workflow node
            source_channel: Output channel name
            sink_node: Destination workflow node
            sink_channel: Input channel name
            
        Returns:
            WorkflowLink: Created workflow link or None
        """
        print(f"🔗 Creating link: {source_node.title}[{source_channel}] -> {sink_node.title}[{sink_channel}]")
        
        workflow_link = WorkflowLink(source_node, source_channel, sink_node, sink_channel)
        self.workflow_links.append(workflow_link)
        
        link_item = LinkItem()
        link_item.set_workflow_link(workflow_link)
        
        source_item = self.node_items.get(source_node)
        sink_item = self.node_items.get(sink_node)
        
        if not source_item or not sink_item:
            print(f"❌ Missing node items: source={source_item}, sink={sink_item}")
            return None
        
        source_anchor = source_item.get_anchor(source_channel)
        sink_anchor = sink_item.get_anchor(sink_channel)
        
        if source_anchor and sink_anchor:
            print(f"🎯 Connecting anchors: {source_anchor.channel_name} -> {sink_anchor.channel_name}")
            
            link_item.set_source_anchor(source_anchor)
            link_item.set_sink_anchor(sink_anchor)
            
            self.addItem(link_item)
            self.link_items[workflow_link] = link_item
            
            print(f"✅ Successfully connected {source_node.title} -> {sink_node.title}")
            
            QApplication.processEvents()
            self._trigger_data_flow(workflow_link)
            
            return workflow_link
        else:
            print(f"❌ Failed to connect: missing anchors")
            return None
    
    def _trigger_data_flow(self, workflow_link):
        """
        Enhanced data flow processing.
        
        Args:
            workflow_link: WorkflowLink to trigger data flow for
        """
        try:
            print(f"🔄 Triggering data flow from {workflow_link.source_node.title} to {workflow_link.sink_node.title}")
            
            source_data = workflow_link.get_data()
            if source_data:
                print(f"📊 Data received: {source_data.get('type', 'unknown')}")
            else:
                print(f"❌ No data from source")
            
            sink_node = workflow_link.sink_node
            if hasattr(sink_node, 'process_data'):
                sink_node.process_data(source_data)
                
        except Exception as e:
            print(f"❌ Error in data flow: {str(e)}")
    
    def mousePressEvent(self, event):
        """
        Handle mouse press events for anchor connection.
        
        Args:
            event: QGraphicsSceneMouseEvent
        """
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.scenePos(), self.views()[0].transform())
            
            current_item = item
            while current_item and not isinstance(current_item, AnchorPoint):
                current_item = current_item.parentItem()
            
            if isinstance(current_item, AnchorPoint) and not current_item.is_input:
                print(f"🎯 Starting connection from output anchor: {current_item.channel_name}")
                self._start_connection_drag(current_item, event.scenePos())
                return
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """
        Handle mouse move events for connection dragging.
        
        Args:
            event: QGraphicsSceneMouseEvent
        """
        if self.dragging_connection and self.temp_link_item:
            self._update_connection_drag(event.scenePos())
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """
        Handle mouse release events to complete connections.
        
        Args:
            event: QGraphicsSceneMouseEvent
        """
        if self.dragging_connection:
            self._complete_connection_drag(event.scenePos())
        else:
            super().mouseReleaseEvent(event)
    
    def _start_connection_drag(self, anchor, pos):
        """
        Start connection drag.
        
        Args:
            anchor: Starting AnchorPoint
            pos: Mouse position as QPointF
        """
        print(f"🎯 Starting connection drag from {anchor.channel_name}")
        self.dragging_connection = True
        self.drag_start_anchor = anchor
        
        self.temp_link_item = LinkItem()
        self.temp_link_item.set_source_anchor(anchor)
        self.temp_link_item.setZValue(100)  
        
        temp_anchor = AnchorPoint(None, "temp", is_input=True)
        temp_anchor.setPos(pos)
        self.addItem(temp_anchor)
        self.temp_link_item.set_sink_anchor(temp_anchor)
        
        self.addItem(self.temp_link_item)
    
    def _update_connection_drag(self, pos):
        """
        Update the temporary connection visual.
        
        Args:
            pos: Mouse position as QPointF
        """
        if self.temp_link_item and self.temp_link_item.sink_anchor:
            temp_anchor = self.temp_link_item.sink_anchor
            temp_anchor.setPos(pos)
    
    def _complete_connection_drag(self, pos):
        """
        Complete connection drag.
        
        Args:
            pos: Mouse position as QPointF
        """
        print(f"🏁 Completing connection drag at {pos}")
        
        if self.temp_link_item:
            if self.temp_link_item.sink_anchor:
                self.removeItem(self.temp_link_item.sink_anchor)
            self.removeItem(self.temp_link_item)
            self.temp_link_item = None
        
        target_anchor = None
        items = self.items(pos, Qt.IntersectsItemShape, Qt.DescendingOrder)
        
        for item in items:
            if isinstance(item, AnchorPoint) and item.is_input and item != self.drag_start_anchor:
                target_anchor = item
                print(f"🎯 Found target anchor: {target_anchor.channel_name}")
                break
        
        if target_anchor and self.drag_start_anchor:
            source_node_item = self.drag_start_anchor.parentItem()
            sink_node_item = target_anchor.parentItem()
            
            if source_node_item and sink_node_item:
                source_workflow_node = None
                sink_workflow_node = None
                
                for wf_node, item in self.node_items.items():
                    if item == source_node_item:
                        source_workflow_node = wf_node
                    elif item == sink_node_item:
                        sink_workflow_node = wf_node
                
                if source_workflow_node and sink_workflow_node:
                    link = self.add_link(
                        source_workflow_node, self.drag_start_anchor.channel_name,
                        sink_workflow_node, target_anchor.channel_name
                    )
                    
                    if link:
                        print(f"✅ Connection created successfully")
                    else:
                        print(f"❌ Failed to create connection")
        
        self.dragging_connection = False
        self.drag_start_anchor = None
        
class ElementBarChartPlotNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Initialize Element Bar Chart node using horizontal bars as the actual node shape.
        
        Args:
            workflow_node: ElementBarChartPlotNode data model
            parent_window: Parent window reference
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        self.width = 90
        self.height = 100
        
        workflow_node.configuration_changed.connect(self.update_display)
        self.update_display()
    
    def update_display(self):
        """
        Update the visual display of the node.
        """
        self.update()
    
    def paint(self, painter, option, widget=None):
        """
        Paint horizontal bar chart icon as the main node.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        painter.setRenderHint(QPainter.Antialiasing)
        
        bar_height = 8
        bar_spacing = 3
        max_width = 55
        start_x = 15
        start_y = 15
        
        colors = [QColor(255, 107, 107), QColor(255, 206, 84), QColor(78, 205, 196), QColor(129, 236, 236)]
        widths = [max_width, max_width * 0.8, max_width * 0.6, max_width * 0.4]
        
        for i, (color, width) in enumerate(zip(colors, widths)):
            y_pos = start_y + i * (bar_height + bar_spacing)
            
            shadow_rect = QRectF(start_x + 1, y_pos + 1, width, bar_height)
            painter.setBrush(QBrush(QColor(0, 0, 0, 20)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(shadow_rect, 2, 2)
            
            bar_rect = QRectF(start_x, y_pos, width, bar_height)
            painter.setBrush(QBrush(color))
            if self.isSelected():
                painter.setPen(QPen(QColor(59, 130, 246), 2))
            else:
                painter.setPen(QPen(QColor(55, 65, 81), 1))
            painter.drawRoundedRect(bar_rect, 2, 2)
        
        text_rect = QRectF(0, 70, self.width, 25)
        painter.setPen(QPen(QColor(55, 65, 81)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignCenter, "Element Bars")
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the node.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return QRectF(-10, -5, self.width + 20, self.height + 10)
    
    def configure_node(self):
        """
        Show element bar chart configuration dialog.
        """
        dialog = ElementBarChartDisplayDialog(self.workflow_node, self.parent_window)
        dialog.show()

class CorrelationPlotNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Initialize Correlation plot node using scatter plot with axes like the image.
        
        Args:
            workflow_node: CorrelationPlotNode data model
            parent_window: Parent window reference
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        self.width = 80
        self.height = 100
        
        workflow_node.configuration_changed.connect(self.update_display)
        self.update_display()
    
    def update_display(self):
        """
        Update the visual display of the node.
        """
        self.update()
    
    def paint(self, painter, option, widget=None):
        """
        Paint correlation scatter plot with axes like the image.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        painter.setRenderHint(QPainter.Antialiasing)
        
        plot_size = 55
        start_x = (self.width - plot_size) / 2
        start_y = 10
        
        axis_color = QColor(0, 0, 0)
        painter.setPen(QPen(axis_color, 3))
        
        painter.drawLine(QPointF(start_x, start_y), QPointF(start_x, start_y + plot_size))
        
        painter.drawLine(QPointF(start_x, start_y + plot_size), 
                        QPointF(start_x + plot_size, start_y + plot_size))
        
        tick_length = 4
        painter.setPen(QPen(axis_color, 2))
        
        for i in range(5):
            tick_y = start_y + i * (plot_size / 4)
            painter.drawLine(QPointF(start_x - tick_length, tick_y), 
                           QPointF(start_x, tick_y))
        
        for i in range(5):
            tick_x = start_x + i * (plot_size / 4)
            painter.drawLine(QPointF(tick_x, start_y + plot_size), 
                           QPointF(tick_x, start_y + plot_size + tick_length))
        
        painter.setPen(QPen(axis_color, 3))
        painter.drawLine(QPointF(start_x + 5, start_y + plot_size - 5), 
                        QPointF(start_x + plot_size - 10, start_y + 15))
        
        points = [
            (start_x + 8, start_y + plot_size - 12),
            (start_x + 15, start_y + plot_size - 18),
            (start_x + 22, start_y + plot_size - 25),
            (start_x + 30, start_y + plot_size - 30),
            (start_x + 38, start_y + plot_size - 38),
            (start_x + 45, start_y + plot_size - 45),
            (start_x + 20, start_y + plot_size - 15),
            (start_x + 35, start_y + plot_size - 25),
            (start_x + 42, start_y + plot_size - 35),
            (start_x + 25, start_y + plot_size - 35),
            (start_x + 12, start_y + plot_size - 25),
        ]
        
        for x, y in points:
            painter.setBrush(QBrush(QColor(0, 0, 0)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(x, y), 4, 4)
            
            painter.setBrush(QBrush(QColor(255, 105, 180)))
            painter.drawEllipse(QPointF(x, y), 2, 2)
        
        if self.isSelected():
            painter.setPen(QPen(QColor(59, 130, 246), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(start_x - 5, start_y - 5, plot_size + 10, plot_size + 15))
        
        text_rect = QRectF(0, 72, self.width, 25)
        painter.setPen(QPen(QColor(55, 65, 81)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignCenter, "Correlation")
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the node.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return QRectF(-10, -5, self.width + 20, self.height + 10)
    
    def configure_node(self):
        """
        Show correlation configuration dialog.
        """
        dialog = CorrelationPlotDisplayDialog(self.workflow_node, self.parent_window)
        dialog.show()


class BoxPlotNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Initialize Box plot node visual item.
        
        Args:
            workflow_node: BoxPlotNode data model
            parent_window: Parent window reference
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        self.width = 80
        self.height = 100
        
        workflow_node.configuration_changed.connect(self.update_display)
        self.update_display()
    
    def update_display(self):
        """
        Update the visual display of the node.
        """
        self.update()
    
    def paint(self, painter, option, widget=None):
        """
        Paint box plot icon as the main node.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        painter.setRenderHint(QPainter.Antialiasing)
        
        box_width = 12
        box_height = 25
        box_spacing = 6
        num_boxes = 4
        
        total_width = num_boxes * box_width + (num_boxes - 1) * box_spacing
        start_x = (self.width - total_width) / 2
        base_y = 55
        
        colors = [QColor(102, 51, 153), QColor(46, 134, 171), QColor(162, 59, 114), QColor(241, 143, 1)]
        box_heights = [25, 35, 20, 30]
        
        for i in range(num_boxes):
            box_x = start_x + i * (box_width + box_spacing)
            box_rect = QRectF(box_x + 2, base_y - box_heights[i] + 2, box_width, box_heights[i])
            painter.setBrush(QBrush(QColor(0, 0, 0, 20)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(box_rect, 2, 2)
        
        for i, (color, height) in enumerate(zip(colors, box_heights)):
            box_x = start_x + i * (box_width + box_spacing)
            
            q1_y = base_y - height * 0.3
            q3_y = base_y - height * 0.7
            box_rect = QRectF(box_x, q3_y, box_width, q1_y - q3_y)
            
            painter.setBrush(QBrush(color))
            if self.isSelected():
                painter.setPen(QPen(QColor(59, 130, 246), 2))
            else:
                painter.setPen(QPen(QColor(55, 65, 81), 1))
            painter.drawRoundedRect(box_rect, 1, 1)
            
            median_y = base_y - height * 0.5
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.drawLine(box_x, median_y, box_x + box_width, median_y)
            
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            center_x = box_x + box_width / 2
            
            upper_whisker_y = base_y - height * 0.9
            painter.drawLine(center_x, q3_y, center_x, upper_whisker_y)
            painter.drawLine(center_x - 3, upper_whisker_y, center_x + 3, upper_whisker_y)
            
            lower_whisker_y = base_y - height * 0.1
            painter.drawLine(center_x, q1_y, center_x, lower_whisker_y)
            painter.drawLine(center_x - 3, lower_whisker_y, center_x + 3, lower_whisker_y)
            
            if i == 1:
                outlier_y = base_y - height * 0.95
                painter.setBrush(QBrush(QColor(255, 0, 0)))
                painter.setPen(QPen(QColor(0, 0, 0), 1))
                painter.drawEllipse(QRectF(center_x - 2, outlier_y - 2, 4, 4))
        
        text_rect = QRectF(0, base_y + 10, self.width, 25)
        painter.setPen(QPen(QColor(55, 65, 81)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignCenter, "Box Plot")
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the node.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return QRectF(-10, -5, self.width + 20, self.height + 10)
    
    def configure_node(self):
        """
        Show box plot configuration dialog.
        """
        dialog = BoxPlotDisplayDialog(self.workflow_node, self.parent_window)
        dialog.show()

class TrianglePlotNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Initialize Triangle plot node with gradient colors like the image.
        
        Args:
            workflow_node: TrianglePlotNode data model
            parent_window: Parent window reference
        """
        
        

        super().__init__(workflow_node)
        self.parent_window = parent_window
        self.width = 80
        self.height = 100
        
        workflow_node.configuration_changed.connect(self.update_display)
        workflow_node.configuration_changed.connect(self.update_title_display)
        self.update_display()
    
    def update_display(self):
        """
        Update the visual display of the node.
        """
        self.update()
    
    def update_title_display(self):
        """
        Update the title display when configuration changes.
        """
        self.update()
    
    def paint(self, painter, option, widget=None):
        """
        Paint gradient triangle like the image.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        painter.setRenderHint(QPainter.Antialiasing)
        
        triangle_size = 50
        center_x = self.width / 2
        top_y = 10
        bottom_y = top_y + triangle_size
        
        triangle_points = [
            QPointF(center_x, top_y),
            QPointF(center_x - triangle_size/2, bottom_y),
            QPointF(center_x + triangle_size/2, bottom_y)
        ]
        
        layer_height = triangle_size / 8
        
        for i in range(8):
            if i < 2:
                color = QColor(129, 236, 141)
            elif i < 3:
                color = QColor(255, 235, 59)
            elif i < 4:
                color = QColor(255, 183, 77)
            elif i < 6:
                color = QColor(255, 138, 128)
            else:
                color = QColor(255, 107, 107)
            
            layer_y = bottom_y - (i + 1) * layer_height
            layer_progress = (i + 1) / 8.0
            
            layer_width = triangle_size * (1.0 - layer_progress * 0.8)
            layer_points = [
                QPointF(center_x, top_y + layer_progress * triangle_size * 0.2),
                QPointF(center_x - layer_width/2, bottom_y),
                QPointF(center_x + layer_width/2, bottom_y)
            ]
            
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(layer_points)
        
        painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
        for i in range(1, 6):
            progress = i / 6.0
            contour_width = triangle_size * (1.0 - progress * 0.6)
            contour_y = top_y + progress * triangle_size * 0.7
            
            contour_points = [
                QPointF(center_x - contour_width/2, bottom_y),
                QPointF(center_x + contour_width/2, bottom_y),
                QPointF(center_x, contour_y)
            ]
            painter.drawPolygon(contour_points)
        
        bar_x = center_x + triangle_size/2 + 8
        bar_width = 8
        bar_colors = [
            QColor(129, 236, 141),
            QColor(255, 235, 59),
            QColor(255, 183, 77),
            QColor(255, 138, 128),
            QColor(255, 107, 107),
        ]
        
        for i, color in enumerate(bar_colors):
            bar_y = top_y + i * 8
            bar_rect = QRectF(bar_x, bar_y, bar_width, 6)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRect(bar_rect)
        
        if self.isSelected():
            painter.setPen(QPen(QColor(59, 130, 246), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawPolygon(triangle_points)
        
        display_title = self.workflow_node.config.get('custom_title', 'Triangle')
        if len(display_title) > 10:
            display_title = display_title[:7] + "..."
        
        text_rect = QRectF(0, bottom_y + 5, self.width, 25)
        painter.setPen(QPen(QColor(55, 65, 81)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignCenter, display_title)
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the node.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return QRectF(-10, -5, self.width + 20, self.height + 10)
    
    def configure_node(self):
        """
        Show triangle configuration dialog.
        """
        dialog = TriangleDisplayDialog(self.workflow_node, self.parent_window)
        dialog.show()


class SingleMultipleElementPlotNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Initialize visual node item for single/multiple element analysis.
        
        Args:
            workflow_node: SingleMultipleElementPlotNode data model
            parent_window: Parent window reference
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        self.width = 100
        self.height = 120
        
    
    def paint(self, painter, option, widget=None):
        """
        Paint the node with pie/bar chart visualization.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        painter.setRenderHint(QPainter.Antialiasing)
        
        center_x = self.width / 2
        center_y = 40
        
        pie_rect = QRectF(center_x - 35, center_y - 15, 25, 25)
        
        painter.setBrush(QBrush(QColor(82, 196, 141)))
        if self.isSelected():
            painter.setPen(QPen(QColor(59, 130, 246), 2))
        else:
            painter.setPen(QPen(QColor(52, 73, 94), 2))
        painter.drawPie(pie_rect, 0, 270 * 16)
        
        painter.setBrush(QBrush(QColor(255, 127, 80)))
        painter.drawPie(pie_rect, 270 * 16, 90 * 16)
        
        bar_colors = [QColor(255, 107, 107), QColor(255, 206, 84), QColor(78, 205, 196)]
        bar_heights = [15, 20, 12]
        bar_width = 6
        
        start_x = center_x + 15
        for i, (color, height) in enumerate(zip(bar_colors, bar_heights)):
            bar_x = start_x + i * (bar_width + 2)
            bar_rect = QRectF(bar_x, center_y + 10 - height, bar_width, height)
            
            painter.setBrush(QBrush(color))
            if self.isSelected():
                painter.setPen(QPen(QColor(59, 130, 246), 1))
            else:
                painter.setPen(QPen(QColor(55, 65, 81), 1))
            painter.drawRoundedRect(bar_rect, 1, 1)
        
        text_rect = QRectF(0, 60, self.width, 20)
        painter.setPen(QPen(QColor(55, 65, 81)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignCenter, "Single/Multiple")
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the node.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return QRectF(-10, -5, self.width + 20, self.height + 10)
    
    def configure_node(self):
        """
        Show configuration dialog.
        """
        dialog = SingleMultipleElementDisplayDialog(self.workflow_node, self.parent_window)
        dialog.show()


class ElementCompositionPlotNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Initialize Element composition node with mixed pie and bar chart like the image.
        
        Args:
            workflow_node: ElementCompositionPlotNode data model
            parent_window: Parent window reference
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        self.width = 85
        self.height = 100
        
        workflow_node.configuration_changed.connect(self.update_display)
        self.update_display()
    
    def update_display(self):
        """
        Update the visual display of the node.
        """
        self.update()
    
    def paint(self, painter, option, widget=None):
        """
        Paint mixed pie and bar chart like the image.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        painter.setRenderHint(QPainter.Antialiasing)
        
        pie_size = 35
        pie_x = 15
        pie_y = 15
        pie_rect = QRectF(pie_x, pie_y, pie_size, pie_size)
        
        painter.setPen(QPen(QColor(0, 0, 0), 2))
        
        painter.setBrush(QBrush(QColor(100, 149, 237)))
        painter.drawPie(pie_rect, 0, 180 * 16)
        
        painter.setBrush(QBrush(QColor(220, 20, 60)))
        painter.drawPie(pie_rect, 180 * 16, 120 * 16)
        
        bar_colors = [
            QColor(100, 149, 237),
            QColor(255, 215, 0),
            QColor(220, 20, 60),
        ]
        
        bar_x = pie_x + pie_size + 8
        for i, color in enumerate(bar_colors):
            bar_rect = QRectF(bar_x, pie_y + i * 12, 15, 8)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            painter.drawRect(bar_rect)
        
        square_size = 6
        squares = [
            (pie_x + pie_size + 5, pie_y + pie_size + 8, QColor(100, 149, 237)),
            (pie_x + pie_size + 15, pie_y + pie_size + 8, QColor(255, 215, 0)),
            (pie_x + pie_size + 25, pie_y + pie_size + 8, QColor(220, 20, 60)),
        ]
        
        for x, y, color in squares:
            square_rect = QRectF(x, y, square_size, square_size)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            painter.drawRect(square_rect)
        
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        
        pie_center_x = pie_x + pie_size/2
        pie_center_y = pie_y + pie_size/2
        painter.drawLine(QPointF(pie_center_x + pie_size/2, pie_center_y), 
                        QPointF(bar_x, pie_y + 12))
        
        if self.isSelected():
            painter.setPen(QPen(QColor(59, 130, 246), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(pie_x - 2, pie_y - 2, self.width - 20, pie_size + 25))
        
        text_rect = QRectF(0, 70, self.width, 25)
        painter.setPen(QPen(QColor(55, 65, 81)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignCenter, "Composition")
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the node.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return QRectF(-10, -5, self.width + 20, self.height + 10)
    
    def configure_node(self):
        """
        Show element composition configuration dialog.
        """
        dialog = ElementCompositionDisplayDialog(self.workflow_node, self.parent_window)
        dialog.show()


class MolarRatioPlotNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Initialize Molar ratio node visual item.
        
        Args:
            workflow_node: MolarRatioPlotNode data model
            parent_window: Parent window reference
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        self.width = 80
        self.height = 100
        
        workflow_node.configuration_changed.connect(self.update_display)
        self.update_display()
    
    def update_display(self):
        """
        Update the visual display of the node.
        """
        self.update()
    
    def paint(self, painter, option, widget=None):
        """
        Paint molar ratio icon as the main node.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        painter.setRenderHint(QPainter.Antialiasing)
        
        center_x = self.width / 2
        center_y = 35
        
        num_rect = QRectF(center_x - 25, center_y - 20, 50, 15)
        painter.setPen(QPen(QColor(102, 51, 153), 2))
        painter.setBrush(QBrush(QColor(102, 51, 153, 100)))
        painter.drawRoundedRect(num_rect, 3, 3)
        
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(num_rect, Qt.AlignCenter, "El₁")
        
        painter.setPen(QPen(QColor(55, 65, 81), 3))
        painter.drawLine(center_x - 20, center_y, center_x + 20, center_y)
        
        den_rect = QRectF(center_x - 25, center_y + 5, 50, 15)
        painter.setPen(QPen(QColor(46, 134, 171), 2))
        painter.setBrush(QBrush(QColor(46, 134, 171, 100)))
        painter.drawRoundedRect(den_rect, 3, 3)
        
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(font)
        painter.drawText(den_rect, Qt.AlignCenter, "El₂")
        
        bar_colors = [QColor(162, 59, 114), QColor(241, 143, 1), QColor(102, 51, 153)]
        bar_heights = [8, 15, 12]
        bar_width = 4
        
        start_x = center_x - 8
        for i, (color, height) in enumerate(zip(bar_colors, bar_heights)):
            bar_x = start_x + i * (bar_width + 2)
            bar_rect = QRectF(bar_x, center_y + 25, bar_width, height)
            
            painter.setBrush(QBrush(color))
            if self.isSelected():
                painter.setPen(QPen(QColor(59, 130, 246), 2))
            else:
                painter.setPen(QPen(QColor(55, 65, 81), 1))
            painter.drawRoundedRect(bar_rect, 1, 1)
        
        text_rect = QRectF(0, center_y + 45, self.width, 25)
        painter.setPen(QPen(QColor(55, 65, 81)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignCenter, "Molar Ratio")
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the node.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return QRectF(-10, -5, self.width + 20, self.height + 10)
    
    def configure_node(self):
        """
        Show molar ratio configuration dialog.
        """
        dialog = MolarRatioDisplayDialog(self.workflow_node, self.parent_window)
        dialog.show()
        
        

class ClusteringPlotNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Initialize Clustering node with network of connected blue circles like the image.
        
        Args:
            workflow_node: ClusteringPlotNode data model
            parent_window: Parent window reference
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        self.width = 80
        self.height = 100
        
        workflow_node.configuration_changed.connect(self.update_display)
        self.update_display()
    
    def update_display(self):
        """
        Update the visual display of the node.
        """
        self.update()
    
    def paint(self, painter, option, widget=None):
        """
        Paint network clustering like the image.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        painter.setRenderHint(QPainter.Antialiasing)
        
        center_x = self.width / 2
        center_y = 35
        
        nodes = [
            (center_x, center_y, 10, QColor(100, 149, 237), True),
            
            (center_x - 20, center_y - 12, 6, QColor(135, 206, 250), True),
            (center_x + 20, center_y - 8, 6, QColor(135, 206, 250), True),
            (center_x + 25, center_y + 15, 6, QColor(135, 206, 250), True),
            
            (center_x - 28, center_y + 8, 4, QColor(100, 149, 237), False),
            (center_x - 15, center_y + 20, 4, QColor(100, 149, 237), False),
            (center_x + 8, center_y - 22, 4, QColor(100, 149, 237), False),
            (center_x + 30, center_y - 20, 4, QColor(100, 149, 237), False),
            (center_x - 35, center_y - 8, 3, QColor(100, 149, 237), False),
            (center_x + 35, center_y + 8, 3, QColor(100, 149, 237), False),
        ]
        
        painter.setPen(QPen(QColor(100, 149, 237), 2))
        
        central_pos = (nodes[0][0], nodes[0][1])
        for i in range(1, 4):
            painter.drawLine(QPointF(central_pos[0], central_pos[1]), 
                           QPointF(nodes[i][0], nodes[i][1]))
        
        for x, y, size, color, filled in nodes:
            if filled:
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(color.darker(150), 2))
                painter.drawEllipse(QPointF(x, y), size, size)
            else:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(color, 2))
                painter.drawEllipse(QPointF(x, y), size, size)
        
        if self.isSelected():
            painter.setPen(QPen(QColor(59, 130, 246), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(5, 10, self.width - 10, 50))
        
        text_rect = QRectF(0, 70, self.width, 25)
        painter.setPen(QPen(QColor(55, 65, 81)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignCenter, "Clustering")
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the node.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return QRectF(-10, -5, self.width + 20, self.height + 10)
    
    def configure_node(self):
        """
        Show clustering configuration dialog.
        """
        dialog = ClusteringDisplayDialog(self.workflow_node, self.parent_window)
        dialog.show()

class HeatmapPlotNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Initialize Heatmap node using the icon as the actual node shape.
        
        Args:
            workflow_node: HeatmapPlotNode data model
            parent_window: Parent window reference
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        self.width = 80
        self.height = 100
        
        workflow_node.configuration_changed.connect(self.update_display)
        self.update_display()
    
    def update_display(self):
        """
        Update the visual display of the node.
        """
        self.update()
    
    def paint(self, painter, option, widget=None):
        """
        Paint the colorful heatmap grid as the main node.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        painter.setRenderHint(QPainter.Antialiasing)
        
        grid_size = 12
        grid_spacing = 2
        grid_rows = 4
        grid_cols = 4
        
        total_width = grid_cols * grid_size + (grid_cols - 1) * grid_spacing
        total_height = grid_rows * grid_size + (grid_rows - 1) * grid_spacing
        start_x = (self.width - total_width) / 2
        start_y = 15
        
        colors = [
            [QColor(52, 73, 124), QColor(52, 73, 124), QColor(230, 230, 230), QColor(255, 127, 80)],
            [QColor(52, 73, 124), QColor(230, 230, 230), QColor(230, 230, 230), QColor(255, 127, 80)],
            [QColor(230, 230, 230), QColor(230, 230, 230), QColor(230, 230, 230), QColor(255, 127, 80)],
            [QColor(230, 230, 230), QColor(255, 127, 80), QColor(255, 127, 80), QColor(255, 127, 80)]
        ]
        
        for row in range(grid_rows):
            for col in range(grid_cols):
                x = start_x + col * (grid_size + grid_spacing) + 1
                y = start_y + row * (grid_size + grid_spacing) + 1
                cell_rect = QRectF(x, y, grid_size, grid_size)
                painter.setBrush(QBrush(QColor(0, 0, 0, 15)))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(cell_rect, 1, 1)
        
        for row in range(grid_rows):
            for col in range(grid_cols):
                x = start_x + col * (grid_size + grid_spacing)
                y = start_y + row * (grid_size + grid_spacing)
                cell_rect = QRectF(x, y, grid_size, grid_size)
                
                painter.setBrush(QBrush(colors[row][col]))
                if self.isSelected():
                    painter.setPen(QPen(QColor(59, 130, 246), 1))
                else:
                    painter.setPen(QPen(QColor(65, 65, 65), 1))
                painter.drawRoundedRect(cell_rect, 1, 1)
        
        text_rect = QRectF(0, start_y + total_height + 10, self.width, 25)
        painter.setPen(QPen(QColor(55, 65, 81)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignCenter, "Heatmap")
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the node.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return QRectF(-10, -5, self.width + 20, self.height + 10)
    
    def configure_node(self):
        """
        Show heatmap configuration dialog.
        """
        dialog = HeatmapDisplayDialog(self.workflow_node, self.parent_window)
        dialog.show()


class IsotopicRatioPlotNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Initialize Isotopic ratio node using percentage symbol and curves as the actual node shape.
        
        Args:
            workflow_node: IsotopicRatioPlotNode data model
            parent_window: Parent window reference
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        self.width = 80
        self.height = 100
        
        workflow_node.configuration_changed.connect(self.update_display)
        self.update_display()
    
    def update_display(self):
        """
        Update the visual display of the node.
        """
        self.update()
    
    def paint(self, painter, option, widget=None):
        """
        Paint percentage symbol with isotope curves as the main node.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        painter.setRenderHint(QPainter.Antialiasing)
        
        center_x = self.width / 2
        center_y = 40
        
        bg_size = 45
        bg_rect = QRectF(center_x - bg_size/2, center_y - bg_size/2, bg_size, bg_size)
        
        painter.setBrush(QBrush(QColor(248, 250, 252)))
        painter.setPen(QPen(QColor(229, 231, 235), 2))
        painter.drawEllipse(bg_rect)
        
        painter.setPen(QPen(QColor(139, 92, 246), 4))
        
        top_circle = QRectF(center_x - 15, center_y - 15, 8, 8)
        painter.drawEllipse(top_circle)
        
        bottom_circle = QRectF(center_x + 7, center_y + 7, 8, 8)
        painter.drawEllipse(bottom_circle)
        
        painter.drawLine(QPointF(center_x - 8, center_y + 12), 
                        QPointF(center_x + 8, center_y - 12))
        
        curves_color = QColor(74, 144, 226)
        painter.setPen(QPen(curves_color, 2))
        
        left_path = QPainterPath()
        left_path.moveTo(center_x - 25, center_y - 10)
        left_path.quadTo(center_x - 30, center_y, center_x - 25, center_y + 10)
        painter.drawPath(left_path)
        
        right_path = QPainterPath()
        right_path.moveTo(center_x + 25, center_y - 10)
        right_path.quadTo(center_x + 30, center_y, center_x + 25, center_y + 10)
        painter.drawPath(right_path)
        
        if self.isSelected():
            painter.setPen(QPen(QColor(59, 130, 246), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(bg_rect.adjusted(-3, -3, 3, 3))
        
        text_rect = QRectF(0, 70, self.width, 25)
        painter.setPen(QPen(QColor(55, 65, 81)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignCenter, "Isotopic")
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the node.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return QRectF(-10, -5, self.width + 20, self.height + 10)
    
    def configure_node(self):
        """
        Show isotopic ratio configuration dialog.
        """
        dialog = IsotopicRatioDisplayDialog(self.workflow_node, self.parent_window)
        dialog.show()




class AIAssistantNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Initialize AI Assistant node using a sparkle/magic icon design.
        
        Args:
            workflow_node: AIAssistantNode data model
            parent_window: Parent window reference
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        self.width = 80
        self.height = 120
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #6B7280;
                padding: 2px 4px;
                background-color: rgba(249, 250, 251, 200);
                border-radius: 3px;
                border: 1px solid #E5E7EB;
            }
        """)
        self.status_label.setAlignment(Qt.AlignCenter)
        
        self.status_proxy = QGraphicsProxyWidget(self)
        self.status_proxy.setWidget(self.status_label)
        self.status_proxy.setPos(10, 85)
        self.status_proxy.resize(60, 20)
        
        workflow_node.configuration_changed.connect(self.update_status)
        self.update_status()
    
    def update_status(self):
        """
        Update status display based on connection state.
        """
        if self.workflow_node.input_data:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 10px;
                    color: #059669;
                    padding: 2px 4px;
                    background-color: rgba(236, 253, 245, 200);
                    border-radius: 3px;
                    border: 1px solid #10B981;
                }
            """)
        else:
            self.status_label.setText("Ready")
            self.status_label.setStyleSheet("""
                QLabel {
                    font-size: 10px;
                    color: #DC2626;
                    padding: 2px 4px;
                    background-color: rgba(254, 242, 242, 200);
                    border-radius: 3px;
                    border: 1px solid #EF4444;
                }
            """)
    
    def paint(self, painter, option, widget=None):
        """
        Paint magic sparkle stars for AI.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        painter.setRenderHint(QPainter.Antialiasing)
        
        center_x = self.width / 2
        center_y = 40
        
        stars = [
            (center_x, center_y - 10, 16, QColor(74, 144, 226)),
            (center_x - 20, center_y - 25, 8, QColor(116, 185, 255)),
            (center_x + 25, center_y + 15, 10, QColor(139, 92, 246)),
            (center_x - 15, center_y + 20, 6, QColor(236, 72, 153)),
        ]
        
        for x, y, size, color in stars:
            self.draw_four_point_star(painter, QPointF(x, y), size, color)
        
        text_rect = QRectF(0, 65, self.width, 20)
        painter.setPen(QPen(QColor(55, 65, 81)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignCenter, "AI Assistant")
    
    def draw_four_point_star(self, painter, center, size, color):
        """
        Draw a four-pointed star (diamond shape with points).
        
        Args:
            painter: QPainter object for drawing
            center: Center point as QPointF
            size: Size of the star
            color: Color for the star
        """
        half_size = size / 2
        
        points = [
            QPointF(center.x(), center.y() - half_size),
            QPointF(center.x() + half_size*0.3, center.y() - half_size*0.3),
            QPointF(center.x() + half_size, center.y()),
            QPointF(center.x() + half_size*0.3, center.y() + half_size*0.3),
            QPointF(center.x(), center.y() + half_size),
            QPointF(center.x() - half_size*0.3, center.y() + half_size*0.3),
            QPointF(center.x() - half_size, center.y()),
            QPointF(center.x() - half_size*0.3, center.y() - half_size*0.3),
        ]
        
        shadow_points = [QPointF(p.x() + 1, p.y() + 1) for p in points]
        painter.setBrush(QBrush(QColor(0, 0, 0, 30)))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(shadow_points)
        
        painter.setBrush(QBrush(color))
        if self.isSelected():
            painter.setPen(QPen(QColor(59, 130, 246), 2))
        else:
            painter.setPen(QPen(color.darker(150), 1))
        painter.drawPolygon(points)
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the node.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return QRectF(-10, -5, self.width + 20, self.height + 10)

    def configure_node(self):
        """
        Show AI assistant configuration dialog.
        """
        if self.parent_window:
            self.workflow_node.configure(self.parent_window)   

class EnhancedCanvasView(QGraphicsView):
    
    def __init__(self, parent_window=None):
        """
        Initialize enhanced view with improved interaction.
        
        Args:
            parent_window: Parent window reference
        """
        super().__init__()
        self.parent_window = parent_window
        self.scene = EnhancedCanvasScene(parent_window)
        self.setScene(self.scene)
        
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setAcceptDrops(True)
        
        self.setStyleSheet("""
            QGraphicsView {
                background-color: #FAFBFC;
                border: 2px solid #E2E8F0;
                border-radius: 8px;
            }
        """)
        
        self.grid_size = 20
        
        self.setup_shortcuts()
        
        self.setFocusPolicy(Qt.StrongFocus)
    
    def setup_shortcuts(self):
        """
        Set up keyboard shortcuts.
        """
        self.delete_shortcut = QShortcut(QKeySequence.Delete, self)
        self.delete_shortcut.activated.connect(self.scene.delete_selected_items)
        
        self.duplicate_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.duplicate_shortcut.activated.connect(self.scene.duplicate_selected_nodes)
        
        self.select_all_shortcut = QShortcut(QKeySequence.SelectAll, self)
        self.select_all_shortcut.activated.connect(self.scene.select_all_items)
        
        self.clear_selection_shortcut = QShortcut(QKeySequence("Escape"), self)
        self.clear_selection_shortcut.activated.connect(self.scene.clearSelection)
    
    def keyPressEvent(self, event):
        """
        Handle key press events.
        
        Args:
            event: QKeyEvent
        """
        self.scene.keyPressEvent(event)
        super().keyPressEvent(event)
    
    def drawBackground(self, painter, rect):
        """
        Enhanced grid drawing with subtle pattern.
        
        Args:
            painter: QPainter object for drawing
            rect: Rectangle area to draw
        """
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, QColor(250, 251, 252))
        gradient.setColorAt(1, QColor(248, 250, 252))
        painter.fillRect(rect, QBrush(gradient))
        
        grid_color = QColor(226, 232, 240, 60)
        painter.setPen(QPen(grid_color, 0.5))
        
        left = int(rect.left()) - (int(rect.left()) % self.grid_size)
        top = int(rect.top()) - (int(rect.top()) % self.grid_size)
        
        x = left
        while x < rect.right():
            painter.drawLine(x, rect.top(), x, rect.bottom())
            x += self.grid_size
        
        y = top
        while y < rect.bottom():
            painter.drawLine(rect.left(), y, rect.right(), y)
            y += self.grid_size
        
        dot_color = QColor(203, 213, 225, 40)
        painter.setPen(QPen(dot_color, 1))
        y = top
        while y < rect.bottom():
            x = left
            while x < rect.right():
                painter.drawPoint(x, y)
                x += self.grid_size
            y += self.grid_size
    
    def dragEnterEvent(self, event):
        """
        Handle drag enter event.
        
        Args:
            event: QDragEnterEvent
        """
        if event.mimeData().hasText():
            event.acceptProposedAction()
    
    def dragMoveEvent(self, event):
        """
        Handle drag move event.
        
        Args:
            event: QDragMoveEvent
        """
        if event.mimeData().hasText():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        """
        Args:
            event: QDropEvent
            
        Returns:
            None
        """
        if event.mimeData().hasText():
            node_type = event.mimeData().text()
            scene_pos = self.mapToScene(event.pos())
            
            snapped_x = round(scene_pos.x() / self.grid_size) * self.grid_size
            snapped_y = round(scene_pos.y() / self.grid_size) * self.grid_size
            snapped_pos = QPointF(snapped_x, snapped_y)
            
            workflow_node = None
            
            if node_type == "sample_selector":
                workflow_node = SampleSelectorNode(self.parent_window)
            elif node_type == "multiple_sample_selector":
                workflow_node = MultipleSampleSelectorNode(self.parent_window)
            elif node_type == "batch_sample_selector":
                workflow_node = BatchSampleSelectorNode(self.parent_window)
            elif node_type == "histogram_plot":
                workflow_node = HistogramPlotNode(self.parent_window)
            elif node_type == "correlation_plot": 
                workflow_node = CorrelationPlotNode(self.parent_window)
            elif node_type == "element_bar_chart_plot": 
                workflow_node = ElementBarChartPlotNode(self.parent_window)
            elif node_type == "box_plot": 
                workflow_node = BoxPlotNode(self.parent_window)
            elif node_type == "molar_ratio_plot": 
                workflow_node = MolarRatioPlotNode(self.parent_window)
            elif node_type == "pie_chart_plot":  
                workflow_node = PieChartPlotNode(self.parent_window)
            elif node_type == "element_composition_plot": 
                workflow_node = ElementCompositionPlotNode(self.parent_window)
            elif node_type == "heatmap_plot":
                workflow_node = HeatmapPlotNode(self.parent_window)
            elif node_type == "isotopic_ratio_plot":
                workflow_node = IsotopicRatioPlotNode(self.parent_window)
            elif node_type == "triangle_plot":
                workflow_node = TrianglePlotNode(self.parent_window)
            elif node_type == "single_multiple_element_plot":
                workflow_node = SingleMultipleElementPlotNode(self.parent_window)
            elif node_type == "clustering_plot":
                workflow_node = ClusteringPlotNode(self.parent_window)
            elif node_type == "ai_assistant":
                workflow_node = AIAssistantNode(self.parent_window)
                    
            if workflow_node is not None:
                self.scene.add_node(workflow_node, snapped_pos)
                event.acceptProposedAction()
            else:
                event.ignore()


class PieChartPlotNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Initialize pie chart node with clean modern design like the image.
        
        Args:
            workflow_node: PieChartPlotNode data model
            parent_window: Parent window reference
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        self.width = 80
        self.height = 100
        
        workflow_node.configuration_changed.connect(self.update_display)
        self.update_display()
    
    def update_display(self):
        """
        Update the visual display of the node.
        """
        self.update()
    
    def paint(self, painter, option, widget=None):
        """
        Paint modern pie chart like the image.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        painter.setRenderHint(QPainter.Antialiasing)
        
        pie_size = 55
        pie_x = (self.width - pie_size) / 2
        pie_y = 10
        pie_rect = QRectF(pie_x, pie_y, pie_size, pie_size)
        
        green_color = QColor(82, 196, 141)
        coral_color = QColor(255, 127, 80)
        border_color = QColor(52, 73, 94)
        
        painter.setBrush(Qt.NoBrush)
        if self.isSelected():
            painter.setPen(QPen(QColor(59, 130, 246), 4))
        else:
            painter.setPen(QPen(border_color, 4))
        painter.drawEllipse(pie_rect)
        
        painter.setBrush(QBrush(green_color))
        painter.setPen(QPen(border_color, 3))
        start_angle = 45 * 16
        span_angle = 270 * 16
        painter.drawPie(pie_rect, start_angle, span_angle)
        
        pulled_rect = pie_rect.translated(3, -2)
        painter.setBrush(QBrush(coral_color))
        painter.setPen(QPen(border_color, 3))
        coral_start = 315 * 16
        coral_span = 90 * 16
        painter.drawPie(pulled_rect, coral_start, coral_span)
        
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        center = pie_rect.center()
        
        import math
        angle1_rad = math.radians(45)
        angle2_rad = math.radians(315)
        
        radius = pie_size / 2
        
        x1 = center.x() + radius * math.cos(angle1_rad)
        y1 = center.y() - radius * math.sin(angle1_rad)
        painter.drawLine(center, QPointF(x1, y1))
        
        x2 = center.x() + radius * math.cos(angle2_rad)
        y2 = center.y() - radius * math.sin(angle2_rad)
        painter.drawLine(QPointF(center.x() + 3, center.y() - 2), QPointF(x2 + 3, y2 - 2))
        
        text_rect = QRectF(0, pie_y + pie_size + 8, self.width, 20)
        painter.setPen(QPen(QColor(55, 65, 81)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignCenter, "Pie Chart")
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the node.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return QRectF(-10, -5, self.width + 20, self.height + 10)
    
    def configure_node(self):
        """
        Show pie chart configuration dialog.
        """
        dialog = PieChartDisplayDialog(self.workflow_node, self.parent_window)
        dialog.show()


class HistogramPlotNodeItem(NodeItem):
    
    def __init__(self, workflow_node, parent_window=None):
        """
        Initialize histogram node using the icon as the actual node shape.
        
        Args:
            workflow_node: HistogramPlotNode data model
            parent_window: Parent window reference
        """
        super().__init__(workflow_node)
        self.parent_window = parent_window
        self.width = 80
        self.height = 100
        
        workflow_node.configuration_changed.connect(self.update_display)
        self.update_display()
    
    def update_display(self):
        """
        Update the visual display of the node.
        """
        self.update()
    
    def paint(self, painter, option, widget=None):
        """
        Paint the colorful bar chart icon as the main node.
        
        Args:
            painter: QPainter object for drawing
            option: Style options for the item
            widget: Optional widget being painted on
        """
        painter.setRenderHint(QPainter.Antialiasing)
        
        bar_width = 12
        bar_spacing = 4
        total_width = 4 * bar_width + 3 * bar_spacing
        start_x = (self.width - total_width) / 2
        base_y = 60
        
        colors = [QColor(255, 107, 107), QColor(255, 206, 84), QColor(78, 205, 196), QColor(129, 236, 236)]
        heights = [45, 35, 25, 15]
        
        for i in range(4):
            bar_x = start_x + i * (bar_width + bar_spacing)
            bar_rect = QRectF(bar_x + 2, base_y - heights[i] + 2, bar_width, heights[i])
            painter.setBrush(QBrush(QColor(0, 0, 0, 20)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bar_rect, 2, 2)
        
        for i, (color, height) in enumerate(zip(colors, heights)):
            bar_x = start_x + i * (bar_width + bar_spacing)
            bar_rect = QRectF(bar_x, base_y - height, bar_width, height)
            
            painter.setBrush(QBrush(color))
            if self.isSelected():
                painter.setPen(QPen(QColor(59, 130, 246), 2))
            else:
                painter.setPen(QPen(QColor(55, 65, 81), 1))
            painter.drawRoundedRect(bar_rect, 2, 2)
        
        text_rect = QRectF(0, base_y + 10, self.width, 25)
        painter.setPen(QPen(QColor(55, 65, 81)))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignCenter, "Histogram")
    
    def boundingRect(self):
        """
        Get the bounding rectangle for the node.
        
        Returns:
            QRectF: Bounding rectangle
        """
        return QRectF(-10, -5, self.width + 20, self.height + 10)
    
    def configure_node(self):
        """
        Show histogram configuration dialog.
        """
        dialog = HistogramDisplayDialog(self.workflow_node, self.parent_window)
        dialog.show()


class CanvasResultsDialog(QDialog):
    
    def __init__(self, parent=None):
        """
        Initialize enhanced canvas results dialog with modern styling.
        
        Args:
            parent: Parent window reference
        """
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Particle Analysis Workflow - Data Processing")
        self.setMinimumSize(1200, 700)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #F8FAFC;
            }
        """)
        
        self.setup_ui()
    
    def setup_ui(self):
        """
        Set up the user interface for the canvas dialog.
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        title_bar = QFrame()
        title_bar.setFixedHeight(60)
        title_bar.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4F46E5, stop:0.5 #3B82F6, stop:1 #06B6D4);
                border-radius: 8px;
            }
        """)
        title_layout = QHBoxLayout(title_bar)

        title_label = QLabel("Particle Analysis Workflow")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 20px;
                font-weight: 700;
                font-family: 'Segoe UI';
                padding: 0px 20px;
            }
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        return_button = QPushButton("Back to Main")
        return_button.setIcon(qta.icon('fa6s.house', color="#B81414"))
        return_button.setFixedSize(150, 40)
        return_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #FF6B6B, stop:0.5 #FF8E53, stop:1 #FF6B9D);
                color: white;
                border: 3px solid #FF4081;
                padding: 6px 14px;
                text-align: center;
                font-size: 12px;
                font-weight: bold;
                border-radius: 20px;
                margin-right: 15px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #FF5252, stop:0.5 #FF7043, stop:1 #FF4081);
                border: 3px solid #E91E63;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #E53935, stop:0.5 #FF5722, stop:1 #E91E63);
                border: 3px solid #AD1457;
                padding: 7px 13px 5px 15px;
            }
        """)
        return_button.clicked.connect(self.close)
        title_layout.addWidget(return_button)
        
        main_layout.addWidget(title_bar)
   
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #E2E8F0, stop:1 #CBD5E1);
                width: 10px;
                border-radius: 5px;
                margin: 2px;
            }
            QSplitter::handle:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3B82F6, stop:1 #1D4ED8);
            }
        """)
        
        palette_frame = QFrame()
        palette_frame.setFixedWidth(260)
        palette_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F9FAFB);
                border: 2px solid #E2E8F0;
                border-radius: 12px;
            }
        """)
        palette_layout = QVBoxLayout(palette_frame)
        palette_layout.setContentsMargins(5, 5, 5, 5)
        
        self.palette = NodePalette(self.parent)
        palette_layout.addWidget(self.palette)
        
        canvas_frame = QFrame()
        canvas_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F9FAFB);
                border: 2px solid #E2E8F0;
                border-radius: 12px;
            }
        """)
        canvas_layout = QVBoxLayout(canvas_frame)
        canvas_layout.setContentsMargins(15, 15, 15, 15)
        canvas_layout.setSpacing(10)
        
        toolbar_frame = QFrame()
        toolbar_frame.setFixedHeight(55)
        toolbar_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #F8FAFC, stop:1 #F1F5F9);
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
        """)
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(20, 10, 20, 10)
        
        clear_btn = self.create_button("Clear Canvas", "#EF4444")
        clear_btn.setIcon(qta.icon('fa6s.trash-can', color="#EF4444"))
        clear_btn.clicked.connect(self.clear_canvas)
        toolbar.addWidget(clear_btn)
        
        toolbar.addStretch()
        
        info_label = QLabel("Build data processing workflows • Click nodes to select • Drag to connect")
        info_label.setStyleSheet("color: #059669; font-weight: 600; font-size: 12px;")
        toolbar.addWidget(info_label)
        
        canvas_layout.addWidget(toolbar_frame)
        
        canvas_container = QFrame()
        canvas_container.setStyleSheet("""
            QFrame {
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                background-color: white;
            }
        """)
        canvas_container_layout = QVBoxLayout(canvas_container)
        canvas_container_layout.setContentsMargins(2, 2, 2, 2)
        
        self.canvas = EnhancedCanvasView(self.parent)
        canvas_container_layout.addWidget(self.canvas)
        
        canvas_layout.addWidget(canvas_container)
        
        splitter.addWidget(palette_frame)
        splitter.addWidget(canvas_frame)
        splitter.setSizes([260, 940])
        
        main_layout.addWidget(splitter)
    
    
    def create_button(self, text, color, primary=False):
        """
        Create a styled button.
        
        Args:
            text: Button text
            color: Button color
            primary: Whether this is a primary button
            
        Returns:
            QPushButton: Styled button
        """
        btn = QPushButton(text)
        btn.setMinimumHeight(36)
        
        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {color}, stop:1 {QColor(color).darker(120).name()});
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: 600;
                    font-family: 'Segoe UI';
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {QColor(color).lighter(110).name()}, stop:1 {color});
                }}
                QPushButton:pressed {{
                    background: {QColor(color).darker(130).name()};
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 white, stop:1 #F9FAFB);
                    color: {color};
                    border: 2px solid {color};
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: 600;
                    font-family: 'Segoe UI';
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {color}, stop:1 {QColor(color).darker(120).name()});
                    color: white;
                }}
            """)
        
        return btn
    
    def clear_canvas(self):
        """
        Clear the canvas with enhanced feedback.
        """
        self.canvas.scene.workflow_nodes.clear()
        self.canvas.scene.workflow_links.clear()  
        self.canvas.scene.node_items.clear()
        self.canvas.scene.link_items.clear()
        self.canvas.scene.clear()


def show_canvas_results(parent_window):
    """
    Show canvas dialog.
    
    Args:
        parent_window: Parent window reference
    """
    dialog = CanvasResultsDialog(parent_window)
    
    if hasattr(parent_window, 'current_sample') and parent_window.current_sample:
        particles = getattr(parent_window, 'sample_particle_data', {}).get(parent_window.current_sample, [])
    
    dialog.exec_()