from __future__ import annotations

from dataclasses import replace
import inspect

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    ATOM_FEATURE_NAMES,
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    IndependentEngineV2,
    IndependentEngineV2Config,
    PeriodicReferencePathError,
    Residue,
    StructureProvenance,
    UnitCell,
    build_deterministic_atom_features,
)
from betelgeuze_engine_v2 import engine as engine_module  # noqa: E402
from betelgeuze_engine_v2 import features as feature_module  # noqa: E402
from betelgeuze_engine_v2.geometry import NeighborOverflowError  # noqa: E402
from betelgeuze_engine_v2.molecular import MolecularValidationError  # noqa: E402


def _system(coordinates: torch.Tensor | None = None) -> AllAtomSystem:
    if coordinates is None:
        coordinates = torch.tensor(
            [
                [
                    [0.0, 0.0, 0.0],
                    [1.2, 0.1, 0.0],
                    [0.2, 1.1, 0.3],
                    [-0.1, 0.2, 1.3],
                ]
            ],
            dtype=torch.float64,
        )
    return AllAtomSystem(
        system_id="reference-tetrahedron",
        atoms=(
            Atom(
                index=0,
                name="C1",
                element="C",
                atomic_number=6,
                residue_index=0,
                isotope_mass_number=13,
                partial_charge_e=0.15,
                mass_da=13.003,
                stereo="R",
            ),
            Atom(
                index=1,
                name="N1",
                element="N",
                atomic_number=7,
                residue_index=0,
                partial_charge_e=-0.2,
                mass_da=14.007,
            ),
            Atom(
                index=2,
                name="O1",
                element="O",
                atomic_number=8,
                residue_index=0,
                partial_charge_e=-0.1,
                mass_da=15.999,
            ),
            Atom(
                index=3,
                name="H1",
                element="H",
                atomic_number=1,
                residue_index=0,
                partial_charge_e=0.15,
                mass_da=1.008,
            ),
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1),
            Bond(index=1, atom_i=0, atom_j=2),
            Bond(index=2, atom_i=0, atom_j=3),
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
        coordinates=coordinates,
        provenance=StructureProvenance(
            source_format="sdf",
            source_id="orchestrator-unit-fixture",
            source_sha256="b" * 64,
            parser_name="unit-fixture",
            parser_version="1.0",
            operations=("explicit-hydrogen-check",),
            preparation_ready=True,
            claim_safe=True,
        ),
    )


def _config(**changes) -> IndependentEngineV2Config:
    defaults = dict(
        seed=7301,
        cutoff_angstrom=3.5,
        max_neighbors=4,
        max_atoms_per_cell=8,
        hidden_features=16,
        radial_features=8,
        layers=2,
        dtype=torch.float64,
    )
    defaults.update(changes)
    return IndependentEngineV2Config(**defaults)


def _proper_rotation() -> torch.Tensor:
    raw = torch.tensor(
        [[0.3, -0.7, 0.4], [0.5, 0.2, -0.8], [0.9, 0.1, 0.3]],
        dtype=torch.float64,
    )
    rotation, _ = torch.linalg.qr(raw)
    if torch.linalg.det(rotation) < 0:
        rotation[:, 0] *= -1
    return rotation


def test_deterministic_all_atom_features_encode_isotope_without_geometry() -> None:
    system = _system()
    first = build_deterministic_atom_features(system, dtype=torch.float64, device="cpu")
    moved = replace(system, coordinates=system.coordinates + 91.0)
    second = build_deterministic_atom_features(moved, dtype=torch.float64, device="cpu")
    assert torch.equal(first.values, second.values)
    assert first.values.shape == (1, 4, len(ATOM_FEATURE_NAMES))
    isotope_value = ATOM_FEATURE_NAMES.index("isotope_mass_number_scaled")
    isotope_present = ATOM_FEATURE_NAMES.index("isotope_mass_number_present")
    assert first.values[0, 0, isotope_value].item() == pytest.approx(13.0 / 350.0)
    assert first.values[0, 0, isotope_present].item() == 1.0
    assert first.values[0, 1, isotope_present].item() == 0.0
    assert first.diagnostics["expected_complexity"] == "O(N + E_bond)"
    assert first.diagnostics["parameterization_inferred"] is False


def test_deterministic_features_distinguish_canonical_e_and_z_bonds() -> None:
    system = _system()
    first_bond = system.bonds[0]
    e_system = replace(
        system,
        bonds=(replace(first_bond, stereo="E", order=2.0), *system.bonds[1:]),
    )
    z_system = replace(
        system,
        bonds=(replace(first_bond, stereo="Z", order=2.0), *system.bonds[1:]),
    )
    e_features = build_deterministic_atom_features(e_system, dtype=torch.float64, device="cpu")
    z_features = build_deterministic_atom_features(z_system, dtype=torch.float64, device="cpu")
    e_index = ATOM_FEATURE_NAMES.index("stereo_e_bond_count_squashed")
    z_index = ATOM_FEATURE_NAMES.index("stereo_z_bond_count_squashed")
    assert e_features.values[0, 0, e_index] > 0.0
    assert e_features.values[0, 0, z_index] == 0.0
    assert z_features.values[0, 0, e_index] == 0.0
    assert z_features.values[0, 0, z_index] > 0.0
    assert not torch.equal(e_features.values, z_features.values)
    assert e_features.diagnostics["bond_ez_stereochemistry_encoded"] is True


def test_engine_initialization_is_rng_isolated_and_reproducible() -> None:
    torch.manual_seed(99012)
    state_before = torch.random.get_rng_state().clone()
    first_engine = IndependentEngineV2(_config())
    assert torch.equal(torch.random.get_rng_state(), state_before)
    second_engine = IndependentEngineV2(_config())
    assert torch.equal(torch.random.get_rng_state(), state_before)
    assert first_engine.parameter_fingerprint_sha256 == second_engine.parameter_fingerprint_sha256

    first = first_engine.run(_system())
    second = second_engine.run(_system())
    assert torch.equal(first.energy, second.energy)
    assert torch.equal(first.energy_gradient_forces, second.energy_gradient_forces)
    assert torch.equal(first.parity_odd, second.parity_odd)


def test_end_to_end_shapes_motion_equivariance_and_provenance() -> None:
    engine = IndependentEngineV2(_config())
    system = _system()
    original = engine.run(system)
    rotation = _proper_rotation()
    transformed_coordinates = system.coordinates @ rotation.T
    transformed_coordinates = transformed_coordinates + torch.tensor(
        [[[8.0, -4.0, 2.5]]], dtype=torch.float64
    )
    transformed = engine.run(replace(system, coordinates=transformed_coordinates))

    assert original.energy.shape == (1,)
    assert original.forces.shape == (1, 4, 3)
    assert original.energy_gradient_forces.shape == (1, 4, 3)
    assert original.parity.shape == (1, 4)
    assert torch.allclose(original.energy, transformed.energy, atol=3.0e-10, rtol=3.0e-10)
    assert torch.allclose(original.parity, transformed.parity, atol=3.0e-10, rtol=3.0e-10)
    assert torch.allclose(
        transformed.energy_gradient_forces,
        original.energy_gradient_forces @ rotation.T,
        atol=3.0e-8,
        rtol=3.0e-8,
    )
    assert original.forces_are_conservative
    assert not original.projection_applied
    assert original.provenance.execution_mode == "internal_unvalidated_cpu_reference"
    assert original.provenance.input_source_sha256 == "b" * 64
    assert original.diagnostics["neighbors"]["nxn_allocation_observed"] is False
    assert original.diagnostics["model"]["constructs_nxn"] is False


def test_reported_raw_force_matches_scalar_energy_finite_difference() -> None:
    engine = IndependentEngineV2(_config())
    system = _system()
    result = engine.run(system)
    epsilon = 1.0e-5
    plus = system.coordinates.clone()
    minus = system.coordinates.clone()
    plus[0, 2, 1] += epsilon
    minus[0, 2, 1] -= epsilon
    energy_plus = engine.run(replace(system, coordinates=plus)).energy
    energy_minus = engine.run(replace(system, coordinates=minus)).energy
    finite_difference = (energy_plus - energy_minus) / (2.0 * epsilon)
    assert torch.allclose(
        -result.energy_gradient_forces[0, 2, 1],
        finite_difference[0],
        atol=4.0e-5,
        rtol=4.0e-5,
    )
    evidence = result.diagnostics["force_evidence"]
    assert evidence["exact_autograd"] is True
    assert evidence["definition"] == "negative_exact_coordinate_gradient_of_scalar_energy"


def test_claims_remain_blocked_even_with_claim_safe_input() -> None:
    result = IndependentEngineV2(_config()).run(_system())
    assert result.claim_safe is False
    assert result.diagnostics["claim_safe"] is False
    gates = {blocker.gate: blocker for blocker in result.blockers}
    assert set(gates) == {"checkpoint", "scientific", "benchmark", "gpu", "product"}
    assert all(blocker.status == "blocked" for blocker in gates.values())
    assert gates["checkpoint"].code == "uncalibrated_checkpoint"
    assert result.diagnostics["validation"]["claim_safe"] is False
    assert result.diagnostics["validation"]["warning_count"] >= 1
    assert result.diagnostics["initialization"]["kind"] == "deterministic_untrained_parameters"
    assert result.to_dict()["claim_safe"] is False


def test_rigid_projection_is_explicit_and_preserves_raw_gradient_evidence() -> None:
    result = IndependentEngineV2(_config()).run(_system(), project_rigid_body=True)
    assert result.projection_applied
    assert not result.forces_are_conservative
    assert "not guaranteed" in result.projection_note
    assert result.energy_gradient_forces.shape == result.forces.shape
    assert torch.allclose(
        result.forces.sum(dim=1),
        torch.zeros((1, 3), dtype=torch.float64),
        atol=3.0e-9,
    )
    centered = _system().coordinates - _system().coordinates.mean(dim=1, keepdim=True)
    torque = torch.cross(centered, result.forces, dim=-1).sum(dim=1)
    assert torch.allclose(torque, torch.zeros_like(torque), atol=3.0e-9)
    assert result.diagnostics["projection"]["constructs_nxn"] is False
    assert result.diagnostics["force_evidence"]["exact_autograd"] is True


def test_invalid_topology_overflow_and_periodic_path_fail_closed() -> None:
    system = _system()
    invalid = replace(system, bonds=(Bond(index=0, atom_i=0, atom_j=99),))
    with pytest.raises(MolecularValidationError):
        IndependentEngineV2(_config()).run(invalid)

    with pytest.raises(NeighborOverflowError):
        IndependentEngineV2(_config(max_neighbors=1)).run(system)

    periodic = replace(
        system,
        cell=UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64),
    )
    with pytest.raises(PeriodicReferencePathError, match="minimum-image"):
        IndependentEngineV2(_config()).run(periodic)


def test_single_atom_reference_execution_returns_zero_force_instead_of_crashing() -> None:
    system = AllAtomSystem(
        system_id="single-helium",
        atoms=(Atom(index=0, name="HE", element="He", atomic_number=2, residue_index=0),),
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="HE",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0,),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.zeros((1, 1, 3), dtype=torch.float64),
        provenance=StructureProvenance(
            source_format="unit_test",
            source_sha256="c" * 64,
            preparation_ready=True,
            claim_safe=True,
        ),
    )
    result = IndependentEngineV2(_config()).run(system)
    assert torch.equal(result.energy_gradient_forces, torch.zeros_like(system.coordinates))


def test_orchestrator_source_contains_no_dense_distance_or_borrowed_solver_path() -> None:
    source = inspect.getsource(engine_module) + inspect.getsource(feature_module)
    prohibited = ("torch." + "cdist", "Multihead" + "Attention", "Transformer" + "Encoder")
    assert all(token not in source for token in prohibited)
