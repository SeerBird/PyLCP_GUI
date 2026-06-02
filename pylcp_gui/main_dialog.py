from __future__ import annotations

from functools import partial
from typing import override

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QDialog, QGridLayout, QGraphicsView, QFrame, QPushButton

from pylcp_gui.diagram_internals.diagram import Diagram
from pylcp_gui.diagram_internals.manifold import Manifold
from pylcp_gui.manifold_dialog import ManifoldDialog
from pylcp_gui.hamiltonian_container import HamiltonianContainer
from pylcp_gui.transition_dialog import TransitionDialog


class MainDialog(QDialog):

    def __init__(self, dataframe: HamiltonianContainer | None = None) -> None:
        super().__init__()
        # region set up initial interface
        self.create_right_panel()
        self.create_left_panel()

        main_layout = QGridLayout(self)
        main_layout.addWidget(self._right_panel, 0, 1)
        main_layout.addWidget(self._left_panel, 0, 0)

        self._main_layout = main_layout
        self.setLayout(self._main_layout)
        self.setWindowTitle("PyLCP GUI")
        self.setMinimumSize(QSize(600, 600))
        # endregion
        # region variables
        self.selected_manifold = None
        # endregion
        if dataframe is None:
            self.dataframe: HamiltonianContainer = HamiltonianContainer()
        else:
            self.dataframe = dataframe
            # TODO: go through all the dataframe components and change the interface to reflect them

    @override
    def exec(self, /) -> HamiltonianContainer:
        # TODO: decide if I want to bother with a 'cleaner'
        #  separate Future that returns the dataframe once the dialog is done and call open() to
        #  start the dialog instead. easy to fix, clutters the code a bit, but potentially improves
        #  reliability?
        super().exec()
        return self.dataframe

    # region actions
    def add_transition_dialog(self, manifold1: Manifold, manifold2: Manifold):
        dialog = TransitionDialog()

        def add_transition_from_dialog():
            d_q = dialog.values
            self.add_transition_from_values(d_q,manifold1,manifold2)

        dialog.finished.connect(add_transition_from_dialog)
        dialog.open()

    def add_transition_from_values(self, d_q,manifold1,manifold2):
        self.diagram.add_transition_from_values(d_q,manifold1,manifold2)

    def add_manifold_from_values(self, label, detuning):
        manifold = self.diagram.add_manifold_from_values(label, detuning)
        manifold.clicked.connect(partial(self.select_manifold, manifold))

    def add_manifold_dialog(self):
        dialog = ManifoldDialog()

        def add_manifold_from_dialog():
            label, detuning = dialog.values
            self.add_manifold_from_values(label, detuning)

        dialog.finished.connect(add_manifold_from_dialog)
        dialog.open()

    def select_manifold(self, manifold: Manifold):
        if self.selected_manifold is None:
            self.selected_manifold = manifold
            # TODO: enter "I'm dragging around the anchor of a line from the first manifold" mode
        else:
            self.add_transition_dialog(self.selected_manifold, manifold)  # TODO: do this first
            self.selected_manifold = None

    # endregion
    # region setup helpers
    def create_right_panel(self):
        self._right_panel = QFrame()
        self._right_layout = QGridLayout(self._right_panel)
        self.diagram = Diagram()
        self._right_layout.addWidget(QGraphicsView(self.diagram))

    def create_left_panel(self):
        self._left_panel = QFrame()
        self.left_layout = QGridLayout(self._left_panel)
        add_manifold_button = QPushButton("Add manifold")
        add_manifold_button.clicked.connect(self.add_manifold_dialog)
        self.left_layout.addWidget(add_manifold_button)

    # endregion
