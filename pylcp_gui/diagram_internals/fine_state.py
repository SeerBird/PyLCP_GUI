import logging

import numpy as np
from PySide6.QtCore import Qt, Signal, QPointF, QObject, QEvent, QRectF
from PySide6.QtGui import QMouseEvent, QPainter, QPen, QPainterPath, QAction
from PySide6.QtWidgets import QGraphicsProxyWidget, \
    QApplication, QGraphicsObject, QMenu

from pylcp_gui.config import fine_state_height, fine_state_width, curly_bracket_thickness, \
    curly_bracket_width, state_line_color, state_line_thickness
from pylcp_gui.dataframe.dataframe import StateData
from pylcp_gui.diagram_internals.diagram_graphics_object import DiagramGraphicsObject

logger: logging.Logger = logging.getLogger(__name__)


class GraphicsDragFilter(QObject):
    def __init__(self, proxy: QGraphicsProxyWidget, parent=None):
        super().__init__(parent)
        self.proxy = proxy
        self.is_dragging = False
        self.is_pressed = False
        self.last_cursor_pos = QPointF()
        self.drag_start_pos = QPointF()

    def eventFilter(self, watched: QObject, event) -> bool:
        # Watching the embedded Manifold
        if not isinstance(watched, FineState):
            return False

        # region mouse button press
        if event.type() == QEvent.Type.MouseButtonPress:
            assert isinstance(event, QMouseEvent)
            if event.button() == Qt.MouseButton.LeftButton:  # drag or click on child
                # TODO: decide later which parts of the manifold you can drag it by
                '''
                # Only drag if clicking empty frame background.
                # If childAt returns an object, the user clicked an internal button/label.
                if watched.childAt(event.position().toPoint()) is None:
                '''
                self.is_pressed = True
                self.last_cursor_pos = event.globalPosition()
                self.drag_start_pos = event.globalPosition()
                event.accept()
                return True  # Stop event from reaching child widgets

        # endregion
        # region dragging
        elif event.type() == QEvent.Type.MouseMove and self.is_pressed:
            assert isinstance(event, QMouseEvent)
            if not self.is_dragging:
                distance = (event.globalPosition() - self.drag_start_pos).manhattanLength()
                if distance > QApplication.startDragDistance():
                    self.is_dragging = True
                return True
            else:
                delta = event.globalPosition() - self.last_cursor_pos
                self.proxy.setPos(self.proxy.pos() + delta)
                self.last_cursor_pos = event.globalPosition()
                self.is_dragging = True
                watched.positionChanged.emit()
                event.accept()
                return True
        # endregion
        # region release
        elif event.type() == QEvent.Type.MouseButtonRelease:
            # TODO: make the manifold clickable almost everywhere
            assert isinstance(event, QMouseEvent)
            if event.button() == Qt.MouseButton.LeftButton:
                self.is_pressed = False
                if self.is_dragging:
                    self.is_dragging = False
                    event.accept()
                    return True
                else:
                    return False
        # endregion
        return super().eventFilter(watched, event)


def paint_curly_bracket(painter, left, right, height):
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(state_line_color, curly_bracket_thickness)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    # the three termina of the curly bracket
    top = QPointF(right, -height / 2)
    bottom = QPointF(right, height / 2)
    center = QPointF(left, 0)

    # curvature intensity
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
    painter.drawPath(path)


class FineState(DiagramGraphicsObject):
    selected = Signal()
    positionChanged = Signal()
    delete = Signal()

    def __init__(self, fine_state_data: StateData):
        super().__init__()
        self.setAcceptHoverEvents(True)
        self.label = fine_state_data.label
        self.energy = fine_state_data.energy
        self.J = fine_state_data.J
        self.hf_coefs = fine_state_data.hf_coefs
        self.gJ = fine_state_data.gJ
        self.allowed_Fs = list(fine_state_data.substates.keys())
        self._width = float(fine_state_width)

    def __str__(self):
        return f"FineState:{self.label}"

    def __del__(self):
        logger.debug(f"Deleted {self}")

    def hyperfine_keys(self):
        return [(self.label, F) for F in self.allowed_Fs]

    def mouseReleaseEvent(self, event, /):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit()
            return True
        return super().mouseReleaseEvent(event)

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

    def paint(self, painter, option, /, widget=...):
        super().paint(painter, option, widget)
        pen = QPen(state_line_color, state_line_thickness, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(0, 0), QPointF(self.width() - curly_bracket_width, 0))
        paint_curly_bracket(painter, self.width() - curly_bracket_width, self.width(),
                            self.height())

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
        if hf_states.size!=0:
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
            self.delete.emit(self.label)
        elif selected_action is not None:
            hf_state = self.scene().get_hf_state(selected_action.data())
            hf_state.toggleEnabled()
            self.scene().rearrange()

        # endregion
