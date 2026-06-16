from __future__ import annotations

import numpy as np

from betelgeuze_ai_md.coarse_md.numpy_ref import (
    FEATURE_ACCEPTOR,
    FEATURE_DONOR,
    FEATURE_HYDROPHOBE,
    BeadKind,
    CoarseForceField,
    CoarseState,
    DirectionalHbondTerm,
    DynamicsEngine,
    HydrophobicContactTerm,
    IntegratorConfig,
    NeighborListBuilder,
    PocketWallTerm,
    ScreenedElectrostaticTerm,
    SoftcoreContactTerm,
    finite_difference_force,
    kabsch,
)


def _tiny_state() -> CoarseState:
    x = np.array(
        [
            [0.0, 0.0, 0.0],
            [4.0, 0.0, 0.0],
            [2.0, 1.0, 0.0],
            [2.8, 1.2, 0.0],
        ],
        dtype=np.float32,
    )
    return CoarseState(
        x=x,
        v=np.zeros_like(x, dtype=np.float32),
        mass=np.ones(4, dtype=np.float32) * 12.0,
        charge=np.array([-0.3, 0.1, 0.2, -0.2], dtype=np.float32),
        radius=np.ones(4, dtype=np.float32) * 1.8,
        epsilon=np.ones(4, dtype=np.float32) * 0.2,
        bead_type=np.array(
            [
                BeadKind.PROTEIN_CA,
                BeadKind.PROTEIN_SC,
                BeadKind.LIGAND_POLAR,
                BeadKind.LIGAND_HYDROPHOBE,
            ],
            dtype=np.int32,
        ),
        feature=np.array(
            [FEATURE_ACCEPTOR, FEATURE_HYDROPHOBE, FEATURE_DONOR, FEATURE_HYDROPHOBE],
            dtype=np.int32,
        ),
        mol_id=np.array([0, 0, 1, 1], dtype=np.int32),
        fixed=np.array([True, True, False, False], dtype=bool),
    )


def test_numpy_ref_neighbor_list_matches_bruteforce_pairs() -> None:
    coords = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [3.0, 0.0, 0.0],
            [0.0, 2.4, 0.0],
            [6.0, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    builder = NeighborListBuilder(cutoff=2.5, skin=0.0)
    observed = builder.build(coords)
    observed_pairs = set(zip(observed.pair_i.tolist(), observed.pair_j.tolist()))
    expected_pairs = {
        (i, j)
        for i in range(coords.shape[0])
        for j in range(i + 1, coords.shape[0])
        if float(np.linalg.norm(coords[i] - coords[j])) <= 2.5
    }

    assert observed_pairs == expected_pairs
    assert builder.needs_rebuild(coords) is False
    moved = coords.copy()
    moved[0, 0] += 0.1
    assert builder.needs_rebuild(moved) is True


def test_screened_electrostatic_force_matches_finite_difference() -> None:
    state = CoarseState(
        x=np.array([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]], dtype=np.float32),
        v=np.zeros((2, 3), dtype=np.float32),
        mass=np.ones(2, dtype=np.float32) * 12.0,
        charge=np.array([1.0, -1.0], dtype=np.float32),
        radius=np.ones(2, dtype=np.float32) * 1.6,
        epsilon=np.zeros(2, dtype=np.float32),
        bead_type=np.array([BeadKind.LIGAND_CHARGED, BeadKind.LIGAND_CHARGED], dtype=np.int32),
        feature=np.zeros(2, dtype=np.int32),
        mol_id=np.array([0, 1], dtype=np.int32),
        fixed=np.zeros(2, dtype=bool),
    )
    neighbor_builder = NeighborListBuilder(cutoff=6.0, skin=0.0)
    forcefield = CoarseForceField(
        [ScreenedElectrostaticTerm(epsilon_r=20.0, kappa=0.15, r_switch=5.0, r_cut=6.0)],
        force_clip=1_000_000.0,
    )

    def energy_fn(x: np.ndarray) -> float:
        shifted = state.with_positions(x)
        return forcefield.compute(shifted, neighbor_builder.build(shifted.x)).energy

    result = forcefield.compute(state, neighbor_builder.build(state.x))
    finite_difference = finite_difference_force(energy_fn, state.x, h=1e-3)

    assert np.allclose(result.forces, finite_difference, rtol=3e-3, atol=3e-3)
    assert np.isfinite(result.energy)


def test_numpy_ref_dynamics_runs_finite_tiny_trajectory() -> None:
    state = _tiny_state()
    forcefield = CoarseForceField(
        [
            SoftcoreContactTerm(),
            ScreenedElectrostaticTerm(),
            DirectionalHbondTerm(),
            HydrophobicContactTerm(),
            PocketWallTerm(np.array([2.0, 0.5, 0.0], dtype=np.float32), pocket_radius=5.0, ligand_mol_id=1),
        ],
        force_clip=250.0,
    )
    engine = DynamicsEngine(forcefield, NeighborListBuilder(cutoff=10.0, skin=2.0))
    trajectory = engine.run(state, IntegratorConfig(max_steps=12, save_every=3, damping=0.95))

    assert [frame.step for frame in trajectory.frames] == [0, 3, 6, 9]
    assert all(np.isfinite(frame.energy) for frame in trajectory.frames)
    assert all(np.isfinite(frame.x).all() for frame in trajectory.frames)
    assert np.allclose(trajectory.frames[0].x[:2], state.x[:2])


def test_kabsch_aligns_rotated_translated_points() -> None:
    mobile = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float32,
    )
    theta = np.pi / 2.0
    rotation_true = np.array(
        [
            [np.cos(theta), -np.sin(theta), 0.0],
            [np.sin(theta), np.cos(theta), 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    translation_true = np.array([3.0, -2.0, 0.5], dtype=np.float32)
    target = mobile @ rotation_true.T + translation_true

    rotation, translation = kabsch(mobile, target)
    aligned = (rotation @ mobile.T).T + translation

    assert np.allclose(aligned, target, atol=1e-5)
