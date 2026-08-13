from typing import TypeAlias, TYPE_CHECKING
import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QFormLayout, QLabel

from pylcp_gui.diagram_internals.fine_state import FineState
from pylcp_gui.diagram_internals.hyperfine_state import HyperfineState
from pylcp_gui.diagram_internals.laser_display import LaserDisplay
from pylcp_gui.laser_tree import LabelGroup, FreqGroup, LaserItem
from pylcp_gui.util import transition_label

if TYPE_CHECKING:
    from pylcp_gui import MainDialog

Selectable: TypeAlias = FineState | HyperfineState | LaserDisplay | LabelGroup | FreqGroup | LaserItem | None


class SelectedDisplay(QGroupBox):
    def __init__(self, /, parent):
        # the parent is the left panel QFrame
        super().__init__(title="", parent=parent)
        self.form_layout = QFormLayout(self)
        self.form_layout.setContentsMargins(8, 8, 8, 8)
        self.form_layout.setHorizontalSpacing(10)
        self.form_layout.setVerticalSpacing(4)
        self.setVisible(False)

    def _main_dialog(self) -> MainDialog:
        return self.parent().parent()

    def _clear_layout(self):
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _add_row(self, label_text: str, value_text: str, tooltip: str = ""):
        lbl = QLabel(label_text)
        val = QLabel(value_text)
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if tooltip:
            val.setToolTip(tooltip)
        self.form_layout.addRow(lbl, val)

    def selection_changed(self, new_selection: Selectable):
        self._clear_layout()

        if new_selection is None:
            self.setTitle("")
            self.setVisible(False)
            return

        self.setVisible(True)

        if isinstance(new_selection, FineState):
            self.setTitle(f"Fine structure state {new_selection.label}")
            self._add_row("Energy:", f"{new_selection.energy:.3E} Hz")
            self._add_row("J:", f"{new_selection.J:g}")
            self._add_row("gJ:", f"{new_selection.gJ:g}")
            A, B, C = new_selection.hf_coefs
            self._add_row("A_hfs:", f"{A:.3E} Hz")
            self._add_row("B_hfs:", f"{B:.3E} Hz")
            self._add_row("C_hfs:", f"{C:.3E} Hz")

        elif isinstance(new_selection, HyperfineState):
            self.setTitle(f"Hyperfine state ({new_selection.key[0]}, F = {new_selection.F:g})")
            self._add_row("Fine Energy:", f"{new_selection.parentItem().energy:.3E} Hz")
            self._add_row("HF Correction:", f"{new_selection.hf_correction():.3E} Hz")

        elif isinstance(new_selection, LaserDisplay):
            self.setTitle(f"LaserDisplay ({new_selection.freq:.3E} Hz)")
            keys = new_selection.keys()
            lower_str = f"({keys[0][0]}, F={keys[0][1]:g})"
            upper_str = f"({keys[1][0]}, F={keys[1][1]:g})"
            self._add_row("Lower State:", lower_str)
            self._add_row("Upper State:", upper_str)
            self._add_row("Frequency:", f"{new_selection.freq:.3E} Hz")

            # Calculate detuning Delta
            detuning = new_selection.detuning()
            self._add_row("Detuning:", f"{detuning:.3E} Hz")

        elif isinstance(new_selection, LabelGroup):
            labels = new_selection.labels
            self.setTitle(f"Transition {transition_label(labels)}")
            lower, upper = [self._main_dialog().fine_state(label) for label in labels]
            self._add_row("Lower Energy:", f"{lower.energy:.3E} Hz")
            self._add_row("Upper Energy:", f"{upper.energy:.3E} Hz")
            trans_energy = upper.energy - lower.energy
            self._add_row("Trans. Energy:", f"{trans_energy:.3E} Hz")
            gamma = self._main_dialog().transition(labels).gamma
            self._add_row("\u0393 (Gamma):", f"{gamma:.3E} Hz")

        elif isinstance(new_selection, FreqGroup):
            self.setTitle(f"Laser {new_selection.text()}")
            self._add_row("Frequency:", f"{new_selection.freq:.3E} Hz")
            self._add_row("Beams Count:", f"{new_selection.rowCount()}")

        elif isinstance(new_selection, LaserItem):
            self.setTitle(f"Laser Beam")
            self._add_row("Frequency:", f"{new_selection.freq:.3E} Hz")
            if isinstance(new_selection.kvec, np.ndarray):
                k_str = f"({new_selection.kvec[0]:.2f}, {new_selection.kvec[1]:.2f}, {new_selection.kvec[2]:.2f})"
            else:
                k_str = str(new_selection.kvec)
            self._add_row("k-vector:", k_str)

            if isinstance(new_selection.pol, np.ndarray):
                p_str = f"({new_selection.pol[0]:.2f}, {new_selection.pol[1]:.2f}, {new_selection.pol[2]:.2f})"
            else:
                p_str = str(new_selection.pol)
            self._add_row("Polarization:", p_str)
            self._add_row("Intensity:", f"{new_selection.intensity}")

        else:
            self.setTitle("")
            self.setVisible(False)
