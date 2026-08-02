"""Legacy / V2 / oracle shadow execution on one prepared input (P1-9).

A legacy-vs-V2 claim is only meaningful when both engines ran on the *same*
prepared input with the same candidate budget, and when the offline baseline
(Vina/GNINA/Smina) is recorded as an oracle rather than as a competitor whose
result can be promoted.

This module enforces that shape:

- exactly one active surface (``legacy_product``);
- ``engine_v2`` runs shadow-only: its result is recorded, never promoted;
- ``external_oracle`` is offline-only and cannot become the active result;
- every surface must carry the same ``prepared_input_hash``, pocket, and
  candidate budget, otherwise the run is not comparable and no delta is claimed.

Shadow-only is a hard invariant here, not a convention: a V2 or oracle result
that tried to act as the active answer is reported as a violation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from betelgeuze_product.docking_result_bundle import DockingResultBundle, compare_bundles
from betelgeuze_product.preparation_packet import (
    ENGINE_SURFACE_ENGINE_V2,
    ENGINE_SURFACE_EXTERNAL_ORACLE,
    ENGINE_SURFACE_LEGACY_PRODUCT,
    PreparationPacket,
)

SHADOW_EXECUTION_SCHEMA_VERSION = "legacy_v2_shadow_execution_v1"

#: The only surface whose result may be served as the active answer.
ACTIVE_SURFACE = ENGINE_SURFACE_LEGACY_PRODUCT

#: Surfaces that are recorded for comparison but never promoted.
SHADOW_ONLY_SURFACES = (ENGINE_SURFACE_ENGINE_V2, ENGINE_SURFACE_EXTERNAL_ORACLE)

STATUS_READY = "shadow_execution_ready"
STATUS_BLOCKED = "blocked_shadow_execution"

CLAIM_BOUNDARY = (
    "Shadow execution record only. The legacy surface is active; engine_v2 and the external oracle are "
    "recorded shadow-only and can never be promoted to the served result. Pairwise deltas are diagnostic "
    "evidence on one prepared input, not a benchmark claim or a winner declaration."
)


@dataclass(frozen=True)
class ShadowExecutionRecord:
    """One case executed across the active and shadow surfaces."""

    prepared_input_hash: str
    bundles: tuple[DockingResultBundle, ...]
    violations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def by_surface(self) -> dict[str, DockingResultBundle]:
        return {bundle.engine_surface: bundle for bundle in self.bundles}

    @property
    def active_bundle(self) -> DockingResultBundle | None:
        return self.by_surface.get(ACTIVE_SURFACE)

    @property
    def shadow_bundles(self) -> tuple[DockingResultBundle, ...]:
        return tuple(
            bundle for bundle in self.bundles if bundle.engine_surface in SHADOW_ONLY_SURFACES
        )

    @property
    def status(self) -> str:
        return STATUS_BLOCKED if self.violations else STATUS_READY

    @property
    def ready(self) -> bool:
        return self.status == STATUS_READY

    def to_dict(self) -> dict[str, Any]:
        comparison = compare_bundles(self.bundles) if len(self.bundles) >= 2 else {
            "comparable": False,
            "invalid_reasons": ["need_at_least_two_engine_surfaces"],
            "pairwise_deltas": [],
        }
        active = self.active_bundle
        return {
            "schema_version": SHADOW_EXECUTION_SCHEMA_VERSION,
            "status": self.status,
            "ready": self.ready,
            "prepared_input_hash": str(self.prepared_input_hash),
            "active_engine_surface": ACTIVE_SURFACE,
            "active_result_present": active is not None,
            "shadow_only_surfaces": list(SHADOW_ONLY_SURFACES),
            "shadow_result_surfaces": [bundle.engine_surface for bundle in self.shadow_bundles],
            "shadow_only_locked": True,
            "claim_promotion_allowed": False,
            "executed_surface_count": len(self.bundles),
            "results": {
                bundle.engine_surface: bundle.to_dict() for bundle in self.bundles
            },
            "comparison": comparison,
            "pairwise_deltas": comparison.get("pairwise_deltas", []),
            "violations": list(self.violations),
            "claim_boundary": CLAIM_BOUNDARY,
        }


def build_shadow_execution_record(
    *,
    packet: PreparationPacket,
    bundles: Sequence[DockingResultBundle],
    served_engine_surface: str = ACTIVE_SURFACE,
) -> ShadowExecutionRecord:
    """Record a shadow run and enforce the shadow-only invariants."""

    rows = list(bundles)
    violations: list[str] = []

    if not packet.ready:
        violations.append("prepared_input_not_ready")

    expected_hash = packet.prepared_input_hash
    for bundle in rows:
        if bundle.prepared_input_hash != expected_hash:
            violations.append(
                f"prepared_input_hash_mismatch:{bundle.engine_surface}"
            )

    surfaces = [bundle.engine_surface for bundle in rows]
    if len(set(surfaces)) != len(surfaces):
        violations.append("duplicate_engine_surface")
    if ACTIVE_SURFACE not in surfaces:
        violations.append("active_legacy_surface_missing")
    if ENGINE_SURFACE_ENGINE_V2 not in surfaces:
        violations.append("v2_shadow_surface_missing")

    # Shadow-only is the invariant: a shadow surface must never be the served
    # result, no matter how much better it scored.
    if str(served_engine_surface) != ACTIVE_SURFACE:
        violations.append(f"shadow_surface_cannot_be_served:{served_engine_surface}")

    budgets = {int(bundle.candidate_budget) for bundle in rows}
    if len(budgets) > 1:
        violations.append("mismatched_candidate_budget")

    return ShadowExecutionRecord(
        prepared_input_hash=expected_hash,
        bundles=tuple(rows),
        violations=tuple(dict.fromkeys(violations)),
    )


__all__ = [
    "ACTIVE_SURFACE",
    "CLAIM_BOUNDARY",
    "SHADOW_EXECUTION_SCHEMA_VERSION",
    "SHADOW_ONLY_SURFACES",
    "STATUS_BLOCKED",
    "STATUS_READY",
    "ShadowExecutionRecord",
    "build_shadow_execution_record",
]
