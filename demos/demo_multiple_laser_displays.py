import sys
import os
import numpy as np
import pylcp
from scipy.constants import c


from PySide6.QtWidgets import QApplication, QStyleFactory
from pylcp_gui.dataframe.dataframe import StateData, TransitionData, LaserDisplayData, DataFrame
from pylcp_gui.main_dialog import MainDialog


def build_rubidium_frame() -> tuple[DataFrame, tuple, tuple]:
    frame = DataFrame()
    rb = pylcp.atom("87Rb")
    frame.I = rb.I
    frame.gI = rb.gI

    def get_state_data(label: str, atom: pylcp.atom, index: int):
        state = atom.state[index]
        energy = state.energy * 1e2 * c
        state_data = StateData(label, energy, state.J,
                               (state.Ahfs, state.Bhfs, state.Chfs), state.gJ)
        Fs = np.arange(np.abs(state.J - atom.I), state.J + atom.I + 1, 1)
        for F in Fs:
            state_data.substates[F] = list(np.arange(-F, F + 1, 1.0))
        return state_data

    frame.states['g'] = get_state_data('g', rb, 0)
    frame.states['e'] = get_state_data('e', rb, 2)
    frame.add_transition('g', 'e', TransitionData(rb.state[2].gammaHz))

    g_F1_key = ('g', 1.0)
    e_F3_key = ('e', 3.0)

    return frame, g_F1_key, e_F3_key


def launch_demo():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))

    frame, g_key, e_key = build_rubidium_frame()

    # Instantiate MainDialog with Rubidium frame
    dialog = MainDialog(frame)

    # Calculate resonance frequency between g (F=1) and e (F=3)
    g_state = dialog.diagram.hf_states[g_key]
    e_state = dialog.diagram.hf_states[e_key]
    res_freq = abs(g_state.energy() - e_state.energy())

    # Add 3 LaserDisplays targeting the SAME excited hyperfine state (e, F=3):
    # 1. On-resonance
    dialog.diagram.add_laser_display(LaserDisplayData(res_freq, (g_key, e_key), True))
    # 2. Detuned +5.0 MHz (or units)
    dialog.diagram.add_laser_display(LaserDisplayData(res_freq + 5.0e6, (g_key, e_key), True))
    # 3. Detuned -5.0 MHz (or units)
    dialog.diagram.add_laser_display(LaserDisplayData(res_freq - 5.0e6, (g_key, e_key), True))

    print("Launching PyLCP GUI with 3 pre-configured LaserDisplays targeting (e, F=3)...")
    dialog.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch_demo()
