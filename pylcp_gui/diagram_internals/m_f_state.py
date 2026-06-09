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

    def __init__(self, mF: int, parent):
        super().__init__(parent=parent)
        self.mF = mF
        self.setCheckable(True)
        self.setChecked(True)
        self.setAutoFillBackground(True)
        self.setFixedSize(config.mFStateSize, config.mFStateSize)
        self.setIconSize(self.size())
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.clicked.connect(self.changeIcon)
        self.changeIcon()

    def __str__(self):
        return "MFState"

    def changeIcon(self, /):
        if self.isChecked():
            self.setIcon(resources.get_icon(MyIcon.mF_state))
            self.setPalette(self.checked_palette)
        else:
            self.setIcon(resources.get_icon(MyIcon.add_state))
            self.setPalette(self.unchecked_palette)

    def event(self, e, /):
        match e.type():
            case QEvent.Type.HoverEnter:
                if self.isChecked():
                    self.setIcon(resources.get_icon(MyIcon.delete_state))
                else:
                    self.setIcon(resources.get_icon(MyIcon.add_state))
            case QEvent.Type.HoverLeave:
                if self.isChecked():
                    self.setIcon(resources.get_icon(MyIcon.mF_state))
                else:
                    self.setIcon(QIcon())
            case _:
                pass
        return super().event(e)
