from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

BLOCKED_HIGH_RISK_CLAIM_IDS = {
    "alphafold_parity",
    "broad_platform_claim",
    "calibrated_delta_g_or_fep",
    "wetlab_hit_claim",
}
BLOCKED_POLICY_FLAGS = {
    "alphafold_parity_claim_allowed": "alphafold_parity",
    "broad_platform_claim_allowed": "broad_platform_claim",
    "calibrated_delta_g_claim_allowed": "calibrated_delta_g_or_fep",
    "wetlab_hit_claim_allowed": "wetlab_hit_claim",
}

CLAIM_BOUNDARY = (
    "Product capability matrix validator only; it reads a local YAML claim matrix and verifies that accounting "
    "readiness is separated from scientific validity, broad/high-risk science claims remain blocked without row-level "
    "evidence, and execution/external mutation flags stay false. It does not run docking, train models, fetch external "
    "data, enable execution, submit predictions, deploy, upload, email, delete, commit, push, or mutate external state."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return bool(value is True)


def _row(check: str, passed: bool, observed: str, required: str) -> dict[str, Any]:
    return {
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "release_blocker": not passed,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def load_product_capability_matrix(path: str | Path) -> dict[str, Any]:
    matrix_path = Path(path)
    payload = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_product_capability_matrix_verification(matrix: dict[str, Any]) -> dict[str, Any]:
    claim_policy = matrix.get("claim_policy") if isinstance(matrix.get("claim_policy"), dict) else {}
    capabilities = [item for item in _as_list(matrix.get("capabilities")) if isinstance(item, dict)]
    by_id = {_text(item.get("id")): item for item in capabilities if _text(item.get("id"))}
    required_high_risk_ids = sorted(BLOCKED_HIGH_RISK_CLAIM_IDS)
    missing_high_risk_ids = [claim_id for claim_id in required_high_risk_ids if claim_id not in by_id]
    policy_overclaims = [
        claim_id
        for policy_key, claim_id in sorted(BLOCKED_POLICY_FLAGS.items())
        if _bool(claim_policy.get(policy_key))
    ]
    if _bool(claim_policy.get("external_state_mutated")):
        policy_overclaims.append("claim_policy_external_state_mutated")
    high_risk_overclaims: list[str] = []
    high_risk_without_row_evidence: list[str] = []

    for claim_id in required_high_risk_ids:
        capability = by_id.get(claim_id, {})
        claim_state = _text(capability.get("claim_state"))
        row_evidence_count = _int(capability.get("row_level_evidence_count"))
        scientific_green = _bool(capability.get("scientific_validity_green"))
        if claim_state not in {"blocked", "blocked_until_external_validation"}:
            high_risk_overclaims.append(claim_id)
        if scientific_green and row_evidence_count <= 0:
            high_risk_without_row_evidence.append(claim_id)

    missing_required_fields = [
        _text(capability.get("id")) or f"row_{index}"
        for index, capability in enumerate(capabilities)
        if not _text(capability.get("owner"))
        or not _text(capability.get("risk"))
        or not _as_list(capability.get("dependencies"))
        or not _as_list(capability.get("definition_of_done"))
    ]
    conflated_green = [
        _text(capability.get("id")) or f"row_{index}"
        for index, capability in enumerate(capabilities)
        if _bool(capability.get("accounting_green")) and _bool(capability.get("scientific_validity_green"))
        and _int(capability.get("row_level_evidence_count")) <= 0
    ]
    unsafe_mutation_flags = [
        _text(capability.get("id")) or f"row_{index}"
        for index, capability in enumerate(capabilities)
        if _bool(capability.get("execution_enabled")) or _bool(capability.get("external_state_mutated"))
    ]

    rows = [
        _row(
            "matrix_has_capabilities",
            len(capabilities) >= 10,
            f"capability_count={len(capabilities)}",
            "at least 10 capability rows covering science and operations",
        ),
        _row(
            "high_risk_claim_ids_present",
            not missing_high_risk_ids,
            f"missing={','.join(missing_high_risk_ids) or 'none'}",
            "explicit rows for AlphaFold parity, broad platform, calibrated Delta G/FEP, and wetlab hit claims",
        ),
        _row(
            "high_risk_claims_blocked",
            not high_risk_overclaims,
            f"overclaims={','.join(high_risk_overclaims) or 'none'}",
            "high-risk broad science claims must be blocked until independent validation",
        ),
        _row(
            "claim_policy_blocks_high_risk_claims",
            not policy_overclaims,
            f"policy_overclaims={','.join(policy_overclaims) or 'none'}",
            "claim_policy must keep broad platform, AlphaFold parity, calibrated Delta G/FEP, wetlab hit, and external mutation flags false",
        ),
        _row(
            "scientific_green_requires_row_evidence",
            not high_risk_without_row_evidence and not conflated_green,
            (
                f"high_risk_without_row_evidence={','.join(high_risk_without_row_evidence) or 'none'};"
                f"conflated_green={','.join(conflated_green) or 'none'}"
            ),
            "scientific_validity_green=true requires row_level_evidence_count > 0 and must not be inferred from accounting green",
        ),
        _row(
            "backlog_metadata_complete",
            not missing_required_fields,
            f"missing_metadata={','.join(missing_required_fields) or 'none'}",
            "every capability row has owner, risk, dependencies, and definition_of_done",
        ),
        _row(
            "local_only_fail_closed_flags",
            not unsafe_mutation_flags,
            f"unsafe_flags={','.join(unsafe_mutation_flags) or 'none'}",
            "execution_enabled and external_state_mutated remain false for every matrix row",
        ),
    ]
    blockers = [row["check"] for row in rows if row["status"] != "pass"]
    return {
        "summary": {
            "packet_type": "product_capability_matrix_verification",
            "status": "product_capability_matrix_verified" if not blockers else "blocked_product_capability_matrix",
            "capability_matrix_ready": not blockers,
            "capability_count": len(capabilities),
            "check_count": len(rows),
            "pass_count": sum(1 for row in rows if row["status"] == "pass"),
            "blocker_count": len(blockers),
            "blocked_checks": blockers,
            "high_risk_claim_ids": required_high_risk_ids,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
            "next_required_step": (
                "Keep the matrix in product verification; only flip blocked science claims after row-level independent evidence exists."
                if not blockers
                else "Repair capability matrix blockers before claiming product or science promotion readiness."
            ),
        },
        "rows": rows,
    }
