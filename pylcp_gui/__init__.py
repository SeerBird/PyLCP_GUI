"""yayyyy"""
import logging
import os

from PySide6.QtWidgets import QApplication, QStyleFactory
from . import _logging
from enum import Enum


# region set up logging
class LoggingLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARN"
    ERROR = "ERROR"


logger = _logging.setupLogging(__name__)
# endregion

from pylcp_gui import resources
from pylcp_gui.dataframe.dataframe import DataFrame
from pylcp_gui.main_dialog import MainDialog


def dialog_from_dataframe(dataframe: DataFrame) -> DataFrame:
    # TODO: validate input
    app = QApplication()
    app.setStyle(QStyleFactory.create('Fusion'))
    _dialog = MainDialog(dataframe)
    res = _dialog.exec()
    app.shutdown()
    return res

def dialog(I:float):
    # TODO: validate input
    app = QApplication()
    app.setStyle(QStyleFactory.create('Fusion'))
    _dialog = MainDialog(I = I)
    res = _dialog.exec()
    app.shutdown()
    return res