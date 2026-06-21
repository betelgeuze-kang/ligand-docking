from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-operational"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_OPERATIONAL_QUALITY_ARTIFACT = ROOT / "runs" / "product_operational_quality_contract_current.json"
PRODUCT_SECURITY_DEPLOYMENT_ARTIFACT = ROOT / "runs" / "product_security_deployment_contract_current.json"


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


@router.get("/operational-quality")
async def get_product_operational_quality() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_OPERATIONAL_QUALITY_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_operational_quality_contract",
            "artifact_path": str(PRODUCT_OPERATIONAL_QUALITY_ARTIFACT),
            "operational_quality_ready": False,
            "blocker_count": 1,
            "production_ai_correction_fail_closed_ready": False,
            "production_ai_shadow_abstention_ready": False,
            "production_ai_guarded_active_ready": False,
            "sample_production_ai_inference_subject_active": False,
            "sample_production_ai_correction_applied": False,
            "sample_production_ai_abstention_enforced": False,
            "sample_production_ai_default_residual_mode": "",
            "sample_production_ai_promotion_allowed": False,
            "sample_production_ai_customer_facing_auto_correction_allowed": False,
            "sample_production_ai_customer_facing_score_mutation_allowed": False,
            "sample_production_ai_customer_facing_ranking_mutation_allowed": False,
            "sample_production_ai_trained_checkpoint_count": 0,
            "sample_production_ai_selected_sidecar_ready": False,
            "sample_production_ai_selected_sidecar_missing_output_fields": [],
            "checks": [],
            "blockers": [],
            "input_payload_persisted": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "license_file_written": False,
            "bundle_assembled": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product operational-quality endpoint only; the local operational-quality artifact is missing or invalid. "
                "It does not run docking, persist jobs, emit scientific results, upload data, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_OPERATIONAL_QUALITY_ARTIFACT),
        "operational_quality_ready": bool(summary.get("operational_quality_ready") is True),
        "check_count": int(summary.get("check_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "fail_closed_docking_intake_ready": bool(summary.get("fail_closed_docking_intake_ready") is True),
        "production_ai_correction_fail_closed_ready": bool(
            summary.get("production_ai_correction_fail_closed_ready") is True
        ),
        "production_ai_shadow_abstention_ready": bool(summary.get("production_ai_shadow_abstention_ready") is True),
        "production_ai_guarded_active_ready": bool(summary.get("production_ai_guarded_active_ready") is True),
        "sample_production_ai_inference_subject_active": bool(
            summary.get("sample_production_ai_inference_subject_active") is True
        ),
        "sample_production_ai_correction_applied": bool(summary.get("sample_production_ai_correction_applied") is True),
        "sample_production_ai_abstention_enforced": bool(
            summary.get("sample_production_ai_abstention_enforced") is True
        ),
        "sample_production_ai_default_residual_mode": summary.get("sample_production_ai_default_residual_mode", ""),
        "sample_production_ai_promotion_allowed": bool(summary.get("sample_production_ai_promotion_allowed") is True),
        "sample_production_ai_customer_facing_auto_correction_allowed": bool(
            summary.get("sample_production_ai_customer_facing_auto_correction_allowed") is True
        ),
        "sample_production_ai_customer_facing_score_mutation_allowed": bool(
            summary.get("sample_production_ai_customer_facing_score_mutation_allowed") is True
        ),
        "sample_production_ai_customer_facing_ranking_mutation_allowed": bool(
            summary.get("sample_production_ai_customer_facing_ranking_mutation_allowed") is True
        ),
        "sample_production_ai_trained_checkpoint_count": int(
            summary.get("sample_production_ai_trained_checkpoint_count") or 0
        ),
        "sample_production_ai_selected_sidecar_ready": bool(
            summary.get("sample_production_ai_selected_sidecar_ready") is True
        ),
        "sample_production_ai_selected_sidecar_missing_output_fields": list(
            summary.get("sample_production_ai_selected_sidecar_missing_output_fields") or []
        ),
        "ledger_payload_privacy_ready": bool(summary.get("ledger_payload_privacy_ready") is True),
        "request_traceability_ready": bool(summary.get("request_traceability_ready") is True),
        "scope_limit_enforcement_ready": bool(summary.get("scope_limit_enforcement_ready") is True),
        "heavy_artifact_policy_ready": bool(summary.get("heavy_artifact_policy_ready") is True),
        "input_payload_persisted": bool(summary.get("input_payload_persisted") is True),
        "allowed_scope_families": summary.get("allowed_scope_families", []),
        "max_p0_ligand_count": int(summary.get("max_p0_ligand_count") or 0),
        "sample_request_sha256": summary.get("sample_request_sha256", ""),
        "checks": rows,
        "blockers": blockers,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/security-deployment-contract")
async def get_product_security_deployment_contract() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_SECURITY_DEPLOYMENT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_security_deployment_contract",
            "artifact_path": str(PRODUCT_SECURITY_DEPLOYMENT_ARTIFACT),
            "security_deployment_ready": False,
            "check_count": 0,
            "pass_count": 0,
            "blocker_count": 1,
            "auth_ready": False,
            "tenant_isolation_ready": False,
            "rate_limit_ready": False,
            "tenant_quota_ready": False,
            "payload_limit_ready": False,
            "path_allowlist_ready": False,
            "audit_log_ready": False,
            "audit_retention_ready": False,
            "blocked_request_audit_ready": False,
            "security_headers_ready": False,
            "fail_closed_block_response_ready": False,
            "audit_redaction_ready": False,
            "hosted_external_exposure_guard_ready": False,
            "hosted_external_exposure_allowed": False,
            "hosted_exposure_approval_token_required": "APPROVE_HOSTED_PRODUCT_API_EXPOSURE",
            "hosted_secret_injection_ready": False,
            "tls_termination_operator_verified": False,
            "hosted_secret_injection_operator_verified": False,
            "hosted_tls_termination_operator_verified": False,
            "hosted_deployment_contract_ready": False,
            "hosted_deployment_currently_satisfied": False,
            "hosted_deployment_blocked_stage_count": 0,
            "hosted_deployment_blocked_stage_ids": [],
            "hosted_deployment_next_stage_id": "",
            "hosted_deployment_next_stage_required": "",
            "secret_rotation_contract_ready": False,
            "backup_dr_contract_ready": False,
            "pager_alert_contract_ready": False,
            "middleware_registered": False,
            "sbom_ready": False,
            "container_image_ready": False,
            "metrics_endpoint_ready": False,
            "metrics_secret_free_ready": False,
            "rollback_ready": False,
            "security_policy_ready": False,
            "sbom_rows": [],
            "checks": [],
            "blockers": [],
            "next_required_step": "Run python3 tools/build_product_security_deployment_contract.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product security-deployment-contract endpoint only; the local deployment contract artifact is missing. "
                "It does not start servers, expose APIs, inject secrets, build containers, deploy, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(PRODUCT_SECURITY_DEPLOYMENT_ARTIFACT),
        "security_deployment_ready": bool(summary.get("security_deployment_ready") is True),
        "check_count": int(summary.get("check_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "auth_ready": bool(summary.get("auth_ready") is True),
        "tenant_isolation_ready": bool(summary.get("tenant_isolation_ready") is True),
        "rate_limit_ready": bool(summary.get("rate_limit_ready") is True),
        "tenant_quota_ready": bool(summary.get("tenant_quota_ready") is True),
        "payload_limit_ready": bool(summary.get("payload_limit_ready") is True),
        "path_allowlist_ready": bool(summary.get("path_allowlist_ready") is True),
        "audit_log_ready": bool(summary.get("audit_log_ready") is True),
        "audit_retention_ready": bool(summary.get("audit_retention_ready") is True),
        "blocked_request_audit_ready": bool(summary.get("blocked_request_audit_ready") is True),
        "security_headers_ready": bool(summary.get("security_headers_ready") is True),
        "fail_closed_block_response_ready": bool(summary.get("fail_closed_block_response_ready") is True),
        "audit_redaction_ready": bool(summary.get("audit_redaction_ready") is True),
        "hosted_external_exposure_guard_ready": bool(
            summary.get("hosted_external_exposure_guard_ready") is True
        ),
        "hosted_external_exposure_allowed": bool(summary.get("hosted_external_exposure_allowed") is True),
        "hosted_exposure_approval_token_required": summary.get(
            "hosted_exposure_approval_token_required", ""
        ),
        "hosted_secret_injection_ready": bool(summary.get("hosted_secret_injection_ready") is True),
        "tls_termination_operator_verified": bool(summary.get("tls_termination_operator_verified") is True),
        "hosted_secret_injection_operator_verified": bool(
            summary.get("hosted_secret_injection_operator_verified") is True
        ),
        "hosted_tls_termination_operator_verified": bool(
            summary.get("hosted_tls_termination_operator_verified") is True
        ),
        "hosted_deployment_contract_ready": bool(summary.get("hosted_deployment_contract_ready") is True),
        "hosted_deployment_currently_satisfied": bool(
            summary.get("hosted_deployment_currently_satisfied") is True
        ),
        "hosted_deployment_blocked_stage_count": int(
            summary.get("hosted_deployment_blocked_stage_count") or 0
        ),
        "hosted_deployment_blocked_stage_ids": list(
            summary.get("hosted_deployment_blocked_stage_ids") or []
        ),
        "hosted_deployment_next_stage_id": summary.get("hosted_deployment_next_stage_id", ""),
        "hosted_deployment_next_stage_required": summary.get(
            "hosted_deployment_next_stage_required", ""
        ),
        "secret_rotation_contract_ready": bool(
            summary.get("secret_rotation_contract_ready") is True
        ),
        "backup_dr_contract_ready": bool(summary.get("backup_dr_contract_ready") is True),
        "pager_alert_contract_ready": bool(summary.get("pager_alert_contract_ready") is True),
        "middleware_registered": bool(summary.get("middleware_registered") is True),
        "sbom_ready": bool(summary.get("sbom_ready") is True),
        "container_image_ready": bool(summary.get("container_image_ready") is True),
        "metrics_endpoint_ready": bool(summary.get("metrics_endpoint_ready") is True),
        "metrics_secret_free_ready": bool(summary.get("metrics_secret_free_ready") is True),
        "rollback_ready": bool(summary.get("rollback_ready") is True),
        "security_policy_ready": bool(summary.get("security_policy_ready") is True),
        "sbom_rows": list(summary.get("sbom_rows") or []),
        "checks": rows,
        "blockers": blockers,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
