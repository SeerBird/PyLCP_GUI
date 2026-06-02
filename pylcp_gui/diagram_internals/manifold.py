from PySide6.QtCore import QSize, Qt, Signal, QPointF, QObject, QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QSizePolicy, QGraphicsProxyWidget, \
    QGraphicsItem, QApplication

from pylcp_gui import config


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
        assert isinstance(watched, Manifold)
        if not isinstance(watched, QFrame):
            return False

        # region mouse button press
        if event.type() == QEvent.Type.MouseButtonPress:
            assert isinstance(event, QMouseEvent)
            if event.button() == Qt.MouseButton.LeftButton:
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
            self.is_pressed = False
            if self.is_dragging:
                self.is_dragging = False
                event.accept()
                return True
            else:
                return False

        # endregion
        return super().eventFilter(watched, event)


class Manifold(QFrame):
    clicked = Signal()
    positionChanged = Signal()

    def __init__(self, label: str, energy: float):
        # TODO: maybe an energy, maybe an F-number,
        super().__init__()
        self.label = label
        self.energy = energy
        self.layout = QGridLayout(self)
        self.layout.addWidget(QLabel(label))
        self.layout.addWidget(QLabel(f"H_0: {energy:.3E}"))
        self.setFrameShape(QFrame.Shape.HLine)  # TODO: make this contain multiple states
        self.setFixedSize(config.manifold_height, config.manifold_width)

    def mouseReleaseEvent(self, event, /):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            return
        super().mouseReleaseEvent(event)
