from __future__ import annotations

from typing import TYPE_CHECKING,Iterable

from PySide6.QtWidgets import QFrame, QLineEdit, QGridLayout

if TYPE_CHECKING:
    from pylcp_gui.dataframe.dataframe import ManifoldData
    from pylcp_gui.diagram_internals import Manifold

import numpy as np
from PySide6.QtCore import QObject, QEvent



def sort_manifolds(manifolds: Iterable[Manifold] | Iterable[ManifoldData]):
    numbers = [manifold.energy for manifold in manifolds]
    strings = [manifold.label for manifold in manifolds]
    return sort_float_then_string(numbers, strings)


def sort_float_then_string(numbers, strings):
    energy_label_pairs = np.asarray([(numbers[i], strings[i]) for i in range(len(numbers))],
                                    dtype=[('energy', float), ('label', 'S10')])
    return np.argsort(energy_label_pairs, order=['energy', 'label'])


class DebugFilter(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)

    def eventFilter(self, watched: QObject, event) -> bool:
        print(f"{watched} got {event} of type {event.type().__repr__()}")
        return super().eventFilter(watched, event)


def addDebugFilter(*watched: QObject):
    for qobject in watched:
        qobject.installEventFilter(DebugFilter(qobject))

class VectorTextInput(QFrame):
    def __init__(self, /):
        super().__init__()
        self.textboxes = (QLineEdit(), QLineEdit(), QLineEdit())
        self._layout = QGridLayout(self)
        for i in range(len(self.textboxes)):
            self._layout.addWidget(self.textboxes[i], 0, i)
    def value(self):
        # TODO: add validation etc.
        return (textbox.text() for textbox in self.textboxes)
