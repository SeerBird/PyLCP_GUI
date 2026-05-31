from __future__ import annotations
from typing import override, TYPE_CHECKING, Self

from pylcp import hamiltonian

if TYPE_CHECKING:
    from main_dialog import MainDialog

import pylcp
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QApplication, QDialog, QLayout, QGridLayout,
                               QMessageBox, QGroupBox, QSpinBox, QSlider,
                               QProgressBar, QDial, QDialogButtonBox,
                               QComboBox, QLabel)
from PySide6.QtCore import (
    Slot,
    Signal
)




class HamiltonianContainer:
    def __init__(self):
        self.hamiltonian: pylcp.hamiltonian = hamiltonian()

    @staticmethod
    def load_from_file():
        pass
