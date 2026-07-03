import logging

from PySide6.QtCore import Qt, Signal, QPointF, QObject, QEvent, QRectF
from PySide6.QtGui import QMouseEvent, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import QGraphicsProxyWidget, \
    QApplication, QGraphicsObject

from pylcp_gui.config import fine_state_height, fine_state_width, curly_bracket_thickness, \
    curly_bracket_width, state_line_color, state_line_thickness
from pylcp_gui.dataframe.dataframe import StateData
from pylcp_gui.util import hyperfine_key

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

    pen = QPen(Qt.GlobalColor.white, curly_bracket_thickness)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    # the three termina of the curly bracket
    top = QPointF(right, -height / 2)
    bottom = QPointF(right, height / 2)
    center = QPointF(0, 0)

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


class FineState(QGraphicsObject):
    selected = Signal()
    positionChanged = Signal()
    delete = Signal()

    def __init__(self, fine_state_data: StateData):
        super().__init__()
        self.setAcceptHoverEvents(True)
        self.label = fine_state_data.label
        self.energy = fine_state_data.energy
        self.L = fine_state_data.L
        self.J = fine_state_data.J
        self.gamma = fine_state_data.gamma
        self.hf_coefs = fine_state_data.hf_coefs
        self.allowed_Fs = list(fine_state_data.substates.keys())
        self.local_geometry = QRectF(0, -fine_state_height / 2,
                                     fine_state_width, fine_state_height)

    def __str__(self):
        return f"FineState:{self.label}"

    def __del__(self):
        logger.debug(f"Deleted {self}")

    def hyperfine_keys(self):
        return [hyperfine_key(self.label, F) for F in self.allowed_Fs]

    def mouseReleaseEvent(self, event, /):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit()
            return True
        return super().mouseReleaseEvent(event)

    def boundingRect(self, /):
        return self.local_geometry.united(self.childrenBoundingRect())

    def width(self):
        return self.local_geometry.width()

    def height(self):
        return self.boundingRect().height()

    def paint(self, painter, option, /, widget=...):
        pen = QPen(state_line_color, state_line_thickness, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(0, 0), QPointF(self.width() - curly_bracket_width, 0))
        paint_curly_bracket(painter, self.width() - curly_bracket_width, self.width(),
                            self.height())
