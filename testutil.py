import numpy as np
import pylcp
from scipy.constants import c

from pylcp_gui import DataFrame, MainDialog
from pylcp_gui.dataframe.dataframe import StateData, TransitionData, LaserDisplayData, Atom
from scipy.spatial.transform import Rotation

from pylcp_gui.laser_tree import FreqGroup, LaserItem


def conventional3DMOTBeams_kvecs_and_pols():
    rot_mat = Rotation.from_euler('ZYZ', [0, 0, 0]).as_matrix()

    kvecs = [np.array([1., 0., 0.]), np.array([-1., 0., 0.]),
             np.array([0., 1., 0.]), np.array([0., -1., 0.]),
             np.array([0., 0., 1.]), np.array([0., 0., -1.])]
    pol = 1
    pols = [-pol, -pol, -pol, -pol, +pol, +pol]
    lasers = []
    for kvec, _pol in zip(kvecs, pols):
        lasers.append((rot_mat @ kvec, _pol))
    return lasers


def get_transition_data(atom: pylcp.atom, upper_index):
    return TransitionData(atom.state[upper_index].gammaHz)


def get_state_data(label: str, atom: pylcp.atom, index):
    state = atom.state[index]
    I, J, energy = atom.I, state.J, state.energy * 1e2 * c
    state_data = StateData(label, energy, I, J,
                           (state.Ahfs, state.Bhfs, state.Chfs), state.gJ)

    return state_data


def make_rubidium_frame(det, s, alpha):
    frame = DataFrame.create_from_atom(Atom.Rb87)
    for kvec, pol in conventional3DMOTBeams_kvecs_and_pols():
        frame.add_laser('g', 'e2', 1, 2, 0, kvec, pol, 0.01 * s)
        frame.add_laser('g', 'e2', 2, 3, det, kvec, pol, s)
    frame.add_laser_display(0, 2, 3, excited_label="e2")
    frame.add_laser_display(1, 1, 2, excited_label="e2")
    frame.set_magnetic_field(pylcp.quadrupoleMagneticField(alpha))
    return frame


def add_laser_display(dialog: MainDialog, groupIndex: int, F1, F2, orientation: bool = True):
    group: FreqGroup | LaserItem = list(dialog.laser_tree.freq_groups.values())[groupIndex]
    label1, label2 = group.labels
    keys = ((label1, float(F1)), (label2, float(F2)))
    dialog.add_laser_display_from_values(LaserDisplayData(group.freq, keys, orientation))
