from __future__ import annotations

from dataclasses import replace
import math

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics import (
    AtomNonbondedParameter,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    PairScalingParameter,
    PeriodicTorsionParameter,
    ReferenceApplicabilityDomain,
    ReferenceForceFieldParameters,
    ReferenceForceFieldProvider,
    ReferenceParameterError,
    ReferencePhysicsApplicabilityError,
    compose_energy_terms,
    evaluate_reference_force_field,
)


def _system(coordinates: torch.Tensor | None = None) -> AllAtomSystem:
    coords = coordinates
    if coords is None:
        coords = torch.tensor(
            [[
                [0.0, 0.0, 0.0],
                [1.45, 0.0, 0.0],
                [2.25, 1.15, 0.0],
                [3.35, 1.30, 0.85],
            ]],
            dtype=torch.float64,
        )
    atoms = tuple(
        Atom(
            index=index,
            name=f"C{index + 1}",
            element="C",
            atomic_number=6,
            residue_index=0,
        )
        for index in range(4)
    )
    bonds = tuple(
        Bond(index=index, atom_i=index, atom_j=index + 1, order=1.0, source="unit")
        for index in range(3)
    )
    return AllAtomSystem(
        system_id="reference-physics-fixture",
        atoms=atoms,
        bonds=bonds,
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
        provenance=StructureProvenance(
            source_format="unit",
            source_id="reference-physics-fixture",
            source_sha256="a" * 64,
            parser_name="unit",
            parser_version="1",
            operations=("unit_fixture",),
            source_digest_verified=True,
            transformation_chain_verified=True,
        ),
    )


def _parameters(
    *,
    complete: bool = True,
    system: AllAtomSystem | None = None,
    metadata: dict[str, object] | None = None,
) -> ReferenceForceFieldParameters:
    bound_system = _system() if system is None else system
    atom_parameters = tuple(
        AtomNonbondedParameter(
            atom_index=index,
            sigma_angstrom=3.4,
            epsilon_kcal_per_mol=0.08 + 0.01 * index,
            charge_e=(-0.15, 0.10, 0.10, -0.05)[index],
        )
        for index in range(4 if complete else 3)
    )
    return ReferenceForceFieldParameters(
        parameter_set_id="unit-reference",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(bound_system),
        atom_parameters=atom_parameters,
        bonds=(
            HarmonicBondParameter(0, 1, 1.45, 200.0),
            HarmonicBondParameter(1, 2, math.sqrt(0.8**2 + 1.15**2), 180.0),
            HarmonicBondParameter(2, 3, math.sqrt(1.1**2 + 0.15**2 + 0.85**2), 160.0),
        ),
        angles=(
            HarmonicAngleParameter(0, 1, 2, 2.0, 45.0),
            HarmonicAngleParameter(1, 2, 3, 2.1, 40.0),
        ),
        torsions=(
            PeriodicTorsionParameter(0, 1, 2, 3, 3, 0.0, 0.5),
        ),
        excluded_pairs=((0, 1), (1, 2), (2, 3), (0, 2), (1, 3)),
        scaled_pairs=(PairScalingParameter(0, 3, 0.5, 0.8333333333),),
        cutoff_angstrom=6.0,
        switch_start_angstrom=5.0,
        dielectric=4.0,
        screening_kappa_per_angstrom=0.1,
        applicability_domain=ReferenceApplicabilityDomain(max_atoms=16),
        scientifically_validated=False,
        metadata={} if metadata is None else metadata,
    )


def _neighbors(system: AllAtomSystem, cutoff: float = 6.0):
    return build_compact_radius_graph(
        system.coordinates,
        RadiusGraphConfig(
            cutoff_angstrom=cutoff,
            max_neighbors=8,
            max_atoms_per_cell=16,
        ),
        cell=system.cell,
    )


def test_reference_terms_are_finite_conservative_and_not_composable_by_default() -> None:
    system = _system()
    evaluation = evaluate_reference_force_field(system, _neighbors(system), _parameters())
    assert evaluation.execution_complete
    assert not evaluation.scientifically_validated
    assert evaluation.term.energy.shape == (1,)
    assert evaluation.term.forces.shape == (1, 4, 3)
    assert torch.isfinite(evaluation.term.energy).all()
    assert torch.isfinite(evaluation.term.forces).all()
    assert set(evaluation.component_energies) == {
        "harmonic_bond",
        "harmonic_angle",
        "periodic_torsion",
        "lennard_jones",
        "screened_coulomb",
    }
    assert evaluation.term.validated_for_composition is False
    assert evaluation.term.energy_descriptor.unit == "kcal/mol"
    assert evaluation.term.force_descriptor.unit == "kcal/mol/angstrom"
    composition = compose_energy_terms(evaluation.term, None)
    assert composition.total_energy is None
    assert composition.blockers == ("independent_physics_energy_unvalidated",)


def test_reference_force_matches_finite_difference() -> None:
    system = _system()
    parameters = _parameters()
    evaluation = evaluate_reference_force_field(system, _neighbors(system), parameters)
    epsilon = 1.0e-5
    plus_coordinates = system.coordinates.clone()
    minus_coordinates = system.coordinates.clone()
    plus_coordinates[0, 3, 0] += epsilon
    minus_coordinates[0, 3, 0] -= epsilon
    plus = system.with_coordinates(plus_coordinates, operation="finite_difference_plus")
    minus = system.with_coordinates(minus_coordinates, operation="finite_difference_minus")
    plus_energy = evaluate_reference_force_field(plus, _neighbors(plus), parameters).term.energy[0]
    minus_energy = evaluate_reference_force_field(minus, _neighbors(minus), parameters).term.energy[0]
    numerical_force = -float(((plus_energy - minus_energy) / (2.0 * epsilon)).item())
    analytic_force = float(evaluation.term.forces[0, 3, 0].item())
    assert analytic_force == pytest.approx(numerical_force, rel=2.0e-4, abs=2.0e-4)


def test_translation_rotation_invariance_and_newton_third_law() -> None:
    system = _system()
    parameters = _parameters()
    original = evaluate_reference_force_field(system, _neighbors(system), parameters)
    rotation = torch.tensor(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=torch.float64,
    )
    transformed_coordinates = system.coordinates @ rotation.T + torch.tensor(
        [4.0, -3.0, 2.0], dtype=torch.float64
    )
    transformed_system = system.with_coordinates(
        transformed_coordinates,
        operation="rigid_transform",
    )
    transformed = evaluate_reference_force_field(
        transformed_system,
        _neighbors(transformed_system),
        parameters,
    )
    assert transformed.term.energy.item() == pytest.approx(original.term.energy.item(), abs=1.0e-9)
    expected_forces = original.term.forces @ rotation.T
    assert torch.allclose(transformed.term.forces, expected_forces, atol=2.0e-8, rtol=2.0e-8)
    assert torch.allclose(
        original.term.forces.sum(dim=1),
        torch.zeros((1, 3), dtype=torch.float64),
        atol=2.0e-8,
        rtol=0.0,
    )


def test_switch_makes_nonbonded_energy_and_force_continuous_at_cutoff() -> None:
    def two_atom(distance: float) -> AllAtomSystem:
        base = _system(
            torch.tensor(
                [[[0.0, 0.0, 0.0], [distance, 0.0, 0.0], [20.0, 0.0, 0.0], [30.0, 0.0, 0.0]]],
                dtype=torch.float64,
            )
        )
        return replace(base, bonds=())

    parameters = ReferenceForceFieldParameters(
        parameter_set_id="cutoff-unit",
        parameter_set_version="1",
        topology_sha256=canonical_topology_sha256(two_atom(1.0)),
        atom_parameters=tuple(
            AtomNonbondedParameter(index, 3.0, 0.1, 0.0) for index in range(4)
        ),
        excluded_pairs=((0, 2), (0, 3), (1, 2), (1, 3), (2, 3)),
        cutoff_angstrom=5.0,
        switch_start_angstrom=4.0,
        applicability_domain=ReferenceApplicabilityDomain(max_atoms=8),
    )
    below = two_atom(5.0 - 1.0e-4)
    above = two_atom(5.0 + 1.0e-4)
    below_eval = evaluate_reference_force_field(below, _neighbors(below, 5.0), parameters)
    above_eval = evaluate_reference_force_field(above, _neighbors(above, 5.0), parameters)
    assert abs(float(below_eval.term.energy.item())) < 1.0e-9
    assert abs(float(below_eval.term.forces[0, 1, 0].item())) < 1.0e-5
    assert float(above_eval.term.energy.item()) == pytest.approx(0.0, abs=1.0e-14)
    assert float(above_eval.term.forces.abs().max().item()) == pytest.approx(0.0, abs=1.0e-14)


def test_periodic_nonbonded_terms_use_neighbor_minimum_image_shift() -> None:
    periodic_coordinates = torch.tensor(
        [[[0.1, 0.0, 0.0], [9.7, 0.0, 0.0], [3.0, 0.0, 0.0], [6.0, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    direct_coordinates = periodic_coordinates.clone()
    direct_coordinates[0, 1, 0] = -0.3
    periodic = replace(
        _system(periodic_coordinates),
        bonds=(),
        cell=UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64),
    )
    direct = replace(_system(direct_coordinates), bonds=())
    parameters = ReferenceForceFieldParameters(
        parameter_set_id="periodic-unit",
        parameter_set_version="1",
        topology_sha256=canonical_topology_sha256(periodic),
        atom_parameters=tuple(
            AtomNonbondedParameter(index, 0.3, 0.1, 0.05) for index in range(4)
        ),
        cutoff_angstrom=1.0,
        switch_start_angstrom=0.8,
        applicability_domain=ReferenceApplicabilityDomain(max_atoms=8),
    )

    periodic_evaluation = evaluate_reference_force_field(
        periodic,
        _neighbors(periodic, 1.0),
        parameters,
    )
    direct_evaluation = evaluate_reference_force_field(
        direct,
        _neighbors(direct, 1.0),
        replace(
            parameters,
            topology_sha256=canonical_topology_sha256(direct),
        ),
    )

    assert periodic_evaluation.term.energy.item() == pytest.approx(
        direct_evaluation.term.energy.item(),
        abs=1.0e-12,
    )
    assert torch.allclose(
        periodic_evaluation.term.forces,
        direct_evaluation.term.forces,
        atol=1.0e-10,
        rtol=1.0e-10,
    )


def test_applicability_fails_closed_for_missing_parameters_and_short_neighbor_cutoff() -> None:
    system = _system()
    with pytest.raises(ReferencePhysicsApplicabilityError, match="nonbonded_parameters"):
        evaluate_reference_force_field(system, _neighbors(system), _parameters(complete=False))
    with pytest.raises(ReferencePhysicsApplicabilityError, match="neighbor_cutoff"):
        evaluate_reference_force_field(system, _neighbors(system, 4.0), _parameters())


def test_parameter_contract_requires_evidence_before_scientific_validation() -> None:
    base = _parameters()
    with pytest.raises(ValueError, match="verified evidence receipt"):
        ReferenceForceFieldParameters(
            **{
                **base.__dict__,
                "scientifically_validated": True,
                "validation_evidence_sha256": "",
            }
        )
    with pytest.raises(ValueError, match="verified evidence receipt"):
        replace(
            base,
            scientifically_validated=True,
            validation_evidence_sha256="0" * 64,
        )
    with pytest.raises(ValueError, match="verified evidence receipt"):
        replace(base, validation_evidence_sha256="0" * 64)


@pytest.mark.parametrize(
    "factory",
    (
        lambda: HarmonicBondParameter(0.5, 1, 1.0, 1.0),
        lambda: HarmonicAngleParameter(0, 1.5, 2, 1.0, 1.0),
        lambda: PeriodicTorsionParameter(0, 1, 2.5, 3, 1, 0.0, 1.0),
        lambda: PeriodicTorsionParameter(0, 1, 2, 3, 1.5, 0.0, 1.0),
        lambda: AtomNonbondedParameter(0.5, 1.0, 0.0, 0.0),
        lambda: PairScalingParameter(0, 1.5, 1.0, 1.0),
        lambda: ReferenceApplicabilityDomain(max_atoms=1.5),
    ),
)
def test_parameter_contract_rejects_nonintegral_indices_and_periodicity(factory) -> None:
    with pytest.raises(ReferenceParameterError, match="integer"):
        factory()


def test_parameter_contract_normalizes_numbers_and_freezes_metadata_snapshot() -> None:
    torsion = PeriodicTorsionParameter(0.0, 1.0, 2.0, 3.0, 3.0, 0, 1)
    assert torsion.periodicity == 3
    assert isinstance(torsion.periodicity, int)
    assert isinstance(torsion.phase_radians, float)
    assert isinstance(torsion.amplitude_kcal_per_mol, float)

    source_metadata = {"nested": {"values": [1, 2]}}
    parameters = _parameters(metadata=source_metadata)
    provider = ReferenceForceFieldProvider(parameters)
    fingerprint = parameters.fingerprint_sha256
    source_metadata["nested"]["values"].append(3)

    assert parameters.fingerprint_sha256 == fingerprint
    assert provider.parameter_fingerprint_sha256 == fingerprint
    assert parameters.to_dict()["metadata"] == {"nested": {"values": [1, 2]}}
    with pytest.raises(TypeError):
        parameters.metadata["new"] = True
    with pytest.raises(TypeError):
        parameters.metadata["nested"]["new"] = True


def test_parameter_topology_binding_and_bond_coverage_fail_closed() -> None:
    system = _system()
    parameters = _parameters(system=system)

    with pytest.raises(ReferencePhysicsApplicabilityError, match="bond_parameters"):
        evaluate_reference_force_field(
            system,
            _neighbors(system),
            replace(parameters, bonds=parameters.bonds[:-1]),
        )

    wrong_atoms = list(system.atoms)
    wrong_atoms[0] = replace(wrong_atoms[0], element="O", atomic_number=8)
    wrong_system = replace(system, atoms=tuple(wrong_atoms))
    with pytest.raises(ReferencePhysicsApplicabilityError, match="topology_identity"):
        evaluate_reference_force_field(
            wrong_system,
            _neighbors(wrong_system),
            parameters,
        )

    with pytest.raises(ReferenceParameterError, match="bond parameter definitions"):
        replace(parameters, bonds=(*parameters.bonds, parameters.bonds[0]))
    with pytest.raises(ReferenceParameterError, match="angle parameter definitions"):
        replace(
            parameters,
            angles=(
                *parameters.angles,
                HarmonicAngleParameter(2, 1, 0, 2.0, 45.0),
            ),
        )
    with pytest.raises(ReferenceParameterError, match="torsion parameter definitions"):
        replace(parameters, torsions=(*parameters.torsions, parameters.torsions[0]))
    with pytest.raises(ReferenceParameterError, match="torsion parameter definitions"):
        replace(
            parameters,
            torsions=(
                *parameters.torsions,
                PeriodicTorsionParameter(3, 2, 1, 0, 3, 0.0, 0.5),
            ),
        )


def test_stale_neighbor_graph_is_rejected_against_current_coordinates() -> None:
    far_coordinates = torch.tensor(
        [[[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [20.0, 0.0, 0.0], [30.0, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    near_coordinates = far_coordinates.clone()
    near_coordinates[0, 1, 0] = 1.0
    far = replace(_system(far_coordinates), bonds=())
    near = replace(_system(near_coordinates), bonds=())
    stale = _neighbors(far, 5.0)
    fresh = _neighbors(near, 5.0)
    parameters = ReferenceForceFieldParameters(
        parameter_set_id="neighbor-binding-unit",
        parameter_set_version="1",
        topology_sha256=canonical_topology_sha256(near),
        atom_parameters=tuple(
            AtomNonbondedParameter(index, 0.5, 1.0, 0.0) for index in range(4)
        ),
        cutoff_angstrom=5.0,
        switch_start_angstrom=4.0,
        applicability_domain=ReferenceApplicabilityDomain(max_atoms=8),
    )

    assert stale.pair_count == 0
    assert fresh.pair_count == 2
    with pytest.raises(ReferencePhysicsApplicabilityError, match="neighbor_graph_not_bound"):
        evaluate_reference_force_field(near, stale, parameters)
    assert evaluate_reference_force_field(near, fresh, parameters).execution_complete


def test_non_angstrom_coordinate_unit_is_rejected() -> None:
    system = replace(_system(), coordinate_unit="nm")
    parameters = _parameters(system=system)

    with pytest.raises(ReferencePhysicsApplicabilityError, match="coordinate_unit"):
        evaluate_reference_force_field(system, _neighbors(system), parameters)


def test_periodic_cutoff_must_stay_strictly_below_half_smallest_box_length() -> None:
    coordinates = torch.tensor(
        [[[0.0, 0.0, 0.0], [4.9, 0.0, 0.0], [2.0, 2.0, 0.0], [3.0, -2.0, 0.0]]],
        dtype=torch.float64,
    )
    system = replace(
        _system(coordinates),
        bonds=(),
        cell=UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64),
    )
    parameters = ReferenceForceFieldParameters(
        parameter_set_id="periodic-half-box-unit",
        parameter_set_version="1",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=tuple(
            AtomNonbondedParameter(index, 3.0, 0.1, 0.0) for index in range(4)
        ),
        cutoff_angstrom=5.0,
        switch_start_angstrom=4.0,
        applicability_domain=ReferenceApplicabilityDomain(max_atoms=8),
    )

    with pytest.raises(ReferencePhysicsApplicabilityError, match="half_smallest_box"):
        evaluate_reference_force_field(system, _neighbors(system, 5.0), parameters)
