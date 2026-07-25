from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QCursor, Qt, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import QGraphicsItem

from pylcp_gui.config import state_line_color, state_line_thickness, draggable_line_grab_width
from pylcp_gui.diagram_internals.diagram_graphics_object import DiagramGraphicsObject


class DraggableLine(DiagramGraphicsObject):
    def __init__(self):
        super().__init__()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        self.top = 0
        self.bottom = 0

    def boundingRect(self,/):
        return QRectF(-draggable_line_grab_width / 2, self.top, draggable_line_grab_width, self.bottom-self.top)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos: QPointF = value

            # Only allow horizontal dragging within the bounds set by the scene
            new_x = self.scene().hf_region_resize(new_pos.x())
            return QPointF(new_x, 0)

        return super().itemChange(change, value)

    def shape(self):
        path = QPainterPath()
        path.addRect(QRectF(-draggable_line_grab_width / 2, self.top,
                            draggable_line_grab_width, self.bottom-self.top))
        return path

    def paint(self, painter, option, /, widget=...):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(state_line_color, state_line_thickness, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(0, self.top), QPointF(0, self.bottom))

    def setExtent(self, top:float, bottom:float):
        self.prepareGeometryChange()
        self.top = top
        self.bottom = bottom
