"""yayyyy"""
from PySide6.QtWidgets import QApplication, QStyleFactory

from pylcp_gui import resources
from pylcp_gui.dataframe.dataframe import DataFrame
from pylcp_gui.main_dialog import MainDialog


def dialog(dataframe: DataFrame | None = None) -> DataFrame:
    app = QApplication()
    app.setStyle(QStyleFactory.create('Fusion'))
    _dialog = MainDialog(dataframe)
    res = _dialog.exec()
    app.shutdown()
    return res

# TODO: add logging