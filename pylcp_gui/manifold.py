from PySide6.QtCore import QSize, Qt, Signal, QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QSizePolicy, QGraphicsProxyWidget, \
    QGraphicsItem

from pylcp_gui import config


class Manifold(QFrame):
    clicked = Signal()
    positionChanged = Signal(QPointF)

    def __init__(self, label: str, energy: float):
        # TODO: maybe an energy, maybe an F-number,
        super().__init__()
        self.label = label
        self.energy = energy
        # region the QWidget container this object is a proxy of
        self.container = QFrame()
        self.layout = QGridLayout(self.container)
        self.layout.addWidget(QLabel(label))
        self.layout.addWidget(QLabel(f"H_0: {energy:.3E}"))
        self.setFrameShape(QFrame.Shape.HLine)  # TODO: make this contain multiple states
        self.setFixedSize(config.manifold_height, config.manifold_width)
        # endregion


    def mouseReleaseEvent(self, event, /):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            return
        super().mouseReleaseEvent(event)


