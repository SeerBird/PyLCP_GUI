from __future__ import annotations

import logging
import sys
import traceback
import weakref
from inspect import signature
from typing import Any, TYPE_CHECKING, Iterable, Literal, Callable, TypeAlias, NamedTuple
from enum import Enum, auto
from dataclasses import dataclass
import numpy as np
from PySide6.QtCore import QObject, QEvent, QPointF, QCoreApplication
from PySide6.QtGui import QMouseEvent, QHoverEvent, QPalette, QColor
from PySide6.QtWidgets import QFrame, QLineEdit, QGridLayout, QWidget, QGraphicsProxyWidget, \
    QApplication, QStyleFactory
from pylcp import magField
from pylcp.hamiltonians import wig3j, wig6j

if TYPE_CHECKING:
    from pylcp_gui.dataframe.dataframe import StateData
    from pylcp_gui.diagram_internals import FineState

logger: logging.Logger = logging.getLogger(__name__)

# region typing
class DiagramChangeType(Enum):
    FINE_STATE_ADDED = auto()
    FINE_STATE_DELETED = auto()
    HYPERFINE_STATE_CHANGED = auto()
    MAGNETIC_STATE_TOGGLED = auto()
    TRANSITION_DELETED = auto()
    LASER_DISPLAY_DELETED = auto()
    GENERIC_REFRESH = auto()


@dataclass
class DiagramChangeEvent:
    change_type: DiagramChangeType
    target: Any = None


class HyperfineKey(NamedTuple):
    label: str
    F: float

    def __str__(self) -> str:
        return f"{self.label}_F{self.F:g}"


class MagneticKey(NamedTuple):
    label: str
    F: float
    mF: float


class FineTransitionKey(NamedTuple):
    lower_label: str
    upper_label: str

    def __str__(self) -> str:
        return f"{self.lower_label}->{self.upper_label}"


class HFTransitionKey(NamedTuple):
    lower_key: HyperfineKey
    upper_key: HyperfineKey

    def __str__(self) -> str:
        return f"{self.lower_key}->{self.upper_key}"

    def to_fine_transition(self) -> FineTransitionKey:
        return FineTransitionKey(self.lower_key.label, self.upper_key.label)


Vector3D = np.ndarray[tuple[Literal[3],], np.dtype[np.float64] | np.dtype[np.complex128]]
Polarization = Vector3D | Callable[[Vector3D, float], Vector3D] | Callable[[Vector3D], Vector3D]
MagneticFieldObject: TypeAlias = (magField
                                  | Callable[[Vector3D, float], Vector3D]
                                  | Callable[[Vector3D], Vector3D]
                                  | Vector3D)
# endregion

# region text representation
def transition_label(labels: tuple[str, str]):
    return f"{labels[0]}->{labels[1]}"


def magnetic_field_string(magnetic_field: MagneticFieldObject):
    if isinstance(magnetic_field, np.ndarray):
        if len(magnetic_field) == 3:
            return f"({magnetic_field[0]:.3E}, {magnetic_field[1]:.3E}, {magnetic_field[2]:.3E})"
        raise ValueError("Magnetic field, when a vector, should be a 3D vector")
    elif isinstance(magnetic_field, magField):
        return f"{magnetic_field.__class__.__name__} object"
    elif isinstance(magnetic_field, Callable):
        name = magnetic_field.__name__
        sig = signature(magnetic_field)
        return f"{name}{sig}"
    else:
        raise ValueError


# endregion

# region sorting
def sort_manifolds(manifolds: Iterable[FineState] | Iterable[StateData]):
    numbers = [manifold.energy for manifold in manifolds]
    strings = [manifold.label for manifold in manifolds]
    return sort_float_then_string(numbers, strings)


def sort_float_then_string(numbers, strings):
    energy_label_pairs = np.asarray([(numbers[i], strings[i]) for i in range(len(numbers))],
                                    dtype=[('energy', float), ('label', 'S10')])
    return np.argsort(energy_label_pairs, order=['energy', 'label'])


# endregion

# region Debug overrides
class DebugFilter(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)

    def eventFilter(self, watched: QObject, event) -> bool:
        logger.debug(f"{watched} got {event} of type {event.type().__repr__()}")
        return super().eventFilter(watched, event)


def addDebugFilter(*watched: QObject):
    for qobject in watched:
        qobject.installEventFilter(DebugFilter(qobject))


class DebugApplication(QApplication):
    def notify(self, receiver, event):
        try:
            return super().notify(receiver, event)
        except Exception as e:
            print(f"Exception caught during event routing!", file=sys.stderr)
            traceback.print_exc()
            return False
        except SystemExit:
            raise
        except:
            print(f"Hard crash occurred while sending event {event.type()} to {receiver}",
                  file=sys.stderr)
            raise


# endregion

# region input helpers
class VectorTextInput(QFrame):
    def __init__(self, /):
        super().__init__()
        self.textboxes = (QLineEdit(), QLineEdit(), QLineEdit())
        self._layout = QGridLayout(self)
        for i in range(len(self.textboxes)):
            self._layout.addWidget(self.textboxes[i], 0, i)

    def value(self) -> np.ndarray:
        # TODO: add validation etc.
        return np.asarray([float(textbox.text()) for textbox in self.textboxes])


# endregion

# region GraphicsViewHoverSupervisor
def get_ancestry_up_to_view(child: QWidget | None):
    if child is None:
        return []
    traversed = child  # TODO: is this line necessary?
    path = []
    while traversed is not None:
        # TODO: this condition requires that all my embeds have no parents,
        #  and all their children have an ancestry tree leading up to the embeds
        # TODO: replace all asserts with proper exceptions later
        path.append(traversed)
        traversed = traversed.parent()
    return path


class GraphicsViewHoverSupervisor(QObject):
    def __init__(self, view):
        super().__init__(view)
        self.last_hovered_ref: weakref.ReferenceType[QWidget] | None = None
        self.lastGlobalPos = QPointF()
        self.view = view

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # get all currently hovered items
        last_hovered_ancestry = get_ancestry_up_to_view(self.last_hovered)
        # region handle mouse movement
        if event.type() == QEvent.Type.MouseMove:
            assert isinstance(event, QMouseEvent)

            globalPos = event.globalPos()
            # region get currently hovered item current_hovered
            current_hovered = None
            item = self.view.scene().itemAt(self.view.mapToScene(event.pos()),
                                            self.view.transform())
            if isinstance(item, QGraphicsProxyWidget):
                embedded_widget = item.widget()
                embeddedPos = embedded_widget.mapFromGlobal(globalPos)
                current_hovered = embedded_widget.childAt(embeddedPos)
                if current_hovered is None:  # also send these events to the embedded item if appropriate
                    if embedded_widget.rect().contains(embeddedPos):
                        current_hovered = embedded_widget  # TODO: check if the embedded widget already receives these events
            # endregion
            if self.last_hovered == current_hovered:  # a little optimization
                return super().eventFilter(watched, event)
            current_hovered_ancestry = get_ancestry_up_to_view(current_hovered)
            # region issue HoverLeave events to all the items we left
            for last_hovered_ancestor in last_hovered_ancestry:
                if not last_hovered_ancestor in current_hovered_ancestry:
                    pos = last_hovered_ancestor.mapFromGlobal(globalPos)
                    self.issue_hover_leave_event(last_hovered_ancestor, pos)
            # endregion
            # region issue HoverEnter events to all the items we entered
            for current_hovered_ancestor in current_hovered_ancestry:
                if not current_hovered_ancestor in last_hovered_ancestry:
                    pos = current_hovered_ancestor.mapFromGlobal(globalPos)
                    self.issue_hover_enter_event(current_hovered_ancestor, pos)
            # endregion
            self.lastGlobalPos = globalPos
            self.last_hovered = current_hovered


        # endregion
        # region handle window changes etc
        elif event.type() in (
                QEvent.Type.Leave,
                QEvent.Type.WindowDeactivate,
                QEvent.Type.FocusOut,
                QEvent.Type.Hide):
            for last_hovered_ancestor in last_hovered_ancestry:
                self.issue_hover_leave_event(last_hovered_ancestor, QPointF())
        # endregion
        return super().eventFilter(watched, event)

    @property
    def last_hovered(self):
        if self.last_hovered_ref is None:
            return None
        return self.last_hovered_ref()

    @last_hovered.setter
    def last_hovered(self, current_hovered):
        if current_hovered is None:
            self.last_hovered_ref = None
        else:
            self.last_hovered_ref = weakref.ref(current_hovered)

    def issue_hover_leave_event(self, target, pos):
        logger.debug(f"Leaving {target}")
        assert target is not None
        hoverLeaveEvent = QHoverEvent(QEvent.Type.HoverLeave, pos,
                                      target.mapFromGlobal(self.lastGlobalPos))
        assert isinstance(target, QObject)
        QCoreApplication.sendEvent(target, hoverLeaveEvent)

    def issue_hover_enter_event(self, target, pos):
        logger.debug(f"Entering {target}")
        hoverEnterEvent = QHoverEvent(QEvent.Type.HoverEnter, pos,
                                      target.mapFromGlobal(self.lastGlobalPos))
        QCoreApplication.sendEvent(target, hoverEnterEvent)


# endregion

# region maths
def angular_momentum_range(J1, J2):
    return np.abs(J1 - J2), J1 + J2 + 1
def _d_q_matrix_element(J, F, m_F, Jp, Fp, m_Fp, q, I):
    return (-1) ** (F - m_F + J + I + Fp + 1) * np.sqrt((2 * F + 1) * (2 * Fp + 1)) * \
        wig3j(F, 1, Fp, -m_F, q, m_Fp) * wig6j(J, F, I, Fp, Jp, 1)


def mu_q_coupled(basis, gJ, gI, J, I):
    Fs, mFs = basis
    n = len(Fs)
    mu_q = np.zeros((3, n, n))
    count = 0
    for ii, q in enumerate(range(-1, 2)):
        for index_1 in range(n):
            for index_2 in range(n):
                count += 1
                F1, F2, mF1, mF2 = Fs[index_1], Fs[index_2], mFs[index_1], mFs[index_2]
                if mF1 == mF2 + q:
                    mu_q[ii, index_1, index_2] -= (gJ * (-1) ** np.abs(F1 - mF1)
                                                   * wig3j(F1, 1, F2, -mF1, q, mF2)
                                                   * np.sqrt((2 * F2 + 1) * (2 * F1 + 1))
                                                   * (-1) ** (J + I + F2 + 1)
                                                   * wig6j(J, F2, I, F1, J, 1)
                                                   * np.sqrt(J * (J + 1) * (2 * J + 1)))

                    mu_q[ii, index_1, index_2] += (gI * (-1) ** np.abs(F1 - mF1)
                                                   * wig3j(F1, 1, F2, -mF1, q, mF2)
                                                   * np.sqrt((2 * F2 + 1) * (2 * F1 + 1))
                                                   * (-1) ** (J + I + F2 + 1)
                                                   * wig6j(I, F2, J, F1, I, 1)
                                                   * np.sqrt(I * (I + 1) * (2 * I + 1)))
    return mu_q


def hyperfine_correction(J, I, F, hf_coefs):
    """F can be a single number or an ndarray"""
    K = F * (F + 1) - I * (I + 1) - J * (J + 1)
    Ahf, Bhf, Chf = hf_coefs
    energy = Ahf * K / 2
    if Bhf != 0:
        energy += Bhf * (1.5 * K * (K + 1) - 2 * I * (I + 1) * J * (J + 1)) / (
                4 * I * (2 * I - 1) * J * (2 * J - 1))
    if Chf != 0:
        energy += Chf * (5 * K ** 2 * (K / 4 + 1)
                         + K * (I * (I + 1) + J * (J + 1) + 3 - 3 * I * (
                        I + 1) * J * (
                                        J + 1))
                         - 5 * I * (I + 1) * J * (J + 1)) / (
                          I * (I - 1) * (2 * I - 1) * J * (J - 1) * (2 * J - 1))
    return energy


def get_state_basis(state, Fs_sorted):
    mFs = []
    Fs = []
    for F in Fs_sorted:
        mFs += state.substates[F]
        Fs += [F] * len(state.substates[F])
    return Fs, mFs
# endregion

def apply_dark_theme(app: QApplication):
    app.setStyle(QStyleFactory.create('Fusion'))
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(40, 40, 40))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(dark_palette)