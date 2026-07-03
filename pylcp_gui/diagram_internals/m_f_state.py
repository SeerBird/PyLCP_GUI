from PySide6 import QtGui, QtCore
from PySide6.QtCore import Signal, Qt, QEvent, QRectF, QPointF
from PySide6.QtGui import QPalette, QIcon, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QPushButton, QToolButton, QGraphicsObject

from pylcp_gui.config import (magnetic_state_width, magnetic_state_height, state_line_color,
                              magnetic_state_spacing_half)
from pylcp_gui.diagram_internals.hyperfine_state import HyperfineState
from pylcp_gui.resources import MyIcon
from pylcp_gui import resources, config
from pylcp_gui.util import addDebugFilter, magnetic_key


class MagneticState(QGraphicsObject):

    def __init__(self, parent: HyperfineState, mF: float, enabled: bool = True):
        super().__init__(parent)
        self.mF = mF
        self.enabled = enabled
        self.key = magnetic_key(parent.key, self.mF)
        self.local_geometry = QRectF(0, -magnetic_state_height / 2,
                                     magnetic_state_width, magnetic_state_height)

    def boundingRect(self, /):
        return self.local_geometry

    def __str__(self):
        return f"MFState:{self.key}"

    def width(self):
        return self.local_geometry.width()

    def height(self):
        return self.local_geometry.height()

    def paint(self, painter, option, /, widget=...):
        # TODO: maybe fill background
        pen = QPen(state_line_color, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(magnetic_state_spacing_half, 0),
                         QPointF(self.local_geometry.width() - magnetic_state_spacing_half, 0))
