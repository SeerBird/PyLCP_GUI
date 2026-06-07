from __future__ import annotations

from functools import partial
from typing import override

import numpy as np
import pylcp
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QDialog, QGridLayout, QGraphicsView, QFrame, QPushButton

from pylcp_gui.diagram_internals.diagram import Diagram
from pylcp_gui.diagram_internals.manifold import Manifold
from pylcp_gui.manifold_dialog import ManifoldDialog
from pylcp_gui.dataframe.dataframe import DataFrame
from pylcp_gui.transition_dialog import TransitionDialog
from pylcp_gui.util import DebugFilter, addDebugFilter


class MainDialog(QDialog):

    def __init__(self, dataframe: DataFrame | None = None) -> None:
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
        self.manifold_dialog = None  # keep this while the manifold dialog is open to prevent garbage collection
        self.transition_dialog = None
        # endregion
        if dataframe is None:
            self.dataframe: DataFrame = DataFrame()
        else:
            self.dataframe = dataframe
            H_0 = dataframe.H_0
            d_q = dataframe.d_q
            for label in H_0.keys():
                self.add_manifold_from_values(label, H_0[label])
            for labels in d_q.keys():
                manifold_pair = [self.diagram.manifolds[label] for label in labels]
                self.add_transition_from_values(d_q[labels], *manifold_pair)

        # TODO: go through all the dataframe components and change the interface to reflect them

    @override
    def exec(self, /) -> DataFrame:
        # TODO: decide if I want to bother with a 'cleaner'
        #  separate Future that returns the dataframe once the dialog is done and call open() to
        #  start the dialog instead. easy to fix, clutters the code a bit, but potentially improves
        #  reliability?
        super().exec()
        return self.pack_dataframe()

    # region actions
    def add_transition_dialog(self, manifold1: Manifold, manifold2: Manifold):
        self.transition_dialog = TransitionDialog()

        def add_transition_from_dialog():
            d_q = self.transition_dialog.values
            self.add_transition_from_values(d_q, manifold1, manifold2)

        self.transition_dialog.finished.connect(add_transition_from_dialog)
        self.transition_dialog.open()

    def add_transition_from_values(self, d_q, manifold1, manifold2):
        self.diagram.add_transition_from_values(d_q, manifold1, manifold2)

    def add_manifold_from_values(self, label, detuning, F):
        manifold = self.diagram.add_manifold_from_values(label, detuning, F)
        manifold.selected.connect(partial(self.select_manifold, manifold))

    def add_manifold_dialog(self):
        self.manifold_dialog = ManifoldDialog()

        def add_manifold_from_dialog():
            label, detuning, F = self.manifold_dialog.values
            self.add_manifold_from_values(label, detuning, F)

        self.manifold_dialog.finished.connect(add_manifold_from_dialog)
        self.manifold_dialog.open()

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
        view = QGraphicsView(self.diagram)
        self._right_layout.addWidget(view)

        view.viewport().setMouseTracking(True)
        view.setMouseTracking(True)
        view.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def create_left_panel(self):
        self._left_panel = QFrame()
        self.left_layout = QGridLayout(self._left_panel)
        add_manifold_button = QPushButton("Add manifold")
        add_manifold_button.clicked.connect(self.add_manifold_dialog)
        self.left_layout.addWidget(add_manifold_button)

    # endregion
    def pack_dataframe(self):
        dataframe = DataFrame()
        manifold_dict = self.diagram.manifolds
        manifolds = list(manifold_dict.values())
        transitions = list(self.diagram.transitions.values())
        energies = np.asarray([manifold.energy for manifold in manifolds])
        # order manifolds in rising energy order
        manifolds = np.asarray(manifolds)[np.argsort(energies)]
        for manifold in manifolds:
            dataframe.H_0[manifold.label] = manifold.energy
        for transition in transitions:
            labels = transition.labels()
            dataframe.d_q[labels] = transition.d_q
        return dataframe
