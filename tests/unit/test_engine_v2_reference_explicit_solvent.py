from __future__ import annotations

from dataclasses import replace
import math

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.geometry import (  # noqa: E402
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    canonical_system_sha256,
    canonical_topology_sha256,
    require_valid_all_atom_system,
)
from betelgeuze_engine_v2.physics.reference_ewald import (  # noqa: E402
    ReferenceEwaldConfig,
    evaluate_reference_force_field_with_ewald,
)
from betelgeuze_engine_v2.physics.reference_canonical_ensemble import (  # noqa: E402
    ReferenceCanonicalEnsembleCheckpoint,
    ReferenceCanonicalEnsembleConfig,
    ReferenceLangevinThermostatConfig,
    ReferenceMonteCarloBarostatConfig,
    resume_reference_canonical_ensemble,
    run_reference_npt,
)
from betelgeuze_engine_v2.physics.reference_explicit_solvent import (  # noqa: E402
    JC_CL_CHARGE_E,
    JC_NA_CHARGE_E,
    REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID,
    REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256,
    REFERENCE_EXPLICIT_SOLVENT_PROFILE_SOURCE_SHA256,
    REFERENCE_EXPLICIT_SOLVENT_SCIENTIFIC_BLOCKERS,
    TIP3P_HH_DISTANCE_ANGSTROM,
    TIP3P_H_CHARGE_E,
    TIP3P_OH_DISTANCE_ANGSTROM,
    TIP3P_O_CHARGE_E,
    ReferenceExplicitSolventConfig,
    ReferenceExplicitSolventError,
    prepare_reference_explicit_solvent,
    reference_explicit_solvent_profile,
    require_reference_explicit_solvent_preparation,
    verify_reference_explicit_solvent_replay,
)
from betelgeuze_engine_v2.physics.reference_nve import (  # noqa: E402
    ReferenceNVECheckpoint,
    ReferenceNVEConfig,
    resume_reference_nve,
    run_reference_nve,
)
from betelgeuze_engine_v2.physics.reference_parameters import (  # noqa: E402
    AtomNonbondedParameter,
    ReferenceForceFieldParameters,
)
from betelgeuze_engine_v2.physics.reference_shake_rattle import (  # noqa: E402
    ReferenceSHAKERATTLEConfig,
    ReferenceSHAKERATTLEDistanceConstraint,
    observe_reference_position_constraints,
)


def _solute(
    *,
    charge_e: float = 0.0,
    mass_da: float | None = 12.011,
    partial_charge_e: float | None = None,
    coordinates: tuple[tuple[float, float, float], ...] = ((0.0, 0.0, 0.0),),
    cell: UnitCell | None = None,
) -> AllAtomSystem:
    active_partial_charge = charge_e if partial_charge_e is None else partial_charge_e
    atoms = tuple(
        Atom(
            index=index,
            name=f"C{index + 1}",
            element="C",
            atomic_number=6,
            residue_index=0,
            partial_charge_e=active_partial_charge if index == 0 else 0.0,
            mass_da=mass_da,
        )
        for index in range(len(coordinates))
    )
    return AllAtomSystem(
        system_id="explicit-solvent-test-solute",
        atoms=atoms,
        bonds=(),
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
    charge_e: float = 0.0,
    cutoff_angstrom: float = 4.0,
) -> ReferenceForceFieldParameters:
    return ReferenceForceFieldParameters(
        parameter_set_id="explicit-solvent-test-parameters",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=tuple(
            AtomNonbondedParameter(
                atom_index=index,
                sigma_angstrom=3.4,
                epsilon_kcal_per_mol=0.1,
                charge_e=charge_e if index == 0 else 0.0,
            )
            for index in range(system.atom_count)
        ),
        cutoff_angstrom=cutoff_angstrom,
        switch_start_angstrom=0.75 * cutoff_angstrom,
    )


def _config(
    *,
    water_count: int = 2,
    sodium_count: int = 1,
    chloride_count: int = 1,
) -> ReferenceExplicitSolventConfig:
    return ReferenceExplicitSolventConfig(
        box_lengths_angstrom=(12.0, 12.0, 12.0),
        water_count=water_count,
        sodium_count=sodium_count,
        chloride_count=chloride_count,
    )


def test_profile_and_config_are_canonical_source_bound_and_bounded() -> None:
    profile = reference_explicit_solvent_profile()
    config = _config()

    assert profile["source_sha256"] == (
        REFERENCE_EXPLICIT_SOLVENT_PROFILE_SOURCE_SHA256
    )
    assert REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256 == (
        "761211b79a889052706ad91626432eda8970eba2fa68123515f93e8990cb2886"
    )
    assert profile["scientifically_validated"] is False
    assert config.to_dict()["algorithm_id"] == (
        REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID
    )
    assert config.to_dict()["profile_fingerprint_sha256"] == (
        REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256
    )
    assert ReferenceExplicitSolventConfig.from_dict(config.to_dict()) == config
    assert ReferenceExplicitSolventConfig.from_dict(
        config.to_dict()
    ).fingerprint_sha256 == config.fingerprint_sha256

    with pytest.raises(ReferenceExplicitSolventError, match="must be an integer"):
        replace(config, water_count=True)
    with pytest.raises(ReferenceExplicitSolventError, match="requires neutrality"):
        replace(config, require_neutral_system=False)
    tampered = config.to_dict()
    tampered["profile_fingerprint_sha256"] = "0" * 64
    with pytest.raises(ReferenceExplicitSolventError, match="profile identity"):
        ReferenceExplicitSolventConfig.from_dict(tampered)


def test_preparation_materializes_full_topology_parameters_constraints_and_receipt() -> None:
    source = _solute()
    source_parameters = _parameters(source)
    preparation = prepare_reference_explicit_solvent(
        source,
        source_parameters,
        _config(),
    )

    require_valid_all_atom_system(preparation.system)
    assert require_reference_explicit_solvent_preparation(preparation) == preparation
    assert (
        verify_reference_explicit_solvent_replay(
            source,
            source_parameters,
            _config(),
            preparation,
        )
        is preparation
    )
    assert preparation.system.atom_count == 9
    assert len(preparation.system.residues) == 5
    assert [residue.name for residue in preparation.system.residues] == [
        "MOL",
        "HOH",
        "HOH",
        "NA",
        "CL",
    ]
    assert len(preparation.system.bonds) == 4
    assert len(preparation.parameters.bonds) == 4
    assert len(preparation.parameters.angles) == 2
    assert len(preparation.parameters.excluded_pairs) == 6
    assert len(preparation.constraint_config.constraints) == 6
    assert set(preparation.parameters.atom_parameter_map) == set(range(9))
    assert preparation.parameters.topology_sha256 == canonical_topology_sha256(
        preparation.system
    )
    assert preparation.system.cell is not None
    assert preparation.system.cell.periodic == (True, True, True)
    assert preparation.receipt.source_system_sha256 == canonical_system_sha256(
        source
    )
    assert preparation.receipt.solvated_system_sha256 == canonical_system_sha256(
        preparation.system
    )
    assert preparation.receipt.source_parameter_fingerprint_sha256 == (
        source_parameters.fingerprint_sha256
    )
    assert preparation.receipt.solvated_parameter_fingerprint_sha256 == (
        preparation.parameters.fingerprint_sha256
    )
    assert preparation.receipt.scientific_blockers == (
        REFERENCE_EXPLICIT_SOLVENT_SCIENTIFIC_BLOCKERS
    )
    assert preparation.receipt.solvated_total_charge_e == 0.0
    assert preparation.receipt.minimum_solute_site_distance_angstrom >= 2.0
    assert (
        preparation.receipt.minimum_intermolecular_solvent_site_distance_angstrom
        >= 0.75
    )
    assert preparation.scientifically_validated is False
    assert preparation.claim_safe is False
    assert preparation.to_dict()["claim_safe"] is False

    atom_map = preparation.parameters.atom_parameter_map
    water_indices = tuple(range(1, 7))
    assert math.fsum(atom_map[index].charge_e for index in water_indices) == 0.0
    assert atom_map[1].charge_e == TIP3P_O_CHARGE_E
    assert atom_map[2].charge_e == TIP3P_H_CHARGE_E
    assert atom_map[7].charge_e == JC_NA_CHARGE_E
    assert atom_map[8].charge_e == JC_CL_CHARGE_E
    observations = observe_reference_position_constraints(
        preparation.system,
        preparation.system.coordinates,
        preparation.constraint_config,
    )
    assert all(row.satisfied for row in observations)
    assert {row.target_distance_angstrom for row in observations} == {
        TIP3P_OH_DISTANCE_ANGSTROM,
        TIP3P_HH_DISTANCE_ANGSTROM,
    }


def test_preparation_is_deterministic_and_configuration_changes_identity() -> None:
    source = _solute()
    parameters = _parameters(source)
    first = prepare_reference_explicit_solvent(source, parameters, _config())
    second = prepare_reference_explicit_solvent(source, parameters, _config())
    changed = prepare_reference_explicit_solvent(
        source,
        parameters,
        _config(water_count=3),
    )

    assert canonical_system_sha256(first.system) == canonical_system_sha256(
        second.system
    )
    assert first.parameters.fingerprint_sha256 == (
        second.parameters.fingerprint_sha256
    )
    assert first.constraint_config.fingerprint_sha256 == (
        second.constraint_config.fingerprint_sha256
    )
    assert first.receipt.fingerprint_sha256 == second.receipt.fingerprint_sha256
    assert first.receipt.placement_trace_sha256 == (
        second.receipt.placement_trace_sha256
    )
    assert canonical_system_sha256(first.system) != canonical_system_sha256(
        changed.system
    )
    assert first.receipt.config_fingerprint_sha256 != (
        changed.receipt.config_fingerprint_sha256
    )
    multi_ion = prepare_reference_explicit_solvent(
        source,
        parameters,
        _config(water_count=1, sodium_count=2, chloride_count=2),
    )
    assert multi_ion.receipt.sodium_count == 2
    assert multi_ion.receipt.chloride_count == 2


def test_charged_solute_is_neutralized_and_direct_ewald_is_finite() -> None:
    source = _solute(charge_e=1.0)
    parameters = _parameters(source, charge_e=1.0)
    preparation = prepare_reference_explicit_solvent(
        source,
        parameters,
        _config(water_count=2, sodium_count=0, chloride_count=1),
    )
    neighbors = build_compact_radius_graph(
        preparation.system.coordinates,
        RadiusGraphConfig(
            cutoff_angstrom=preparation.parameters.cutoff_angstrom,
            max_neighbors=32,
            max_atoms_per_cell=32,
        ),
        cell=preparation.system.cell,
    )
    evaluation = evaluate_reference_force_field_with_ewald(
        preparation.system,
        neighbors,
        preparation.parameters,
        ReferenceEwaldConfig(
            alpha_per_angstrom=0.35,
            reciprocal_max_indices=(2, 2, 2),
        ),
    )

    assert preparation.receipt.source_total_charge_e == 1.0
    assert preparation.receipt.solvated_total_charge_e == 0.0
    assert evaluation.total_charge_e == 0.0
    assert bool(torch.isfinite(evaluation.term.energy).all().item())
    assert bool(torch.isfinite(evaluation.term.forces).all().item())
    assert evaluation.term.forces.shape == preparation.system.coordinates.shape


def test_explicit_solvent_runs_constrained_ewald_nve_with_exact_restart() -> None:
    source = _solute()
    preparation = prepare_reference_explicit_solvent(
        source,
        _parameters(source),
        _config(),
    )
    ewald = ReferenceEwaldConfig(
        alpha_per_angstrom=0.35,
        reciprocal_max_indices=(2, 2, 2),
    )
    nve_config = ReferenceNVEConfig(
        timestep_ps=1.0e-6,
        trajectory_stride=1,
        max_neighbors=32,
        max_atoms_per_cell=32,
        ewald_config=ewald,
    )
    velocities = torch.zeros_like(preparation.system.coordinates)

    uninterrupted = run_reference_nve(
        preparation.system,
        preparation.parameters,
        velocities,
        steps=2,
        config=nve_config,
        constraint_config=preparation.constraint_config,
    )
    paused = run_reference_nve(
        preparation.system,
        preparation.parameters,
        velocities,
        steps=1,
        config=nve_config,
        constraint_config=preparation.constraint_config,
    )
    restored = ReferenceNVECheckpoint.from_json_bytes(
        paused.checkpoint.to_json_bytes()
    )
    resumed = resume_reference_nve(
        preparation.system,
        preparation.parameters,
        restored,
        additional_steps=1,
    )

    assert uninterrupted.checkpoint.checkpoint_sha256 == (
        resumed.checkpoint.checkpoint_sha256
    )
    assert torch.equal(
        uninterrupted.checkpoint.coordinates,
        resumed.checkpoint.coordinates,
    )
    assert torch.equal(
        uninterrupted.checkpoint.velocities_angstrom_per_ps,
        resumed.checkpoint.velocities_angstrom_per_ps,
    )
    assert uninterrupted.max_abs_energy_drift_kcal_per_mol < 1.0e-6
    assert (
        uninterrupted.checkpoint.max_abs_position_constraint_residual_angstrom
        <= 1.0e-8
    )
    assert (
        uninterrupted.checkpoint.max_abs_velocity_constraint_residual_angstrom_per_ps
        <= 1.0e-10
    )


def test_explicit_solvent_runs_constrained_ewald_npt_with_exact_restart() -> None:
    source = _solute()
    preparation = prepare_reference_explicit_solvent(
        source,
        _parameters(source),
        _config(),
    )
    config = ReferenceCanonicalEnsembleConfig(
        timestep_ps=1.0e-6,
        trajectory_stride=1,
        max_neighbors=32,
        max_atoms_per_cell=32,
        thermostat=ReferenceLangevinThermostatConfig(
            temperature_kelvin=300.0,
            collision_rate_per_ps=1.0,
            random_seed=20260722,
        ),
        barostat=ReferenceMonteCarloBarostatConfig(
            pressure_bar=1.0,
            interval_steps=1,
            max_delta_volume_angstrom3=0.1,
            pressure_observation_stride=1,
            pressure_log_length_step=1.0e-5,
        ),
        ewald_config=ReferenceEwaldConfig(
            alpha_per_angstrom=0.35,
            reciprocal_max_indices=(2, 2, 2),
        ),
    )
    velocities = torch.zeros_like(preparation.system.coordinates)

    uninterrupted = run_reference_npt(
        preparation.system,
        preparation.parameters,
        velocities,
        steps=2,
        config=config,
        constraint_config=preparation.constraint_config,
    )
    paused = run_reference_npt(
        preparation.system,
        preparation.parameters,
        velocities,
        steps=1,
        config=config,
        constraint_config=preparation.constraint_config,
    )
    restored = ReferenceCanonicalEnsembleCheckpoint.from_json_bytes(
        paused.checkpoint.to_json_bytes()
    )
    resumed = resume_reference_canonical_ensemble(
        preparation.system,
        preparation.parameters,
        restored,
        additional_steps=1,
    )

    assert uninterrupted.checkpoint.checkpoint_sha256 == (
        resumed.checkpoint.checkpoint_sha256
    )
    assert uninterrupted.checkpoint.barostat_head_sha256 == (
        resumed.checkpoint.barostat_head_sha256
    )
    assert torch.equal(
        uninterrupted.checkpoint.coordinates,
        resumed.checkpoint.coordinates,
    )
    assert torch.equal(
        uninterrupted.system.cell.vectors,
        resumed.system.cell.vectors,
    )
    assert uninterrupted.checkpoint.cumulative_barostat_attempt_count == 2
    assert all(
        frame.instantaneous_pressure_bar is not None
        for frame in uninterrupted.frames
    )
    assert (
        uninterrupted.checkpoint.max_abs_position_constraint_residual_angstrom
        <= 1.0e-8
    )
    assert (
        uninterrupted.checkpoint.max_abs_velocity_constraint_residual_angstrom_per_ps
        <= 1.0e-10
    )


def test_existing_solute_constraints_are_preserved_before_water_constraints() -> None:
    source = _solute(
        coordinates=((0.0, 0.0, 0.0), (1.5, 0.0, 0.0)),
    )
    source_constraints = ReferenceSHAKERATTLEConfig(
        constraints=(
            ReferenceSHAKERATTLEDistanceConstraint(
                atom_i=0,
                atom_j=1,
                target_distance_angstrom=1.5,
            ),
        ),
    )
    preparation = prepare_reference_explicit_solvent(
        source,
        _parameters(source),
        _config(water_count=1, sodium_count=0, chloride_count=0),
        solute_constraints=source_constraints,
    )

    assert len(preparation.constraint_config.constraints) == 4
    assert preparation.constraint_config.constraints[0].pair == (0, 1)
    assert all(
        row.satisfied
        for row in observe_reference_position_constraints(
            preparation.system,
            preparation.system.coordinates,
            preparation.constraint_config,
        )
    )


def test_preparation_fails_closed_for_non_neutral_or_unbound_inputs() -> None:
    neutral = _solute()
    with pytest.raises(ReferenceExplicitSolventError, match="do not produce a neutral"):
        prepare_reference_explicit_solvent(
            neutral,
            _parameters(neutral),
            _config(water_count=1, sodium_count=1, chloride_count=0),
        )

    mismatched = _solute(partial_charge_e=0.25)
    with pytest.raises(ReferenceExplicitSolventError, match="partial charge"):
        prepare_reference_explicit_solvent(
            mismatched,
            _parameters(mismatched, charge_e=0.0),
            _config(water_count=1, sodium_count=0, chloride_count=0),
        )

    missing_mass = _solute(mass_da=None)
    with pytest.raises(ReferenceExplicitSolventError, match="missing mass_da"):
        prepare_reference_explicit_solvent(
            missing_mass,
            _parameters(missing_mass),
            _config(water_count=1, sodium_count=0, chloride_count=0),
        )

    boxed = _solute(
        cell=UnitCell.orthorhombic((12.0, 12.0, 12.0), dtype=torch.float64)
    )
    with pytest.raises(ReferenceExplicitSolventError, match="unboxed source"):
        prepare_reference_explicit_solvent(
            boxed,
            _parameters(boxed),
            _config(water_count=1, sodium_count=0, chloride_count=0),
        )

    with pytest.raises(ReferenceExplicitSolventError, match="below half"):
        prepare_reference_explicit_solvent(
            neutral,
            _parameters(neutral, cutoff_angstrom=6.0),
            _config(water_count=1, sodium_count=0, chloride_count=0),
        )

    two_atom = _solute(coordinates=((0.0, 0.0, 0.0), (1.5, 0.0, 0.0)))
    bonded = replace(
        two_atom,
        bonds=(Bond(index=0, atom_i=0, atom_j=1),),
    )
    with pytest.raises(ReferenceExplicitSolventError, match="bond parameters"):
        prepare_reference_explicit_solvent(
            bonded,
            _parameters(bonded),
            _config(water_count=1, sodium_count=0, chloride_count=0),
        )


def test_preparation_fails_when_clearance_or_lattice_capacity_is_impossible() -> None:
    extended = _solute(coordinates=((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)))
    with pytest.raises(ReferenceExplicitSolventError, match="box clearance"):
        prepare_reference_explicit_solvent(
            extended,
            _parameters(extended),
            _config(water_count=1, sodium_count=0, chloride_count=0),
        )

    source = _solute()
    impossible = replace(
        _config(water_count=1, sodium_count=0, chloride_count=0),
        minimum_solute_site_distance_angstrom=10.0,
    )
    with pytest.raises(ReferenceExplicitSolventError, match="lattice capacity"):
        prepare_reference_explicit_solvent(
            source,
            _parameters(source),
            impossible,
        )


def test_result_rejects_tampered_receipt_or_scientific_promotion() -> None:
    source = _solute()
    preparation = prepare_reference_explicit_solvent(
        source,
        _parameters(source),
        _config(),
    )

    with pytest.raises(ReferenceExplicitSolventError, match="atom count"):
        replace(
            preparation,
            receipt=replace(
                preparation.receipt,
                solvated_atom_count=preparation.receipt.solvated_atom_count - 1,
            ),
        )
    with pytest.raises(ReferenceExplicitSolventError, match="cannot be promoted"):
        replace(
            preparation.receipt,
            scientific_blockers=(),
        )
    with pytest.raises(ReferenceExplicitSolventError, match="water_molarity"):
        replace(
            preparation,
            receipt=replace(
                preparation.receipt,
                water_molarity=preparation.receipt.water_molarity + 1.0,
            ),
        )
    atom_parameters = list(preparation.parameters.atom_parameters)
    atom_parameters[1] = replace(
        atom_parameters[1],
        epsilon_kcal_per_mol=atom_parameters[1].epsilon_kcal_per_mol + 0.01,
    )
    tampered_parameters = replace(
        preparation.parameters,
        atom_parameters=tuple(atom_parameters),
    )
    with pytest.raises(ReferenceExplicitSolventError, match="profile drifted"):
        replace(
            preparation,
            parameters=tampered_parameters,
            receipt=replace(
                preparation.receipt,
                solvated_parameter_fingerprint_sha256=(
                    tampered_parameters.fingerprint_sha256
                ),
            ),
        )
    with pytest.raises(ReferenceExplicitSolventError, match="trusted-input replay"):
        verify_reference_explicit_solvent_replay(
            source,
            _parameters(source),
            _config(water_count=3),
            preparation,
        )


def test_physics_package_exports_explicit_solvent_surface() -> None:
    from betelgeuze_engine_v2 import physics

    assert physics.ReferenceExplicitSolventConfig is ReferenceExplicitSolventConfig
    assert physics.prepare_reference_explicit_solvent is (
        prepare_reference_explicit_solvent
    )
    assert physics.reference_explicit_solvent_profile is (
        reference_explicit_solvent_profile
    )
    assert physics.verify_reference_explicit_solvent_replay is (
        verify_reference_explicit_solvent_replay
    )
