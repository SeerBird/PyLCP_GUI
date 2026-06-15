from PySide6 import QtGui
from PySide6.QtCore import Signal, Qt, QEvent
from PySide6.QtGui import QPalette, QIcon
from PySide6.QtWidgets import QFrame, QGridLayout, QPushButton, QToolButton

from pylcp_gui.resources import MyIcon
from pylcp_gui import resources, config
from pylcp_gui.util import addDebugFilter


class MFState(QToolButton):
    checked_palette = QPalette()
    checked_palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.lightGray)
    unchecked_palette = QPalette()
    unchecked_palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.transparent)

    def __init__(self, mF: int):
        super().__init__()
        self.mF = mF
        self.setAutoFillBackground(True)
        self.setFixedSize(config.mFStateSize, config.mFStateSize)
        self.setIconSize(self.size())
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setIcon(resources.get_icon(MyIcon.mF_state))

    def __str__(self):
        return "MFState"
