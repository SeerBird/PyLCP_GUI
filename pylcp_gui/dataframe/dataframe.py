from __future__ import annotations

import pickle
from os import PathLike

import numpy as np
import pylcp

from pylcp_gui import util


class DataFrame:
    def __init__(self):
        self.H_0 = {}
        self.d_q: dict[tuple[str,str], float] = {}  # keys are
        # label tuple in increasing energy order

    @staticmethod
    def load_from_file(path: PathLike|str):
        with open(path, 'rb') as f:
            return pickle.load(f)

    def save(self, path: PathLike|str):
        with open(path, 'wb') as f:
            pickle.dump(self, f)

    def hamiltonian(self):
        ham = pylcp.hamiltonian()
        labels = np.asarray(list(self.H_0.keys()))
        energies = list(self.H_0.values())
        labels = labels[util.sort_float_then_string(energies,labels)]
        for label in labels:
            ham.add_H_0_block(label, np.asarray([[self.H_0[label]]]))
        for label_pair in self.d_q.keys():
            label1, label2 = label_pair
            d_q = np.zeros((3,1,1))
            d_q[1] = self.d_q[label_pair]
            ham.add_d_q_block(label1, label2, d_q)
        return ham
