from __future__ import annotations

import logging
from functools import partial
from typing import override

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QDialog, QGridLayout, QVBoxLayout, QFormLayout, QGraphicsView, QFrame, \
    QPushButton, QLabel, \
    QMessageBox
from sympy import true

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
from pylcp_gui.selected_display import SelectedDisplay
from pylcp_gui.util import GraphicsViewHoverSupervisor, magnetic_field_string, FineTransitionKey

logger: logging.Logger = logging.getLogger(__name__)


class MainDialog(QDialog):
    def __init__(self, dataframe: DataFrame) -> None:
        """
        Internal use only. Specify a complete dataframe OR a nuclear angular momentum number
        """
        super().__init__()
        # region get Dataframe I, gI, magnetic_field

        # endregion
        # region set up initial interface
        # region right panel
        self._right_panel = QFrame()
        self._right_layout = QGridLayout(self._right_panel)

        self.diagram = Diagram(self)
        view = QGraphicsView(self.diagram)
        view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        view.viewport().installEventFilter(self.diagram)
        view.verticalScrollBar().valueChanged.connect(self.diagram.refresh_line_extent)
        view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        view.setMaximumSize(10000, 10000)  # TODO: figure view size out
        self._right_layout.addWidget(view)
        # issue HoverEnter and HoverLeave events to the widgets in the GraphicsScene
        # TODO: check if this is being used at all
        view.viewport().installEventFilter(GraphicsViewHoverSupervisor(view))
        view.setMouseTracking(True)
        # endregion
        # region left panel
        self._left_panel = QFrame()
        self._left_panel.setFixedWidth(240)
        self.left_layout = QVBoxLayout(self._left_panel)
        self.left_layout.setContentsMargins(4, 4, 4, 4)
        # region system parameters frame
        self.param_frame = QFrame()
        self.param_frame.setFrameShape(QFrame.Shape.StyledPanel)
        param_layout = QFormLayout(self.param_frame)
        param_layout.setContentsMargins(8, 8, 8, 8)
        param_layout.setHorizontalSpacing(10)
        param_layout.setVerticalSpacing(6)

        I_label = QLabel("I =")
        self.I_display = QLabel()
        gI_label = QLabel("gI =")
        self.gI_display = QLabel()
        B_label = QLabel("B =")
        self.B_field_display = QLabel()

        for display in (self.I_display, self.gI_display, self.B_field_display):
            display.setWordWrap(True)
            display.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        param_layout.addRow(I_label, self.I_display)
        param_layout.addRow(gI_label, self.gI_display)
        param_layout.addRow(B_label, self.B_field_display)
        # endregion
        self.left_layout.addWidget(self.param_frame)
        # region LaserTree
        self.laser_tree = LaserTree()
        self.laser_tree.setMinimumHeight(150)
        self.laser_tree.add_laser_display.connect(self.add_laser_display_dialog)
        self.laser_tree.item_selected.connect(self.handle_laser_tree_selection_changed)
        # endregion
        self.left_layout.addWidget(self.laser_tree, stretch=1)
        # region 'selected' display
        self.selected_display = SelectedDisplay(parent=self._left_panel)
        # endregion
        self.left_layout.addWidget(self.selected_display, stretch=1)

        self.diagram.selectionChanged.connect(self.handle_diagram_selection_changed)
        self.diagram.diagram_changed.connect(self.selected_display.handle_diagram_changed)
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
        # region load dataframe in
        self.I: float = dataframe.I
        self.gI = dataframe.gI
        self.magnetic_field = dataframe.magnetic_field

        i_str = f"{self.I:g}"
        gi_str = f"{self.gI:.3E}"
        b_str = magnetic_field_string(self.magnetic_field)

        self.I_display.setText(i_str)
        self.I_display.setToolTip(f"I = {self.I}")

        self.gI_display.setText(gi_str)
        self.gI_display.setToolTip(f"gI = {self.gI}")

        self.B_field_display.setText(b_str)
        self.B_field_display.setToolTip(f"B = {b_str}")
        states = dataframe.fine_states
        transitions = dataframe.transitions
        lasers = dataframe.lasers
        laser_displays = dataframe.laser_displays
        for state in states.values():
            self.add_fine_state_from_values(state)
        for label_pair in transitions.keys():
            self.add_transition_from_values(transitions[label_pair],
                                            self.diagram.fine_states[label_pair[0]],
                                            self.diagram.fine_states[label_pair[1]])
        for tran_group in lasers.values():
            for freq_group in tran_group:
                for laser_data in freq_group:
                    self.laser_tree.add_laser(laser_data, tran_group.transition)
        for key_pair in laser_displays:
            for freq in laser_displays[key_pair]:
                self.add_laser_display_from_values(laser_displays[key_pair][freq])
        # endregion

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
        fine_state.delete.connect(partial(self.diagram.delete_fine_state, fine_state.label))

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
        self.laser_tree.add_transition_key(FineTransitionKey(state1.label,state2.label))
        # transition.delete.connect(partial(self.diagram.delete_transition, transition.keys))
        # transition.add_laser.connect(partial(self.add_laser_dialog, transition.keys))

    # endregion

    # region add laser
    def add_laser_dialog(self, transition: FineTransitionKey):
        self.laser_dialog = LaserDialog()

        def add_laser_from_dialog():
            self.laser_tree.add_laser(self.laser_dialog.value(), transition)

        self.laser_dialog.finished.connect(add_laser_from_dialog)
        self.laser_dialog.open()

    # endregion

    # region add laser display
    def add_laser_display_from_values(self, laser_display_data: LaserDisplayData):
        keys = laser_display_data.keys
        if keys in self.diagram.laser_displays:
            if laser_display_data.freq in self.diagram.laser_displays[keys]:
                raise ValueError(
                    "A laser display of this laser energy on this pair of hf states already exists")
        self.diagram.add_laser_display(laser_display_data)

    def add_laser_display_dialog(self, labels, freq):
        label1, label2 = labels
        lower_keys = self.diagram.enabled_hyperfine_substates(label1)
        upper_keys = self.diagram.enabled_hyperfine_substates(label2)
        self.laser_display_dialog = LaserDisplayDialog(self, lower_keys, upper_keys, freq)

        # TODO: make sure to prevent adding duplicate laser displays
        def add_laser_display_from_dialog():
            if self.laser_display_dialog.result():
                self.add_laser_display_from_values(self.laser_display_dialog.value())

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

    def check_existing_laser_display_keys(self, keys, freq) -> bool:
        if keys in self.diagram.laser_displays:
            if freq in self.diagram.laser_displays[keys]:
                return False
        return True

    # endregion

    # region getters
    def fine_state(self, label: str):
        return self.diagram.fine_states[label]

    def transition(self, keys: FineTransitionKey):
        return self.diagram.transitions[keys]

    # endregion

    # region selection handling
    def handle_diagram_selection_changed(self):
        items = self.diagram.selectedItems()
        if items:
            self.laser_tree.blockSignals(True)
            self.laser_tree.clearSelection()
            self.laser_tree.blockSignals(False)
            self.selected_display.selection_changed(items[0])
            self.diagram.show_magnetic_couplings(items[0])
        elif not self.laser_tree.tree_view.selectedIndexes():
            self.selected_display.selection_changed(None)
            self.diagram.show_magnetic_couplings(None)

    def handle_laser_tree_selection_changed(self, item):
        if item is not None:
            self.diagram.blockSignals(True) # prevent Diagram selectionChanged trigger
            self.diagram.clearSelection()
            self.diagram.blockSignals(False)
            self.selected_display.selection_changed(item)
            self.diagram.show_magnetic_couplings(item)
        elif not self.diagram.selectedItems():
            self.selected_display.selection_changed(None)
            self.diagram.show_magnetic_couplings(None)

    # endregion

    def pack_dataframe(self) -> DataFrame:
        # TODO: redo this almost completely
        dataframe = DataFrame(self.I, self.gI)
        if hasattr(self, 'magnetic_field'):
            dataframe.magnetic_field = self.magnetic_field
        fine_state: FineState
        for fine_state in list(self.diagram.fine_states.values()):
            fine_state_data = dataframe.add_fine_state(StateData(fine_state.label,
                                                                 fine_state.energy,
                                                                 self.I,
                                                                 fine_state.J,
                                                                 fine_state.hf_coefs,
                                                                 fine_state.gJ))
            for hf_key in fine_state.hyperfine_keys():
                hf_state = self.diagram.hf_states[hf_key]
                if not hf_state.isEnabled():
                    fine_state_data.substates[hf_state.F] = []
                else:
                    for mf_key in hf_state.magnetic_keys():
                        m_f_state = self.diagram.magnetic_states[mf_key]
                        if not m_f_state.enabled:
                            fine_state_data.substates[hf_state.F].remove(m_f_state.mF)

        for transition in list(self.diagram.transitions.values()):
            label_pair = transition.keys
            dataframe.transitions[label_pair] = TransitionData(transition.gamma)
            dataframe.lasers[label_pair] = []
        for label_group in self.laser_tree.lasers.values():
            label_pair = (label_group.transition.lower_label, label_group.transition.upper_label)
            if label_pair not in dataframe.lasers:
                dataframe.lasers[label_pair] = []
            for freq_group in label_group.freq_groups.values():
                for laser_item in freq_group.lasers:
                    dataframe.lasers[label_pair].append(LaserData(laser_item.freq, laser_item.kvec,
                                                                   laser_item.pol, laser_item.intensity))
        for hf_pair_group in list(self.diagram.laser_displays.values()):
            for laser_display in list(hf_pair_group.values()):
                dataframe.add_laser_display_from_data(LaserDisplayData(laser_display.freq,
                                                                       laser_display.keys,
                                                                       laser_display.upwards))
        return dataframe

    def get_detuning(self, transition: FineTransitionKey, freq: float):
        """
        :return: the detuning of the frequency freq relative to the transition in units of Gamma
        of the transition
        """
        return ((freq
                - (self.fine_state(transition.upper_label).energy
                   - self.fine_state(transition.lower_label).energy))
                /self.diagram.transitions[transition].gamma)
