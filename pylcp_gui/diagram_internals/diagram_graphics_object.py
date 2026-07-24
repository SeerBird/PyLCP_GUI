from abc import abstractmethod, ABC
from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPen, Qt
from PySide6.QtWidgets import QGraphicsObject

from pylcp_gui.config import state_line_thickness, debug_highlight

if TYPE_CHECKING:
    from pylcp_gui.diagram_internals.diagram import Diagram


class DiagramGraphicsObject(QGraphicsObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.prog_changing = False

    def scene(self, /) -> Diagram:
        scene = super().scene()
        # TODO: python typing is disgusting. is there really no way to do this cleanly?
        #  if not isinstance(scene, Diagram):
        #    raise RuntimeError("PyLCP_GUI QGraphicsObjects should only go on the Diagram, what?")
        return scene

    def width(self) -> float:
        raise NotImplementedError(f"{self.__class__} is an abstract class")

    def height(self) -> float:
        raise NotImplementedError(f"{self.__class__} is an abstract class")

    def paint(self, painter, option, /, widget=...):
        pen = QPen(debug_highlight, state_line_thickness, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        painter.save()
        painter.setPen(pen)
        painter.drawRect(QRectF(0, -self.height() / 2, self.width(), self.height()))
        painter.restore()

    def progSetX(self, x, /):
        self.prog_changing = True
        super().setX(x)
        self.prog_changing = False

    def progSetY(self, y, /):
        self.prog_changing = True
        super().setY(y)
        self.prog_changing = False

    def progSetPos(self, pos, /):
        self.prog_changing = True
        super().setPos(pos)
        self.prog_changing = False
