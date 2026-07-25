import math

from PySide6.QtCore import QPointF, QRectF, Signal
from PySide6.QtGui import QPen, QColor, QPolygonF, QBrush, Qt
from PySide6.QtWidgets import QMenu

from pylcp_gui.config import state_line_color, arrow_length, arrow_flare_angle, \
    state_line_thickness, debug_highlight, debug_thickness
from pylcp_gui.dataframe.dataframe import LaserDisplayData
from pylcp_gui.diagram_internals.diagram_graphics_object import DiagramGraphicsObject


def draw_arrow(painter, start: QPointF, end: QPointF, color: QColor):
    dx = end.x() - start.x()
    dy = end.y() - start.y()

    if dy == 0:
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

    painter.save()  # Protect the painter's existing state
    painter.setBrush(QBrush(color))
    painter.setPen(QPen(color, state_line_thickness, Qt.PenStyle.SolidLine))
    painter.drawLine(start, end)
    painter.drawPolygon(arrow_head)
    painter.restore()  # Revert painter settings back to normal


def draw_dash_line(painter, y: float, width: float, color: QColor):
    start = QPointF(0, y)
    end = QPointF(width, y)
    painter.save()  # Protect the painter's existing state
    painter.setBrush(QBrush(color))
    painter.setPen(QPen(color, state_line_thickness, Qt.PenStyle.DashLine))
    painter.drawLine(start, end)
    painter.restore()  # Revert painter settings back to normal


class LaserDisplay(DiagramGraphicsObject):
    delete = Signal(tuple, float)  # tuple[HyperfineKey, HyperfineKey], float (freq)

    def __init__(self, data: LaserDisplayData, /):
        super().__init__()
        self.freq, self._keys, self.upwards = data.freq, data.keys, data.upwards
        self.setAnchors(QPointF(), QPointF(), 0)

    def paint(self, painter, option, /, widget=...):
        # region debug frame
        pen = QPen(debug_highlight, debug_thickness, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        painter.save()
        painter.setPen(pen)
        painter.drawRect(self.boundingRect())
        painter.restore()
        # endregion
        arrow_start = self.mapFromScene(self.origin)
        arrow_end = self.mapFromScene(self.target + QPointF(0, self.delta))
        draw_arrow(painter, arrow_start, arrow_end, state_line_color)
        draw_dash_line(painter, arrow_end.y(), self.scene().hf_region_width(), state_line_color)

    def keys(self):
        """:return keys of the origin and target states, in that order"""
        if self.upwards:
            return self._keys
        else:
            return self._keys[1], self._keys[0]

    def setAnchors(self, origin: QPointF, target: QPointF, delta: float):
        self.origin = origin
        self.target = target
        self.delta = delta  # dotted line y - target y
        self.prepareGeometryChange()
        self.update()

    def width(self):
        return abs(self.origin.x() - self.target.x())

    def height(self):
        return self.bot() - self.top()

    def top(self):
        return min(self.origin.y(), min(self.target.y(), self.target.y() + self.delta))

    def bot(self):
        return max(self.origin.y(), max(self.target.y(), self.target.y() + self.delta))

    def boundingRect(self, /):
        top = self.mapFromScene(QPointF(0, self.top())).y()
        return QRectF(0, top, self.scene().hf_region_width(), self.height())

    def contextMenuEvent(self, event):
        event.accept()

        # region build the menu
        menu = QMenu()
        delete = menu.addAction("Delete")
        # endregion

        global_pos = event.screenPos()

        selected_action = menu.exec(global_pos)

        # region process selected action
        if selected_action == delete:
            self.delete.emit(self._keys, self.freq)
        # endregion
