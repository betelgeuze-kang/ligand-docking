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
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (  # noqa: E402
    ReferenceForceFieldV2Parameters,
)
from betelgeuze_engine_v2.physics.reference_parameters import (  # noqa: E402
    COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
    AtomNonbondedParameter,
    ReferenceApplicabilityDomain,
    ReferenceForceFieldParameters,
)
from betelgeuze_engine_v2.physics.reference_solvation import (  # noqa: E402
    REFERENCE_FIXED_BORN_PRIMARY_REFERENCE_DOI,
    REFERENCE_FIXED_BORN_SCIENTIFIC_BLOCKERS,
    FixedBornAtomParameter,
    FixedBornPolarSolvationParameters,
    ReferenceFixedBornSolvationApplicabilityError,
    ReferenceFixedBornSolvationError,
    evaluate_fixed_born_polar_solvation,
    evaluate_reference_force_field_v2_with_fixed_born,
)


def _provenance(source_id: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=source_id,
        source_sha256="c" * 64,
        parser_name="unit",
        parser_version="1",
        operations=("unit_fixture",),
        source_digest_verified=True,
        transformation_chain_verified=True,
    )


def _system(
    coordinates: torch.Tensor | None = None,
    *,
    cell: UnitCell | None = None,
) -> AllAtomSystem:
    coords = coordinates
    if coords is None:
        coords = torch.tensor(
            [[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]]], dtype=torch.float64
        )
    return AllAtomSystem(
        system_id="fixed-born-pair",
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
        coordinates=coords,
        provenance=_provenance("fixed-born-pair"),
        cell=cell,
    )


def _forcefield_parameters(
    system: AllAtomSystem,
    *,
    charges: tuple[float, float] = (1.0, -1.0),
    metadata: dict[str, object] | None = None,
) -> ReferenceForceFieldV2Parameters:
    return ReferenceForceFieldV2Parameters(
        base_parameters=ReferenceForceFieldParameters(
            parameter_set_id="fixed-born-charge-source",
            parameter_set_version="1.0.0",
            topology_sha256=canonical_topology_sha256(system),
            atom_parameters=tuple(
                AtomNonbondedParameter(index, 1.0, 0.0, charges[index])
                for index in range(2)
            ),
            excluded_pairs=((0, 1),),
            cutoff_angstrom=4.0,
            switch_start_angstrom=3.0,
            applicability_domain=ReferenceApplicabilityDomain(max_atoms=8),
        ),
        metadata={} if metadata is None else metadata,
    )


def _solvation_parameters(
    system: AllAtomSystem,
    forcefield: ReferenceForceFieldV2Parameters,
    *,
    radii: tuple[float, float] = (1.5, 2.0),
) -> FixedBornPolarSolvationParameters:
    return FixedBornPolarSolvationParameters(
        parameter_set_id="unit-fixed-effective-born-radii",
        parameter_set_version="1.0.0",
        parameter_source_sha256="d" * 64,
        topology_sha256=canonical_topology_sha256(system),
        charge_parameter_fingerprint_sha256=forcefield.fingerprint_sha256,
        atom_parameters=tuple(
            FixedBornAtomParameter(index, radii[index]) for index in range(2)
        ),
        metadata={"scope": "unit_only"},
    )


def _neighbors(system: AllAtomSystem):
    return build_compact_radius_graph(
        system.coordinates,
        RadiusGraphConfig(cutoff_angstrom=4.0, max_neighbors=4, max_atoms_per_cell=8),
        cell=system.cell,
    )


def _expected_components(
    distance: float,
    charges: tuple[float, float] = (1.0, -1.0),
    radii: tuple[float, float] = (1.5, 2.0),
    solute_dielectric: float = 1.0,
    solvent_dielectric: float = 78.5,
) -> tuple[float, float]:
    coefficient = -0.5 * COULOMB_KCAL_ANGSTROM_PER_MOL_E2 * (
        1.0 / solute_dielectric - 1.0 / solvent_dielectric
    )
    self_energy = coefficient * sum(
        charge**2 / radius for charge, radius in zip(charges, radii)
    )
    radius_product = radii[0] * radii[1]
    pair_function = math.sqrt(
        distance**2
        + radius_product * math.exp(-(distance**2) / (4.0 * radius_product))
    )
    pair_energy = coefficient * 2.0 * charges[0] * charges[1] / pair_function
    return self_energy, pair_energy


def test_fixed_born_energy_matches_explicit_still_pair_function() -> None:
    system = _system()
    forcefield = _forcefield_parameters(system)
    parameters = _solvation_parameters(system, forcefield)
    evaluation = evaluate_fixed_born_polar_solvation(
        system, forcefield, parameters
    )
    expected_self, expected_pair = _expected_components(2.0)

    assert evaluation.component_energies["fixed_born_self_polar"].item() == (
        pytest.approx(expected_self, abs=1.0e-12)
    )
    assert evaluation.component_energies["fixed_born_pair_polar"].item() == (
        pytest.approx(expected_pair, abs=1.0e-12)
    )
    assert evaluation.term.energy.item() == pytest.approx(
        expected_self + expected_pair, abs=1.0e-12
    )
    assert evaluation.pair_count == 1
    assert evaluation.term.validated_for_composition is False
    assert evaluation.scientific_blockers == REFERENCE_FIXED_BORN_SCIENTIFIC_BLOCKERS
    assert not evaluation.scientifically_validated
    assert evaluation.to_dict()["primary_reference_doi"] == (
        REFERENCE_FIXED_BORN_PRIMARY_REFERENCE_DOI
    )
    assert parameters.to_dict()["nonpolar_solvation"] == "not_implemented"
    assert parameters.to_dict()["effective_radius_semantics"] == (
        "caller_supplied_fixed_not_geometry_derived"
    )
    assert len(parameters.fingerprint_sha256) == 64
    with pytest.raises(TypeError):
        parameters.metadata["new"] = True


def test_fixed_born_force_matches_finite_difference_and_is_balanced() -> None:
    system = _system()
    forcefield = _forcefield_parameters(system)
    parameters = _solvation_parameters(system, forcefield)
    evaluation = evaluate_fixed_born_polar_solvation(
        system, forcefield, parameters
    )
    step = 1.0e-5
    plus_coordinates = system.coordinates.clone()
    minus_coordinates = system.coordinates.clone()
    plus_coordinates[0, 1, 0] += step
    minus_coordinates[0, 1, 0] -= step
    plus = system.with_coordinates(plus_coordinates, operation="finite_difference_plus")
    minus = system.with_coordinates(minus_coordinates, operation="finite_difference_minus")
    plus_energy = evaluate_fixed_born_polar_solvation(
        plus, forcefield, parameters
    ).term.energy[0]
    minus_energy = evaluate_fixed_born_polar_solvation(
        minus, forcefield, parameters
    ).term.energy[0]
    numerical_force = -float(((plus_energy - minus_energy) / (2.0 * step)).item())
    analytic_force = float(evaluation.term.forces[0, 1, 0].item())

    assert analytic_force == pytest.approx(numerical_force, rel=2.0e-8, abs=2.0e-8)
    assert torch.allclose(
        evaluation.term.forces.sum(dim=1),
        torch.zeros((1, 3), dtype=torch.float64),
        atol=1.0e-12,
        rtol=0.0,
    )


def test_fixed_born_is_rigid_transform_and_permutation_covariant() -> None:
    system = _system()
    forcefield = _forcefield_parameters(system)
    parameters = _solvation_parameters(system, forcefield)
    original = evaluate_fixed_born_polar_solvation(system, forcefield, parameters)
    rotation = torch.tensor(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=torch.float64,
    )
    transformed_system = system.with_coordinates(
        system.coordinates @ rotation.T
        + torch.tensor([4.0, -3.0, 2.0], dtype=torch.float64),
        operation="rigid_transform",
    )
    transformed = evaluate_fixed_born_polar_solvation(
        transformed_system, forcefield, parameters
    )
    assert transformed.term.energy.item() == pytest.approx(
        original.term.energy.item(), abs=1.0e-12
    )
    assert torch.allclose(
        transformed.term.forces,
        original.term.forces @ rotation.T,
        atol=2.0e-12,
        rtol=0.0,
    )

    swapped_system = system.with_coordinates(
        system.coordinates[:, [1, 0], :], operation="swap_atoms"
    )
    swapped_forcefield = _forcefield_parameters(
        swapped_system, charges=(-1.0, 1.0)
    )
    swapped_parameters = _solvation_parameters(
        swapped_system, swapped_forcefield, radii=(2.0, 1.5)
    )
    swapped = evaluate_fixed_born_polar_solvation(
        swapped_system, swapped_forcefield, swapped_parameters
    )
    assert swapped.term.energy.item() == pytest.approx(
        original.term.energy.item(), abs=1.0e-12
    )
    assert torch.allclose(
        swapped.term.forces,
        original.term.forces[:, [1, 0], :],
        atol=2.0e-12,
        rtol=0.0,
    )


def test_solvated_v2_evaluator_adds_energy_force_and_components() -> None:
    system = _system()
    forcefield = _forcefield_parameters(system)
    parameters = _solvation_parameters(system, forcefield)
    solvation = evaluate_fixed_born_polar_solvation(
        system, forcefield, parameters
    )
    combined = evaluate_reference_force_field_v2_with_fixed_born(
        system, _neighbors(system), forcefield, parameters
    )

    assert torch.equal(combined.term.energy, solvation.term.energy)
    assert torch.equal(combined.term.forces, solvation.term.forces)
    assert tuple(combined.component_energies)[-2:] == (
        "fixed_born_self_polar",
        "fixed_born_pair_polar",
    )
    assert combined.constraints_satisfied
    assert combined.term.validated_for_composition is False
    assert combined.to_dict()["claim_safe"] is False
    assert not combined.scientifically_validated


def test_fixed_born_parameter_schema_fails_closed() -> None:
    system = _system()
    forcefield = _forcefield_parameters(system)
    common = {
        "parameter_set_id": "unit",
        "parameter_set_version": "1",
        "parameter_source_sha256": "d" * 64,
        "topology_sha256": canonical_topology_sha256(system),
        "charge_parameter_fingerprint_sha256": forcefield.fingerprint_sha256,
        "atom_parameters": (
            FixedBornAtomParameter(0, 1.5),
            FixedBornAtomParameter(1, 2.0),
        ),
    }
    with pytest.raises(ReferenceFixedBornSolvationError, match="greater"):
        FixedBornPolarSolvationParameters(
            **common, solute_dielectric=80.0, solvent_dielectric=78.5
        )
    with pytest.raises(ReferenceFixedBornSolvationError, match="independent evidence"):
        FixedBornPolarSolvationParameters(
            **common, scientifically_validated=True
        )
    with pytest.raises(ReferenceFixedBornSolvationError, match="unique"):
        FixedBornPolarSolvationParameters(
            **{
                **common,
                "atom_parameters": (
                    FixedBornAtomParameter(0, 1.5),
                    FixedBornAtomParameter(0, 2.0),
                ),
            }
        )
    with pytest.raises(ReferenceFixedBornSolvationError, match="FixedBornAtomParameter"):
        FixedBornPolarSolvationParameters(
            **{**common, "atom_parameters": ("invalid",)}
        )
    with pytest.raises(ReferenceFixedBornSolvationError, match="effective_born"):
        FixedBornAtomParameter(0, 0.0)
    with pytest.raises(ReferenceFixedBornSolvationError, match="SHA-256"):
        FixedBornPolarSolvationParameters(
            **{**common, "parameter_source_sha256": "not-a-digest"}
        )


def test_fixed_born_identity_coverage_and_distance_fail_closed() -> None:
    system = _system()
    forcefield = _forcefield_parameters(system)
    parameters = _solvation_parameters(system, forcefield)
    crosswired = _forcefield_parameters(system, metadata={"different": True})
    with pytest.raises(
        ReferenceFixedBornSolvationApplicabilityError,
        match="charge parameter fingerprint mismatch",
    ):
        evaluate_fixed_born_polar_solvation(system, crosswired, parameters)

    incomplete = FixedBornPolarSolvationParameters(
        parameter_set_id="incomplete",
        parameter_set_version="1",
        parameter_source_sha256="d" * 64,
        topology_sha256=canonical_topology_sha256(system),
        charge_parameter_fingerprint_sha256=forcefield.fingerprint_sha256,
        atom_parameters=(FixedBornAtomParameter(0, 1.5),),
    )
    with pytest.raises(
        ReferenceFixedBornSolvationApplicabilityError,
        match="coverage",
    ):
        evaluate_fixed_born_polar_solvation(system, forcefield, incomplete)

    overlapping = system.with_coordinates(
        torch.tensor(
            [[[0.0, 0.0, 0.0], [0.1, 0.0, 0.0]]], dtype=torch.float64
        ),
        operation="overlap",
    )
    with pytest.raises(
        ReferenceFixedBornSolvationApplicabilityError,
        match="below minimum_pair_distance",
    ):
        evaluate_fixed_born_polar_solvation(overlapping, forcefield, parameters)


def test_fixed_born_rejects_periodic_non_float64_and_multimodel() -> None:
    system = _system()
    forcefield = _forcefield_parameters(system)
    parameters = _solvation_parameters(system, forcefield)
    periodic = replace(
        system,
        cell=UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64),
    )
    with pytest.raises(
        ReferenceFixedBornSolvationApplicabilityError, match="periodic cells"
    ):
        evaluate_fixed_born_polar_solvation(periodic, forcefield, parameters)
    float32_system = system.with_coordinates(
        system.coordinates.float(), operation="float32"
    )
    with pytest.raises(
        ReferenceFixedBornSolvationApplicabilityError, match="CPU float64"
    ):
        evaluate_fixed_born_polar_solvation(
            float32_system, forcefield, parameters
        )
    multimodel = replace(
        system,
        coordinates=torch.cat((system.coordinates, system.coordinates), dim=0),
    )
    with pytest.raises(
        ReferenceFixedBornSolvationApplicabilityError, match="exactly one model"
    ):
        evaluate_fixed_born_polar_solvation(multimodel, forcefield, parameters)
