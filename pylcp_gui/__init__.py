"""yayyyy"""
__all__ = [
    "DataFrame",
    "dialog",
    "dialog_from_dataframe",

]

from typing import cast

from .util import apply_dark_theme
from enum import Enum

from PySide6.QtWidgets import QApplication

from . import _logging


# region set up logging
class LoggingLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARN"
    ERROR = "ERROR"


logger = _logging.setupLogging(__name__)
# endregion

from pylcp_gui import resources
from pylcp_gui.dataframe.dataframe import (
    DataFrame,
    StateData,
    TransitionData,
    LaserData,
    LaserDisplayData,
)
from pylcp_gui.main_dialog import MainDialog


def dialog_from_dataframe(dataframe: DataFrame) -> DataFrame:
    # TODO: validate input
    app = QApplication.instance()
    if app is None:
        app = QApplication()
    else:
        app = cast(QApplication, app)
    apply_dark_theme(app)
    _dialog = MainDialog(dataframe)
    res = _dialog.exec()
    app.shutdown()
    return res


def dialog(I: float, gI: float = 0.0) -> DataFrame:
    # TODO: validate input
    app = QApplication.instance()
    if app is None:
        app = QApplication()
    else:
        app = cast(QApplication, app)
    apply_dark_theme(app)
    frame = DataFrame(I, gI)
    _dialog = MainDialog(frame)
    res = _dialog.exec()
    app.shutdown()
    return res
