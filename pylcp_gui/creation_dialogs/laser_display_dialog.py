from PySide6.QtWidgets import QDialog, QGridLayout, QPushButton, QLabel, QComboBox


def add_items_from_keys(keys, combobox: QComboBox):
    for key in keys:
        combobox.addItem(f"{key[0]}, F = {key[1]:g}", key)


class LaserDisplayDialog(QDialog):
    def __init__(self, lower_keys, upper_keys):
        super().__init__()
        self.layout = QGridLayout(self)

        self.lower_state = QComboBox()
        add_items_from_keys(lower_keys, self.lower_state)
        self.upper_state = QComboBox()
        add_items_from_keys(upper_keys, self.upper_state)

        self.upwards_toggle = QPushButton("Orientation")
        self.upwards_toggle.setCheckable(True)

        self.submit_button = QPushButton("Submit")

        self.layout.addWidget(QLabel("Upper state"), 0, 0)
        self.layout.addWidget(QLabel("Lower state:"), 1, 0)
        self.layout.addWidget(QLabel("Orientation:"), 2, 0)
        self.layout.addWidget(self.lower_state, 0, 1)
        self.layout.addWidget(self.upper_state, 1, 1)
        self.layout.addWidget(self.submit_button, 2, 1)
        self.layout.addWidget(self.submit_button)
        self.submit_button.clicked.connect(self.close)

    def values(self):
        return ((self.lower_state.currentData(), self.upper_state.currentData()),
                self.upwards_toggle.isChecked())
