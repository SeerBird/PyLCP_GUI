from PySide6.QtWidgets import QGraphicsScene, QGraphicsProxyWidget, QGraphicsItem

from pylcp_gui import config
from pylcp_gui.manifold import Manifold
import numpy as np

from pylcp_gui.transition import Transition


class Diagram(QGraphicsScene):
    def __init__(self, /):
        super().__init__()
        self.manifolds = {}  # dict str->QGraphicsProxy
        self.transitions = {}  # dict frozenset[str]->Transition
        self.selected_manifold = None

    def add_manifold_from_values(self, label, detuning):
        pos = self.sceneRect().center()
        manifold = Manifold(label, float(detuning))
        # TODO: handling for pre-existing labels?
        proxy = self.addWidget(manifold)
        proxy.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        proxy.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        proxy.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        proxy.setPos(pos.x(), pos.y())

        def itemChange(_self, change, value, /):
            if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and _self.scene():
                _self.positionChanged.emit(value)
                # TODO: limit manifold movement here

        proxy.itemChange = itemChange
        self.manifolds[label] = proxy
        self.rearrange()

    def add_transition_from_values(self, d_q, manifold1: Manifold, manifold2: Manifold):
        transition = Transition(self.manifolds[manifold1.label],
                                self.manifolds[manifold2.label], d_q)
        self.transitions[transition.labels()] = transition

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
