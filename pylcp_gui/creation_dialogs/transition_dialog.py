from PySide6.QtWidgets import QDialog, QGridLayout, QLineEdit, QLabel, QPushButton

from pylcp_gui.dataframe.dataframe import TransitionData


class TransitionDialog(QDialog):
    def __init__(self, /):
        super().__init__()
        self.layout = QGridLayout(self)
        self.gamma = QLineEdit()
        self.submit_button = QPushButton("Submit")
        self.layout.addWidget(QLabel("Γ:"), 0, 0)
        self.layout.addWidget(self.gamma, 1, 0)
        self.layout.addWidget(self.submit_button)
        self.submit_button.clicked.connect(self.close)

    def value(self):
        return TransitionData(float(self.gamma.text()))
