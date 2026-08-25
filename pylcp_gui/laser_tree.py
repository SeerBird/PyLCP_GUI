from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem, Qt, QAction
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QAbstractItemView, QMenu

if TYPE_CHECKING:
    from pylcp_gui.main_dialog import MainDialog
from pylcp_gui.dataframe.dataframe import LaserData, LaserFreqGroup, LaserTransitionGroup
from pylcp_gui.util import FineTransitionKey


def laser_item_key(labels, freq, name):
    return labels, freq, name


def freq_group_key(labels, freq):
    return labels, freq


class LaserItem(LaserData, QStandardItem):
    def __init__(self, laser_data: LaserData, name):
        LaserData.__init__(self, laser_data)
        QStandardItem.__init__(self, name)

    def parent(self, /) -> FreqGroup:
        return super().parent()


class FreqGroup(LaserFreqGroup[LaserItem], QStandardItem):
    def __init__(self, laser_tree: LaserTree, freq: float, transition: FineTransitionKey):
        LaserFreqGroup.__init__(self, freq, transition)
        main_dialog = laser_tree.main_dialog()
        delta = main_dialog.get_detuning(transition, freq)
        QStandardItem.__init__(self, f"{delta} Gamma")

    def add_laser(self, laser: LaserItem):
        LaserFreqGroup.add_laser(self, laser)
        self.appendRow(laser)


class LabelGroup(LaserTransitionGroup[FreqGroup], QStandardItem):
    def __init__(self, transition: FineTransitionKey):
        QStandardItem.__init__(self, str(transition))
        LaserTransitionGroup.__init__(self, transition)

    def add_freq_group(self, freq_group: FreqGroup):
        self.appendRow(freq_group)
        self.freq_groups[freq_group.freq] = freq_group


class LaserTree(QWidget):
    add_laser_display = Signal(tuple, float)  # tuple[str,str]
    item_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree_view = QTreeView(self)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)  # read-only
        layout.addWidget(self.tree_view)

        self.model = QStandardItemModel()
        self.tree_view.setModel(self.model)

        self.tree_view.selectionModel().selectionChanged.connect(self.handle_selection_changed)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)
        self.lasers: dict[FineTransitionKey, LabelGroup] = {}

    def clearSelection(self):
        self.tree_view.selectionModel().clearSelection()

    def handle_selection_changed(self, selected, deselected):
        indexes = self.tree_view.selectedIndexes()
        if indexes:
            item = self.model.itemFromIndex(indexes[0])
            self.item_selected.emit(item)
        else:
            self.item_selected.emit(None)

    def add_laser(self, laser_data: LaserData, transition: FineTransitionKey):
        """group_name will be used as the name of the new frequency group if there is exactly one existing laser with the same
        frequency as the new one"""
        freq = laser_data.freq
        i = 0
        if transition not in self.lasers:
            raise ValueError()
        label_group = self.lasers[transition]
        if freq not in label_group.freq_groups:
            freq_group = FreqGroup(self, freq, transition)
            label_group.add_freq_group(freq_group)
        else:
            freq_group = label_group.freq_groups[freq]
        names = [laser.text() for laser in freq_group.lasers]
        while True:
            name = f"Laser {i}"
            if not name in names:
                item = LaserItem(laser_data, name)
                freq_group.add_laser(item)
                break
            i += 1

    def show_context_menu(self, position: QPoint):
        index = self.tree_view.indexAt(position)
        if not index.isValid():
            return  # right-clicked empty white space inside the tree window

        item = self.model.itemFromIndex(index)

        if isinstance(item, FreqGroup | LaserItem):
            if isinstance(item, LaserItem):
                freq = item.freq
                transition = item.parent().transition
            elif isinstance(item, FreqGroup):
                freq = item.freq
                transition = item.transition
            menu = QMenu(self.tree_view)
            add_display = QAction("Add display", self)
            add_display.triggered.connect(
                lambda: self.add_laser_display.emit(transition, freq))
            menu.addAction(add_display)
            global_position = self.tree_view.viewport().mapToGlobal(position)
            menu.exec(global_position)

    def main_dialog(self) -> MainDialog:
        return self.parent().parent()

    def add_transition_key(self, transition_key: FineTransitionKey):
        label_group = LabelGroup(transition_key)
        self.lasers[transition_key] = label_group
        self.model.appendRow(label_group)
        self.tree_view.expand(label_group.index())

    def remove_transition_key(self, transition_key: FineTransitionKey):
        label_group = self.lasers.pop(transition_key)
        self.model.removeRow(label_group.row())

    def purge_hyperfine_key(self, hf_key: HyperfineKey):
        """Remove any enabled transition in all FreqGroups involving the given HyperfineKey."""
        for label_group in self.lasers.values():
            for freq_group in label_group.freq_groups.values():
                freq_group.enabled_transitions = [
                    trans for trans in freq_group.enabled_transitions
                    if trans.lower_key != hf_key and trans.upper_key != hf_key
                ]

    def purge_fine_state(self, label: str):
        """Remove any enabled transition in all FreqGroups involving the given FineState label."""
        for label_group in self.lasers.values():
            for freq_group in label_group.freq_groups.values():
                freq_group.enabled_transitions = [
                    trans for trans in freq_group.enabled_transitions
                    if trans.lower_key.label != label and trans.upper_key.label != label
                ]
