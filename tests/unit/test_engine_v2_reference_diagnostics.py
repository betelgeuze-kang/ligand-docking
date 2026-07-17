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
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_diagnostics import (  # noqa: E402
    REFERENCE_TERM_DIAGNOSTICS_MAX_ATOMS,
    REFERENCE_TERM_DIAGNOSTICS_SCIENTIFIC_BLOCKERS,
    REFERENCE_TERM_NAMES,
    REFERENCE_VIRIAL_CONVENTION,
    ReferenceTermDiagnosticsConfig,
    ReferenceTermDiagnosticsError,
    evaluate_reference_term_diagnostics,
)
from betelgeuze_engine_v2.physics.reference_forcefield import (  # noqa: E402
    evaluate_reference_force_field,
)
from betelgeuze_engine_v2.physics.reference_parameters import (  # noqa: E402
    AtomNonbondedParameter,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    PairScalingParameter,
    PeriodicTorsionParameter,
    ReferenceApplicabilityDomain,
    ReferenceForceFieldParameters,
)
from betelgeuze_engine_v2.physics.reference_validation_artifact_binding import (  # noqa: E402
    FROZEN_REFERENCE_FORCEFIELD_SOURCE_SHA256,
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
        system_id="reference-diagnostics-fixture",
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
            source_id="reference-diagnostics-fixture",
            source_sha256="a" * 64,
            parser_name="unit",
            parser_version="1",
            operations=("unit_fixture",),
            source_digest_verified=True,
            transformation_chain_verified=True,
        ),
    )


def _parameters(system: AllAtomSystem | None = None) -> ReferenceForceFieldParameters:
    bound_system = _system() if system is None else system
    return ReferenceForceFieldParameters(
        parameter_set_id="diagnostics-unit-reference",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(bound_system),
        atom_parameters=tuple(
            AtomNonbondedParameter(
                atom_index=index,
                sigma_angstrom=3.4,
                epsilon_kcal_per_mol=0.08 + 0.01 * index,
                charge_e=(-0.15, 0.10, 0.10, -0.05)[index],
            )
            for index in range(4)
        ),
        bonds=(
            HarmonicBondParameter(0, 1, 1.45, 200.0),
            HarmonicBondParameter(1, 2, math.sqrt(0.8**2 + 1.15**2), 180.0),
            HarmonicBondParameter(
                2,
                3,
                math.sqrt(1.1**2 + 0.15**2 + 0.85**2),
                160.0,
            ),
        ),
        angles=(
            HarmonicAngleParameter(0, 1, 2, 2.0, 45.0),
            HarmonicAngleParameter(1, 2, 3, 2.1, 40.0),
        ),
        torsions=(PeriodicTorsionParameter(0, 1, 2, 3, 3, 0.0, 0.5),),
        excluded_pairs=((0, 1), (1, 2), (2, 3), (0, 2), (1, 3)),
        scaled_pairs=(PairScalingParameter(0, 3, 0.5, 0.8333333333),),
        cutoff_angstrom=6.0,
        switch_start_angstrom=5.0,
        dielectric=4.0,
        screening_kappa_per_angstrom=0.1,
        applicability_domain=ReferenceApplicabilityDomain(max_atoms=16),
    )


def _config(**overrides: object) -> ReferenceTermDiagnosticsConfig:
    values: dict[str, object] = {
        "max_atoms": 16,
        "max_neighbors": 8,
        "max_atoms_per_cell": 16,
    }
    values.update(overrides)
    return ReferenceTermDiagnosticsConfig(**values)


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


def test_per_term_force_and_virial_diagnostics_are_complete_and_deterministic() -> None:
    system = _system()
    parameters = _parameters(system)
    config = _config()

    first = evaluate_reference_term_diagnostics(system, parameters, config)
    second = evaluate_reference_term_diagnostics(system, parameters, config)

    assert first.diagnostics_complete
    assert first.force_diagnostics_complete
    assert first.virial_diagnostics_complete
    assert first.blockers == ()
    assert tuple(first.component_forces) == REFERENCE_TERM_NAMES
    assert tuple(first.component_virials) == REFERENCE_TERM_NAMES
    assert first.expected_perturbation_count == 24
    assert first.observed_perturbation_count == 24
    assert first.failed_perturbation_count == 0
    assert first.evaluator_source_sha256 == FROZEN_REFERENCE_FORCEFIELD_SOURCE_SHA256
    assert first.scientific_blockers == REFERENCE_TERM_DIAGNOSTICS_SCIENTIFIC_BLOCKERS
    assert not first.scientifically_validated
    assert first.to_dict() == second.to_dict()
    assert first.to_dict()["virial_convention"] == REFERENCE_VIRIAL_CONVENTION
    assert all(row.status == "success" for row in first.observations)

    numerical_total = first.total_component_force()
    assert numerical_total is not None
    assert torch.allclose(
        numerical_total,
        first.base_evaluation.term.forces,
        atol=config.force_consistency_atol_kcal_per_mol_angstrom,
        rtol=config.force_consistency_rtol,
    )
    assert first.max_component_force_sum_error_kcal_per_mol_angstrom < 1.0e-7
    assert first.max_component_net_force_kcal_per_mol_angstrom < 1.0e-7
    assert first.max_component_virial_antisymmetry_kcal_per_mol < 1.0e-7

    total_virial = first.total_component_virial()
    assert total_virial is not None
    assert torch.isfinite(total_virial).all()
    assert torch.allclose(
        total_virial,
        total_virial.transpose(-1, -2),
        atol=config.virial_symmetry_atol_kcal_per_mol,
        rtol=0.0,
    )
    with pytest.raises(TypeError):
        first.component_forces["new"] = torch.zeros_like(system.coordinates)


def test_component_virial_matches_uniform_strain_energy_derivative() -> None:
    system = _system()
    parameters = _parameters(system)
    result = evaluate_reference_term_diagnostics(system, parameters, _config())
    center = system.coordinates.mean(dim=1, keepdim=True)
    strain_step = 1.0e-5
    energies: dict[int, dict[str, float]] = {}

    for direction in (-1, 1):
        coordinates = center + (system.coordinates - center) * (
            1.0 + direction * strain_step
        )
        strained = system.with_coordinates(
            coordinates,
            operation=f"uniform_strain_{direction}",
        )
        evaluation = evaluate_reference_force_field(
            strained,
            _neighbors(strained),
            parameters,
        )
        energies[direction] = {
            name: float(value[0].item())
            for name, value in evaluation.component_energies.items()
        }

    for name in REFERENCE_TERM_NAMES:
        numerical_derivative = (
            energies[1][name] - energies[-1][name]
        ) / (2.0 * strain_step)
        virial_derivative = -float(
            torch.trace(result.component_virials[name][0]).item()
        )
        assert virial_derivative == pytest.approx(
            numerical_derivative,
            abs=2.0e-6,
            rel=2.0e-5,
        )


def test_component_force_and_virial_are_translation_invariant_and_rotation_covariant() -> None:
    system = _system()
    parameters = _parameters(system)
    original = evaluate_reference_term_diagnostics(system, parameters, _config())
    rotation = torch.tensor(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=torch.float64,
    )
    transformed_coordinates = system.coordinates @ rotation.T + torch.tensor(
        [5.0, -4.0, 3.0], dtype=torch.float64
    )
    transformed_system = system.with_coordinates(
        transformed_coordinates,
        operation="rigid_transform",
    )
    transformed = evaluate_reference_term_diagnostics(
        transformed_system,
        parameters,
        _config(),
    )

    assert transformed.diagnostics_complete
    for name in REFERENCE_TERM_NAMES:
        assert torch.allclose(
            transformed.component_forces[name],
            original.component_forces[name] @ rotation.T,
            atol=2.0e-7,
            rtol=2.0e-7,
        )
        expected_virial = (
            rotation @ original.component_virials[name][0] @ rotation.T
        )
        assert torch.allclose(
            transformed.component_virials[name][0],
            expected_virial,
            atol=2.0e-7,
            rtol=2.0e-7,
        )


def test_periodic_force_diagnostics_remain_available_but_virial_fails_closed() -> None:
    base = _system()
    periodic = replace(
        base,
        cell=UnitCell.orthorhombic((20.0, 20.0, 20.0), dtype=torch.float64),
    )
    parameters = _parameters(periodic)
    result = evaluate_reference_term_diagnostics(periodic, parameters, _config())

    assert result.force_diagnostics_complete
    assert not result.virial_diagnostics_complete
    assert not result.diagnostics_complete
    assert tuple(result.component_forces) == REFERENCE_TERM_NAMES
    assert dict(result.component_virials) == {}
    assert "periodic_virial_requires_cell_strain_derivative" in result.blockers
    assert result.failed_perturbation_count == 0


def _close_pair_system() -> AllAtomSystem:
    base = _system(
        torch.tensor(
            [[[0.0, 0.0, 0.0], [0.4, 0.0, 0.0], [5.0, 0.0, 0.0], [8.0, 0.0, 0.0]]],
            dtype=torch.float64,
        )
    )
    return replace(base, bonds=())


def _close_pair_parameters(system: AllAtomSystem) -> ReferenceForceFieldParameters:
    return ReferenceForceFieldParameters(
        parameter_set_id="diagnostics-close-pair",
        parameter_set_version="1",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=tuple(
            AtomNonbondedParameter(index, 0.2, 0.01, 0.0) for index in range(4)
        ),
        excluded_pairs=((0, 2), (0, 3), (1, 2), (1, 3), (2, 3)),
        cutoff_angstrom=1.0,
        switch_start_angstrom=0.8,
        applicability_domain=ReferenceApplicabilityDomain(
            max_atoms=8,
            minimum_pair_distance_angstrom=0.35,
        ),
    )


def test_failed_perturbations_remain_in_denominator_and_suppress_partial_outputs() -> None:
    system = _close_pair_system()
    result = evaluate_reference_term_diagnostics(
        system,
        _close_pair_parameters(system),
        _config(
            central_difference_step_angstrom=0.1,
            max_neighbors=4,
            max_atoms_per_cell=8,
        ),
    )

    assert result.observed_perturbation_count == result.expected_perturbation_count == 24
    assert result.failed_perturbation_count == 2
    assert not result.force_diagnostics_complete
    assert not result.virial_diagnostics_complete
    assert dict(result.component_forces) == {}
    assert dict(result.component_virials) == {}
    assert "perturbation_evaluations_failed" in result.blockers
    failed = [row for row in result.observations if row.status != "success"]
    assert {(row.atom_index, row.axis, row.direction) for row in failed} == {
        (0, 0, 1),
        (1, 0, -1),
    }
    assert all(not row.component_energies_kcal_per_mol for row in failed)
    assert all(row.failure_code for row in failed)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        ({"central_difference_step_angstrom": 0.0}, "central_difference_step"),
        ({"central_difference_step_angstrom": 0.2}, "central_difference_step"),
        ({"max_atoms": REFERENCE_TERM_DIAGNOSTICS_MAX_ATOMS + 1}, "max_atoms"),
        ({"max_neighbors": 0}, "max_neighbors"),
    ),
)
def test_diagnostics_config_rejects_invalid_or_unbounded_values(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(ReferenceTermDiagnosticsError, match=message):
        _config(**kwargs)


def test_diagnostics_reject_non_float64_multimodel_and_capacity_overflow() -> None:
    float32_system = _system().with_coordinates(
        _system().coordinates.float(),
        operation="float32",
    )
    with pytest.raises(ReferenceTermDiagnosticsError, match="float64"):
        evaluate_reference_term_diagnostics(
            float32_system,
            _parameters(float32_system),
            _config(),
        )

    system = _system()
    multimodel = replace(
        system,
        coordinates=torch.cat((system.coordinates, system.coordinates), dim=0),
    )
    with pytest.raises(ReferenceTermDiagnosticsError, match="exactly one model"):
        evaluate_reference_term_diagnostics(
            multimodel,
            _parameters(multimodel),
            _config(),
        )

    with pytest.raises(ReferenceTermDiagnosticsError, match="atom count"):
        evaluate_reference_term_diagnostics(
            system,
            _parameters(system),
            _config(max_atoms=3),
        )
