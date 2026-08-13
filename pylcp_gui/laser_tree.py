from PySide6.QtCore import QPoint, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem, Qt, QAction
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QAbstractItemView, QMenu

from pylcp_gui.dataframe.dataframe import LaserData
from pylcp_gui.util import transition_label

FreqGroupKey = tuple[tuple[str, str], float]
LaserItemKey = tuple[tuple[str, str], float, str] # label pair, frequency, name


def laser_item_key(labels, freq, name):
    return labels, freq, name


def freq_group_key(labels, freq):
    return labels, freq


class LabelGroup(QStandardItem):
    def __init__(self, labels: tuple[str, str]):
        super().__init__(transition_label(labels))
        self.labels = labels


class DisplayableItem(QStandardItem):
    def __init__(self, text, freq, labels):
        super().__init__(text)
        self.freq = freq
        self.labels = labels


class FreqGroup(DisplayableItem):
    def __init__(self, freq, labels: tuple[str, str],name):
        super().__init__(name, freq, labels)
        self.key = freq_group_key(labels, freq)


class LaserItem(DisplayableItem):
    def __init__(self, laser_data: LaserData, labels, name):
        super().__init__(name, laser_data.freq, labels)
        self.kvec = laser_data.kvec  # unit vector
        self.pol = laser_data.pol  # stored in polar
        self.intensity = laser_data.intensity
        self.name = name
        self.key = laser_item_key(labels, self.freq, name)


class LaserTree(QWidget):
    add_laser_display = Signal(tuple, float) # tuple[str,str]
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
        self.tree_view.clicked.connect(self.handle_item_clicked)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)
        self.freq_groups: dict[FreqGroupKey, FreqGroup | LaserItem] = {}
        self.label_groups: dict[tuple[str, str], LabelGroup] = {}
        self.lasers: dict[LaserItemKey, LaserItem] = {}

    def clearSelection(self):
        self.tree_view.selectionModel().clearSelection()

    def handle_selection_changed(self, selected, deselected):
        indexes = self.tree_view.selectedIndexes()
        if indexes:
            item = self.model.itemFromIndex(indexes[0])
            self.item_selected.emit(item)
        else:
            self.item_selected.emit(None)

    def add_laser(self, laser_data, labels, group_name = None):
        """group_name will be used as the name of the new frequency group if there is exactly one existing laser with the same
        frequency as the new one"""
        freq = laser_data.freq
        i = 0
        while True:
            name = f"Laser {i}"
            key = laser_item_key(labels, freq, name)
            if not key in self.lasers:
                item = LaserItem(laser_data, labels, name)
                self.lasers[key] = item
                break
            i += 1

        # if no previous lasers on this transition, add label group (e.g. 'g->e')
        if not labels in self.label_groups:
            label_group = LabelGroup(labels)
            self.label_groups[labels] = label_group
            self.model.appendRow(label_group)
        label_group = self.label_groups[labels]
        # if there is a previous laser with the same frequency, check how many
        freq_key = freq_group_key(labels, freq)
        if freq_key in self.freq_groups:
            previous_item = self.freq_groups[freq_key]
            # if there was only one laser with the same frequency, create a freq group
            if isinstance(previous_item, LaserItem):
                if group_name is None:
                    i = 0
                    existing_names = [freq_group.text() if isinstance(freq_group,FreqGroup) else None for freq_group in self.freq_groups.values()]
                    while True:
                        group_name = f"Group {i}"
                        if not group_name in existing_names:
                            break
                        i += 1
                label_group.takeRow(self.model.indexFromItem(previous_item).row())
                group = FreqGroup(freq, labels, group_name)
                self.freq_groups[freq_group_key(labels,freq)] = group
                group.appendRow(previous_item)
                group.appendRow(item)
                label_group.appendRow(group)
            else:  # if there was already a frequency group for this frequency, add to it
                previous_item.appendRow(item)
        else:
            self.freq_groups[freq_key] = item
            label_group.appendRow(item)

    def show_context_menu(self, position: QPoint):
        index = self.tree_view.indexAt(position)
        if not index.isValid():
            return  # right-clicked empty white space inside the tree window

        item = self.model.itemFromIndex(index)

        if isinstance(item, DisplayableItem):
            menu = QMenu(self.tree_view)
            add_display = QAction("Add display", self)
            add_display.triggered.connect(
                lambda: self.add_laser_display.emit(item.labels, item.freq))
            menu.addAction(add_display)
            global_position = self.tree_view.viewport().mapToGlobal(position)
            menu.exec(global_position)

    def handle_item_clicked(self, index):
        if not index.isValid():
            return  # right-clicked empty white space inside the tree window
        pass

    def has_one_in_freq_group(self, labels, freq):
        return isinstance(self.freq_groups[freq_group_key(labels,freq)], LaserItem)
