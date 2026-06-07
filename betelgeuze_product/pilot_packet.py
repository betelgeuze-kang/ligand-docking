from __future__ import annotations

from pathlib import Path
from typing import Any

CLAIM_BOUNDARY = (
    "Product pilot packet contract only; it reconciles product handoff evidence, bundle contract, and optional final "
    "bundle validation evidence. It does not run docking, assemble bundles, validate bundles, emit customer wording, "
    "or mutate external state."
)

READY_STATUSES = {"product_pilot_packet_preflight_ready", "product_pilot_packet_ready"}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else (packet if isinstance(packet, dict) else {})


def _validation_summary(packet: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(packet, dict):
        return {}
    summary = packet.get("summary")
    merged = dict(summary) if isinstance(summary, dict) else {}
    for key in ("overall_ok", "delivery_ready_policy_ok", "manifest_signature_ok", "checksum", "blocker_count"):
        if key in packet:
            merged[key] = packet[key]
    return merged


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


def _resolve(root: Path, path_like: str) -> Path:
    path = Path(path_like).expanduser()
    return path if path.is_absolute() else root / path


def _blocker(code: str, reason: str, *, check: str = "") -> dict[str, str]:
    payload = {"code": code, "severity": "hard", "reason": reason}
    if check:
        payload["check"] = check
    return payload


def _warning(code: str, reason: str, *, check: str = "") -> dict[str, str]:
    payload = {"code": code, "severity": "warning", "reason": reason}
    if check:
        payload["check"] = check
    return payload


def _row(check: str, status: str, observed: str, required: str, artifact_path: str = "") -> dict[str, Any]:
    return {
        "check": check,
        "status": status,
        "observed": observed,
        "required": required,
        "artifact_path": artifact_path,
        "execution_enabled": False,
        "action_executed": False,
        "external_state_mutated": False,
    }


def _pass_fail(condition: bool) -> str:
    return "pass" if condition else "fail"


def build_product_pilot_packet_contract(
    *,
    product_readiness_packet: dict[str, Any],
    product_execution_preflight_packet: dict[str, Any],
    product_bundle_contract_packet: dict[str, Any],
    product_delivery_evidence_packet: dict[str, Any],
    bundle_validation_packet: dict[str, Any] | None = None,
    root: str | Path = ".",
    product_readiness_path: str = "runs/product_readiness_gate_current.json",
    product_execution_preflight_path: str = "runs/product_execution_preflight_current.json",
    product_bundle_contract_path: str = "runs/product_bundle_contract_current.json",
    product_delivery_evidence_path: str = "runs/product_delivery_evidence_contract_current.json",
    bundle_validation_path: str = "",
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    readiness = _summary(product_readiness_packet)
    preflight = _summary(product_execution_preflight_packet)
    bundle_contract = _summary(product_bundle_contract_packet)
    delivery_evidence = _summary(product_delivery_evidence_packet)
    validation_packet = bundle_validation_packet or {}
    validation = _validation_summary(validation_packet)

    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []

    product_ready = readiness.get("status") == "product_handoff_ready"
    execution_ready = preflight.get("status") == "product_execution_preflight_ready"
    bundle_contract_ready = bundle_contract.get("status") == "product_bundle_contract_ready"
    delivery_evidence_ready = delivery_evidence.get("status") == "product_delivery_evidence_contract_ready"
    expected_bundle_dir = _text(bundle_contract.get("expected_bundle_dir"))
    bundle_dir_exists = bool(expected_bundle_dir and _resolve(root_path, expected_bundle_dir).is_dir())
    bundle_assembled = _bool(bundle_contract.get("bundle_assembled")) or bundle_dir_exists
    validation_present = bool(validation_packet)
    validation_overall_ok = _bool(validation.get("overall_ok"))
    validation_policy_ok = _bool(validation.get("delivery_ready_policy_ok"))
    validation_manifest_ok = _bool(validation.get("manifest_signature_ok"))
    validation_checksum_ok = _bool(validation.get("checksum", {}).get("ok")) if isinstance(validation.get("checksum"), dict) else False
    bundle_validation_passed = validation_present and validation_overall_ok and validation_policy_ok and validation_manifest_ok and validation_checksum_ok
    delivery_ready_claim_allowed = _bool(delivery_evidence.get("delivery_ready_claim_allowed"))

    checks = [
        ("product_readiness", product_ready, _text(readiness.get("status")), "product_handoff_ready", product_readiness_path),
        ("product_execution_preflight", execution_ready, _text(preflight.get("status")), "product_execution_preflight_ready", product_execution_preflight_path),
        ("product_bundle_contract", bundle_contract_ready, _text(bundle_contract.get("status")), "product_bundle_contract_ready", product_bundle_contract_path),
        ("product_delivery_evidence", delivery_evidence_ready, _text(delivery_evidence.get("status")), "product_delivery_evidence_contract_ready", product_delivery_evidence_path),
        ("bundle_output_location", bool(expected_bundle_dir), expected_bundle_dir, "expected_bundle_dir recorded", product_bundle_contract_path),
    ]
    for check, passed, observed, required, artifact_path in checks:
        rows.append(_row(check, _pass_fail(passed), observed, required, artifact_path))
        if not passed:
            blockers.append(_blocker(f"{check}_not_ready", f"{check} must satisfy: {required}; observed: {observed}", check=check))

    rows.append(
        _row(
            "bundle_finalization",
            "pass" if bundle_validation_passed else "pending",
            f"bundle_dir_exists={bundle_dir_exists} validation_present={validation_present} validation_overall_ok={validation_overall_ok}",
            "assembled bundle plus validator overall_ok=true, delivery_ready_policy_ok=true, manifest_signature_ok=true, checksums ok",
            bundle_validation_path or expected_bundle_dir,
        )
    )

    for label, summary in (("preflight", preflight), ("bundle_contract", bundle_contract), ("delivery_evidence", delivery_evidence)):
        if summary.get("execution_enabled") is not False:
            blockers.append(_blocker(f"{label}_execution_flag_invalid", f"{label} must keep execution_enabled=false."))
        if summary.get("docking_results_emitted") is not False:
            blockers.append(_blocker(f"{label}_results_flag_invalid", f"{label} must keep docking_results_emitted=false."))
        if summary.get("external_state_mutated") is not False:
            blockers.append(_blocker(f"{label}_external_state_flag_invalid", f"{label} must keep external_state_mutated=false."))

    if validation_present and not bundle_dir_exists:
        blockers.append(_blocker("validation_without_bundle_dir", "Bundle validation evidence cannot be accepted when the expected bundle directory is absent.", check="bundle_finalization"))
    if delivery_ready_claim_allowed and not bundle_validation_passed:
        blockers.append(_blocker("delivery_claim_without_final_bundle_validation", "Delivery-ready claims require a passed final bundle validator.", check="bundle_finalization"))
    if not bundle_assembled:
        warnings.append(_warning("pilot_bundle_not_assembled_yet", "Pilot bundle is not assembled; this contract remains preflight-only.", check="bundle_finalization"))
    if not bundle_validation_passed:
        warnings.append(_warning("pilot_bundle_validation_not_passed_yet", "Final bundle validation has not passed; customer handoff remains disallowed.", check="bundle_finalization"))

    pilot_delivery_ready = (
        product_ready
        and execution_ready
        and bundle_contract_ready
        and delivery_evidence_ready
        and delivery_ready_claim_allowed
        and bundle_validation_passed
        and not blockers
    )
    if blockers:
        status = "blocked_product_pilot_packet_contract"
    elif pilot_delivery_ready:
        status = "product_pilot_packet_ready"
    else:
        status = "product_pilot_packet_preflight_ready"

    summary = {
        "packet_type": "product_pilot_packet_contract",
        "status": status,
        "target_id": _text(readiness.get("target_id") or bundle_contract.get("target_id")),
        "family": _text(readiness.get("family") or bundle_contract.get("family")),
        "ligand_count": _int(readiness.get("ligand_count") or bundle_contract.get("ligand_count")),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "expected_bundle_dir": expected_bundle_dir,
        "bundle_dir_exists": bundle_dir_exists,
        "bundle_assembled": bundle_assembled,
        "bundle_validation_present": validation_present,
        "bundle_validation_passed": bundle_validation_passed,
        "delivery_ready_claim_allowed": delivery_ready_claim_allowed,
        "pilot_delivery_ready": pilot_delivery_ready,
        "operator_approval_required": not pilot_delivery_ready,
        "approval_token_required": _text(preflight.get("approval_token_required") or readiness.get("execution_approval_token_required")),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "validated_without_execution": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Pilot packet is ready for final human review and restricted customer handoff."
            if pilot_delivery_ready
            else "Obtain product execution approval, assemble the expected local-delivery bundle, run its validator, then refresh delivery evidence before customer handoff."
        ),
    }
    return {"summary": summary, "blockers": blockers, "warnings": warnings, "rows": rows}
