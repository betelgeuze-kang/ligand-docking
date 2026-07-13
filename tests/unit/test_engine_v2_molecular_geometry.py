from __future__ import annotations

from dataclasses import replace

import pytest
import torch

from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID, ContractVersionError, require_compatible_schema
from betelgeuze_engine_v2.geometry import (
    MAX_COMPACT_ATOMS_PER_CELL,
    MAX_COMPACT_NEIGHBORS,
    NeighborOverflowError,
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    LegacyAdapterError,
    Residue,
    StructureProvenance,
    UnitCell,
    from_legacy_engine_state,
    molecular_preparation_blockers,
    to_legacy_engine_state,
    validate_all_atom_system,
)


def _system(*, cell: UnitCell | None = None) -> AllAtomSystem:
    return AllAtomSystem(
        system_id="methanol-fragment",
        atoms=(
            Atom(
                index=0,
                name="C1",
                element="C",
                atomic_number=6,
                residue_index=0,
                partial_charge_e=0.1,
                isotope_mass_number=13,
            ),
            Atom(index=1, name="O1", element="O", atomic_number=8, residue_index=0, partial_charge_e=-0.2),
            Atom(index=2, name="H1", element="H", atomic_number=1, residue_index=0, partial_charge_e=0.1),
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1, order=1.0),
            Bond(index=1, atom_i=1, atom_j=2, order=1.0),
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
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor([[[0.0, 0.0, 0.0], [1.4, 0.0, 0.0], [2.3, 0.0, 0.0]]]),
        provenance=StructureProvenance(
            source_format="sdf",
            source_id="unit-fixture",
            source_sha256="a" * 64,
            parser_name="unit-test",
            parser_version="1.0",
            preparation_ready=True,
            claim_safe=True,
        ),
        cell=cell,
        metadata={"purpose": "unit-test"},
    )


def test_versioned_all_atom_contract_and_linear_validation() -> None:
    identity = require_compatible_schema(ALL_ATOM_SCHEMA_ID)
    assert identity.schema_id == ALL_ATOM_SCHEMA_ID
    with pytest.raises(ContractVersionError):
        require_compatible_schema("betelgeuze.all_atom_system/3.0.0")

    report = validate_all_atom_system(_system())
    assert report.valid
    assert report.claim_safe
    assert report.to_dict()["error_count"] == 0


def test_validation_rejects_noncanonical_membership_and_element_identity() -> None:
    system = _system()
    atoms = list(system.atoms)
    atoms[1] = replace(atoms[1], atomic_number=7)
    invalid = replace(
        system,
        atoms=tuple(atoms),
        residues=(replace(system.residues[0], atom_indices=(0, 1)),),
    )
    report = validate_all_atom_system(invalid)
    codes = {issue.code for issue in report.errors}
    assert "element_atomic_number_mismatch" in codes
    assert "atom_residue_membership_count" in codes
    assert not report.valid


def test_validation_preserves_typed_isotope_identity_and_rejects_impossible_mass_number() -> None:
    system = _system()
    assert system.atoms[0].isotope_mass_number == 13
    invalid_atoms = list(system.atoms)
    invalid_atoms[0] = replace(invalid_atoms[0], isotope_mass_number=5)
    report = validate_all_atom_system(replace(system, atoms=tuple(invalid_atoms)))
    assert "invalid_isotope_mass_number" in {issue.code for issue in report.errors}


def test_stereochemistry_vocabulary_and_bond_compatibility_fail_closed() -> None:
    system = _system()
    invalid_atom = list(system.atoms)
    invalid_atom[0] = replace(invalid_atom[0], stereo="BANANA")
    report = validate_all_atom_system(replace(system, atoms=tuple(invalid_atom)))
    assert "unsupported_atom_stereo" in {issue.code for issue in report.errors}

    invalid_bond = list(system.bonds)
    invalid_bond[0] = replace(invalid_bond[0], stereo="E", order=1.0)
    report = validate_all_atom_system(replace(system, bonds=tuple(invalid_bond)))
    assert "incompatible_ez_bond_stereo" in {issue.code for issue in report.errors}

    explicit_stereo = replace(
        system,
        atoms=(replace(system.atoms[0], stereo="R"), *system.atoms[1:]),
        bonds=(replace(system.bonds[0], stereo="E", order=2.0), *system.bonds[1:]),
    )
    report = validate_all_atom_system(explicit_stereo)
    assert report.valid
    assert report.claim_safe is False
    assert {issue.code for issue in report.warnings} >= {
        "atom_stereo_geometry_unverified",
        "bond_stereo_geometry_unverified",
    }


def test_legacy_adapter_round_trips_embedded_topology_and_coordinates() -> None:
    cell = UnitCell.orthorhombic((20.0, 21.0, 22.0))
    source = _system(cell=cell)
    state = to_legacy_engine_state(source, dtype=torch.float64)
    assert state.coords.dtype == torch.float64
    assert state.atom_types.tolist() == [6, 8, 1]
    assert state.residue_types.tolist() == [0, 0, 0]

    restored = from_legacy_engine_state(state)
    assert restored.schema_id == source.schema_id
    assert restored.atoms == source.atoms
    assert restored.bonds == source.bonds
    assert restored.residues == source.residues
    assert restored.chains == source.chains
    assert restored.metadata == source.metadata
    assert torch.equal(restored.coordinates, state.coords)
    assert restored.cell is not None
    assert torch.allclose(restored.cell.orthorhombic_lengths(), torch.tensor([20.0, 21.0, 22.0], dtype=torch.float64))


def test_legacy_adapter_thaws_nested_canonical_metadata_without_aliasing() -> None:
    source = replace(
        _system(),
        metadata={"nested": {"values": [1, 2]}},
    )
    state = to_legacy_engine_state(source)
    assert type(state.metadata["nested"]) is dict
    assert type(state.metadata["nested"]["values"]) is list
    state.metadata["nested"]["values"].append(3)

    assert source.metadata["nested"]["values"] == [1, 2]
    restored = from_legacy_engine_state(state)
    assert restored.metadata["nested"]["values"] == [1, 2]


def test_legacy_adapter_detects_type_order_drift_and_requires_explicit_coordinate_updates() -> None:
    source = _system(cell=UnitCell.orthorhombic((20.0, 21.0, 22.0)))
    state = to_legacy_engine_state(source, dtype=torch.float64)
    state.atom_types = state.atom_types.flip(0)
    with pytest.raises(LegacyAdapterError, match="atom_types changed"):
        from_legacy_engine_state(state)

    state = to_legacy_engine_state(source, dtype=torch.float64)
    state.coords = state.coords + 0.25
    state.box = state.box + 1.0
    with pytest.raises(LegacyAdapterError, match="allow_coordinate_updates"):
        from_legacy_engine_state(state)
    updated = from_legacy_engine_state(state, allow_coordinate_updates=True)
    assert updated.provenance.claim_safe is False
    assert "legacy_state_coordinates_or_box_updated" in updated.provenance.operations
    assert updated.cell is not None
    assert torch.allclose(updated.cell.orthorhombic_lengths(), state.box)

    with pytest.raises(LegacyAdapterError, match="float32 or torch.float64"):
        to_legacy_engine_state(source, dtype=torch.long)
    with pytest.raises(TypeError, match="float32 or float64"):
        replace(source, coordinates=source.coordinates.to(torch.bfloat16))


def test_bare_legacy_state_is_fail_closed_unless_lossy_inference_is_explicit() -> None:
    state = EngineState(
        coords=torch.tensor([[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]]),
        atom_types=torch.tensor([6, 8]),
    )
    with pytest.raises(LegacyAdapterError, match="lacks embedded canonical topology"):
        from_legacy_engine_state(state)

    inferred = from_legacy_engine_state(state, allow_lossy_inference=True)
    assert [atom.element for atom in inferred.atoms] == ["C", "O"]
    assert all(not atom.formal_charge_known for atom in inferred.atoms)
    assert inferred.provenance.preparation_ready is False
    assert molecular_preparation_blockers(inferred) == (
        "formal_charge_unknown_for_some_atoms",
        "preparation_not_complete",
    )
    assert inferred.provenance.claim_safe is False
    assert validate_all_atom_system(inferred).valid


def test_compact_radius_graph_has_bounded_shape_and_autograd_geometry() -> None:
    coordinates = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [3.0, 0.0, 0.0]]],
        dtype=torch.float64,
        requires_grad=True,
    )
    graph = build_compact_radius_graph(
        coordinates,
        RadiusGraphConfig(cutoff_angstrom=1.5, max_neighbors=2, max_atoms_per_cell=4),
    )
    assert graph.indices.shape == (1, 3, 2)
    assert graph.pair_count == 2
    assert graph.indices[0, 0, 0].item() == 1
    assert graph.indices[0, 1, 0].item() == 0
    assert graph.edge_triplets().shape == (3, 2)
    assert graph.edge_triplets(upper_only=True).shape == (3, 1)
    assert graph.diagnostics.claim_safe
    assert not graph.diagnostics.nxn_allocation_observed

    graph.distances[graph.mask].sum().backward()
    assert coordinates.grad is not None
    assert torch.isfinite(coordinates.grad).all()


def test_compact_radius_graph_applies_orthorhombic_minimum_image() -> None:
    coordinates = torch.tensor([[[0.2, 1.0, 1.0], [9.8, 1.0, 1.0]]], dtype=torch.float64)
    graph = build_compact_radius_graph(
        coordinates,
        RadiusGraphConfig(cutoff_angstrom=1.0, max_neighbors=2, max_atoms_per_cell=4),
        cell=UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64),
    )
    assert graph.pair_count == 2
    assert torch.allclose(graph.distances[graph.mask], torch.tensor([0.4, 0.4], dtype=torch.float64))
    assert graph.diagnostics.periodic == (True, True, True)


def test_compact_radius_graph_fails_closed_on_cell_or_neighbor_overflow() -> None:
    coordinates = torch.tensor(
        [[[0.0, 0.0, 0.0], [0.1, 0.0, 0.0], [0.2, 0.0, 0.0]]],
        dtype=torch.float32,
    )
    with pytest.raises(NeighborOverflowError) as cell_error:
        build_compact_radius_graph(
            coordinates,
            RadiusGraphConfig(cutoff_angstrom=1.0, max_neighbors=4, max_atoms_per_cell=2),
        )
    assert cell_error.value.diagnostics.overflow_kind == "cell_capacity"
    assert not cell_error.value.diagnostics.claim_safe

    with pytest.raises(NeighborOverflowError) as neighbor_error:
        build_compact_radius_graph(
            coordinates,
            RadiusGraphConfig(cutoff_angstrom=1.0, max_neighbors=1, max_atoms_per_cell=4),
        )
    assert neighbor_error.value.diagnostics.overflow_kind == "neighbor_capacity"

    with pytest.raises(ValueError, match="at least one batch and one atom"):
        build_compact_radius_graph(
            torch.empty((1, 0, 3), dtype=torch.float32),
            RadiusGraphConfig(cutoff_angstrom=1.0),
        )
    with pytest.raises(ValueError, match="max_neighbors exceeds hard cap"):
        RadiusGraphConfig(
            cutoff_angstrom=1.0,
            max_neighbors=MAX_COMPACT_NEIGHBORS + 1,
        )
    with pytest.raises(ValueError, match="max_atoms_per_cell exceeds hard cap"):
        RadiusGraphConfig(
            cutoff_angstrom=1.0,
            max_atoms_per_cell=MAX_COMPACT_ATOMS_PER_CELL + 1,
        )
