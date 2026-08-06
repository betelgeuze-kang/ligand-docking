#!/usr/bin/env python3
"""Verify the product capability, identity, workflow, and claim registry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping


SCHEMA_ID = "betelgeuze.product_capability_registry/1.0.0"
EXPECTED_PRODUCT_IDENTITY = {
    "brand": "Betelgeuze",
    "customer_product": "Betelgeuze Docking",
    "evidence_review_ui": "Evidence Desk",
    "research_lane": "Research Validation Lanes",
    "scientific_engine": "Engine V2",
    "supported_positioning": (
        "Local-first restricted docking validation and audit-ready evidence delivery"
    ),
    "unsupported_positioning": (
        "Blanket docking, MD, FEP, or commercial-suite replacement"
    ),
}
EXPECTED_WORKFLOW_STEPS = (
    "prepare",
    "validate",
    "propose",
    "score",
    "select",
    "review",
    "export",
)
REQUIRED_CAPABILITY_KEYS = {
    "allowed_wording",
    "benchmark_status",
    "blocked_by",
    "capability_id",
    "claim_safe",
    "claim_scope",
    "customer_execution",
    "default_enabled",
    "display_name",
    "evidence_source_paths",
    "forbidden_wording",
    "implementation_lane",
    "implementation_status",
    "product_status",
    "scientific_status",
}
CLAIM_SCOPES = {
    "none",
    "per_result_gate",
    "restricted_target_specific",
}
CUSTOMER_EXECUTION_VALUES = {
    "disabled",
    "guarded_operator_only",
    "qualified_self_service",
}
PRODUCT_STATUSES = {
    "disabled",
    "research_only",
    "restricted_delivery",
    "product_qualified",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CAPABILITY_ID_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


class ProductCapabilityRegistryError(ValueError):
    """Raised when the registry fails closed."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ProductCapabilityRegistryError(f"{name} must be an object")
    return value


def _string_list(value: object, *, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ProductCapabilityRegistryError(
            f"{name} must be an array of non-empty strings"
        )
    return tuple(value)


def _relative_source_path(value: str, *, name: str) -> None:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ProductCapabilityRegistryError(f"{name} is not a safe relative path")


def load_registry(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductCapabilityRegistryError(
            f"registry is not readable JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ProductCapabilityRegistryError("registry must be a JSON object")
    return payload


def verify_registry(registry: Mapping[str, Any]) -> str:
    required_top_keys = {
        "canonical_workflow",
        "capabilities",
        "governance",
        "product_identity",
        "registry_role",
        "registry_sha256",
        "schema_id",
    }
    if set(registry) != required_top_keys:
        raise ProductCapabilityRegistryError("registry key set is invalid")
    if registry.get("schema_id") != SCHEMA_ID:
        raise ProductCapabilityRegistryError("registry schema is invalid")
    if (
        registry.get("registry_role")
        != "product_capability_status_and_claim_source_of_truth"
    ):
        raise ProductCapabilityRegistryError("registry role is invalid")
    observed_hash = registry.get("registry_sha256")
    if (
        not isinstance(observed_hash, str)
        or _SHA256_RE.fullmatch(observed_hash) is None
    ):
        raise ProductCapabilityRegistryError("registry SHA-256 is invalid")
    projection = dict(registry)
    projection.pop("registry_sha256")
    expected_hash = _sha256(projection)
    if observed_hash != expected_hash:
        raise ProductCapabilityRegistryError("registry self-hash is invalid")

    identity = _mapping(registry.get("product_identity"), name="product_identity")
    if dict(identity) != EXPECTED_PRODUCT_IDENTITY:
        raise ProductCapabilityRegistryError("canonical product identity drifted")

    workflow = registry.get("canonical_workflow")
    if not isinstance(workflow, list) or not workflow:
        raise ProductCapabilityRegistryError("canonical_workflow must be non-empty")
    observed_steps: list[str] = []
    for index, raw_step in enumerate(workflow):
        step = _mapping(raw_step, name=f"canonical_workflow[{index}]")
        if set(step) != {"authority_boundary", "display_name", "step_id"}:
            raise ProductCapabilityRegistryError(
                "canonical workflow step keys drifted"
            )
        step_id = step.get("step_id")
        if not isinstance(step_id, str) or not step_id:
            raise ProductCapabilityRegistryError("workflow step_id is invalid")
        if (
            not isinstance(step.get("display_name"), str)
            or not step.get("display_name")
        ):
            raise ProductCapabilityRegistryError("workflow display_name is invalid")
        if (
            not isinstance(step.get("authority_boundary"), str)
            or not step.get("authority_boundary")
        ):
            raise ProductCapabilityRegistryError(
                "workflow authority_boundary is invalid"
            )
        observed_steps.append(step_id)
    if tuple(observed_steps) != EXPECTED_WORKFLOW_STEPS:
        raise ProductCapabilityRegistryError("canonical workflow order drifted")

    governance = _mapping(registry.get("governance"), name="governance")
    required_governance_keys = {
        "claim_safe_benchmark_statuses",
        "claim_safe_scientific_statuses",
        "default_enabled_requires_product_status",
        "disabled_customer_execution_values",
        "registry_is_product_routing_source",
        "registry_is_status_and_claim_source",
    }
    if set(governance) != required_governance_keys:
        raise ProductCapabilityRegistryError("governance key set is invalid")
    claim_benchmark_statuses = set(
        _string_list(
            governance.get("claim_safe_benchmark_statuses"),
            name="claim_safe_benchmark_statuses",
        )
    )
    claim_scientific_statuses = set(
        _string_list(
            governance.get("claim_safe_scientific_statuses"),
            name="claim_safe_scientific_statuses",
        )
    )
    default_product_statuses = set(
        _string_list(
            governance.get("default_enabled_requires_product_status"),
            name="default_enabled_requires_product_status",
        )
    )
    if governance.get("registry_is_status_and_claim_source") is not True:
        raise ProductCapabilityRegistryError(
            "registry must remain the status and claim source"
        )
    if governance.get("registry_is_product_routing_source") is not False:
        raise ProductCapabilityRegistryError(
            "registry must not silently become a product routing authority"
        )

    capabilities = registry.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        raise ProductCapabilityRegistryError("capabilities must be non-empty")
    capability_ids: list[str] = []
    for index, raw_capability in enumerate(capabilities):
        capability = _mapping(raw_capability, name=f"capabilities[{index}]")
        if set(capability) != REQUIRED_CAPABILITY_KEYS:
            raise ProductCapabilityRegistryError(
                f"capabilities[{index}] key set is invalid"
            )
        capability_id = capability.get("capability_id")
        if (
            not isinstance(capability_id, str)
            or _CAPABILITY_ID_RE.fullmatch(capability_id) is None
        ):
            raise ProductCapabilityRegistryError("capability_id is invalid")
        capability_ids.append(capability_id)
        if (
            not isinstance(capability.get("display_name"), str)
            or not capability.get("display_name")
        ):
            raise ProductCapabilityRegistryError(
                f"{capability_id} display_name is invalid"
            )
        for key in (
            "benchmark_status",
            "implementation_lane",
            "implementation_status",
            "scientific_status",
        ):
            if not isinstance(capability.get(key), str) or not capability.get(key):
                raise ProductCapabilityRegistryError(
                    f"{capability_id} {key} is invalid"
                )
        claim_scope = capability.get("claim_scope")
        if claim_scope not in CLAIM_SCOPES:
            raise ProductCapabilityRegistryError(
                f"{capability_id} claim_scope is invalid"
            )
        customer_execution = capability.get("customer_execution")
        if customer_execution not in CUSTOMER_EXECUTION_VALUES:
            raise ProductCapabilityRegistryError(
                f"{capability_id} customer_execution is invalid"
            )
        product_status = capability.get("product_status")
        if product_status not in PRODUCT_STATUSES:
            raise ProductCapabilityRegistryError(
                f"{capability_id} product_status is invalid"
            )
        if type(capability.get("claim_safe")) is not bool:
            raise ProductCapabilityRegistryError(
                f"{capability_id} claim_safe must be boolean"
            )
        if type(capability.get("default_enabled")) is not bool:
            raise ProductCapabilityRegistryError(
                f"{capability_id} default_enabled must be boolean"
            )
        allowed_wording = _string_list(
            capability.get("allowed_wording"),
            name=f"{capability_id}.allowed_wording",
        )
        forbidden_wording = _string_list(
            capability.get("forbidden_wording"),
            name=f"{capability_id}.forbidden_wording",
        )
        if not forbidden_wording:
            raise ProductCapabilityRegistryError(
                f"{capability_id} requires forbidden wording"
            )
        blocked_by = _string_list(
            capability.get("blocked_by"),
            name=f"{capability_id}.blocked_by",
        )
        if tuple(sorted(set(blocked_by))) != blocked_by:
            raise ProductCapabilityRegistryError(
                f"{capability_id} blocked_by must be sorted and unique"
            )
        source_paths = _string_list(
            capability.get("evidence_source_paths"),
            name=f"{capability_id}.evidence_source_paths",
        )
        if not source_paths:
            raise ProductCapabilityRegistryError(
                f"{capability_id} requires evidence source paths"
            )
        for source_path in source_paths:
            _relative_source_path(
                source_path,
                name=f"{capability_id}.evidence_source_paths",
            )

        claim_safe = capability["claim_safe"]
        if claim_safe:
            if claim_scope == "none" or not allowed_wording:
                raise ProductCapabilityRegistryError(
                    f"{capability_id} claim-safe wording is incomplete"
                )
            if capability["benchmark_status"] not in claim_benchmark_statuses:
                raise ProductCapabilityRegistryError(
                    f"{capability_id} benchmark status is not claim-safe"
                )
            if capability["scientific_status"] not in claim_scientific_statuses:
                raise ProductCapabilityRegistryError(
                    f"{capability_id} scientific status is not claim-safe"
                )
        if product_status in {"disabled", "research_only"}:
            if customer_execution != "disabled" or capability["default_enabled"]:
                raise ProductCapabilityRegistryError(
                    f"{capability_id} disabled/research status opened execution"
                )
        if capability["default_enabled"]:
            if product_status not in default_product_statuses:
                raise ProductCapabilityRegistryError(
                    f"{capability_id} default enablement is unauthorized"
                )
            if customer_execution != "qualified_self_service" or not claim_safe:
                raise ProductCapabilityRegistryError(
                    f"{capability_id} default enablement is not qualified"
                )

    if tuple(sorted(capability_ids)) != tuple(capability_ids):
        raise ProductCapabilityRegistryError(
            "capabilities must be sorted by capability_id"
        )
    if len(set(capability_ids)) != len(capability_ids):
        raise ProductCapabilityRegistryError("capability IDs must be unique")

    capability_map = {
        capability["capability_id"]: capability for capability in capabilities
    }
    for blocked_id in (
        "engine_v2_global_orientation",
        "engine_v2_redocking",
        "full_all_atom_md_fep",
        "gpcr_broad_router",
        "pocketmd_lite",
        "public_benchmark_harness",
    ):
        capability = capability_map.get(blocked_id)
        if capability is None:
            raise ProductCapabilityRegistryError(
                f"required blocked capability {blocked_id} is missing"
            )
        if (
            capability["claim_safe"]
            or capability["customer_execution"] != "disabled"
            or capability["default_enabled"]
        ):
            raise ProductCapabilityRegistryError(
                f"{blocked_id} must remain claim and execution blocked"
            )

    return expected_hash


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "config/product_capability_registry.json"
        ),
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    registry = load_registry(arguments.registry)
    print(verify_registry(registry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
