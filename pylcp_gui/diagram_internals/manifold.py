import logging

from PySide6.QtCore import QSize, Qt, Signal, QPointF, QObject, QEvent, QCoreApplication
from PySide6.QtGui import QMouseEvent, QHoverEvent, QIcon
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QSizePolicy, QGraphicsProxyWidget, \
    QGraphicsItem, QApplication, QGroupBox, QPushButton

from pylcp_gui import config
from pylcp_gui.dataframe.dataframe import ManifoldData
from pylcp_gui.diagram_internals.m_f_state import MFState
from pylcp_gui.util import addDebugFilter

logger: logging.Logger = logging.getLogger(__name__)


class GraphicsDragFilter(QObject):
    def __init__(self, proxy: QGraphicsProxyWidget, parent=None):
        super().__init__(parent)
        self.proxy = proxy
        self.is_dragging = False
        self.is_pressed = False
        self.last_cursor_pos = QPointF()
        self.drag_start_pos = QPointF()

    def eventFilter(self, watched: QObject, event) -> bool:
        # Watching the embedded Manifold
        if not isinstance(watched, Manifold):
            return False

        # region mouse button press
        if event.type() == QEvent.Type.MouseButtonPress:
            assert isinstance(event, QMouseEvent)
            if event.button() == Qt.MouseButton.LeftButton:  # drag or click on child
                # TODO: decide later which parts of the manifold you can drag it by
                '''
                # Only drag if clicking empty frame background.
                # If childAt returns an object, the user clicked an internal button/label.
                if watched.childAt(event.position().toPoint()) is None:
                '''
                self.is_pressed = True
                self.last_cursor_pos = event.globalPosition()
                self.drag_start_pos = event.globalPosition()
                event.accept()
                return True  # Stop event from reaching child widgets

        # endregion
        # region dragging
        elif event.type() == QEvent.Type.MouseMove and self.is_pressed:
            assert isinstance(event, QMouseEvent)
            if not self.is_dragging:
                distance = (event.globalPosition() - self.drag_start_pos).manhattanLength()
                if distance > QApplication.startDragDistance():
                    self.is_dragging = True
                return True
            else:
                delta = event.globalPosition() - self.last_cursor_pos
                self.proxy.setPos(self.proxy.pos() + delta)
                self.last_cursor_pos = event.globalPosition()
                self.is_dragging = True
                watched.positionChanged.emit()
                event.accept()
                return True
        # endregion
        # region release
        elif event.type() == QEvent.Type.MouseButtonRelease:
            # TODO: make the manifold clickable almost everywhere
            assert isinstance(event, QMouseEvent)
            if event.button() == Qt.MouseButton.LeftButton:
                self.is_pressed = False
                if self.is_dragging:
                    self.is_dragging = False
                    event.accept()
                    return True
                else:
                    return False
        # endregion
        return super().eventFilter(watched, event)


class Manifold(QGroupBox):
    selected = Signal()
    positionChanged = Signal()
    delete = Signal()

    def __init__(self, manifold_data: ManifoldData):
        label, energy, F, J, gamma = (manifold_data.label, manifold_data.energy,
                                      manifold_data.F, manifold_data.J, manifold_data.gamma)
        super().__init__(label)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.label = label
        self.energy = energy
        self.states: list[MFState] = []
        self.F = F
        self.J = J
        self.gamma = gamma
        self._layout = QGridLayout(self)
        self.top_layout = QGridLayout()
        self._layout.addLayout(self.top_layout, 0, 0)
        self.bottom_layout = QGridLayout()
        self._layout.addLayout(self.bottom_layout, 1, 0)
        # region top panel - labels and stuff
        F_label = QLabel(f"F = {self.F}")
        self.top_layout.addWidget(F_label, 0, 0)

        self.top_layout.setColumnMinimumWidth(1, config.manifold_top_layout_spacer_width)

        F_label = QLabel(f"J = {self.J}")
        self.top_layout.addWidget(F_label, 0, 2)

        self.top_layout.setColumnMinimumWidth(3, config.manifold_top_layout_spacer_width)

        E_label = QLabel(f"E = {energy:.3E}")
        self.top_layout.addWidget(E_label, 0, 4)

        self.top_layout.setColumnMinimumWidth(5, config.manifold_top_layout_spacer_width)

        gamma_label = QLabel(f"Γ = {self.gamma:.3E}")
        self.top_layout.addWidget(gamma_label, 0, 6)

        self.top_layout.setColumnMinimumWidth(7, config.manifold_top_layout_spacer_width)

        delete_button = QPushButton(QIcon.fromTheme(QIcon.ThemeIcon.EditDelete), "")
        delete_button.clicked.connect(self.delete)
        self.top_layout.addWidget(delete_button, 0, 8, Qt.AlignmentFlag.AlignRight)
        # endregion
        # region bottom panel - m_F states
        mF_label = QLabel("m_F:")
        self.bottom_layout.addWidget(mF_label, 0, 0)
        self.bottom_layout.setColumnStretch(0, 0)
        for mF in range(-F, F + 1):
            state = MFState(mF)
            self.states.append(state)
            label = QLabel(f"{mF}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.bottom_layout.addWidget(label, 0, F + mF + 1)
            self.bottom_layout.addWidget(state, 1, F + mF + 1)
        self.bottom_layout.setColumnStretch(2 * F+2, 1000000)
        # endregion

    def __str__(self):
        return "Manifold"

    def __del__(self):
        logger.debug(f"Deleted {self}")

    def mouseReleaseEvent(self, event, /):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit()
            return True
        return super().mouseReleaseEvent(event)
