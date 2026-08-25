from __future__ import annotations

import logging
import pickle
from enum import Enum
from os import PathLike

import numpy as np
import pylcp
from pylcp import infinitePlaneWaveBeam, atom as Pylcp_atom
from pylcp.atom import state as Pylcp_state
from scipy.constants import c, h, elementary_charge

from pylcp_gui.dataframe.dataframe_internals import StateData, TransitionData, LaserTransitionGroup, \
    LaserDisplayData, LaserFreqGroup, LaserData
from pylcp_gui.util import sort_float_then_string, HyperfineKey, MagneticFieldObject, \
    HFTransitionKey, FineTransitionKey, hyperfine_correction, get_state_basis, \
    mu_q_coupled, _d_q_matrix_element

logger: logging.Logger = logging.getLogger(__name__)


class Atom(Enum):
    Li6 = "Li6"
    Li7 = "Li7"
    Na23 = "Na23"
    K39 = "K39"
    K40 = "K40"
    K41 = "K41"
    Rb85 = "Rb85"
    Rb87 = "Rb87"
    Cs133 = "Cs133"


class DataFrame:
    def __init__(self, I, gI):
        """
        :param I:
        :param gI:
        """
        self.I: float = I
        self.gI = gI
        self.fine_states: dict[str, StateData] = {}
        # keys are label tuples in increasing energy order
        self.transitions: dict[FineTransitionKey, TransitionData] = {}
        self.lasers: dict[FineTransitionKey, LaserTransitionGroup] = {}
        self.laser_displays: dict[HFTransitionKey, dict[float, LaserDisplayData]] = {}
        self.magnetic_field: MagneticFieldObject = np.zeros(3)

    @staticmethod
    def load_from_file(path: PathLike | str) -> DataFrame:
        with open(path, 'rb') as f:
            return pickle.load(f)

    def save(self, path: PathLike | str):
        with open(path, 'wb') as f:
            pickle.dump(self, f)

    # region get pylcp results
    def obe(self):
        ham = self._hamiltonian()
        lasers = self._lasers()
        return pylcp.obe(lasers, self.magnetic_field, ham)

    def rateeq(self):
        return pylcp.rateeq(self._lasers(), self.magnetic_field, self._hamiltonian(),
                            include_mag_forces=False)

    # endregion
    # region building the dataframe
    @classmethod
    def create_from_atom(cls, atom: Atom):
        atom_data = Pylcp_atom(atom.value)
        states = atom_data.state
        frame = DataFrame(atom_data.I, atom_data.gI)
        if len(states) == 0:
            return frame  # This shouldn't happen, ever, but it's fine if it does
        elif len(states) == 1:
            labels = ['g']  # This shouldn't happen either, but it's fine
        elif len(states) == 2:
            labels = ['g', 'e']
        else:
            labels = ['g']
            for i in range(1, len(states)):
                labels.append(f"e{i}")
        # region add all fine structure states
        for i in range(len(states)):
            state: Pylcp_state = states[i]
            frame.add_fine_state(labels[i],
                                 state.energy * 1e2 * c,
                                 state.J,
                                 (state.Ahfs, state.Bhfs, state.Chfs),
                                 state.gJ)
        # endregion
        # region add all transitions
        for i in range(1, len(states)):
            state: Pylcp_state = states[i]
            excited_state = frame.fine_states[labels[i]]
            frame.add_transition(labels[0], labels[i], state.gammaHz)
        # endregion
        return frame

    def set_magnetic_field(self, magnetic_field: MagneticFieldObject):
        self.magnetic_field = magnetic_field

    def add_fine_state(self, label: str, energy: float, J: float,
                       hf_coefs: tuple[float, float, float], gJ: float):
        fine_state = StateData(label, energy, self.I, J, hf_coefs, gJ)
        self.fine_states[label] = fine_state
        return fine_state

    def add_transition(self, label1, label2, gamma: float):
        key = FineTransitionKey(label1, label2)
        self.transitions[key] = TransitionData(gamma)
        self.lasers[key] = LaserTransitionGroup(key)

    def add_laser(self, label1, label2, F1, F2, delta, kvec, pol, intensity):
        """
        :param label1: lower state label
        :param label2: upper state label
        :param F1:
        :param F2:
        :param delta: in (global) gamma units, relative to the F1-F2 transition
        :param kvec: unit vector in spherical coords
        :param pol: +1 or -1, or an np.ndarray in spherical polar coordinates, or a callable
        :param intensity: normalized to the saturation intensity
        :return:
        """

        key1, key2 = HyperfineKey(label1, F1), HyperfineKey(label2, F2)
        hf_transition = HFTransitionKey(key1, key2)
        fine_transition = hf_transition.to_fine_transition()
        transition_energy = self.hf_energy(key2) - self.hf_energy(key1)
        freq = transition_energy + delta * self._principal_gamma_and_energy()[0]
        if not fine_transition in self.lasers:
            raise ValueError()
        transition_group = self.lasers[fine_transition]
        if freq in transition_group.freq_groups:
            freq_group = transition_group.freq_groups[freq]
        else:
            enabled_transitions = []
            lower_state = self.fine_states[fine_transition.lower_label]
            upper_state = self.fine_states[fine_transition.upper_label]
            for hfkey1 in lower_state.hyperfine_keys():
                if not lower_state.substates[hfkey1.F]:
                    continue
                for hfkey2 in upper_state.hyperfine_keys():
                    if not upper_state.substates[hfkey2.F]:
                        continue
                    enabled_transitions.append(HFTransitionKey(hfkey1, hfkey2))

            freq_group = LaserFreqGroup(freq, fine_transition, enabled_transitions)
            transition_group.freq_groups[freq] = freq_group

        freq_group.add_laser(LaserData(freq, kvec, pol, intensity
                                       * self._saturation_intensity(hf_transition)))

    def add_laser_display(self, freqIndex: int, F_ground: float, F_excited: float,
                          ground_label="g", excited_label="e", upwards: bool = True) -> None:
        """

        :param freqIndex: the index of the frequency group, in ascending order.
        Example: if this is the lowest-frequency laser coupling this !fine! state pair,
        the index is 0, second lowest — 1, and so on.
        :param F_ground:
        :param F_excited:
        :param ground_label:
        :param excited_label:
        :param upwards: True if the display has the detuning indicator on the upper state,
         false if on the lower
        """
        keys = HFTransitionKey(HyperfineKey(ground_label, float(F_ground)),
                               HyperfineKey(excited_label, float(F_excited)))
        fine_transition = keys.to_fine_transition()
        freqs = list(self.lasers[fine_transition].freqs())
        freq = np.sort(np.asarray(freqs))[freqIndex]
        self.add_laser_display_from_data(LaserDisplayData(freq, keys, upwards))

    def add_laser_display_from_data(self, display_data: LaserDisplayData):
        keys = display_data.keys
        if keys in self.laser_displays:
            if display_data.freq in self.laser_displays[keys]:
                raise ValueError(
                    "A laser display of this laser energy on this pair of hf states already exists")
        self.laser_displays.setdefault(keys, {})[display_data.freq] = display_data

    # endregion
    # region building the dataframe helpers

    # endregion
    # region results helpers
    def hf_energy(self, key: HyperfineKey):
        fine_state = self.fine_states[key.label]
        return fine_state.energy + hyperfine_correction(fine_state.J, self.I, key.F,
                                                        fine_state.hf_coefs)

    def _hamiltonian(self):
        ham = pylcp.hamiltonian()
        ref_gamma: float = self._principal_gamma_and_energy()[0]
        # rest frame electronic energies
        labels = np.asarray(list(self.fine_states.keys()))
        energies = np.asarray([self.fine_states[label].energy for label in labels])
        sort = sort_float_then_string(energies, labels)
        labels = labels[sort]  # in the order the blocks should be added
        hf_bases = {}
        # region H_0 & mu_q per hyperfine manifold
        for state_label in labels:
            fine_state: StateData = self.fine_states[state_label]
            active_Fs = [F for F, mFs in fine_state.substates.items() if len(mFs) > 0]
            if not active_Fs:
                continue
            Fs = np.asarray(active_Fs)
            sort = np.argsort(hyperfine_correction(fine_state.J, self.I, Fs,
                                                   fine_state.hf_coefs))
            Fs = Fs[sort]

            for idx, F in enumerate(Fs):
                block_name = str(HyperfineKey(state_label, F))
                basis = get_state_basis(fine_state, [F])
                # TODO: this reuses old code,
                #  make something that matches the new architecture cleaner
                hf_bases[HyperfineKey(state_label, F)] = (block_name, basis)

                # H_0 block (zeros as we're in the rotating frame of each hyperfine state)
                mF_count = len(fine_state.substates[F])
                ham.add_H_0_block(block_name, np.zeros((mF_count, mF_count)))

                # mu_q block
                mu_q = mu_q_coupled(basis, fine_state.gJ, self.gI, fine_state.J, self.I)
                ham.add_mu_q_block(block_name, mu_q)
        # endregion
        # region d_q between active hyperfine pairs
        for traverse_label_pair in self.transitions.keys():
            label1, label2 = traverse_label_pair
            state_1 = self.fine_states[label1]
            state_2 = self.fine_states[label2]
            J1, J2 = state_1.J, state_2.J
            transition_energy = np.abs(state_1.energy - state_2.energy)
            transition_gamma = self.transitions[traverse_label_pair].gamma

            active_Fs1 = [F for F, mFs in state_1.substates.items() if len(mFs) > 0]
            active_Fs2 = [F for F, mFs in state_2.substates.items() if len(mFs) > 0]

            for F1 in active_Fs1:
                for F2 in active_Fs2:
                    if (HyperfineKey(label1, F1) not in hf_bases or
                            HyperfineKey(label2, F2) not in hf_bases):
                        continue
                    b1_name, basis1 = hf_bases[(label1, F1)]
                    b2_name, basis2 = hf_bases[(label2, F2)]
                    Fs1, mFs1 = basis1
                    Fs2, mFs2 = basis2

                    d_q = np.zeros((3, len(Fs1), len(Fs2)))
                    I = self.I
                    for index_1 in range(len(Fs1)):
                        for index_2 in range(len(Fs2)):
                            f1_val, f2_val, mf1_val, mf2_val = Fs1[index_1], Fs2[index_2], mFs1[
                                index_1], mFs2[index_2]
                            for q_index, q in enumerate((-1., 0., 1.)):
                                if mf2_val == mf1_val - q:
                                    d_q[q_index, index_1, index_2] = _d_q_matrix_element(J1, f1_val,
                                                                                         mf1_val,
                                                                                         J2, f2_val,
                                                                                         mf2_val,
                                                                                         q, I)
                    d_q *= np.sqrt(J2 * 2 + 1)
                    # TODO: for extremely small transition gammas, figure out if rescaling Gamma' = Gamma/k,
                    #  d_q' = d_q * sqrt(k), s' = k*s (for laser) works in handling the 'infinite s' issue
                    ham.add_d_q_block(b1_name, b2_name, d_q,
                                      k=transition_energy / ref_gamma,
                                      gamma=transition_gamma / ref_gamma)
        # endregion
        return ham

    def _lasers(self) -> dict[str, pylcp.laserBeams]:
        lasers = {}
        laser_lists = {}
        ref_gamma, ref_energy = self._principal_gamma_and_energy()
        for fine_transition_laser_group in self.lasers.values():
            for freq_group in fine_transition_laser_group.freq_groups.values():
                freq = freq_group.freq
                for hf_transition in freq_group.enabled_transitions:
                    hf_key1, hf_key2 = hf_transition
                    sat_intensity = self._saturation_intensity(hf_transition)
                    delta = (freq - np.abs(self.hf_energy(hf_key2) - self.hf_energy(hf_key1)))
                    if hf_transition not in laser_lists:
                        laser_lists[hf_transition] = []
                    laser_list = laser_lists[hf_transition]
                    for laser_data in freq_group.lasers:
                        laser_list.append(infinitePlaneWaveBeam(laser_data.kvec * freq / ref_energy,
                                                                laser_data.pol,
                                                                laser_data.intensity / sat_intensity,
                                                                delta / ref_gamma))
        for hf_transition in laser_lists:
            lasers[str(hf_transition)] = pylcp.laserBeams(laser_lists[hf_transition])
        return lasers

    def _principal_gamma_and_energy(self):
        """
        :return: the gamma and energy of the transition with the highest gamma
        """
        reference_gamma = 0
        reference_energy = None
        for label_pair in self.transitions:
            transition_gamma = self.transitions[label_pair].gamma
            if transition_gamma > reference_gamma:
                reference_gamma = transition_gamma
                reference_energy = (self.fine_states[label_pair[1]].energy -
                                    self.fine_states[label_pair[0]].energy)
        return reference_gamma, reference_energy

    def _saturation_intensity(self, hf_transition: HFTransitionKey):
        fine_transition = hf_transition.to_fine_transition()
        energy = np.abs(self.fine_states[fine_transition.lower_label].energy -
                        self.fine_states[fine_transition.upper_label].energy)  # eV
        gamma = self.transitions[fine_transition].gamma  # Hz
        return (2 * np.pi ** 2 * h * energy ** 3 * gamma) / (3 * c ** 2)
    # endregion
