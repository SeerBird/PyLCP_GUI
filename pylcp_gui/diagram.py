from PySide6.QtWidgets import QGraphicsScene, QGraphicsProxyWidget

from pylcp_gui import config
from pylcp_gui.manifold import Manifold
import numpy as np


class Diagram(QGraphicsScene):
    def __init__(self, /):
        super().__init__()
        self.manifold_proxys = {}

    def add_manifold_from_values(self, values):
        label, detuning = values
        manifold = Manifold(label,float(detuning))
        # TODO: handling for pre-existing labels?
        self.manifold_proxys[label] = self.addWidget(manifold)
        self.rearrange()

    def rearrange(self):
        # TODO: can we rely on there being an absolute ground state with 0 detuning?
        manifolds = np.asarray(list(self.manifold_proxys.values()))
        energies = np.asarray([manifold_proxy.widget().energy for manifold_proxy in manifolds])
        sort = np.argsort(energies)
        manifolds = manifolds[sort] # sorted in ascending energy order
        y = 0
        manifold:QGraphicsProxyWidget
        for manifold in manifolds:
            manifold.setY(y)
            y+=config.manifold_spacing

    def rearrange_transitions(self, labels):
        pass

