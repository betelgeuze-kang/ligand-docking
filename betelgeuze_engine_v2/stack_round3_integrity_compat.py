"""Keep molecular object integrity separate from canonical validity.

Engine v2 intentionally permits construction of some contract-invalid systems
so that the validation layer can return structured diagnostics. The initial
round-3 integrity digest used canonical serialization during construction and
therefore rejected non-finite metadata too early. This installer replaces that
step with an exact structural mutation digest that can represent invalid values,
while public canonical SHA functions still enforce canonical validity.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
import hashlib
import json
import math
import sys
from typing import Any, Mapping

import torch

from betelgeuze_engine_v2.stack_round3_molecular import (
    MolecularIntegrityError,
    _deep_freeze,
)


STACK_ROUND3_INTEGRITY_COMPAT_SCHEMA_ID = (
    "betelgeuze.engine_v2_stack_round3_integrity_compat/1.0.0"
)


def _identity_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            token = "nan"
        elif math.isinf(value):
            token = "+inf" if value > 0 else "-inf"
        else:
            token = value.hex()
        return {"$float_identity": token}
    if isinstance(value, torch.Tensor):
        tensor = value.detach().to(device="cpu").contiguous()
        if tensor.is_floating_point():
            values = [
                _identity_value(float(item))
                for item in tensor.reshape(-1).tolist()
            ]
        else:
            values = tensor.reshape(-1).tolist()
        return {
            "$tensor_identity": {
                "dtype": str(tensor.dtype).removeprefix("torch."),
                "shape": [int(size) for size in tensor.shape],
                "values": values,
            }
        }
    if is_dataclass(value):
        return {
            field.name: _identity_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): _identity_value(item)
            for key, item in sorted(value.items(), key=lambda row: str(row[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_identity_value(item) for item in value]
    return {"$repr_identity": repr(value)}


def _raw_system_integrity_sha256(system: object) -> str:
    payload = {
        "schema_id": "betelgeuze.engine_v2_molecular_object_integrity/1.0.0",
        "system_id": system.system_id,
        "atoms": _identity_value(system.atoms),
        "bonds": _identity_value(system.bonds),
        "residues": _identity_value(system.residues),
        "chains": _identity_value(system.chains),
        "coordinates": _identity_value(system.coordinates),
        "provenance": _identity_value(system.provenance),
        "cell": _identity_value(system.cell),
        "coordinate_unit": system.coordinate_unit,
        "metadata": _identity_value(system.metadata),
        "system_schema_id": system.schema_id,
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()


def install_stack_round3_integrity_compat() -> str:
    marker = "_betelgeuze_stack_round3_integrity_compat_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing

    from betelgeuze_engine_v2 import molecular as molecular_package
    from betelgeuze_engine_v2.molecular import models, serialization

    def system_post_init(self) -> None:
        if not isinstance(self.coordinates, torch.Tensor):
            raise TypeError("coordinates must be a torch.Tensor")
        if self.coordinates.ndim != 3 or self.coordinates.shape[-1] != 3:
            raise ValueError("coordinates must have shape [M, N, 3]")
        if not self.coordinates.is_floating_point():
            raise TypeError("coordinates must use a floating dtype")
        object.__setattr__(self, "system_id", str(self.system_id))
        object.__setattr__(self, "atoms", tuple(self.atoms))
        object.__setattr__(self, "bonds", tuple(self.bonds))
        object.__setattr__(self, "residues", tuple(self.residues))
        object.__setattr__(self, "chains", tuple(self.chains))
        object.__setattr__(
            self,
            "coordinates",
            self.coordinates.detach().clone().contiguous(),
        )
        object.__setattr__(
            self,
            "coordinate_unit",
            str(self.coordinate_unit).lower(),
        )
        object.__setattr__(
            self,
            "metadata",
            _deep_freeze(dict(self.metadata)),
        )
        object.__setattr__(
            self,
            "_integrity_sha256",
            _raw_system_integrity_sha256(self),
        )

    def assert_integrity(self) -> None:
        expected = getattr(self, "_integrity_sha256", "")
        if not expected:
            raise MolecularIntegrityError(
                "molecular system predates the integrity contract"
            )
        observed = _raw_system_integrity_sha256(self)
        if observed != expected:
            raise MolecularIntegrityError(
                "molecular system changed after construction"
            )

    def integrity_sha256(self) -> str:
        assert_integrity(self)
        return str(self._integrity_sha256)

    current_system_sha256 = serialization.canonical_system_sha256

    def canonical_system_sha256(system) -> str:
        if hasattr(system, "assert_integrity"):
            system.assert_integrity()
        return serialization.sha256_canonical(
            serialization.canonical_system_payload(system)
        )

    models.AllAtomSystem.__post_init__ = system_post_init
    models.AllAtomSystem.assert_integrity = assert_integrity
    models.AllAtomSystem.integrity_sha256 = property(integrity_sha256)
    serialization.canonical_system_sha256 = canonical_system_sha256
    molecular_package.canonical_system_sha256 = canonical_system_sha256
    for loaded in tuple(sys.modules.values()):
        if loaded is not None and getattr(
            loaded, "canonical_system_sha256", None
        ) is current_system_sha256:
            setattr(loaded, "canonical_system_sha256", canonical_system_sha256)

    receipt = hashlib.sha256(
        json.dumps(
            {
                "schema_id": STACK_ROUND3_INTEGRITY_COMPAT_SCHEMA_ID,
                "object_integrity_separate_from_canonical_validity": True,
                "invalid_systems_reach_structured_validation": True,
                "post_construction_mutation_rejected": True,
                "recursive_metadata_immutability_preserved": True,
                "chemistry_validated": False,
                "scientifically_validated": False,
                "claim_safe": False,
            },
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "STACK_ROUND3_INTEGRITY_COMPAT_SCHEMA_ID",
    "install_stack_round3_integrity_compat",
]
