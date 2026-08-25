import math
import numpy as np
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPen, QColor, QPolygonF, QBrush, Qt, QPainter
from PySide6.QtWidgets import QGraphicsObject

from pylcp_gui.config import arrow_length, arrow_flare_angle, DiagramElementType, theme_colors, ElementColorRole
from pylcp_gui.diagram_internals.diagram_graphics_object import DiagramGraphicsObject
from pylcp_gui.util import MagneticKey


class MagneticCouplingArrow(DiagramGraphicsObject):
    """Parentless Qt graphics item that renders a coupling arrow between two magnetic sublevel lines.

    Stores pure MagneticKey tuples (key1, key2) instead of direct Qt object pointers to maintain 100% C++ Shiboken memory safety.
    """

    def __init__(self, key1: MagneticKey, key2: MagneticKey, /):
        """Initialize MagneticCouplingArrow between two magnetic state keys.

        Args:
            key1: MagneticKey of the lower magnetic state.
            key2: MagneticKey of the upper magnetic state.
        """
        super().__init__(parent=None)  # Parentless graphics object
        self.key1 = key1
        self.key2 = key2
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, False)
        self.origin_scene = QPointF()
        self.target_scene = QPointF()
        self.setZValue(-1)

    def set_anchors(self, p1: QPointF, p2: QPointF):
        """Set scene start and end points computed by Diagram.

        Args:
            p1: Scene coordinates of the first magnetic sublevel line.
            p2: Scene coordinates of the second magnetic sublevel line.
        """
        # Ensure arrow points upwards (from lower energy to upper energy)
        if p1.y() < p2.y():
            self.origin_scene = p2
            self.target_scene = p1
        else:
            self.origin_scene = p1
            self.target_scene = p2
            
        self.setPos(self.origin_scene)
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self, /):
        start = self.mapFromScene(self.origin_scene)
        end = self.mapFromScene(self.target_scene)
        
        min_x = min(start.x(), end.x()) - 10.0
        max_x = max(start.x(), end.x()) + 10.0
        min_y = min(start.y(), end.y()) - 10.0
        max_y = max(start.y(), end.y()) + 10.0
        
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

    def paint(self, painter, option, /, widget=...):
        start = self.mapFromScene(self.origin_scene)
        end = self.mapFromScene(self.target_scene)
        
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        if dy == 0 and dx == 0:
            return
            
        angle = math.atan2(dy, dx)
        
        left_fin = QPointF(
            end.x() - arrow_length * math.cos(angle - arrow_flare_angle),
            end.y() - arrow_length * math.sin(angle - arrow_flare_angle)
        )
        right_fin = QPointF(
            end.x() - arrow_length * math.cos(angle + arrow_flare_angle),
            end.y() - arrow_length * math.sin(angle + arrow_flare_angle)
        )
        
        arrow_head = QPolygonF([end, left_fin, right_fin])
        color = theme_colors[DiagramElementType.LASER_DISPLAY][ElementColorRole.NORMAL]
        
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color, 2.0, Qt.PenStyle.SolidLine))
        painter.drawLine(start, end)
        painter.drawPolygon(arrow_head)
        painter.restore()
