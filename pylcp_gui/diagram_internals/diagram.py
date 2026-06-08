from PySide6.QtWidgets import QGraphicsScene, QGraphicsProxyWidget, QGraphicsItem

from pylcp_gui import config
from pylcp_gui.diagram_internals.manifold import Manifold, GraphicsDragFilter
import numpy as np

from pylcp_gui.diagram_internals.manifold_proxy import ManifoldProxy
from pylcp_gui.diagram_internals.transition import Transition
from pylcp_gui.util import addDebugFilter


class Diagram(QGraphicsScene):
    def __init__(self, /):
        super().__init__()
        self.manifolds:dict[str,Manifold] = {}  # dict str->Manifold
        self.transitions:dict[frozenset[str],Transition] = {}
        self.selected_manifold = None


    def add_manifold_from_values(self, label:str, detuning:float,F:int):
        pos = self.sceneRect().center()
        manifold = Manifold(label, detuning, F)
        # TODO: handling for pre-existing labels?
        proxy = ManifoldProxy(manifold)
        proxy.setPos(pos.x(), pos.y())
        self.addItem(proxy)
        manifold.installEventFilter(GraphicsDragFilter(proxy, proxy))
        self.manifolds[label] = manifold
        self.rearrange()
        return manifold

    def add_transition_from_values(self, d_q, manifold1: Manifold, manifold2: Manifold):
        transition = Transition(manifold1,
                                manifold2, d_q)
        self.transitions[frozenset(transition.labels())] = transition
        self.addItem(transition)
        return transition

    def rearrange(self):
        # TODO: can we rely on there being an absolute ground state with 0 detuning?
        self.setSceneRect(self.itemsBoundingRect())
        return
        manifolds = np.asarray(list(self.manifolds.values()))
        energies = np.asarray([manifold_proxy.widget().energy for manifold_proxy in manifolds])
        sort = np.argsort(energies)
        manifolds = manifolds[sort]  # sorted in ascending energy order
        y = 0
        manifold: QGraphicsProxyWidget
        for manifold in manifolds:
            manifold.setY(y)
            y += config.manifold_spacing
