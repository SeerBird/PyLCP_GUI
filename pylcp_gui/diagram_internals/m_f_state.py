from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPen
from PySide6.QtWidgets import QGraphicsObject

from pylcp_gui.config import (magnetic_state_width, magnetic_state_height, state_line_color,
                              magnetic_state_spacing_half, mf_add_color, mf_remove_color, theme_colors, DiagramElementType, ElementColorRole)
from pylcp_gui.diagram_internals.diagram_graphics_object import DiagramGraphicsObject
from pylcp_gui.diagram_internals.hyperfine_state import HyperfineState


class MagneticState(DiagramGraphicsObject):

    def __init__(self, hf_state: HyperfineState, mF: float, enabled: bool = True):
        super().__init__(hf_state)
        self.mF = mF
        self.enabled = enabled
        self.key = (hf_state.key[0], hf_state.key[1], self.mF)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, False)
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
        super().paint(painter, option, widget)
        colors = theme_colors[DiagramElementType.MAGNETIC_STATE]
        if self.hovered:
            if self.enabled:
                color = colors[ElementColorRole.REMOVE_HOVER]
            else:
                color = colors[ElementColorRole.ADD_HOVER]
        elif self.enabled:
            color = colors[ElementColorRole.NORMAL]
        else:
            color = colors[ElementColorRole.DISABLED]

        pen = QPen(color, 5., Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(magnetic_state_spacing_half, 0),
                         QPointF(self.local_geometry.width() - magnetic_state_spacing_half, 0))
    def mousePressEvent(self, event, /):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
        else:
            super().mousePressEvent(event)
    def mouseReleaseEvent(self, event, /):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self.enabled ^= True
            self.update()
            if self.scene() is not None and hasattr(self.scene(), 'notify_diagram_changed'):
                from pylcp_gui.util import DiagramChangeType
                self.scene().notify_diagram_changed(DiagramChangeType.MAGNETIC_STATE_TOGGLED, self.key)
        else:
            super().mouseReleaseEvent(event)


