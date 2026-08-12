from __future__ import annotations

import logging
import sys
import traceback
import weakref
from typing import TYPE_CHECKING, Iterable, Literal

from PySide6.QtGui import QMouseEvent, QHoverEvent
from PySide6.QtWidgets import QFrame, QLineEdit, QGridLayout, QWidget, QGraphicsProxyWidget, \
    QApplication, QGraphicsScene

if TYPE_CHECKING:
    from pylcp_gui.dataframe.dataframe import StateData
    from pylcp_gui.diagram_internals import FineState

import numpy as np
from PySide6.QtCore import QObject, QEvent, QPointF, QCoreApplication

logger: logging.Logger = logging.getLogger(__name__)
HyperfineKey = tuple[str,float]
MagneticKey = tuple[str,float,float]
Vector3D = np.ndarray[tuple[Literal[3],], np.dtype[np.float64]]
# region labels
def transition_label(labels:tuple[str,str]):
    return f"{labels[0]}->{labels[1]}"
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
# endregion

