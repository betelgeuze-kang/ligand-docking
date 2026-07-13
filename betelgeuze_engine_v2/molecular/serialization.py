"""Deterministic canonical snapshot serialization for all-atom systems."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping

import torch

from betelgeuze_engine_v2.contracts import ContractVersionError, require_compatible_schema
from .models import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
)
from .validation import MolecularValidationError, require_valid_all_atom_system

CANONICAL_SNAPSHOT_VERSION = "1.2.0"
_MAX_CANONICAL_SNAPSHOT_BYTES = 64 * 1024 * 1024

_SUPPORTED_TENSOR_DTYPES = frozenset({torch.float32, torch.float64})

_ATOM_KEYS = frozenset(
    {
        "index",
        "name",
        "element",
        "atomic_number",
        "residue_index",
        "formal_charge",
        "formal_charge_known",
        "partial_charge_e",
        "mass_da",
        "isotope_mass_number",
        "serial",
        "atom_map",
        "altloc",
        "occupancy",
        "b_factor",
        "aromatic",
        "stereo",
        "metadata",
    }
)
_BOND_KEYS = frozenset(
    {
        "index",
        "atom_i",
        "atom_j",
        "order",
        "aromatic",
        "stereo",
        "source",
        "metadata",
    }
)
_RESIDUE_KEYS = frozenset(
    {
        "index",
        "name",
        "chain_index",
        "sequence_number",
        "atom_indices",
        "insertion_code",
        "entity_type",
        "hetero",
        "metadata",
    }
)
_CHAIN_KEYS = frozenset({"index", "chain_id", "residue_indices", "entity_id", "metadata"})
_CELL_KEYS = frozenset({"vectors", "periodic"})
_PROVENANCE_KEYS = frozenset(
    {
        "source_format",
        "source_id",
        "source_sha256",
        "parser_name",
        "parser_version",
        "operations",
        "parent_sha256",
        "preparation_ready",
        "claim_safe",
        "metadata",
    }
)
_TENSOR_KEYS = frozenset({"dtype", "shape", "data"})
_SNAPSHOT_KEYS = frozenset(
    {
        "snapshot_version",
        "schema_id",
        "system_id",
        "atoms",
        "bonds",
        "residues",
        "chains",
        "coordinates",
        "provenance",
        "cell",
        "coordinate_unit",
        "metadata",
    }
)


class MolecularSerializationError(ValueError):
    """Raised when canonical snapshot serialization or deserialization fails."""


def _require_exact_keys(payload: Mapping[str, Any], *, allowed: frozenset[str], location: str) -> None:
    observed = set(payload.keys())
    extra = observed - allowed
    missing = allowed - observed
    if extra or missing:
        details: list[str] = []
        if missing:
            details.append(f"missing {sorted(missing)}")
        if extra:
            details.append(f"unexpected {sorted(extra)}")
        raise MolecularSerializationError(f"{location}: {'; '.join(details)}")


def _require_json_type(value: Any, expected: type | tuple[type, ...], *, location: str) -> Any:
    if not isinstance(value, expected):
        raise MolecularSerializationError(f"{location}: expected {expected}, got {type(value).__name__}")
    return value


def _require_string(value: Any, *, location: str) -> str:
    if type(value) is not str:
        raise MolecularSerializationError(f"{location}: expected string, got {type(value).__name__}")
    return value


def _require_boolean(value: Any, *, location: str) -> bool:
    if type(value) is not bool:
        raise MolecularSerializationError(f"{location}: expected boolean, got {type(value).__name__}")
    return value


def _require_integer(value: Any, *, location: str) -> int:
    if type(value) is not int:
        raise MolecularSerializationError(f"{location}: expected integer, got {type(value).__name__}")
    return value


def _finite_float(value: Any, *, location: str) -> float:
    if type(value) is not float:
        raise MolecularSerializationError(f"{location}: expected finite float, got {type(value).__name__}")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise MolecularSerializationError(f"{location}: invalid finite number: {exc}") from exc
    if not math.isfinite(number):
        raise MolecularSerializationError(f"{location}: non-finite float")
    return number


def _json_metadata_value(value: Any, *, location: str) -> Any:
    if value is None:
        return None
    if type(value) is bool:
        return value
    if type(value) is int:
        return int(value)
    if type(value) is str:
        return value
    if type(value) is float:
        return _finite_float(value, location=location)
    if isinstance(value, (list, tuple)):
        return [_json_metadata_value(item, location=f"{location}[]") for item in value]
    if isinstance(value, Mapping):
        return _json_metadata_dict(value, location=location)
    raise MolecularSerializationError(f"{location}: unsupported metadata type {type(value).__name__}")


def _json_metadata_dict(value: Mapping[str, Any], *, location: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in sorted(value.keys(), key=str):
        if not isinstance(key, str):
            raise MolecularSerializationError(f"{location}: metadata keys must be strings")
        payload[key] = _json_metadata_value(value[key], location=f"{location}.{key}")
    return payload


def _parse_metadata_dict(value: Any, *, location: str) -> dict[str, Any]:
    return _require_json_type(value, dict, location=location)


def _dtype_name(dtype: torch.dtype) -> str:
    if dtype not in _SUPPORTED_TENSOR_DTYPES:
        raise MolecularSerializationError(f"unsupported tensor dtype {dtype}")
    return "float32" if dtype is torch.float32 else "float64"


def _dtype_from_name(name: str, *, location: str) -> torch.dtype:
    text = _require_string(name, location=f"{location}.dtype")
    if text == "float32":
        return torch.float32
    if text == "float64":
        return torch.float64
    raise MolecularSerializationError(f"{location}: unsupported tensor dtype {name!r}")


def _canonical_tensor_data(tensor: torch.Tensor, *, location: str) -> dict[str, Any]:
    if not isinstance(tensor, torch.Tensor):
        raise MolecularSerializationError(f"{location}: expected torch.Tensor")
    if tensor.dtype not in _SUPPORTED_TENSOR_DTYPES:
        raise MolecularSerializationError(f"{location}: unsupported tensor dtype {tensor.dtype}")
    value = tensor.detach().cpu().contiguous()
    if not bool(torch.isfinite(value).all().item()):
        raise MolecularSerializationError(f"{location}: tensor values must be finite")
    return {
        "dtype": _dtype_name(value.dtype),
        "shape": [int(dim) for dim in value.shape],
        "data": value.tolist(),
    }


def _validate_tensor_data_shape(
    value: Any,
    *,
    shape: tuple[int, ...],
    location: str,
) -> None:
    """Validate nested tensor data without losing dimensions after a zero axis."""

    if not shape:
        if type(value) is not float:
            raise MolecularSerializationError(f"{location}: tensor values must be finite floats")
        _finite_float(value, location=location)
        return
    if type(value) is not list:
        raise MolecularSerializationError(
            f"{location}: tensor shape mismatch; expected a list for declared tensor dimension {shape[0]}"
        )
    if len(value) != shape[0]:
        raise MolecularSerializationError(
            f"{location}: tensor shape mismatch; data length {len(value)} "
            f"does not match declared dimension {shape[0]}"
        )
    for index, item in enumerate(value):
        _validate_tensor_data_shape(
            item,
            shape=shape[1:],
            location=f"{location}[{index}]",
        )


def _parse_tensor_payload(payload: Any, *, location: str) -> torch.Tensor:
    mapping = _require_json_type(payload, dict, location=location)
    _require_exact_keys(mapping, allowed=_TENSOR_KEYS, location=location)
    dtype = _dtype_from_name(mapping["dtype"], location=location)
    shape = _require_json_type(mapping["shape"], list, location=f"{location}.shape")
    if not shape or not all(type(dim) is int and dim >= 0 for dim in shape):
        raise MolecularSerializationError(f"{location}.shape: must be a non-empty list of non-negative integers")
    expected_shape = tuple(int(dim) for dim in shape)
    data = mapping["data"]
    _validate_tensor_data_shape(
        data,
        shape=expected_shape,
        location=f"{location}.data",
    )
    try:
        tensor = (
            torch.empty(expected_shape, dtype=dtype)
            if 0 in expected_shape
            else torch.as_tensor(data, dtype=dtype)
        )
    except (TypeError, ValueError, OverflowError, RuntimeError) as exc:
        raise MolecularSerializationError(f"{location}.data: invalid tensor payload: {exc}") from exc
    if tuple(tensor.shape) != expected_shape:
        raise MolecularSerializationError(
            f"{location}: tensor shape {tuple(tensor.shape)} does not match declared shape {expected_shape}"
        )
    if not bool(torch.isfinite(tensor).all().item()):
        raise MolecularSerializationError(f"{location}: tensor values must be finite")
    return tensor.contiguous()


def _atom_to_json(atom: Atom) -> dict[str, Any]:
    return {
        "index": atom.index,
        "name": atom.name,
        "element": atom.element,
        "atomic_number": atom.atomic_number,
        "residue_index": atom.residue_index,
        "formal_charge": atom.formal_charge,
        "formal_charge_known": atom.formal_charge_known,
        "partial_charge_e": atom.partial_charge_e,
        "mass_da": atom.mass_da,
        "isotope_mass_number": atom.isotope_mass_number,
        "serial": atom.serial,
        "atom_map": atom.atom_map,
        "altloc": atom.altloc,
        "occupancy": atom.occupancy,
        "b_factor": atom.b_factor,
        "aromatic": atom.aromatic,
        "stereo": atom.stereo,
        "metadata": _json_metadata_dict(atom.metadata, location="atom.metadata"),
    }


def _bond_to_json(bond: Bond) -> dict[str, Any]:
    return {
        "index": bond.index,
        "atom_i": bond.atom_i,
        "atom_j": bond.atom_j,
        "order": bond.order,
        "aromatic": bond.aromatic,
        "stereo": bond.stereo,
        "source": bond.source,
        "metadata": _json_metadata_dict(bond.metadata, location="bond.metadata"),
    }


def _residue_to_json(residue: Residue) -> dict[str, Any]:
    return {
        "index": residue.index,
        "name": residue.name,
        "chain_index": residue.chain_index,
        "sequence_number": residue.sequence_number,
        "atom_indices": list(residue.atom_indices),
        "insertion_code": residue.insertion_code,
        "entity_type": residue.entity_type,
        "hetero": residue.hetero,
        "metadata": _json_metadata_dict(residue.metadata, location="residue.metadata"),
    }


def _chain_to_json(chain: Chain) -> dict[str, Any]:
    return {
        "index": chain.index,
        "chain_id": chain.chain_id,
        "residue_indices": list(chain.residue_indices),
        "entity_id": chain.entity_id,
        "metadata": _json_metadata_dict(chain.metadata, location="chain.metadata"),
    }


def _provenance_to_json(provenance: StructureProvenance) -> dict[str, Any]:
    return {
        "source_format": provenance.source_format,
        "source_id": provenance.source_id,
        "source_sha256": provenance.source_sha256,
        "parser_name": provenance.parser_name,
        "parser_version": provenance.parser_version,
        "operations": list(provenance.operations),
        "parent_sha256": list(provenance.parent_sha256),
        "preparation_ready": provenance.preparation_ready,
        "claim_safe": provenance.claim_safe,
        "metadata": _json_metadata_dict(provenance.metadata, location="provenance.metadata"),
    }


def _cell_to_json(cell: UnitCell) -> dict[str, Any]:
    return {
        "vectors": _canonical_tensor_data(cell.vectors, location="cell.vectors"),
        "periodic": [bool(flag) for flag in cell.periodic],
    }


def _system_to_snapshot_document(system: AllAtomSystem) -> dict[str, Any]:
    cell_payload = None
    if system.cell is not None:
        cell_payload = _cell_to_json(system.cell)
    return {
        "snapshot_version": CANONICAL_SNAPSHOT_VERSION,
        "schema_id": system.schema_id,
        "system_id": system.system_id,
        "atoms": [_atom_to_json(atom) for atom in system.atoms],
        "bonds": [_bond_to_json(bond) for bond in system.bonds],
        "residues": [_residue_to_json(residue) for residue in system.residues],
        "chains": [_chain_to_json(chain) for chain in system.chains],
        "coordinates": _canonical_tensor_data(system.coordinates, location="coordinates"),
        "provenance": _provenance_to_json(system.provenance),
        "cell": cell_payload,
        "coordinate_unit": system.coordinate_unit,
        "metadata": _json_metadata_dict(system.metadata, location="system.metadata"),
    }


def _canonical_snapshot_bytes(document: Mapping[str, Any]) -> bytes:
    try:
        text = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise MolecularSerializationError(f"canonical JSON encoding failed: {exc}") from exc
    payload = text.encode("utf-8")
    if len(payload) > _MAX_CANONICAL_SNAPSHOT_BYTES:
        raise MolecularSerializationError(
            "canonical snapshot exceeds the fixed byte safety limit"
        )
    return payload


def _reject_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key, value in pairs:
        if key in mapping:
            raise MolecularSerializationError(f"duplicate JSON object key {key!r}")
        mapping[key] = value
    return mapping


def _reject_nonstandard_json_constant(value: str) -> None:
    raise MolecularSerializationError(f"non-standard JSON constant {value!r} is not allowed")


def _parse_atom(payload: Any, *, location: str) -> Atom:
    mapping = _require_json_type(payload, dict, location=location)
    _require_exact_keys(mapping, allowed=_ATOM_KEYS, location=location)
    return Atom(
        index=_require_integer(mapping["index"], location=f"{location}.index"),
        name=_require_string(mapping["name"], location=f"{location}.name"),
        element=_require_string(mapping["element"], location=f"{location}.element"),
        atomic_number=_require_integer(mapping["atomic_number"], location=f"{location}.atomic_number"),
        residue_index=_require_integer(mapping["residue_index"], location=f"{location}.residue_index"),
        formal_charge=_require_integer(mapping["formal_charge"], location=f"{location}.formal_charge"),
        formal_charge_known=_require_boolean(
            mapping["formal_charge_known"],
            location=f"{location}.formal_charge_known",
        ),
        partial_charge_e=None if mapping["partial_charge_e"] is None else _finite_float(
            mapping["partial_charge_e"],
            location=f"{location}.partial_charge_e",
        ),
        mass_da=None if mapping["mass_da"] is None else _finite_float(mapping["mass_da"], location=f"{location}.mass_da"),
        isotope_mass_number=None
        if mapping["isotope_mass_number"] is None
        else _require_integer(mapping["isotope_mass_number"], location=f"{location}.isotope_mass_number"),
        serial=None
        if mapping["serial"] is None
        else _require_integer(mapping["serial"], location=f"{location}.serial"),
        atom_map=None
        if mapping["atom_map"] is None
        else _require_integer(mapping["atom_map"], location=f"{location}.atom_map"),
        altloc=_require_string(mapping["altloc"], location=f"{location}.altloc"),
        occupancy=None if mapping["occupancy"] is None else _finite_float(mapping["occupancy"], location=f"{location}.occupancy"),
        b_factor=None if mapping["b_factor"] is None else _finite_float(mapping["b_factor"], location=f"{location}.b_factor"),
        aromatic=_require_boolean(mapping["aromatic"], location=f"{location}.aromatic"),
        stereo=_require_string(mapping["stereo"], location=f"{location}.stereo"),
        metadata=_parse_metadata_dict(mapping["metadata"], location=f"{location}.metadata"),
    )


def _parse_bond(payload: Any, *, location: str) -> Bond:
    mapping = _require_json_type(payload, dict, location=location)
    _require_exact_keys(mapping, allowed=_BOND_KEYS, location=location)
    return Bond(
        index=_require_integer(mapping["index"], location=f"{location}.index"),
        atom_i=_require_integer(mapping["atom_i"], location=f"{location}.atom_i"),
        atom_j=_require_integer(mapping["atom_j"], location=f"{location}.atom_j"),
        order=_finite_float(mapping["order"], location=f"{location}.order"),
        aromatic=_require_boolean(mapping["aromatic"], location=f"{location}.aromatic"),
        stereo=_require_string(mapping["stereo"], location=f"{location}.stereo"),
        source=_require_string(mapping["source"], location=f"{location}.source"),
        metadata=_parse_metadata_dict(mapping["metadata"], location=f"{location}.metadata"),
    )


def _parse_residue(payload: Any, *, location: str) -> Residue:
    mapping = _require_json_type(payload, dict, location=location)
    _require_exact_keys(mapping, allowed=_RESIDUE_KEYS, location=location)
    atom_indices = _require_json_type(mapping["atom_indices"], list, location=f"{location}.atom_indices")
    return Residue(
        index=_require_integer(mapping["index"], location=f"{location}.index"),
        name=_require_string(mapping["name"], location=f"{location}.name"),
        chain_index=_require_integer(mapping["chain_index"], location=f"{location}.chain_index"),
        sequence_number=_require_integer(mapping["sequence_number"], location=f"{location}.sequence_number"),
        atom_indices=tuple(
            _require_integer(value, location=f"{location}.atom_indices[{index}]")
            for index, value in enumerate(atom_indices)
        ),
        insertion_code=_require_string(mapping["insertion_code"], location=f"{location}.insertion_code"),
        entity_type=_require_string(mapping["entity_type"], location=f"{location}.entity_type"),
        hetero=_require_boolean(mapping["hetero"], location=f"{location}.hetero"),
        metadata=_parse_metadata_dict(mapping["metadata"], location=f"{location}.metadata"),
    )


def _parse_chain(payload: Any, *, location: str) -> Chain:
    mapping = _require_json_type(payload, dict, location=location)
    _require_exact_keys(mapping, allowed=_CHAIN_KEYS, location=location)
    residue_indices = _require_json_type(mapping["residue_indices"], list, location=f"{location}.residue_indices")
    return Chain(
        index=_require_integer(mapping["index"], location=f"{location}.index"),
        chain_id=_require_string(mapping["chain_id"], location=f"{location}.chain_id"),
        residue_indices=tuple(
            _require_integer(value, location=f"{location}.residue_indices[{index}]")
            for index, value in enumerate(residue_indices)
        ),
        entity_id=_require_string(mapping["entity_id"], location=f"{location}.entity_id"),
        metadata=_parse_metadata_dict(mapping["metadata"], location=f"{location}.metadata"),
    )


def _parse_provenance(payload: Any, *, location: str) -> StructureProvenance:
    mapping = _require_json_type(payload, dict, location=location)
    _require_exact_keys(mapping, allowed=_PROVENANCE_KEYS, location=location)
    operations = _require_json_type(mapping["operations"], list, location=f"{location}.operations")
    parent_sha256 = _require_json_type(mapping["parent_sha256"], list, location=f"{location}.parent_sha256")
    return StructureProvenance(
        source_format=_require_string(mapping["source_format"], location=f"{location}.source_format"),
        source_id=_require_string(mapping["source_id"], location=f"{location}.source_id"),
        source_sha256=_require_string(mapping["source_sha256"], location=f"{location}.source_sha256"),
        parser_name=_require_string(mapping["parser_name"], location=f"{location}.parser_name"),
        parser_version=_require_string(mapping["parser_version"], location=f"{location}.parser_version"),
        operations=tuple(
            _require_string(value, location=f"{location}.operations[{index}]")
            for index, value in enumerate(operations)
        ),
        parent_sha256=tuple(
            _require_string(value, location=f"{location}.parent_sha256[{index}]")
            for index, value in enumerate(parent_sha256)
        ),
        preparation_ready=_require_boolean(
            mapping["preparation_ready"],
            location=f"{location}.preparation_ready",
        ),
        claim_safe=_require_boolean(mapping["claim_safe"], location=f"{location}.claim_safe"),
        metadata=_parse_metadata_dict(mapping["metadata"], location=f"{location}.metadata"),
    )


def _parse_cell(payload: Any, *, location: str) -> UnitCell:
    mapping = _require_json_type(payload, dict, location=location)
    _require_exact_keys(mapping, allowed=_CELL_KEYS, location=location)
    periodic = _require_json_type(mapping["periodic"], list, location=f"{location}.periodic")
    if len(periodic) != 3 or not all(isinstance(flag, bool) for flag in periodic):
        raise MolecularSerializationError(f"{location}.periodic: expected three booleans")
    return UnitCell(
        vectors=_parse_tensor_payload(mapping["vectors"], location=f"{location}.vectors"),
        periodic=(bool(periodic[0]), bool(periodic[1]), bool(periodic[2])),
    )


def _snapshot_document_to_system(document: Mapping[str, Any]) -> AllAtomSystem:
    _require_exact_keys(document, allowed=_SNAPSHOT_KEYS, location="snapshot")
    snapshot_version = _require_string(document["snapshot_version"], location="snapshot_version")
    if snapshot_version != CANONICAL_SNAPSHOT_VERSION:
        raise MolecularSerializationError(
            f"unsupported snapshot_version {snapshot_version!r}; expected {CANONICAL_SNAPSHOT_VERSION!r}"
        )
    schema_id = _require_string(document["schema_id"], location="schema_id")
    try:
        require_compatible_schema(schema_id)
    except ContractVersionError as exc:
        raise MolecularSerializationError(str(exc)) from exc

    atoms_payload = _require_json_type(document["atoms"], list, location="atoms")
    bonds_payload = _require_json_type(document["bonds"], list, location="bonds")
    residues_payload = _require_json_type(document["residues"], list, location="residues")
    chains_payload = _require_json_type(document["chains"], list, location="chains")
    cell_payload = document["cell"]
    if cell_payload is not None and not isinstance(cell_payload, dict):
        raise MolecularSerializationError("cell: expected object or null")

    return AllAtomSystem(
        system_id=_require_string(document["system_id"], location="system_id"),
        atoms=tuple(_parse_atom(item, location=f"atoms[{index}]") for index, item in enumerate(atoms_payload)),
        bonds=tuple(_parse_bond(item, location=f"bonds[{index}]") for index, item in enumerate(bonds_payload)),
        residues=tuple(
            _parse_residue(item, location=f"residues[{index}]") for index, item in enumerate(residues_payload)
        ),
        chains=tuple(_parse_chain(item, location=f"chains[{index}]") for index, item in enumerate(chains_payload)),
        coordinates=_parse_tensor_payload(document["coordinates"], location="coordinates"),
        provenance=_parse_provenance(document["provenance"], location="provenance"),
        cell=None if cell_payload is None else _parse_cell(cell_payload, location="cell"),
        coordinate_unit=_require_string(document["coordinate_unit"], location="coordinate_unit"),
        metadata=_parse_metadata_dict(document["metadata"], location="system.metadata"),
        schema_id=schema_id,
    )


def serialize_all_atom_system(system: AllAtomSystem) -> bytes:
    """Serialize a validated all-atom system to canonical UTF-8 JSON bytes."""

    require_valid_all_atom_system(system)
    document = _system_to_snapshot_document(system)
    return _canonical_snapshot_bytes(document)


def deserialize_all_atom_system(data: bytes) -> AllAtomSystem:
    """Deserialize canonical UTF-8 JSON bytes into a validated all-atom system."""

    if not isinstance(data, (bytes, bytearray)):
        raise MolecularSerializationError("snapshot payload must be bytes")
    if len(data) > _MAX_CANONICAL_SNAPSHOT_BYTES:
        raise MolecularSerializationError(
            "snapshot payload exceeds the fixed byte safety limit"
        )
    try:
        text = bytes(data).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MolecularSerializationError("snapshot payload must be valid UTF-8") from exc
    try:
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_object_keys,
            parse_constant=_reject_nonstandard_json_constant,
        )
    except MolecularSerializationError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise MolecularSerializationError(f"invalid JSON snapshot: {exc}") from exc
    if not isinstance(document, dict):
        raise MolecularSerializationError("snapshot root must be a JSON object")
    try:
        system = _snapshot_document_to_system(document)
        require_valid_all_atom_system(system)
    except MolecularSerializationError:
        raise
    except (
        MolecularValidationError,
        TypeError,
        ValueError,
        OverflowError,
        RuntimeError,
        RecursionError,
    ) as exc:
        raise MolecularSerializationError(f"invalid canonical snapshot: {exc}") from exc
    return system


def canonical_all_atom_snapshot_digest(system: AllAtomSystem) -> str:
    """Return the device-independent SHA-256 digest of the canonical snapshot bytes."""

    payload = serialize_all_atom_system(system)
    return hashlib.sha256(payload).hexdigest()


def canonical_all_atom_systems_equal(left: AllAtomSystem, right: AllAtomSystem) -> bool:
    """Compare complete validated systems by their device-independent canonical bytes."""

    if not isinstance(left, AllAtomSystem) or not isinstance(right, AllAtomSystem):
        raise TypeError("canonical equality requires two AllAtomSystem values")
    return serialize_all_atom_system(left) == serialize_all_atom_system(right)


def round_trip_all_atom_system(system: AllAtomSystem) -> AllAtomSystem:
    """Serialize and deserialize a system, returning the restored value."""

    return deserialize_all_atom_system(serialize_all_atom_system(system))
