from typing import TypeAlias, TYPE_CHECKING

from PySide6.QtWidgets import QGroupBox

from pylcp_gui.diagram_internals.fine_state import FineState
from pylcp_gui.diagram_internals.hyperfine_state import HyperfineState
from pylcp_gui.diagram_internals.laser_display import LaserDisplay
from pylcp_gui.laser_tree import LabelGroup, FreqGroup, LaserItem

if TYPE_CHECKING:
    from pylcp_gui import MainDialog

Selectable: TypeAlias = FineState | HyperfineState | LaserDisplay | LabelGroup | FreqGroup | LaserItem


class SelectedDisplay(QGroupBox):
    def __init__(self, /, parent):
        # the parent is the left panel QFrame
        super().__init__(title="", parent=parent)

    def _main_dialog(self) -> MainDialog:
        return self.parent().parent()

    def selection_changed(self, new_selection: Selectable):
        # TODO: in each case, redo layout and display the object's properties, formatted reasonably;
        #  the QGroupBox title should be the name of the item
        if isinstance(new_selection, FineState):
            pass  # show J, energy, gamma, hyperfine coefficients, gJ
        elif isinstance(new_selection, HyperfineState):
            pass  # show F, fine state energy, hyperfine correction
        elif isinstance(new_selection, LaserDisplay):
            # show lower state (fine state label, F), upper state (fine state label, F),
            # laser frequency, detuning
            pass
        elif isinstance(new_selection, LabelGroup):
            lower, upper = [self._main_dialog().fine_state(label) for label in new_selection.labels]
            transition_energy = upper.energy - lower.energy
            pass  # show transition energy
        elif isinstance(new_selection, FreqGroup):
            pass # show frequency
        elif isinstance(new_selection, LaserItem):
            pass # show frequency, k-vector, polarization, intensity,
        else:
            pass # make the 'selected' display invisible
