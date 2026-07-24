from PySide6.QtWidgets import QDialog, QGridLayout, QLineEdit, QLabel, QPushButton


class LaserGroupDialog(QDialog):
    def __init__(self, /):
        super().__init__()
        self.layout = QGridLayout(self)
        self.name = QLineEdit()
        self.submit_button = QPushButton("Submit")
        self.layout.addWidget(QLabel("Laser Group Name:"), 0, 0)
        self.layout.addWidget(self.name, 1, 0)
        self.layout.addWidget(self.submit_button)
        self.submit_button.clicked.connect(self.close)

    def value(self):
        return self.name.text()