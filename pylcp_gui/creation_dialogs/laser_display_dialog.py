from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QDialog, QGridLayout, QPushButton, QLabel, QComboBox

if TYPE_CHECKING:
    from pylcp_gui import MainDialog
from pylcp_gui.dataframe.dataframe import LaserDisplayData


def add_items_from_keys(keys, combobox: QComboBox):
    for key in keys:
        combobox.addItem(f"{key[0]}, F = {key[1]:g}", key)


class LaserDisplayDialog(QDialog):
    def __init__(self, parent, lower_keys, upper_keys, freq):
        super().__init__(parent)
        self.layout = QGridLayout(self)
        self.freq = freq
        self.lower_state = QComboBox()
        add_items_from_keys(lower_keys, self.lower_state)
        self.upper_state = QComboBox()
        add_items_from_keys(upper_keys, self.upper_state)
        self.lower_state.currentIndexChanged.connect(self.check_validity)
        self.upper_state.currentIndexChanged.connect(self.check_validity)

        self.upwards_toggle = QPushButton("Orientation")
        self.upwards_toggle.setCheckable(True)
        self.upwards_toggle.setChecked(True)

        self.submit_button = QPushButton("Submit")

        self.layout.addWidget(QLabel("Lower state"), 0, 0)
        self.layout.addWidget(QLabel("Upper state:"), 1, 0)
        self.layout.addWidget(QLabel("Orientation:"), 2, 0)
        self.layout.addWidget(self.lower_state, 0, 1)
        self.layout.addWidget(self.upper_state, 1, 1)
        self.layout.addWidget(self.submit_button, 2, 1)
        self.layout.addWidget(self.submit_button)
        self.submit_button.clicked.connect(self.accept)
        self.check_validity()

    def value(self):
        return LaserDisplayData(self.freq,
                                self.keys(),
                                self.upwards_toggle.isChecked())

    def keys(self):
        return (self.lower_state.currentData(),
                self.upper_state.currentData())

    def parent(self, /) -> MainDialog:
        parent = super().parent()
        return parent

    def check_validity(self):
        valid = self.parent().check_existing_laser_display_keys(self.keys(), self.freq)
        if valid:
            self.submit_button.setEnabled(True)
            self.submit_button.setToolTip("")
        else:
            self.submit_button.setEnabled(False)
            self.submit_button.setToolTip(
                "A LaserDisplay of this energy for this hyperfine state pair already exists")

