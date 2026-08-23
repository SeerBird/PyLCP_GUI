import math

from PySide6.QtCore import QPointF, QRectF, Signal
from PySide6.QtGui import QPen, QColor, QPolygonF, QBrush, Qt, QPainterPath, QPainterPathStroker
from PySide6.QtWidgets import QMenu, QGraphicsObject

from pylcp_gui.config import state_line_color, arrow_length, arrow_flare_angle, \
    state_line_thickness, debug_highlight, debug_thickness, laser_display_hover_width, \
    DiagramElementType
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
        self.data = data
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAnchors(QPointF(), QPointF(), 0)

    # region get LaserDisplayData properties
    @property
    def freq(self):
        return self.data.freq

    @property
    def keys(self):
        return self.data.keys

    @property
    def upwards(self):
        return self.data.upwards
    # endregion

    def detuning(self):
        lower_state = self.scene().hf_states[self.keys[0]]
        upper_state = self.scene().hf_states[self.keys[1]]
        return self.freq - (abs(upper_state.energy() - lower_state.energy()))

    def paint(self, painter, option, /, widget=...):
        # region debug frame
        pen = QPen(debug_highlight, debug_thickness, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        painter.save()
        painter.setPen(pen)
        painter.drawRect(self.boundingRect())
        painter.restore()
        # endregion
        color = self.get_theme_color(DiagramElementType.LASER_DISPLAY)
        arrow_start = self.mapFromScene(self.origin)
        arrow_end = self.mapFromScene(self.target + QPointF(0, self.delta))
        draw_arrow(painter, arrow_start, arrow_end, color)
        if self.delta != 0:
            draw_arrow(painter, arrow_end, self.mapFromScene(self.target), color)
            draw_dash_line(painter, arrow_end.y(), self.scene().hf_region_width(), color)

    def keys_ordered(self):
        """:return keys of the origin and target states, in that order"""
        if self.upwards:
            return self.keys
        else:
            return self.keys[1], self.keys[0]

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

    def shape(self):
        if self.scene() is None:
            return QPainterPath()

        path = QPainterPath()
        arrow_start = self.mapFromScene(self.origin)
        arrow_end = self.mapFromScene(self.target + QPointF(0, self.delta))

        # Main arrow line from origin state to target / dashed line
        path.moveTo(arrow_start)
        path.lineTo(arrow_end)

        if self.delta != 0:
            # Delta indicator arrow between target state line and dashed line
            target_pt = self.mapFromScene(self.target)
            path.moveTo(arrow_end)
            path.lineTo(target_pt)

            # Horizontal dashed line across hyperfine region
            path.moveTo(0, arrow_end.y())
            path.lineTo(self.scene().hf_region_width(), arrow_end.y())

        stroker = QPainterPathStroker()
        stroker.setWidth(laser_display_hover_width)
        return stroker.createStroke(path)

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
            self.delete.emit(self.keys, self.freq)
        # endregion
