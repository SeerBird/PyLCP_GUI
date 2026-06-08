import numpy as np
from PySide6.QtCore import QObject, QEvent


def sort_float_then_string(numbers,strings):
    energy_label_pairs = np.asarray([(numbers[i], strings[i]) for i in range(len(numbers))],
                                    dtype=[('energy', float), ('label', 'S10')])
    return np.argsort(energy_label_pairs, order=['energy', 'label'])

class DebugFilter(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
    def eventFilter(self, watched: QObject, event) -> bool:
        print(f"{watched} got {event} of type {event.type().__repr__()}")
        return super().eventFilter(watched, event)

def addDebugFilter(*watched:QObject):
    for qobject in watched:
        qobject.installEventFilter(DebugFilter(qobject))