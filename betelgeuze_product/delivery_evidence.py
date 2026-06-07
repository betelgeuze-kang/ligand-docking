from __future__ import annotations

from typing import Any

CLAIM_BOUNDARY = (
    "Product delivery evidence contract only; it audits current local-delivery evidence and product handoff artifacts. "
    "It does not run docking, assemble bundles, validate completed bundles, emit delivery-ready wording, or mutate external state."
)
ALLOWED_INITIAL_FAMILIES = {"kinase", "gpcr", "ion_channel"}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else (packet if isinstance(packet, dict) else {})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


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


def _check_row(name: str, status: str, observed: str, required: str, artifact_path: str = "") -> dict[str, Any]:
    return {
        "check": name,
        "status": status,
        "observed": observed,
        "required": required,
        "artifact_path": artifact_path,
        "action_executed": False,
        "external_state_mutated": False,
    }


def _pass_fail(condition: bool) -> str:
    return "pass" if condition else "fail"


def build_product_delivery_evidence_contract(
    *,
    product_readiness_packet: dict[str, Any],
    product_execution_preflight_packet: dict[str, Any],
    product_bundle_contract_packet: dict[str, Any],
    local_delivery_verdict_packet: dict[str, Any],
    local_delivery_preflight_packet: dict[str, Any],
    environment_manifest_packet: dict[str, Any],
    requirements_lock_packet: dict[str, Any],
    engine_provenance_packet: dict[str, Any],
    commercialization_queue_packet: dict[str, Any],
    nightly_gate_packet: dict[str, Any],
    wetlab_gate_packet: dict[str, Any],
    product_readiness_path: str = "runs/product_readiness_gate_current.json",
    product_execution_preflight_path: str = "runs/product_execution_preflight_current.json",
    product_bundle_contract_path: str = "runs/product_bundle_contract_current.json",
    local_delivery_verdict_path: str = "runs/local_delivery_verdict_gate_current.json",
    local_delivery_preflight_path: str = "runs/local_delivery_preflight_current.json",
    environment_manifest_path: str = "runs/local_delivery_environment_manifest_current.json",
    requirements_lock_path: str = "runs/local_delivery_requirements_lock_current.json",
    engine_provenance_path: str = "runs/local_delivery_engine_provenance_current.json",
    commercialization_queue_path: str = "runs/local_engine_commercialization_queue_current.json",
    nightly_gate_path: str = "runs/nightly_gate_burndown_packet_current.json",
    wetlab_gate_path: str = "runs/wetlab_selected_allatom_gate_burndown_packet_current.json",
) -> dict[str, Any]:
    readiness = _summary(product_readiness_packet)
    execution_preflight = _summary(product_execution_preflight_packet)
    bundle_contract = _summary(product_bundle_contract_packet)
    verdict = _summary(local_delivery_verdict_packet)
    local_preflight = _summary(local_delivery_preflight_packet)
    environment = _summary(environment_manifest_packet)
    requirements = _summary(requirements_lock_packet)
    engine = _summary(engine_provenance_packet)
    queue = _summary(commercialization_queue_packet)
    nightly = _summary(nightly_gate_packet)
    wetlab = _summary(wetlab_gate_packet)

    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []

    family = _text(readiness.get("family"))
    product_ready = readiness.get("status") == "product_handoff_ready"
    execution_ready = execution_preflight.get("status") == "product_execution_preflight_ready"
    bundle_contract_ready = bundle_contract.get("status") == "product_bundle_contract_ready"
    family_allowed = family in ALLOWED_INITIAL_FAMILIES
    local_delivery_green = (
        verdict.get("delivery_ready") is True
        and verdict.get("verdict") == "delivery_ready"
        and _int(verdict.get("p0_blocker_count")) == 0
        and _int(verdict.get("hard_blocker_count")) == 0
        and verdict.get("source_artifacts_all_fingerprinted") is True
    )
    local_preflight_green = local_preflight.get("overall_ok") is True and local_preflight.get("dry_run") is False
    requirements_complete = (
        _int(requirements.get("missing_count")) == 0
        and _int(requirements.get("blocking_missing_count")) == 0
        and _int(requirements.get("loose_source_requirement_count")) == 0
        and _int(requirements.get("missing_input_file_count")) == 0
        and _int(requirements.get("incomplete_reason_count")) == 0
    )
    environment_complete = (
        environment.get("requirements_lock_complete") is True
        and _text(environment.get("torch_blas_prefer_hipblaslt")) == "0"
        and _int(environment.get("requirements_lock_missing_count")) == 0
    )
    engine_ok = engine.get("provenance_ok") is True and engine.get("existing_engine_reused") is True
    queue_clear = queue.get("queue_clear") is True and _int(queue.get("blocked_count")) == 0
    nightly_green = nightly.get("status") == "nightly_gate_green" and nightly.get("stage6_gate_failed") is False
    wetlab_green = (
        wetlab.get("selected_allatom_wetlab_gate_pass") is True
        and wetlab.get("selected_allatom_final_gate_pass") is True
        and _int(wetlab.get("hard_block_count")) == 0
    )
    bundle_assembled = bundle_contract.get("bundle_assembled") is True
    bundle_validation_passed = bundle_contract.get("bundle_validation_passed") is True
    delivery_ready_claim_allowed = (
        product_ready
        and execution_ready
        and bundle_contract_ready
        and family_allowed
        and local_delivery_green
        and local_preflight_green
        and requirements_complete
        and environment_complete
        and engine_ok
        and queue_clear
        and nightly_green
        and wetlab_green
        and bundle_assembled
        and bundle_validation_passed
    )

    checks = [
        ("product_readiness", product_ready, _text(readiness.get("status")), "product_handoff_ready", product_readiness_path),
        ("product_execution_preflight", execution_ready, _text(execution_preflight.get("status")), "product_execution_preflight_ready", product_execution_preflight_path),
        ("product_bundle_contract", bundle_contract_ready, _text(bundle_contract.get("status")), "product_bundle_contract_ready", product_bundle_contract_path),
        ("restricted_product_family", family_allowed, family, "kinase|gpcr|ion_channel", product_readiness_path),
        ("local_delivery_verdict_gate", local_delivery_green, _text(verdict.get("verdict")), "delivery_ready with p0/hard blockers=0 and fingerprints=true", local_delivery_verdict_path),
        ("local_delivery_preflight", local_preflight_green, f"overall_ok={local_preflight.get('overall_ok')} dry_run={local_preflight.get('dry_run')}", "overall_ok=true dry_run=false", local_delivery_preflight_path),
        ("requirements_lock", requirements_complete, f"missing={requirements.get('missing_count')} incomplete={requirements.get('incomplete_reason_count')}", "no missing/blocking/loose/incomplete requirements", requirements_lock_path),
        ("environment_manifest", environment_complete, f"torch_blas_prefer_hipblaslt={environment.get('torch_blas_prefer_hipblaslt')}", "requirements lock complete and TORCH_BLAS_PREFER_HIPBLASLT=0", environment_manifest_path),
        ("engine_provenance", engine_ok, f"provenance_ok={engine.get('provenance_ok')} existing_engine_reused={engine.get('existing_engine_reused')}", "provenance_ok=true and existing_engine_reused=true", engine_provenance_path),
        ("commercialization_queue", queue_clear, f"queue_clear={queue.get('queue_clear')} blocked_count={queue.get('blocked_count')}", "queue_clear=true blocked_count=0", commercialization_queue_path),
        ("nightly_gate", nightly_green, _text(nightly.get("status")), "nightly_gate_green and stage6_gate_failed=false", nightly_gate_path),
        ("wetlab_selected_allatom_gate", wetlab_green, f"final={wetlab.get('selected_allatom_final_gate_pass')} hard={wetlab.get('hard_block_count')}", "final pass and hard_block_count=0", wetlab_gate_path),
    ]
    for check, passed, observed, required, artifact_path in checks:
        rows.append(_check_row(check, _pass_fail(passed), observed, required, artifact_path))
        if not passed:
            blockers.append(_blocker(f"{check}_not_ready", f"{check} must satisfy: {required}; observed: {observed}", check=check))

    if bundle_contract.get("execution_enabled") is not False:
        blockers.append(_blocker("bundle_contract_execution_flag_invalid", "Product bundle contract must keep execution_enabled=false."))
    if bundle_contract.get("docking_results_emitted") is not False:
        blockers.append(_blocker("bundle_contract_results_flag_invalid", "Product bundle contract must keep docking_results_emitted=false."))
    if bundle_contract.get("external_state_mutated") is not False:
        blockers.append(_blocker("bundle_contract_external_state_invalid", "Product bundle contract must keep external_state_mutated=false."))
    if not bundle_assembled:
        warnings.append(_warning("bundle_not_assembled_yet", "Product bundle has not been assembled; delivery-ready customer wording remains disallowed.", check="bundle_finalization"))
    if not bundle_validation_passed:
        warnings.append(_warning("bundle_validation_not_passed_yet", "Final local-delivery bundle validator has not passed for this product bundle.", check="bundle_finalization"))

    status = "product_delivery_evidence_contract_ready" if not blockers else "blocked_product_delivery_evidence_contract"
    summary = {
        "packet_type": "product_delivery_evidence_contract",
        "status": status,
        "target_id": _text(readiness.get("target_id")),
        "family": family,
        "ligand_count": _int(readiness.get("ligand_count")),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "evidence_check_count": len(rows),
        "evidence_pass_count": sum(1 for row in rows if row["status"] == "pass"),
        "delivery_ready_claim_allowed": delivery_ready_claim_allowed,
        "bundle_assembled": bundle_assembled,
        "bundle_validation_passed": bundle_validation_passed,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "validated_without_execution": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run approved product execution, assemble the local-delivery bundle, and pass the final bundle validator before delivery-ready customer wording."
            if status == "product_delivery_evidence_contract_ready" and not delivery_ready_claim_allowed
            else (
                "Delivery-ready wording is locally claim-allowed for this product bundle; perform final human review before handoff."
                if delivery_ready_claim_allowed
                else "Repair failed evidence checks before treating this product lane as customer-delivery ready."
            )
        ),
    }
    return {"summary": summary, "blockers": blockers, "warnings": warnings, "rows": rows}
