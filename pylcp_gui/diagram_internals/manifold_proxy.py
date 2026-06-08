from PySide6.QtCore import QEvent, QCoreApplication
from PySide6.QtGui import QHoverEvent
from PySide6.QtWidgets import QGraphicsProxyWidget, QGraphicsItem, QGraphicsSceneHoverEvent

from pylcp_gui.util import addDebugFilter


class ManifoldProxy(QGraphicsProxyWidget):
    def __init__(self, manifold):
        super().__init__()
        self.manifold = manifold
        self.setWidget(manifold)
        # self.setAcceptHoverEvents(True)
        # self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        # self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        # self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
