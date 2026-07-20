"""Fail-closed capability truthfulness projection for Independent Engine v2.

The existing capability snapshot records whether a source surface exists and
whether selected internal reference paths may execute.  This module adds a
separate, exact projection for questions that must not be conflated:
component implementation, focused testing, process-entrypoint wiring,
production authorization, observed result evidence, independent review,
scientific validation, benchmark validation, product qualification, customer
enablement, and claim safety.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any

from .capabilities import (
    CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID,
    CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID,
    DOCKING_CAPABILITY_ID,
    PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID,
    capability_snapshot,
)


CAPABILITY_TRUTHFULNESS_SCHEMA_ID = (
    "betelgeuze.engine_v2_capability_truthfulness/1.0.0"
)
CAPABILITY_TRUTHFULNESS_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_capability_truthfulness_policy/1.0.0"
)
CAPABILITY_TRUTHFULNESS_SCHEMA_VERSION = 1

REQUIRED_CAPABILITY_STATUS_FIELDS = (
    "implemented",
    "component_tested",
    "canonical_entrypoint_wired",
    "internal_reference_execution_enabled",
    "production_execution_authorized",
    "observed_result_receipt_present",
    "independent_result_reviewed",
    "calibrated",
    "scientifically_validated",
    "public_evidence_ready",
    "benchmark_validated",
    "product_qualified",
    "customer_execution_enabled",
    "claim_safe",
)

FORBIDDEN_STALE_BLOCKERS_BY_CAPABILITY = {
    CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID: (
        "validation_runner_not_implemented",
        "result_receipt_writer_not_implemented",
    ),
    PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID: (
        "symmetry_mapping_materializer_not_implemented",
        "reference_ligand_match_materializer_not_implemented",
    ),
}

CAPABILITY_FACT_OVERRIDES: dict[str, dict[str, bool]] = {
    CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID: {
        "canonical_entrypoint_wired": True,
        "failure_inclusive_result_writer_implemented": True,
        "bounded_validation_runner_implemented": True,
    },
    CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID: {
        "canonical_entrypoint_wired": True,
        "failure_inclusive_result_writer_implemented": True,
        "bounded_validation_runner_implemented": True,
    },
    DOCKING_CAPABILITY_ID: {
        "bound_problem_identity_required": True,
        "bound_problem_validity_context_required": True,
        "invalid_or_incomplete_pose_top_k_selection_blocked": True,
        "scorer_and_refiner_problem_binding_required": True,
    },
    PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID: {
        "result_free_input_materializer_implemented": True,
        "reference_ligand_match_materializer_implemented": True,
        "symmetry_mapping_materializer_implemented": True,
        "benchmark_execution_implemented": False,
    },
}


class CapabilityTruthfulnessError(ValueError):
    """Capability state is incomplete, contradictory, or stale."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise CapabilityTruthfulnessError(
            "capability truthfulness artifact is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def truthfulness_policy_document() -> dict[str, Any]:
    """Return the immutable policy that the focused CI check enforces."""

    return {
        "schema_id": CAPABILITY_TRUTHFULNESS_POLICY_SCHEMA_ID,
        "schema_version": CAPABILITY_TRUTHFULNESS_SCHEMA_VERSION,
        "required_capability_status_fields": list(
            REQUIRED_CAPABILITY_STATUS_FIELDS
        ),
        "forbidden_stale_blockers_by_capability": {
            capability_id: list(blockers)
            for capability_id, blockers in sorted(
                FORBIDDEN_STALE_BLOCKERS_BY_CAPABILITY.items()
            )
        },
        "status_implications": {
            "production_execution_authorized_requires_canonical_entrypoint": True,
            "observed_result_receipt_requires_production_execution_authorized": True,
            "independent_result_review_requires_observed_result_receipt": True,
            "scientific_validation_requires_independent_result_review": True,
            "benchmark_validation_requires_public_evidence": True,
            "product_qualification_requires_scientific_validation": True,
            "customer_execution_requires_product_qualification": True,
            "claim_safe_requires_customer_execution": True,
        },
        "repository_bundles_production_authorization": False,
        "repository_bundles_production_result_receipt": False,
        "repository_bundles_independent_result_review": False,
        "external_state_mutated": False,
    }


def _require_boolean_fields(row: Mapping[str, Any]) -> None:
    for field_name in REQUIRED_CAPABILITY_STATUS_FIELDS:
        if type(row.get(field_name)) is not bool:
            raise CapabilityTruthfulnessError(
                f"capability field {field_name} must be boolean"
            )


def _require_status_implications(row: Mapping[str, Any]) -> None:
    implications = (
        (
            "production_execution_authorized",
            "canonical_entrypoint_wired",
        ),
        (
            "observed_result_receipt_present",
            "production_execution_authorized",
        ),
        (
            "independent_result_reviewed",
            "observed_result_receipt_present",
        ),
        (
            "scientifically_validated",
            "independent_result_reviewed",
        ),
        ("benchmark_validated", "public_evidence_ready"),
        ("product_qualified", "scientifically_validated"),
        ("customer_execution_enabled", "product_qualified"),
        ("claim_safe", "customer_execution_enabled"),
    )
    for consequence, prerequisite in implications:
        if row[consequence] and not row[prerequisite]:
            raise CapabilityTruthfulnessError(
                f"{consequence} requires {prerequisite}"
            )


def _truthful_capability_row(
    capability_id: str,
    source_row: Mapping[str, Any],
) -> dict[str, Any]:
    blockers = tuple(str(value) for value in source_row.get("blockers", ()))
    stale = set(blockers).intersection(
        FORBIDDEN_STALE_BLOCKERS_BY_CAPABILITY.get(capability_id, ())
    )
    if stale:
        raise CapabilityTruthfulnessError(
            f"{capability_id} retains stale blockers: {sorted(stale)}"
        )

    facts = dict(CAPABILITY_FACT_OVERRIDES.get(capability_id, {}))
    row = {
        "capability_id": capability_id,
        "current_state": str(source_row.get("current_state", "")),
        "implemented": source_row.get("implemented") is True,
        "component_tested": source_row.get("reference_contract_ready") is True,
        "canonical_entrypoint_wired": facts.pop(
            "canonical_entrypoint_wired",
            False,
        ),
        "internal_reference_execution_enabled": (
            source_row.get("internal_reference_execution_enabled") is True
        ),
        "production_execution_authorized": False,
        "observed_result_receipt_present": False,
        "independent_result_reviewed": False,
        "calibrated": source_row.get("calibrated") is True,
        "scientifically_validated": (
            source_row.get("scientifically_validated") is True
        ),
        "public_evidence_ready": (
            source_row.get("public_evidence_ready") is True
        ),
        "benchmark_validated": source_row.get("benchmark_validated") is True,
        "product_qualified": source_row.get("product_qualified") is True,
        "customer_execution_enabled": (
            source_row.get("customer_execution_enabled") is True
        ),
        "claim_safe": source_row.get("claim_safe") is True,
        "implementation_facts": facts,
        "blocker_source": str(source_row.get("blocker_source", "")),
        "blockers": list(blockers),
    }
    _require_boolean_fields(row)
    _require_status_implications(row)
    return row


def capability_truthfulness_snapshot() -> dict[str, Any]:
    """Project current capabilities onto a non-conflating status vocabulary."""

    source = capability_snapshot()
    source_capabilities = source.get("capabilities")
    if not isinstance(source_capabilities, Mapping) or not source_capabilities:
        raise CapabilityTruthfulnessError(
            "source capability snapshot has no capability rows"
        )
    rows = {
        capability_id: _truthful_capability_row(capability_id, source_row)
        for capability_id, source_row in sorted(source_capabilities.items())
        if isinstance(capability_id, str) and isinstance(source_row, Mapping)
    }
    if len(rows) != len(source_capabilities):
        raise CapabilityTruthfulnessError(
            "source capability rows contain invalid keys or values"
        )
    payload: dict[str, Any] = {
        "schema_id": CAPABILITY_TRUTHFULNESS_SCHEMA_ID,
        "schema_version": CAPABILITY_TRUTHFULNESS_SCHEMA_VERSION,
        "engine_id": source.get("engine_id"),
        "implementation_stage": source.get("implementation_stage"),
        "source_capability_schema_version": source.get("schema_version"),
        "source_snapshot_sha256": _sha256(source),
        "policy": truthfulness_policy_document(),
        "capabilities": rows,
        "repository_evidence_state": {
            "production_execution_authorized": False,
            "production_result_receipt_present": False,
            "independent_result_review_present": False,
            "scientific_validity_green": False,
            "benchmark_validity_green": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
            "external_state_mutated": False,
        },
    }
    payload["snapshot_sha256"] = _sha256(payload)
    return payload


def require_capability_truthfulness_snapshot(
    payload: object,
) -> Mapping[str, Any]:
    """Require exact agreement with the current executable projection."""

    if not isinstance(payload, Mapping):
        raise CapabilityTruthfulnessError(
            "capability truthfulness snapshot must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    expected = capability_truthfulness_snapshot()
    if observed != expected:
        raise CapabilityTruthfulnessError(
            "capability truthfulness snapshot drifted from executable policy"
        )
    return deepcopy(observed)


__all__ = [
    "CAPABILITY_FACT_OVERRIDES",
    "CAPABILITY_TRUTHFULNESS_POLICY_SCHEMA_ID",
    "CAPABILITY_TRUTHFULNESS_SCHEMA_ID",
    "CAPABILITY_TRUTHFULNESS_SCHEMA_VERSION",
    "FORBIDDEN_STALE_BLOCKERS_BY_CAPABILITY",
    "REQUIRED_CAPABILITY_STATUS_FIELDS",
    "CapabilityTruthfulnessError",
    "capability_truthfulness_snapshot",
    "require_capability_truthfulness_snapshot",
    "truthfulness_policy_document",
]
