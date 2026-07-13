"""Bounded registry for independently owned physical energy terms."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Protocol, runtime_checkable

import torch

from betelgeuze_engine_v2.contracts import failure_receipt
from betelgeuze_engine_v2.geometry import CompactNeighborList
from betelgeuze_engine_v2.molecular import AllAtomSystem
from betelgeuze_engine_v2.physics.composition import EnergyTermResult

MAX_REGISTERED_PHYSICS_TERMS = 64


class PhysicsTermRegistryError(RuntimeError):
    """Term registration or validated composition failed closed."""


@runtime_checkable
class IndependentPhysicsTerm(Protocol):
    provider_id: str
    provider_version: str

    def evaluate(
        self,
        system: AllAtomSystem,
        neighbors: CompactNeighborList,
    ) -> EnergyTermResult:
        ...


@dataclass(frozen=True)
class PhysicsTermRow:
    provider_id: str
    provider_version: str
    status: str
    result: EnergyTermResult | None = None
    error_code: str = ""
    error_message: str = ""
    private_error_sha256: str = ""
    private_error_byte_length: int = 0

    @property
    def succeeded(self) -> bool:
        return self.status == "success" and self.result is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "status": self.status,
            "succeeded": self.succeeded,
            "validated_for_composition": bool(
                self.result is not None and self.result.validated_for_composition
            ),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "private_error_sha256": self.private_error_sha256,
            "private_error_byte_length": int(self.private_error_byte_length),
        }


@dataclass(frozen=True)
class PhysicsRegistryEvaluation:
    rows: tuple[PhysicsTermRow, ...]
    registry_fingerprint_sha256: str

    @property
    def failed_rows(self) -> tuple[PhysicsTermRow, ...]:
        return tuple(row for row in self.rows if not row.succeeded)

    @property
    def successful_terms(self) -> tuple[EnergyTermResult, ...]:
        return tuple(row.result for row in self.rows if row.result is not None and row.succeeded)

    @property
    def complete(self) -> bool:
        return bool(self.rows and not self.failed_rows)

    def to_dict(self) -> dict[str, object]:
        return {
            "row_count": len(self.rows),
            "success_count": len(self.successful_terms),
            "failure_count": len(self.failed_rows),
            "complete": self.complete,
            "registry_fingerprint_sha256": self.registry_fingerprint_sha256,
            "rows": [row.to_dict() for row in self.rows],
        }


class PhysicsTermRegistry:
    """Register a fixed number of explicit independent physics providers."""

    def __init__(self, *, max_terms: int = MAX_REGISTERED_PHYSICS_TERMS):
        if int(max_terms) < 1 or int(max_terms) > MAX_REGISTERED_PHYSICS_TERMS:
            raise ValueError(
                f"max_terms must be in [1, {MAX_REGISTERED_PHYSICS_TERMS}]"
            )
        self.max_terms = int(max_terms)
        self._providers: dict[str, IndependentPhysicsTerm] = {}

    def register(self, provider: IndependentPhysicsTerm) -> None:
        if not isinstance(provider, IndependentPhysicsTerm):
            raise TypeError("provider must satisfy IndependentPhysicsTerm")
        provider_id = str(provider.provider_id or "").strip()
        provider_version = str(provider.provider_version or "").strip()
        if not provider_id or not provider_version:
            raise PhysicsTermRegistryError("provider ID and version must be non-empty")
        if provider_id in self._providers:
            raise PhysicsTermRegistryError(f"duplicate physics provider {provider_id!r}")
        if len(self._providers) >= self.max_terms:
            raise PhysicsTermRegistryError("physics provider registry capacity exceeded")
        self._providers[provider_id] = provider

    @property
    def provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    @property
    def fingerprint_sha256(self) -> str:
        payload = [
            {
                "provider_id": provider_id,
                "provider_version": str(self._providers[provider_id].provider_version),
                "provider_class": (
                    f"{self._providers[provider_id].__class__.__module__}."
                    f"{self._providers[provider_id].__class__.__qualname__}"
                ),
                "parameter_fingerprint_sha256": str(
                    getattr(self._providers[provider_id], "parameter_fingerprint_sha256", "") or ""
                ),
                "config_fingerprint_sha256": str(
                    getattr(self._providers[provider_id], "config_fingerprint_sha256", "") or ""
                ),
            }
            for provider_id in self.provider_ids
        ]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def evaluate(
        self,
        system: AllAtomSystem,
        neighbors: CompactNeighborList,
        *,
        provider_ids: tuple[str, ...] | None = None,
    ) -> PhysicsRegistryEvaluation:
        selected = self.provider_ids if provider_ids is None else tuple(provider_ids)
        if not selected:
            raise PhysicsTermRegistryError("at least one physics provider must be selected")
        if len(set(selected)) != len(selected):
            raise PhysicsTermRegistryError("duplicate provider IDs in evaluation request")
        rows: list[PhysicsTermRow] = []
        for provider_id in selected:
            provider = self._providers.get(provider_id)
            if provider is None:
                rows.append(
                    PhysicsTermRow(
                        provider_id=str(provider_id),
                        provider_version="",
                        status="failure",
                        error_code="provider_not_registered",
                        error_message="requested physics provider is not registered",
                    )
                )
                continue
            try:
                result = provider.evaluate(system, neighbors)
                if not isinstance(result, EnergyTermResult):
                    raise TypeError("provider did not return EnergyTermResult")
                if result.forces.shape[:2] != system.coordinates.shape[:2]:
                    raise ValueError("provider force shape does not match system coordinates")
                rows.append(
                    PhysicsTermRow(
                        provider_id=provider_id,
                        provider_version=str(provider.provider_version),
                        status="success",
                        result=result,
                    )
                )
            except Exception as exc:
                receipt = failure_receipt(exc, public_message="physics provider execution failed")
                rows.append(
                    PhysicsTermRow(
                        provider_id=provider_id,
                        provider_version=str(provider.provider_version),
                        status="failure",
                        error_code=receipt.public_error_code,
                        error_message=receipt.public_message,
                        private_error_sha256=receipt.private_error_sha256,
                        private_error_byte_length=receipt.private_error_byte_length,
                    )
                )
        return PhysicsRegistryEvaluation(
            rows=tuple(rows),
            registry_fingerprint_sha256=self.fingerprint_sha256,
        )


def sum_validated_physics_terms(
    evaluation: PhysicsRegistryEvaluation,
    *,
    name: str = "independent_physics_total",
) -> EnergyTermResult:
    """Sum only a complete set of calibrated physical terms with matching units."""

    if not evaluation.complete:
        raise PhysicsTermRegistryError("cannot compose physics terms while failure rows exist")
    terms = evaluation.successful_terms
    if not terms:
        raise PhysicsTermRegistryError("no successful physics terms to compose")
    first = terms[0]
    if not first.validated_for_composition:
        raise PhysicsTermRegistryError("physics term is not validated for composition")
    for term in terms[1:]:
        if not term.validated_for_composition:
            raise PhysicsTermRegistryError("physics term is not validated for composition")
        if term.energy_descriptor != first.energy_descriptor:
            raise PhysicsTermRegistryError("physics energy descriptors are incompatible")
        if term.force_descriptor != first.force_descriptor:
            raise PhysicsTermRegistryError("physics force descriptors are incompatible")
        if term.energy.shape != first.energy.shape or term.forces.shape != first.forces.shape:
            raise PhysicsTermRegistryError("physics term tensor shapes are incompatible")

    total_energy = torch.stack([term.energy for term in terms], dim=0).sum(dim=0)
    total_forces = torch.stack([term.forces for term in terms], dim=0).sum(dim=0)
    provenance_payload = [term.provenance_sha256 for term in terms]
    provenance_sha256 = hashlib.sha256(
        json.dumps(provenance_payload, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return EnergyTermResult(
        name=str(name),
        energy=total_energy,
        forces=total_forces,
        energy_descriptor=first.energy_descriptor,
        force_descriptor=first.force_descriptor,
        validated_for_composition=True,
        provenance_sha256=provenance_sha256,
    )


__all__ = [
    "MAX_REGISTERED_PHYSICS_TERMS",
    "IndependentPhysicsTerm",
    "PhysicsRegistryEvaluation",
    "PhysicsTermRegistry",
    "PhysicsTermRegistryError",
    "PhysicsTermRow",
    "sum_validated_physics_terms",
]
