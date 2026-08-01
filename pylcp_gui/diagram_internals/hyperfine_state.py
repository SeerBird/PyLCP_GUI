import numpy as np
from PySide6.QtCore import QRectF, Qt, QPointF, Signal
from PySide6.QtGui import QPen
from PySide6.QtWidgets import QGraphicsItem, QMenu, QGraphicsSimpleTextItem

from pylcp_gui.config import hf_state_width, hf_state_height, state_line_color, \
    hf_width_drawn_proportion, fine_state_width, label_color, hf_label_font
from pylcp_gui.dataframe.dataframe import hyperfine_correction
from pylcp_gui.diagram_internals.diagram_graphics_object import DiagramGraphicsObject
from pylcp_gui.diagram_internals.fine_state import FineState


class HyperfineState(DiagramGraphicsObject):
    moved = Signal(tuple)  # HyperfineKey
    delete = Signal(tuple)  # HyperfineKey

    def __init__(self, parent: FineState, F: float):
        super().__init__(parent)
        self.F = F
        self.key = (parent.label, self.F)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.local_geometry = QRectF(0, -hf_state_height / 2,
                                     hf_state_width, hf_state_height)
        self.label_item = QGraphicsSimpleTextItem(f"F = {self.F:g}", self)
        self.label_item.setFont(hf_label_font)
        self.label_item.setBrush(label_color)
        self.label_item.setY(-self.label_item.boundingRect().height())
        self.label_item.setX(self.width() * (1 - hf_width_drawn_proportion) / 2)

    def __str__(self):
        return f"'{self.key[0]}', F = {self.key[1]:g}"

    def parentItem(self, /) -> FineState:
        res = super().parentItem()
        if not isinstance(res, FineState):
            raise RuntimeError("HyperfineState somehow not a child item of FineState")
        return res

    def hf_correction(self):
        I = self.scene().I
        fine_state = self.parentItem()
        return hyperfine_correction(fine_state.J, I, self.F, fine_state.hf_coefs)

    def energy(self):
        return self.parentItem().energy + self.hf_correction()

    def magnetic_keys(self):
        return [(self.key[0], self.key[1], mF) for mF in self.allowed_mFs()]

    def allowed_mFs(self):
        return np.arange(-self.F, self.F + 1, 1)

    def boundingRect(self, /):
        return self.local_geometry

    def width(self):
        return self.local_geometry.width()

    def height(self):
        return self.local_geometry.height()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        new_pos: QPointF = value
        if self.scene():
            if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
                self.moved.emit(self.key)
                if not self.prog_changing:
                    # Only allow horizontal dragging within the bounds set by the scene
                    x = new_pos.x()
                    x = max(fine_state_width, x)
                    x = min(fine_state_width
                            + self.scene().hf_region_width()
                            - hf_state_width, x)
                    new_pos = QPointF(x, self.y())

                for mf_key in self.magnetic_keys():
                    mf_state = self.scene().magnetic_states[mf_key]
                    mf_state.progSetX(mf_state.x() - (new_pos.x() - self.x()))
        return super().itemChange(change, new_pos)

    def paint(self, painter, option, /, widget=...):
        super().paint(painter, option, widget)
        # TODO: add hover highlight
        pen = QPen(state_line_color, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        pad_proportion = (1 - hf_width_drawn_proportion) / 2
        painter.drawLine(QPointF(self.width() * pad_proportion, 0),
                         QPointF(self.width() * (1 - pad_proportion), 0))

    def contextMenuEvent(self, event):
        if not self.hovered:
            return
        event.accept()

        # region build the menu
        menu = QMenu()
        delete = menu.addAction("Delete")
        # endregion

        global_pos = event.screenPos()

        selected_action = menu.exec(global_pos)

        # region process selected action
        if selected_action == delete:
            self.delete.emit(self.key)
        # endregion

    def toggleEnabled(self):
        self.parentItem().prepareGeometryChange()
        self.setEnabled(self.isEnabled() ^ True)
        self.setVisible(self.isEnabled())
        for mf_key in self.magnetic_keys():
            mf_state = self.scene().magnetic_states[mf_key]
            mf_state.setEnabled(self.isEnabled())
            mf_state.setVisible(self.isEnabled())
