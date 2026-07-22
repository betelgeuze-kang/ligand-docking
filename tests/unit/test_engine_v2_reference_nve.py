from __future__ import annotations

from dataclasses import replace
import json

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.molecular import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    atomic_number_for_element,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics import (  # noqa: E402
    MAX_REFERENCE_NVE_RETAINED_FRAMES,
    REFERENCE_NVE_SCIENTIFIC_BLOCKERS,
    AtomNonbondedParameter,
    HarmonicBondParameter,
    ReferenceEwaldConfig,
    ReferenceForceFieldParameters,
    ReferenceNVECheckpoint,
    ReferenceNVEConfig,
    ReferenceNVEError,
    ReferenceSHAKERATTLEConfig,
    ReferenceSHAKERATTLEDistanceConstraint,
    ReferenceSHAKERATTLEError,
    project_reference_rattle_velocities,
    project_reference_shake_positions,
    resume_reference_nve,
    run_reference_nve,
)


def _system(
    coordinates: tuple[tuple[float, float, float], ...],
    *,
    masses: tuple[float | None, ...] | None = None,
    bonded: bool = False,
    cell: UnitCell | None = None,
) -> AllAtomSystem:
    active_masses = masses or tuple(12.0 for _ in coordinates)
    atoms = tuple(
        Atom(
            index=index,
            name=f"C{index + 1}",
            element="C",
            atomic_number=atomic_number_for_element("C"),
            residue_index=0,
            partial_charge_e=0.0,
            mass_da=active_masses[index],
        )
        for index in range(len(coordinates))
    )
    bonds = (Bond(index=0, atom_i=0, atom_j=1),) if bonded else ()
    return AllAtomSystem(
        system_id="reference-nve-unit-system",
        atoms=atoms,
        bonds=bonds,
        residues=(
            Residue(
                index=0,
                name="MOL",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
                entity_type="non-polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor((coordinates,), dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit-test"),
        cell=cell,
    )


def _parameters(
    system: AllAtomSystem,
    *,
    equilibrium_angstrom: float = 1.0,
    force_constant: float = 100.0,
    charges: tuple[float, ...] | None = None,
) -> ReferenceForceFieldParameters:
    active_charges = charges or tuple(0.0 for _ in system.atoms)
    bonds = tuple(
        HarmonicBondParameter(
            atom_i=bond.atom_i,
            atom_j=bond.atom_j,
            equilibrium_angstrom=equilibrium_angstrom,
            force_constant_kcal_per_mol_angstrom2=force_constant,
        )
        for bond in system.bonds
    )
    return ReferenceForceFieldParameters(
        parameter_set_id="reference-nve-unit-parameters",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=tuple(
            AtomNonbondedParameter(
                atom_index=atom.index,
                sigma_angstrom=3.4,
                epsilon_kcal_per_mol=0.0,
                charge_e=active_charges[atom.index],
            )
            for atom in system.atoms
        ),
        bonds=bonds,
        excluded_pairs=tuple((bond.atom_i, bond.atom_j) for bond in system.bonds),
        cutoff_angstrom=4.0 if system.cell is not None else 10.0,
        switch_start_angstrom=3.0 if system.cell is not None else 8.0,
    )


def test_force_free_particle_follows_ballistic_nve_trajectory() -> None:
    system = _system(((0.0, 0.0, 0.0),))
    velocity = torch.tensor([[[1.0, -2.0, 0.5]]], dtype=torch.float64)
    result = run_reference_nve(
        system,
        _parameters(system),
        velocity,
        steps=10,
        config=ReferenceNVEConfig(timestep_ps=0.01, trajectory_stride=4),
    )

    torch.testing.assert_close(
        result.system.coordinates,
        torch.tensor([[[0.1, -0.2, 0.05]]], dtype=torch.float64),
        atol=1.0e-15,
        rtol=0.0,
    )
    assert torch.equal(result.checkpoint.velocities_angstrom_per_ps, velocity)
    assert [frame.step for frame in result.frames] == [0, 4, 8, 10]
    assert result.checkpoint.evaluated_frame_count == 11
    assert result.energy_drift_kcal_per_mol == 0.0
    assert result.max_abs_energy_drift_kcal_per_mol == 0.0
    assert result.scientific_blockers == REFERENCE_NVE_SCIENTIFIC_BLOCKERS
    assert "shake_rattle_constraints_not_implemented" not in result.scientific_blockers
    assert (
        "shake_rattle_reference_path_not_independently_validated"
        in result.scientific_blockers
    )
    assert result.claim_safe is False
    assert result.to_dict()["claim_safe"] is False


def test_full_orthorhombic_pbc_wraps_coordinates_each_step() -> None:
    cell = UnitCell.orthorhombic(
        (10.0, 10.0, 10.0),
        dtype=torch.float64,
    )
    system = _system(((9.9, 0.0, 0.0),), cell=cell)
    result = run_reference_nve(
        system,
        _parameters(system),
        torch.tensor([[[2.0, 0.0, 0.0]]], dtype=torch.float64),
        steps=1,
        config=ReferenceNVEConfig(timestep_ps=0.1),
    )

    assert result.system.coordinates[0, 0, 0].item() == pytest.approx(
        0.1,
        abs=1.0e-14,
    )
    assert result.energy_drift_kcal_per_mol == 0.0


def test_harmonic_dimer_has_bounded_velocity_verlet_energy_drift() -> None:
    system = _system(((-0.55, 0.0, 0.0), (0.55, 0.0, 0.0)), bonded=True)
    result = run_reference_nve(
        system,
        _parameters(system),
        torch.zeros((1, 2, 3), dtype=torch.float64),
        steps=200,
        config=ReferenceNVEConfig(timestep_ps=0.0001, trajectory_stride=20),
    )

    assert result.initial_total_energy_kcal_per_mol == pytest.approx(0.5)
    assert result.max_abs_energy_drift_kcal_per_mol < 1.0e-4
    assert result.checkpoint.evaluated_frame_count == 201


def test_checkpoint_round_trip_and_resume_are_bit_exact() -> None:
    system = _system(((-0.55, 0.0, 0.0), (0.55, 0.0, 0.0)), bonded=True)
    parameters = _parameters(system)
    velocities = torch.tensor(
        [[[0.1, 0.0, 0.0], [-0.1, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    config = ReferenceNVEConfig(timestep_ps=0.0001, trajectory_stride=3)

    uninterrupted = run_reference_nve(
        system,
        parameters,
        velocities,
        steps=12,
        config=config,
    )
    paused = run_reference_nve(
        system,
        parameters,
        velocities,
        steps=5,
        config=config,
    )
    raw = paused.checkpoint.to_json_bytes()
    restored = ReferenceNVECheckpoint.from_json_bytes(raw)
    assert restored.to_json_bytes() == raw
    assert restored.checkpoint_sha256 == paused.checkpoint.checkpoint_sha256

    resumed = resume_reference_nve(
        system,
        parameters,
        restored,
        additional_steps=7,
    )
    assert torch.equal(
        resumed.checkpoint.coordinates,
        uninterrupted.checkpoint.coordinates,
    )
    assert torch.equal(
        resumed.checkpoint.velocities_angstrom_per_ps,
        uninterrupted.checkpoint.velocities_angstrom_per_ps,
    )
    assert resumed.checkpoint.current_total_energy_kcal_per_mol.hex() == (
        uninterrupted.checkpoint.current_total_energy_kcal_per_mol.hex()
    )
    assert resumed.checkpoint.trajectory_head_sha256 == (
        uninterrupted.checkpoint.trajectory_head_sha256
    )
    assert resumed.checkpoint.checkpoint_sha256 == (
        uninterrupted.checkpoint.checkpoint_sha256
    )
    assert resumed.checkpoint.evaluated_frame_count == 13


def test_periodic_direct_ewald_nve_is_bound_into_checkpoint_and_restart() -> None:
    cell = UnitCell.orthorhombic(
        (10.0, 10.0, 10.0),
        dtype=torch.float64,
    )
    system = _system(
        ((2.0, 5.0, 5.0), (5.0, 5.0, 5.0)),
        cell=cell,
    )
    parameters = _parameters(system, charges=(0.25, -0.25))
    velocities = torch.tensor(
        [[[0.0, 0.01, 0.0], [0.0, -0.01, 0.0]]],
        dtype=torch.float64,
    )
    ewald = ReferenceEwaldConfig(
        alpha_per_angstrom=0.4,
        reciprocal_max_indices=(4, 4, 4),
    )
    config = ReferenceNVEConfig(
        timestep_ps=1.0e-5,
        trajectory_stride=2,
        ewald_config=ewald,
    )

    uninterrupted = run_reference_nve(
        system,
        parameters,
        velocities,
        steps=6,
        config=config,
    )
    paused = run_reference_nve(
        system,
        parameters,
        velocities,
        steps=2,
        config=config,
    )
    restored = ReferenceNVECheckpoint.from_json_bytes(
        paused.checkpoint.to_json_bytes()
    )
    resumed = resume_reference_nve(
        system,
        parameters,
        restored,
        additional_steps=4,
    )

    assert config.electrostatics_mode == "neutral_direct_ewald_v1"
    assert ReferenceNVEConfig.from_dict(config.to_dict()) == config
    assert restored.config.ewald_config == ewald
    assert uninterrupted.to_dict()["electrostatics_mode"] == (
        "neutral_direct_ewald_v1"
    )
    assert uninterrupted.to_dict()["ewald_config_fingerprint_sha256"] == (
        ewald.fingerprint_sha256
    )
    assert uninterrupted.max_abs_energy_drift_kcal_per_mol < 1.0e-6
    assert torch.equal(
        resumed.checkpoint.coordinates,
        uninterrupted.checkpoint.coordinates,
    )
    assert torch.equal(
        resumed.checkpoint.velocities_angstrom_per_ps,
        uninterrupted.checkpoint.velocities_angstrom_per_ps,
    )
    assert resumed.checkpoint.checkpoint_sha256 == (
        uninterrupted.checkpoint.checkpoint_sha256
    )
    assert resumed.checkpoint.trajectory_head_sha256 == (
        uninterrupted.checkpoint.trajectory_head_sha256
    )


def test_direct_ewald_nve_fails_closed_for_nonperiodic_or_net_charged_input() -> None:
    nonperiodic = _system(((0.0, 0.0, 0.0), (3.0, 0.0, 0.0)))
    config = ReferenceNVEConfig(ewald_config=ReferenceEwaldConfig())
    with pytest.raises(ReferenceNVEError, match="fully periodic"):
        run_reference_nve(
            nonperiodic,
            _parameters(nonperiodic, charges=(0.5, -0.5)),
            torch.zeros((1, 2, 3), dtype=torch.float64),
            steps=1,
            config=config,
        )

    cell = UnitCell.orthorhombic(
        (10.0, 10.0, 10.0),
        dtype=torch.float64,
    )
    charged = _system(
        ((2.0, 5.0, 5.0), (5.0, 5.0, 5.0)),
        cell=cell,
    )
    with pytest.raises(ReferenceNVEError, match="net charge"):
        run_reference_nve(
            charged,
            _parameters(charged, charges=(0.5, -0.4)),
            torch.zeros((1, 2, 3), dtype=torch.float64),
            steps=1,
            config=config,
        )


def test_checkpoint_transport_and_restart_identity_fail_closed() -> None:
    system = _system(((0.0, 0.0, 0.0),))
    parameters = _parameters(system)
    result = run_reference_nve(
        system,
        parameters,
        torch.zeros((1, 1, 3), dtype=torch.float64),
        steps=2,
    )
    raw = result.checkpoint.to_json_bytes()
    tampered = raw.replace(
        result.checkpoint.checkpoint_sha256.encode("ascii"),
        b"0" * 64,
    )

    with pytest.raises(ReferenceNVEError, match="self-digest mismatch"):
        ReferenceNVECheckpoint.from_json_bytes(tampered)
    with pytest.raises(ReferenceNVEError, match="transport is not canonical"):
        ReferenceNVECheckpoint.from_json_bytes(raw.rstrip(b"\n"))

    foreign_runtime = replace(
        result.checkpoint,
        torch_version="0.0.0-foreign-runtime",
    )
    parsed_foreign_runtime = ReferenceNVECheckpoint.from_json_bytes(
        foreign_runtime.to_json_bytes()
    )
    with pytest.raises(ReferenceNVEError, match="provenance mismatch"):
        resume_reference_nve(
            system,
            parameters,
            parsed_foreign_runtime,
            additional_steps=1,
        )

    different_source = replace(
        system,
        coordinates=system.coordinates + torch.tensor([[[0.1, 0.0, 0.0]]]),
    )
    with pytest.raises(ReferenceNVEError, match="provenance mismatch"):
        resume_reference_nve(
            different_source,
            parameters,
            result.checkpoint,
            additional_steps=1,
        )
    different_parameters = replace(parameters, parameter_set_version="1.0.1")
    with pytest.raises(ReferenceNVEError, match="provenance mismatch"):
        resume_reference_nve(
            system,
            different_parameters,
            result.checkpoint,
            additional_steps=1,
        )


def test_nve_admission_and_retained_frame_capacity_fail_closed() -> None:
    missing_mass = _system(((0.0, 0.0, 0.0),), masses=(None,))
    with pytest.raises(ReferenceNVEError, match="missing mass_da"):
        run_reference_nve(
            missing_mass,
            _parameters(missing_mass),
            torch.zeros((1, 1, 3), dtype=torch.float64),
            steps=1,
        )

    system = _system(((0.0, 0.0, 0.0),))
    with pytest.raises(ReferenceNVEError, match="CPU float64"):
        run_reference_nve(
            system,
            _parameters(system),
            torch.zeros((1, 1, 3), dtype=torch.float32),
            steps=1,
        )
    with pytest.raises(ReferenceNVEError, match="retained trajectory-frame capacity"):
        run_reference_nve(
            system,
            _parameters(system),
            torch.zeros((1, 1, 3), dtype=torch.float64),
            steps=MAX_REFERENCE_NVE_RETAINED_FRAMES,
            config=ReferenceNVEConfig(trajectory_stride=1),
        )

    partial_cell = UnitCell.orthorhombic(
        (10.0, 10.0, 10.0),
        dtype=torch.float64,
        periodic=(True, True, False),
    )
    partial_periodic = _system(((0.0, 0.0, 0.0),), cell=partial_cell)
    with pytest.raises(ReferenceNVEError, match="all three dimensions"):
        run_reference_nve(
            partial_periodic,
            _parameters(partial_periodic),
            torch.zeros((1, 1, 3), dtype=torch.float64),
            steps=1,
        )

    triclinic_cell = UnitCell(
        vectors=torch.tensor(
            [[10.0, 1.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]],
            dtype=torch.float64,
        )
    )
    triclinic = _system(((0.0, 0.0, 0.0),), cell=triclinic_cell)
    with pytest.raises(ReferenceNVEError, match="orthorhombic"):
        run_reference_nve(
            triclinic,
            _parameters(triclinic),
            torch.zeros((1, 1, 3), dtype=torch.float64),
            steps=1,
        )


def test_reference_nve_symbols_are_reexported_by_physics_package() -> None:
    from betelgeuze_engine_v2 import physics
    from betelgeuze_engine_v2.physics.reference_nve import __all__ as nve_exports

    assert set(nve_exports) <= set(physics.__all__)


def _distance_constraint(
    *,
    target: float = 1.0,
    tolerance: float = 1.0e-10,
) -> ReferenceSHAKERATTLEConfig:
    return ReferenceSHAKERATTLEConfig(
        constraints=(
            ReferenceSHAKERATTLEDistanceConstraint(
                atom_i=0,
                atom_j=1,
                target_distance_angstrom=target,
                tolerance_angstrom=tolerance,
            ),
        ),
    )


def test_shake_and_rattle_use_inverse_mass_weighting_and_preserve_momentum() -> None:
    system = _system(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        masses=(1.0, 3.0),
    )
    masses = torch.tensor((1.0, 3.0), dtype=torch.float64)
    predicted = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    constraint_config = _distance_constraint(tolerance=1.0e-12)
    before_center_of_mass = (
        predicted * masses.view(1, -1, 1)
    ).sum(dim=1) / masses.sum()

    shake = project_reference_shake_positions(
        system,
        system.coordinates,
        predicted,
        masses,
        constraint_config,
    )
    assert shake.converged is True
    assert shake.iteration_count > 0
    assert shake.max_abs_residual_angstrom <= 1.0e-12
    assert shake.to_dict()["config_fingerprint_sha256"] == (
        constraint_config.fingerprint_sha256
    )
    assert shake.scientifically_validated is False
    assert shake.to_dict()["claim_safe"] is False
    after_center_of_mass = (
        shake.coordinates * masses.view(1, -1, 1)
    ).sum(dim=1) / masses.sum()
    assert torch.equal(after_center_of_mass, before_center_of_mass)
    first_correction = shake.coordinates[0, 0, 0] - predicted[0, 0, 0]
    second_correction = shake.coordinates[0, 1, 0] - predicted[0, 1, 0]
    assert first_correction.item() == pytest.approx(
        -3.0 * second_correction.item(),
        abs=1.0e-15,
    )

    velocities = torch.tensor(
        [[[-0.2, 0.0, 0.0], [0.1, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    momentum_before = (velocities * masses.view(1, -1, 1)).sum(dim=1)
    rattle = project_reference_rattle_velocities(
        system,
        shake.coordinates,
        velocities,
        masses,
        constraint_config,
    )
    assert rattle.converged is True
    assert rattle.iteration_count == 1
    assert rattle.max_abs_residual_angstrom_per_ps <= 1.0e-10
    momentum_after = (
        rattle.velocities_angstrom_per_ps * masses.view(1, -1, 1)
    ).sum(dim=1)
    torch.testing.assert_close(
        momentum_after,
        momentum_before,
        atol=1.0e-16,
        rtol=0.0,
    )


def test_constrained_nve_records_residuals_and_iteration_counts() -> None:
    system = _system(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        masses=(1.0, 3.0),
    )
    result = run_reference_nve(
        system,
        _parameters(system),
        torch.tensor(
            [[[0.0, 1.0, 0.0], [0.0, 0.0, 0.0]]],
            dtype=torch.float64,
        ),
        steps=20,
        config=ReferenceNVEConfig(timestep_ps=0.001, trajectory_stride=5),
        constraint_config=_distance_constraint(),
    )

    delta = result.system.coordinates[:, 0] - result.system.coordinates[:, 1]
    assert torch.linalg.vector_norm(delta).item() == pytest.approx(
        1.0,
        abs=1.0e-10,
    )
    relative_velocity = (
        result.checkpoint.velocities_angstrom_per_ps[0, 0]
        - result.checkpoint.velocities_angstrom_per_ps[0, 1]
    )
    assert abs(float(torch.dot(delta[0], relative_velocity).item())) <= 1.0e-10
    assert result.max_abs_position_constraint_residual_angstrom <= 1.0e-10
    assert (
        result.max_abs_velocity_constraint_residual_angstrom_per_ps <= 1.0e-10
    )
    assert result.cumulative_shake_iteration_count > 0
    assert result.cumulative_rattle_iteration_count > 0
    assert result.max_abs_energy_drift_kcal_per_mol < 1.0e-12
    assert result.to_dict()["constraint_count"] == 1


def test_coupled_constraints_converge_and_preserve_mass_weighted_invariants() -> None:
    system = _system(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        masses=(16.0, 1.0, 1.0),
    )
    masses = torch.tensor((16.0, 1.0, 1.0), dtype=torch.float64)
    config = ReferenceSHAKERATTLEConfig(
        constraints=(
            ReferenceSHAKERATTLEDistanceConstraint(0, 2, 1.0),
            ReferenceSHAKERATTLEDistanceConstraint(0, 1, 1.0),
        )
    )
    predicted = torch.tensor(
        [[[0.01, -0.02, 0.0], [1.2, 0.1, 0.0], [-0.1, 0.8, 0.0]]],
        dtype=torch.float64,
    )
    center_before = (predicted * masses.view(1, -1, 1)).sum(dim=1)
    shake = project_reference_shake_positions(
        system,
        system.coordinates,
        predicted,
        masses,
        config,
    )
    assert shake.converged is True
    assert shake.iteration_count > 1
    center_after = (shake.coordinates * masses.view(1, -1, 1)).sum(dim=1)
    torch.testing.assert_close(center_after, center_before, atol=1.0e-14, rtol=0.0)
    for atom_j in (1, 2):
        distance = torch.linalg.vector_norm(
            shake.coordinates[0, 0] - shake.coordinates[0, atom_j]
        )
        assert distance.item() == pytest.approx(1.0, abs=1.0e-8)

    velocities = torch.tensor(
        [[[0.2, 0.1, 0.0], [-0.3, 0.4, 0.0], [0.5, -0.2, 0.0]]],
        dtype=torch.float64,
    )
    momentum_before = (velocities * masses.view(1, -1, 1)).sum(dim=1)
    rattle = project_reference_rattle_velocities(
        system,
        shake.coordinates,
        velocities,
        masses,
        config,
    )
    assert rattle.converged is True
    assert rattle.iteration_count > 1
    momentum_after = (
        rattle.velocities_angstrom_per_ps * masses.view(1, -1, 1)
    ).sum(dim=1)
    torch.testing.assert_close(
        momentum_after,
        momentum_before,
        atol=1.0e-14,
        rtol=0.0,
    )


def test_constrained_nve_uses_minimum_image_geometry_across_pbc() -> None:
    cell = UnitCell.orthorhombic(
        (10.0, 10.0, 10.0),
        dtype=torch.float64,
    )
    system = _system(
        ((9.8, 0.0, 0.0), (0.2, 0.0, 0.0)),
        masses=(1.0, 3.0),
        cell=cell,
    )
    result = run_reference_nve(
        system,
        _parameters(system),
        torch.tensor(
            [[[0.0, 1.0, 0.0], [0.0, 0.0, 0.0]]],
            dtype=torch.float64,
        ),
        steps=20,
        config=ReferenceNVEConfig(timestep_ps=0.001),
        constraint_config=_distance_constraint(target=0.4),
    )

    delta = result.system.coordinates[:, 0] - result.system.coordinates[:, 1]
    lengths = torch.tensor((10.0, 10.0, 10.0), dtype=torch.float64)
    delta = delta - torch.round(delta / lengths) * lengths
    assert torch.linalg.vector_norm(delta).item() == pytest.approx(
        0.4,
        abs=1.0e-10,
    )
    assert bool((result.system.coordinates >= 0.0).all().item())
    assert bool((result.system.coordinates < 10.0).all().item())


def test_constrained_checkpoint_round_trip_and_resume_are_bit_exact() -> None:
    system = _system(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        masses=(1.0, 3.0),
    )
    parameters = _parameters(system)
    velocities = torch.tensor(
        [[[0.0, 1.0, 0.0], [0.0, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    config = ReferenceNVEConfig(timestep_ps=0.001, trajectory_stride=3)
    constraint_config = _distance_constraint()
    uninterrupted = run_reference_nve(
        system,
        parameters,
        velocities,
        steps=12,
        config=config,
        constraint_config=constraint_config,
    )
    paused = run_reference_nve(
        system,
        parameters,
        velocities,
        steps=5,
        config=config,
        constraint_config=constraint_config,
    )
    raw = paused.checkpoint.to_json_bytes()
    restored = ReferenceNVECheckpoint.from_json_bytes(raw)
    assert restored.to_json_bytes() == raw
    assert restored.constraint_config == constraint_config
    tampered_payload = json.loads(raw.decode("ascii"))
    tampered_payload["constraint_config"]["constraints"][0][
        "target_distance_angstrom_hex"
    ] = float(1.1).hex()
    tampered = (
        json.dumps(
            tampered_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )
    with pytest.raises(
        ReferenceNVEError,
        match="constraint config fingerprint mismatch",
    ):
        ReferenceNVECheckpoint.from_json_bytes(tampered)

    resumed = resume_reference_nve(
        system,
        parameters,
        restored,
        additional_steps=7,
    )
    assert resumed.checkpoint.checkpoint_sha256 == (
        uninterrupted.checkpoint.checkpoint_sha256
    )
    assert resumed.checkpoint.trajectory_head_sha256 == (
        uninterrupted.checkpoint.trajectory_head_sha256
    )
    assert torch.equal(
        resumed.checkpoint.coordinates,
        uninterrupted.checkpoint.coordinates,
    )
    assert torch.equal(
        resumed.checkpoint.velocities_angstrom_per_ps,
        uninterrupted.checkpoint.velocities_angstrom_per_ps,
    )


def test_shake_failure_paths_and_periodic_ambiguity_fail_closed() -> None:
    system = _system(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        masses=(1.0, 3.0),
    )
    strict = ReferenceSHAKERATTLEConfig(
        constraints=(
            ReferenceSHAKERATTLEDistanceConstraint(
                0,
                1,
                1.0,
                tolerance_angstrom=1.0e-14,
            ),
        ),
        max_position_iterations=1,
    )
    report = project_reference_shake_positions(
        system,
        system.coordinates,
        torch.tensor(
            [[[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]]],
            dtype=torch.float64,
        ),
        torch.tensor((1.0, 3.0), dtype=torch.float64),
        strict,
    )
    assert report.converged is False
    assert report.failure_code == "shake_iteration_budget_exhausted"
    assert len(report.max_abs_residual_trace_angstrom) == 2

    invalid_initial = replace(
        system,
        coordinates=torch.tensor(
            [[[0.0, 0.0, 0.0], [1.1, 0.0, 0.0]]],
            dtype=torch.float64,
        ),
    )
    with pytest.raises(ReferenceNVEError, match="initial SHAKE state failed closed"):
        run_reference_nve(
            invalid_initial,
            _parameters(invalid_initial),
            torch.zeros((1, 2, 3), dtype=torch.float64),
            steps=1,
            constraint_config=_distance_constraint(),
        )

    cell = UnitCell.orthorhombic(
        (10.0, 10.0, 10.0),
        dtype=torch.float64,
    )
    periodic = _system(
        ((0.0, 0.0, 0.0), (4.9, 0.0, 0.0)),
        masses=(1.0, 3.0),
        cell=cell,
    )
    with pytest.raises(ReferenceNVEError, match="below half the shortest box"):
        run_reference_nve(
            periodic,
            _parameters(periodic),
            torch.zeros((1, 2, 3), dtype=torch.float64),
            steps=1,
            constraint_config=_distance_constraint(target=5.0),
        )


def test_shake_rattle_config_is_canonical_and_rejects_duplicate_pairs() -> None:
    first = ReferenceSHAKERATTLEDistanceConstraint(1, 0, 1.0)
    second = ReferenceSHAKERATTLEDistanceConstraint(2, 1, 1.1)
    config = ReferenceSHAKERATTLEConfig(constraints=(second, first))
    assert [row.pair for row in config.constraints] == [(0, 1), (1, 2)]
    assert ReferenceSHAKERATTLEConfig.from_dict(config.to_dict()) == config

    with pytest.raises(ReferenceSHAKERATTLEError, match="must be unique"):
        ReferenceSHAKERATTLEConfig(constraints=(first, first))


def test_shake_rattle_symbols_are_reexported_by_physics_package() -> None:
    from betelgeuze_engine_v2 import physics
    from betelgeuze_engine_v2.physics.reference_shake_rattle import (
        __all__ as constraint_exports,
    )

    assert set(constraint_exports) <= set(physics.__all__)
