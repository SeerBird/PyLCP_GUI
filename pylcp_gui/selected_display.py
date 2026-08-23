from typing import TypeAlias, TYPE_CHECKING
import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QFormLayout, QLabel, QScrollArea, QWidget, QVBoxLayout, QPushButton

from pylcp_gui.config import toggle_checked_bg, toggle_unchecked_bg
from pylcp_gui.diagram_internals.fine_state import FineState
from pylcp_gui.diagram_internals.hyperfine_state import HyperfineState
from pylcp_gui.diagram_internals.laser_display import LaserDisplay
from pylcp_gui.laser_tree import LabelGroup, FreqGroup, LaserItem
from pylcp_gui.util import transition_label, HyperfineKey, HFTransitionKey

if TYPE_CHECKING:
    from pylcp_gui import MainDialog

Selectable: TypeAlias = FineState | HyperfineState | LaserDisplay | LabelGroup | FreqGroup | LaserItem | None


class SelectedDisplay(QGroupBox):
    def __init__(self, /, parent):
        # the parent is the left panel QFrame
        super().__init__(title="", parent=parent)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(6)

        self.form_layout = QFormLayout()
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setHorizontalSpacing(10)
        self.form_layout.setVerticalSpacing(4)
        self.main_layout.addLayout(self.form_layout)
        self.setVisible(False)

    def _main_dialog(self) -> MainDialog:
        return self.parent().parent()

    def _clear_layout(self):
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        while self.main_layout.count() > 1:
            item = self.main_layout.takeAt(1)
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
            keys = new_selection.keys_ordered()
            lower_str = f"({keys[0][0]}, F={keys[0][1]:g})"
            upper_str = f"({keys[1][0]}, F={keys[1][1]:g})"
            self._add_row("Lower State:", lower_str)
            self._add_row("Upper State:", upper_str)
            self._add_row("Frequency:", f"{new_selection.freq:.3E} Hz")

            # Calculate detuning Delta
            detuning = new_selection.detuning()
            self._add_row("Detuning:", f"{detuning:.3E} Hz")

        elif isinstance(new_selection, LabelGroup):
            labels = new_selection.transition
            self.setTitle(f"Transition {transition_label(labels)}")
            lower, upper = [self._main_dialog().fine_state(label) for label in labels]
            self._add_row("Lower Energy:", f"{lower.energy:.3E} Hz")
            self._add_row("Upper Energy:", f"{upper.energy:.3E} Hz")
            trans_energy = upper.energy - lower.energy
            self._add_row("Trans. Energy:", f"{trans_energy:.3E} Hz")
            gamma = self._main_dialog().transition(labels).gamma
            self._add_row("\u0393 (Gamma):", f"{gamma:.3E} Hz")

        elif isinstance(new_selection, FreqGroup):
            self.setTitle(f"{new_selection.text()}")
            self._add_row("Frequency:", f"{new_selection.freq:.3E} Hz")
            self._add_row("Beams Count:", f"{new_selection.rowCount()}")
            self._add_row("Transition:", str(new_selection.transition))
            # region get hf transitions
            main_dialog = self._main_dialog()
            fine_trans = new_selection.transition
            fine_lower = main_dialog.fine_state(fine_trans.lower_label)
            fine_upper = main_dialog.fine_state(fine_trans.upper_label)

            gamma = main_dialog.transition(fine_trans).gamma

            lower_substates = fine_lower.active_substates if hasattr(fine_lower, 'active_substates') else fine_lower.substates
            upper_substates = fine_upper.active_substates if hasattr(fine_upper, 'active_substates') else fine_upper.substates

            candidates:list[tuple[HFTransitionKey,float,float,float]] = []
            for F1 in lower_substates.keys():
                for F2 in upper_substates.keys():
                    key1 = HyperfineKey(fine_trans.lower_label, float(F1))
                    key2 = HyperfineKey(fine_trans.upper_label, float(F2))
                    hf_trans = HFTransitionKey(key1, key2)

                    hf1 = main_dialog.diagram.hf_states[key1]
                    hf2 = main_dialog.diagram.hf_states[key2]
                    lower_energy = hf1.parentItem().energy + hf1.hf_correction()
                    upper_energy = hf2.parentItem().energy + hf2.hf_correction()
                    trans_energy = upper_energy - lower_energy
                    detuning_Hz = new_selection.freq - trans_energy
                    delta_gamma = detuning_Hz / gamma
                    candidates.append((hf_trans, F1, F2, delta_gamma))

            candidates.sort(key=lambda item: abs(item[3]))
            # endregion
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            container = QWidget()
            layout = QVBoxLayout(container)

            toggle_style = f"""
                QPushButton {{
                    background-color: {toggle_unchecked_bg.name()};
                }}
                QPushButton:checked {{
                    background-color: {toggle_checked_bg.name()};
                }}
            """

            for hf_trans, F1, F2, delta_gamma in candidates:
                btn = QPushButton(f"F={F1:g} \u2192 F'={F2:g}  (\u0394 = {delta_gamma:+.2f} \u0393)")
                btn.setCheckable(True)
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                btn.setStyleSheet(toggle_style)
                btn.setChecked(hf_trans in new_selection.enabled_transitions)

                def make_handler(key=hf_trans, group=new_selection):
                    def handler(checked: bool):
                        if checked:
                            if key not in group.enabled_transitions:
                                group.enabled_transitions.append(key)
                        else:
                            if key in group.enabled_transitions:
                                group.enabled_transitions.remove(key)
                    return handler

                btn.toggled.connect(make_handler(hf_trans, new_selection))
                layout.addWidget(btn)

            scroll.setWidget(container)
            self.form_layout.addRow(QLabel("Transitions:"))
            self.main_layout.addWidget(scroll, stretch=1)

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
