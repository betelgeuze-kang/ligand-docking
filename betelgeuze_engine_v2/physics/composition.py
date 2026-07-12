"""Explicit composition contracts for independent physics and AI residual terms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import torch

from betelgeuze_engine_v2.contracts import QuantityDescriptor
from betelgeuze_engine_v2.geometry import CompactNeighborList
from betelgeuze_engine_v2.molecular import AllAtomSystem


@dataclass(frozen=True)
class EnergyTermResult:
    """One energy/force contribution with machine-readable scientific semantics."""

    name: str
    energy: torch.Tensor
    forces: torch.Tensor
    energy_descriptor: QuantityDescriptor
    force_descriptor: QuantityDescriptor
    validated_for_composition: bool
    provenance_sha256: str = ""

    def __post_init__(self) -> None:
        if self.energy.ndim != 1:
            raise ValueError("energy terms must have shape [B]")
        if self.forces.ndim != 3 or self.forces.shape[-1] != 3:
            raise ValueError("force terms must have shape [B,N,3]")
        if self.energy.shape[0] != self.forces.shape[0]:
            raise ValueError("energy and force batch dimensions must match")
        if self.energy.device != self.forces.device:
            raise ValueError("energy and force terms must share a device")
        if self.energy.dtype != self.forces.dtype:
            raise ValueError("energy and force terms must share a dtype")
        if not bool(torch.isfinite(self.energy).all().item()):
            raise ValueError("energy term must be finite")
        if not bool(torch.isfinite(self.forces).all().item()):
            raise ValueError("force term must be finite")
        if self.validated_for_composition:
            if not self.energy_descriptor.physical_quantity:
                raise ValueError("composable energy terms must be physical quantities")
            if not self.force_descriptor.physical_quantity:
                raise ValueError("composable force terms must be physical quantities")
            if not self.energy_descriptor.calibrated or not self.force_descriptor.calibrated:
                raise ValueError("composable terms must be calibrated")


@runtime_checkable
class IndependentPhysicsProvider(Protocol):
    """Independent, non-AI physics term provider."""

    provider_id: str

    def evaluate(
        self,
        system: AllAtomSystem,
        neighbors: CompactNeighborList,
    ) -> EnergyTermResult:
        ...


@dataclass(frozen=True)
class EnergyCompositionResult:
    physics: EnergyTermResult | None
    residual: EnergyTermResult | None
    total_energy: torch.Tensor | None
    total_forces: torch.Tensor | None
    total_energy_descriptor: QuantityDescriptor | None
    total_force_descriptor: QuantityDescriptor | None
    blockers: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return bool(not self.blockers and self.total_energy is not None and self.total_forces is not None)

    def to_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "physics_present": self.physics is not None,
            "residual_present": self.residual is not None,
            "total_energy_present": self.total_energy is not None,
            "total_forces_present": self.total_forces is not None,
            "total_energy_descriptor": None
            if self.total_energy_descriptor is None
            else self.total_energy_descriptor.to_dict(),
            "total_force_descriptor": None
            if self.total_force_descriptor is None
            else self.total_force_descriptor.to_dict(),
            "blockers": list(self.blockers),
        }


def _compatible_descriptors(
    first: QuantityDescriptor,
    second: QuantityDescriptor,
) -> bool:
    return bool(
        first.unit == second.unit
        and first.physical_quantity
        and second.physical_quantity
        and first.calibrated
        and second.calibrated
    )


def compose_energy_terms(
    physics: EnergyTermResult | None,
    residual: EnergyTermResult | None,
) -> EnergyCompositionResult:
    """Compose only calibrated physical terms with compatible units.

    Missing physics or an uncalibrated residual does not silently become total
    physical energy. Raw terms remain available for internal diagnostics.
    """

    blockers: list[str] = []
    if physics is None:
        blockers.append("independent_physics_energy_missing")
    elif not physics.validated_for_composition:
        blockers.append("independent_physics_energy_unvalidated")

    if residual is not None and not residual.validated_for_composition:
        blockers.append("residual_energy_uncalibrated")

    if blockers:
        return EnergyCompositionResult(
            physics=physics,
            residual=residual,
            total_energy=None,
            total_forces=None,
            total_energy_descriptor=None,
            total_force_descriptor=None,
            blockers=tuple(blockers),
        )

    assert physics is not None
    total_energy = physics.energy
    total_forces = physics.forces
    energy_descriptor = physics.energy_descriptor
    force_descriptor = physics.force_descriptor
    if residual is not None:
        if not _compatible_descriptors(physics.energy_descriptor, residual.energy_descriptor):
            blockers.append("energy_unit_or_calibration_mismatch")
        if not _compatible_descriptors(physics.force_descriptor, residual.force_descriptor):
            blockers.append("force_unit_or_calibration_mismatch")
        if blockers:
            return EnergyCompositionResult(
                physics=physics,
                residual=residual,
                total_energy=None,
                total_forces=None,
                total_energy_descriptor=None,
                total_force_descriptor=None,
                blockers=tuple(blockers),
            )
        total_energy = total_energy + residual.energy
        total_forces = total_forces + residual.forces

    return EnergyCompositionResult(
        physics=physics,
        residual=residual,
        total_energy=total_energy,
        total_forces=total_forces,
        total_energy_descriptor=energy_descriptor,
        total_force_descriptor=force_descriptor,
        blockers=(),
    )
