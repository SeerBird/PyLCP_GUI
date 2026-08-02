import os.path

import numpy as np
import pylcp

from scipy.constants import c
from scipy.spatial.transform import Rotation

from pylcp_gui.dataframe.dataframe import StateData, TransitionData
from pylcp_gui import DataFrame, dialog_from_dataframe
import matplotlib.pyplot as plt

from testutil import make_rubidium_frame

det = -2.0
s = 1.0
alpha = 1.0

# region frame
frame = make_rubidium_frame(det, s)
dialog_from_dataframe(frame)

frame_ham = frame._hamiltonian()
frame_ham.make_full_matrices()
frame_lasers = frame._lasers()
frame_rate = frame.rateeq(pylcp.quadrupoleMagneticField(alpha))
# endregion


# region pylcp example
atom = pylcp.atom("87Rb")
H_g_D2, mu_q_g_D2 = pylcp.hamiltonians.hyperfine_coupled(
    atom.state[0].J, atom.I, atom.state[0].gJ, atom.gI,
    atom.state[0].Ahfs / atom.state[2].gammaHz, Bhfs=0, Chfs=0,
    muB=1)
H_e_D2, mu_q_e_D2 = pylcp.hamiltonians.hyperfine_coupled(
    atom.state[2].J, atom.I, atom.state[2].gJ, atom.gI,
    Ahfs=atom.state[2].Ahfs / atom.state[2].gammaHz,
    Bhfs=atom.state[2].Bhfs / atom.state[2].gammaHz, Chfs=0,
    muB=1)
dijq_D2 = pylcp.hamiltonians.dqij_two_hyperfine_manifolds(
    atom.state[0].J, atom.state[2].J, atom.I)

E_e_D2 = np.unique(np.diagonal(H_e_D2))
E_g_D2 = np.unique(np.diagonal(H_g_D2))

hamiltonian_D2 = pylcp.hamiltonian(H_g_D2, H_e_D2, mu_q_g_D2, mu_q_e_D2, dijq_D2)
hamiltonian_D2.make_full_matrices()

# Now, we need two sets of laser beams -> one for F=1->2 and one for F=2->3:
laserBeams_cooling_D2 = pylcp.conventional3DMOTBeams(
    s=s, delta=(E_e_D2[-1] - E_g_D2[-1]) + det)  # F=3 minus F=2 hyperfine energies
laserBeams_repump_D2 = pylcp.conventional3DMOTBeams(
    s=0.01 * s, delta=(E_e_D2[-2] - E_g_D2[-2]))  # F = 2 minus F = 1 hyperfine energies
laserBeams_D2 = laserBeams_cooling_D2 + laserBeams_repump_D2
ex_rate = pylcp.rateeq(laserBeams_D2, pylcp.quadrupoleMagneticField(alpha), hamiltonian_D2,
                       include_mag_forces=False)


# endregion
def compareLasers(attribute: str):
    return [[getattr(laserBeams_repump_D2.beam_vector[0], attribute)(),
             getattr(frame_lasers['g->e'].beam_vector[0], attribute)()],
            [getattr(laserBeams_cooling_D2.beam_vector[0], attribute)(),
             getattr(frame_lasers['g->e'].beam_vector[1], attribute)()], ]


x = np.arange(-5, 5.1, 0.2)
v = np.arange(-5, 5.1, 0.2)

dx = np.mean(np.diff(x))
dv = np.mean(np.diff(v))

X, V = np.meshgrid(x, v)


def force_profile(rate):
    rate.generate_force_profile(
        [np.zeros(X.shape), np.zeros(X.shape), X],
        [np.zeros(V.shape), np.zeros(V.shape), V],
        name='Fz')
    return rate.profile['Fz'].F[2]


# region plot
ex_profile = force_profile(ex_rate)
frame_profile = force_profile(frame_rate)
plt.subplot(2, 2, 1)
plt.title("Frame force profile")
plt.ylabel('$v/(\\Gamma/k)$')
plt.xlabel('$x/\\mu_B B\'/\\hbar\\Gamma$')
plt.imshow(frame_profile, origin='lower',
           extent=(np.amin(x) - dx / 2, np.amax(x) + dx / 2,
                   np.amin(v) - dv / 2, np.amax(v) + dv / 2),
           aspect='auto')
plt.subplot(2, 2, 2)
plt.title("Example force profile")
plt.ylabel('$v/(\\Gamma/k)$')
plt.xlabel('$x/\\mu_B B\'/\\hbar\\Gamma$')
plt.imshow(ex_profile, origin='lower',
           extent=(np.amin(x) - dx / 2, np.amax(x) + dx / 2,
                   np.amin(v) - dv / 2, np.amax(v) + dv / 2),
           aspect='auto')
plt.subplot(2, 2, 3)
plt.title("Difference")
plt.ylabel('$v/(\\Gamma/k)$')
plt.xlabel('$x/\\mu_B B\'/\\hbar\\Gamma$')
plt.imshow(frame_profile - ex_profile, origin='lower',
           extent=(np.amin(x) - dx / 2, np.amax(x) + dx / 2,
                   np.amin(v) - dv / 2, np.amax(v) + dv / 2),
           aspect='auto')
plt.tight_layout()
plt.show()
# endregion
