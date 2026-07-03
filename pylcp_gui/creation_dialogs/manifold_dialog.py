from PySide6.QtWidgets import QDialog, QGridLayout, QLineEdit, QLabel, QPushButton

from pylcp_gui.dataframe.dataframe import StateData


class FineStateDialog(QDialog):
    def __init__(self, /):
        super().__init__()
        self.layout = QGridLayout(self)
        self.label = QLineEdit()
        self.energy = QLineEdit()
        self.J = QLineEdit()
        self.gamma = QLineEdit()
        self.Ahf = QLineEdit()
        self.Bhf = QLineEdit()
        self.Chf = QLineEdit()
        self.gJ = QLineEdit()
        self.submit_button = QPushButton("Submit")
        self.layout.addWidget(QLabel("Label:"), 0, 0)
        self.layout.addWidget(QLabel("Energy:"), 0, 1)  # TODO: units here
        self.layout.addWidget(QLabel("J:"), 0, 2)
        self.layout.addWidget(QLabel("Γ:"), 0, 3)
        self.layout.addWidget(QLabel("Ahf:"), 0, 4)  # TODO: group these, single import
        self.layout.addWidget(QLabel("Bhf:"), 0, 5)
        self.layout.addWidget(QLabel("Chf:"), 0, 6)
        self.layout.addWidget(QLabel("gJ:"), 0, 7)
        self.layout.addWidget(self.label, 1, 0)
        self.layout.addWidget(self.energy, 1, 1)
        self.layout.addWidget(self.J, 1, 2)
        self.layout.addWidget(self.gamma, 1, 3)
        self.layout.addWidget(self.Ahf, 1, 4)
        self.layout.addWidget(self.Bhf, 1, 5)
        self.layout.addWidget(self.Chf, 1, 6)
        self.layout.addWidget(self.gJ, 1, 7)
        self.layout.addWidget(self.submit_button)
        self.submit_button.clicked.connect(self.close)

    def value(self):
        return StateData(self.label.text(),
                         float(self.energy.text()),
                         float(self.J.text()),
                         float(self.gamma.text()),
                         float(self.Ahf.text()),
                         float(self.Bhf.text()),
                         float(self.Chf.text()),
                         float(self.gJ.text()))
