"""Fail-closed status and physical-quantity contracts for Engine v2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class ClaimStage(IntEnum):
    """Monotonic evidence stages; higher stages require all lower stages."""

    INVALID = 0
    CONTRACT_VALID = 1
    PROVENANCE_VERIFIED = 2
    CHEMISTRY_VALIDATED = 3
    SCIENTIFICALLY_VALIDATED = 4
    PRODUCT_QUALIFIED = 5

    @property
    def claim_safe(self) -> bool:
        """Compatibility view: only scientific validation or above is claim-safe."""

        return self >= ClaimStage.SCIENTIFICALLY_VALIDATED


@dataclass(frozen=True)
class QuantityDescriptor:
    """Machine-readable semantics for a reported scalar or vector quantity."""

    name: str
    unit: str | None
    semantics: str
    physical_quantity: bool
    calibrated: bool
    reference_method: str | None = None

    def __post_init__(self) -> None:
        if not str(self.name or "").strip():
            raise ValueError("quantity name must be non-empty")
        if not str(self.semantics or "").strip():
            raise ValueError("quantity semantics must be non-empty")
        if self.physical_quantity and not self.unit:
            raise ValueError("physical quantities must declare a unit")
        if self.calibrated and not self.reference_method:
            raise ValueError("calibrated quantities must declare a reference method")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "unit": self.unit,
            "semantics": self.semantics,
            "physical_quantity": self.physical_quantity,
            "calibrated": self.calibrated,
            "reference_method": self.reference_method,
        }


UNCALIBRATED_ENERGY = QuantityDescriptor(
    name="energy",
    unit=None,
    semantics="uncalibrated_internal_scalar",
    physical_quantity=False,
    calibrated=False,
)

UNCALIBRATED_FORCE = QuantityDescriptor(
    name="force",
    unit=None,
    semantics="negative_gradient_of_uncalibrated_scalar_per_angstrom",
    physical_quantity=False,
    calibrated=False,
)
