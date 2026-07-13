from __future__ import annotations

from dataclasses import fields, replace
import hashlib
import json
import math
import struct

import pytest
import torch

from betelgeuze_engine_v2.molecular import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    CANONICAL_TOPOLOGY_VERSION,
    AllAtomSystem,
    Atom,
    Bond,
    CanonicalTopologyError,
    Chain,
    MolecularValidationError,
    Residue,
    StructureProvenance,
    UnitCell,
    attached_canonical_topology_sha256_matches,
    canonical_topologies_equal,
    canonical_topology_document,
    canonical_topology_sha256,
    canonical_topology_sha256_for_valid_topology,
    deserialize_all_atom_system,
    serialize_all_atom_system,
    serialize_canonical_topology,
    topology_validation_error_codes,
)


def _system() -> AllAtomSystem:
    return AllAtomSystem(
        system_id="topology-fixture",
        atoms=(
            Atom(
                index=0,
                name="C1",
                element="C",
                atomic_number=6,
                residue_index=0,
                formal_charge=0,
                atom_map=7,
                partial_charge_e=0.1,
                mass_da=12.0,
                serial=11,
                occupancy=1.0,
                b_factor=10.0,
                metadata={"source": "first"},
            ),
            Atom(index=1, name="O1", element="O", atomic_number=8, residue_index=0),
            Atom(index=2, name="H1", element="H", atomic_number=1, residue_index=0),
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1, order=1.0, source="fixture", metadata={"raw": 1}),
            Bond(index=1, atom_i=1, atom_j=2, order=1.0),
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=4,
                atom_indices=(0, 1, 2),
                insertion_code="A",
                entity_type="non_polymer",
                hetero=True,
                metadata={"source": "residue"},
            ),
        ),
        chains=(
            Chain(
                index=0,
                chain_id="L",
                residue_indices=(0,),
                entity_id="ligand",
                metadata={"source": "chain"},
            ),
        ),
        coordinates=torch.tensor(
            [[[0.0, 0.0, 0.0], [1.2, 0.0, 0.0], [2.0, 0.0, 0.0]]],
            dtype=torch.float64,
        ),
        provenance=StructureProvenance(
            source_format="unit",
            source_id="source-a",
            source_sha256="a" * 64,
            preparation_ready=True,
            metadata={"audit": 1},
        ),
        metadata={"system": "metadata"},
    )


def test_topology_document_and_bytes_are_versioned_deterministic_json() -> None:
    source = _system()
    document = canonical_topology_document(source)
    payload = serialize_canonical_topology(source)

    assert CANONICAL_TOPOLOGY_VERSION == "1.0.0"
    assert document["topology_schema_id"] == CANONICAL_TOPOLOGY_SCHEMA_ID
    assert CANONICAL_TOPOLOGY_SCHEMA_ID == (
        "betelgeuze.canonical_ordered_topology/1.0.0"
    )
    assert document["system_schema_id"] == source.schema_id
    assert set(document) == {
        "topology_schema_id",
        "system_schema_id",
        "atoms",
        "bonds",
        "residues",
        "chains",
    }
    assert json.loads(payload.decode("utf-8")) == document
    assert canonical_topology_sha256(source) == hashlib.sha256(payload).hexdigest()
    assert payload == serialize_canonical_topology(_system())
    assert document["bonds"][0]["order_ieee754_binary64_be"] == struct.pack(
        ">d", 1.0
    ).hex()
    assert len(payload) == 1250
    assert canonical_topology_sha256(source) == (
        "6ba80b223d94c5402cfd80d38c8056ee38f35e0a4887a9de9a4171ee517e984a"
    )


def test_topology_document_field_sets_pin_the_complete_v1_contract() -> None:
    document = canonical_topology_document(_system())

    assert set(document["atoms"][0]) == {
        "index",
        "name",
        "element",
        "atomic_number",
        "residue_index",
        "formal_charge",
        "formal_charge_known",
        "isotope_mass_number",
        "atom_map",
        "altloc",
        "aromatic",
        "stereo",
    }
    assert set(document["bonds"][0]) == {
        "index",
        "atom_i",
        "atom_j",
        "order_ieee754_binary64_be",
        "aromatic",
        "stereo",
    }
    assert set(document["residues"][0]) == {
        "index",
        "name",
        "chain_index",
        "sequence_number",
        "atom_indices",
        "insertion_code",
        "entity_type",
        "hetero",
    }
    assert set(document["chains"][0]) == {
        "index",
        "chain_id",
        "residue_indices",
        "entity_id",
    }


def test_every_typed_record_field_is_explicitly_included_or_excluded() -> None:
    classifications = (
        (
            Atom,
            {
                "index",
                "name",
                "element",
                "atomic_number",
                "residue_index",
                "formal_charge",
                "formal_charge_known",
                "isotope_mass_number",
                "atom_map",
                "altloc",
                "aromatic",
                "stereo",
            },
            {
                "partial_charge_e",
                "mass_da",
                "serial",
                "occupancy",
                "b_factor",
                "metadata",
            },
        ),
        (
            Bond,
            {"index", "atom_i", "atom_j", "order", "aromatic", "stereo"},
            {"source", "metadata"},
        ),
        (
            Residue,
            {
                "index",
                "name",
                "chain_index",
                "sequence_number",
                "atom_indices",
                "insertion_code",
                "entity_type",
                "hetero",
            },
            {"metadata"},
        ),
        (
            Chain,
            {"index", "chain_id", "residue_indices", "entity_id"},
            {"metadata"},
        ),
        (
            AllAtomSystem,
            {"atoms", "bonds", "residues", "chains", "schema_id"},
            {
                "system_id",
                "coordinates",
                "provenance",
                "cell",
                "coordinate_unit",
                "metadata",
            },
        ),
    )
    for record_type, included, excluded in classifications:
        assert included.isdisjoint(excluded)
        assert {field.name for field in fields(record_type)} == included | excluded


def test_topology_identity_excludes_coordinates_provenance_observations_and_parameters() -> None:
    source = _system()
    excluded_state_changed = replace(
        source,
        system_id="different-alias",
        atoms=(
            replace(
                source.atoms[0],
                partial_charge_e=-0.4,
                mass_da=13.5,
                serial=999,
                occupancy=0.25,
                b_factor=88.0,
                metadata={"tampered": True},
            ),
            *source.atoms[1:],
        ),
        bonds=(replace(source.bonds[0], source="other", metadata={"tampered": True}), source.bonds[1]),
        residues=(replace(source.residues[0], metadata={"tampered": True}),),
        chains=(replace(source.chains[0], metadata={"tampered": True}),),
        coordinates=torch.tensor(
            [
                [[9.0, 8.0, 7.0], [6.0, 5.0, 4.0], [3.0, 2.0, 1.0]],
                [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]],
            ],
            dtype=torch.float32,
        ),
        provenance=StructureProvenance(
            source_format="other",
            source_id="source-b",
            source_sha256="b" * 64,
            operations=("changed",),
            preparation_ready=False,
            metadata={"tampered": True},
        ),
        cell=UnitCell.orthorhombic((20.0, 21.0, 22.0)),
        metadata={"tampered": True},
    )
    assert canonical_topologies_equal(source, excluded_state_changed)
    assert canonical_topology_sha256(source) == canonical_topology_sha256(excluded_state_changed)

    topology_only = replace(
        source,
        coordinates=torch.empty((0, source.atom_count, 3), dtype=torch.float64),
    )
    assert canonical_topologies_equal(source, topology_only)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda system: replace(system, atoms=(replace(system.atoms[0], name="CX"), *system.atoms[1:])),
        lambda system: replace(
            system,
            atoms=(replace(system.atoms[0], element="N", atomic_number=7), *system.atoms[1:]),
        ),
        lambda system: replace(system, atoms=(replace(system.atoms[0], formal_charge=1), *system.atoms[1:])),
        lambda system: replace(system, atoms=(replace(system.atoms[0], formal_charge_known=False), *system.atoms[1:])),
        lambda system: replace(system, atoms=(replace(system.atoms[0], isotope_mass_number=13), *system.atoms[1:])),
        lambda system: replace(system, atoms=(replace(system.atoms[0], atom_map=8), *system.atoms[1:])),
        lambda system: replace(system, atoms=(replace(system.atoms[0], altloc="B"), *system.atoms[1:])),
        lambda system: replace(system, atoms=(replace(system.atoms[0], aromatic=True), *system.atoms[1:])),
        lambda system: replace(system, atoms=(replace(system.atoms[0], stereo="R"), *system.atoms[1:])),
        lambda system: replace(
            system,
            bonds=(replace(system.bonds[0], atom_j=2), system.bonds[1]),
        ),
        lambda system: replace(system, bonds=(replace(system.bonds[0], order=2.0), system.bonds[1])),
        lambda system: replace(system, bonds=(replace(system.bonds[0], aromatic=True), system.bonds[1])),
        lambda system: replace(system, bonds=(replace(system.bonds[0], stereo="UP"), system.bonds[1])),
        lambda system: replace(system, residues=(replace(system.residues[0], name="DRG"),)),
        lambda system: replace(system, residues=(replace(system.residues[0], sequence_number=5),)),
        lambda system: replace(system, residues=(replace(system.residues[0], insertion_code="B"),)),
        lambda system: replace(system, residues=(replace(system.residues[0], entity_type="cofactor"),)),
        lambda system: replace(system, residues=(replace(system.residues[0], hetero=False),)),
        lambda system: replace(system, chains=(replace(system.chains[0], chain_id="X"),)),
        lambda system: replace(system, chains=(replace(system.chains[0], entity_id="drug"),)),
    ],
)
def test_every_included_topology_mutation_changes_digest(mutation: object) -> None:
    source = _system()
    changed = mutation(source)  # type: ignore[operator]
    assert canonical_topology_sha256(changed) != canonical_topology_sha256(source)
    assert not canonical_topologies_equal(changed, source)


def test_atom_order_is_identity_but_bond_record_order_is_not() -> None:
    source = _system()
    reordered_bonds = tuple(
        replace(bond, index=index)
        for index, bond in enumerate(reversed(source.bonds))
    )
    bond_records_reordered = replace(source, bonds=reordered_bonds)
    assert canonical_topologies_equal(source, bond_records_reordered)

    atom_order_changed = replace(
        source,
        atoms=(
            source.atoms[0],
            replace(source.atoms[2], index=1),
            replace(source.atoms[1], index=2),
        ),
        bonds=(
            replace(source.bonds[0], index=0, atom_i=0, atom_j=2),
            replace(source.bonds[1], index=1, atom_i=1, atom_j=2),
        ),
        coordinates=source.coordinates[:, [0, 2, 1], :],
    )
    assert canonical_topology_sha256(atom_order_changed) != canonical_topology_sha256(source)


def test_membership_identity_changes_are_hashed_as_consistent_typed_state() -> None:
    source = _system()
    split = replace(
        source,
        atoms=(*source.atoms[:2], replace(source.atoms[2], residue_index=1)),
        residues=(
            replace(source.residues[0], atom_indices=(0, 1)),
            Residue(
                index=1,
                name="SOL",
                chain_index=1,
                sequence_number=5,
                atom_indices=(2,),
                entity_type="solvent",
                hetero=True,
            ),
        ),
        chains=(
            source.chains[0],
            Chain(index=1, chain_id="W", residue_indices=(1,), entity_id="water"),
        ),
    )
    atom_membership_changed = replace(
        split,
        atoms=(*split.atoms[:2], replace(split.atoms[2], residue_index=0)),
        residues=(
            replace(split.residues[0], atom_indices=(0, 1, 2)),
            replace(split.residues[1], atom_indices=()),
        ),
    )
    assert canonical_topology_sha256(atom_membership_changed) != canonical_topology_sha256(split)

    chain_membership_changed = replace(
        split,
        residues=(split.residues[0], replace(split.residues[1], chain_index=0)),
        chains=(
            replace(split.chains[0], residue_indices=(0, 1)),
            replace(split.chains[1], residue_indices=()),
        ),
    )
    assert canonical_topology_sha256(chain_membership_changed) != canonical_topology_sha256(split)


def test_stereo_spelling_is_normalized_but_stereo_meaning_is_not() -> None:
    source = _system()
    atom_lower = replace(
        source,
        atoms=(replace(source.atoms[0], stereo=" r "), *source.atoms[1:]),
    )
    atom_upper = replace(
        source,
        atoms=(replace(source.atoms[0], stereo="R"), *source.atoms[1:]),
    )
    atom_opposite = replace(
        source,
        atoms=(replace(source.atoms[0], stereo="S"), *source.atoms[1:]),
    )
    assert canonical_topologies_equal(atom_lower, atom_upper)
    assert not canonical_topologies_equal(atom_upper, atom_opposite)

    bond_lower = replace(
        source,
        bonds=(replace(source.bonds[0], order=2.0, stereo=" e "), source.bonds[1]),
    )
    bond_upper = replace(
        source,
        bonds=(replace(source.bonds[0], order=2.0, stereo="E"), source.bonds[1]),
    )
    bond_opposite = replace(
        source,
        bonds=(replace(source.bonds[0], order=2.0, stereo="Z"), source.bonds[1]),
    )
    assert canonical_topologies_equal(bond_lower, bond_upper)
    assert not canonical_topologies_equal(bond_upper, bond_opposite)


def test_bond_order_uses_exact_binary64_not_decimal_rounding() -> None:
    source = _system()
    adjacent_order = math.nextafter(1.0, 2.0)
    changed = replace(
        source,
        bonds=(replace(source.bonds[0], order=adjacent_order), source.bonds[1]),
    )
    document = canonical_topology_document(changed)
    assert document["bonds"][0]["order_ieee754_binary64_be"] == struct.pack(
        ">d", adjacent_order
    ).hex()
    assert canonical_topology_sha256(changed) != canonical_topology_sha256(source)


def test_snapshot_round_trip_preserves_topology_bytes_and_digest() -> None:
    source = _system()
    restored = deserialize_all_atom_system(serialize_all_atom_system(source))
    assert serialize_canonical_topology(restored) == serialize_canonical_topology(source)
    assert canonical_topology_sha256(restored) == canonical_topology_sha256(source)


def test_attached_digest_is_only_a_verified_cache_and_never_an_authority() -> None:
    source = _system()
    digest = canonical_topology_sha256(source)
    assert attached_canonical_topology_sha256_matches(source) is False

    attached = replace(
        source,
        provenance=replace(
            source.provenance,
            metadata={
                "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
                "canonical_topology_sha256": digest,
            },
        ),
    )
    assert attached_canonical_topology_sha256_matches(attached) is True
    assert canonical_topology_sha256(attached) == digest

    stale = replace(
        attached,
        atoms=(replace(attached.atoms[0], formal_charge=1), *attached.atoms[1:]),
    )
    assert attached_canonical_topology_sha256_matches(stale) is False

    for bad_metadata in (
        {"canonical_topology_sha256": digest},
        {
            "canonical_topology_schema_id": "betelgeuze.canonical_ordered_topology/9.0.0",
            "canonical_topology_sha256": digest,
        },
        {
            "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
            "canonical_topology_sha256": "0" * 64,
        },
        {
            "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
            "canonical_topology_sha256": "A" * 64,
        },
        {
            "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
            "canonical_topology_sha256": "٠" * 64,
        },
        {
            "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
            "canonical_topology_sha256": 7,
        },
        {
            "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
            "canonical_topology_sha256": "0" * 63,
        },
        {
            "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
            "canonical_topology_sha256": "g" * 64,
        },
    ):
        tampered = replace(
            source,
            provenance=replace(source.provenance, metadata=bad_metadata),
        )
        assert attached_canonical_topology_sha256_matches(tampered) is False


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA is unavailable")
def test_coordinate_device_does_not_change_topology_digest() -> None:
    source = _system()
    on_cuda = replace(
        source,
        coordinates=source.coordinates.to(device="cuda", dtype=torch.float32).requires_grad_(),
        cell=UnitCell.orthorhombic(
            (20.0, 21.0, 22.0),
            dtype=torch.float64,
            device="cuda",
            periodic=(False, True, False),
        ),
    )
    assert canonical_topology_sha256(on_cuda) == canonical_topology_sha256(source)


def test_digest_requires_a_valid_canonical_system_and_exact_type() -> None:
    with pytest.raises(TypeError, match="system must be an AllAtomSystem"):
        canonical_topology_sha256(object())  # type: ignore[arg-type]

    class DerivedSystem(AllAtomSystem):
        pass

    source = _system()
    derived = DerivedSystem(**source.__dict__)
    with pytest.raises(TypeError, match="system must be an AllAtomSystem"):
        canonical_topology_sha256(derived)

    invalid = replace(
        source,
        coordinates=torch.tensor(
            [[[float("nan"), 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]],
            dtype=torch.float64,
        ),
    )
    with pytest.raises(MolecularValidationError):
        canonical_topology_sha256(invalid)

    assert topology_validation_error_codes(invalid) == ()
    assert canonical_topology_sha256_for_valid_topology(invalid) == (
        canonical_topology_sha256(source)
    )

    invalid_provenance = replace(
        source,
        provenance=replace(source.provenance, source_sha256="invalid"),
    )
    assert topology_validation_error_codes(invalid_provenance) == ()
    assert canonical_topology_sha256_for_valid_topology(invalid_provenance) == (
        canonical_topology_sha256(source)
    )

    invalid_topology = replace(
        source,
        bonds=(replace(source.bonds[0], atom_j=99), source.bonds[1]),
    )
    assert "invalid_bond_atom" in topology_validation_error_codes(
        invalid_topology
    )
    with pytest.raises(CanonicalTopologyError, match="validation failed"):
        canonical_topology_sha256_for_valid_topology(invalid_topology)


def test_typed_identity_strings_reject_lone_unicode_surrogates() -> None:
    with pytest.raises(ValueError, match="Unicode scalar values"):
        replace(_system().atoms[0], name="\ud800")


@pytest.mark.parametrize(
    "schema_id",
    [
        "betelgeuze.all_atom_system/2.0.0",
        "betelgeuze.all_atom_system/2.2.0",
        "betelgeuze.all_atom_system/3.0.0",
    ],
)
def test_topology_v1_fails_closed_for_every_unreviewed_system_schema(
    schema_id: str,
) -> None:
    with pytest.raises(CanonicalTopologyError, match="does not support system schema"):
        canonical_topology_sha256(replace(_system(), schema_id=schema_id))
