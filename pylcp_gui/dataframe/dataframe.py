from __future__ import annotations

import logging
import pickle
from os import PathLike

import numpy as np
import pylcp
from pylcp import infinitePlaneWaveBeam
from pylcp.common import cart2spherical
from pylcp.hamiltonians import wig3j
import scipy.constants as constants

from pylcp_gui import util
from pylcp_gui.util import sort_float_then_string

logger: logging.Logger = logging.getLogger(__name__)


class ManifoldData:
    def __init__(self, label, energy, F, mFs):
        self.label = label  # TODO: excise this label, I think
        self.energy = energy
        self.F = F
        self.mFs: np.ndarray = mFs


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
        self.manifolds: dict[str, ManifoldData] = {}
        # keys are label tuples in increasing energy order
        self.transitions: dict[tuple[str, str], TransitionData] = {}
        self.lasers: dict[tuple[str, str], LaserData] = {}

    def _change_values_for_debug(self):
        for laser in self.lasers.values():
            theta = float(laser.kvec[0])
            laser.kvec = np.asarray([np.cos(theta), np.sin(theta),0])
            laser.pol = cart2spherical(np.asarray([np.sin(theta), -np.cos(theta),0]))

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

    def _hamiltonian(self):
        ham = pylcp.hamiltonian()
        # region H_0
        labels = np.asarray(list(self.manifolds.keys()))
        # region get H_0_values
        # region get manifold_transition_map
        manifold_laser_map = {}
        for manifold in self.manifolds.values():
            label = manifold.label
            manifold_laser_map[manifold] = []
            for traverse_label_pair in self.lasers:
                if label in traverse_label_pair:
                    manifold_laser_map[manifold].append(traverse_label_pair)
        # endregion
        H_0_values = {}
        lasers_traversed = []
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
            while len(
                    path) != 0:  # depth-first traversal, terminates when we backtrack on the root node
                current = path[-1]
                traversed_new_manifold = False
                for traverse_label_pair in manifold_laser_map[current]:
                    # TODO: sort lasers by some sort of priority?
                    if traverse_label_pair in lasers_traversed:
                        continue
                    lasers_traversed.append(traverse_label_pair)
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
                        H_0_value -= (self.lasers[laser_label_pair].freq
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
        energies = np.asarray(
            [H_0_values[label] for label in labels])  # rotating frame energies
        sort = sort_float_then_string(energies, labels)
        labels = labels[sort]
        energies = energies[sort]
        energies -= energies[0]  # choose the gauge such that the lowest energy state is ground
        for i in range(len(labels)):
            H_0_values[labels[i]] = energies[i]  # update H_0_values for later use
            label = labels[i]
            manifold = self.manifolds[label]
            n = len(manifold.mFs)
            ham.add_H_0_block(label, np.zeros((n, n)) + np.eye(n, n) * energies[i])
        # endregion
        # region d_q
        for traverse_label_pair in self.transitions.keys():
            energy_pair = [H_0_values[label] for label in traverse_label_pair]
            label1, label2 = np.asarray(traverse_label_pair)[
                sort_float_then_string(energy_pair, traverse_label_pair)]
            manifold_1 = self.manifolds[label1]
            manifold_2 = self.manifolds[label2]
            F1 = manifold_1.F
            F2 = manifold_2.F
            mFs1 = manifold_1.mFs
            mFs2 = manifold_2.mFs
            n1 = len(mFs1)
            n2 = len(mFs2)
            d_q = np.zeros((3, n1, n2))
            for i_comp, q in enumerate(np.arange(-1, 2, 1)):
                for i2 in range(n2):
                    m_F2 = mFs2[i2]
                    m_F1 = m_F2 + q
                    if m_F1 in mFs1:
                        i1 = np.where(mFs1 == m_F1)[0][0]
                        d_q[i_comp, i1, i2] = \
                            (-1) ** (F1 - m_F1) * wig3j(F1, 1, F2, -m_F1, q, m_F2)
            ham.add_d_q_block(label1, label2, d_q)
            # TODO: find how each block is scaled
        # endregion
        return ham

    def _lasers(self):
        lasers = []
        for label_pair in self.lasers:
            manifold1, manifold2 = self.manifolds[label_pair[0]], self.manifolds[label_pair[1]]
            laser_data = self.lasers[label_pair]
            delta = (np.abs(manifold1.energy - manifold2.energy)
                     - laser_data.freq * constants.h / constants.elementary_charge)
            # TODO: divide by Gamma
            s = laser_data.intensity  # TODO: figure out saturation intensity, which one?
            lasers.append(infinitePlaneWaveBeam(laser_data.kvec, laser_data.pol, s, delta, ))
        return lasers
