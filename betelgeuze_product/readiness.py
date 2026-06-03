from __future__ import annotations

from typing import Any

from betelgeuze_product.docking_request import ALLOWED_SCOPE_FAMILIES, validate_docking_request

CLAIM_BOUNDARY = (
    "Product readiness gate only; combines a commercial docking request contract with local-delivery verdict evidence. "
    "It does not run docking, emit scientific results, widen scope, or mutate external state."
)
EXECUTION_APPROVAL_TOKEN = "APPROVE_PRODUCT_DOCKING_EXECUTION"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return bool(value is True)


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        merged = dict(payload)
        merged.update(summary)
        return merged
    return dict(payload)


def _request_contract(request_payload: dict[str, Any]) -> dict[str, Any]:
    if "validation_status" in request_payload and "family" in request_payload:
        blockers = request_payload.get("blockers") if isinstance(request_payload.get("blockers"), list) else []
        warnings = request_payload.get("warnings") if isinstance(request_payload.get("warnings"), list) else []
        return {
            "status": "pass" if request_payload.get("validation_status") == "pass" and not blockers else "fail",
            "blockers": blockers,
            "warnings": warnings,
            "normalized": {
                "request_type": _text(request_payload.get("request_type")),
                "family": _text(request_payload.get("family")),
                "target_id": _text(request_payload.get("target_id")),
                "structure_source_kind": _text(request_payload.get("structure_source_kind")),
                "ligand_count": _int(request_payload.get("ligand_count")),
                "ligand_ids": [],
            },
        }
    return validate_docking_request(request_payload)


def build_product_readiness_gate(
    request_payload: dict[str, Any],
    local_delivery_verdict_payload: dict[str, Any],
    *,
    local_delivery_verdict_path: str = "runs/local_delivery_verdict_gate_current.json",
) -> dict[str, Any]:
    contract = _request_contract(request_payload)
    normalized = contract["normalized"]
    verdict = _summary(local_delivery_verdict_payload)
    blockers: list[dict[str, str]] = []
    for blocker in contract.get("blockers", []) or []:
        if isinstance(blocker, dict):
            blockers.append(dict(blocker))
    if contract["status"] != "pass":
        blockers.append(_blocker("request_contract_not_pass", "Commercial docking request contract must pass before product handoff."))

    family = _text(normalized.get("family"))
    if family not in ALLOWED_SCOPE_FAMILIES:
        blockers.append(_blocker("family_outside_product_scope", "Product readiness is restricted to kinase, gpcr, and ion_channel."))
    if not _bool(verdict.get("delivery_ready")):
        blockers.append(_blocker("local_delivery_verdict_not_ready", "Local delivery verdict gate must report delivery_ready=true."))
    if _text(verdict.get("verdict")) != "delivery_ready":
        blockers.append(_blocker("local_delivery_verdict_label_not_ready", "Local delivery verdict must be delivery_ready."))
    if _int(verdict.get("p0_blocker_count")) > 0 or _int(verdict.get("hard_blocker_count")) > 0:
        blockers.append(_blocker("local_delivery_blockers_present", "Local delivery verdict reports P0 or hard blockers."))
    if verdict.get("source_artifacts_all_fingerprinted") is not True:
        blockers.append(_blocker("local_delivery_fingerprints_missing", "Local delivery verdict source artifacts must all be fingerprinted."))

    status = "product_handoff_ready" if not blockers else "blocked_product_handoff"
    summary = {
        "packet_type": "product_readiness_gate",
        "status": status,
        "target_id": _text(normalized.get("target_id")),
        "family": family,
        "ligand_count": _int(normalized.get("ligand_count")),
        "request_contract_status": contract["status"],
        "local_delivery_verdict_path": local_delivery_verdict_path,
        "local_delivery_delivery_ready": _bool(verdict.get("delivery_ready")),
        "local_delivery_verdict": _text(verdict.get("verdict")),
        "local_delivery_p0_blocker_count": _int(verdict.get("p0_blocker_count")),
        "local_delivery_hard_blocker_count": _int(verdict.get("hard_blocker_count")),
        "source_artifacts_all_fingerprinted": verdict.get("source_artifacts_all_fingerprinted") is True,
        "blocker_count": len(blockers),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "execution_approval_token_required": EXECUTION_APPROVAL_TOKEN,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Assemble a scoped local-delivery bundle or explicit execution work order; execution remains disabled until operator approval."
            if status == "product_handoff_ready"
            else "Repair request-contract or local-delivery verdict blockers before product handoff."
        ),
    }
    return {"summary": summary, "blockers": blockers, "request_contract": contract}
