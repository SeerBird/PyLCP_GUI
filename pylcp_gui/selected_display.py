from typing import TypeAlias, TYPE_CHECKING
import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QFormLayout, QLabel, QScrollArea, QWidget, QVBoxLayout, \
    QPushButton, QHBoxLayout, QComboBox

from pylcp_gui.config import toggle_checked_bg, toggle_unchecked_bg
from pylcp_gui.diagram_internals.fine_state import FineState
from pylcp_gui.diagram_internals.hyperfine_state import HyperfineState
from pylcp_gui.diagram_internals.laser_display import LaserDisplay
from pylcp_gui.laser_tree import LabelGroup, FreqGroup, LaserItem
from pylcp_gui.util import transition_label, HyperfineKey, HFTransitionKey, DiagramChangeEvent, DiagramChangeType

if TYPE_CHECKING:
    from pylcp_gui import MainDialog

Selectable: TypeAlias = FineState | HyperfineState | LaserDisplay | LabelGroup | FreqGroup | LaserItem | None


class SelectedDisplay(QGroupBox):
    """Side panel widget that displays detailed properties and action controls for the currently selected GUI item.

    Supports inspecting FineState, HyperfineState, LaserDisplay, LabelGroup, FreqGroup, and LaserItem.
    MainDialog connects Diagram.diagram_changed to handle_diagram_changed to keep side panel controls in sync.
    """

    def __init__(self, /, parent):
        """Initialize SelectedDisplay inside the left panel container."""
        # the parent is the left panel QFrame
        super().__init__(title="", parent=parent)
        self.current_selection: Selectable = None
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
        """Helper to navigate up the widget hierarchy to retrieve the root MainDialog instance."""
        return self.parent().parent()

    def handle_diagram_changed(self, event: DiagramChangeEvent):
        """Handle Diagram model change signals to auto-clear or refresh side-panel controls.

        :param event: DiagramChangeEvent indicating which state, transition, or display was mutated.
        """
        if self.current_selection is None:
            return

        # Handle deletion invalidations
        if event.change_type == DiagramChangeType.FINE_STATE_DELETED:
            target_label = event.target
            if isinstance(self.current_selection, FineState) and self.current_selection.label == target_label:
                self.selection_changed(None)
                return
            if isinstance(self.current_selection, HyperfineState) and self.current_selection.key[0] == target_label:
                self.selection_changed(None)
                return
            if isinstance(self.current_selection, (FreqGroup, LaserItem, LabelGroup)):
                fine_trans = getattr(self.current_selection, 'transition', None)
                if fine_trans and (fine_trans.lower_label == target_label or fine_trans.upper_label == target_label):
                    self.selection_changed(None)
                    return

        if event.change_type == DiagramChangeType.TRANSITION_DELETED:
            target_labels = event.target
            if isinstance(self.current_selection, (LabelGroup, FreqGroup)):
                fine_trans = getattr(self.current_selection, 'transition', None)
                if fine_trans and (fine_trans.lower_label, fine_trans.upper_label) == target_labels:
                    self.selection_changed(None)
                    return

        # Re-render UI against live model
        self.refresh()

    def refresh(self):
        """Re-render the controls for the currently selected item against live diagram state."""
        if self.current_selection is not None:
            self.selection_changed(self.current_selection)

    def _clear_layout(self):
        """Remove and delete all dynamically generated child widgets from form and main layouts."""
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
        """Add a key-value text property row to the form layout.

        Args:
            label_text: Property description label.
            value_text: Property value string.
            tooltip: Optional tooltip for extra context.
        """
        lbl = QLabel(label_text)
        val = QLabel(value_text)
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if tooltip:
            val.setToolTip(tooltip)
        self.form_layout.addRow(lbl, val)

    def _add_delete_button(self, on_delete_callback):
        """Add a standardized 'Delete Item' button at the bottom of the side panel.

        Args:
            on_delete_callback: Callable function invoked when the delete button is clicked.
        """
        delete_btn = QPushButton("Delete Item")
        delete_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        delete_btn.setStyleSheet("background-color: #3d0c11; color: white;")
        delete_btn.clicked.connect(on_delete_callback)
        self.main_layout.addWidget(delete_btn)

    def selection_changed(self, new_selection: Selectable):
        """Update the side panel UI controls to reflect a newly selected workspace item.

        Args:
            new_selection: The selected item (FineState, HyperfineState, LaserDisplay, LabelGroup, FreqGroup, LaserItem, or None).
        """
        self.current_selection = new_selection
        self._clear_layout()

        if new_selection is None:
            self.setTitle("")
            self.setVisible(False)
            return

        self.setVisible(True)
        main_dialog = self._main_dialog()

        if isinstance(new_selection, FineState):
            self.setTitle(f"Fine structure state {new_selection.label}")
            self._add_row("Energy:", f"{new_selection.energy:.3E} Hz")
            self._add_row("J:", f"{new_selection.J:g}")
            self._add_row("gJ:", f"{new_selection.gJ:g}")
            A, B, C = new_selection.hf_coefs
            self._add_row("A_hfs:", f"{A:.3E} Hz")
            self._add_row("B_hfs:", f"{B:.3E} Hz")
            self._add_row("C_hfs:", f"{C:.3E} Hz")

            # Hyperfine States Toggle Section
            toggle_style = f"""
                QPushButton {{
                    background-color: {toggle_unchecked_bg.name()};
                }}
                QPushButton:checked {{
                    background-color: {toggle_checked_bg.name()};
                }}
            """
            all_hf = []
            for hf_key in new_selection.hyperfine_keys():
                if hf_key in main_dialog.diagram.hf_states:
                    all_hf.append(main_dialog.diagram.hf_states[hf_key])

            if all_hf:
                self.form_layout.addRow(QLabel("Hyperfine States:"))
                for hf_item in all_hf:
                    btn = QPushButton(f"F = {hf_item.F:g}")
                    btn.setCheckable(True)
                    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                    btn.setStyleSheet(toggle_style)
                    btn.setChecked(hf_item.isEnabled())

                    def hf_toggle(checked: bool, item=hf_item):
                        if item.isEnabled() != checked:
                            main_dialog.diagram.disable_hyperfine_state(item.key)

                    btn.toggled.connect(hf_toggle)
                    self.main_layout.addWidget(btn)

            def delete_state():
                main_dialog.diagram.delete_fine_state(new_selection.label)

            self._add_delete_button(delete_state)

        elif isinstance(new_selection, HyperfineState):
            self.setTitle(f"Hyperfine state ({new_selection.key[0]}, F = {new_selection.F:g})")
            self._add_row("Fine Energy:", f"{new_selection.parentItem().energy:.3E} Hz")
            self._add_row("HF Correction:", f"{new_selection.hf_correction():.3E} Hz")

            def delete_hf():
                main_dialog.diagram.disable_hyperfine_state(new_selection.key)

            self._add_delete_button(delete_hf)

        elif isinstance(new_selection, LaserDisplay):
            self.setTitle(f"LaserDisplay ({new_selection.freq:.3E} Hz)")
            keys = new_selection.keys_ordered()
            lower_str = f"({keys[0][0]}, F={keys[0][1]:g})"
            upper_str = f"({keys[1][0]}, F={keys[1][1]:g})"
            self._add_row("Lower State:", lower_str)
            self._add_row("Upper State:", upper_str)
            self._add_row("Frequency:", f"{new_selection.freq:.3E} Hz")

            detuning = new_selection.detuning()
            self._add_row("Detuning:", f"{detuning:.3E} Hz")

            def delete_display():
                main_dialog.diagram.delete_laser_display(new_selection.keys, new_selection.freq)

            self._add_delete_button(delete_display)

        elif isinstance(new_selection, LabelGroup):
            labels = new_selection.transition
            self.setTitle(f"Transition {transition_label(labels)}")
            lower, upper = [main_dialog.fine_state(label) for label in labels]
            self._add_row("Lower Energy:", f"{lower.energy:.3E} Hz")
            self._add_row("Upper Energy:", f"{upper.energy:.3E} Hz")
            trans_energy = upper.energy - lower.energy
            self._add_row("Trans. Energy:", f"{trans_energy:.3E} Hz")
            gamma = main_dialog.transition(labels).gamma
            self._add_row("\u0393 (Gamma):", f"{gamma:.3E} Hz")

            def delete_trans():
                main_dialog.diagram.delete_transition((labels.lower_label, labels.upper_label))

            self._add_delete_button(delete_trans)

        elif isinstance(new_selection, FreqGroup):
            self.setTitle(f"{new_selection.text()}")
            self._add_row("Frequency:", f"{new_selection.freq:.3E} Hz")
            self._add_row("Beams Count:", f"{new_selection.rowCount()}")
            self._add_row("Transition:", str(new_selection.transition))

            fine_trans = new_selection.transition
            fine_lower = main_dialog.fine_state(fine_trans.lower_label)
            fine_upper = main_dialog.fine_state(fine_trans.upper_label)

            gamma = main_dialog.transition(fine_trans).gamma

            lower_substates = fine_lower.active_substates if hasattr(fine_lower, 'active_substates') else fine_lower.substates
            upper_substates = fine_upper.active_substates if hasattr(fine_upper, 'active_substates') else fine_upper.substates

            candidates: list[tuple[HFTransitionKey, float, float, float]] = []
            for F1 in lower_substates.keys():
                for F2 in upper_substates.keys():
                    key1 = HyperfineKey(fine_trans.lower_label, float(F1))
                    key2 = HyperfineKey(fine_trans.upper_label, float(F2))
                    hf_trans = HFTransitionKey(key1, key2)

                    if key1 not in main_dialog.diagram.hf_states or key2 not in main_dialog.diagram.hf_states:
                        continue
                    hf1 = main_dialog.diagram.hf_states[key1]
                    hf2 = main_dialog.diagram.hf_states[key2]
                    if not (hf1.isEnabled() and hf2.isEnabled()):
                        continue
                    lower_energy = hf1.parentItem().energy + hf1.hf_correction()
                    upper_energy = hf2.parentItem().energy + hf2.hf_correction()
                    trans_energy = upper_energy - lower_energy
                    detuning_Hz = new_selection.freq - trans_energy
                    delta_gamma = detuning_Hz / gamma
                    candidates.append((hf_trans, F1, F2, delta_gamma))

            candidates.sort(key=lambda item: abs(item[3]))

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
                button = QPushButton(f"F={F1:g} \u2192 F'={F2:g}  (\u0394 = {delta_gamma:+.2f} \u0393)")
                button.setCheckable(True)
                button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                button.setStyleSheet(toggle_style)
                button.setChecked(hf_trans in new_selection.enabled_transitions)

                def handler(checked: bool, key=hf_trans, group=new_selection):
                    if checked:
                        if key not in group.enabled_transitions:
                            group.enabled_transitions.append(key)
                    else:
                        if key in group.enabled_transitions:
                            group.enabled_transitions.remove(key)
                    main_dialog.diagram.show_magnetic_couplings(group.lasers[0] if group.lasers else None)

                button.toggled.connect(handler)
                layout.addWidget(button)

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

            def delete_laser():
                freq_group = new_selection.parent()
                if freq_group is not None:
                    freq_group.lasers.remove(new_selection)
                    freq_group.removeRow(new_selection.row())
                    main_dialog.laser_tree.item_selected.emit(None)

            self._add_delete_button(delete_laser)
        else:
            self.setTitle("")
            self.setVisible(False)
