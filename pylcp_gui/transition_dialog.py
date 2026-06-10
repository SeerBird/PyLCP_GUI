from PySide6.QtWidgets import QDialog, QGridLayout, QLineEdit, QLabel, QPushButton


class TransitionDialog(QDialog):
    def __init__(self, /):
        super().__init__()
        self.layout = QGridLayout(self)
        self.gamma = QLineEdit()
        self.submit_button = QPushButton("Submit")
        self.layout.addWidget(QLabel("Γ:"), 0, 0)
        self.layout.addWidget(self.gamma, 1, 0)
        self.layout.addWidget(self.submit_button)
        self.submit_button.clicked.connect(self.submit)

    def submit(self):
        self.values = float(self.gamma.text())
        self.close()