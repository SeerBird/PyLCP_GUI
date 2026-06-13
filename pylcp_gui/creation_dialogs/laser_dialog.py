from PySide6.QtWidgets import QDialog, QGridLayout, QLineEdit, QLabel, QPushButton

from pylcp_gui.dataframe.dataframe import LaserData
from pylcp_gui.util import VectorTextInput


class LaserDialog(QDialog):
    def __init__(self, /):
        super().__init__()
        self.values = None
        self.layout = QGridLayout(self)
        self.freq = QLineEdit()
        self.kvec = VectorTextInput()
        self.pol = VectorTextInput()
        self.intensity = QLineEdit()
        self.submit_button = QPushButton("Submit")
        self.layout.addWidget(QLabel("freq:"), 0, 0)
        self.layout.addWidget(QLabel("kvec:"), 0, 1)
        self.layout.addWidget(QLabel("pol:"), 0, 2)
        self.layout.addWidget(QLabel("intensity:"), 0, 3)
        self.layout.addWidget(self.freq, 1, 0)
        self.layout.addWidget(self.kvec, 1, 1)
        self.layout.addWidget(self.pol, 1, 2)
        self.layout.addWidget(self.intensity, 1, 3)
        self.layout.addWidget(self.submit_button)
        self.submit_button.clicked.connect(self.close)

    def value(self):
        return LaserData(float(self.freq.text()),
                         self.kvec.value(),
                         self.pol.value(),
                         float(self.intensity.text()))
