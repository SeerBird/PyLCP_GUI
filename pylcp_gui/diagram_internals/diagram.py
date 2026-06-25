import logging
from functools import partial

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QGraphicsScene, QGraphicsProxyWidget, QGraphicsItem

from pylcp_gui import config
from pylcp_gui.dataframe.dataframe import StateData, TransitionData, LaserData
from pylcp_gui.diagram_internals.laser_beam import LaserBeam
from pylcp_gui.diagram_internals.manifold import Manifold, GraphicsDragFilter
import numpy as np

from pylcp_gui.diagram_internals.manifold_proxy import ManifoldProxy
from pylcp_gui.diagram_internals.transition import Transition
from pylcp_gui.util import addDebugFilter, sort_float_then_string, sort_manifolds

logger: logging.Logger = logging.getLogger(__name__)


class Diagram(QGraphicsScene):

    def __init__(self, /):
        super().__init__()
        self.manifolds: dict[str, Manifold] = {}  # dict str->Manifold
        self.transitions: dict[frozenset[str], Transition] = {}
        # TODO: decide if I'm keeping the frozenset
        self.lasers: dict[frozenset[str], list[LaserBeam]] = {}
        self.manifold_transition_map: dict[str, list[Transition]] = {}
        self.selected_manifold = None

    # region adding elements

    def add_manifold_from_values(self, manifold_data: StateData):
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
        manifold.positionChanged.connect(partial(self.manifoldMoved, manifold.label))
        manifold.delete.connect(partial(self.delete_manifold, manifold.label))
        return manifold

    def add_transition_from_values(self, transition_data: TransitionData,
                                   manifold1: Manifold, manifold2: Manifold):
        transition = Transition(transition_data, manifold1, manifold2)
        self.transitions[frozenset(transition.labels)] = transition
        self.manifold_transition_map[manifold1.label].append(transition)
        self.manifold_transition_map[manifold2.label].append(transition)
        self.lasers[frozenset(transition.labels)] = []
        self.addItem(transition)
        return transition

    def add_laser_from_values(self, laser_data: LaserData, labels: tuple[str,str]):
        laser = LaserBeam(laser_data, labels)
        self.lasers[frozenset(labels)].append(laser)
        return laser

    # endregion

    # region deleting elements
    def removeItemDeferred(self, item: QGraphicsItem):
        QTimer.singleShot(0, partial(self.removeItem, item))

    def delete_transition(self, labels: tuple[str, str]):
        transition = self.transitions[frozenset(labels)]
        self.manifold_transition_map[labels[0]].remove(transition)
        self.manifold_transition_map[labels[1]].remove(transition)
        self.transitions.pop(frozenset(transition.labels))
        transition.deleteLater()
        logger.debug(f"Deleting transition")

    def delete_manifold(self, label: str):
        manifold = self.manifolds[label]
        transitions = self.manifold_transition_map[label].copy()
        for transition in transitions:
            self.delete_transition(transition.labels)
        self.manifold_transition_map.pop(label)
        self.manifolds.pop(label)
        proxy = manifold.graphicsProxyWidget()
        assert proxy is not None
        proxy.deleteLater()
        logger.debug(f"Deleting manifold")

    # endregion

    def manifoldMoved(self, label: str):
        for transition in self.manifold_transition_map[label]:
            p1 = self.manifolds[transition.labels[0]].geometry().center()
            p2 = self.manifolds[transition.labels[1]].geometry().center()
            transition.trackNodes(p1, p2)

    def rearrange(self):
        self.setSceneRect(self.views()[0].rect())  # TODO: this is iffy
        manifolds = np.asarray(list(self.manifolds.values()))
        if manifolds.size == 0:
            return
        sort = sort_manifolds(manifolds)
        manifolds = manifolds[sort]  # sorted in ascending energy order
        # TODO: manifolds[0] is iffy
        total_height = self.sceneRect().height() - manifolds[0].height()
        y = np.linspace(total_height * config.diagram_rearrange_margin_fraction,
                        total_height * (1 - config.diagram_rearrange_margin_fraction),
                        manifolds.size)[::-1]
        manifold: Manifold
        for i in range(manifolds.size):
            manifold = manifolds[i]
            proxy = manifold.graphicsProxyWidget()
            assert proxy is not None
            proxy.setY(y[i])
            manifold.positionChanged.emit()
