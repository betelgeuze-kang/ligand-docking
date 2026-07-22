from __future__ import annotations

from dataclasses import replace

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
    AtomNonbondedParameter,
    HarmonicBondParameter,
    ReferenceEwaldConfig,
    ReferenceForceFieldParameters,
    ReferenceNVECheckpoint,
    ReferenceNVEConfig,
    ReferenceSHAKERATTLEConfig,
    ReferenceSHAKERATTLEDistanceConstraint,
    resume_reference_nve,
    run_reference_nve,
)
from betelgeuze_engine_v2.physics.reference_nve_drift import (  # noqa: E402
    MOLAR_GAS_CONSTANT_KCAL_PER_MOL_K,
    REFERENCE_NVE_DRIFT_METRIC_IDS,
    REFERENCE_NVE_DRIFT_SCIENTIFIC_BLOCKERS,
    ReferenceNVEDriftAcceptanceConfig,
    ReferenceNVEDriftError,
    analyze_reference_nve_drift,
)


def _system(
    coordinates: tuple[tuple[float, float, float], ...],
    *,
    masses: tuple[float, ...] | None = None,
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
        system_id="reference-nve-drift-unit-system",
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
    charges: tuple[float, ...] | None = None,
    equilibrium_angstrom: float = 1.0,
    force_constant: float = 100.0,
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
        parameter_set_id="reference-nve-drift-unit-parameters",
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


def _acceptance(
    *,
    energy: float = 1.0e-3,
    rms_energy: float = 1.0e-3,
    relative: float = 1.0e-2,
    slope: float = 1.0,
    momentum: float = 1.0e-10,
    rms_momentum: float = 1.0e-10,
    position: float = 1.0e-9,
    velocity: float = 1.0e-9,
) -> ReferenceNVEDriftAcceptanceConfig:
    return ReferenceNVEDriftAcceptanceConfig(
        max_abs_energy_drift_kcal_per_mol_per_atom=energy,
        max_rms_energy_drift_kcal_per_mol_per_atom=rms_energy,
        max_abs_relative_energy_drift=relative,
        max_abs_energy_drift_slope_kcal_per_mol_per_ps_per_atom=slope,
        max_linear_momentum_drift_da_angstrom_per_ps=momentum,
        max_rms_linear_momentum_drift_da_angstrom_per_ps=rms_momentum,
        max_position_constraint_residual_angstrom=position,
        max_velocity_constraint_residual_angstrom_per_ps=velocity,
    )


def _run_with_restart(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    velocities: torch.Tensor,
    *,
    steps: int,
    pause_step: int,
    config: ReferenceNVEConfig,
    constraints: ReferenceSHAKERATTLEConfig | None = None,
    resumed_additional_steps: int | None = None,
):
    uninterrupted = run_reference_nve(
        system,
        parameters,
        velocities,
        steps=steps,
        config=config,
        constraint_config=constraints,
    )
    paused = run_reference_nve(
        system,
        parameters,
        velocities,
        steps=pause_step,
        config=config,
        constraint_config=constraints,
    )
    restored = ReferenceNVECheckpoint.from_json_bytes(
        paused.checkpoint.to_json_bytes()
    )
    restarted = resume_reference_nve(
        system,
        parameters,
        restored,
        additional_steps=(
            steps - pause_step
            if resumed_additional_steps is None
            else resumed_additional_steps
        ),
    )
    return uninterrupted, restarted


def test_acceptance_config_is_canonical_and_rejects_nonfinite_values() -> None:
    config = _acceptance()
    assert ReferenceNVEDriftAcceptanceConfig.from_dict(config.to_dict()) == config
    assert len(config.fingerprint_sha256) == 64

    with pytest.raises(ReferenceNVEDriftError, match="non-negative"):
        _acceptance(energy=-1.0)
    with pytest.raises(ReferenceNVEDriftError, match="finite"):
        _acceptance(slope=float("inf"))


def test_force_free_trace_has_exact_energy_momentum_and_restart_equality() -> None:
    system = _system(((0.0, 0.0, 0.0),))
    parameters = _parameters(system)
    velocity = torch.tensor([[[1.0, -2.0, 0.5]]], dtype=torch.float64)
    uninterrupted, restarted = _run_with_restart(
        system,
        parameters,
        velocity,
        steps=10,
        pause_step=4,
        config=ReferenceNVEConfig(timestep_ps=0.01, trajectory_stride=1),
    )
    result = analyze_reference_nve_drift(
        uninterrupted,
        restarted,
        _acceptance(
            energy=0.0,
            rms_energy=0.0,
            relative=0.0,
            slope=0.0,
            momentum=0.0,
            rms_momentum=0.0,
            position=0.0,
            velocity=0.0,
        ),
    )

    assert result.numerical_acceptance_passed is True
    assert result.restart_equality.exact is True
    assert result.max_abs_energy_drift_kcal_per_mol == 0.0
    assert result.rms_energy_drift_kcal_per_mol == 0.0
    assert result.energy_drift_slope_kcal_per_mol_per_ps == 0.0
    assert result.max_linear_momentum_drift_da_angstrom_per_ps == 0.0
    assert result.rms_linear_momentum_drift_da_angstrom_per_ps == 0.0
    assert len(result.observations) == 11
    expected_temperature = (
        2.0
        * uninterrupted.frames[0].kinetic_energy_kcal_per_mol
        / (3.0 * MOLAR_GAS_CONSTANT_KCAL_PER_MOL_K)
    )
    assert result.observations[0].kinetic_temperature_k == pytest.approx(
        expected_temperature
    )
    assert result.scientific_blockers == REFERENCE_NVE_DRIFT_SCIENTIFIC_BLOCKERS
    assert result.scientifically_validated is False
    assert result.claim_safe is False

    with pytest.raises(ReferenceNVEDriftError, match="summary"):
        replace(result, max_abs_energy_drift_kcal_per_mol=1.0)
    with pytest.raises(ReferenceNVEDriftError, match="degrees of freedom"):
        replace(result, atom_count=2)
    drifted_metric = replace(result.metrics[0], threshold=1.0)
    with pytest.raises(ReferenceNVEDriftError, match="metric"):
        replace(result, metrics=(drifted_metric, *result.metrics[1:]))
    with pytest.raises(ReferenceNVEDriftError, match="total energy"):
        replace(
            result.observations[0],
            total_energy_kcal_per_mol=(
                result.observations[0].total_energy_kcal_per_mol + 1.0
            ),
        )


def test_harmonic_dimer_reports_all_step_drift_and_metric_rows() -> None:
    system = _system(
        ((-0.55, 0.0, 0.0), (0.55, 0.0, 0.0)),
        bonded=True,
    )
    uninterrupted, restarted = _run_with_restart(
        system,
        _parameters(system),
        torch.zeros((1, 2, 3), dtype=torch.float64),
        steps=200,
        pause_step=73,
        config=ReferenceNVEConfig(timestep_ps=0.0001, trajectory_stride=1),
    )
    result = analyze_reference_nve_drift(
        uninterrupted,
        restarted,
        _acceptance(
            energy=1.0e-4,
            rms_energy=1.0e-4,
            relative=5.0e-4,
            slope=0.1,
        ),
    )
    payload = result.to_dict()

    assert result.numerical_acceptance_passed is True
    assert tuple(row.metric_id for row in result.metrics) == (
        REFERENCE_NVE_DRIFT_METRIC_IDS
    )
    assert len(result.observations) == 201
    assert result.max_abs_energy_drift_kcal_per_mol == (
        uninterrupted.max_abs_energy_drift_kcal_per_mol
    )
    assert payload["failed_metric_ids"] == []
    assert payload["observation_count"] == 201
    assert payload["trajectory_head_sha256"] == (
        uninterrupted.checkpoint.trajectory_head_sha256
    )
    assert result.observations[-1].frame_sha256 == (
        uninterrupted.frames[-1].fingerprint_sha256
    )


def test_constrained_trace_reports_current_position_and_velocity_residuals() -> None:
    system = _system(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        masses=(1.0, 3.0),
    )
    constraints = ReferenceSHAKERATTLEConfig(
        constraints=(
            ReferenceSHAKERATTLEDistanceConstraint(
                atom_i=0,
                atom_j=1,
                target_distance_angstrom=1.0,
                tolerance_angstrom=1.0e-10,
            ),
        ),
    )
    uninterrupted, restarted = _run_with_restart(
        system,
        _parameters(system),
        torch.tensor(
            [[[0.0, 1.0, 0.0], [0.0, 0.0, 0.0]]],
            dtype=torch.float64,
        ),
        steps=20,
        pause_step=7,
        config=ReferenceNVEConfig(timestep_ps=0.001, trajectory_stride=1),
        constraints=constraints,
    )
    result = analyze_reference_nve_drift(
        uninterrupted,
        restarted,
        _acceptance(
            energy=1.0e-10,
            rms_energy=1.0e-10,
            relative=1.0e-8,
            slope=1.0e-8,
            momentum=1.0e-12,
            position=1.0e-10,
            velocity=1.0e-10,
        ),
    )

    assert result.numerical_acceptance_passed is True
    assert max(
        row.max_position_constraint_residual_angstrom
        for row in result.observations
    ) <= 1.0e-10
    assert max(
        row.max_velocity_constraint_residual_angstrom_per_ps
        for row in result.observations
    ) <= 1.0e-10
    assert result.max_linear_momentum_drift_da_angstrom_per_ps <= 1.0e-12
    assert result.kinetic_temperature_degrees_of_freedom == 5
    assert result.to_dict()["kinetic_temperature_dof_policy"] == (
        "3N_minus_declared_distance_constraints_no_com_removal"
    )


def test_periodic_direct_ewald_trace_has_bounded_drift_and_exact_restart() -> None:
    cell = UnitCell.orthorhombic(
        (10.0, 10.0, 10.0),
        dtype=torch.float64,
    )
    system = _system(
        ((2.0, 5.0, 5.0), (5.0, 5.0, 5.0)),
        cell=cell,
    )
    parameters = _parameters(system, charges=(0.25, -0.25))
    config = ReferenceNVEConfig(
        timestep_ps=1.0e-5,
        trajectory_stride=1,
        ewald_config=ReferenceEwaldConfig(
            alpha_per_angstrom=0.4,
            reciprocal_max_indices=(4, 4, 4),
        ),
    )
    uninterrupted, restarted = _run_with_restart(
        system,
        parameters,
        torch.tensor(
            [[[0.0, 0.01, 0.0], [0.0, -0.01, 0.0]]],
            dtype=torch.float64,
        ),
        steps=20,
        pause_step=7,
        config=config,
    )
    result = analyze_reference_nve_drift(
        uninterrupted,
        restarted,
        _acceptance(
            energy=1.0e-6,
            rms_energy=1.0e-6,
            relative=1.0e-6,
            slope=1.0e-2,
            momentum=1.0e-10,
        ),
    )

    assert result.numerical_acceptance_passed is True
    assert result.restart_equality.exact is True
    assert result.max_abs_energy_drift_kcal_per_mol / system.atom_count < 1.0e-6
    assert result.max_linear_momentum_drift_da_angstrom_per_ps < 1.0e-10


def test_failure_rows_preserve_threshold_and_restart_mismatches() -> None:
    system = _system(((0.0, 0.0, 0.0),))
    parameters = _parameters(system)
    velocity = torch.tensor([[[1.0, 0.0, 0.0]]], dtype=torch.float64)
    uninterrupted, short_restart = _run_with_restart(
        system,
        parameters,
        velocity,
        steps=10,
        pause_step=4,
        resumed_additional_steps=5,
        config=ReferenceNVEConfig(timestep_ps=0.01, trajectory_stride=1),
    )
    result = analyze_reference_nve_drift(
        uninterrupted,
        short_restart,
        _acceptance(
            energy=0.0,
            rms_energy=0.0,
            relative=0.0,
            slope=0.0,
            momentum=0.0,
            rms_momentum=0.0,
            position=0.0,
            velocity=0.0,
        ),
    )

    assert result.numerical_acceptance_passed is False
    assert result.restart_equality.exact is False
    assert result.metrics[-1].metric_id == "exact_checkpoint_restart_equality"
    assert result.metrics[-1].passed is False
    assert result.to_dict()["failed_metric_ids"] == [
        "exact_checkpoint_restart_equality"
    ]


def test_failed_energy_thresholds_remain_in_complete_metric_denominator() -> None:
    system = _system(
        ((-0.55, 0.0, 0.0), (0.55, 0.0, 0.0)),
        bonded=True,
    )
    uninterrupted, restarted = _run_with_restart(
        system,
        _parameters(system),
        torch.zeros((1, 2, 3), dtype=torch.float64),
        steps=20,
        pause_step=7,
        config=ReferenceNVEConfig(timestep_ps=0.001, trajectory_stride=1),
    )
    result = analyze_reference_nve_drift(
        uninterrupted,
        restarted,
        _acceptance(
            energy=0.0,
            rms_energy=0.0,
            relative=0.0,
            slope=0.0,
        ),
    )

    assert result.numerical_acceptance_passed is False
    assert tuple(row.metric_id for row in result.metrics) == (
        REFERENCE_NVE_DRIFT_METRIC_IDS
    )
    assert len(result.metrics) == len(REFERENCE_NVE_DRIFT_METRIC_IDS)
    assert "max_abs_energy_drift_kcal_per_mol_per_atom" in (
        result.to_dict()["failed_metric_ids"]
    )
    assert result.metrics[-1].passed is True


def test_incomplete_or_subsampled_trajectory_fails_closed() -> None:
    system = _system(((0.0, 0.0, 0.0),))
    parameters = _parameters(system)
    velocity = torch.zeros((1, 1, 3), dtype=torch.float64)
    uninterrupted, restarted = _run_with_restart(
        system,
        parameters,
        velocity,
        steps=6,
        pause_step=2,
        config=ReferenceNVEConfig(timestep_ps=0.01, trajectory_stride=2),
    )
    with pytest.raises(ReferenceNVEDriftError, match="trajectory_stride=1"):
        analyze_reference_nve_drift(
            uninterrupted,
            restarted,
            _acceptance(),
        )


def test_nve_drift_symbols_are_reexported_by_physics_package() -> None:
    from betelgeuze_engine_v2 import physics
    from betelgeuze_engine_v2.physics.reference_nve_drift import (
        __all__ as drift_exports,
    )

    assert set(drift_exports) <= set(physics.__all__)
