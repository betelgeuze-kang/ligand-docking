"""Canonical serialization and SHA-256 identities for Engine v2 molecular state."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
import hashlib
import json
import math
import os
from pathlib import Path
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
    value = getattr(torch, str(name), None)
    if not isinstance(value, torch.dtype):
        raise CanonicalSerializationError(f"unsupported tensor dtype {name!r}")
    return value


def _decode_canonical_value(value: Any, *, path: str = "$") -> Any:
    if isinstance(value, list):
        return [_decode_canonical_value(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    if not isinstance(value, dict):
        return value
    if set(value) == {"$float_hex"}:
        try:
            number = float.fromhex(str(value["$float_hex"]))
        except (TypeError, ValueError) as exc:
            raise CanonicalSerializationError(f"invalid hexadecimal float at {path}") from exc
        if not math.isfinite(number):
            raise CanonicalSerializationError(f"non-finite decoded float at {path}")
        return number
    if set(value) == {"$path"}:
        return str(value["$path"])
    if set(value) == {"$tensor"}:
        tensor_payload = value["$tensor"]
        if not isinstance(tensor_payload, dict):
            raise CanonicalSerializationError(f"invalid tensor payload at {path}")
        try:
            dtype = _torch_dtype(str(tensor_payload["dtype"]))
            shape = tuple(int(size) for size in tensor_payload["shape"])
            raw_values = tensor_payload["values"]
        except (KeyError, TypeError, ValueError) as exc:
            raise CanonicalSerializationError(f"invalid tensor metadata at {path}") from exc
        if any(size < 0 for size in shape) or not isinstance(raw_values, list):
            raise CanonicalSerializationError(f"invalid tensor shape or values at {path}")
        decoded_values = [
            _decode_canonical_value(item, path=f"{path}.values[{index}]")
            for index, item in enumerate(raw_values)
        ]
        expected = math.prod(shape)
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


def _construct_system(payload: Mapping[str, Any], *, device: torch.device | str) -> AllAtomSystem:
    topology = _require_mapping(payload.get("topology"), path="$.system.topology")
    coordinate_payload = _require_mapping(payload.get("coordinates"), path="$.system.coordinates")
    provenance_payload = _require_mapping(payload.get("provenance"), path="$.system.provenance")

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
        if not isinstance(periodic, list):
            raise CanonicalSerializationError("canonical cell periodic flags are missing")
        cell = UnitCell(
            vectors=cell_vectors.to(device=device, dtype=coordinates.dtype),
            periodic=tuple(bool(value) for value in periodic),
        )

    atoms = tuple(Atom(**dict(row)) for row in topology.get("atoms", ()))
    bonds = tuple(Bond(**dict(row)) for row in topology.get("bonds", ()))
    residues = tuple(
        Residue(
            **{
                **dict(row),
                "atom_indices": tuple(row.get("atom_indices", ())),
            }
        )
        for row in topology.get("residues", ())
    )
    chains = tuple(
        Chain(
            **{
                **dict(row),
                "residue_indices": tuple(row.get("residue_indices", ())),
            }
        )
        for row in topology.get("chains", ())
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
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanonicalSerializationError("canonical system document must be UTF-8 JSON") from exc
    decoded = _decode_canonical_value(document)
    mapping = _require_mapping(decoded, path="$")
    if mapping.get("schema_id") != CANONICAL_SYSTEM_JSON_SCHEMA_ID:
        raise CanonicalSerializationError("unsupported canonical system JSON schema")
    payload = _require_mapping(mapping.get("system"), path="$.system")
    expected_digest = str(mapping.get("system_sha256", ""))
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
    temporary.write_bytes(canonical_system_json_bytes(system) + b"\n")
    os.replace(temporary, output)
    return output


__all__ = [
    "CANONICAL_SYSTEM_JSON_SCHEMA_ID",
    "CanonicalSerializationError",
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
