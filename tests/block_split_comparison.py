"""
block_split_comparison.py
--------------------------
Compares PyLCP performance between:
1. Current 2-Block Setup: Fine Structure manifolds ('g' and 'e2')
2. Hyperfine Partitioned Setup: Separate Hamiltonian blocks for each active F manifold
"""

import sys
import os
import time
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import pylcp
from pylcp_gui.dataframe.dataframe import (
    StateData, TransitionData, _d_q_matrix_element,
    mu_q_coupled, get_state_basis, hyperfine_correction
)
from testutil import make_rubidium_frame


def build_fine_blocks_sim(frame):
    """Method 1: Current 2-Block Fine-Structure Setup ('g' and 'e2')"""
    ham = frame._hamiltonian()
    lasers = frame._lasers()
    magfield = frame.magnetic_field
    obe = pylcp.obe(lasers, magfield, ham)
    rateeq = pylcp.rateeq(lasers, magfield, ham)
    return obe, rateeq


def build_hyperfine_partitioned_sim(frame):
    """Method 2: Hyperfine Partitioned Setup (Only active F blocks)"""
    ham = pylcp.hamiltonian()
    ref_gamma, ref_energy = frame._principal_gamma_and_energy()

    # 1. Build H_0 and mu_q per active hyperfine manifold
    hf_bases = {}
    for state_label, fine_state in frame.states.items():
        # Only process F manifolds that contain enabled substates
        active_Fs = [F for F, mFs in fine_state.substates.items() if len(mFs) > 0]
        if not active_Fs:
            continue

        Fs = np.asarray(active_Fs)
        hyperfine_energies = hyperfine_correction(fine_state.J, frame.I, Fs, fine_state.hf_coefs)
        sort = np.argsort(hyperfine_energies)
        Fs = Fs[sort]
        hyperfine_energies = hyperfine_energies[sort]

        for idx, F in enumerate(Fs):
            block_name = f"{state_label}_F{int(F)}"
            basis = get_state_basis(fine_state, [F])
            hf_bases[(state_label, F)] = (block_name, basis)

            # H_0 block (diagonal for single F)
            mF_count = len(fine_state.substates[F])
            H_0_diag = np.full(mF_count, hyperfine_energies[idx]) / ref_gamma
            ham.add_H_0_block(block_name, np.diag(H_0_diag))

            # mu_q block
            mu_q = mu_q_coupled(basis, fine_state.gJ, frame.gI, fine_state.J, frame.I)
            ham.add_mu_q_block(block_name, mu_q)

    # 2. Build d_q blocks between active hyperfine pairs
    for traverse_label_pair, trans_data in frame.transitions.items():
        l1, l2 = traverse_label_pair
        s1, s2 = frame.states[l1], frame.states[l2]
        J1, J2 = s1.J, s2.J
        trans_energy = np.abs(s1.energy - s2.energy)
        trans_gamma = trans_data.gamma

        active_Fs1 = [F for F, mFs in s1.substates.items() if len(mFs) > 0]
        active_Fs2 = [F for F, mFs in s2.substates.items() if len(mFs) > 0]

        for F1 in active_Fs1:
            for F2 in active_Fs2:
                b1_name, basis1 = hf_bases[(l1, F1)]
                b2_name, basis2 = hf_bases[(l2, F2)]
                Fs1, mFs1 = basis1
                Fs2, mFs2 = basis2

                d_q = np.zeros((3, len(Fs1), len(Fs2)))
                for idx1 in range(len(Fs1)):
                    for idx2 in range(len(Fs2)):
                        f1_val, f2_val, mf1_val, mf2_val = Fs1[idx1], Fs2[idx2], mFs1[idx1], mFs2[idx2]
                        for q_idx, q in enumerate((-1., 0., 1.)):
                            if mf2_val == mf1_val - q:
                                d_q[q_idx, idx1, idx2] = _d_q_matrix_element(J1, f1_val, mf1_val, J2, f2_val, mf2_val, q, frame.I)
                d_q *= np.sqrt(J2 * 2 + 1)
                ham.add_d_q_block(b1_name, b2_name, d_q, k=trans_energy / ref_gamma, gamma=trans_gamma / ref_gamma)

    # 3. Build lasers dictionary mapping to specific hf block pairs
    lasers_dict = {}
    for label_pair, laser_list_data in frame.lasers.items():
        l1, l2 = label_pair
        s1, s2 = frame.states[l1], frame.states[l2]
        sat_intensity = frame._saturation_intensity(label_pair)

        for laser_data in laser_list_data:
            freq = laser_data.freq
            delta = (freq - np.abs(s1.energy - s2.energy))
            beam = pylcp.infinitePlaneWaveBeam(
                laser_data.kvec * freq / ref_energy,
                laser_data.pol,
                laser_data.intensity / sat_intensity,
                delta / ref_gamma
            )

            # Match 87Rb transition: F=1 -> F'=2 (repump) vs F=2 -> F'=3 (cooler)
            if np.isclose(freq, s2.energy + hyperfine_correction(s2.J, frame.I, 2, s2.hf_coefs) - (s1.energy + hyperfine_correction(s1.J, frame.I, 1, s1.hf_coefs))):
                key = "g_F1->e2_F2"
            else:
                key = "g_F2->e2_F3"

            if key in ham.laser_keys:
                lasers_dict.setdefault(key, []).append(beam)

    final_lasers = {k: pylcp.laserBeams(v) for k, v in lasers_dict.items()}
    magfield = frame.magnetic_field
    obe = pylcp.obe(final_lasers, magfield, ham)
    rateeq = pylcp.rateeq(final_lasers, magfield, ham)
    return obe, rateeq


def main():
    print("==========================================================================")
    print("      PyLCP Benchmark: 2-Block Fine State vs. Hyperfine Partitioned")
    print("==========================================================================")
    
    # 1. Create standard 87Rb 3D MOT frame
    frame = make_rubidium_frame(det=-1.5, s=1.0, alpha=1.0)

    # Optionally prune uncoupled excited states (F'=0 and F'=1) to speed up simulation
    prune_uncoupled_states = True
    if prune_uncoupled_states:
        print("Pruning unused hyperfine manifolds (F'=0, F'=1 in excited state e2)...")
        frame.states.pop('e1')
        frame.transitions.pop(('g','e1'))
        frame.lasers.pop(('g','e1'))
        frame.states['e2'].substates[0.0] = []
        frame.states['e2'].substates[1.0] = []

    # --- Model Construction ---
    t0 = time.perf_counter()
    obe_fine, rateeq_fine = build_fine_blocks_sim(frame)
    t_build_fine = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    obe_hf, rateeq_hf = build_hyperfine_partitioned_sim(frame)
    t_build_hf = (time.perf_counter() - t0) * 1000

    print(f"\n[Model Build Times]")
    print(f"  • Fine-Structure (2 Blocks)      : {t_build_fine:.2f} ms")
    print(f"  • Hyperfine Partitioned          : {t_build_hf:.2f} ms")

    # --- Rate Equations Equilibrium Force Benchmark ---
    print("\n[Rate Equations Equilibrium Force Benchmark]")
    
    t0 = time.perf_counter()
    f_rateeq_fine = rateeq_fine.find_equilibrium_force()
    t_rateeq_fine = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    f_rateeq_hf = rateeq_hf.find_equilibrium_force()
    t_rateeq_hf = (time.perf_counter() - t0) * 1000

    print(f"  • Fine-Structure (2 Blocks)      : {t_rateeq_fine:.2f} ms | Force: {f_rateeq_fine[0]}")
    print(f"  • Hyperfine Partitioned          : {t_rateeq_hf:.2f} ms | Force: {f_rateeq_hf[0]}")

    # --- Optical Bloch Equations (OBE) Benchmark ---
    print("\n[Optical Bloch Equations (OBE) Benchmark]")
    
    t0 = time.perf_counter()
    f_obe_fine = obe_fine.find_equilibrium_force(deltat=5, itermax=2, Npts=15)
    t_obe_fine = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    f_obe_hf = obe_hf.find_equilibrium_force(deltat=5, itermax=2, Npts=15)
    t_obe_hf = (time.perf_counter() - t0) * 1000

    print(f"  • Fine-Structure (2 Blocks)      : {t_obe_fine:.2f} ms | Force: {f_obe_fine[0]}")
    print(f"  • Hyperfine Partitioned          : {t_obe_hf:.2f} ms | Force: {f_obe_hf[0]}")
    print("\n==========================================================================")


if __name__ == "__main__":
    main()
