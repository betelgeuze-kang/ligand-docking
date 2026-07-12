from __future__ import annotations

from dataclasses import replace

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    IndependentEngineV2,
    IndependentEngineV2Config,
    QuantityDescriptor,
    Residue,
    StructureProvenance,
    UnitCell,
)
from betelgeuze_engine_v2.physics import EnergyTermResult  # noqa: E402


ENERGY = QuantityDescriptor(
    name="energy",
    unit="kcal/mol",
    semantics="unit_test_harmonic_energy",
    physical_quantity=True,
    calibrated=True,
    reference_method="unit-test-harmonic",
)
FORCE = QuantityDescriptor(
    name="force",
    unit="kcal/mol/angstrom",
    semantics="negative_gradient_of_unit_test_harmonic_energy",
    physical_quantity=True,
    calibrated=True,
    reference_method="unit-test-harmonic",
)


def _system(*, periodic: bool = False) -> AllAtomSystem:
    coordinates = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.2, 0.1, 0.0], [0.2, 1.1, 0.3], [-0.1, 0.2, 1.3]]],
        dtype=torch.float64,
    )
    return AllAtomSystem(
        system_id="reference-tetrahedron",
        atoms=(
            Atom(index=0, name="C1", element="C", atomic_number=6, residue_index=0),
            Atom(index=1, name="N1", element="N", atomic_number=7, residue_index=0),
            Atom(index=2, name="O1", element="O", atomic_number=8, residue_index=0),
            Atom(index=3, name="H1", element="H", atomic_number=1, residue_index=0),
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
            source_format="unit_test",
            source_sha256="c" * 64,
        ),
        cell=UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64)
        if periodic
        else None,
    )


def _config(**changes) -> IndependentEngineV2Config:
    values = dict(
        seed=7301,
        cutoff_angstrom=3.5,
        max_neighbors=4,
        max_atoms_per_cell=8,
        hidden_features=16,
        radial_features=8,
        layers=2,
        dtype=torch.float64,
    )
    values.update(changes)
    return IndependentEngineV2Config(**values)


class HarmonicPhysics:
    provider_id = "unit-test-harmonic"

    def evaluate(self, system, neighbors):  # type: ignore[no-untyped-def]
        coordinates = system.coordinates.to(dtype=torch.float64, device="cpu")
        energy = 0.5 * coordinates.square().sum(dim=(1, 2))
        forces = -coordinates
        return EnergyTermResult(
            name="unit_test_harmonic",
            energy=energy,
            forces=forces,
            energy_descriptor=ENERGY,
            force_descriptor=FORCE,
            validated_for_composition=True,
            provenance_sha256="d" * 64,
        )


def test_initialization_is_reproducible_and_does_not_mutate_global_rng() -> None:
    torch.manual_seed(9912)
    before = torch.random.get_rng_state().clone()
    first = IndependentEngineV2(_config())
    assert torch.equal(torch.random.get_rng_state(), before)
    second = IndependentEngineV2(_config())
    assert torch.equal(torch.random.get_rng_state(), before)
    assert first.parameter_fingerprint_sha256 == second.parameter_fingerprint_sha256
    assert first.config_fingerprint_sha256 == second.config_fingerprint_sha256


def test_reference_residual_is_not_promoted_to_total_physical_energy() -> None:
    result = IndependentEngineV2(_config()).run(_system())
    assert result.reference_scalar_energy is not None
    assert result.reference_scalar_forces is not None
    assert result.energy_gradient_forces is not None
    assert result.total_physical_energy is None
    assert result.total_physical_forces is None
    assert result.claim_safe is False
    assert result.composition.ready is False
    assert "independent_physics_energy_missing" in result.composition.blockers
    assert "residual_energy_uncalibrated" in result.composition.blockers
    assert result.to_dict()["reference_energy_descriptor"]["physical_quantity"] is False
    assert result.diagnostics["neighbors"]["nxn_allocation_observed"] is False
    assert result.diagnostics["model"]["constructs_nxn"] is False


def test_validated_physics_without_reference_residual_can_form_total_energy() -> None:
    engine = IndependentEngineV2(
        _config(enable_reference_residual=False),
        physics_provider=HarmonicPhysics(),
    )
    result = engine.run(_system())
    assert result.reference_scalar_energy is None
    assert result.reference_scalar_forces is None
    assert result.composition.ready is True
    assert result.total_physical_energy is not None
    assert result.total_physical_forces is not None
    assert torch.allclose(result.total_physical_forces, -_system().coordinates)
    # Product/scientific gates remain blocked even when the isolated unit-test
    # composition contract itself is valid.
    assert result.claim_safe is False
    assert {blocker.gate for blocker in result.blockers} >= {
        "checkpoint", "scientific", "benchmark", "gpu", "product"
    }


def test_uncalibrated_residual_blocks_composition_with_validated_physics() -> None:
    result = IndependentEngineV2(
        _config(enable_reference_residual=True),
        physics_provider=HarmonicPhysics(),
    ).run(_system())
    assert result.composition.ready is False
    assert result.total_physical_energy is None
    assert result.composition.blockers == ("residual_energy_uncalibrated",)


def test_periodic_orchestration_uses_image_shift_gradient_path() -> None:
    system = _system(periodic=True)
    coordinates = system.coordinates.clone()
    coordinates[0, 1, 0] = 9.8
    periodic_system = replace(system, coordinates=coordinates)
    result = IndependentEngineV2(
        _config(cutoff_angstrom=1.5, max_neighbors=3),
    ).run(periodic_system)
    assert result.reference_scalar_energy is not None
    assert torch.isfinite(result.reference_scalar_energy).all()
    assert result.diagnostics["model"]["periodic_image_gradient_path"] is True
    assert result.diagnostics["sparse_graph"]["periodic_geometry_ready"] is True


def test_reference_scalar_force_matches_finite_difference() -> None:
    engine = IndependentEngineV2(_config())
    system = _system()
    result = engine.run(system)
    assert result.energy_gradient_forces is not None
    epsilon = 1.0e-5
    plus = system.coordinates.clone()
    minus = system.coordinates.clone()
    plus[0, 2, 1] += epsilon
    minus[0, 2, 1] -= epsilon
    energy_plus = engine.run(replace(system, coordinates=plus)).reference_scalar_energy
    energy_minus = engine.run(replace(system, coordinates=minus)).reference_scalar_energy
    assert energy_plus is not None and energy_minus is not None
    finite_difference = (energy_plus - energy_minus) / (2.0 * epsilon)
    assert torch.allclose(
        -result.energy_gradient_forces[0, 2, 1],
        finite_difference[0],
        atol=4.0e-5,
        rtol=4.0e-5,
    )


def test_rigid_projection_is_explicit_and_preserves_raw_gradient_evidence() -> None:
    result = IndependentEngineV2(_config()).run(_system(), project_rigid_body=True)
    assert result.projection_applied is True
    assert result.forces_are_conservative is False
    assert result.reference_scalar_forces is not None
    assert result.energy_gradient_forces is not None
    assert not torch.equal(result.reference_scalar_forces, result.energy_gradient_forces)
    assert torch.allclose(
        result.reference_scalar_forces.sum(dim=1),
        torch.zeros((1, 3), dtype=torch.float64),
        atol=3.0e-9,
        rtol=0.0,
    )
    assert "not guaranteed" in result.projection_note
