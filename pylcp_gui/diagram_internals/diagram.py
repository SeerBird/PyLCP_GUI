import logging
from functools import partial

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QGraphicsScene, QGraphicsProxyWidget, QGraphicsItem

from pylcp_gui.config import magnetic_state_width, hyperfine_state_height
from pylcp_gui.dataframe.dataframe import StateData, TransitionData, LaserData, hyperfine_correction
from pylcp_gui.diagram_internals.hyperfine_state import HyperfineState
from pylcp_gui.diagram_internals.laser_beam import LaserBeam
from pylcp_gui.diagram_internals.finestate import FineState, GraphicsDragFilter
import numpy as np

from pylcp_gui.diagram_internals.m_f_state import MagneticState
from pylcp_gui.diagram_internals.manifold_proxy import ManifoldProxy
from pylcp_gui.diagram_internals.transition import Transition
from pylcp_gui.util import addDebugFilter, sort_float_then_string, sort_manifolds, \
    angular_momentum_range

logger: logging.Logger = logging.getLogger(__name__)


class Diagram(QGraphicsScene):

    def __init__(self, I:float):
        super().__init__()
        self.fine_states: dict[str, FineState] = {}
        self.hyperfine_states: dict[str, HyperfineState] = {}
        self.magnetic_states: dict[str, MagneticState] = {}
        self.transitions: dict[frozenset[str], Transition] = {}
        # TODO: decide if I'm keeping the frozenset
        self.lasers: dict[frozenset[str], list[LaserBeam]] = {}
        self.manifold_transition_map: dict[str, list[Transition]] = {}
        self.selected_manifold = None
        self.I = I  # TODO: possibly this breaks when the app closes

    # region adding elements

    def add_fine_state_from_values(self, state_data: StateData, I: float):
        state = FineState(state_data)
        for F in range(angular_momentum_range(state.J, I)):
            hyperfine_active = F in state_data.substates
            hyperfine_state = HyperfineState(state, F, hyperfine_active)
            self.hyperfine_states[hyperfine_state.key] = hyperfine_state
            for mF in range(-F, F + 1):
                magnetic_active = False
                if hyperfine_active:
                    magnetic_active = mF in state_data.substates[F]
                magnetic_state = MagneticState(hyperfine_state, mF, magnetic_active)
                self.magnetic_states[magnetic_state.key] = magnetic_state
        state.delete.connect(partial(self.delete_manifold, state.label))
        self.fine_states[state.label] = state
        self.addItem(state)
        state.setX(0)
        self.manifold_transition_map[state.label] = []
        self.rearrange()
        return state

    def add_transition_from_values(self, transition_data: TransitionData,
                                   manifold1: FineState, manifold2: FineState):
        transition = Transition(transition_data, manifold1, manifold2)
        self.transitions[frozenset(transition.labels)] = transition
        self.manifold_transition_map[manifold1.label].append(transition)
        self.manifold_transition_map[manifold2.label].append(transition)
        self.lasers[frozenset(transition.labels)] = []
        self.addItem(transition)
        return transition

    def add_laser_from_values(self, laser_data: LaserData, labels: tuple[str, str]):
        laser = LaserBeam(laser_data, labels)
        self.lasers[frozenset(labels)].append(laser)
        return laser

    # endregion

    # region deleting elements
    def removeItemDeferred(self, item: QGraphicsItem):
        QTimer.singleShot(0, partial(self.removeItem, item))

    def delete_transition(self, labels: tuple[str, str]):
        transition = self.transitions[frozenset(labels)]
        self.manifold_transition_map[labels[0]].remove(transition)
        self.manifold_transition_map[labels[1]].remove(transition)
        self.transitions.pop(frozenset(transition.labels))
        transition.deleteLater()
        logger.debug(f"Deleting transition")

    def delete_manifold(self, label: str):
        manifold = self.fine_states[label]
        transitions = self.manifold_transition_map[label].copy()
        for transition in transitions:
            self.delete_transition(transition.labels)
        self.manifold_transition_map.pop(label)
        self.fine_states.pop(label)
        proxy = manifold.graphicsProxyWidget()
        assert proxy is not None
        proxy.deleteLater()
        logger.debug(f"Deleting manifold")

    # endregion

    def manifoldMoved(self, label: str):
        for transition in self.manifold_transition_map[label]:
            p1 = self.fine_states[transition.labels[0]].geometry().center()
            p2 = self.fine_states[transition.labels[1]].geometry().center()
            transition.trackNodes(p1, p2)

    def rearrange(self):
        I = self.I
        self.setSceneRect(self.views()[0].rect())  # TODO: this is iffy
        fine_states = np.asarray(list(self.fine_states.values()))
        if fine_states.size == 0:
            return
        # region get mF range, assumed symmetric
        max_mF = 0
        for magnetic_state in self.magnetic_states.values():
            if magnetic_state.mF > max_mF:
                max_mF = magnetic_state.mF
        # endregion
        # TODO: no real point in sorting by label as well
        sort = sort_float_then_string([fine_state.energy for fine_state in fine_states],
                                      [fine_state.label for fine_state in fine_states])
        # sorted in increasing energy, label order
        fine_states = fine_states[sort]
        y_tracker = 0
        fine_state: FineState
        for fine_state in fine_states:
            # region sort hyperfine substates in increasing energy,F order
            J = fine_state.J
            hf_states = np.asarray(
                [self.hyperfine_states[key] for key in fine_state.hyperfine_keys()])
            sort = sort_float_then_string(
                [hyperfine_correction(J, I, hf_state.F, fine_state.hf_coefs)
                 for hf_state in hf_states],
                [hyperfine_state.key for hyperfine_state in hf_states])
            # endregion
            hf_states = hf_states[sort]
            # TODO: do I want removal and addition of hf states to disable/enable them or actually
            #  remove and add them? might as well keep them in memory, right?
            # only keep enabled states
            hf_states = hf_states[np.asarray([hf_state.enabled for hf_state in hf_states])]
            # TODO: switch to spacing dependent on energy
            fine_state_height = len(hf_states) * hyperfine_state_height
            for hf_i in range(len(hf_states)):
                hf_state: HyperfineState = hf_states[hf_i]
                hf_state.setY(-fine_state_height + (hf_i + 0.5) * hyperfine_state_height)
                # sorted in increasing mF order
                # TODO: optimally this should only be done once when the hf_state is added,
                #  as mF positions are relative to hf positions, and only change when hf gets
                #  slid horizontally (yeah this to-do is incomprehensible)
                mF_states = [self.magnetic_states[key] for key in hf_state.magnetic_keys()]
                mF_state: MagneticState
                for mF_state in mF_states:
                    mF = mF_state.mF
                    # TODO: decide between using config constants and .width(), .height()
                    #  for clarity
                    mF_state.setX(hf_state.width() + (mF + max_mF) * magnetic_state_width)

            fine_state.setY(y_tracker + self.height()/2)
            y_tracker += self.height()
