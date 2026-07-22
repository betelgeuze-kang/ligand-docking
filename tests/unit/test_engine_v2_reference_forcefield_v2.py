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
)
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (  # noqa: E402
    REFERENCE_DISTANCE_CONSTRAINT_PROJECTION_CONVERGENCE_TOLERANCE_SCALE,
    REFERENCE_FORCEFIELD_V2_SCIENTIFIC_BLOCKERS,
    DistanceConstraintParameter,
    DistanceConstraintProjectionConfig,
    HarmonicOutOfPlaneImproperParameter,
    ReferenceForceFieldV2ApplicabilityError,
    ReferenceForceFieldV2Error,
    ReferenceForceFieldV2Parameters,
    evaluate_reference_force_field_v2,
    project_distance_constraints,
)
from betelgeuze_engine_v2.physics.reference_parameters import (  # noqa: E402
    AtomNonbondedParameter,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    ReferenceApplicabilityDomain,
    ReferenceForceFieldParameters,
)


def _provenance(source_id: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=source_id,
        source_sha256="a" * 64,
        parser_name="unit",
        parser_version="1",
        operations=("unit_fixture",),
        source_digest_verified=True,
        transformation_chain_verified=True,
    )


def _star_system(coordinates: torch.Tensor | None = None) -> AllAtomSystem:
    coords = coordinates
    if coords is None:
        coords = torch.tensor(
            [[
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.4, 0.3, 0.2],
            ]],
            dtype=torch.float64,
        )
    return AllAtomSystem(
        system_id="forcefield-v2-star",
        atoms=tuple(
            Atom(
                index=index,
                name=f"C{index}",
                element="C",
                atomic_number=6,
                residue_index=0,
            )
            for index in range(4)
        ),
        bonds=tuple(
            Bond(index=index, atom_i=0, atom_j=index + 1, order=1.0, source="unit")
            for index in range(3)
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2, 3),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=coords,
        provenance=_provenance("forcefield-v2-star"),
    )


def _angle(first: torch.Tensor, second: torch.Tensor) -> float:
    return float(
        torch.acos(
            torch.dot(first, second)
            / (torch.linalg.vector_norm(first) * torch.linalg.vector_norm(second))
        ).item()
    )


def _star_base_parameters(system: AllAtomSystem) -> ReferenceForceFieldParameters:
    coordinates = system.coordinates[0]
    center = coordinates[0]
    vectors = [coordinates[index] - center for index in (1, 2, 3)]
    return ReferenceForceFieldParameters(
        parameter_set_id="forcefield-v2-star-base",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=tuple(
            AtomNonbondedParameter(index, 1.0, 0.0, 0.0) for index in range(4)
        ),
        bonds=tuple(
            HarmonicBondParameter(
                0,
                index,
                float(torch.linalg.vector_norm(vectors[index - 1]).item()),
                100.0,
            )
            for index in (1, 2, 3)
        ),
        angles=(
            HarmonicAngleParameter(1, 0, 2, _angle(vectors[0], vectors[1]), 30.0),
            HarmonicAngleParameter(1, 0, 3, _angle(vectors[0], vectors[2]), 30.0),
            HarmonicAngleParameter(2, 0, 3, _angle(vectors[1], vectors[2]), 30.0),
        ),
        excluded_pairs=((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)),
        cutoff_angstrom=4.0,
        switch_start_angstrom=3.0,
        applicability_domain=ReferenceApplicabilityDomain(max_atoms=8),
    )


def _star_v2_parameters(system: AllAtomSystem) -> ReferenceForceFieldV2Parameters:
    return ReferenceForceFieldV2Parameters(
        base_parameters=_star_base_parameters(system),
        impropers=(
            HarmonicOutOfPlaneImproperParameter(
                center_atom=0,
                plane_atom_i=1,
                plane_atom_j=2,
                out_of_plane_atom=3,
                equilibrium_radians=0.0,
                force_constant_kcal_per_mol_radian2=20.0,
            ),
        ),
        constraints=(
            DistanceConstraintParameter(0, 3, 0.6, tolerance_angstrom=1.0e-8),
        ),
        metadata={"scope": {"kind": "unit"}},
    )


def _neighbors(system: AllAtomSystem, cutoff: float = 4.0):
    return build_compact_radius_graph(
        system.coordinates,
        RadiusGraphConfig(
            cutoff_angstrom=cutoff,
            max_neighbors=8,
            max_atoms_per_cell=16,
        ),
        cell=system.cell,
    )


def test_v2_improper_energy_force_and_constraint_observation_are_explicit() -> None:
    system = _star_system()
    parameters = _star_v2_parameters(system)
    evaluation = evaluate_reference_force_field_v2(
        system,
        _neighbors(system),
        parameters,
    )

    expected_angle = math.asin(0.2 / math.sqrt(0.4**2 + 0.3**2 + 0.2**2))
    expected_energy = 0.5 * 20.0 * expected_angle**2
    assert evaluation.component_energies["harmonic_out_of_plane_improper"].item() == (
        pytest.approx(expected_energy, abs=1.0e-12)
    )
    assert evaluation.term.energy.item() == pytest.approx(expected_energy, abs=1.0e-12)
    assert torch.isfinite(evaluation.term.forces).all()
    assert torch.allclose(
        evaluation.term.forces,
        evaluation.improper_forces,
        atol=1.0e-11,
        rtol=1.0e-11,
    )
    assert evaluation.term.validated_for_composition is False
    assert not evaluation.scientifically_validated
    assert evaluation.scientific_blockers == REFERENCE_FORCEFIELD_V2_SCIENTIFIC_BLOCKERS
    assert not evaluation.constraints_satisfied
    assert len(evaluation.constraint_observations) == 1
    assert evaluation.constraint_observations[0].observed_distance_angstrom == (
        pytest.approx(math.sqrt(0.29), abs=1.0e-12)
    )
    assert evaluation.to_dict()["claim_safe"] is False
    assert parameters.to_dict()["improper_angle_semantics"] == (
        "ordered_star_out_of_plane_asin"
    )
    assert len(parameters.fingerprint_sha256) == 64
    with pytest.raises(TypeError):
        parameters.metadata["new"] = True


def test_v2_improper_force_matches_finite_difference() -> None:
    system = _star_system()
    parameters = _star_v2_parameters(system)
    evaluation = evaluate_reference_force_field_v2(
        system,
        _neighbors(system),
        parameters,
    )
    step = 1.0e-5
    plus_coordinates = system.coordinates.clone()
    minus_coordinates = system.coordinates.clone()
    plus_coordinates[0, 3, 2] += step
    minus_coordinates[0, 3, 2] -= step
    plus = system.with_coordinates(plus_coordinates, operation="finite_difference_plus")
    minus = system.with_coordinates(minus_coordinates, operation="finite_difference_minus")
    plus_energy = evaluate_reference_force_field_v2(
        plus,
        _neighbors(plus),
        parameters,
    ).term.energy[0]
    minus_energy = evaluate_reference_force_field_v2(
        minus,
        _neighbors(minus),
        parameters,
    ).term.energy[0]
    numerical_force = -float(((plus_energy - minus_energy) / (2.0 * step)).item())
    analytic_force = float(evaluation.term.forces[0, 3, 2].item())
    assert analytic_force == pytest.approx(numerical_force, rel=2.0e-5, abs=2.0e-5)


def test_v2_improper_is_translation_invariant_rotation_covariant_and_force_balanced() -> None:
    system = _star_system()
    parameters = _star_v2_parameters(system)
    original = evaluate_reference_force_field_v2(system, _neighbors(system), parameters)
    rotation = torch.tensor(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=torch.float64,
    )
    transformed = system.with_coordinates(
        system.coordinates @ rotation.T
        + torch.tensor([4.0, -3.0, 2.0], dtype=torch.float64),
        operation="rigid_transform",
    )
    transformed_evaluation = evaluate_reference_force_field_v2(
        transformed,
        _neighbors(transformed),
        parameters,
    )

    assert transformed_evaluation.term.energy.item() == pytest.approx(
        original.term.energy.item(),
        abs=1.0e-10,
    )
    assert torch.allclose(
        transformed_evaluation.term.forces,
        original.term.forces @ rotation.T,
        atol=2.0e-8,
        rtol=2.0e-8,
    )
    assert torch.allclose(
        original.improper_forces.sum(dim=1),
        torch.zeros((1, 3), dtype=torch.float64),
        atol=2.0e-10,
        rtol=0.0,
    )


def _free_system(coordinates: torch.Tensor, *, cell: UnitCell | None = None) -> AllAtomSystem:
    atom_count = coordinates.shape[1]
    return AllAtomSystem(
        system_id="forcefield-v2-free",
        atoms=tuple(
            Atom(
                index=index,
                name=f"C{index}",
                element="C",
                atomic_number=6,
                residue_index=0,
            )
            for index in range(atom_count)
        ),
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(atom_count)),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=coordinates,
        provenance=_provenance("forcefield-v2-free"),
        cell=cell,
    )


def _free_v2_parameters(
    system: AllAtomSystem,
    constraints: tuple[DistanceConstraintParameter, ...],
) -> ReferenceForceFieldV2Parameters:
    atom_count = system.atom_count
    return ReferenceForceFieldV2Parameters(
        base_parameters=ReferenceForceFieldParameters(
            parameter_set_id="forcefield-v2-free-base",
            parameter_set_version="1",
            topology_sha256=canonical_topology_sha256(system),
            atom_parameters=tuple(
                AtomNonbondedParameter(index, 1.0, 0.0, 0.0)
                for index in range(atom_count)
            ),
            excluded_pairs=tuple(
                (first, second)
                for first in range(atom_count)
                for second in range(first + 1, atom_count)
            ),
            cutoff_angstrom=4.0,
            switch_start_angstrom=3.0,
            applicability_domain=ReferenceApplicabilityDomain(max_atoms=8),
        ),
        constraints=constraints,
    )


def test_distance_constraint_projection_converges_deterministically_and_preserves_center() -> None:
    system = _free_system(
        torch.tensor([[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]]], dtype=torch.float64)
    )
    parameters = _free_v2_parameters(
        system,
        (DistanceConstraintParameter(0, 1, 1.0, tolerance_angstrom=1.0e-12),),
    )
    config = DistanceConstraintProjectionConfig(
        max_iterations=10,
        max_pair_correction_angstrom=2.0,
    )

    first = project_distance_constraints(system, parameters, config)
    second = project_distance_constraints(system, parameters, config)

    assert first.converged
    assert first.status == "converged"
    assert first.failure_code is None
    assert len(first.iterations) == 2
    assert first.final_observation.satisfied_constraint_count == 1
    assert first.final_observation.max_absolute_residual_angstrom <= 1.0e-12
    assert torch.allclose(
        first.system.coordinates.mean(dim=1),
        system.coordinates.mean(dim=1),
        atol=0.0,
        rtol=0.0,
    )
    assert torch.linalg.vector_norm(
        first.system.coordinates[0, 0] - first.system.coordinates[0, 1]
    ).item() == pytest.approx(1.0, abs=1.0e-12)
    assert first.to_dict() == second.to_dict()
    assert torch.equal(first.system.coordinates, second.system.coordinates)
    assert first.source_system_sha256 == canonical_system_sha256(system)
    assert first.system.provenance.metadata["last_operation_evidence_sha256"] == (
        first.projection_sha256
    )
    assert not first.scientifically_validated


def test_projection_convergence_retains_half_tolerance_roundoff_headroom() -> None:
    tolerance = 1.0e-10
    initial_distance = 1.0 + 0.75 * tolerance
    system = _free_system(
        torch.tensor(
            [[[0.0, 0.0, 0.0], [initial_distance, 0.0, 0.0]]],
            dtype=torch.float64,
        )
    )
    parameters = _free_v2_parameters(
        system,
        (DistanceConstraintParameter(0, 1, 1.0, tolerance_angstrom=tolerance),),
    )

    result = project_distance_constraints(system, parameters)

    assert result.iterations[0].constraint_observations[0].satisfied is True
    assert len(result.iterations) == 2
    assert result.converged
    assert result.final_observation.max_absolute_residual_angstrom <= (
        REFERENCE_DISTANCE_CONSTRAINT_PROJECTION_CONVERGENCE_TOLERANCE_SCALE
        * tolerance
    )
    assert DistanceConstraintProjectionConfig().to_dict()[
        "convergence_tolerance_scale"
    ] == REFERENCE_DISTANCE_CONSTRAINT_PROJECTION_CONVERGENCE_TOLERANCE_SCALE


def test_periodic_constraint_uses_minimum_image_distance() -> None:
    system = _free_system(
        torch.tensor([[[0.1, 0.0, 0.0], [9.7, 0.0, 0.0]]], dtype=torch.float64),
        cell=UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64),
    )
    parameters = _free_v2_parameters(
        system,
        (DistanceConstraintParameter(0, 1, 0.4, tolerance_angstrom=1.0e-12),),
    )
    result = project_distance_constraints(system, parameters)

    assert result.converged
    assert len(result.iterations) == 1
    assert result.final_observation.constraint_observations[0].observed_distance_angstrom == (
        pytest.approx(0.4, abs=1.0e-12)
    )
    assert torch.equal(result.system.coordinates, system.coordinates)


def test_conflicting_constraints_exhaust_budget_and_retain_every_iteration() -> None:
    system = _free_system(
        torch.tensor(
            [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]],
            dtype=torch.float64,
        )
    )
    parameters = _free_v2_parameters(
        system,
        (
            DistanceConstraintParameter(0, 1, 1.0),
            DistanceConstraintParameter(1, 2, 1.0),
            DistanceConstraintParameter(0, 2, 3.0),
        ),
    )
    result = project_distance_constraints(
        system,
        parameters,
        DistanceConstraintProjectionConfig(
            max_iterations=5,
            max_pair_correction_angstrom=10.0,
        ),
    )

    assert not result.converged
    assert result.status == "max_iterations_reached"
    assert result.failure_code == "constraint_iteration_budget_exhausted"
    assert len(result.iterations) == 6
    assert [row.iteration for row in result.iterations] == list(range(6))
    assert result.final_observation.satisfied_constraint_count < 3


def test_degenerate_constraint_geometry_fails_closed_with_observation() -> None:
    system = _free_system(torch.zeros((1, 2, 3), dtype=torch.float64))
    parameters = _free_v2_parameters(
        system,
        (DistanceConstraintParameter(0, 1, 1.0),),
    )
    result = project_distance_constraints(system, parameters)

    assert not result.converged
    assert result.status == "degenerate_constraint_geometry"
    assert result.failure_code == "constraint_pair_has_zero_distance"
    assert len(result.iterations) == 2
    assert result.iterations[-1].failure_code == "constraint_pair_has_zero_distance"
    assert torch.equal(result.system.coordinates, system.coordinates)


def test_v2_extension_rejects_duplicate_invalid_and_out_of_topology_rows() -> None:
    system = _star_system()
    base = _star_base_parameters(system)
    improper = HarmonicOutOfPlaneImproperParameter(0, 1, 2, 3, 0.0, 10.0)
    with pytest.raises(ReferenceForceFieldV2Error, match="improper star"):
        ReferenceForceFieldV2Parameters(
            base_parameters=base,
            impropers=(
                improper,
                HarmonicOutOfPlaneImproperParameter(0, 2, 1, 3, 0.0, 10.0),
            ),
        )
    with pytest.raises(ReferenceForceFieldV2Error, match="constraint pair"):
        ReferenceForceFieldV2Parameters(
            base_parameters=base,
            constraints=(
                DistanceConstraintParameter(0, 1, 1.0),
                DistanceConstraintParameter(1, 0, 1.1),
            ),
        )
    with pytest.raises(ReferenceForceFieldV2Error, match="distinct"):
        HarmonicOutOfPlaneImproperParameter(0, 1, 1, 3, 0.0, 10.0)
    with pytest.raises(ReferenceForceFieldV2Error, match="external evidence"):
        ReferenceForceFieldV2Parameters(
            base_parameters=base,
            scientifically_validated=True,
        )

    out_of_range = ReferenceForceFieldV2Parameters(
        base_parameters=base,
        impropers=(
            HarmonicOutOfPlaneImproperParameter(0, 1, 2, 4, 0.0, 10.0),
        ),
    )
    with pytest.raises(ReferenceForceFieldV2ApplicabilityError, match="outside topology"):
        evaluate_reference_force_field_v2(
            system,
            _neighbors(system),
            out_of_range,
        )


def test_collinear_improper_plane_fails_closed() -> None:
    coordinates = torch.tensor(
        [[
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [0.4, 0.3, 0.2],
        ]],
        dtype=torch.float64,
    )
    system = _star_system(coordinates)
    # Coordinates are not part of topology identity.  Reuse a valid explicit base
    # parameter set so the failure under test comes from the v2 improper plane,
    # not from constructing a zero/straight v1 equilibrium angle.
    parameters = _star_v2_parameters(_star_system())
    with pytest.raises(ReferenceForceFieldV2ApplicabilityError, match="collinear"):
        evaluate_reference_force_field_v2(
            system,
            _neighbors(system),
            parameters,
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        ({"max_iterations": 0}, "max_iterations"),
        ({"max_iterations": 1001}, "max_iterations"),
        ({"max_pair_correction_angstrom": 0.0}, "max_pair_correction"),
        ({"convergence_tolerance_scale": 1.0}, "frozen value"),
    ),
)
def test_constraint_projection_config_is_bounded(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(ReferenceForceFieldV2Error, match=message):
        DistanceConstraintProjectionConfig(**kwargs)


def test_constraint_projection_rejects_non_float64_and_multimodel() -> None:
    system = _free_system(
        torch.tensor([[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]]], dtype=torch.float64)
    )
    parameters = _free_v2_parameters(
        system,
        (DistanceConstraintParameter(0, 1, 1.0),),
    )
    float32_system = system.with_coordinates(
        system.coordinates.float(),
        operation="float32",
    )
    with pytest.raises(ReferenceForceFieldV2Error, match="CPU float64"):
        project_distance_constraints(float32_system, parameters)
    multimodel = replace(
        system,
        coordinates=torch.cat((system.coordinates, system.coordinates), dim=0),
    )
    with pytest.raises(ReferenceForceFieldV2Error, match="exactly one model"):
        project_distance_constraints(multimodel, parameters)
