from __future__ import annotations

import pickle
from os import PathLike

import numpy as np
import pylcp
from pylcp.hamiltonians import wig3j

from pylcp_gui import util


class ManifoldData:
    def __init__(self, label, energy, F, mFs):
        self.label = label # TODO: excise this label, I think
        self.energy = energy
        self.F = F
        self.mFs:np.ndarray = mFs


class TransitionData:
    def __init__(self, gamma):
        self.gamma = gamma


class LaserData:
    def __init__(self, freq, kvec, pol, intensity):
        self.freq = freq
        self.kvec = kvec
        self.pol = pol
        self.intensity = intensity


class DataFrame:
    def __init__(self):
        self.manifolds: dict[str, ManifoldData] = {}
        # keys are label tuples in increasing energy order
        self.transitions: dict[tuple[str, str], TransitionData] = {}
        self.lasers: dict[tuple[str, str], LaserData]

    @staticmethod
    def load_from_file(path: PathLike | str):
        with open(path, 'rb') as f:
            return pickle.load(f)

    def save(self, path: PathLike | str):
        with open(path, 'wb') as f:
            pickle.dump(self, f)

    def hamiltonian(self):
        ham = pylcp.hamiltonian()
        labels = np.asarray(list(self.manifolds.keys()))
        energies = [manifold.energy for manifold in self.manifolds.values()]
        labels = labels[util.sort_float_then_string(energies, labels)]  # sorted
        for label in labels:
            manifold = self.manifolds[label]
            n = len(manifold.mFs)
            ham.add_H_0_block(label, np.zeros((n, n)) + np.eye(n, n) * manifold.energy)
        for label_pair in self.transitions.keys():
            # TODO: figure out the wig3j stuff together with manifold mFs and everything
            label1, label2 = label_pair
            manifold_1 = self.manifolds[label1]
            manifold_2 = self.manifolds[label2]
            F1 = manifold_1.F
            F2 = manifold_2.F
            mFs1 = manifold_1.mFs
            mFs2 = manifold_2.mFs
            n1 = len(mFs1)
            n2 = len(mFs2)
            d_q = np.zeros((3, n1,n2))
            for i_comp, q in enumerate(np.arange(-1, 2, 1)):
                for i2 in range(n2):
                    m_F2 = mFs2[i2]
                    m_F1 = m_F2 + q
                    if m_F1 in mFs1:
                        i1 = np.where(mFs1==m_F1)[0]
                        d_q[i_comp, i1, i2] = \
                            (-1) ** (F1 - m_F1) * wig3j(F1, 1, F2, -m_F1, q, m_F2)
            ham.add_d_q_block(label1, label2, d_q)
            # TODO: find how each block is scaled
        return ham
