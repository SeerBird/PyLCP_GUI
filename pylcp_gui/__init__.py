"""yayyyy"""
from PySide6.QtWidgets import QApplication

from pylcp_gui.dataframe.dataframe import DataFrame
from pylcp_gui.main_dialog import MainDialog


def dialog(dataframe: DataFrame | None = None) -> DataFrame:
    app = QApplication()
    _dialog = MainDialog(dataframe)
    res = _dialog.exec()
    app.shutdown()
    return res

# TODO: add logging