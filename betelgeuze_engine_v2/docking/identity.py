"""Canonical identities for bounded docking problems and search spaces."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, Mapping

import torch

_DOCKING_PROBLEM_SCHEMA_ID = "betelgeuze.engine_v2_docking_problem/1.1.0"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ZERO_SHA256 = "0" * 64


class DockingIdentityError(ValueError):
    """A docking identity is incomplete or not canonical."""


def _digest(value: str, *, name: str, allow_empty: bool = False) -> str:
    text = str(value or "").strip().lower()
    if allow_empty and not text:
        return ""
    if _SHA256_RE.fullmatch(text) is None:
        raise DockingIdentityError(f"{name} must be a lowercase SHA-256")
    return text


def _freeze_json(value: Any, *, path: str = "metadata") -> Any:
    """Return a recursively immutable, canonical-JSON-compatible value."""

    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DockingIdentityError(f"{path} contains a non-finite float")
        return float(value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise DockingIdentityError(f"{path} keys must be strings")
        return MappingProxyType(
            {
                key: _freeze_json(value[key], path=f"{path}.{key}")
                for key in sorted(value)
            }
        )
    if isinstance(value, (tuple, list)):
        return tuple(
            _freeze_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    raise DockingIdentityError(
        f"{path} contains unsupported JSON value {type(value).__name__}"
    )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _canonical_sha256(payload: object) -> str:
    try:
        encoded = json.dumps(
            _thaw_json(payload),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DockingIdentityError("docking identity is not canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _tensor_payload(tensor: torch.Tensor | None) -> object:
    if tensor is None:
        return None
    values = (
        tensor.detach()
        .to(dtype=torch.float64, device="cpu")
        .contiguous()
        .reshape(-1)
        .tolist()
    )
    return {
        "shape": [int(size) for size in tensor.shape],
        "values_hex": [float(value).hex() for value in values],
    }


@dataclass(frozen=True)
class DockingProblemIdentity:
    """Immutable identity of receptor, ligand, pocket, and coordinate frame."""

    receptor_system_sha256: str
    ligand_system_sha256: str
    pocket_definition_sha256: str = ""
    coordinate_frame_id: str = "receptor_input_frame"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_id: str = _DOCKING_PROBLEM_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != _DOCKING_PROBLEM_SCHEMA_ID:
            raise DockingIdentityError("unsupported docking problem schema")
        object.__setattr__(
            self,
            "receptor_system_sha256",
            _digest(self.receptor_system_sha256, name="receptor_system_sha256"),
        )
        object.__setattr__(
            self,
            "ligand_system_sha256",
            _digest(self.ligand_system_sha256, name="ligand_system_sha256"),
        )
        object.__setattr__(
            self,
            "pocket_definition_sha256",
            _digest(
                self.pocket_definition_sha256,
                name="pocket_definition_sha256",
                allow_empty=True,
            ),
        )
        frame = str(self.coordinate_frame_id or "").strip()
        if not frame:
            raise DockingIdentityError("coordinate_frame_id must be non-empty")
        object.__setattr__(self, "coordinate_frame_id", frame)
        metadata = _freeze_json(dict(self.metadata))
        _canonical_sha256(metadata)
        object.__setattr__(self, "metadata", metadata)

    @classmethod
    def unbound(cls) -> "DockingProblemIdentity":
        """Compatibility identity for explicitly internal receptor-free tests."""

        return cls(
            receptor_system_sha256=_ZERO_SHA256,
            ligand_system_sha256=_ZERO_SHA256,
            coordinate_frame_id="unbound_internal_scaffold",
            metadata={"bound": False},
        )

    @property
    def bound(self) -> bool:
        return bool(
            self.receptor_system_sha256 != _ZERO_SHA256
            and self.ligand_system_sha256 != _ZERO_SHA256
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "receptor_system_sha256": self.receptor_system_sha256,
            "ligand_system_sha256": self.ligand_system_sha256,
            "pocket_definition_sha256": self.pocket_definition_sha256,
            "coordinate_frame_id": self.coordinate_frame_id,
            "metadata": _thaw_json(self.metadata),
            "bound": self.bound,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def search_space_fingerprint(
    *,
    local_offsets: torch.Tensor,
    parent: torch.Tensor,
    local_axes: torch.Tensor,
    rotatable_mask: torch.Tensor,
    root_positions: torch.Tensor | None,
) -> str:
    payload = {
        "schema_id": "betelgeuze.engine_v2_torsion_search_space/1.1.0",
        "local_offsets": _tensor_payload(local_offsets),
        "parent": {
            "shape": [int(size) for size in parent.shape],
            "values": [
                int(value) for value in parent.detach().cpu().reshape(-1).tolist()
            ],
        },
        "local_axes": _tensor_payload(local_axes),
        "rotatable_mask": {
            "shape": [int(size) for size in rotatable_mask.shape],
            "values": [
                bool(value)
                for value in rotatable_mask.detach().cpu().reshape(-1).tolist()
            ],
        },
        "root_positions": _tensor_payload(root_positions),
    }
    return _canonical_sha256(payload)


def coordinate_fingerprint(coordinates: torch.Tensor) -> str:
    return _canonical_sha256(
        {
            "schema_id": "betelgeuze.engine_v2_pose_coordinates/1.1.0",
            "coordinates": _tensor_payload(coordinates),
        }
    )


__all__ = [
    "DockingIdentityError",
    "DockingProblemIdentity",
    "coordinate_fingerprint",
    "search_space_fingerprint",
]
