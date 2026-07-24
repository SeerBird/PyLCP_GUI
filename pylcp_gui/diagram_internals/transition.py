import logging

import numpy as np
from PySide6.QtCore import Qt, QRectF, Signal, QObject, QPointF
from PySide6.QtGui import QPainterPath, QPainterPathStroker, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QMenu, QGraphicsObject

from pylcp_gui import config, util
from pylcp_gui.config import transition_hover_color, transition_color
from pylcp_gui.dataframe.dataframe import TransitionData
from pylcp_gui.diagram_internals.laser_display import LaserDisplay
from pylcp_gui.diagram_internals.finestate import FineState
from pylcp_gui.config import transition_thickness


logger: logging.Logger = logging.getLogger(__name__)
class Transition(QGraphicsObject):
    delete = Signal()
    add_laser = Signal()
    edit = Signal()

    def __init__(self, transition_data: TransitionData, manifold1: FineState, manifold2: FineState):
        super().__init__()
        self.gamma = transition_data.gamma
        self.hovered_over = False
        self.setZValue(-1)
        self.setAcceptHoverEvents(True)
        self.p1 = QPointF()
        self.p2 = QPointF()
        energies = np.asarray([manifold1.energy, manifold2.energy])
        keys = np.asarray([manifold1.label, manifold2.label])
        # keys are in increasing rest frame energy order
        self.keys = tuple(keys[util.sort_float_then_string(energies, keys)])

    def setAnchors(self, p1, p2):
        self.p1 = p1
        self.p2 = p2
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self, /):
        return QRectF(self.p1, self.p2).normalized().adjusted(-transition_thickness,
                                                              -transition_thickness,
                                                              transition_thickness,
                                                              transition_thickness)

    def shape(self, /):
        linePath = QPainterPath()
        linePath.moveTo(self.p1)
        linePath.lineTo(self.p2)
        stroker = QPainterPathStroker()
        stroker.setWidth(transition_thickness)
        return stroker.createStroke(linePath)

    def paint(self, painter, option, /, widget=...):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        lineColor = transition_hover_color if self.hovered_over else transition_color
        painter.setPen(QPen(lineColor, config.transition_line_thickness, Qt.PenStyle.SolidLine))
        painter.drawLine(self.p1, self.p2)

    def hoverEnterEvent(self, event, /):
        self.hovered_over = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event, /):
        self.hovered_over = False
        self.update()
        super().hoverEnterEvent(event)

    def contextMenuEvent(self, event):
        event.accept()

        # region build the menu
        menu = QMenu()
        add_laser = menu.addAction("Add laser beam")
        delete = menu.addAction("Delete transition")
        # endregion

        global_pos = event.screenPos()

        selected_action = menu.exec(global_pos)

        # region process selected action
        if selected_action == add_laser:
            self.add_laser.emit()
        elif selected_action == delete:
            self.delete.emit()
        # endregion
