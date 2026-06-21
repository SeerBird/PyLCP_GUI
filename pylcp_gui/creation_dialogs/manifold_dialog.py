from PySide6.QtWidgets import QDialog, QGridLayout, QLineEdit, QLabel, QPushButton

from pylcp_gui.dataframe.dataframe import ManifoldData


class ManifoldDialog(QDialog):
    def __init__(self, /):
        super().__init__()
        self.layout = QGridLayout(self)
        self.label = QLineEdit()
        self.delta = QLineEdit()
        self.F = QLineEdit()
        self.J = QLineEdit()
        self.gamma = QLineEdit()
        self.submit_button = QPushButton("Submit")
        self.layout.addWidget(QLabel("Label:"), 0, 0)
        self.layout.addWidget(QLabel("H_0:"), 0, 1)
        self.layout.addWidget(QLabel("F:"), 0, 2)
        self.layout.addWidget(QLabel("J:"), 0, 3)
        self.layout.addWidget(QLabel("Γ:"), 0, 4)
        self.layout.addWidget(self.label, 1, 0)
        self.layout.addWidget(self.delta, 1, 1)
        self.layout.addWidget(self.F, 1, 2)
        self.layout.addWidget(self.J, 1, 3)
        self.layout.addWidget(self.gamma, 1, 4)
        self.layout.addWidget(self.submit_button)
        self.submit_button.clicked.connect(self.close)

    def value(self):
        return ManifoldData(self.label.text(),
                            float(self.delta.text()),
                            float(self.F.text()),
                            float(self.J.text()),
                            float(self.gamma.text()))
