"""Canonical serialization and SHA-256 identities for Engine v2 molecular state."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Mapping

import torch

from .models import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
)

CANONICAL_SYSTEM_JSON_SCHEMA_ID = "betelgeuze.engine_v2_canonical_system/1.0.0"
MAX_CANONICAL_SYSTEM_JSON_BYTES = 256 * 1024 * 1024
MAX_CANONICAL_TENSOR_ELEMENTS = 50_000_000

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_TENSOR_DTYPES = frozenset(
    {
        "bool",
        "uint8",
        "int8",
        "int16",
        "int32",
        "int64",
        "float16",
        "bfloat16",
        "float32",
        "float64",
    }
)
_DOCUMENT_FIELDS = frozenset({"schema_id", "system_sha256", "system"})
_SYSTEM_FIELDS = frozenset({"topology", "coordinates", "provenance"})
_TOPOLOGY_FIELDS = frozenset(
    {
        "schema_id",
        "system_id",
        "coordinate_unit",
        "atoms",
        "bonds",
        "residues",
        "chains",
        "cell_periodic",
        "metadata",
        "source",
    }
)
_TOPOLOGY_SOURCE_FIELDS = frozenset(
    {"format", "id", "sha256", "parser_name", "parser_version"}
)
_COORDINATE_FIELDS = frozenset(
    {"coordinate_unit", "coordinates", "cell_vectors", "cell_periodic"}
)
_ATOM_FIELDS = frozenset(
    {
        "index",
        "name",
        "element",
        "atomic_number",
        "residue_index",
        "formal_charge",
        "partial_charge_e",
        "mass_da",
        "isotope_mass_number",
        "serial",
        "altloc",
        "occupancy",
        "b_factor",
        "aromatic",
        "stereo",
        "metadata",
    }
)
_BOND_FIELDS = frozenset(
    {"index", "atom_i", "atom_j", "order", "aromatic", "stereo", "source", "metadata"}
)
_RESIDUE_FIELDS = frozenset(
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
_CHAIN_FIELDS = frozenset(
    {"index", "chain_id", "residue_indices", "entity_id", "metadata"}
)
_PROVENANCE_FIELDS = frozenset(
    {
        "source_format",
        "source_id",
        "source_sha256",
        "parser_name",
        "parser_version",
        "operations",
        "parent_sha256",
        "source_digest_verified",
        "transformation_chain_verified",
        "chemistry_validated",
        "scientifically_validated",
        "product_qualified",
        "metadata",
    }
)


class CanonicalSerializationError(ValueError):
    """Raised when a value cannot be represented without ambiguity."""


def _float_token(value: float, *, path: str) -> dict[str, str]:
    number = float(value)
    if not math.isfinite(number):
        raise CanonicalSerializationError(f"non-finite float at {path}")
    return {"$float_hex": number.hex()}


def canonical_json_value(value: Any, *, path: str = "$") -> Any:
    """Return a JSON-safe value with deterministic ordering and float encoding."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return _float_token(value, path=path)
    if isinstance(value, Path):
        return {"$path": value.as_posix()}
    if isinstance(value, torch.Tensor):
        if not value.is_floating_point() and value.dtype != torch.bool:
            data = value.detach().cpu().reshape(-1).tolist()
        elif value.dtype == torch.bool:
            data = [bool(item) for item in value.detach().cpu().reshape(-1).tolist()]
        else:
            data = [
                _float_token(float(item), path=f"{path}.values[{index}]")
                for index, item in enumerate(value.detach().cpu().reshape(-1).tolist())
            ]
        return {
            "$tensor": {
                "dtype": str(value.dtype).removeprefix("torch."),
                "shape": [int(size) for size in value.shape],
                "values": data,
            }
        }
    if is_dataclass(value):
        return {
            field.name: canonical_json_value(
                getattr(value, field.name),
                path=f"{path}.{field.name}",
            )
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key in sorted(value, key=lambda item: str(item)):
            text = str(key)
            if text in normalized:
                raise CanonicalSerializationError(
                    f"mapping keys collide after string conversion at {path}: {text!r}"
                )
            normalized[text] = canonical_json_value(value[key], path=f"{path}.{text}")
        return normalized
    if isinstance(value, (tuple, list)):
        return [
            canonical_json_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise CanonicalSerializationError(
        f"unsupported canonical value at {path}: {type(value).__name__}"
    )


def canonical_json_bytes(value: Any) -> bytes:
    normalized = canonical_json_value(value)
    return json.dumps(
        normalized,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_canonical(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def canonical_topology_payload(system: AllAtomSystem) -> dict[str, Any]:
    """Return the coordinate-independent topology and provenance-source payload."""

    return {
        "schema_id": system.schema_id,
        "system_id": system.system_id,
        "coordinate_unit": system.coordinate_unit,
        "atoms": system.atoms,
        "bonds": system.bonds,
        "residues": system.residues,
        "chains": system.chains,
        "cell_periodic": None if system.cell is None else system.cell.periodic,
        "metadata": system.metadata,
        "source": {
            "format": system.provenance.source_format,
            "id": system.provenance.source_id,
            "sha256": system.provenance.source_sha256,
            "parser_name": system.provenance.parser_name,
            "parser_version": system.provenance.parser_version,
        },
    }


def canonical_coordinates_payload(system: AllAtomSystem) -> dict[str, Any]:
    return {
        "coordinate_unit": system.coordinate_unit,
        "coordinates": system.coordinates,
        "cell_vectors": None if system.cell is None else system.cell.vectors,
        "cell_periodic": None if system.cell is None else system.cell.periodic,
    }


def canonical_system_payload(system: AllAtomSystem) -> dict[str, Any]:
    return {
        "topology": canonical_topology_payload(system),
        "coordinates": canonical_coordinates_payload(system),
        "provenance": system.provenance,
    }


def canonical_topology_sha256(system: AllAtomSystem) -> str:
    return sha256_canonical(canonical_topology_payload(system))


def canonical_coordinates_sha256(system: AllAtomSystem) -> str:
    return sha256_canonical(canonical_coordinates_payload(system))


def canonical_system_sha256(system: AllAtomSystem) -> str:
    return sha256_canonical(canonical_system_payload(system))


def canonical_system_document(system: AllAtomSystem) -> dict[str, Any]:
    """Return a self-verifying canonical JSON document for one molecular system."""

    payload = canonical_system_payload(system)
    return {
        "schema_id": CANONICAL_SYSTEM_JSON_SCHEMA_ID,
        "system_sha256": sha256_canonical(payload),
        "system": payload,
    }


def canonical_system_json_bytes(system: AllAtomSystem) -> bytes:
    return canonical_json_bytes(canonical_system_document(system))


def _torch_dtype(name: str) -> torch.dtype:
    if name not in _SUPPORTED_TENSOR_DTYPES:
        raise CanonicalSerializationError(f"unsupported tensor dtype {name!r}")
    value = getattr(torch, str(name), None)
    if not isinstance(value, torch.dtype):
        raise CanonicalSerializationError(f"unsupported tensor dtype {name!r}")
    return value


def _decode_canonical_value(value: Any, *, path: str = "$") -> Any:
    if isinstance(value, list):
        return [_decode_canonical_value(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    if not isinstance(value, dict):
        return value
    reserved_keys = {"$float_hex", "$path", "$tensor"}.intersection(value)
    if reserved_keys and len(value) != 1:
        raise CanonicalSerializationError(
            f"reserved canonical tag mixed with other fields at {path}"
        )
    if set(value) == {"$float_hex"}:
        token = value["$float_hex"]
        if not isinstance(token, str):
            raise CanonicalSerializationError(
                f"hexadecimal float token must be a string at {path}"
            )
        try:
            number = float.fromhex(token)
        except (TypeError, ValueError) as exc:
            raise CanonicalSerializationError(f"invalid hexadecimal float at {path}") from exc
        if not math.isfinite(number):
            raise CanonicalSerializationError(f"non-finite decoded float at {path}")
        if token != number.hex():
            raise CanonicalSerializationError(
                f"non-canonical hexadecimal float at {path}"
            )
        return number
    if set(value) == {"$path"}:
        raw_path = value["$path"]
        if not isinstance(raw_path, str):
            raise CanonicalSerializationError(
                f"canonical path token must be a string at {path}"
            )
        decoded_path = Path(raw_path)
        if decoded_path.as_posix() != raw_path:
            raise CanonicalSerializationError(f"non-canonical path at {path}")
        return decoded_path
    if set(value) == {"$tensor"}:
        tensor_payload = value["$tensor"]
        if not isinstance(tensor_payload, dict):
            raise CanonicalSerializationError(f"invalid tensor payload at {path}")
        _require_exact_fields(
            tensor_payload,
            expected={"dtype", "shape", "values"},
            path=f"{path}.$tensor",
        )
        try:
            dtype_name = tensor_payload["dtype"]
            raw_shape = tensor_payload["shape"]
            raw_values = tensor_payload["values"]
        except (KeyError, TypeError, ValueError) as exc:
            raise CanonicalSerializationError(f"invalid tensor metadata at {path}") from exc
        if not isinstance(dtype_name, str):
            raise CanonicalSerializationError(f"invalid tensor dtype at {path}")
        dtype = _torch_dtype(dtype_name)
        if not isinstance(raw_shape, list) or any(
            isinstance(size, bool) or not isinstance(size, int) for size in raw_shape
        ):
            raise CanonicalSerializationError(f"invalid tensor shape at {path}")
        shape = tuple(raw_shape)
        if any(size < 0 for size in shape) or not isinstance(raw_values, list):
            raise CanonicalSerializationError(f"invalid tensor shape or values at {path}")
        expected = math.prod(shape)
        if expected > MAX_CANONICAL_TENSOR_ELEMENTS:
            raise CanonicalSerializationError(
                f"tensor element count exceeds limit at {path}"
            )
        decoded_values = [
            _decode_canonical_value(item, path=f"{path}.values[{index}]")
            for index, item in enumerate(raw_values)
        ]
        if len(decoded_values) != expected:
            raise CanonicalSerializationError(
                f"tensor value count mismatch at {path}: expected {expected}, got {len(decoded_values)}"
            )
        try:
            return torch.tensor(decoded_values, dtype=dtype).reshape(shape)
        except (TypeError, RuntimeError, ValueError) as exc:
            raise CanonicalSerializationError(f"invalid tensor values at {path}") from exc
    return {
        str(key): _decode_canonical_value(item, path=f"{path}.{key}")
        for key, item in value.items()
    }


def _require_mapping(value: Any, *, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CanonicalSerializationError(f"expected mapping at {path}")
    return value


def _require_exact_fields(
    value: Mapping[str, Any],
    *,
    expected: set[str] | frozenset[str],
    path: str,
) -> None:
    observed = set(value)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    if missing or unexpected:
        detail = []
        if missing:
            detail.append(f"missing={missing}")
        if unexpected:
            detail.append(f"unexpected={unexpected}")
        raise CanonicalSerializationError(
            f"non-canonical fields at {path}: {', '.join(detail)}"
        )


def _require_rows(
    value: Any,
    *,
    expected_fields: frozenset[str],
    path: str,
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        raise CanonicalSerializationError(f"expected array at {path}")
    rows = []
    for index, row in enumerate(value):
        row_path = f"{path}[{index}]"
        mapping = _require_mapping(row, path=row_path)
        _require_exact_fields(mapping, expected=expected_fields, path=row_path)
        rows.append(mapping)
    return tuple(rows)


def _construct_system(
    payload: Mapping[str, Any],
    *,
    device: torch.device | str,
) -> AllAtomSystem:
    _require_exact_fields(payload, expected=_SYSTEM_FIELDS, path="$.system")
    topology = _require_mapping(payload.get("topology"), path="$.system.topology")
    coordinate_payload = _require_mapping(payload.get("coordinates"), path="$.system.coordinates")
    provenance_payload = _require_mapping(payload.get("provenance"), path="$.system.provenance")
    _require_exact_fields(
        topology,
        expected=_TOPOLOGY_FIELDS,
        path="$.system.topology",
    )
    _require_exact_fields(
        coordinate_payload,
        expected=_COORDINATE_FIELDS,
        path="$.system.coordinates",
    )
    _require_exact_fields(
        provenance_payload,
        expected=_PROVENANCE_FIELDS,
        path="$.system.provenance",
    )
    source_payload = _require_mapping(
        topology.get("source"),
        path="$.system.topology.source",
    )
    _require_exact_fields(
        source_payload,
        expected=_TOPOLOGY_SOURCE_FIELDS,
        path="$.system.topology.source",
    )

    coordinates = coordinate_payload.get("coordinates")
    if not isinstance(coordinates, torch.Tensor):
        raise CanonicalSerializationError("canonical system coordinates are not a tensor")
    coordinates = coordinates.to(device=device)
    cell_vectors = coordinate_payload.get("cell_vectors")
    periodic = coordinate_payload.get("cell_periodic")
    cell = None
    if cell_vectors is not None:
        if not isinstance(cell_vectors, torch.Tensor):
            raise CanonicalSerializationError("canonical cell vectors are not a tensor")
        if (
            not isinstance(periodic, list)
            or len(periodic) != 3
            or any(not isinstance(value, bool) for value in periodic)
        ):
            raise CanonicalSerializationError("canonical cell periodic flags are missing")
        periodic_flags = (bool(periodic[0]), bool(periodic[1]), bool(periodic[2]))
        cell = UnitCell(
            vectors=cell_vectors.to(device=device, dtype=coordinates.dtype),
            periodic=periodic_flags,
        )
    elif periodic is not None:
        raise CanonicalSerializationError(
            "canonical cell periodic flags require cell vectors"
        )

    atom_rows = _require_rows(
        topology.get("atoms"),
        expected_fields=_ATOM_FIELDS,
        path="$.system.topology.atoms",
    )
    bond_rows = _require_rows(
        topology.get("bonds"),
        expected_fields=_BOND_FIELDS,
        path="$.system.topology.bonds",
    )
    residue_rows = _require_rows(
        topology.get("residues"),
        expected_fields=_RESIDUE_FIELDS,
        path="$.system.topology.residues",
    )
    chain_rows = _require_rows(
        topology.get("chains"),
        expected_fields=_CHAIN_FIELDS,
        path="$.system.topology.chains",
    )
    atoms = tuple(Atom(**dict(row)) for row in atom_rows)
    bonds = tuple(Bond(**dict(row)) for row in bond_rows)
    residues = tuple(
        Residue(
            **{
                **dict(row),
                "atom_indices": tuple(row.get("atom_indices", ())),
            }
        )
        for row in residue_rows
    )
    chains = tuple(
        Chain(
            **{
                **dict(row),
                "residue_indices": tuple(row.get("residue_indices", ())),
            }
        )
        for row in chain_rows
    )
    provenance = StructureProvenance(
        **{
            **dict(provenance_payload),
            "operations": tuple(provenance_payload.get("operations", ())),
            "parent_sha256": tuple(provenance_payload.get("parent_sha256", ())),
        }
    )
    return AllAtomSystem(
        system_id=str(topology.get("system_id", "")),
        atoms=atoms,
        bonds=bonds,
        residues=residues,
        chains=chains,
        coordinates=coordinates,
        provenance=provenance,
        cell=cell,
        coordinate_unit=str(topology.get("coordinate_unit", "angstrom")),
        metadata=dict(topology.get("metadata", {})),
        schema_id=str(topology.get("schema_id", "")),
    )


def all_atom_system_from_canonical_json(
    source: str | bytes,
    *,
    device: torch.device | str = "cpu",
) -> AllAtomSystem:
    """Load and verify one canonical Engine v2 system JSON document."""

    raw = source.encode("utf-8") if isinstance(source, str) else source
    if not isinstance(raw, bytes):
        raise TypeError("canonical system source must be str or bytes")
    if len(raw) > MAX_CANONICAL_SYSTEM_JSON_BYTES:
        raise CanonicalSerializationError(
            "canonical system document exceeds the byte limit"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        mapping: dict[str, Any] = {}
        for key, value in pairs:
            if key in mapping:
                raise CanonicalSerializationError(
                    f"duplicate JSON object key {key!r}"
                )
            mapping[key] = value
        return mapping

    def reject_nonfinite_constant(value: str) -> None:
        raise CanonicalSerializationError(
            f"non-standard JSON numeric constant {value!r}"
        )

    try:
        text = raw.decode("utf-8")
        document = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite_constant,
        )
    except CanonicalSerializationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanonicalSerializationError("canonical system document must be UTF-8 JSON") from exc
    if raw != canonical_json_bytes(document):
        raise CanonicalSerializationError(
            "canonical system document is not exact canonical JSON"
        )
    decoded = _decode_canonical_value(document)
    mapping = _require_mapping(decoded, path="$")
    _require_exact_fields(mapping, expected=_DOCUMENT_FIELDS, path="$")
    if mapping.get("schema_id") != CANONICAL_SYSTEM_JSON_SCHEMA_ID:
        raise CanonicalSerializationError("unsupported canonical system JSON schema")
    payload = _require_mapping(mapping.get("system"), path="$.system")
    expected_digest = mapping.get("system_sha256")
    if not isinstance(expected_digest, str) or _SHA256_RE.fullmatch(expected_digest) is None:
        raise CanonicalSerializationError(
            "canonical system SHA-256 must be lowercase hexadecimal"
        )
    actual_digest = sha256_canonical(payload)
    if expected_digest != actual_digest:
        raise CanonicalSerializationError("canonical system SHA-256 mismatch")
    system = _construct_system(payload, device=device)
    if canonical_system_sha256(system) != expected_digest:
        raise CanonicalSerializationError("reconstructed system identity does not match document")
    return system


def write_canonical_system_json(system: AllAtomSystem, path: str | Path) -> Path:
    """Atomically write one canonical system document."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp-{os.getpid()}")
    temporary.write_bytes(canonical_system_json_bytes(system))
    os.replace(temporary, output)
    return output


__all__ = [
    "CANONICAL_SYSTEM_JSON_SCHEMA_ID",
    "CanonicalSerializationError",
    "MAX_CANONICAL_SYSTEM_JSON_BYTES",
    "MAX_CANONICAL_TENSOR_ELEMENTS",
    "all_atom_system_from_canonical_json",
    "canonical_coordinates_payload",
    "canonical_coordinates_sha256",
    "canonical_json_bytes",
    "canonical_json_value",
    "canonical_system_document",
    "canonical_system_json_bytes",
    "canonical_system_payload",
    "canonical_system_sha256",
    "canonical_topology_payload",
    "canonical_topology_sha256",
    "sha256_canonical",
    "write_canonical_system_json",
]
