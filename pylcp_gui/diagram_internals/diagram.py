from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QGraphicsScene, QGraphicsProxyWidget, QGraphicsItem

from pylcp_gui import config
from pylcp_gui.dataframe.dataframe import ManifoldData, TransitionData
from pylcp_gui.diagram_internals.manifold import Manifold, GraphicsDragFilter
import numpy as np

from pylcp_gui.diagram_internals.manifold_proxy import ManifoldProxy
from pylcp_gui.diagram_internals.transition import Transition
from pylcp_gui.util import addDebugFilter, sort_float_then_string, sort_manifolds


class Diagram(QGraphicsScene):

    def __init__(self, /):
        super().__init__()
        self.manifolds: dict[str, Manifold] = {}  # dict str->Manifold
        self.transitions: dict[frozenset[str], Transition] = {}
        self.manifold_transition_map:dict[str,list[Transition]] = {}
        self.selected_manifold = None

    def add_manifold_from_values(self, manifold_data: ManifoldData):
        pos = self.sceneRect().center()
        manifold = Manifold(manifold_data)
        # TODO: handling for pre-existing labels?
        proxy = ManifoldProxy(manifold)
        proxy.setPos(pos.x(), pos.y())
        self.addItem(proxy)
        manifold.installEventFilter(GraphicsDragFilter(proxy, proxy))
        self.manifolds[manifold.label] = manifold
        self.manifold_transition_map[manifold.label] = []
        self.rearrange()
        manifold.positionChanged.connect(self.manifoldMoved)
        return manifold

    def add_transition_from_values(self, transition_data: TransitionData,
                                   manifold1: Manifold, manifold2: Manifold):
        transition = Transition(manifold1,
                                manifold2, transition_data)
        self.transitions[frozenset(transition.labels)] = transition
        self.manifold_transition_map[manifold1.label].append(transition)
        self.manifold_transition_map[manifold2.label].append(transition)
        self.addItem(transition)
        return transition

    def delete_transition(self, transition: Transition):
        self.manifold_transition_map[transition.labels[0]].remove(transition)
        self.manifold_transition_map[transition.labels[1]].remove(transition)
        self.transitions.pop(frozenset(transition.labels))
        self.removeItem(transition)
        transition.deleteLater()


    def rearrange(self):
        self.setSceneRect(self.views()[0].rect())  # TODO: this is iffy
        manifolds = np.asarray(list(self.manifolds.values()))
        if manifolds.size == 0:
            return
        sort = sort_manifolds(manifolds)
        manifolds = manifolds[sort]  # sorted in ascending energy order
        # TODO: manifolds[0] is iffy
        y = np.linspace(0, self.sceneRect().height() - manifolds[0].height(),
                        manifolds.size)
        manifold: Manifold
        for i in range(manifolds.size):
            manifold = manifolds[i]
            proxy = manifold.graphicsProxyWidget()
            assert proxy is not None
            proxy.setY(y[i])

    def manifoldMoved(self,label:str):
        for transition in self.manifold_transition_map[label]:
            p1 = self.manifolds[transition.labels[0]].geometry().center()
            p2 = self.manifolds[transition.labels[1]].geometry().center()
            transition.trackNodes(p1,p2)
