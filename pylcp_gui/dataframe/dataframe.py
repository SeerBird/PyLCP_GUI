from __future__ import annotations

import logging
import pickle
import time
from enum import Enum
from os import PathLike
from typing import overload, Callable, TypeVar

import numpy as np
import pylcp
from pylcp import infinitePlaneWaveBeam, atom as Pylcp_atom, magField
from pylcp.atom import state as Pylcp_state
from pylcp.hamiltonians import wig3j, wig6j
from scipy.constants import c, h, elementary_charge

from pylcp_gui.util import sort_float_then_string, HyperfineKey, Vector3D, MagneticFieldObject, \
    HFTransitionKey, FineTransitionKey

logger: logging.Logger = logging.getLogger(__name__)


def _d_q_matrix_element(J, F, m_F, Jp, Fp, m_Fp, q, I):
    return (-1) ** (F - m_F + J + I + Fp + 1) * np.sqrt((2 * F + 1) * (2 * Fp + 1)) * \
        wig3j(F, 1, Fp, -m_F, q, m_Fp) * wig6j(J, F, I, Fp, Jp, 1)


def mu_q_coupled(basis, gJ, gI, J, I):
    Fs, mFs = basis
    n = len(Fs)
    mu_q = np.zeros((3, n, n))
    count = 0
    for ii, q in enumerate(range(-1, 2)):
        for index_1 in range(n):
            for index_2 in range(n):
                count += 1
                F1, F2, mF1, mF2 = Fs[index_1], Fs[index_2], mFs[index_1], mFs[index_2]
                if mF1 == mF2 + q:
                    mu_q[ii, index_1, index_2] -= (gJ * (-1) ** np.abs(F1 - mF1)
                                                   * wig3j(F1, 1, F2, -mF1, q, mF2)
                                                   * np.sqrt((2 * F2 + 1) * (2 * F1 + 1))
                                                   * (-1) ** (J + I + F2 + 1)
                                                   * wig6j(J, F2, I, F1, J, 1)
                                                   * np.sqrt(J * (J + 1) * (2 * J + 1)))

                    mu_q[ii, index_1, index_2] += (gI * (-1) ** np.abs(F1 - mF1)
                                                   * wig3j(F1, 1, F2, -mF1, q, mF2)
                                                   * np.sqrt((2 * F2 + 1) * (2 * F1 + 1))
                                                   * (-1) ** (J + I + F2 + 1)
                                                   * wig6j(I, F2, J, F1, I, 1)
                                                   * np.sqrt(I * (I + 1) * (2 * I + 1)))
    return mu_q


def hyperfine_correction(J, I, F, hf_coefs):
    """F can be a single number or an ndarray"""
    K = F * (F + 1) - I * (I + 1) - J * (J + 1)
    Ahf, Bhf, Chf = hf_coefs
    energy = Ahf * K / 2
    if Bhf != 0:
        energy += Bhf * (1.5 * K * (K + 1) - 2 * I * (I + 1) * J * (J + 1)) / (
                4 * I * (2 * I - 1) * J * (2 * J - 1))
    if Chf != 0:
        energy += Chf * (5 * K ** 2 * (K / 4 + 1)
                         + K * (I * (I + 1) + J * (J + 1) + 3 - 3 * I * (
                        I + 1) * J * (
                                        J + 1))
                         - 5 * I * (I + 1) * J * (J + 1)) / (
                          I * (I - 1) * (2 * I - 1) * J * (J - 1) * (2 * J - 1))
    return energy


def get_state_basis(state, Fs_sorted):
    mFs = []
    Fs = []
    for F in Fs_sorted:
        mFs += state.substates[F]
        Fs += [F] * len(state.substates[F])
    return Fs, mFs


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


class LaserData:
    def __init__(self, freq, kvec, pol, intensity):
        self.freq: float = freq  # Hz
        self.kvec: np.ndarray = kvec  # unit vector
        self.pol: np.ndarray = pol  # stored in polar
        self.intensity: float = intensity  # TODO: add units: SI or unitless

    def __str__(self):
        return (f"kvec = ({self.kvec[0]},{self.kvec[1]},{self.kvec[2]}), " +
                f"pol = ({self.pol[0]},{self.pol[1]},{self.pol[2]})" +
                f"intensity = {self.intensity}")


LaserDataStructure = dict[tuple[str, str], list[LaserData]]


class StateData:
    def __init__(self, label: str, energy: float, I: float, J: float,
                 hf_coefs: tuple[float, float, float],
                 gJ: float):
        self.label = label
        self.energy = energy  # Hz
        self.hf_coefs = hf_coefs  # Hz
        self.J = J
        self.gJ = gJ  #
        self.substates: dict[
            float, list[float]] = {}  # list of lists of mF values for each possible F
        # each mF list is sorted in increasing mF order
        Fs = np.arange(np.abs(J - I), J + I + 1, 1)
        for F in Fs:
            self.substates[F] = list(np.arange(-F, F + 1, 1.))


class TransitionData:
    def __init__(self, gamma):
        self.gamma = gamma  # Hz


class LaserFreqGroup:
    def __init__(self, freq: float):
        self.freq = freq
        self.lasers: list[LaserData] = []  # all the lasers have the same frequency
        self.enabled_transitions: list[HFTransitionKey] = []

    def add_laser(self, laser: LaserData):
        self.lasers.append(laser)


class LaserDisplayData:
    def __init__(self, freq: float, keys: HFTransitionKey, orientation: bool):
        self.freq: float = freq
        self.keys: HFTransitionKey = keys
        self.upwards: bool = orientation


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
        self.lasers: dict[float, LaserFreqGroup] = {}
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
            return  # This shouldn't happen, ever, but it's fine if it does
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
            frame.add_fine_state(StateData(labels[i],
                                           state.energy * 1e2 * c,
                                           frame.I,
                                           state.J,
                                           (state.Ahfs, state.Bhfs, state.Chfs),
                                           state.gJ))
        # endregion
        # region add all transitions
        for i in range(1, len(states)):
            state: Pylcp_state = states[i]
            excited_state = frame.fine_states[labels[i]]
            frame.add_transition(labels[0], labels[i], TransitionData(state.gammaHz))
        # endregion
        return frame

    def set_magnetic_field(self, magnetic_field: MagneticFieldObject):
        self.magnetic_field = magnetic_field

    def add_fine_state(self, fine_state: StateData):
        self.fine_states[fine_state.label] = fine_state
        return fine_state

    def add_transition(self, label1, label2, transition_data: TransitionData):
        self.transitions[FineTransitionKey(label1, label2)] = transition_data

    def add_laser(self, label1, label2, F1, F2, delta, kvec, pol, intensity):
        """
        :param label1: lower state label
        :param label2: upper state label
        :param F1:
        :param F2:
        :param delta: in (global) gamma units, relative to the F1-F2 transition
        :param kvec: unit vector in spherical coords
        :param pol:
        :param intensity: normalized to the saturation intensity
        :return:
        """

        key1, key2 = HyperfineKey(label1, F1), HyperfineKey(label2, F2)
        transition_key = HFTransitionKey(key1, key2)
        transition_energy = self.hf_energy(key2) - self.hf_energy(key1)
        freq = transition_energy + delta * self._principal_gamma_and_energy()[0]
        if freq not in self.lasers:
            self.lasers[freq] = LaserFreqGroup(freq)
        self.lasers[freq].add_laser(LaserData(freq, kvec, pol, intensity
                                              * self._saturation_intensity(transition_key)))

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
        freqs = list(self.lasers.keys())
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
        logger.debug("Started dataframe hamiltonian packing")
        t0 = time.perf_counter()
        ham = pylcp.hamiltonian()
        ref_gamma: float = self._principal_gamma_and_energy()[0]
        # rest frame electronic energies
        labels = np.asarray(list(self.states.keys()))
        energies = np.asarray([self.states[label].energy for label in labels])
        sort = sort_float_then_string(energies, labels)
        labels = labels[sort]  # in the order the blocks should be added
        state_bases = {}
        for state_label in labels:
            fine_state: StateData = self.states[state_label]
            Fs = np.asarray(list(fine_state.substates.keys()))
            # sort the Fs by energy
            hyperfine_energies = hyperfine_correction(fine_state.J, self.I, Fs,
                                                      fine_state.hf_coefs)
            sort = np.argsort(hyperfine_energies)
            Fs = Fs[sort]
            basis = get_state_basis(fine_state, Fs)
            state_bases[state_label] = basis
            # region H_0
            hyperfine_energies = hyperfine_energies[sort]
            diagonal = []
            for i in range(len(Fs)):
                diagonal += [hyperfine_energies[i]] * len(fine_state.substates[Fs[i]])
            ham.add_H_0_block(state_label, np.diag(diagonal) / ref_gamma)
            # endregion
            # region mu_q
            mu_q = mu_q_coupled(basis, fine_state.gJ, self.gI, fine_state.J, self.I)
            ham.add_mu_q_block(state_label, mu_q)
            # endregion
        # region d_q
        for traverse_label_pair in self.transitions.keys():
            label1, label2 = traverse_label_pair
            state_1 = self.fine_states[label1]
            state_2 = self.fine_states[label2]
            J1, J2 = state_1.J, state_2.J
            transition_energy = np.abs(state_1.energy - state_2.energy)
            transition_gamma = self.transitions[traverse_label_pair].gamma
            Fs1, mFs1 = state_bases[label1]
            Fs2, mFs2 = state_bases[label2]
            # TODO: consider vectorizing if vectorizable wig3j, wig6j exist
            d_q = np.zeros((3, len(Fs1), len(Fs2)))
            I = self.I
            for index_1 in range(len(Fs1)):
                for index_2 in range(len(Fs2)):
                    F1, F2, mF1, mF2 = Fs1[index_1], Fs2[index_2], mFs1[index_1], mFs2[index_2]
                    for q_index, q in enumerate((-1., 0., 1.)):
                        if mF2 == mF1 - q:
                            d_q[q_index, index_1, index_2] = _d_q_matrix_element(J1, F1, mF1,
                                                                                 J2, F2, mF2,
                                                                                 q, I)
            d_q *= np.sqrt(J2 * 2 + 1)
            # TODO: for extremely small transition gammas, figure out if rescaling Gamma' = Gamma/k,
            #  d_q' = d_q * sqrt(k), s' = k*s (for laser) works in handling the 'infinite s' issue
            ham.add_d_q_block(label1, label2, d_q,
                              k=transition_energy / ref_gamma,
                              gamma=transition_gamma / ref_gamma)
        # endregion
        return ham

    def _lasers(self):
        lasers = {}
        ref_gamma, ref_energy = self._principal_gamma_and_energy()
        for label_pair in self.lasers:
            laser_list = []
            state1, state2 = self.fine_states[label_pair[0]], self.fine_states[label_pair[1]]
            sat_intensity = self._saturation_intensity(label_pair)
            for laser_data in self.lasers[label_pair]:
                freq = laser_data.freq
                delta = (freq - np.abs(state1.energy - state2.energy))
                laser_list.append(infinitePlaneWaveBeam(laser_data.kvec * freq / ref_energy,
                                                        laser_data.pol,
                                                        laser_data.intensity / sat_intensity,
                                                        delta / ref_gamma))
            label1, label2 = label_pair
            lasers[f"{label1}->{label2}"] = pylcp.laserBeams(laser_list)
        return lasers

    def _principal_gamma_and_energy(self):
        reference_gamma = 0
        reference_energy = None
        for label_pair in self.lasers:
            # take the gamma of the rest frame upper Manifold
            transition_gamma = self.transitions[label_pair].gamma
            if transition_gamma > reference_gamma:
                reference_gamma = transition_gamma
                reference_energy = (self.fine_states[label_pair[1]].energy -
                                    self.fine_states[label_pair[0]].energy)
        return reference_gamma, reference_energy

    def _saturation_intensity(self, transition_label_pair):
        energy = np.abs(self.fine_states[transition_label_pair[0]].energy -
                        self.fine_states[transition_label_pair[1]].energy)  # eV
        gamma = self.transitions[transition_label_pair].gamma  # Hz
        freq = energy * elementary_charge / h
        return (2 * np.pi ** 2 * h * freq ** 3 * gamma) / (3 * c ** 2)
    # endregion
