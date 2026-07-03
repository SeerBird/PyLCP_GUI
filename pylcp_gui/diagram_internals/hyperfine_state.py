import numpy as np
from PySide6.QtCore import QRectF, Qt, QPointF
from PySide6.QtGui import QPen
from PySide6.QtWidgets import QGraphicsObject

from pylcp_gui.config import hyperfine_state_width, hyperfine_state_height, state_line_color
from pylcp_gui.diagram_internals.finestate import FineState
from pylcp_gui.util import hyperfine_key, magnetic_key


class HyperfineState(QGraphicsObject):
    def __init__(self, parent: FineState, F: float, enabled: bool = True):
        super().__init__(parent)
        self.F = F
        self.key = hyperfine_key(parent.label, self.F)
        self.enabled = enabled
        self.local_geometry = QRectF(0, -hyperfine_state_height/2,
                                     hyperfine_state_width, hyperfine_state_height)

    def magnetic_keys(self):
        return [magnetic_key(self.key, mF) for mF in self.allowed_mFs()]

    def allowed_mFs(self):
        return np.arange(-self.F,self.F+1,1)

    def boundingRect(self, /):
        return self.local_geometry.united(self.childrenBoundingRect())

    def width(self):
        return self.local_geometry.width()

    def height(self):
        return self.local_geometry.height()

    def paint(self, painter, option, /, widget = ...):
        pen = QPen(state_line_color, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(0, 0),
                         QPointF(self.width(), 0))
