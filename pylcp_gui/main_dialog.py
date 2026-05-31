from __future__ import annotations
from typing import override, TYPE_CHECKING

from PySide6.QtCore import Signal, QSize
from PySide6.QtWidgets import QDialog, QGridLayout, QDialogButtonBox, QApplication, QGroupBox, \
    QComboBox, QLayout, QGraphicsScene, QGraphicsView, QFrame, QInputDialog, QLineEdit, QPushButton

from pylcp_gui.manifold_dialog import ManifoldDialog
from pylcp_gui.diagram import Diagram
from pylcp_gui.graphics_view import GraphicsView
from pylcp_gui.hamiltonian_container import HamiltonianContainer


class MainDialog(QDialog):

    def __init__(self, dataframe: HamiltonianContainer | None = None) -> None:
        super().__init__()
        # region set up initial interface
        self.create_right_panel()
        self.create_left_panel()

        main_layout = QGridLayout(self)
        main_layout.addWidget(self._right_panel, 0, 1)
        main_layout.addWidget(self._left_panel, 0, 0)
        main_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        self._main_layout = main_layout
        self.setLayout(self._main_layout)
        self.setWindowTitle("PyLCP GUI")
        self.setMinimumSize(QSize(8000,8000))
        # endregion
        if dataframe is None:
            self.dataframe: HamiltonianContainer = HamiltonianContainer()
        else:
            self.dataframe = dataframe
            # TODO: go through all the dataframe components and change the interface to reflect them

    @override
    def exec(self, /) -> HamiltonianContainer:
        # TODO: decide if I want to bother with a 'cleaner'
        #  separate Future that returns the dataframe once the dialog is done and call open() to
        #  start the dialog instead. easy to fix, clutters the code a bit, but potentially improves
        #  reliability?
        super().exec()
        return self.dataframe

    # region actions
    def add_manifold(self):
        dialog = ManifoldDialog()

        def add_manifold_from_dialog():
            values = dialog.values
            self.diagram.add_manifold_from_values(values)

        dialog.finished.connect(add_manifold_from_dialog)
        dialog.open()

    # endregion
    # region setup helpers
    def create_right_panel(self):
        self._right_panel = QFrame()
        self._right_layout = QGridLayout(self._right_panel)
        self.diagram = Diagram()
        self._right_layout.addWidget(GraphicsView(self.diagram))

    def create_left_panel(self):
        self._left_panel = QFrame()
        self.left_layout = QGridLayout(self._left_panel)
        add_manifold_button = QPushButton("Add manifold")
        add_manifold_button.clicked.connect(self.add_manifold)
        self.left_layout.addWidget(add_manifold_button)

    # endregion
