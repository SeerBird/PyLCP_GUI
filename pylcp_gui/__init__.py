"""yayyyy"""
from PySide6.QtWidgets import QApplication

from pylcp_gui.hamiltonian_container import HamiltonianContainer
from pylcp_gui.main_dialog import MainDialog


def dialog(matrix: HamiltonianContainer | None = None) -> HamiltonianContainer:
    app = QApplication()
    _dialog = MainDialog(matrix)
    return _dialog.exec()

# TODO: add logging