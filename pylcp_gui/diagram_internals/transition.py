from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainterPath, QPainterPathStroker, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem

from pylcp_gui import config
from pylcp_gui.config import transition_hover_color, transition_color
from pylcp_gui.diagram_internals.manifold import Manifold
from pylcp_gui.config import transition_thickness


class Transition(QGraphicsItem):
    def __init__(self, manifold1: Manifold, manifold2: Manifold, d_q):
        super().__init__()
        self.hovered_over = False
        self.manifold1 = manifold1
        self.manifold2 = manifold2
        # TODO: is there a point maintaining an explicit order-independence? or rather
        #  an order-indifference?
        self.d_q = d_q
        self.setZValue(-1)
        self.manifold1.positionChanged.connect(self.trackNodes)
        self.manifold2.positionChanged.connect(self.trackNodes)

    def labels(self):
        return frozenset([self.manifold1.label, self.manifold2.label])

    def trackNodes(self):
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self, /):
        return QRectF(*self.get_nodes()).normalized().adjusted(-transition_thickness,
                                                               -transition_thickness,
                                                               transition_thickness,
                                                               transition_thickness)

    def shape(self, /):
        p1, p2 = self.get_nodes()
        linePath = QPainterPath()
        linePath.moveTo(p1)
        linePath.lineTo(p2)
        stroker = QPainterPathStroker()
        stroker.setWidth(transition_thickness)
        return stroker.createStroke(linePath)

    def paint(self, painter, option, /, widget=...):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        p1, p2 = self.get_nodes()
        lineColor = transition_hover_color if self.hovered_over else transition_color
        painter.setPen(QPen(lineColor, config.transition_line_thickness, Qt.PenStyle.SolidLine))
        painter.drawLine(p1, p2)

    def hoverEnterEvent(self, event, /):
        self.hovered_over = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event, /):
        self.hovered_over = False
        self.update()
        super().hoverEnterEvent(event)

    def get_nodes(self):
        return (self.manifold1.geometry().center(),
                self.manifold2.geometry().center())
