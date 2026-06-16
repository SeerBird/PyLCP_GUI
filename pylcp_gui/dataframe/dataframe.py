from __future__ import annotations

import logging
import pickle
from os import PathLike

import numpy as np
import pylcp
from numpy.ma.core import less_equal
from pylcp import infinitePlaneWaveBeam
from pylcp.common import cart2spherical, spherical2cart
from pylcp.hamiltonians import wig3j, wig6j
import scipy.constants as constants
from scipy.constants import c, h, elementary_charge

from pylcp_gui import util
from pylcp_gui.util import sort_float_then_string

logger: logging.Logger = logging.getLogger(__name__)


class ManifoldData:
    def __init__(self, label, energy, F, J):
        self.label = label  # TODO: excise this label, I think
        self.energy = energy
        self.F = F
        self.J = J


class TransitionData:
    def __init__(self, gamma):
        self.gamma = gamma


class LaserData:
    def __init__(self, freq, kvec, pol, intensity):
        self.freq: float = freq
        self.kvec: np.ndarray = kvec
        self.pol: np.ndarray = pol
        self.intensity: float = intensity


class DataFrame:
    def __init__(self):
        self.I = None
        self.manifolds: dict[str, ManifoldData] = {}
        # keys are label tuples in increasing energy order
        self.transitions: dict[tuple[str, str], TransitionData] = {}
        self.lasers: dict[tuple[str, str], list[LaserData]] = {}

    def _change_values_for_debug(self):
        # region ensure kvec and pol orthogonality
        for laser_set in self.lasers.values():
            for laser in laser_set:
                theta = float(laser.kvec[0])
                laser.kvec = np.asarray([np.cos(theta), np.sin(theta), 0]) / 1e8
                laser.pol = cart2spherical(np.asarray([np.sin(theta), -np.cos(theta), 0]))
        # endregion

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
        result = pylcp.obe(lasers, np.zeros(3), ham)
        return result

    def _hamiltonian(self):
        ham = pylcp.hamiltonian()
        ref_gamma = self._reference_gamma()
        k_vec_unit = self._k_vec_unit()
        energy_unit = self._energy_unit()
        I = self.I
        # region H_0
        labels = np.asarray(list(self.manifolds.keys()))
        # region get H_0_values
        # region get manifold_transition_map
        manifold_laser_map = {}
        for manifold in self.manifolds.values():
            label = manifold.label
            manifold_laser_map[manifold] = []
            for traverse_label_pair in self.lasers:
                # if there is a non-empty laser set connecting this manifold to another, append
                # the label pair
                if label in traverse_label_pair and len(self.lasers[traverse_label_pair]) != 0:
                    manifold_laser_map[manifold].append(traverse_label_pair)
        # endregion
        H_0_values = {}
        transitions_traversed = []
        visited = []
        # loop through the manifolds to detect disjoint laser transition graphs
        for root in self.manifolds.values():
            if root in visited:
                continue
            H_0_values[root.label] = root.energy
            # region traverse all manifolds connected to this root via lasers
            path = [root]
            visited.append(root)
            laser_path = []
            # depth-first traversal, terminates when we backtrack on the root node
            while len(path) != 0:
                current = path[-1]
                traversed_new_manifold = False
                for traverse_label_pair in manifold_laser_map[current]:
                    # TODO: sort lasers by some sort of priority?
                    if traverse_label_pair in transitions_traversed:
                        continue
                    transitions_traversed.append(traverse_label_pair)
                    next_manifold = self.manifolds[
                        traverse_label_pair[0] if traverse_label_pair[1] == current.label else
                        traverse_label_pair[1]]
                    if next_manifold in visited:
                        raise RuntimeError(
                            "Loop in laser transition graph - time-independent Hamiltonian"
                            "unachievable")
                    traversed_new_manifold = True
                    visited.append(next_manifold)
                    path.append(next_manifold)
                    laser_path.append(traverse_label_pair)
                    H_0_value = next_manifold.energy  # eV?
                    for laser_label_pair in laser_path:
                        # TODO: relying on all the lasers coupling to a transition
                        #  having the same frequency for now. iffy [0], fine for now
                        H_0_value -= (self.lasers[laser_label_pair][0].freq
                                      * constants.h / constants.elementary_charge)
                    H_0_values[next_manifold.label] = H_0_value
                    # TODO: divide by Gamma
                    break
                if not traversed_new_manifold:  # backtrack
                    path.pop(-1)
                    if len(laser_path) > 0:
                        laser_path.pop(-1)

            # endregion
        # endregion
        energies = np.asarray([H_0_values[label] for label in labels])  # rotating frame energies
        sort = sort_float_then_string(energies, labels)
        labels = labels[sort]
        energies = energies[sort]
        energies -= energies[0]  # choose the gauge such that the lowest energy state is ground
        energies = energies / energy_unit
        for i in range(len(labels)):
            H_0_values[labels[i]] = energies[i]  # update H_0_values for later use
            label = labels[i]
            manifold = self.manifolds[label]
            n = 2 * manifold.F + 1
            ham.add_H_0_block(label, np.zeros((n, n)) + np.eye(n, n) * energies[i])
        # endregion
        # region d_q
        for traverse_label_pair in self.transitions.keys():
            energy_pair = [H_0_values[label] for label in traverse_label_pair]
            label1, label2 = np.asarray(traverse_label_pair)[
                sort_float_then_string(energy_pair, traverse_label_pair)]
            manifold_1 = self.manifolds[label1]
            manifold_2 = self.manifolds[label2]
            F1, F2, J1, J2 = manifold_1.F, manifold_2.F, manifold_1.J, manifold_2.J
            transition_energy = np.abs(manifold_1.energy - manifold_2.energy)
            transition_gamma = self.transitions[traverse_label_pair].gamma
            # TODO: vectorize this if easy
            d_q = (pylcp.hamiltonians.dqij_two_bare_hyperfine(F1, F2, normalize=False) # wig3j
                   * (-1) ** (J1 + I + F1 + 1) * np.sqrt((2 * F1 + 1) * (2 * F2 + 1))
                   * wig6j(J1, F1, I, F2, J2, 1))  # TODO: check all this again. obv.
            ham.add_d_q_block(label1, label2, d_q,
                              k=transition_energy / energy_unit,
                              gamma=transition_gamma / ref_gamma)
        # endregion
        return ham

    def _lasers(self):
        lasers = {}
        k_vec_unit = self._k_vec_unit()
        energy_unit = self._energy_unit()
        for label_pair in self.lasers:
            laser_list = []
            manifold1, manifold2 = self.manifolds[label_pair[0]], self.manifolds[label_pair[1]]
            # TODO: either handle different frequencies or add validation that all lasers are
            #  single-frequency
            sat_intensity = self._saturation_intensity(label_pair)
            for laser_data in self.lasers[label_pair]:
                delta = (np.abs(manifold1.energy - manifold2.energy)
                         - laser_data.freq * h / elementary_charge)
                # TODO: figure out how we're storing kvec - unit vector? angles?
                laser_list.append(infinitePlaneWaveBeam(laser_data.kvec / k_vec_unit,
                                                        laser_data.pol,
                                                        laser_data.intensity / sat_intensity,
                                                        delta / energy_unit))
            label1, label2 = label_pair if manifold1.energy < manifold2.energy \
                else np.asarray(label_pair)[:-1]
            lasers[f"{label1}->{label2}"] = pylcp.laserBeams(laser_list)
        return lasers

    def _reference_gamma(self):
        reference_gamma = 0
        for label_pair in self.lasers:
            if len(self.lasers[label_pair]) > 0:
                transition_gamma = self.transitions[label_pair].gamma
                if transition_gamma > reference_gamma:
                    reference_gamma = transition_gamma
        return reference_gamma

    def _energy_unit(self):
        return (constants.h * self._reference_gamma()) / constants.elementary_charge

    def _k_vec_unit(self):
        return self._reference_gamma() / c

    def _saturation_intensity(self, transition_label_pair):
        energy = np.abs(self.manifolds[transition_label_pair[0]].energy -
                        self.manifolds[transition_label_pair[1]].energy)  # eV
        gamma = self.transitions[transition_label_pair].gamma  # Hz
        freq = energy * elementary_charge / h
        return (2 * np.pi ** 2 * h * freq ** 3 * gamma) / (3 * c ** 2)
