from __future__ import annotations

import logging
import pickle
from os import PathLike

import numpy as np
import pylcp
from pylcp import infinitePlaneWaveBeam
from pylcp.hamiltonians import wig3j, wig6j
from scipy.constants import c, h, elementary_charge

from pylcp_gui.util import sort_float_then_string

logger: logging.Logger = logging.getLogger(__name__)


def _d_q_matrix_element(J, F, m_F, Jp, Fp, m_Fp, q, I):
    return (-1) ** (F - m_F + J + I + Fp + 1) * np.sqrt((2 * F + 1) * (2 * Fp + 1)) * \
        wig3j(F, 1, Fp, -m_F, q, m_Fp) * wig6j(J, F, I, Fp, Jp, 1)


def mu_q_coupled(basis, gJ, gI, J, I):
    Fs, mFs = basis
    n = len(Fs)
    mu_q = np.zeros((3, n, n))
    for ii, q in enumerate(range(-1, 2)):
        for index_1 in range(n):
            for index_2 in range(n):
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


class StateData:
    def __init__(self, label, energy, J, hf_coefs, gJ):
        self.label = label
        self.energy = energy  # Hz
        self.hf_coefs = hf_coefs
        self.J = J
        self.gJ = gJ
        self.substates: dict[
            float, list[float]] = {}  # list of lists of mF values for each possible F
        # each mF list is assumed to be sorted in increasing mF order


class TransitionData:
    def __init__(self, gamma):
        self.gamma = gamma


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


class LaserDisplayData:
    def __init__(self, freq, keys, orientation):
        self.freq, self.keys, self.upwards = freq, keys, orientation


class DataFrame:
    def __init__(self):
        self.I: float = 0
        self.gI = None
        self.states: dict[str, StateData] = {}
        # keys are label tuples in increasing energy order
        # rn this can actually be set to boolean
        self.transitions: dict[tuple[str, str], TransitionData] = {}
        self.lasers: dict[tuple[str, str], list[LaserData]] = {}

    @staticmethod
    def load_from_file(path: PathLike | str) -> DataFrame:
        with open(path, 'rb') as f:
            return pickle.load(f)

    def save(self, path: PathLike | str):
        with open(path, 'wb') as f:
            pickle.dump(self, f)

    def obe(self):
        ham = self._hamiltonian()
        lasers = self._lasers()
        return pylcp.obe(lasers, np.zeros(3), ham)

    def rateeq(self, magField):
        return pylcp.rateeq(self._lasers(), magField, self._hamiltonian(), include_mag_forces=False)

    def add_state(self, state: StateData):
        self.states[state.label] = state

    def add_transition(self, label1, label2, transition_data):
        self.transitions[(label1, label2)] = transition_data
        self.lasers[(label1, label2)] = []

    def add_laser(self, label1, label2, F1, F2, delta, kvec, pol, intensity):
        """
        :param label1: lower state label
        :param label2: upper state label
        :param F1:
        :param F2:
        :param delta: in gamma units, relative to the F1-F2 transition
        :param kvec: unit vector in spherical coords
        :param pol:
        :param intensity: normalized to the saturation intensity
        :return:
        """
        label_pair = (label1, label2)
        if not label_pair in self.transitions.keys():
            raise ValueError("Laser key does not have a corresponding transition defined")
        state1, state2 = self.states[label1], self.states[label2]
        transition_energy = (state2.energy + hyperfine_correction(state2.J, self.I, F2,
                                                                  state2.hf_coefs)
                             - (state1.energy + hyperfine_correction(state1.J, self.I, F1,
                                                                     state1.hf_coefs)))
        laser_energy = transition_energy + delta * self._principal_gamma_and_energy()[0]
        self.lasers[label_pair].append(
            LaserData(laser_energy, kvec, pol, intensity * self._saturation_intensity(label_pair)))

    def _hamiltonian(self):
        ham = pylcp.hamiltonian()
        ref_gamma: float = self._principal_gamma_and_energy()[0]
        # rest frame electronic energies
        labels = np.asarray(list(self.states.keys()))
        energies = np.asarray([self.states[label].energy for label in labels])
        sort = sort_float_then_string(energies, labels)
        labels = labels[sort]  # in the order the blocks should be added
        state_bases = {}
        for state_label in labels:
            state = self.states[state_label]
            Fs = np.asarray(list(state.substates.keys()))
            hyperfine_energies = hyperfine_correction(state.J, self.I, Fs,
                                                      state.hf_coefs)
            sort = np.argsort(hyperfine_energies)
            Fs = Fs[sort]
            basis = get_state_basis(state, Fs)
            state_bases[state_label] = basis
            # region H_0
            hyperfine_energies = hyperfine_energies[sort]
            diagonal = []
            for i in range(len(Fs)):
                diagonal += [hyperfine_energies[i]] * len(state.substates[Fs[i]])
            ham.add_H_0_block(state_label, np.diag(diagonal) / ref_gamma)
            # endregion
            # region mu_q
            mu_q = mu_q_coupled(basis, state.gJ, self.gI, state.J, self.I)
            ham.add_mu_q_block(state_label, mu_q)
            # endregion
        # region d_q
        for traverse_label_pair in self.transitions.keys():
            label1, label2 = traverse_label_pair
            state_1 = self.states[label1]
            state_2 = self.states[label2]
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
            state1, state2 = self.states[label_pair[0]], self.states[label_pair[1]]
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
                reference_energy = (self.states[label_pair[1]].energy -
                                    self.states[label_pair[0]].energy)
        return reference_gamma, reference_energy

    def _saturation_intensity(self, transition_label_pair):
        energy = np.abs(self.states[transition_label_pair[0]].energy -
                        self.states[transition_label_pair[1]].energy)  # eV
        gamma = self.transitions[transition_label_pair].gamma  # Hz
        freq = energy * elementary_charge / h
        return (2 * np.pi ** 2 * h * freq ** 3 * gamma) / (3 * c ** 2)
