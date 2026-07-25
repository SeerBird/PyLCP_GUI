from __future__ import annotations

import logging
from functools import partial
from typing import override

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QDialog, QGridLayout, QGraphicsView, QFrame, QPushButton, QLabel

from pylcp_gui.creation_dialogs.laser_dialog import LaserDialog
from pylcp_gui.creation_dialogs.laser_display_dialog import LaserDisplayDialog
from pylcp_gui.creation_dialogs.laser_group_dialog import LaserGroupDialog
from pylcp_gui.creation_dialogs.manifold_dialog import FineStateDialog
from pylcp_gui.creation_dialogs.transition_dialog import TransitionDialog
from pylcp_gui.dataframe.dataframe import DataFrame, LaserData, StateData, TransitionData, \
    LaserDisplayData
from pylcp_gui.diagram_internals.diagram import Diagram
from pylcp_gui.diagram_internals.fine_state import FineState
from pylcp_gui.laser_tree import LaserTree
from pylcp_gui.util import GraphicsViewHoverSupervisor

logger: logging.Logger = logging.getLogger(__name__)


class MainDialog(QDialog):
    def __init__(self, dataframe: DataFrame | None = None, I: float | None = None) -> None:
        """
        Internal use only. Specify a complete dataframe OR a nuclear angular momentum number
        """
        super().__init__()
        # region set up initial interface
        # region right panel
        self._right_panel = QFrame()
        self._right_layout = QGridLayout(self._right_panel)
        self.diagram = Diagram(I)
        view = QGraphicsView(self.diagram)
        view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        view.viewport().installEventFilter(self.diagram)
        view.verticalScrollBar().valueChanged.connect(self.diagram.refresh_line_extent)
        view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        view.setMaximumSize(10000, 10000)  # TODO: figure view size out
        self._right_layout.addWidget(view)
        # issue HoverEnter and HoverLeave events to the widgets in the GraphicsScene
        view.viewport().installEventFilter(GraphicsViewHoverSupervisor(view))
        view.setMouseTracking(True)
        # endregion
        # region left panel
        self._left_panel = QFrame()
        self._left_panel.setMaximumWidth(200)
        self.left_layout = QGridLayout(self._left_panel)

        I_label = QLabel("I = ")
        I_label.setFixedWidth(40)
        self.left_layout.addWidget(I_label, 0, 0)

        self.I_display = QLabel(str(I))
        self.I_display.setFixedWidth(40)
        self.left_layout.addWidget(self.I_display, 0, 1)

        add_manifold_button = QPushButton("Add fine structure state")
        add_manifold_button.clicked.connect(self.add_fine_state_dialog)
        self.left_layout.addWidget(add_manifold_button, 1, 0, 1, 2)

        self.laser_tree = LaserTree()
        self.laser_tree.add_laser_display.connect(self.add_laser_display_dialog)
        self.left_layout.addWidget(self.laser_tree, 2, 0, 1, 2)
        # endregion
        main_layout = QGridLayout(self)
        main_layout.addWidget(self._right_panel, 0, 1)
        main_layout.addWidget(self._left_panel, 0, 0)

        self._main_layout = main_layout
        self.setLayout(self._main_layout)
        self.setWindowTitle("PyLCP GUI")
        self.setMinimumSize(QSize(600, 600))
        # endregion
        # region tracking variables
        self.selected_manifold = None
        # prevent garbage collection
        self.fine_state_dialog = None
        self.transition_dialog = None
        self.laser_freq_group_dialog = None
        # endregion
        if dataframe is not None:
            self.I: float = dataframe.I
            self.I_display.setText(str(self.I))
            self.diagram.I = dataframe.I
            states = dataframe.states
            transitions = dataframe.transitions
            lasers = dataframe.lasers
            for state in states.values():
                self.add_fine_state_from_values(state)
            for label_pair in transitions.keys():
                self.add_transition_from_values(transitions[label_pair],
                                                self.diagram.fine_states[label_pair[0]],
                                                self.diagram.fine_states[label_pair[1]])
            for label_pair in lasers.keys():
                for laser_data in lasers[label_pair]:
                    self.laser_tree.add_laser(laser_data, label_pair)
        elif I is None:
            raise ValueError("MainDialog needs to be initialised with either a DataFrame or a " +
                             "valid nuclear angular momentum number")

    @override
    def exec(self, /) -> DataFrame:
        # TODO: decide if I want to bother with a 'cleaner'
        #  separate Future that returns the dataframe once the dialog is done and call open() to
        #  start the dialog instead. easy to fix, clutters the code a bit, but potentially improves
        #  reliability?
        self.showMaximized()
        super().exec()
        return self.pack_dataframe()

    # region actions
    # region add state
    def add_fine_state_from_values(self, state_data: StateData):
        fine_state = self.diagram.add_fine_state_from_values(state_data)
        # fine_state.selected.connect(partial(self.select_state, fine_state.label))

    def add_fine_state_dialog(self):
        self.fine_state_dialog = FineStateDialog()

        def add_fine_state_from_dialog():
            state_data = self.fine_state_dialog.value()
            self.add_fine_state_from_values(state_data)

        self.fine_state_dialog.finished.connect(add_fine_state_from_dialog)
        self.fine_state_dialog.open()

    # endregion

    # region add transition
    def add_transition_dialog(self, manifold1: FineState, manifold2: FineState):
        self.transition_dialog = TransitionDialog()

        def add_transition_from_dialog():
            transition_data = self.transition_dialog.value()
            self.add_transition_from_values(transition_data, manifold1, manifold2)

        self.transition_dialog.finished.connect(add_transition_from_dialog)
        self.transition_dialog.open()

    def add_transition_from_values(self, transition_data, state1, state2):
        transition = self.diagram.add_transition_from_values(transition_data, state1, state2)
        # transition.delete.connect(partial(self.diagram.delete_transition, transition.keys))
        # transition.add_laser.connect(partial(self.add_laser_dialog, transition.keys))

    # endregion

    # region add laser
    def add_laser_dialog(self, labels: tuple[str, str]):
        self.laser_dialog = LaserDialog()

        def add_laser_with_group():
            laser_data = self.laser_dialog.value()
            group_name = self.laser_freq_group_dialog.value()
            self.laser_tree.add_laser(laser_data, labels, group_name)

        def add_laser_from_dialog():
            laser_data = self.laser_dialog.value()
            if self.laser_tree.has_one_in_freq_group(laser_data.keys, laser_data.freq):
                self.laser_freq_group_dialog = LaserGroupDialog()
                self.laser_freq_group_dialog.finished.connect(add_laser_with_group)
                self.laser_freq_group_dialog.open()
            self.laser_tree.add_laser(self.laser_dialog.value(), labels)

        self.laser_dialog.finished.connect(add_laser_from_dialog)
        self.laser_dialog.open()

    # endregion

    # region add laser display
    def add_laser_display_dialog(self, labels, freq):
        label1, label2 = labels
        lower_keys = self.diagram.enabled_hyperfine_substates(label1)
        upper_keys = self.diagram.enabled_hyperfine_substates(label2)
        self.laser_display_dialog = LaserDisplayDialog(lower_keys, upper_keys)
        # TODO: make sure to prevent adding duplicate laser displays
        def add_laser_display_from_dialog():
            keys, upwards = self.laser_display_dialog.values()
            self.diagram.add_laser_display(LaserDisplayData(freq, keys, upwards))

        self.laser_display_dialog.finished.connect(add_laser_display_from_dialog)
        self.laser_display_dialog.open()

    # endregion

    def select_state(self, label: str):
        manifold = self.diagram.fine_states[label]
        if self.selected_manifold is None:
            self.selected_manifold = manifold
            # TODO: enter "I'm dragging around the anchor of a line from the first manifold" mode
        else:
            self.add_transition_dialog(self.selected_manifold, manifold)  # TODO: do this first
            self.selected_manifold = None

    # endregion

    def pack_dataframe(self):
        dataframe = DataFrame()
        dataframe.I = self.I
        fine_state: FineState
        for fine_state in list(self.diagram.fine_states.values()):
            dataframe.states[fine_state.label] = StateData(fine_state.label,
                                                           fine_state.energy,
                                                           fine_state.J,
                                                           fine_state.hf_coefs,
                                                           fine_state.gJ)
        for transition in list(self.diagram.transitions.values()):
            label_pair = transition.keys
            dataframe.transitions[label_pair] = TransitionData(transition.gamma)
            dataframe.lasers[label_pair] = []
        lasers = self.laser_tree.lasers
        for laser in lasers.values():
            dataframe.lasers[laser.labels].append(LaserData(laser.freq, laser.kvec,
                                                            laser.pol, laser.intensity))
        return dataframe
