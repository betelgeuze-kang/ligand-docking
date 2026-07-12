"""Canonical serialization and SHA-256 identities for Engine v2 molecular state."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import torch

from .models import AllAtomSystem


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
