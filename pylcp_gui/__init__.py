"""yayyyy"""

from enum import Enum

from PySide6.QtWidgets import QApplication, QStyleFactory

from . import _logging


# region set up logging
class LoggingLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARN"
    ERROR = "ERROR"


logger = _logging.setupLogging(__name__)
# endregion

from PySide6.QtGui import QPalette, QColor
from pylcp_gui import resources
from pylcp_gui.dataframe.dataframe import DataFrame
from pylcp_gui.main_dialog import MainDialog


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


def dialog_from_dataframe(dataframe: DataFrame) -> DataFrame:
    # TODO: validate input
    app = QApplication.instance()
    if app is None:
        app = QApplication()
    apply_dark_theme(app)
    _dialog = MainDialog(dataframe)
    res = _dialog.exec()
    app.shutdown()
    return res

def dialog(I: float, gI: float = 0.0):
    # TODO: validate input
    app = QApplication.instance()
    if app is None:
        app = QApplication()
    apply_dark_theme(app)
    frame = DataFrame(I, gI)
    _dialog = MainDialog(frame)
    res = _dialog.exec()
    app.shutdown()
    return res