import numpy as np
import pylcp
import matplotlib.pyplot as plt
import types

from testutil import make_rubidium_frame
from pylcp_gui.util import (
    get_state_basis,
    hyperfine_correction,
    mu_q_coupled,
    _d_q_matrix_element,
    FineTransitionKey
)

# Simulation parameters
det = -2.0
s = 1.0
alpha = 1.0


# region 1. PyLCP Reference Model
def build_pylcp_reference(det: float, s: float, alpha: float):
    """Builds reference PyLCP rateeq model for 87Rb 3D MOT."""
    atom = pylcp.atom("87Rb")
    H_g_D2, mu_q_g_D2 = pylcp.hamiltonians.hyperfine_coupled(
        atom.state[0].J, atom.I, atom.state[0].gJ, atom.gI,
        atom.state[0].Ahfs / atom.state[2].gammaHz, Bhfs=0, Chfs=0, muB=1
    )
    H_e_D2, mu_q_e_D2 = pylcp.hamiltonians.hyperfine_coupled(
        atom.state[2].J, atom.I, atom.state[2].gJ, atom.gI,
        Ahfs=atom.state[2].Ahfs / atom.state[2].gammaHz,
        Bhfs=atom.state[2].Bhfs / atom.state[2].gammaHz, Chfs=0, muB=1
    )
    dijq_D2 = pylcp.hamiltonians.dqij_two_hyperfine_manifolds(
        atom.state[0].J, atom.state[2].J, atom.I
    )
    E_e_D2 = np.unique(np.diagonal(H_e_D2))
    E_g_D2 = np.unique(np.diagonal(H_g_D2))

    hamiltonian_D2 = pylcp.hamiltonian(H_g_D2, H_e_D2, mu_q_g_D2, mu_q_e_D2, dijq_D2)
    hamiltonian_D2.make_full_matrices()

    laserBeams_cooling_D2 = pylcp.conventional3DMOTBeams(
        s=s, delta=(E_e_D2[-1] - E_g_D2[-1]) + det
    )
    laserBeams_repump_D2 = pylcp.conventional3DMOTBeams(
        s=0.01 * s, delta=(E_e_D2[-2] - E_g_D2[-2])
    )
    laserBeams_D2 = laserBeams_cooling_D2 + laserBeams_repump_D2

    rate = pylcp.rateeq(
        laserBeams_D2,
        pylcp.quadrupoleMagneticField(alpha),
        hamiltonian_D2,
        include_mag_forces=False
    )
    return rate
# endregion


# region 2. DataFrame Fine-Structure Block Model (Default)
def build_dataframe_fine_block(det: float, s: float, alpha: float):
    """Builds DataFrame rateeq model using Fine-Structure blocks (default)."""
    frame = make_rubidium_frame(det, s, alpha)
    # Remove unused e1 state for D2-only comparison
    del frame.fine_states['e1']
    key_e1 = FineTransitionKey('g', 'e1')
    del frame.transitions[key_e1]
    del frame.lasers[key_e1]
    return frame.rateeq()
# endregion


# region 3. DataFrame Hyperfine Block Model (Forced Fallback)
def build_dataframe_hyperfine_block(det: float, s: float, alpha: float):
    """Builds DataFrame rateeq model forced into Hyperfine Block mode."""
    frame = make_rubidium_frame(det, s, alpha)
    del frame.fine_states['e1']
    key_e1 = FineTransitionKey('g', 'e1')
    del frame.transitions[key_e1]
    del frame.lasers[key_e1]
    # Force fallback to Hyperfine Block mode
    frame._has_custom_hyperfine_coupling = lambda: True
    return frame.rateeq()
# endregion


# region 4. Fine-Structure Block Model with Zeroed Inter-F mu_q
def build_dataframe_zero_interF_block(det: float, s: float, alpha: float):
    """Builds Fine-Structure block model with inter-F mu_q matrix elements zeroed out."""
    frame = make_rubidium_frame(det, s, alpha)
    del frame.fine_states['e1']
    key_e1 = FineTransitionKey('g', 'e1')
    del frame.transitions[key_e1]
    del frame.lasers[key_e1]

    def fine_ham_zero_interF(self):
        ham = pylcp.hamiltonian()
        ref_gamma = self._principal_gamma_and_energy()[0]
        for label, fine_state in self.fine_states.items():
            active_Fs = [F for F, mFs in fine_state.substates.items() if len(mFs) > 0]
            if not active_Fs:
                continue
            Fs_sorted = np.sort(active_Fs)
            basis = get_state_basis(fine_state, Fs_sorted)
            Fs_vec, mFs_vec = basis
            n = len(Fs_vec)

            H_0 = np.zeros((n, n), dtype=complex)
            for i in range(n):
                H_0[i, i] = hyperfine_correction(fine_state.J, self.I, Fs_vec[i], fine_state.hf_coefs) / ref_gamma
            ham.add_H_0_block(label, H_0)

            # Compute full mu_q and zero out inter-F off-diagonal elements
            mu_q = mu_q_coupled(basis, fine_state.gJ, self.gI, fine_state.J, self.I)
            for i in range(n):
                for j in range(n):
                    if Fs_vec[i] != Fs_vec[j]:
                        mu_q[:, i, j] = 0.0
            ham.add_mu_q_block(label, mu_q)

        for fine_trans, trans_data in self.transitions.items():
            l1, l2 = fine_trans.lower_label, fine_trans.upper_label
            if l1 not in self.fine_states or l2 not in self.fine_states:
                continue
            s1, s2 = self.fine_states[l1], self.fine_states[l2]
            b1 = get_state_basis(s1, np.sort([F for F, mFs in s1.substates.items() if len(mFs) > 0]))
            b2 = get_state_basis(s2, np.sort([F for F, mFs in s2.substates.items() if len(mFs) > 0]))
            Fs1, mFs1 = b1
            Fs2, mFs2 = b2
            d_q = np.zeros((3, len(Fs1), len(Fs2)))
            J1, J2 = s1.J, s2.J
            I = self.I
            for idx1 in range(len(Fs1)):
                for idx2 in range(len(Fs2)):
                    f1_val, f2_val = Fs1[idx1], Fs2[idx2]
                    mf1_val, mf2_val = mFs1[idx1], mFs2[idx2]
                    for q_idx, q in enumerate((-1.0, 0.0, 1.0)):
                        if mf2_val == mf1_val - q:
                            d_q[q_idx, idx1, idx2] = _d_q_matrix_element(J1, f1_val, mf1_val, J2, f2_val, mf2_val, q, I)
            d_q *= np.sqrt(2 * J2 + 1)
            transition_energy = np.abs(s1.energy - s2.energy)
            ham.add_d_q_block(l1, l2, d_q, k=transition_energy / ref_gamma, gamma=trans_data.gamma / ref_gamma)
        return ham

    frame._hamiltonian = types.MethodType(fine_ham_zero_interF, frame)
    return frame.rateeq()
# endregion


# region Force Profile Calculation Helper
def compute_force_profile(rate_model, X: np.ndarray, V: np.ndarray) -> np.ndarray:
    """Computes z-component force profile on a 2D position-velocity grid."""
    rate_model.generate_force_profile(
        [np.zeros(X.shape), np.zeros(X.shape), X],
        [np.zeros(V.shape), np.zeros(V.shape), V],
        name='Fz'
    )
    return rate_model.profile['Fz'].F[2]
# endregion


def run_comparative_analysis():
    x = np.arange(-5, 5.1, 0.2)
    v = np.arange(-5, 5.1, 0.2)
    dx = np.mean(np.diff(x))
    dv = np.mean(np.diff(v))
    X, V = np.meshgrid(x, v)

    print("--- Building Rate Equation Models ---")
    pylcp_ref_rate = build_pylcp_reference(det, s, alpha)
    fine_block_rate = build_dataframe_fine_block(det, s, alpha)
    hf_block_rate = build_dataframe_hyperfine_block(det, s, alpha)
    zero_interF_rate = build_dataframe_zero_interF_block(det, s, alpha)

    print("--- Computing 2D Force Profiles ---")
    prof_pylcp = compute_force_profile(pylcp_ref_rate, X, V)
    prof_fine = compute_force_profile(fine_block_rate, X, V)
    prof_hf = compute_force_profile(hf_block_rate, X, V)
    prof_zero = compute_force_profile(zero_interF_rate, X, V)

    print("\n=== COMPARISON SUMMARY VS PYLCP REFERENCE ===")
    models = {
        "Fine Block Method (Default)": prof_fine,
        "Fine Block (Zero Inter-F mu_q)": prof_zero,
        "Hyperfine Block Method (Fallback)": prof_hf,
    }
    for name, prof in models.items():
        diff = np.abs(prof - prof_pylcp)
        print(f"{name}:")
        print(f"  Max absolute diff:  {np.max(diff):.6e}")
        print(f"  Mean absolute diff: {np.mean(diff):.6e}")

    # Plotting results in 2x4 Grid
    plt.figure(figsize=(18, 9))
    extent = (np.amin(x) - dx / 2, np.amax(x) + dx / 2, np.amin(v) - dv / 2, np.amax(v) + dv / 2)

    plt.subplot(2, 4, 1)
    plt.title("1. PyLCP Reference")
    plt.ylabel(r'$v/(\Gamma/k)$')
    plt.xlabel(r'$x/\mu_B B\'/\hbar\Gamma$')
    plt.imshow(prof_pylcp, origin='lower', extent=extent, aspect='auto')
    plt.colorbar()

    plt.subplot(2, 4, 2)
    plt.title("2. Fine Block Method")
    plt.xlabel(r'$x/\mu_B B\'/\hbar\Gamma$')
    plt.imshow(prof_fine, origin='lower', extent=extent, aspect='auto')
    plt.colorbar()

    plt.subplot(2, 4, 3)
    plt.title("3. Fine Block (Zero Inter-F mu_q)")
    plt.xlabel(r'$x/\mu_B B\'/\hbar\Gamma$')
    plt.imshow(prof_zero, origin='lower', extent=extent, aspect='auto')
    plt.colorbar()

    plt.subplot(2, 4, 4)
    plt.title("4. Hyperfine Block Method")
    plt.xlabel(r'$x/\mu_B B\'/\hbar\Gamma$')
    plt.imshow(prof_hf, origin='lower', extent=extent, aspect='auto')
    plt.colorbar()

    plt.subplot(2, 4, 5)
    plt.title("Diff: Fine Block - PyLCP")
    plt.ylabel(r'$v/(\Gamma/k)$')
    plt.xlabel(r'$x/\mu_B B\'/\hbar\Gamma$')
    plt.imshow(prof_fine - prof_pylcp, origin='lower', extent=extent, aspect='auto')
    plt.colorbar()

    plt.subplot(2, 4, 6)
    plt.title("Diff: Zero Inter-F mu_q - PyLCP")
    plt.xlabel(r'$x/\mu_B B\'/\hbar\Gamma$')
    plt.imshow(prof_zero - prof_pylcp, origin='lower', extent=extent, aspect='auto')
    plt.colorbar()

    plt.subplot(2, 4, 7)
    plt.title("Diff: Hyperfine Block - PyLCP")
    plt.xlabel(r'$x/\mu_B B\'/\hbar\Gamma$')
    plt.imshow(prof_hf - prof_pylcp, origin='lower', extent=extent, aspect='auto')
    plt.colorbar()

    plt.subplot(2, 4, 8)
    plt.title("Diff: Zero Inter-F vs Hyperfine")
    plt.xlabel(r'$x/\mu_B B\'/\hbar\Gamma$')
    plt.imshow(prof_zero - prof_hf, origin='lower', extent=extent, aspect='auto')
    plt.colorbar()

    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    run_comparative_analysis()
