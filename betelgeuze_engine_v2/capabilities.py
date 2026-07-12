"""Machine-readable capability state derived from executable Engine v2 blockers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .engine import REFERENCE_CLAIM_BLOCKERS


CAPABILITY_SCHEMA_VERSION = 2
CAPABILITY_ID = "v2_cpu_reference_orchestrator"


def capability_snapshot() -> dict[str, Any]:
    return {
        "schema_version": CAPABILITY_SCHEMA_VERSION,
        "engine_id": "betelgeuze_independent_engine_v2",
        "implementation_stage": "v2_e_runtime_checkpoint_contracts",
        "claim_policy": {
            "customer_execution_enabled": False,
            "scientific_validity_green": False,
            "benchmark_validity_green": False,
            "gpu_acceleration_claim_allowed": False,
            "docking_accuracy_claim_allowed": False,
        },
        "capabilities": {
            CAPABILITY_ID: {
                "current_state": "fail_closed_internal_reference",
                "execution_enabled": False,
                "internal_reference_execution_enabled": True,
                "blocker_source": "betelgeuze_engine_v2.engine.REFERENCE_CLAIM_BLOCKERS",
                "blockers": list(REFERENCE_CLAIM_BLOCKERS),
            }
        },
    }


def require_capability_snapshot(payload: object) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("capability payload must be a mapping")
    expected = capability_snapshot()
    if payload.get("schema_version") != expected["schema_version"]:
        raise ValueError("capability schema version drift")
    if payload.get("engine_id") != expected["engine_id"]:
        raise ValueError("capability engine ID drift")
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, Mapping):
        raise ValueError("capability map is missing")
    actual = capabilities.get(CAPABILITY_ID)
    if not isinstance(actual, Mapping):
        raise ValueError(f"capability {CAPABILITY_ID!r} is missing")
    expected_capability = expected["capabilities"][CAPABILITY_ID]
    if actual.get("blocker_source") != expected_capability["blocker_source"]:
        raise ValueError("capability blocker source drift")
    if list(actual.get("blockers", ())) != list(expected_capability["blockers"]):
        raise ValueError("capability blocker codes drifted from executable code")
    if actual.get("execution_enabled") is not False:
        raise ValueError("customer execution must remain fail-closed")
    return payload


__all__ = [
    "CAPABILITY_ID",
    "CAPABILITY_SCHEMA_VERSION",
    "capability_snapshot",
    "require_capability_snapshot",
]
