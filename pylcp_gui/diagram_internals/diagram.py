import logging
from functools import partial

import numpy as np
from PySide6.QtCore import QTimer, QPointF, QEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsItem

from pylcp_gui.config import magnetic_state_width, hyperfine_state_height, hyperfine_state_width, \
    fine_state_width
from pylcp_gui.dataframe.dataframe import StateData, TransitionData, hyperfine_correction, \
    LaserDisplayData
from pylcp_gui.diagram_internals.draggable_line import DraggableLine
from pylcp_gui.diagram_internals.finestate import FineState
from pylcp_gui.diagram_internals.hyperfine_state import HyperfineState
from pylcp_gui.diagram_internals.laser_display import LaserDisplay
from pylcp_gui.diagram_internals.m_f_state import MagneticState
from pylcp_gui.diagram_internals.transition import Transition
from pylcp_gui.util import sort_float_then_string, HyperfineKey, MagneticKey

logger: logging.Logger = logging.getLogger(__name__)


class Diagram(QGraphicsScene):

    def __init__(self, I: float | None):
        super().__init__()
        self.fine_states: dict[str, FineState] = {}
        self.hyperfine_states: dict[HyperfineKey, HyperfineState] = {}
        self.magnetic_states: dict[MagneticKey, MagneticState] = {}
        self.transitions: dict[tuple[str, str], Transition] = {}
        self.laser_displays: dict[tuple[HyperfineKey, HyperfineKey], list[LaserDisplay]] = {}
        # TODO: decide if I'm keeping the frozenset
        self.lasers: dict[tuple[str, str], list[LaserDisplay]] = {}
        self.state_transition_map: dict[str, list[Transition]] = {}
        self.selected_manifold = None
        self.I = I
        # region geometry
        self.hyperfine_width = hyperfine_state_width
        # endregion
        self.draggable_line = DraggableLine()
        QTimer.singleShot(0, self.add_initial_items)

    # region setup
    def add_initial_items(self):
        self.addItem(self.draggable_line)
        self.draggable_line.setX(fine_state_width + hyperfine_state_width)
        self.draggable_line.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.rearrange()

    # endregion

    # region adding elements

    def add_fine_state_from_values(self, state_data: StateData):
        state = FineState(state_data)
        for F in state_data.substates:
            hyperfine_active = bool(state_data.substates[F])
            hyperfine_state = HyperfineState(state, F)
            hyperfine_state.setEnabled(hyperfine_active)
            hyperfine_state.progSetX(fine_state_width)
            self.hyperfine_states[hyperfine_state.key] = hyperfine_state
            hyperfine_state.moved.connect(self.resolve_laser_display_anchors)
            hyperfine_state.delete.connect(self.delete_hyperfine_state)
            for mF in np.arange(-F, F + 1):
                magnetic_active = False
                if hyperfine_active:
                    magnetic_active = mF in state_data.substates[F]
                magnetic_state = MagneticState(hyperfine_state, mF, magnetic_active)
                magnetic_state.setX(hyperfine_state_width)
                self.magnetic_states[magnetic_state.key] = magnetic_state
        # state.delete.connect(partial(self.delete_state, state.label))
        self.fine_states[state.label] = state
        self.addItem(state)
        state.setX(0)
        self.state_transition_map[state.label] = []
        self.rearrange()
        return state

    def add_transition_from_values(self, transition_data: TransitionData,
                                   state1: FineState, state2: FineState):
        transition = Transition(transition_data, state1, state2)
        self.transitions[transition.keys] = transition
        self.state_transition_map[state1.label].append(transition)
        self.state_transition_map[state2.label].append(transition)
        self.lasers[transition.keys] = []
        self.addItem(transition)
        self.update()  # TODO: add bounding rect?
        return transition

    def add_laser_display(self, display_data: LaserDisplayData):
        keys = display_data.keys
        display = LaserDisplay(display_data)
        display.setX(fine_state_width)
        if not keys in self.laser_displays:
            self.laser_displays[keys] = [display]
        else:
            self.laser_displays[keys].append(display)
        self.addItem(display)
        self.rearrange()

    # endregion

    # region deleting elements
    def delete_transition(self, labels: tuple[str, str]):
        transition = self.transitions[labels]
        self.state_transition_map[labels[0]].remove(transition)
        self.state_transition_map[labels[1]].remove(transition)
        self.transitions.pop(labels)
        transition.deleteLater()
        logger.debug(f"Deleting transition")

    def delete_fine_state(self, label: str):
        state = self.fine_states[label]
        transitions = self.state_transition_map[label].copy()
        for transition in transitions:
            self.delete_transition(transition.keys)
        self.state_transition_map.pop(label)
        self.fine_states.pop(label)
        state.deleteLater()
        logger.debug(f"Deleting fine structure state")

    def delete_hyperfine_state(self, key: HyperfineKey):
        hf_state = self.hyperfine_states[key]
        hf_state.parentItem().prepareGeometryChange()
        hf_state.toggleEnabled()
        for hf_key_pair in self.laser_displays:
            if key in hf_key_pair:
                display_list = self.laser_displays[hf_key_pair]
                for laser_display in display_list:
                    display_list.remove(laser_display)
                    laser_display.deleteLater()
        self.rearrange()

    # endregion

    def rearrange(self):
        I = self.I
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
                [str(hyperfine_state) for hyperfine_state in hf_states])
            # endregion
            hf_states = hf_states[sort][::-1]
            # only keep enabled states
            hf_state: HyperfineState
            hf_states = hf_states[np.asarray([hf_state.isEnabled() for hf_state in hf_states])]
            # TODO: switch to spacing dependent on energy
            fine_state_height = len(hf_states) * hyperfine_state_height
            for hf_i in range(len(hf_states)):
                hf_state: HyperfineState = hf_states[hf_i]
                hf_state.prepareGeometryChange()
                hf_state.progSetY(-fine_state_height / 2 + (hf_i + 0.5) * hyperfine_state_height)
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
                    mf_state_x = hf_state.mapFromItem(
                        self.draggable_line,
                        QPointF((mF + max_mF) * magnetic_state_width, 0)).x()
                    mF_state.progSetX(mf_state_x)

            fine_state.progSetY(y_tracker + fine_state.height() / 2)
            logger.debug(f"Children: {fine_state.childrenBoundingRect()}")
            logger.debug(f"Whole: {fine_state.boundingRect()}")
            y_tracker += fine_state.height()

        transition: Transition
        for transition in self.transitions.values():
            origin_state, target_state = [self.fine_states[key] for key in transition.keys]
            origin = QPointF(origin_state.x() + 0.5 * origin_state.width(), origin_state.y())
            target = QPointF(target_state.x() + 0.5 * target_state.width(), target_state.y())
            transition.setAnchors(origin, target)
        self.resolve_laser_display_anchors()
        self.refresh_line_extent()
        self.update()

    # region getters
    def get_hf_state(self, key):
        return self.hyperfine_states[key]

    def get_hf_energy(self, key):
        fine_state = self.fine_states[key[0]]
        return fine_state.energy + hyperfine_correction(fine_state.J, self.I, key[1],
                                                        fine_state.hf_coefs)

    def enabled_hyperfine_substates(self, label: str):
        fine_state = self.fine_states[label]
        enabled_substates = []
        for hf_key in fine_state.hyperfine_keys():
            if self.hyperfine_states[hf_key].isEnabled():
                enabled_substates.append(hf_key)
        return enabled_substates

    def hf_region_width(self):
        return self.draggable_line.x() - fine_state_width

    # endregion

    def eventFilter(self, watched, event, /):
        if watched == self.views()[0].viewport():
            if event.type() == QEvent.Type.Resize:
                self.refresh_line_extent()
        return super().eventFilter(watched, event)

    def hf_region_resize(self, new_x: float) -> float:
        prev_x = self.draggable_line.x()
        new_x = max(new_x, fine_state_width + hyperfine_state_width)
        hf_state: HyperfineState
        validated_new_x = new_x  # TODO: change x positions of magnetic and hf states
        for mf_state in self.magnetic_states.values():
            mf_state.progSetX(mf_state.x() + validated_new_x - prev_x)
        for hf_state in self.hyperfine_states.values():
            right = hf_state.x() + hyperfine_state_width
            if validated_new_x < right:
                hf_state.progSetX(hf_state.x() + validated_new_x - right)
        return validated_new_x

    def refresh_line_extent(self):
        view = self.views()[0]
        topLeft = view.mapToScene(view.viewport().rect().topLeft())
        bottomLeft = view.mapToScene(view.viewport().rect().bottomLeft())
        self.draggable_line.setExtent(topLeft.y(), bottomLeft.y())

    def resolve_laser_display_anchors(self):
        laser_display: LaserDisplay
        for laser_display_list in self.laser_displays.values():
            for laser_display in laser_display_list:
                keys = laser_display.keys()
                origin_state, target_state = [self.hyperfine_states[key] for key in keys]
                origin_pos = origin_state.scenePos()
                target_pos = target_state.scenePos()
                origin = QPointF(origin_pos.x() + 0.5 * origin_state.width(), origin_pos.y())
                target = QPointF(target_pos.x() + 0.5 * target_state.width(), target_pos.y())
                delta = (abs(self.get_hf_energy(keys[0]) - self.get_hf_energy(keys[1])) -
                         laser_display.freq) * (-1 if laser_display.upwards else 1)
                laser_display.setAnchors(origin, target,
                                         0.3 * target_state.height() * np.sign(delta))
