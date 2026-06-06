from PySide6.QtWidgets import QDialog, QGridLayout, QLineEdit, QLabel, QPushButton


class ManifoldDialog(QDialog):
    def __init__(self, /):
        super().__init__()
        self.values = None
        self.layout = QGridLayout(self)
        self.label = QLineEdit()
        self.delta = QLineEdit()
        self.F = QLineEdit()
        self.submit_button = QPushButton("Submit")
        self.layout.addWidget(QLabel("Label:"),0,0)
        self.layout.addWidget(QLabel("H_0:"), 0, 1)
        self.layout.addWidget(QLabel("F:"), 0, 2)
        self.layout.addWidget(self.label, 1, 0)
        self.layout.addWidget(self.delta, 1, 1)
        self.layout.addWidget(self.F, 1, 2)
        self.layout.addWidget(self.submit_button)
        self.submit_button.clicked.connect(self.submit)

    def submit(self):
        self.values = (self.label.text(), float(self.delta.text()), int(self.F.text()))
        self.close()