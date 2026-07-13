from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace

import pytest
import torch

import betelgeuze_engine_v2.molecular.models as molecular_models
import betelgeuze_engine_v2.molecular.serialization as molecular_serialization
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    MolecularSerializationError,
    MolecularValidationError,
    Residue,
    StructureProvenance,
    UnitCell,
    canonical_all_atom_snapshot_digest,
    canonical_all_atom_systems_equal,
    deserialize_all_atom_system,
    round_trip_all_atom_system,
    serialize_all_atom_system,
    validate_all_atom_system,
)


def _system(*, cell: UnitCell | None = None, coordinates: torch.Tensor | None = None) -> AllAtomSystem:
    coords = coordinates
    if coords is None:
        coords = torch.tensor([[[0.0, 0.0, 0.0], [1.4, 0.0, 0.0], [2.3, 0.0, 0.0]]], dtype=torch.float64)
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
                serial=1,
                atom_map=17,
                occupancy=1.0,
                b_factor=12.5,
                metadata={"source": "fixture", "rank": 2},
            ),
            Atom(index=1, name="O1", element="O", atomic_number=8, residue_index=0, partial_charge_e=-0.2),
            Atom(index=2, name="H1", element="H", atomic_number=1, residue_index=0, partial_charge_e=0.1),
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1, order=1.0, metadata={"kind": "single"}),
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
                metadata={"class": "ligand"},
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,), metadata={"auth": "A"}),),
        coordinates=coords,
        provenance=StructureProvenance(
            source_format="sdf",
            source_id="unit-fixture",
            source_sha256="a" * 64,
            parser_name="unit-test",
            parser_version="1.0",
            operations=("normalize",),
            parent_sha256=("b" * 64,),
            preparation_ready=True,
            claim_safe=True,
            metadata={"stage": "serialization"},
        ),
        cell=cell,
        metadata={"purpose": "unit-test", "nested": {"z": 1, "a": 2}},
    )


def test_canonical_snapshot_round_trips_all_supported_fields() -> None:
    cell = UnitCell.orthorhombic((20.0, 21.0, 22.0), dtype=torch.float64)
    source = _system(cell=cell)
    restored = round_trip_all_atom_system(source)
    assert restored.atoms == source.atoms
    assert restored.bonds == source.bonds
    assert restored.residues == source.residues
    assert restored.chains == source.chains
    assert [dict(atom.metadata) for atom in restored.atoms] == [dict(atom.metadata) for atom in source.atoms]
    assert [dict(bond.metadata) for bond in restored.bonds] == [dict(bond.metadata) for bond in source.bonds]
    assert [dict(residue.metadata) for residue in restored.residues] == [
        dict(residue.metadata) for residue in source.residues
    ]
    assert [dict(chain.metadata) for chain in restored.chains] == [dict(chain.metadata) for chain in source.chains]
    assert restored.provenance == source.provenance
    assert restored.metadata == source.metadata
    assert torch.equal(restored.coordinates, source.coordinates)
    assert restored.cell is not None
    assert torch.equal(restored.cell.vectors, source.cell.vectors)
    assert restored.cell.periodic == source.cell.periodic
    assert validate_all_atom_system(restored).valid
    assert serialize_all_atom_system(restored) == serialize_all_atom_system(source)
    assert canonical_all_atom_systems_equal(restored, source)


def test_canonical_snapshot_digest_is_deterministic_and_device_independent() -> None:
    source = _system(cell=UnitCell.orthorhombic((10.0, 11.0, 12.0), dtype=torch.float32))
    coords_cpu = source.coordinates.detach().clone().requires_grad_(True)
    coords_cuda = coords_cpu.detach().clone()
    if torch.cuda.is_available():
        coords_cuda = coords_cuda.cuda().requires_grad_(True)
    system_cpu = source.with_coordinates(coords_cpu)
    system_cuda = source.with_coordinates(coords_cuda)

    payload_a = serialize_all_atom_system(system_cpu)
    payload_b = serialize_all_atom_system(system_cuda)
    digest_a = canonical_all_atom_snapshot_digest(system_cpu)
    digest_b = canonical_all_atom_snapshot_digest(system_cuda)

    assert payload_a == payload_b
    assert digest_a == digest_b
    assert digest_a == hashlib.sha256(payload_a).hexdigest()


def test_canonical_snapshot_v1_2_golden_bytes_are_stable() -> None:
    payload = serialize_all_atom_system(_system())
    expected_digest = "4d0948fa26b2e748bdeff8c1d90c7872bd1ba62578dc9911e640840b83112f52"
    assert len(payload) == 2199
    assert hashlib.sha256(payload).hexdigest() == expected_digest
    assert canonical_all_atom_snapshot_digest(_system()) == expected_digest


def test_canonical_snapshot_metadata_insertion_order_is_irrelevant() -> None:
    source = _system()
    reordered = replace(
        source,
        metadata={"nested": {"a": 2, "z": 1}, "purpose": "unit-test"},
        atoms=tuple(
            replace(atom, metadata={"rank": 2, "source": "fixture"}) if atom.index == 0 else atom
            for atom in source.atoms
        ),
    )
    assert serialize_all_atom_system(source) == serialize_all_atom_system(reordered)


def test_canonical_metadata_is_deeply_immutable_and_detached_from_input_aliases() -> None:
    source = _system()
    supplied = {"nested": {"values": [1, {"label": "kept"}]}}
    system = replace(
        source,
        atoms=(replace(source.atoms[0], metadata=supplied), *source.atoms[1:]),
        bonds=(replace(source.bonds[0], metadata=supplied), *source.bonds[1:]),
        residues=(replace(source.residues[0], metadata=supplied),),
        chains=(replace(source.chains[0], metadata=supplied),),
        provenance=replace(source.provenance, metadata=supplied),
        metadata=supplied,
    )
    baseline = serialize_all_atom_system(system)
    supplied["nested"]["values"].append(99)
    supplied["nested"]["forged"] = True

    metadata_values = (
        system.atoms[0].metadata,
        system.bonds[0].metadata,
        system.residues[0].metadata,
        system.chains[0].metadata,
        system.provenance.metadata,
        system.metadata,
    )
    for metadata in metadata_values:
        assert metadata["nested"]["values"] == [1, {"label": "kept"}]
        assert "forged" not in metadata["nested"]
        with pytest.raises(TypeError):
            metadata["new"] = "forged"  # type: ignore[index]
        with pytest.raises(TypeError):
            metadata["nested"]["new"] = "forged"  # type: ignore[index]
        with pytest.raises(AttributeError):
            metadata["nested"]["values"].append("forged")
    assert serialize_all_atom_system(system) == baseline
    restored = deserialize_all_atom_system(baseline)
    with pytest.raises(TypeError):
        restored.metadata["nested"]["forged"] = True  # type: ignore[index]


def test_canonical_metadata_rejects_cycles_excess_depth_and_non_json_values() -> None:
    source = _system()
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    with pytest.raises(ValueError, match="reference cycle"):
        replace(source, metadata=cyclic)

    too_deep: dict[str, object] = {}
    for _ in range(66):
        too_deep = {"nested": too_deep}
    with pytest.raises(ValueError, match="depth limit"):
        replace(source, metadata=too_deep)

    with pytest.raises(TypeError, match="supports only JSON"):
        replace(source, metadata={"tuple": (1, 2)})
    with pytest.raises(ValueError, match="floats must be finite"):
        replace(source, metadata={"nan": float("nan")})


def test_canonical_metadata_node_budget_is_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(molecular_models, "_MAX_CANONICAL_METADATA_NODES", 3)
    with pytest.raises(ValueError, match="node safety limit"):
        replace(_system(), metadata={"items": [1, 2]})


def test_snapshot_deserializer_normalizes_json_recursion_and_integer_limits() -> None:
    deeply_nested_json = b"[" * 1_100 + b"0" + b"]" * 1_100
    with pytest.raises(MolecularSerializationError, match="invalid JSON snapshot"):
        deserialize_all_atom_system(deeply_nested_json)

    oversized_integer_json = b'{"value":' + b"9" * 5_000 + b"}"
    with pytest.raises(MolecularSerializationError, match="invalid JSON snapshot"):
        deserialize_all_atom_system(oversized_integer_json)


def test_snapshot_deserializer_applies_canonical_metadata_depth_limit() -> None:
    document = json.loads(serialize_all_atom_system(_system()))
    nested: dict[str, object] = {}
    for _ in range(66):
        nested = {"nested": nested}
    document["metadata"] = nested
    with pytest.raises(MolecularSerializationError, match="depth limit"):
        deserialize_all_atom_system(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )


def test_snapshot_byte_budget_is_enforced_before_decode_and_after_encode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = serialize_all_atom_system(_system())
    monkeypatch.setattr(
        molecular_serialization,
        "_MAX_CANONICAL_SNAPSHOT_BYTES",
        len(baseline) - 1,
    )
    with pytest.raises(MolecularSerializationError, match="byte safety limit"):
        deserialize_all_atom_system(baseline)
    with pytest.raises(MolecularSerializationError, match="byte safety limit"):
        serialize_all_atom_system(_system())


def test_canonical_snapshot_rejects_invalid_system_before_serialization() -> None:
    source = _system()
    invalid_atoms = list(source.atoms)
    invalid_atoms[0] = replace(invalid_atoms[0], atomic_number=7)
    invalid = replace(source, atoms=tuple(invalid_atoms))
    with pytest.raises(MolecularValidationError):
        serialize_all_atom_system(invalid)


def test_canonical_snapshot_rejects_malformed_payloads() -> None:
    source = _system()
    payload = serialize_all_atom_system(source)
    document = json.loads(payload.decode("utf-8"))

    with pytest.raises(MolecularSerializationError, match="UTF-8"):
        deserialize_all_atom_system(b"\xff\xfe")

    with pytest.raises(MolecularSerializationError, match="invalid JSON"):
        deserialize_all_atom_system(b"{")

    mutated = copy.deepcopy(document)
    mutated["snapshot_version"] = "9.9.9"
    with pytest.raises(MolecularSerializationError, match="unsupported snapshot_version"):
        deserialize_all_atom_system(json.dumps(mutated, sort_keys=True).encode("utf-8"))

    mutated = copy.deepcopy(document)
    mutated["schema_id"] = "betelgeuze.all_atom_system/3.0.0"
    with pytest.raises(MolecularSerializationError, match="unsupported"):
        deserialize_all_atom_system(json.dumps(mutated, sort_keys=True).encode("utf-8"))

    mutated = copy.deepcopy(document)
    mutated["extra_field"] = "forbidden"
    with pytest.raises(MolecularSerializationError, match="unexpected"):
        deserialize_all_atom_system(json.dumps(mutated, sort_keys=True).encode("utf-8"))

    mutated = copy.deepcopy(document)
    del mutated["system_id"]
    with pytest.raises(MolecularSerializationError, match="missing"):
        deserialize_all_atom_system(json.dumps(mutated, sort_keys=True).encode("utf-8"))

    mutated = copy.deepcopy(document)
    mutated["atoms"][0]["unexpected"] = True
    with pytest.raises(MolecularSerializationError, match="unexpected"):
        deserialize_all_atom_system(json.dumps(mutated, sort_keys=True).encode("utf-8"))

    mutated = copy.deepcopy(document)
    mutated["coordinates"]["dtype"] = "float16"
    with pytest.raises(MolecularSerializationError, match="unsupported tensor dtype"):
        deserialize_all_atom_system(json.dumps(mutated, sort_keys=True).encode("utf-8"))

    mutated = copy.deepcopy(document)
    mutated["coordinates"]["shape"] = [1, 3, 4]
    with pytest.raises(MolecularSerializationError, match="declared dimension"):
        deserialize_all_atom_system(json.dumps(mutated, sort_keys=True).encode("utf-8"))

    mutated = copy.deepcopy(document)
    mutated["coordinates"]["data"][0][0][0] = "nan"
    with pytest.raises(MolecularSerializationError):
        deserialize_all_atom_system(json.dumps(mutated, sort_keys=True).encode("utf-8"))

    mutated = copy.deepcopy(document)
    mutated["metadata"]["nested"]["bad"] = float("inf")
    with pytest.raises(MolecularSerializationError, match="non-standard JSON constant"):
        deserialize_all_atom_system(json.dumps(mutated, sort_keys=True).encode("utf-8"))


def _replace_document_path(document: dict[str, object], path: tuple[object, ...], value: object) -> None:
    target: object = document
    for segment in path[:-1]:
        target = target[segment]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("system_id",), 7, "system_id"),
        (("coordinate_unit",), 7, "coordinate_unit"),
        (("atoms", 0, "index"), "0", "atoms\\[0\\].index"),
        (("atoms", 0, "name"), 7, "atoms\\[0\\].name"),
        (("atoms", 0, "aromatic"), "false", "atoms\\[0\\].aromatic"),
        (("atoms", 0, "atom_map"), True, "atoms\\[0\\].atom_map"),
        (("bonds", 0, "order"), True, "bonds\\[0\\].order"),
        (("bonds", 0, "order"), 1, "bonds\\[0\\].order"),
        (("residues", 0, "atom_indices"), [True, 1, 2], "atom_indices\\[0\\]"),
        (("chains", 0, "residue_indices"), ["0"], "residue_indices\\[0\\]"),
        (("provenance", "operations"), [1], "operations\\[0\\]"),
        (("provenance", "preparation_ready"), 1, "provenance.preparation_ready"),
        (("provenance", "claim_safe"), 1, "provenance.claim_safe"),
    ],
)
def test_canonical_snapshot_rejects_scalar_type_coercion(
    path: tuple[object, ...], value: object, message: str
) -> None:
    document = json.loads(serialize_all_atom_system(_system()).decode("utf-8"))
    _replace_document_path(document, path, value)
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with pytest.raises(MolecularSerializationError, match=message):
        deserialize_all_atom_system(payload)


def test_canonical_snapshot_rejects_duplicate_keys_and_nonstandard_constants() -> None:
    payload = serialize_all_atom_system(_system()).decode("utf-8")
    duplicate = payload.replace(
        '"snapshot_version":"1.2.0"',
        '"snapshot_version":"1.2.0","snapshot_version":"1.2.0"',
        1,
    )
    with pytest.raises(MolecularSerializationError, match="duplicate JSON object key"):
        deserialize_all_atom_system(duplicate.encode("utf-8"))

    nonstandard = payload.replace('"system_id":"methanol-fragment"', '"system_id":NaN', 1)
    with pytest.raises(MolecularSerializationError, match="non-standard JSON constant"):
        deserialize_all_atom_system(nonstandard.encode("utf-8"))


def test_canonical_snapshot_normalizes_validation_failure_to_serialization_error() -> None:
    document = json.loads(serialize_all_atom_system(_system()).decode("utf-8"))
    document["atoms"][0]["index"] = 9
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with pytest.raises(MolecularSerializationError, match="invalid canonical snapshot"):
        deserialize_all_atom_system(payload)


def test_canonical_snapshot_rejects_integer_payloads_for_float_fields_and_tensors() -> None:
    document = json.loads(serialize_all_atom_system(_system()).decode("utf-8"))
    document["bonds"][0]["order"] = 10**400
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with pytest.raises(MolecularSerializationError, match="expected finite float"):
        deserialize_all_atom_system(payload)

    document = json.loads(serialize_all_atom_system(_system()).decode("utf-8"))
    document["coordinates"]["data"][0][0][0] = 10**400
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with pytest.raises(MolecularSerializationError, match="finite floats"):
        deserialize_all_atom_system(payload)


def test_canonical_snapshot_rejects_nonfinite_coordinates_on_serialize() -> None:
    source = _system(coordinates=torch.tensor([[[float("nan"), 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]]))
    with pytest.raises(MolecularValidationError):
        serialize_all_atom_system(source)


def test_canonical_model_rejects_unsupported_runtime_tensor_dtype() -> None:
    with pytest.raises(TypeError, match="float32 or float64"):
        _system(
            coordinates=torch.tensor(
                [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]],
                dtype=torch.bfloat16,
            )
        )


@pytest.mark.parametrize(
    "field",
    [
        "atom_aromatic",
        "bond_aromatic",
        "residue_hetero",
        "provenance_preparation_ready",
        "provenance_claim_safe",
    ],
)
def test_canonical_model_constructor_rejects_non_boolean_flags(field: str) -> None:
    source = _system()
    with pytest.raises(TypeError, match="must be a boolean"):
        if field == "atom_aromatic":
            replace(source.atoms[0], aromatic="false")
        elif field == "bond_aromatic":
            replace(source.bonds[0], aromatic=1)
        elif field == "residue_hetero":
            replace(source.residues[0], hetero="false")
        elif field == "provenance_preparation_ready":
            replace(source.provenance, preparation_ready=1)
        else:
            replace(source.provenance, claim_safe="false")


def test_canonical_model_constructor_rejects_lossy_numeric_coercion() -> None:
    source = _system()
    with pytest.raises(TypeError, match="atom.index must be an integer"):
        replace(source.atoms[0], index=0.9)
    with pytest.raises(TypeError, match="atom.formal_charge must be an integer"):
        replace(source.atoms[0], formal_charge=1.9)
    with pytest.raises(TypeError, match="atom.isotope_mass_number must be an integer"):
        replace(source.atoms[0], isotope_mass_number=13.9)
    with pytest.raises(TypeError, match="atom.atom_map must be an integer"):
        replace(source.atoms[0], atom_map=True)
    with pytest.raises(TypeError, match="atom.occupancy must be a float"):
        replace(source.atoms[0], occupancy=True)
    with pytest.raises(TypeError, match="bond.order must be a float"):
        replace(source.bonds[0], order=1)
    with pytest.raises(TypeError, match="residue.sequence_number must be an integer"):
        replace(source.residues[0], sequence_number=1.2)
    with pytest.raises(TypeError, match=r"residue.atom_indices\[0\] must be an integer"):
        replace(source.residues[0], atom_indices=(True, 1, 2))


def test_formal_charge_known_is_typed_and_round_trips() -> None:
    source = _system()
    unknown_atom = replace(source.atoms[0], formal_charge_known=False)
    unknown = replace(source, atoms=(unknown_atom, *source.atoms[1:]))
    restored = round_trip_all_atom_system(unknown)
    assert restored.atoms[0].formal_charge == 0
    assert restored.atoms[0].formal_charge_known is False
    with pytest.raises(TypeError, match="formal_charge_known must be a boolean"):
        replace(source.atoms[0], formal_charge_known=0)


def test_atom_map_is_typed_round_trips_and_is_positive_and_system_wide_unique() -> None:
    source = _system()
    restored = round_trip_all_atom_system(source)
    assert restored.atoms[0].atom_map == 17
    assert restored.atoms[1].atom_map is None

    nonpositive = replace(
        source,
        atoms=(replace(source.atoms[0], atom_map=0), *source.atoms[1:]),
    )
    nonpositive_report = validate_all_atom_system(nonpositive)
    assert {issue.code for issue in nonpositive_report.errors} == {"nonpositive_atom_map"}

    duplicate = replace(
        source,
        atoms=(source.atoms[0], replace(source.atoms[1], atom_map=17), source.atoms[2]),
    )
    duplicate_report = validate_all_atom_system(duplicate)
    assert {issue.code for issue in duplicate_report.errors} == {"duplicate_atom_map"}


def test_topology_only_snapshot_preserves_declared_zero_model_shape() -> None:
    source = _system(coordinates=torch.empty((0, 3, 3), dtype=torch.float64))
    report = validate_all_atom_system(source)
    assert report.valid
    assert {issue.code for issue in report.warnings} == {"coordinates_missing"}
    assert source.has_coordinates is False
    assert source.model_count == 0

    payload = serialize_all_atom_system(source)
    document = json.loads(payload.decode("utf-8"))
    assert document["coordinates"] == {
        "data": [],
        "dtype": "float64",
        "shape": [0, 3, 3],
    }
    restored = deserialize_all_atom_system(payload)
    assert restored.coordinates.shape == (0, 3, 3)
    assert restored.coordinates.dtype == torch.float64
    assert restored.has_coordinates is False
    assert canonical_all_atom_systems_equal(source, restored)


def test_topology_only_snapshot_rejects_data_incompatible_with_zero_model_shape() -> None:
    source = _system(coordinates=torch.empty((0, 3, 3), dtype=torch.float32))
    document = json.loads(serialize_all_atom_system(source).decode("utf-8"))
    document["coordinates"]["data"] = [[]]
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with pytest.raises(MolecularSerializationError, match="declared dimension 0"):
        deserialize_all_atom_system(payload)


def test_unit_cell_rejects_non_boolean_periodic_flags() -> None:
    with pytest.raises(TypeError, match="periodic flags must be booleans"):
        UnitCell(vectors=torch.eye(3), periodic=(True, "false", True))


def test_canonical_snapshot_mutation_breaks_round_trip_or_digest() -> None:
    source = _system()
    baseline = serialize_all_atom_system(source)
    baseline_digest = canonical_all_atom_snapshot_digest(source)

    mutated_system = replace(source, system_id="changed-id")
    assert serialize_all_atom_system(mutated_system) != baseline
    assert canonical_all_atom_snapshot_digest(mutated_system) != baseline_digest

    payload = json.loads(baseline.decode("utf-8"))
    payload["atoms"][0]["formal_charge"] = 99
    restored = deserialize_all_atom_system(json.dumps(payload, sort_keys=True).encode("utf-8"))
    assert restored != source


def test_canonical_equality_includes_metadata_and_avoids_tensor_dataclass_equality() -> None:
    source = _system()
    restored = round_trip_all_atom_system(source)
    assert canonical_all_atom_systems_equal(source, restored)

    changed_metadata = replace(source, metadata={**source.metadata, "new": "value"})
    assert not canonical_all_atom_systems_equal(source, changed_metadata)

    with pytest.raises(TypeError, match="two AllAtomSystem"):
        canonical_all_atom_systems_equal(source, object())
