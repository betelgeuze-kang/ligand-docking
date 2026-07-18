from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
import struct

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
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_constrained_minimization import (  # noqa: E402
    REFERENCE_CONSTRAINED_MINIMIZATION_SCIENTIFIC_BLOCKERS,
    ReferenceConstrainedMinimizationConfig,
    ReferenceConstrainedMinimizationError,
    minimize_reference_force_field_v2_constrained,
    require_reference_constrained_minimization_checkpoint_document,
)
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (  # noqa: E402
    DistanceConstraintParameter,
    DistanceConstraintProjectionConfig,
    ReferenceForceFieldV2Parameters,
)
from betelgeuze_engine_v2.physics.reference_minimization import (  # noqa: E402
    ReferenceMinimizationConfig,
)
from betelgeuze_engine_v2.physics.reference_parameters import (  # noqa: E402
    AtomNonbondedParameter,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    ReferenceApplicabilityDomain,
    ReferenceForceFieldParameters,
)
from betelgeuze_engine_v2.physics.reference_solvation import (  # noqa: E402
    FixedBornAtomParameter,
    FixedBornPolarSolvationParameters,
)


def _provenance(source_id: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=source_id,
        source_sha256="b" * 64,
        parser_name="unit",
        parser_version="1",
        operations=("unit_fixture",),
        source_digest_verified=True,
        transformation_chain_verified=True,
    )


def _angle_system() -> AllAtomSystem:
    angle = 2.0 * math.pi / 3.0
    return AllAtomSystem(
        system_id="constrained-angle",
        atoms=tuple(
            Atom(
                index=index,
                name=f"C{index}",
                element="C",
                atomic_number=6,
                residue_index=0,
            )
            for index in range(3)
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1, order=1.0, source="unit"),
            Bond(index=1, atom_i=0, atom_j=2, order=1.0, source="unit"),
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [math.cos(angle), math.sin(angle), 0.0]]],
            dtype=torch.float64,
        ),
        provenance=_provenance("constrained-angle"),
    )


def _angle_parameters(
    system: AllAtomSystem,
    *,
    charges: tuple[float, float, float] = (0.0, 0.0, 0.0),
    metadata: dict[str, object] | None = None,
    constraints: tuple[DistanceConstraintParameter, ...] | None = None,
) -> ReferenceForceFieldV2Parameters:
    return ReferenceForceFieldV2Parameters(
        base_parameters=ReferenceForceFieldParameters(
            parameter_set_id="constrained-angle-base",
            parameter_set_version="1.0.0",
            topology_sha256=canonical_topology_sha256(system),
            atom_parameters=tuple(
                AtomNonbondedParameter(index, 1.0, 0.0, charges[index])
                for index in range(3)
            ),
            bonds=(
                HarmonicBondParameter(0, 1, 1.0, 100.0),
                HarmonicBondParameter(0, 2, 1.0, 100.0),
            ),
            angles=(HarmonicAngleParameter(1, 0, 2, math.pi / 2.0, 20.0),),
            excluded_pairs=((0, 1), (0, 2), (1, 2)),
            cutoff_angstrom=4.0,
            switch_start_angstrom=3.0,
            applicability_domain=ReferenceApplicabilityDomain(max_atoms=8),
        ),
        constraints=(
            (
                DistanceConstraintParameter(0, 1, 1.0, tolerance_angstrom=1.0e-10),
                DistanceConstraintParameter(0, 2, 1.0, tolerance_angstrom=1.0e-10),
            )
            if constraints is None
            else constraints
        ),
        metadata={} if metadata is None else metadata,
    )


def _angle_solvation_parameters(
    system: AllAtomSystem,
    forcefield: ReferenceForceFieldV2Parameters,
    *,
    radii: tuple[float, float, float] = (1.5, 1.6, 1.7),
) -> FixedBornPolarSolvationParameters:
    return FixedBornPolarSolvationParameters(
        parameter_set_id="constrained-angle-fixed-born",
        parameter_set_version="1.0.0",
        parameter_source_sha256="e" * 64,
        topology_sha256=canonical_topology_sha256(system),
        charge_parameter_fingerprint_sha256=forcefield.fingerprint_sha256,
        atom_parameters=tuple(
            FixedBornAtomParameter(index, radii[index]) for index in range(3)
        ),
    )


def _config(
    *,
    max_iterations: int = 60,
    max_backtracks: int = 12,
    projection_iterations: int = 100,
    force_tolerance: float = 1.0e-7,
) -> ReferenceConstrainedMinimizationConfig:
    return ReferenceConstrainedMinimizationConfig(
        minimization=ReferenceMinimizationConfig(
            max_iterations=max_iterations,
            max_backtracks=max_backtracks,
            initial_step_size_angstrom2_mol_per_kcal=1.0e-2,
            backtrack_factor=0.5,
            armijo_constant=1.0e-4,
            maximum_atom_displacement_angstrom=0.05,
            force_tolerance_kcal_per_mol_angstrom=force_tolerance,
            max_neighbors=8,
            max_atoms_per_cell=16,
        ),
        constraint_projection=DistanceConstraintProjectionConfig(
            max_iterations=projection_iterations,
            max_pair_correction_angstrom=0.25,
        ),
        force_projection_max_sweeps=100,
        force_projection_tolerance_kcal_per_mol_angstrom=1.0e-10,
    )


def _distances(system: AllAtomSystem) -> tuple[float, float]:
    coordinates = system.coordinates[0]
    return tuple(
        float(torch.linalg.vector_norm(coordinates[index] - coordinates[0]).item())
        for index in (1, 2)
    )


def test_constrained_minimization_decreases_energy_and_retains_constraints() -> None:
    system = _angle_system()
    parameters = _angle_parameters(system)
    result = minimize_reference_force_field_v2_constrained(
        system, parameters, _config()
    )

    assert result.converged
    assert result.final_energy_kcal_per_mol < result.initial_energy_kcal_per_mol
    assert result.final_max_tangent_force_kcal_per_mol_angstrom <= 1.0e-7
    assert result.final_max_constraint_residual_angstrom <= 1.0e-10
    assert _distances(result.system) == pytest.approx((1.0, 1.0), abs=1.0e-10)
    assert result.accepted_iterations > 0
    accepted_energies = [
        row.energy_kcal_per_mol
        for row in result.observations
        if row.outcome in {"initial", "accepted"}
    ]
    assert all(
        second < first
        for first, second in zip(accepted_energies, accepted_energies[1:])
    )
    assert all(
        row.constraint_projection["status"] == "converged"
        for row in result.observations
        if row.outcome in {"initial", "accepted"}
    )
    assert result.scientific_blockers == (
        REFERENCE_CONSTRAINED_MINIMIZATION_SCIENTIFIC_BLOCKERS
    )
    assert result.to_dict()["claim_safe"] is False
    assert not result.scientifically_validated


def test_constrained_checkpoint_restart_is_bit_exact() -> None:
    system = _angle_system()
    parameters = _angle_parameters(system)
    config = _config(max_iterations=12, force_tolerance=1.0e-12)

    uninterrupted = minimize_reference_force_field_v2_constrained(
        system, parameters, config
    )
    paused = minimize_reference_force_field_v2_constrained(
        system,
        parameters,
        config,
        pause_after_accepted_iterations=3,
    )
    resumed = minimize_reference_force_field_v2_constrained(
        system,
        parameters,
        config,
        checkpoint=paused.checkpoint.to_dict(),
    )

    assert paused.status == "checkpointed"
    assert paused.accepted_iterations == 3
    assert torch.equal(resumed.system.coordinates, uninterrupted.system.coordinates)
    assert resumed.checkpoint.to_dict() == uninterrupted.checkpoint.to_dict()
    assert resumed.to_dict() == uninterrupted.to_dict()


def test_solvated_constrained_minimization_decreases_and_restarts_bit_exact() -> None:
    system = _angle_system()
    forcefield = _angle_parameters(
        system, charges=(0.8, -0.4, -0.4)
    )
    solvation = _angle_solvation_parameters(system, forcefield)
    config = _config(max_iterations=12, force_tolerance=1.0e-12)

    uninterrupted = minimize_reference_force_field_v2_constrained(
        system,
        forcefield,
        config,
        solvation_parameters=solvation,
    )
    paused = minimize_reference_force_field_v2_constrained(
        system,
        forcefield,
        config,
        solvation_parameters=solvation,
        pause_after_accepted_iterations=3,
    )
    resumed = minimize_reference_force_field_v2_constrained(
        system,
        forcefield,
        config,
        solvation_parameters=solvation,
        checkpoint=paused.checkpoint.to_dict(),
    )

    assert uninterrupted.final_energy_kcal_per_mol < (
        uninterrupted.initial_energy_kcal_per_mol
    )
    assert uninterrupted.final_max_constraint_residual_angstrom <= 1.0e-10
    assert _distances(uninterrupted.system) == pytest.approx(
        (1.0, 1.0), abs=1.0e-10
    )
    assert uninterrupted.solvation_parameter_fingerprint_sha256 == (
        solvation.fingerprint_sha256
    )
    assert uninterrupted.checkpoint.solvation_parameter_fingerprint_sha256 == (
        solvation.fingerprint_sha256
    )
    assert paused.status == "checkpointed"
    assert torch.equal(resumed.system.coordinates, uninterrupted.system.coordinates)
    assert resumed.checkpoint.to_dict() == uninterrupted.checkpoint.to_dict()
    assert resumed.to_dict() == uninterrupted.to_dict()


def test_solvated_checkpoint_crosswire_and_periodic_input_fail_closed() -> None:
    system = _angle_system()
    forcefield = _angle_parameters(system, charges=(0.8, -0.4, -0.4))
    solvation = _angle_solvation_parameters(system, forcefield)
    config = _config(max_iterations=4, force_tolerance=1.0e-12)
    result = minimize_reference_force_field_v2_constrained(
        system,
        forcefield,
        config,
        solvation_parameters=solvation,
    )

    with pytest.raises(
        ReferenceConstrainedMinimizationError,
        match="solvation parameter fingerprint mismatch",
    ):
        minimize_reference_force_field_v2_constrained(
            system,
            forcefield,
            config,
            checkpoint=result.checkpoint,
        )
    different = _angle_solvation_parameters(
        system, forcefield, radii=(1.5, 1.6, 1.8)
    )
    with pytest.raises(
        ReferenceConstrainedMinimizationError,
        match="solvation parameter fingerprint mismatch",
    ):
        minimize_reference_force_field_v2_constrained(
            system,
            forcefield,
            config,
            solvation_parameters=different,
            checkpoint=result.checkpoint,
        )

    periodic_system = replace(
        system,
        cell=UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64),
    )
    periodic_forcefield = _angle_parameters(
        periodic_system,
        charges=(0.8, -0.4, -0.4),
    )
    periodic_solvation = _angle_solvation_parameters(
        periodic_system,
        periodic_forcefield,
    )
    with pytest.raises(
        ReferenceConstrainedMinimizationError,
        match="does not support periodic cells",
    ):
        minimize_reference_force_field_v2_constrained(
            periodic_system,
            periodic_forcefield,
            config,
            solvation_parameters=periodic_solvation,
        )


def test_constrained_minimization_is_rigid_transform_and_outer_swap_covariant() -> None:
    system = _angle_system()
    parameters = _angle_parameters(system)
    config = _config(max_iterations=12, force_tolerance=1.0e-12)
    reference = minimize_reference_force_field_v2_constrained(
        system, parameters, config
    )

    rotation = torch.tensor(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=torch.float64,
    )
    shift = torch.tensor([3.0, -2.0, 1.5], dtype=torch.float64)
    transformed_system = system.with_coordinates(
        system.coordinates @ rotation.T + shift,
        operation="rigid_transform",
    )
    transformed = minimize_reference_force_field_v2_constrained(
        transformed_system, parameters, config
    )
    assert transformed.final_energy_kcal_per_mol == pytest.approx(
        reference.final_energy_kcal_per_mol, abs=2.0e-12
    )
    assert torch.allclose(
        transformed.system.coordinates,
        reference.system.coordinates @ rotation.T + shift,
        atol=2.0e-11,
        rtol=0.0,
    )

    swapped_system = system.with_coordinates(
        system.coordinates[:, [0, 2, 1], :],
        operation="swap_equivalent_outer_atoms",
    )
    swapped = minimize_reference_force_field_v2_constrained(
        swapped_system, parameters, config
    )
    assert swapped.final_energy_kcal_per_mol == pytest.approx(
        reference.final_energy_kcal_per_mol, abs=2.0e-12
    )
    assert torch.allclose(
        swapped.system.coordinates,
        reference.system.coordinates[:, [0, 2, 1], :],
        atol=2.0e-11,
        rtol=0.0,
    )


def test_projection_budget_failure_is_retained_in_minimization_ledger() -> None:
    system = _angle_system()
    parameters = _angle_parameters(system)
    result = minimize_reference_force_field_v2_constrained(
        system,
        parameters,
        _config(
            max_iterations=1,
            max_backtracks=0,
            projection_iterations=1,
            force_tolerance=1.0e-12,
        ),
    )

    assert result.status == "line_search_failed"
    assert result.failure_code == "bounded_projected_backtracking_exhausted"
    assert result.accepted_iterations == 0
    assert result.rejected_evaluations == 1
    failure = result.observations[-1]
    assert failure.outcome == "rejected_constraint_projection"
    assert failure.failure_code == "constraint_iteration_budget_exhausted"
    assert failure.constraint_projection["status"] == "max_iterations_reached"
    assert len(failure.constraint_projection["iterations"]) == 2
    assert failure.max_constraint_residual_angstrom > 1.0e-10
    with pytest.raises(
        ReferenceConstrainedMinimizationError,
        match="terminal failed line-search checkpoint",
    ):
        minimize_reference_force_field_v2_constrained(
            system,
            parameters,
            _config(
                max_iterations=1,
                max_backtracks=0,
                projection_iterations=1,
                force_tolerance=1.0e-12,
            ),
            checkpoint=result.checkpoint,
        )


def _periodic_system() -> AllAtomSystem:
    return AllAtomSystem(
        system_id="periodic-constraint",
        atoms=tuple(
            Atom(
                index=index,
                name=f"C{index}",
                element="C",
                atomic_number=6,
                residue_index=0,
            )
            for index in range(2)
        ),
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [[[0.1, 0.0, 0.0], [9.7, 0.0, 0.0]]], dtype=torch.float64
        ),
        provenance=_provenance("periodic-constraint"),
        cell=UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64),
    )


def test_periodic_minimum_image_constraint_converges_without_motion() -> None:
    system = _periodic_system()
    parameters = ReferenceForceFieldV2Parameters(
        base_parameters=ReferenceForceFieldParameters(
            parameter_set_id="periodic-constraint-base",
            parameter_set_version="1",
            topology_sha256=canonical_topology_sha256(system),
            atom_parameters=(
                AtomNonbondedParameter(0, 1.0, 0.0, 0.0),
                AtomNonbondedParameter(1, 1.0, 0.0, 0.0),
            ),
            excluded_pairs=((0, 1),),
            cutoff_angstrom=4.0,
            switch_start_angstrom=3.0,
            applicability_domain=ReferenceApplicabilityDomain(max_atoms=4),
        ),
        constraints=(
            DistanceConstraintParameter(0, 1, 0.4, tolerance_angstrom=1.0e-10),
        ),
    )
    result = minimize_reference_force_field_v2_constrained(
        system, parameters, _config(force_tolerance=1.0e-12)
    )

    assert result.converged
    assert result.accepted_iterations == 0
    assert torch.equal(result.system.coordinates, system.coordinates)
    assert result.final_max_constraint_residual_angstrom <= 1.0e-10


def test_unsatisfiable_initial_constraints_fail_closed_with_projection_identity() -> None:
    system = _angle_system()
    parameters = _angle_parameters(
        system,
        constraints=(
            DistanceConstraintParameter(0, 1, 1.0),
            DistanceConstraintParameter(0, 2, 1.0),
            DistanceConstraintParameter(1, 2, 3.0),
        ),
    )
    with pytest.raises(
        ReferenceConstrainedMinimizationError,
        match=r"initial constraint projection failed:.*\([0-9a-f]{64}\)",
    ):
        minimize_reference_force_field_v2_constrained(
            system,
            parameters,
            _config(projection_iterations=3),
        )


def test_checkpoint_tampering_and_parameter_crosswire_fail_closed() -> None:
    system = _angle_system()
    parameters = _angle_parameters(system)
    config = _config(max_iterations=4, force_tolerance=1.0e-12)
    result = minimize_reference_force_field_v2_constrained(
        system, parameters, config
    )
    payload = result.checkpoint.to_dict()
    payload["current_energy_kcal_per_mol"] = float(
        payload["current_energy_kcal_per_mol"]
    ) + 1.0
    with pytest.raises(ReferenceConstrainedMinimizationError, match="digest mismatch"):
        require_reference_constrained_minimization_checkpoint_document(payload)

    shortened_trace = result.checkpoint.to_dict()
    first_observation = shortened_trace["observations"][0]
    for coordinates_key, digest_key in (
        ("raw_coordinates_angstrom_hex", "raw_coordinates_sha256"),
        ("projected_coordinates_angstrom_hex", "projected_coordinates_sha256"),
    ):
        first_observation[coordinates_key] = first_observation[coordinates_key][:-1]
        first_observation[digest_key] = hashlib.sha256(
            b"".join(
                struct.pack("<d", float.fromhex(item))
                for row in first_observation[coordinates_key]
                for item in row
            )
        ).hexdigest()
    shortened_projection = {
        key: value
        for key, value in shortened_trace.items()
        if key != "checkpoint_sha256"
    }
    shortened_trace["checkpoint_sha256"] = hashlib.sha256(
        json.dumps(
            shortened_projection,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()
    with pytest.raises(ReferenceConstrainedMinimizationError, match="atom count"):
        require_reference_constrained_minimization_checkpoint_document(
            shortened_trace
        )

    repeated_initial = result.checkpoint.to_dict()
    repeated_row = next(
        row
        for row in repeated_initial["observations"][1:]
        if row["outcome"] == "accepted"
    )
    repeated_row["outcome"] = "initial"
    repeated_row["failure_code"] = None
    repeated_initial_projection = {
        key: value
        for key, value in repeated_initial.items()
        if key != "checkpoint_sha256"
    }
    repeated_initial["checkpoint_sha256"] = hashlib.sha256(
        json.dumps(
            repeated_initial_projection,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()
    with pytest.raises(
        ReferenceConstrainedMinimizationError,
        match="repeats the initial state",
    ):
        require_reference_constrained_minimization_checkpoint_document(
            repeated_initial
        )

    source_drifted_trace = result.checkpoint.to_dict()
    initial_coordinates = source_drifted_trace["observations"][0][
        "raw_coordinates_angstrom_hex"
    ]
    initial_coordinates[0][0] = float(123.0).hex()
    source_drifted_trace["observations"][0]["raw_coordinates_sha256"] = (
        hashlib.sha256(
            b"".join(
                struct.pack("<d", float.fromhex(item))
                for row in initial_coordinates
                for item in row
            )
        ).hexdigest()
    )
    source_drifted_projection = {
        key: value
        for key, value in source_drifted_trace.items()
        if key != "checkpoint_sha256"
    }
    source_drifted_trace["checkpoint_sha256"] = hashlib.sha256(
        json.dumps(
            source_drifted_projection,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()
    require_reference_constrained_minimization_checkpoint_document(
        source_drifted_trace
    )
    with pytest.raises(
        ReferenceConstrainedMinimizationError,
        match="history does not replay exactly from the source system",
    ):
        minimize_reference_force_field_v2_constrained(
            system,
            parameters,
            config,
            checkpoint=source_drifted_trace,
        )

    nested_payload = result.checkpoint.to_dict()
    nested_payload["observations"][0]["max_constraint_residual_angstrom"] += 1.0e-6
    projection = {
        key: value
        for key, value in nested_payload.items()
        if key != "checkpoint_sha256"
    }
    nested_payload["checkpoint_sha256"] = hashlib.sha256(
        json.dumps(
            projection,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()
    with pytest.raises(
        ReferenceConstrainedMinimizationError,
        match="constraint residual disagrees",
    ):
        require_reference_constrained_minimization_checkpoint_document(
            nested_payload
        )

    with pytest.raises(
        ReferenceConstrainedMinimizationError,
        match="parameter fingerprint mismatch",
    ):
        minimize_reference_force_field_v2_constrained(
            system,
            _angle_parameters(system, metadata={"different": True}),
            config,
            checkpoint=result.checkpoint,
        )


def test_rehashed_initial_projected_coordinate_tamper_fails_source_replay() -> None:
    system = _angle_system()
    parameters = _angle_parameters(system)
    config = _config(max_iterations=4, force_tolerance=1.0e-12)
    result = minimize_reference_force_field_v2_constrained(
        system, parameters, config
    )
    payload = result.checkpoint.to_dict()
    initial = payload["observations"][0]
    projected_coordinates = initial["projected_coordinates_angstrom_hex"]
    projected_coordinates[0][0] = float(123.0).hex()
    projected_digest = hashlib.sha256(
        b"".join(
            struct.pack("<d", float.fromhex(item))
            for row in projected_coordinates
            for item in row
        )
    ).hexdigest()
    initial["projected_coordinates_sha256"] = projected_digest
    constraint_projection = initial["constraint_projection"]
    constraint_projection["final_coordinates_sha256"] = projected_digest
    constraint_projection_payload = {
        key: value
        for key, value in constraint_projection.items()
        if key != "projection_sha256"
    }
    constraint_projection["projection_sha256"] = hashlib.sha256(
        json.dumps(
            constraint_projection_payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()
    checkpoint_projection = {
        key: value for key, value in payload.items() if key != "checkpoint_sha256"
    }
    payload["checkpoint_sha256"] = hashlib.sha256(
        json.dumps(
            checkpoint_projection,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()

    require_reference_constrained_minimization_checkpoint_document(payload)
    with pytest.raises(
        ReferenceConstrainedMinimizationError,
        match="history does not replay exactly from the source system",
    ):
        minimize_reference_force_field_v2_constrained(
            system,
            parameters,
            config,
            checkpoint=payload,
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        ({"force_projection_max_sweeps": 0}, "force_projection_max_sweeps"),
        ({"force_projection_max_sweeps": 1001}, "force_projection_max_sweeps"),
        (
            {"force_projection_tolerance_kcal_per_mol_angstrom": 0.0},
            "force_projection_tolerance",
        ),
    ),
)
def test_constrained_minimization_config_is_bounded(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(ReferenceConstrainedMinimizationError, match=message):
        ReferenceConstrainedMinimizationConfig(**kwargs)


def test_constrained_minimization_rejects_non_float64_and_multimodel() -> None:
    system = _angle_system()
    parameters = _angle_parameters(system)
    float32_system = system.with_coordinates(
        system.coordinates.float(), operation="float32"
    )
    with pytest.raises(ReferenceConstrainedMinimizationError, match="CPU float64"):
        minimize_reference_force_field_v2_constrained(
            float32_system, parameters, _config(max_iterations=1)
        )
    multimodel = replace(
        system,
        coordinates=torch.cat((system.coordinates, system.coordinates), dim=0),
    )
    with pytest.raises(ReferenceConstrainedMinimizationError, match="exactly one model"):
        minimize_reference_force_field_v2_constrained(
            multimodel, parameters, _config(max_iterations=1)
        )
