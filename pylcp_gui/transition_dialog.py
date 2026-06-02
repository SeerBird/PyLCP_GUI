from PySide6.QtWidgets import QDialog, QGridLayout, QLineEdit, QLabel, QPushButton


class TransitionDialog(QDialog):
    def __init__(self, /):
        super().__init__()
        self.layout = QGridLayout(self)
        self.d_q = QLineEdit()
        self.submit_button = QPushButton("Submit")
        self.layout.addWidget(QLabel("d_q:"), 0, 0)
        self.layout.addWidget(self.d_q, 1, 0)
        self.layout.addWidget(self.submit_button)
        self.submit_button.clicked.connect(self.submit)

    def submit(self):
        self.values = self.d_q.text()