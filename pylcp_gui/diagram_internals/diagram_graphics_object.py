from abc import abstractmethod, ABC
from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPen, QColor, Qt, QTransform
from PySide6.QtWidgets import QGraphicsObject

from pylcp_gui.config import state_line_thickness, debug_highlight, debug_thickness, theme_colors, DiagramElementType, ElementColorRole

if TYPE_CHECKING:
    from pylcp_gui.diagram_internals.diagram import Diagram


class DiagramGraphicsObject(QGraphicsObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.prog_changing = False
        self.hovered = False
        self.setAcceptHoverEvents(True)

    def get_theme_color(self, element_type: DiagramElementType) -> QColor:
        element_colors = theme_colors.get(element_type, theme_colors[DiagramElementType.FINE_STATE])
        if self.isSelected():
            return element_colors.get(ElementColorRole.SELECTED, element_colors[ElementColorRole.NORMAL])
        elif self.hovered:
            return element_colors.get(ElementColorRole.HOVER, element_colors[ElementColorRole.NORMAL])
        return element_colors.get(ElementColorRole.NORMAL, QColor(255, 255, 255))

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
        pen = QPen(debug_highlight, debug_thickness, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        painter.save()
        painter.setPen(pen)
        painter.drawRect(self.boundingRect())
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

    def update_hover_state(self, scene_pos):
        if not self.scene() or not self.scene().views():
            is_direct = True
        else:
            view = self.scene().views()[0]
            top_item = self.scene().itemAt(scene_pos, view.transform())
            # Directly hovered if top_item is self, or a non-DiagramGraphicsObject child (e.g. text label)
            is_direct = (top_item is self) or (
                top_item is not None
                and top_item.parentItem() is self
                and not isinstance(top_item, DiagramGraphicsObject)
            )
        if self.hovered != is_direct:
            self.hovered = is_direct
            self.update()

    def _get_scene_pos(self, event):
        if hasattr(event, 'scenePos'):
            return event.scenePos()
        elif hasattr(event, 'pos'):
            return self.mapToScene(event.pos())
        return self.scenePos()

    def hoverEnterEvent(self, event, /):
        self.update_hover_state(self._get_scene_pos(event))

    def hoverMoveEvent(self, event, /):
        self.update_hover_state(self._get_scene_pos(event))

    def hoverLeaveEvent(self, event, /):
        if self.hovered:
            self.hovered = False
            self.update()
        parent = self.parentItem()
        if isinstance(parent, DiagramGraphicsObject):
            parent.update_hover_state(self._get_scene_pos(event))
