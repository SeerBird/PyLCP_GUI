import logging
from functools import partial

import numpy as np
from PySide6.QtCore import QTimer, QPointF, QEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsItem, QGraphicsView

from pylcp_gui.config import magnetic_state_width, hf_state_height, hf_state_width, \
    fine_state_width, fine_state_vertical_empty_space_proportion, \
    diagram_fine_state_view_proportion, diagram_fine_state_spacer_view_proportion, \
    hf_width_drawn_proportion
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
        logger.debug(f"Deleting fine structure state")

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
        fine_states = fine_states[sort]  # sorted in increasing energy, label order

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
        views = self.views()
        if not views:
            return 0.0, 600.0, 600.0
        view = views[0]
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
        views = self.views()
        if not views:
            return
        view = views[0]
        topLeft = view.mapToScene(view.viewport().rect().topLeft())
        bottomLeft = view.mapToScene(view.viewport().rect().bottomLeft())
        self.draggable_line.setExtent(topLeft.y(), bottomLeft.y())

    def resolve_laser_display_anchors(self):
        # Group laser displays by target hyperfine state
        displays_by_target: dict[HyperfineKey, list[LaserDisplay]] = {}
        for display_dict in self.laser_displays.values():
            for display in display_dict.values():
                target_key = display.keys()[1]
                displays_by_target.setdefault(target_key, []).append(display)

        for target_key, displays in displays_by_target.items():
            target_state = self.hf_states[target_key]
            n_displays = len(displays)

            target_scene_x = target_state.scenePos().x()
            target_w = target_state.width()
            pad_prop = (1.0 - hf_width_drawn_proportion) / 2.0
            left_x = target_scene_x + target_w * (pad_prop + 0.1)
            right_x = target_scene_x + target_w * (1.0 - pad_prop - 0.1)
            if n_displays == 1:
                xs = [target_scene_x + 0.5 * target_w]
            else:
                xs = np.linspace(left_x, right_x, n_displays)

            target_manifold_keys = [k for k in target_state.parentItem().hyperfine_keys()
                                    if k in self.hf_states and self.hf_states[k].isEnabled()]
            manifold_hf_states = [self.hf_states[k] for k in target_manifold_keys]
            manifold_hf_states.sort(key=lambda s: s.energy())
            state_energies = np.array([s.energy() for s in manifold_hf_states])
            state_y_scene = np.array([s.scenePos().y() for s in manifold_hf_states])

            for idx, laser_display in enumerate(displays):
                origin_key = laser_display.keys()[0]
                origin_state = self.hf_states[origin_key]
                origin = origin_state.scenePos() + QPointF(0.5 * origin_state.width(), 0)

                target_x = xs[idx]
                target_y = target_state.scenePos().y()
                target = QPointF(target_x, target_y)

                E_res = abs(origin_state.energy() - target_state.energy())
                detuning_E = (laser_display.freq - E_res) * (1 if laser_display.upwards else -1)

                if detuning_E == 0 or len(manifold_hf_states) == 0:
                    laser_display.setAnchors(origin, target, 0, 0.0)
                    continue

                E_target_laser = target_state.energy() + detuning_E

                if len(manifold_hf_states) == 1:
                    scale = 0.3 * target_state.height()
                    y_indicator = target_y - detuning_E * scale
                else:
                    if E_target_laser >= state_energies[-1]:
                        denom = (state_energies[-1] - state_energies[-2])
                        slope = (state_y_scene[-1] - state_y_scene[-2]) / (denom if denom != 0 else 1.0)
                        y_indicator = state_y_scene[-1] + slope * (E_target_laser - state_energies[-1])
                    elif E_target_laser <= state_energies[0]:
                        denom = (state_energies[1] - state_energies[0])
                        slope = (state_y_scene[1] - state_y_scene[0]) / (denom if denom != 0 else 1.0)
                        y_indicator = state_y_scene[0] + slope * (E_target_laser - state_energies[0])
                    else:
                        idx_above = int(np.searchsorted(state_energies, E_target_laser))
                        idx_below = idx_above - 1
                        E1, E2 = state_energies[idx_below], state_energies[idx_above]
                        Y1, Y2 = state_y_scene[idx_below], state_y_scene[idx_above]
                        if E2 == E1:
                            y_indicator = Y1
                        else:
                            frac = (E_target_laser - E1) / (E2 - E1)
                            y_indicator = Y1 + frac * (Y2 - Y1)

                delta_y = y_indicator - target_y

                min_state_gap = 6.0
                for s_y in state_y_scene:
                    if abs(y_indicator - s_y) < min_state_gap and abs(y_indicator - s_y) > 1e-4:
                        nudge = min_state_gap - abs(y_indicator - s_y)
                        if y_indicator < s_y:
                            delta_y -= nudge
                        else:
                            delta_y += nudge

                laser_display.setAnchors(origin, target, delta_y, detuning_E)
