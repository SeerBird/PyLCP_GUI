import os.path

import numpy as np
import pylcp
from pylcp import obe
import faulthandler

from scipy.constants import h, elementary_charge, c

import pylcp_gui
from pylcp_gui.dataframe.dataframe import ManifoldData, TransitionData

# Force Python to print a dump of the active thread stack traces upon a hard crash
faulthandler.enable()
import pylcp_gui as gui
from pylcp_gui import DataFrame
det = -2.0
alpha = 1.0
s = 1.0
atom = pylcp.atom("87Rb")
H_g_D2, mu_q_g_D2 = pylcp.hamiltonians.hyperfine_coupled(
    atom.state[0].J, atom.I, atom.state[0].gJ, atom.gI,
    atom.state[0].Ahfs/atom.state[2].gammaHz, Bhfs=0, Chfs=0,
    muB=1)
H_e_D2, mu_q_e_D2 = pylcp.hamiltonians.hyperfine_coupled(
    atom.state[2].J, atom.I, atom.state[2].gJ, atom.gI,
    Ahfs=atom.state[2].Ahfs/atom.state[2].gammaHz,
    Bhfs=atom.state[2].Bhfs/atom.state[2].gammaHz, Chfs=0,
    muB=1)
dijq_D2 = pylcp.hamiltonians.dqij_two_hyperfine_manifolds(
    atom.state[0].J, atom.state[2].J, atom.I)

E_e_D2 = np.unique(np.diagonal(H_e_D2))
E_g_D2 = np.unique(np.diagonal(H_g_D2))

hamiltonian_D2 = pylcp.hamiltonian(H_g_D2, H_e_D2, mu_q_g_D2, mu_q_e_D2, dijq_D2)

# Now, we need to sets of laser beams -> one for F=1->2 and one for F=2->3:
laserBeams_cooling_D2 = pylcp.conventional3DMOTBeams(
    s=s, delta=(E_e_D2[-1] - E_g_D2[-1]) + det)
laserBeams_repump_D2 = pylcp.conventional3DMOTBeams(
    s=0.01*s, delta=(E_e_D2[-2] - E_g_D2[-2]))
laserBeams_D2 = laserBeams_cooling_D2 + laserBeams_repump_D2
def get_manifold(label: str, atom: pylcp.atom, index, F: int):
    state = atom.state[index]
    I, J, gamma = atom.I, state.J, state.gammaHz
    Ahf, Bhf, Chf = state.Ahfs, state.Bhfs, state.Chfs  # these are in Hz, I think
    K = F * (F + 1) - I * (I + 1) - J * (J + 1)
    energy = state.energy * 1e2 * c + Ahf * K / 2
    if Bhf != 0:
        energy += Bhf * (1.5 * K * (K + 1) - 2 * I * (I + 1) * J * (J + 1)) / (
                4 * I * (2 * I - 1) * J * (2 * J - 1))
    if Chf != 0:
        energy += Chf * (5 * K ** 2 * (K / 4 + 1)
                         + K * (I * (I + 1) + J * (J + 1) + 3 - 3 * I * (I + 1) * J * (J + 1))
                         - 5 * I * (I + 1) * J * (J + 1)) / (
                          I * (I - 1) * (2 * I - 1) * J * (J - 1) * (2 * J - 1))
    # change from Hz to eV
    energy *= h / elementary_charge
    return ManifoldData(label, energy, F, J, gamma)


frame = DataFrame()
rb = pylcp.atom("Rb87")
frame.I = rb.I
frame.manifolds['g'] = get_manifold('g', rb, 0, 2)
frame.manifolds['e'] = get_manifold('e', rb, 2, 3)
frame.manifolds['r'] = get_manifold('r', rb, 0, 1)
frame.transitions[('g', 'e')] = TransitionData()
frame.transitions[('r', 'e')] = TransitionData()
dialog = pylcp_gui.dialog(frame)
