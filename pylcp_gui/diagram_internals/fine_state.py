import logging
from typing import override

import numpy as np
from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QPainterPath, QPainterPathStroker, QAction
from PySide6.QtWidgets import QGraphicsObject, QMenu, QGraphicsSimpleTextItem

from pylcp_gui.config import fine_state_height, fine_state_width, curly_bracket_thickness, \
    curly_bracket_width, state_line_color, state_line_thickness, fine_label_font, label_color, \
    DiagramElementType, fine_state_hover_width
from pylcp_gui.dataframe.dataframe import StateData
from pylcp_gui.diagram_internals.diagram_graphics_object import DiagramGraphicsObject
from pylcp_gui.util import HyperfineKey

logger: logging.Logger = logging.getLogger(__name__)


def get_curly_bracket_path(left: float, right: float, height: float) -> QPainterPath:
    top = QPointF(right, -height / 2)
    bottom = QPointF(right, height / 2)
    center = QPointF(left, 0)
    ctrl_offset = (right - left) * 0.6

    path = QPainterPath()
    path.moveTo(top)
    path.cubicTo(
        QPointF(top.x() - ctrl_offset, top.y()),
        QPointF(center.x() + ctrl_offset, center.y() - height * 0.1),
        center
    )
    path.cubicTo(
        QPointF(center.x() + ctrl_offset, center.y() + height * 0.1),
        QPointF(bottom.x() - ctrl_offset, bottom.y()),
        bottom
    )
    return path


def paint_curly_bracket(painter, left, right, height, color=state_line_color):
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(color, curly_bracket_thickness)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawPath(get_curly_bracket_path(left, right, height))


class FineState(StateData, DiagramGraphicsObject):
    delete = Signal()

    def __init__(self, state_data: StateData):
        DiagramGraphicsObject.__init__(self)
        StateData.__init__(self, state_data)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, True)
        self._width = float(fine_state_width)
        self.label_item = QGraphicsSimpleTextItem(self.label, self)
        self.label_item.setFont(fine_label_font)
        self.label_item.setBrush(label_color)
        self.label_item.setY(-self.label_item.boundingRect().height())

    def __str__(self):
        return f"FineState:{self.label}"

    def __del__(self):
        logger.debug(f"Deleted {self}")

    @property
    def active_substates(self):
        substates = {}
        for hf_key in self.hyperfine_keys():
            hf_state = self.scene().get_hf_state(hf_key)
            active_mFs = [m_state.mF for m_state in hf_state.magnetic_states if m_state.enabled]
            substates[hf_key.F] = active_mFs
        return substates

    def enabledChildrenBoundingRect(self):
        rect = QRectF()
        for child in self.childItems():
            if child.isEnabled():
                child_rect_in_parent = self.mapRectFromItem(child, child.boundingRect())
                if rect.isEmpty():
                    rect = child_rect_in_parent
                else:
                    rect = rect.united(child_rect_in_parent)
        return rect

    def boundingRect(self, /):
        height = self.height()
        return QRectF(0, -height / 2, self._width, height)

    def width(self):
        return self._width

    def height(self):
        return max(fine_state_height, self.enabledChildrenBoundingRect().height())

    def shape(self, /):
        path = QPainterPath()
        path.moveTo(0, 0)
        path.lineTo(self.width() - curly_bracket_width, 0)
        path.addPath(
            get_curly_bracket_path(self.width() - curly_bracket_width, self.width(), self.height()))

        stroker = QPainterPathStroker()
        stroker.setWidth(fine_state_hover_width)
        return stroker.createStroke(path)

    def paint(self, painter, option, /, widget=...):
        super().paint(painter, option, widget)
        color = self.get_theme_color(DiagramElementType.FINE_STATE)
        pen = QPen(color, state_line_thickness, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(0, 0), QPointF(self.width() - curly_bracket_width, 0))
        paint_curly_bracket(painter, self.width() - curly_bracket_width, self.width(),
                            self.height(), color)

    def contextMenuEvent(self, event):
        if not self.hovered:
            return
        event.accept()

        # region build the menu
        menu = QMenu()
        delete = menu.addAction("Delete")
        add_hf_menu = QMenu("Add hyperfine state")
        hf_states = np.asarray([self.scene().get_hf_state(key) for key in self.hyperfine_keys()])
        hf_states = hf_states[~np.asarray([hf_state.isEnabled() for hf_state in hf_states])]
        if hf_states.size != 0:
            actions = []
            for hf_state in hf_states:
                action = QAction(f"F = {hf_state.F}")
                actions.append(action)
                action.setData(hf_state.key)
                add_hf_menu.addAction(action)
            menu.addMenu(add_hf_menu)
        # endregion

        global_pos = event.screenPos()

        selected_action = menu.exec(global_pos)

        # region process selected action
        if selected_action == delete:
            self.delete.emit()
        elif selected_action is not None:
            hf_state = self.scene().get_hf_state(selected_action.data())
            hf_state.toggleEnabled()
            self.scene().rearrange()

        # endregion
