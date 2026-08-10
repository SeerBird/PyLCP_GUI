import logging
from functools import partial

import numpy as np
from PySide6.QtCore import QTimer, QPointF, QEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsItem, QGraphicsView

from pylcp_gui.config import magnetic_state_width, hf_state_height, hf_state_width, \
    fine_state_width, fine_state_vertical_empty_space_proportion, \
    diagram_fine_state_view_proportion, diagram_fine_state_spacer_view_proportion
from pylcp_gui.dataframe.dataframe import StateData, TransitionData, hyperfine_correction, \
    LaserDisplayData
from pylcp_gui.diagram_internals import laser_display
from pylcp_gui.diagram_internals.draggable_line import DraggableLine
from pylcp_gui.diagram_internals.fine_state import FineState
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
        self.hf_states: dict[HyperfineKey, HyperfineState] = {}
        self.magnetic_states: dict[MagneticKey, MagneticState] = {}
        self.transitions: dict[tuple[str, str], Transition] = {}
        self.laser_displays: dict[tuple[HyperfineKey, HyperfineKey], dict[float, LaserDisplay]] = {}
        # TODO: decide if I'm keeping the frozenset
        self.lasers: dict[tuple[str, str], list[LaserDisplay]] = {}
        self.state_transition_map: dict[str, list[Transition]] = {}
        self.selected_manifold = None
        self.I = I
        # region geometry
        self.hyperfine_width = hf_state_width
        # endregion
        self.draggable_line = DraggableLine()
        QTimer.singleShot(0, self.add_initial_items)

    # region setup
    def add_initial_items(self):
        self.addItem(self.draggable_line)
        self.draggable_line.setX(fine_state_width + hf_state_width)
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
            self.hf_states[hyperfine_state.key] = hyperfine_state
            hyperfine_state.moved.connect(self.resolve_laser_display_anchors)
            hyperfine_state.delete.connect(self.delete_hyperfine_state)
            for mF in np.arange(-F, F + 1):
                magnetic_active = False
                if hyperfine_active:
                    magnetic_active = mF in state_data.substates[F]
                magnetic_state = MagneticState(hyperfine_state, mF, magnetic_active)
                magnetic_state.setX(hf_state_width)
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
        transition.setZValue(2)
        self.transitions[transition.keys] = transition
        self.state_transition_map[state1.label].append(transition)
        self.state_transition_map[state2.label].append(transition)
        self.addItem(transition)
        self.update()  # TODO: add bounding rect?
        return transition

    def add_laser_display(self, display_data: LaserDisplayData):
        """
        Relies on the new display_data not having the same keys and frequency as an existing display
        """
        keys = display_data.keys
        display = LaserDisplay(display_data)
        display.setX(fine_state_width)
        if not keys in self.laser_displays:
            self.laser_displays[keys] = {display.freq: display}
        else:
            self.laser_displays[keys][display.freq] = display
        display.delete.connect(self.delete_laser_display)
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

    def delete_laser_display(self, keys: tuple[HyperfineKey, HyperfineKey], freq: float):
        laser_display = self.laser_displays[keys][freq]
        self.laser_displays[keys].pop(freq)
        laser_display.deleteLater()

    def delete_fine_state(self, label: str):
        state = self.fine_states[label]
        transitions = self.state_transition_map[label].copy()
        for transition in transitions:
            self.delete_transition(transition.keys)
        self.state_transition_map.pop(label)
        self.fine_states.pop(label)
        state.deleteLater()
        self.rearrange()

    def delete_hyperfine_state(self, key: HyperfineKey):
        hf_state = self.hf_states[key]
        hf_state.toggleEnabled()
        for hf_key_pair in self.laser_displays:
            if key in hf_key_pair:
                display_dict = self.laser_displays[hf_key_pair]
                for freq in list(display_dict.keys()):
                    laser_display = display_dict[freq]
                    display_dict.pop(freq)
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
        fine_states = fine_states[sort][::-1]  # sorted in increasing energy, label order

        view_height = self.get_visible_scene_bounds()[2]
        y_tracker = 0  # top of current fine state
        fine_state: FineState
        for fine_state in fine_states:
            # region Sort hyperfine substates in decreasing energy, F order
            hf_states = np.asarray(
                [self.hf_states[key] for key in fine_state.hyperfine_keys()])
            energies = np.asarray(
                [hf_state.hf_correction() for hf_state in hf_states])
            sort = sort_float_then_string(energies,
                                          [str(hyperfine_state) for hyperfine_state in hf_states])
            # endregion
            hf_states = hf_states[sort][::-1]
            energies = energies[sort][::-1]
            # Only keep enabled states
            hf_states = hf_states[np.asarray([hf_state.isEnabled() for hf_state in hf_states])]
            # Each fine state takes up at least the config-defined proportion of the view height,
            # and more if it contains enough hyperfine states to maintain the right proportion of
            # empty space in the fine state
            fine_state_total_height = max(view_height * diagram_fine_state_view_proportion,
                                          (len(hf_states) * hf_state_height /
                                           (1 - fine_state_vertical_empty_space_proportion)))

            if len(hf_states) != 0:
                # region Get hf_state positions relative to fine state top
                max_E: float = np.max(energies)
                min_E: float = np.min(energies)
                if max_E == min_E:
                    # Spread out evenly
                    positions = np.linspace(hf_state_height / 2,
                                            fine_state_total_height - hf_state_height / 2,
                                            len(hf_states) + 1)[:-1]
                else:
                    positions = (hf_state_height / 2  # top hf_state position
                                 + (max_E - energies) / (max_E - min_E)  # value from 0 to 1
                                 * (fine_state_total_height - hf_state_height)  # position range
                                 )
                    # region Make sure there are no overlaps
                    spacings = positions[1:] - positions[:-1] - hf_state_height
                    overlapping = spacings < 0
                    # Scale down positive spacings to increase negative spacings to zero, keeping
                    # total height the same
                    spacings[~overlapping] *= (1 + np.sum(spacings[overlapping])
                                               / np.sum(spacings[~overlapping]))
                    spacings[overlapping] = 0
                    positions = np.zeros(positions.size) + hf_state_height / 2
                    positions[1:] += np.cumsum(spacings + hf_state_height)
                    # endregion
                # endregion
                for hf_i in range(len(hf_states)):
                    hf_state: HyperfineState = hf_states[hf_i]
                    hf_state.prepareGeometryChange()
                    hf_state.progSetY(positions[hf_i] - fine_state_total_height / 2)
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
            y_tracker += (fine_state_total_height +
                          view_height * diagram_fine_state_spacer_view_proportion)

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
    def get_visible_scene_bounds(self) -> tuple[float, float, float]:
        """Returns (top_y, bottom_y, total_height) in scene coordinates."""
        view = self.views()[0]
        viewport_rect = view.viewport().rect()

        # Map the top-left and bottom-right viewport pixels into scene space
        top_left_scene = view.mapToScene(viewport_rect.topLeft())
        bottom_right_scene = view.mapToScene(viewport_rect.bottomRight())

        top_y = top_left_scene.y()
        bottom_y = bottom_right_scene.y()
        visible_height = bottom_y - top_y

        return top_y, bottom_y, visible_height

    def get_hf_state(self, key):
        return self.hf_states[key]

    def get_hf_energy(self, key):
        fine_state = self.fine_states[key[0]]
        return fine_state.energy + hyperfine_correction(fine_state.J, self.I, key[1],
                                                        fine_state.hf_coefs)

    def enabled_hyperfine_substates(self, label: str):
        fine_state = self.fine_states[label]
        enabled_substates = []
        for hf_key in fine_state.hyperfine_keys():
            if self.hf_states[hf_key].isEnabled():
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
        new_x = max(new_x, fine_state_width + hf_state_width)
        hf_state: HyperfineState
        validated_new_x = new_x  # TODO: change x positions of magnetic and hf states
        for mf_state in self.magnetic_states.values():
            mf_state.progSetX(mf_state.x() + validated_new_x - prev_x)
        for hf_state in self.hf_states.values():
            right = hf_state.x() + hf_state_width
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
        # region regroup displays by target
        displays_by_target = {}
        for freq_group in self.laser_displays.values():
            for laser_display in freq_group.values():
                target_key = laser_display.keys()[1]
                if not target_key in displays_by_target:
                    displays_by_target[target_key] = []
                displays_by_target[target_key].append(laser_display)
        # endregion
        for target_key in displays_by_target:
            # TODO: add horizontal shift to multiple displays with same target
            target_state: HyperfineState = self.hf_states[target_key]
            target_displays = displays_by_target[target_key]
            anchor_xs = target_state.laser_display_anchors(len(target_displays))
            for i in range(len(target_displays)):
                laser_display = target_displays[i]
                origin_state = self.hf_states[laser_display.keys()[0]]
                origin = origin_state.scenePos() + QPointF(0.5 * origin_state.width(), 0)
                target = target_state.scenePos() + QPointF(anchor_xs[i], 0)
                delta = laser_display.freq - (abs(origin_state.energy() - target_state.energy()))
                if delta == 0:
                    laser_display.setAnchors(origin, target, 0)
                    continue
                # get all hf_states in the target fine structure manifold
                target_hf_states = np.asarray([self.hf_states[key]
                                               for key in
                                               target_state.parentItem().hyperfine_keys()])
                # energies relative to the laser indicator energy
                energies = (np.asarray([hf_state.hf_correction() for hf_state in target_hf_states])
                            - target_state.hf_correction() - delta)
                below_index = np.where(energies <= 0, energies, -np.inf).argmax()
                above_index = np.where(energies >= 0, energies, np.inf).argmax()
                below_energy = energies[below_index]
                above_energy = energies[above_index]
                if below_energy > 0 or above_energy < 0:  # the laser display has a
                    # lower or higher energy indicator than all relevant hf states
                    below_energy = energies[0]
                    above_energy = energies[-1]
                    below_index = 0
                    above_index = -1
                    # TODO: in this case, ensure the indicator is not going too far off
                below_y = target_hf_states[below_index].y()
                above_y = target_hf_states[above_index].y()
                # TODO: ensure nothing's too close together
                y = below_y + (above_y - below_y) * (0 - below_energy) / (
                        above_energy - below_energy)
                laser_display.setAnchors(origin, target, y -
                                         target_state.parentItem().mapFromScene(target).y())
