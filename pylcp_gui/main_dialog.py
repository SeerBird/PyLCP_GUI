from __future__ import annotations

import logging
from functools import partial
from typing import override

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QDialog, QGridLayout, QGraphicsView, QFrame, QPushButton

from pylcp_gui.diagram_internals import Transition
from pylcp_gui.diagram_internals.diagram import Diagram
from pylcp_gui.diagram_internals.manifold import Manifold
from pylcp_gui.creation_dialogs.laser_dialog import LaserDialog
from pylcp_gui.creation_dialogs.manifold_dialog import ManifoldDialog
from pylcp_gui.dataframe.dataframe import DataFrame, LaserData, ManifoldData, TransitionData
from pylcp_gui.creation_dialogs.transition_dialog import TransitionDialog
from pylcp_gui.util import sort_manifolds, GraphicsViewHoverSupervisor

logger: logging.Logger = logging.getLogger(__name__)


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
            manifolds = dataframe.manifolds
            transitions = dataframe.transitions
            lasers = dataframe.lasers
            for manifold in manifolds.values():
                self.add_manifold_from_values(manifold)
            for labels in transitions.keys():
                self.add_transition_from_values(transitions[labels],
                                                self.diagram.manifolds[labels[0]],
                                                self.diagram.manifolds[labels[1]])
            for labels in lasers.keys():
                self.add_laser_from_values(lasers[labels],labels)

    @override
    def exec(self, /) -> DataFrame:
        # TODO: decide if I want to bother with a 'cleaner'
        #  separate Future that returns the dataframe once the dialog is done and call open() to
        #  start the dialog instead. easy to fix, clutters the code a bit, but potentially improves
        #  reliability?
        super().exec()
        return self.pack_dataframe()

    # region actions
    # region add manifold
    def add_manifold_from_values(self, manifold_data: ManifoldData):
        manifold = self.diagram.add_manifold_from_values(manifold_data)
        manifold.selected.connect(partial(self.select_manifold, manifold.label))

    def add_manifold_dialog(self):
        self.manifold_dialog = ManifoldDialog()

        def add_manifold_from_dialog():
            manifold_data = self.manifold_dialog.value()
            self.add_manifold_from_values(manifold_data)

        self.manifold_dialog.finished.connect(add_manifold_from_dialog)
        self.manifold_dialog.open()

    # endregion

    # region add transition
    def add_transition_dialog(self, manifold1: Manifold, manifold2: Manifold):
        self.transition_dialog = TransitionDialog()

        def add_transition_from_dialog():
            transition_data = self.transition_dialog.value()
            self.add_transition_from_values(transition_data, manifold1, manifold2)

        self.transition_dialog.finished.connect(add_transition_from_dialog)
        self.transition_dialog.open()

    def add_transition_from_values(self, transition_data, manifold1, manifold2):
        transition = self.diagram.add_transition_from_values(transition_data, manifold1, manifold2)
        transition.delete.connect(partial(self.diagram.delete_transition, transition.labels))
        transition.add_laser.connect(partial(self.add_laser_dialog, transition.labels))

    # endregion

    # region add laser
    def add_laser_dialog(self, labels: tuple[str, str]):
        self.laser_dialog = LaserDialog()

        def add_laser_from_dialog():
            self.add_laser_from_values(self.laser_dialog.value(), labels)

        self.laser_dialog.finished.connect(add_laser_from_dialog)
        self.laser_dialog.open()

    def add_laser_from_values(self, laser_data: LaserData, labels: tuple[str, str]):
        laser = self.diagram.add_laser_from_values(laser_data, labels)

        # TODO: figure out how we want to show the lasers

    # endregion

    def select_manifold(self, label: str):
        manifold = self.diagram.manifolds[label]
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
        view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._right_layout.addWidget(view)
        # issue HoverEnter and HoverLeave events to the widgets in the GraphicsScene
        view.viewport().installEventFilter(GraphicsViewHoverSupervisor(view))
        view.setMouseTracking(True)

    def create_left_panel(self):
        self._left_panel = QFrame()
        self.left_layout = QGridLayout(self._left_panel)
        add_manifold_button = QPushButton("Add manifold")
        add_manifold_button.clicked.connect(self.add_manifold_dialog)
        self.left_layout.addWidget(add_manifold_button)

    # endregion

    def pack_dataframe(self):
        dataframe = DataFrame()

        for manifold in list(self.diagram.manifolds.values()):
            assert isinstance(manifold, Manifold)
            F = manifold.F
            mFs = np.arange(-F, F + 1)
            mFs_included = np.asarray([mF.isChecked() for mF in manifold.states])
            mFs = mFs[mFs_included]
            dataframe.manifolds[manifold.label] = ManifoldData(manifold.label, manifold.energy, F,
                                                               mFs)
        for transition in list(self.diagram.transitions.values()):
            labels = transition.labels
            dataframe.transitions[labels] = TransitionData(transition.gamma)

        for laser in list(self.diagram.lasers.values()):
            dataframe.lasers[laser.labels] = LaserData(laser.freq, laser.kvec,
                                                       laser.pol, laser.intensity)
        return dataframe
