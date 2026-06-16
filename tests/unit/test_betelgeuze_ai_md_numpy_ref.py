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
    build_bruteforce_neighbor_list,
    finite_difference_force,
    kabsch,
    summarize_trajectory,
)
from betelgeuze_ai_md.contracts import TrajectorySummary


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


def _invariance_state() -> CoarseState:
    x = np.array(
        [
            [0.0, 0.0, 0.0],
            [3.8, 0.2, 0.1],
            [1.8, 2.6, 0.2],
            [4.5, 2.8, -0.1],
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
        fixed=np.zeros(4, dtype=bool),
    )


def _pairwise_forcefield() -> CoarseForceField:
    return CoarseForceField(
        [
            SoftcoreContactTerm(r_switch=5.0, r_cut=6.0),
            ScreenedElectrostaticTerm(epsilon_r=20.0, kappa=0.15, r_switch=5.0, r_cut=6.0),
            DirectionalHbondTerm(),
            HydrophobicContactTerm(),
        ],
        force_clip=1_000_000.0,
    )


def _permuted_state(state: CoarseState, order: np.ndarray) -> CoarseState:
    return CoarseState(
        x=state.x[order],
        v=state.v[order],
        mass=state.mass[order],
        charge=state.charge[order],
        radius=state.radius[order],
        epsilon=state.epsilon[order],
        bead_type=state.bead_type[order],
        feature=state.feature[order],
        mol_id=state.mol_id[order],
        fixed=state.fixed[order],
    )


def _assert_force_matches_finite_difference(
    state: CoarseState,
    forcefield: CoarseForceField,
    neighbor_builder: NeighborListBuilder,
    *,
    rtol: float = 3e-3,
    atol: float = 3e-3,
) -> None:
    def energy_fn(x: np.ndarray) -> float:
        shifted = state.with_positions(x)
        return forcefield.compute(shifted, neighbor_builder.build(shifted.x)).energy

    result = forcefield.compute(state, neighbor_builder.build(state.x))
    finite_difference = finite_difference_force(energy_fn, state.x, h=1e-3)

    assert np.allclose(result.forces, finite_difference, rtol=rtol, atol=atol)
    assert np.isfinite(result.energy)


def _compute_forcefield(state: CoarseState, forcefield: CoarseForceField):
    neighbors = NeighborListBuilder(cutoff=6.0, skin=0.0).build(state.x)
    return forcefield.compute(state, neighbors)


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


def test_numpy_ref_forcefield_matches_bruteforce_neighbor_oracle() -> None:
    state = _tiny_state()
    forcefield = _pairwise_forcefield()
    cell_neighbors = NeighborListBuilder(cutoff=6.0, skin=0.0).build(state.x)
    brute_neighbors = build_bruteforce_neighbor_list(state.x, cutoff=6.0, skin=0.0)

    cell_result = forcefield.compute(state, cell_neighbors)
    brute_result = forcefield.compute(state, brute_neighbors)

    assert set(zip(cell_neighbors.pair_i.tolist(), cell_neighbors.pair_j.tolist())) == set(
        zip(brute_neighbors.pair_i.tolist(), brute_neighbors.pair_j.tolist())
    )
    assert np.isclose(cell_result.energy, brute_result.energy, rtol=1e-6, atol=1e-6)
    assert np.allclose(cell_result.forces, brute_result.forces, rtol=1e-6, atol=1e-6)


def test_numpy_ref_pairwise_forcefield_invariance_and_cutoff_stability() -> None:
    state = _invariance_state()
    forcefield = _pairwise_forcefield()
    base = _compute_forcefield(state, forcefield)

    shifted = state.with_positions(state.x + np.array([7.0, -3.0, 1.5], dtype=np.float32))
    shifted_result = _compute_forcefield(shifted, forcefield)
    assert np.isclose(shifted_result.energy, base.energy, rtol=1e-6, atol=1e-6)
    assert np.allclose(shifted_result.forces, base.forces, rtol=3e-6, atol=3e-6)

    theta = np.pi / 3.0
    rotation = np.array(
        [
            [np.cos(theta), -np.sin(theta), 0.0],
            [np.sin(theta), np.cos(theta), 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    rotated = state.with_positions(state.x @ rotation.T)
    rotated_result = _compute_forcefield(rotated, forcefield)
    assert np.isclose(rotated_result.energy, base.energy, rtol=1e-5, atol=1e-5)
    assert np.allclose(rotated_result.forces, base.forces @ rotation.T, rtol=1e-5, atol=1e-5)

    order = np.array([2, 0, 3, 1], dtype=np.int64)
    permuted = _permuted_state(state, order)
    permuted_result = _compute_forcefield(permuted, forcefield)
    inverse_order = np.argsort(order)
    assert np.isclose(permuted_result.energy, base.energy, rtol=1e-6, atol=1e-6)
    assert np.allclose(permuted_result.forces[inverse_order], base.forces, rtol=1e-6, atol=1e-6)

    cutoff_state = CoarseState(
        x=np.array([[0.0, 0.0, 0.0], [6.0, 0.0, 0.0]], dtype=np.float32),
        v=np.zeros((2, 3), dtype=np.float32),
        mass=np.ones(2, dtype=np.float32) * 12.0,
        charge=np.array([1.0, -1.0], dtype=np.float32),
        radius=np.ones(2, dtype=np.float32),
        epsilon=np.ones(2, dtype=np.float32) * 0.2,
        bead_type=np.array([BeadKind.LIGAND_CHARGED, BeadKind.LIGAND_CHARGED], dtype=np.int32),
        feature=np.zeros(2, dtype=np.int32),
        mol_id=np.array([0, 1], dtype=np.int32),
        fixed=np.zeros(2, dtype=bool),
    )
    cutoff_result = _compute_forcefield(cutoff_state, forcefield)
    assert np.isclose(cutoff_result.energy, 0.0, atol=1e-7)
    assert np.allclose(cutoff_result.forces, 0.0, atol=1e-7)

    stress_state = cutoff_state.with_positions(np.array([[0.0, 0.0, 0.0], [1e-4, 0.0, 0.0]], dtype=np.float32))
    stress_result = _compute_forcefield(stress_state, forcefield)
    assert np.isfinite(stress_result.energy)
    assert np.isfinite(stress_result.forces).all()


def test_screened_electrostatic_force_matches_finite_difference() -> None:
    state = CoarseState(
        x=np.array([[0.0, 0.0, 0.0], [5.5, 0.0, 0.0]], dtype=np.float32),
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


def test_softcore_contact_force_matches_finite_difference_in_switching_region() -> None:
    state = CoarseState(
        x=np.array([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]], dtype=np.float32),
        v=np.zeros((2, 3), dtype=np.float32),
        mass=np.ones(2, dtype=np.float32) * 12.0,
        charge=np.zeros(2, dtype=np.float32),
        radius=np.ones(2, dtype=np.float32),
        epsilon=np.ones(2, dtype=np.float32) * 0.2,
        bead_type=np.array([BeadKind.LIGAND_POLAR, BeadKind.LIGAND_POLAR], dtype=np.int32),
        feature=np.zeros(2, dtype=np.int32),
        mol_id=np.array([0, 1], dtype=np.int32),
        fixed=np.zeros(2, dtype=bool),
    )
    neighbor_builder = NeighborListBuilder(cutoff=5.0, skin=0.0)
    forcefield = CoarseForceField(
        [SoftcoreContactTerm(r_switch=2.5, r_cut=3.5)],
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


def test_numpy_ref_dynamics_summarizes_to_trajectory_contract() -> None:
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

    summary = summarize_trajectory(trajectory, state, ligand_mol_id=1)

    assert isinstance(summary, TrajectorySummary)
    assert summary.frame_count == len(trajectory.frames)
    assert len(summary.energy_trace) == summary.frame_count
    assert len(summary.contact_trace) == summary.frame_count
    assert 0.0 <= summary.stability_score <= 1.0
    assert summary.mean_min_distance > 0.0
    assert 0.0 <= summary.escape_fraction <= 1.0
    assert 0.0 <= summary.clash_fraction <= 1.0
    assert len(summary.contract_hash()) == 64


def test_directional_hbond_force_matches_finite_difference() -> None:
    state = CoarseState(
        x=np.array([[0.0, 0.0, 0.0], [3.2, 0.0, 0.0]], dtype=np.float32),
        v=np.zeros((2, 3), dtype=np.float32),
        mass=np.ones(2, dtype=np.float32) * 12.0,
        charge=np.zeros(2, dtype=np.float32),
        radius=np.ones(2, dtype=np.float32),
        epsilon=np.ones(2, dtype=np.float32) * 0.2,
        bead_type=np.array([BeadKind.PROTEIN_HB_DONOR, BeadKind.LIGAND_POLAR], dtype=np.int32),
        feature=np.array([FEATURE_DONOR, FEATURE_ACCEPTOR], dtype=np.int32),
        mol_id=np.array([0, 1], dtype=np.int32),
        fixed=np.zeros(2, dtype=bool),
    )

    _assert_force_matches_finite_difference(
        state,
        CoarseForceField([DirectionalHbondTerm()], force_clip=1_000_000.0),
        NeighborListBuilder(cutoff=5.0, skin=0.0),
    )


def test_hydrophobic_contact_force_matches_finite_difference() -> None:
    state = CoarseState(
        x=np.array([[0.0, 0.0, 0.0], [4.2, 0.0, 0.0]], dtype=np.float32),
        v=np.zeros((2, 3), dtype=np.float32),
        mass=np.ones(2, dtype=np.float32) * 12.0,
        charge=np.zeros(2, dtype=np.float32),
        radius=np.ones(2, dtype=np.float32),
        epsilon=np.ones(2, dtype=np.float32) * 0.2,
        bead_type=np.array([BeadKind.LIGAND_HYDROPHOBE, BeadKind.LIGAND_HYDROPHOBE], dtype=np.int32),
        feature=np.array([FEATURE_HYDROPHOBE, FEATURE_HYDROPHOBE], dtype=np.int32),
        mol_id=np.array([0, 1], dtype=np.int32),
        fixed=np.zeros(2, dtype=bool),
    )

    _assert_force_matches_finite_difference(
        state,
        CoarseForceField([HydrophobicContactTerm()], force_clip=1_000_000.0),
        NeighborListBuilder(cutoff=6.0, skin=0.0),
    )


def test_pocket_wall_force_matches_finite_difference() -> None:
    state = CoarseState(
        x=np.array([[0.0, 0.0, 0.0], [8.0, 0.0, 0.0], [8.0, 2.0, 0.0]], dtype=np.float32),
        v=np.zeros((3, 3), dtype=np.float32),
        mass=np.ones(3, dtype=np.float32) * 12.0,
        charge=np.zeros(3, dtype=np.float32),
        radius=np.ones(3, dtype=np.float32),
        epsilon=np.ones(3, dtype=np.float32) * 0.2,
        bead_type=np.array([BeadKind.PROTEIN_CA, BeadKind.LIGAND_POLAR, BeadKind.LIGAND_POLAR], dtype=np.int32),
        feature=np.zeros(3, dtype=np.int32),
        mol_id=np.array([0, 1, 1], dtype=np.int32),
        fixed=np.zeros(3, dtype=bool),
    )

    _assert_force_matches_finite_difference(
        state,
        CoarseForceField(
            [PocketWallTerm(np.array([0.0, 0.0, 0.0], dtype=np.float32), pocket_radius=5.0, ligand_mol_id=1)],
            force_clip=1_000_000.0,
        ),
        NeighborListBuilder(cutoff=10.0, skin=0.0),
        atol=1e-3,
    )


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
